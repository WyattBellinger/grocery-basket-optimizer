"""Declaration-only structured inputs and outputs for a bounded grocery basket."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    OPTIMIZE_BASKET = "optimize_basket"


class Task(Enum):
    OPTIMIZE_GROCERY_BASKET = "optimize-grocery-basket"


class Unit(Enum):
    COUNT = "count"
    MILLILITER = "ml"
    LITER = "l"
    GRAM = "g"
    KILOGRAM = "kg"


class BaseUnit(Enum):
    COUNT = "count"
    MILLILITER = "ml"
    GRAM = "g"


@dataclass
class Requirement(Output):
    item_id: Annotated[str, "Unique requested item, for example eggs, milk, or rice"]
    amount: Annotated[int, "Positive whole units; express fractions in ml or g"]
    unit: Unit
    required_tags: Annotated[list[str], "Every selected package of this item must have all these tags"]


@dataclass
class Package(Output):
    package_id: str
    item_id: str
    amount: Annotated[int, "Amount in one indivisible package"]
    unit: Unit
    price_cents: Annotated[int, "Nonnegative price per package in hundredths of the declared currency"]
    stock: Annotated[int, "Available whole packages, from 0 to 8"]
    tags: Annotated[list[str], "Catalog claims, for example lactose_free; no inferred properties"]


@dataclass
class BasketInput(Output):
    currency: Annotated[str, "One uppercase three-letter currency code; no conversion, tax, or fees"]
    requirements: Annotated[list[Requirement], "At most 6 requirements, with unique item IDs"]
    catalog: Annotated[list[Package], "At most 12 packages; product of (stock + 1) must not exceed 100000"]


@dataclass
class Selection(Output):
    package_id: str
    quantity: Annotated[int, "Positive integer, at most the package stock"]


@dataclass
class Coverage(Output):
    item_id: str
    unit: Annotated[BaseUnit, "Canonical unit: count, ml, or g"]
    required_amount: int
    covered_amount: int
    surplus_amount: int
    satisfied: bool


@dataclass
class BasketOutput(Output):
    feasible: Annotated[bool, "False only if no allowed basket covers every requirement"]
    currency: str
    selections: Annotated[list[Selection], "Unique selected IDs in lexicographic order; zero quantities omitted"]
    coverage: Annotated[list[Coverage], "Every requirement in item_id order, recomputed from the selections"]
    total_cost_cents: Annotated[int | None, "Exact minimum if feasible; null with empty selections if infeasible"]


TOOLS = {Tool.OPTIMIZE_BASKET: (BasketInput, BasketOutput)}
TASKS = {Task.OPTIMIZE_GROCERY_BASKET: (BasketInput, BasketOutput)}
