# Grocery Basket Optimizer

A `nanoagent.plugin/v0001` plugin that chooses minimum-cost whole grocery
packages from a supplied, bounded catalog. An independent deterministic verifier
enumerates every stock combination, checks the returned basket, and proves its
cost is the minimum. No model, network request, or API key is needed to execute
or verify the task. The host's conversational interface uses its own model.

## Tools

| Name | Kind | Purpose |
|---|---|---|
| `optimize_basket` | Tool | Calculate a basket with dynamic programming |
| `optimize-grocery-basket` | Task, runner `tool`, reference `null` | Run the optimizer and independently verify feasibility and minimum cost |

In RUSH Lab, provide a catalog and request, for example:

> I need at least 12 eggs, 2 liters of milk, and 1 kilogram of rice.
> Milk must be lactose-free. Choose the cheapest packages from this catalog.

The exact structured input is [tests/fixtures/example.json](tests/fixtures/example.json).
It is a synthetic catalog, not a claim about actual shop prices or stock.
The hand-calculated answer in [tests/fixtures/expected.json](tests/fixtures/expected.json)
selects two `eggs-6`, two `milk-lf-1l`, and two `rice-600g` packages for **1100 cents
(USD 11.00)**. Coverage is 12 eggs, 2000 ml of lactose-free milk, and 1200 g of
rice, including 200 g surplus rice. Cheaper regular milk is excluded.

The user supplies the catalog. This plugin does not obtain prices, infer product
properties, or translate unlisted brands into packages. Natural-language amounts
and dietary constraints must be mapped to the exact typed input before running.

### Exact specification

- Input has one `currency`, `requirements`, and `catalog`. Currency is three
  uppercase ASCII letters describing a single common currency, whose hundredths
  are called cents here. It is metadata, not a validated ISO registry entry.
  All prices are integer cents, without tax, fees, discounts, or currency conversion.
- Each requirement has a unique `item_id`, positive integer `amount`, `unit`, and
  `required_tags`. Each catalog package has a unique `package_id`, `item_id`,
  positive integer `amount`, `unit`, nonnegative `price_cents`, integer `stock`,
  and `tags`. Fields are required even when lists are empty. Unknown fields fail.
- Units are `count`, `ml`, `l`, `g`, and `kg`. Convert 1 l to 1000 ml and 1 kg to
  1000 g exactly, with no rounding or density conversions. Express fractional
  liters or kilograms as integer ml or g. All rows for one item, including
  unrequested catalog items, must have the same measurement dimension.
- IDs and tags match `[a-z][a-z0-9_-]{0,47}` exactly. Matching is case-sensitive;
  no aliases, trimming, or inferred tags. Each tag list has at most 8 unique tags.
  A package must have **every** tag required by its item. Additional tags are allowed.
- At most 6 requirements and 12 catalog packages. Each normalized amount is
  1..1,000,000 base units; each price is 0..1,000,000 cents; each stock is 0..8.
  The product of `(stock + 1)` across **all** catalog packages must be <= 100,000.
  Invalid or larger instances fail explicitly, rather than using an approximate answer.
- Choose integer package quantities from zero through stock. Selected packages
  must belong to a requested item and meet its tags. Packages cover only their
  own item. There are no bundles, cross-item substitutions, splitting, shared
  budgets, or delivery charges. Overbuying is allowed; stock zero means unavailable.
- A feasible basket covers **at least** each requested amount and has the least
  total catalog cost. Any equal-cost optimum passes verification, regardless
  of surplus or package count. Runtime ties choose fewer packages, then the
  lexicographically smallest quantity vector over eligible IDs for each item.
- Output has `feasible`, the unchanged `currency`, `selections` (unique package
  IDs in lexicographic order, positive quantities only), `coverage` (every
  requirement exactly once in item ID order), and `total_cost_cents`.
  Coverage uses canonical `count`, `ml`, or `g`, and reports `required_amount`,
  actual `covered_amount`, `surplus_amount = max(0, covered - required)`, and
  `satisfied = (covered >= required)`. There is no output rounding.
- If no basket covers everything, output `feasible: false`, `selections: []`,
  and `total_cost_cents: null`. Coverage still lists every requirement with
  its original normalized demand, zero covered/surplus, and `satisfied: false`.
  No partial basket is returned. Empty requirements have the feasible empty
  basket costing zero. An empty catalog is valid, and is infeasible for a
  nonempty requirement list.

### Independent verification

The runtime uses bounded dynamic programming separately for each item, capping
coverage states at the required amount. This decomposition is valid because
packages cover one item, prices add, and no constraint couples items.

The verifier imports no optimizer implementation or runtime constants. It
independently validates semantic constraints and normalizes quantities, visits
the full Cartesian product of stock choices, rejects prohibited selections, and
calculates feasibility and minimum cost from the **original task input**. It
then checks selected IDs, quantities, every coverage field, currency, and actual
cost. It proves an infeasibility claim by exhausting the same search space.
It accepts any optimal basket, not only the runtime's preferred tie.

NanoAgent enforces contract types before verification, statically checks the
verifier, executes it isolated from network/process access, and calls it twice
to enforce identical verdicts. The verifier reads no workspace files, model,
network, clock, or randomness. Unit tests include handwritten answers, corrupted
outputs, malformed/missing values, feasible but nonoptimal baskets, false
infeasibility, ties, free products, unit conversion, dietary constraints,
stock shortages, greedy counterexamples, seeded differential checks, and bounds.

This establishes correctness relative to the supplied catalog and its tag
claims. It does not establish real-world availability, dietary suitability,
or accuracy of natural-language interpretation. The small input bound is
deliberate: exhaustive independent verification is part of the task.

## Layout

```text
nanoagent.yaml             Typed manifest; one tool and one task; no network or write permissions
contract.py               Typed task/tool input and output declarations
LICENSE                   MIT license for the plugin code and synthetic fixtures
pyproject.toml, uv.lock    Independent package and locked dependencies
src/plugin/__main__.py    Typed MCP stdio server
src/plugin/basket.py      Input checks and bounded dynamic programming
verifier/                 Independent validation and exhaustive search
tests/                    Synthetic catalog, handwritten answer, and adversarial tests
ui/                       Standard NanoAgent schema renderer
product/                  Marketplace description and original basket icon
```

Keep run logs, packages, hashes, and milestone evidence outside this repository,
as in the sibling `grocery-basket-optimizer-evidence/` folder. The authoring
checker permits only standard plugin files at the top level. There is no report
in this repository.

## Develop and run

Use Git, uv, and Python 3.12+. Run from this plugin's root:

```bash
uv sync --frozen --extra dev
uv run --frozen pytest -v
uv run --frozen ruff check .
uv run --frozen ruff format --check .
```

`uv.lock` pins exact dependency versions, including the SlimConfig git commit.
Initial setup needs package access; task execution is entirely offline.

With the course repository checked out beside this plugin:

```bash
uv sync --project ../nanoagent/nanoagent
uv run --project ../nanoagent/nanoagent nanoagent plugin inspect "$PWD"
mkdir -p ../grocery-basket-optimizer-evidence
cat > ../grocery-basket-optimizer-evidence/example.yaml <<EOF_CONFIG
_ > nanoagent.cli.plugin.PluginRunConfig:
plugin: "$PWD"
task: optimize-grocery-basket
arguments: "$PWD/tests/fixtures/example.json"
inputs: []
timeout: 60.0
EOF_CONFIG
uv run --project ../nanoagent/nanoagent nanoagent plugin run \
  config="$PWD/../grocery-basket-optimizer-evidence/example.yaml" \
  home="$PWD/../grocery-basket-optimizer-evidence/example-run"
```

Use a new `home` folder for each run. It holds `result.json`, `verdict.json`,
`config.yaml`, `metadata.json`, `run.log`, and an empty `workspace/`. This task
uses `runner: tool`: no model configuration or paid requests are needed. The
RUSH Lab chat can invoke the same task through the host's agent.

Package separately from source:

```bash
uv run --project ../nanoagent/nanoagent nanoagent plugin pack \
  "$PWD" "$PWD/../grocery-basket-optimizer-evidence/grocery-basket-optimizer.tar.gz"
```

### Publication and desktop validation still required

This is an independent plugin folder prepared for its own GitHub repository.
Local checks do not constitute marketplace publication or an interactive RUSH
Lab test. After reviewing the implementation, create the public repository,
push the source, publish with the authenticated RUSH CLI, install the package,
and run the example in the desktop app. Record that result and verifier verdict
before claiming full milestone completion. Submit the actual GitHub URL with
the other tasks. The report is intentionally deferred.
