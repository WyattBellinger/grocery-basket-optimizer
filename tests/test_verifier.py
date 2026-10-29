import copy

import pytest
from slimconfig import build_output, plain_output

import verifier
from contract import BasketInput, BasketOutput
from plugin.basket import optimize_basket


def check(arguments, output):
    return verifier.verify_task(
        "optimize-grocery-basket",
        build_output(arguments, BasketInput),
        build_output(output, BasketOutput),
        None,
        "unused",
    )


def empty_result(expected):
    expected.update(feasible=False, selections=[], total_cost_cents=None)
    for row in expected["coverage"]:
        row.update(covered_amount=0, surplus_amount=0, satisfied=False)
    return expected


def test_accepts_handwritten_answer_and_reports_independent_optimum(arguments, expected):
    result = check(arguments, expected)
    assert result["valid"]
    assert result["details"] == {"minimum_cost_cents": 1100, "combinations_examined": 864}


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_selection",
        "unknown_package",
        "duplicate_selection",
        "selection_order",
        "zero_quantity",
        "negative_quantity",
        "over_stock",
        "wrong_cost",
        "negative_cost",
        "missing_cost",
        "currency",
        "coverage_missing",
        "coverage_extra",
        "coverage_duplicate",
        "coverage_order",
        "coverage_unit",
        "coverage_required",
        "coverage_actual",
        "coverage_surplus",
        "coverage_satisfied",
        "feasible_flag",
    ],
)
def test_rejects_corrupted_answer(arguments, expected, mutation):
    if mutation == "missing_selection":
        expected["selections"].pop()
    elif mutation == "unknown_package":
        expected["selections"][0]["package_id"] = "fiction"
    elif mutation == "duplicate_selection":
        expected["selections"].append(copy.deepcopy(expected["selections"][0]))
    elif mutation == "selection_order":
        expected["selections"].reverse()
    elif mutation in ("zero_quantity", "negative_quantity", "over_stock"):
        expected["selections"][0]["quantity"] = {"zero_quantity": 0, "negative_quantity": -1, "over_stock": 3}[mutation]
    elif mutation in ("wrong_cost", "negative_cost", "missing_cost"):
        expected["total_cost_cents"] = {"wrong_cost": 1099, "negative_cost": -1100, "missing_cost": None}[mutation]
    elif mutation == "currency":
        expected["currency"] = "EUR"
    elif mutation == "coverage_missing":
        expected["coverage"].pop()
    elif mutation == "coverage_extra":
        expected["coverage"].append({**expected["coverage"][0], "item_id": "tea"})
    elif mutation == "coverage_duplicate":
        expected["coverage"].append(copy.deepcopy(expected["coverage"][0]))
    elif mutation == "coverage_order":
        expected["coverage"].reverse()
    elif mutation == "coverage_unit":
        expected["coverage"][0]["unit"] = "g"
    elif mutation == "coverage_satisfied":
        expected["coverage"][0]["satisfied"] = False
    elif mutation == "feasible_flag":
        expected["feasible"] = False
    else:
        field = {
            "coverage_required": "required_amount",
            "coverage_actual": "covered_amount",
            "coverage_surplus": "surplus_amount",
        }[mutation]
        expected["coverage"][0][field] += 1
    assert not check(arguments, expected)["valid"]


def test_rejects_feasible_but_more_expensive_basket(arguments, expected):
    expected["selections"][0] = {"package_id": "eggs-12", "quantity": 1}
    expected["total_cost_cents"] += 30
    result = check(arguments, expected)
    assert not result["valid"]
    assert result["message"] == "feasible basket is not minimum cost"
    assert result["details"]["minimum_cost_cents"] == 1100


def test_rejects_cheap_milk_without_required_tag(arguments, expected):
    expected["selections"][1] = {"package_id": "milk-regular-2l", "quantity": 1}
    expected["total_cost_cents"] -= 280
    assert not check(arguments, expected)["valid"]


def test_rejects_unrequested_even_free_package(arguments, expected):
    arguments["catalog"].append(
        {"package_id": "tea", "item_id": "tea", "amount": 1, "unit": "count", "price_cents": 0, "stock": 1, "tags": []}
    )
    expected["selections"].append({"package_id": "tea", "quantity": 1})
    assert not check(arguments, expected)["valid"]


def test_rejects_truthfully_reported_undercoverage(arguments, expected):
    expected["selections"][0]["quantity"] = 1
    expected["total_cost_cents"] -= 190
    expected["coverage"][0].update(covered_amount=6, satisfied=False)
    assert not check(arguments, expected)["valid"]


def test_false_infeasibility_is_rejected(arguments, expected):
    result = check(arguments, empty_result(expected))
    assert not result["valid"]
    assert result["details"]["minimum_cost_cents"] == 1100


def test_accepts_proven_infeasibility(arguments, expected):
    arguments["catalog"] = [row for row in arguments["catalog"] if row["item_id"] != "milk"]
    result = check(arguments, empty_result(expected))
    assert result["valid"]
    assert result["details"]["minimum_cost_cents"] is None


@pytest.mark.parametrize("mutation", ["numeric_cost", "nonempty_selection", "true_flag", "partial_coverage"])
def test_infeasible_output_must_be_canonical(arguments, expected, mutation):
    arguments["catalog"] = []
    empty_result(expected)
    if mutation == "numeric_cost":
        expected["total_cost_cents"] = 0
    elif mutation == "nonempty_selection":
        expected["selections"] = [{"package_id": "eggs-6", "quantity": 1}]
    elif mutation == "true_flag":
        expected["feasible"] = True
    else:
        expected["coverage"][0]["covered_amount"] = 6
    assert not check(arguments, expected)["valid"]


def test_ties_accept_any_minimum_even_with_different_package_counts():
    value = {
        "currency": "USD",
        "requirements": [{"item_id": "eggs", "amount": 2, "unit": "count", "required_tags": []}],
        "catalog": [
            {
                "package_id": "a",
                "item_id": "eggs",
                "amount": 1,
                "unit": "count",
                "price_cents": 100,
                "stock": 2,
                "tags": [],
            },
            {
                "package_id": "b",
                "item_id": "eggs",
                "amount": 2,
                "unit": "count",
                "price_cents": 200,
                "stock": 1,
                "tags": [],
            },
        ],
    }
    output = {
        "feasible": True,
        "currency": "USD",
        "selections": [{"package_id": "a", "quantity": 2}],
        "coverage": [
            {
                "item_id": "eggs",
                "unit": "count",
                "required_amount": 2,
                "covered_amount": 2,
                "surplus_amount": 0,
                "satisfied": True,
            }
        ],
        "total_cost_cents": 200,
    }
    assert check(value, output)["valid"]
    output["selections"] = [{"package_id": "b", "quantity": 1}]
    assert check(value, output)["valid"]


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("currency",), "usd"),
        (("currency",), "US"),
        (("requirements", 0, "item_id"), ""),
        (("requirements", 0, "item_id"), " eggs"),
        (("requirements", 0, "item_id"), "a" * 49),
        (("requirements", 0, "amount"), 0),
        (("requirements", 0, "amount"), -1),
        (("requirements", 0, "amount"), 1_000_001),
        (("requirements", 1, "amount"), 1001),
        (("requirements", 0, "required_tags"), ["x", "x"]),
        (("requirements", 0, "required_tags"), ["Lactose-Free"]),
        (("requirements", 0, "required_tags"), [f"t{i}" for i in range(9)]),
        (("catalog", 0, "package_id"), ""),
        (("catalog", 0, "item_id"), ""),
        (("catalog", 0, "package_id"), "a" * 49),
        (("catalog", 0, "amount"), 0),
        (("catalog", 0, "amount"), 1_000_001),
        (("catalog", 0, "price_cents"), -1),
        (("catalog", 0, "price_cents"), 1_000_001),
        (("catalog", 0, "stock"), -1),
        (("catalog", 0, "stock"), 9),
        (("catalog", 0, "tags"), [""]),
        (("catalog", 0, "tags"), ["x", "x"]),
        (("catalog", 0, "tags"), [f"t{i}" for i in range(9)]),
        (("catalog", 0, "unit"), "g"),
    ],
)
def test_semantically_invalid_inputs_fail_both_implementations(arguments, tmp_path, path, replacement):
    target = arguments
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement
    given = build_output(arguments, BasketInput)
    assert not verifier.verify_input("optimize_basket", given)["valid"]
    with pytest.raises(ValueError):
        optimize_basket(given, tmp_path)


@pytest.mark.parametrize("mutation", ["duplicate_item", "duplicate_package", "too_many_items", "too_many_packages"])
def test_duplicate_and_list_bounds(arguments, tmp_path, mutation):
    if mutation == "duplicate_item":
        arguments["requirements"].append(copy.deepcopy(arguments["requirements"][0]))
    elif mutation == "duplicate_package":
        arguments["catalog"].append(copy.deepcopy(arguments["catalog"][0]))
    elif mutation == "too_many_items":
        arguments["requirements"] = [{**arguments["requirements"][0], "item_id": f"item{i}"} for i in range(7)]
    else:
        arguments["catalog"] = [{**arguments["catalog"][0], "package_id": f"p{i}"} for i in range(13)]
    given = build_output(arguments, BasketInput)
    assert not verifier.verify_input("optimize_basket", given)["valid"]
    with pytest.raises(ValueError):
        optimize_basket(given, tmp_path)


def test_search_bound_inclusive_and_rejected_above(tmp_path):
    value = {
        "currency": "USD",
        "requirements": [],
        "catalog": [
            {
                "package_id": f"p{i}",
                "item_id": "eggs",
                "amount": 1,
                "unit": "count",
                "price_cents": 1,
                "stock": 1 if i < 5 else 4,
                "tags": [],
            }
            for i in range(10)
        ],
    }
    given = build_output(value, BasketInput)
    made = optimize_basket(given, tmp_path)
    checked = verifier.verify_task("optimize-grocery-basket", given, made, None, tmp_path)
    assert checked["valid"]
    assert checked["details"]["combinations_examined"] == 100_000
    value["catalog"][-1]["stock"] = 5
    given = build_output(value, BasketInput)
    assert not verifier.verify_input("optimize_basket", given)["valid"]
    with pytest.raises(ValueError):
        optimize_basket(given, tmp_path)


def test_maximum_list_lengths_are_accepted(tmp_path):
    value = {
        "currency": "USD",
        "requirements": [{"item_id": f"item{i}", "amount": 1, "unit": "count", "required_tags": []} for i in range(6)],
        "catalog": [
            {
                "package_id": f"p{i}",
                "item_id": f"item{i % 6}",
                "amount": 1,
                "unit": "count",
                "price_cents": 1,
                "stock": 0,
                "tags": [],
            }
            for i in range(12)
        ],
    }
    given = build_output(value, BasketInput)
    assert verifier.verify_input("optimize_basket", given)["valid"]
    assert not optimize_basket(given, tmp_path).feasible


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("catalog", 0, "price_cents"), True),
        (("catalog", 0, "price_cents"), 1.5),
        (("catalog", 0, "price_cents"), "190"),
        (("catalog", 0, "stock"), False),
        (("catalog", 0, "stock"), 1.0),
        (("catalog", 0, "tags"), "lactose_free"),
        (("requirements", 0, "amount"), True),
        (("requirements", 0, "amount"), 1.5),
        (("requirements", 0, "amount"), None),
        (("requirements", 0, "unit"), "dozen"),
        (("requirements",), None),
        (("catalog",), {}),
    ],
)
def test_contract_rejects_malformed_input(arguments, path, replacement):
    target = arguments
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement
    with pytest.raises(ValueError):
        build_output(arguments, BasketInput)


def test_contract_rejects_missing_and_extra_input_fields(arguments):
    del arguments["catalog"][0]["price_cents"]
    with pytest.raises(ValueError):
        build_output(arguments, BasketInput)
    arguments["catalog"][0]["price_cents"] = 190
    arguments["budget"] = 1000
    with pytest.raises(ValueError):
        build_output(arguments, BasketInput)


@pytest.mark.parametrize("output", [None, {}, {"feasible": True}, {"selections": []}])
def test_contract_rejects_missing_output(output):
    with pytest.raises(ValueError):
        build_output(output, BasketOutput)


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("feasible",), "true"),
        (("feasible",), 1),
        (("total_cost_cents",), True),
        (("total_cost_cents",), 11.0),
        (("total_cost_cents",), "1100"),
        (("selections",), None),
        (("selections", 0, "quantity"), 1.5),
        (("selections", 0, "quantity"), True),
        (("coverage",), None),
        (("coverage", 0, "unit"), "l"),
        (("coverage", 0, "covered_amount"), 12.0),
    ],
)
def test_contract_rejects_malformed_output(expected, path, replacement):
    target = expected
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement
    with pytest.raises(ValueError):
        build_output(expected, BasketOutput)


def test_extra_output_fields_fail_contract(expected):
    expected["optimal"] = True
    with pytest.raises(ValueError):
        build_output(expected, BasketOutput)


def test_entrypoints_and_determinism(arguments, expected):
    given = build_output(arguments, BasketInput)
    made = build_output(expected, BasketOutput)
    result = check(arguments, expected)
    assert result == check(arguments, expected)
    assert result == verifier.verify_output("optimize_basket", given, made, "unused")
    assert verifier.verify_input("optimize_basket", given)["valid"]
    assert not verifier.verify_input("unknown", given)["valid"]
    assert not verifier.verify_output("unknown", given, made, "unused")["valid"]
    assert not verifier.verify_task("unknown", given, made, None, "unused")["valid"]
    assert plain_output(given) == arguments  # Verification does not rewrite task inputs.
