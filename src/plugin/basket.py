"""Bounded dynamic programming; the verifier uses a separate exhaustive algorithm."""

import re
from pathlib import Path

from contract import BaseUnit, BasketInput, BasketOutput, Coverage, Selection

UNITS = {
    "count": (BaseUnit.COUNT, 1),
    "ml": (BaseUnit.MILLILITER, 1),
    "l": (BaseUnit.MILLILITER, 1000),
    "g": (BaseUnit.GRAM, 1),
    "kg": (BaseUnit.GRAM, 1000),
}
TOKEN = re.compile(r"[a-z][a-z0-9_-]{0,47}")


def validate_input(value: BasketInput) -> None:
    if not re.fullmatch(r"[A-Z]{3}", value.currency):
        raise ValueError("currency must be three uppercase letters")
    if len(value.requirements) > 6 or len(value.catalog) > 12:
        raise ValueError("at most 6 requirements and 12 catalog packages are allowed")
    for rows, field in ((value.requirements, "item_id"), (value.catalog, "package_id")):
        identifiers = [getattr(row, field) for row in rows]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError(f"{field} must be unique")
    dimensions = {}
    combinations = 1
    for row in [*value.requirements, *value.catalog]:
        if not TOKEN.fullmatch(row.item_id):
            raise ValueError("item IDs must be lowercase tokens of at most 48 characters")
        unit, scale = UNITS[row.unit.value]
        if not 1 <= row.amount * scale <= 1_000_000:
            raise ValueError("amounts must normalize to 1 through 1000000 base units")
        if row.item_id in dimensions and dimensions[row.item_id] != unit:
            raise ValueError("an item must use one compatible measurement dimension")
        dimensions[row.item_id] = unit
    for tags in [*(row.required_tags for row in value.requirements), *(row.tags for row in value.catalog)]:
        if len(tags) > 8 or len(tags) != len(set(tags)) or any(not TOKEN.fullmatch(tag) for tag in tags):
            raise ValueError("tags must be at most 8 unique lowercase tokens")
    for package in value.catalog:
        if not TOKEN.fullmatch(package.package_id):
            raise ValueError("package IDs must be lowercase tokens of at most 48 characters")
        if not 0 <= package.stock <= 8 or not 0 <= package.price_cents <= 1_000_000:
            raise ValueError("stock must be 0..8 and price_cents must be 0..1000000")
        combinations *= package.stock + 1
    if combinations > 100_000:
        raise ValueError("catalog exceeds 100000 stock combinations")


def optimize_basket(value: BasketInput, workspace: Path) -> BasketOutput:
    """Minimize additive cost independently per item, capping DP coverage at demand."""
    validate_input(value)
    chosen = {}
    feasible = True
    for requirement in sorted(value.requirements, key=lambda row: row.item_id):
        need = requirement.amount * UNITS[requirement.unit.value][1]
        packages = sorted(
            (
                row
                for row in value.catalog
                if row.item_id == requirement.item_id and set(requirement.required_tags) <= set(row.tags)
            ),
            key=lambda row: row.package_id,
        )
        # State: capped coverage -> (cost, package count, quantity vector).
        # Secondary keys make the runtime repeatable, but are not verifier objectives.
        states = {0: (0, 0, ())}
        for package in packages:
            following = {}
            amount = package.amount * UNITS[package.unit.value][1]
            for covered, (cost, count, quantities) in states.items():
                for quantity in range(package.stock + 1):
                    total = min(need, covered + amount * quantity)
                    candidate = (cost + package.price_cents * quantity, count + quantity, (*quantities, quantity))
                    if total not in following or candidate < following[total]:
                        following[total] = candidate
            states = following
        if need not in states:
            feasible = False
            break
        for package, quantity in zip(packages, states[need][2]):
            if quantity:
                chosen[package.package_id] = quantity
    if not feasible:
        chosen = {}
    catalog = {row.package_id: row for row in value.catalog}
    coverage = []
    for requirement in sorted(value.requirements, key=lambda row: row.item_id):
        unit, scale = UNITS[requirement.unit.value]
        need = requirement.amount * scale
        covered = sum(
            quantity * catalog[identifier].amount * UNITS[catalog[identifier].unit.value][1]
            for identifier, quantity in chosen.items()
            if catalog[identifier].item_id == requirement.item_id
        )
        coverage.append(Coverage(requirement.item_id, unit, need, covered, max(0, covered - need), covered >= need))
    cost = sum(catalog[identifier].price_cents * quantity for identifier, quantity in chosen.items())
    return BasketOutput(
        feasible=feasible,
        currency=value.currency,
        selections=[Selection(identifier, chosen[identifier]) for identifier in sorted(chosen)],
        coverage=coverage,
        total_cost_cents=cost if feasible else None,
    )
