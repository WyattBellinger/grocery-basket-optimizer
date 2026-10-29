import copy
import random

from slimconfig import build_output, plain_output

import verifier
from contract import BasketInput
from plugin.basket import optimize_basket


def solve(arguments, tmp_path):
    return plain_output(optimize_basket(build_output(arguments, BasketInput), tmp_path))


def tiny(amount=12, stock=2):
    return {
        "currency": "USD",
        "requirements": [{"item_id": "eggs", "amount": amount, "unit": "count", "required_tags": []}],
        "catalog": [
            {
                "package_id": "eggs-6",
                "item_id": "eggs",
                "amount": 6,
                "unit": "count",
                "price_cents": 190,
                "stock": stock,
                "tags": [],
            }
        ],
    }


def test_example_matches_hand_calculation(arguments, expected, tmp_path):
    assert solve(arguments, tmp_path) == expected
    assert list(tmp_path.iterdir()) == []


def test_not_greedy_by_unit_price(tmp_path):
    value = tiny()
    value["catalog"].append({**value["catalog"][0], "package_id": "eggs-10", "amount": 10, "price_cents": 250})
    result = solve(value, tmp_path)
    assert result["selections"] == [{"package_id": "eggs-6", "quantity": 2}]
    assert result["total_cost_cents"] == 380  # Cheaper-per-egg 10-packs would cost 500.


def test_mixed_packages_beat_repeating_either(tmp_path):
    value = tiny(amount=10)
    value["catalog"][0].update(price_cents=200)
    value["catalog"].append({**value["catalog"][0], "package_id": "eggs-4", "amount": 4, "price_cents": 150})
    result = solve(value, tmp_path)
    assert result["total_cost_cents"] == 350
    assert result["selections"] == [{"package_id": "eggs-4", "quantity": 1}, {"package_id": "eggs-6", "quantity": 1}]


def test_stock_limit_changes_optimum(tmp_path):
    value = tiny(amount=12, stock=1)
    value["catalog"].append({**value["catalog"][0], "package_id": "eggs-12", "amount": 12, "price_cents": 410})
    assert solve(value, tmp_path)["selections"] == [{"package_id": "eggs-12", "quantity": 1}]


def test_free_and_zero_stock(tmp_path):
    value = tiny()
    value["catalog"][0]["price_cents"] = 0
    assert solve(value, tmp_path)["total_cost_cents"] == 0
    value["catalog"][0]["stock"] = 0
    assert solve(value, tmp_path)["feasible"] is False


def test_missing_item_and_empty_catalog(tmp_path):
    value = tiny()
    value["catalog"] = []
    result = solve(value, tmp_path)
    assert result["feasible"] is False
    assert result["total_cost_cents"] is None
    assert result["selections"] == []
    assert result["coverage"][0]["covered_amount"] == 0


def test_infeasible_does_not_return_partial_basket(arguments, tmp_path):
    arguments["catalog"] = [row for row in arguments["catalog"] if row["item_id"] != "rice"]
    result = solve(arguments, tmp_path)
    assert result["feasible"] is False
    assert result["selections"] == []
    assert all(row["covered_amount"] == 0 and row["satisfied"] is False for row in result["coverage"])


def test_empty_requirements_even_with_unrelated_free_products(tmp_path):
    value = tiny()
    value["requirements"] = []
    value["catalog"][0]["price_cents"] = 0
    assert solve(value, tmp_path) == {
        "feasible": True,
        "currency": "USD",
        "selections": [],
        "coverage": [],
        "total_cost_cents": 0,
    }


def test_every_required_tag_is_needed(tmp_path):
    value = tiny()
    value["requirements"][0]["required_tags"] = ["organic", "free_range"]
    value["catalog"][0]["tags"] = ["organic"]
    assert solve(value, tmp_path)["feasible"] is False
    value["catalog"][0]["tags"].append("free_range")
    assert solve(value, tmp_path)["feasible"] is True


def test_permutations_do_not_change_runtime_answer(arguments, expected, tmp_path):
    arguments["requirements"].reverse()
    arguments["catalog"].reverse()
    assert solve(arguments, tmp_path) == expected


def test_exact_lower_and_upper_numeric_boundaries(tmp_path):
    value = tiny(amount=1_000_000, stock=8)
    value["catalog"][0].update(amount=1_000_000, price_cents=1_000_000)
    result = solve(value, tmp_path)
    assert result["total_cost_cents"] == 1_000_000
    value["requirements"][0]["amount"] = 1
    value["catalog"][0].update(amount=1, price_cents=0)
    assert solve(value, tmp_path)["total_cost_cents"] == 0


def test_dp_agrees_with_exhaustive_verifier_on_generated_cases(tmp_path):
    # Fixed seed covers multiple items, unit scales, tags, free products, and shortages.
    rng = random.Random(480)
    for _ in range(100):
        value = {"currency": "USD", "requirements": [], "catalog": []}
        for index, (item, units) in enumerate((("eggs", ["count"]), ("milk", ["ml", "l"]))):
            value["requirements"].append(
                {
                    "item_id": item,
                    "amount": rng.randint(1, 12),
                    "unit": units[0],
                    "required_tags": ["special"] if rng.randrange(2) else [],
                }
            )
            for package in range(rng.randint(0, 3)):
                value["catalog"].append(
                    {
                        "package_id": f"p{index}-{package}",
                        "item_id": item,
                        "amount": rng.randint(1, 8),
                        "unit": rng.choice(units),
                        "price_cents": rng.randint(0, 500),
                        "stock": rng.randint(0, 2),
                        "tags": ["special"] if rng.randrange(2) else [],
                    }
                )
        given = build_output(copy.deepcopy(value), BasketInput)
        made = optimize_basket(given, tmp_path)
        checked = verifier.verify_task("optimize-grocery-basket", given, made, None, tmp_path)
        assert checked["valid"], (value, plain_output(made), checked)
