"""Independent full Cartesian enumeration, exact integer arithmetic, no files or models."""

import itertools
import re


def verdict(valid, message, **details):
    return {"valid": valid, "score": float(valid), "message": message, "details": details}


def normalized(amount, unit):
    if unit.value == "l":
        return amount * 1000, "ml"
    if unit.value == "kg":
        return amount * 1000, "g"
    return amount, unit.value


def token(value):
    return re.fullmatch(r"[a-z][a-z0-9_-]{0,47}", value) is not None


def check_input(value):
    if re.fullmatch(r"[A-Z]{3}", value.currency) is None:
        return verdict(False, "invalid currency code")
    if len(value.requirements) > 6 or len(value.catalog) > 12:
        return verdict(False, "too many requirements or catalog packages")
    items = [row.item_id for row in value.requirements]
    identifiers = [row.package_id for row in value.catalog]
    if len(set(items)) != len(items) or len(set(identifiers)) != len(identifiers):
        return verdict(False, "duplicate requirement item or package ID")
    dimensions = {}
    for row in [*value.requirements, *value.catalog]:
        amount, dimension = normalized(row.amount, row.unit)
        if not token(row.item_id) or not 1 <= amount <= 1_000_000:
            return verdict(False, "invalid item ID or normalized amount")
        if row.item_id in dimensions and dimension != dimensions[row.item_id]:
            return verdict(False, "incompatible units for one item")
        dimensions[row.item_id] = dimension
    tag_lists = [row.required_tags for row in value.requirements] + [row.tags for row in value.catalog]
    for tags in tag_lists:
        if len(tags) > 8 or len(set(tags)) != len(tags) or not all(token(tag) for tag in tags):
            return verdict(False, "invalid or duplicate tags")
    combinations = 1
    for row in value.catalog:
        if not token(row.package_id) or not 0 <= row.stock <= 8 or not 0 <= row.price_cents <= 1_000_000:
            return verdict(False, "invalid package ID, stock, or price")
        combinations *= row.stock + 1
    if combinations > 100_000:
        return verdict(False, "more than 100000 stock combinations")
    return verdict(True, "input is valid", stock_combinations=combinations)


def minimum_cost(arguments):
    """Visit every stock vector, including zero, and calculate feasibility from input alone."""
    requirements = sorted(arguments.requirements, key=lambda row: row.item_id)
    indices = {row.item_id: index for index, row in enumerate(requirements)}
    needs = [normalized(row.amount, row.unit)[0] for row in requirements]
    packages = []
    for row in arguments.catalog:
        index = indices.get(row.item_id)
        allowed = index is not None and all(tag in row.tags for tag in requirements[index].required_tags)
        packages.append((index, normalized(row.amount, row.unit)[0], row.price_cents, allowed))
    best = None
    examined = 0
    for quantities in itertools.product(*(range(row.stock + 1) for row in arguments.catalog)):
        examined += 1
        covered = [0] * len(needs)
        cost = 0
        allowed = True
        for quantity, (index, amount, price, eligible) in zip(quantities, packages):
            if quantity:
                if not eligible:
                    allowed = False
                    break
                covered[index] += amount * quantity
                cost += price * quantity
        if allowed and all(have >= need for have, need in zip(covered, needs)) and (best is None or cost < best):
            best = cost
    return best, examined


def check_result(arguments, output):
    checked = check_input(arguments)
    if not checked["valid"]:
        return checked
    if output.currency != arguments.currency:
        return verdict(False, "currency differs from input")
    requirements = {row.item_id: row for row in arguments.requirements}
    catalog = {row.package_id: row for row in arguments.catalog}
    identifiers = [row.package_id for row in output.selections]
    if identifiers != sorted(set(identifiers)):
        return verdict(False, "selection IDs must be unique and sorted")
    covered = {item: 0 for item in requirements}
    cost = 0
    for selection in output.selections:
        if selection.package_id not in catalog:
            return verdict(False, "unknown package ID")
        package = catalog[selection.package_id]
        if not 1 <= selection.quantity <= package.stock:
            return verdict(False, "quantity must be positive and within stock")
        if package.item_id not in requirements:
            return verdict(False, "selected package is not a requested item")
        if not all(tag in package.tags for tag in requirements[package.item_id].required_tags):
            return verdict(False, "selected package violates required tags")
        covered[package.item_id] += selection.quantity * normalized(package.amount, package.unit)[0]
        cost += selection.quantity * package.price_cents
    if [row.item_id for row in output.coverage] != sorted(requirements):
        return verdict(False, "coverage must list every requirement once in sorted order")
    for row in output.coverage:
        requirement = requirements[row.item_id]
        need, unit = normalized(requirement.amount, requirement.unit)
        have = covered[row.item_id]
        if (row.unit.value, row.required_amount, row.covered_amount, row.surplus_amount, row.satisfied) != (
            unit,
            need,
            have,
            max(0, have - need),
            have >= need,
        ):
            return verdict(False, "coverage differs from independently calculated amounts", item_id=row.item_id)
    optimum, examined = minimum_cost(arguments)
    if optimum is None:
        if output.feasible or output.selections or output.total_cost_cents is not None:
            return verdict(False, "infeasible input requires false, empty selections, null cost, and zero coverage")
        return verdict(
            True, "exhaustive search proves infeasibility", combinations_examined=examined, minimum_cost_cents=None
        )
    if not output.feasible or output.total_cost_cents is None:
        return verdict(False, "a feasible basket exists", minimum_cost_cents=optimum)
    if any(covered[item] < normalized(row.amount, row.unit)[0] for item, row in requirements.items()):
        return verdict(False, "selected basket does not cover every requirement")
    if output.total_cost_cents != cost:
        return verdict(False, "reported cost differs from catalog arithmetic", actual_cost_cents=cost)
    if cost != optimum:
        return verdict(False, "feasible basket is not minimum cost", minimum_cost_cents=optimum, actual_cost_cents=cost)
    return verdict(
        True,
        "feasible basket has independently proven minimum cost",
        minimum_cost_cents=optimum,
        combinations_examined=examined,
    )
