# Matched-store pilot contract (v1)

This contract is for a **store-randomized, matched-pair** price-promotion
pilot. One store in each pair is assigned to the promotion for every post
week; the other remains at regular price. The pre-period has no promotion.
Assignment must be recorded before outcomes are seen. The application can
check the file's structure and execution flags, but cannot prove the original
assignment was truly randomized.

## Grain and fields

One row per `store_id × week_index`, with no duplicates. A pair contains
exactly two stores and all stores share the same weekly calendar.

| Field | Contract |
| --- | --- |
| `product_id` | Stable nonempty product ID; this v1 pilot contains one product. |
| `store_id`, `pair_id` | Stable nonempty IDs; each store belongs to one pair. |
| `week_index` | Integer; negative values are pre-period, zero and above are post-period. |
| `week_start` | ISO date for the start of a seven-day sales week. |
| `period` | `pre` or `post`, consistent with `week_index`. |
| `assigned_promo` | Fixed 0/1 assignment by store; one treated store per pair. |
| `executed_promo` | 0 in pre-period; equals assignment in post-period. |
| `units` | Nonnegative units sold in that store-week. |
| `regular_price`, `observed_price`, `unit_cost` | Dollars per unit. Positive prices; nonnegative cost. |
| `available_units` | Units available to sell in that week; cannot be below sales. |
| `stockout` | 0/1; any stockout blocks estimation because sales censor demand. |
| `source_published_at` | ISO timestamp with timezone, after the sales week closed. |
| `ingested_at` | ISO timestamp with timezone, no earlier than source publication. |

There must be at least four pairs, four pre weeks, and four post weeks.
This v1 estimator also requires one common regular price and one common
promoted price. The app blocks transferring a pilot lift to a scenario with
a different product, shelf price, or discount. Matching these does not prove
the result transports to new stores, dates, displays, or product mixes.
`source_published_at` identifies when source data became available;
`ingested_at` identifies when this pipeline received it. `week_start` is
event time. The quality gate rejects rows ingested after the analysis run's
recorded UTC as-of time.
For this fixed synthetic demo, all rows are historical and available before
analysis. A real pipeline also needs correction/version history and an
immutable assignment log. Do not select stores, weeks, or outcomes using
post-treatment results.

## Estimand and method

The estimand is the average incremental unit lift for these assigned store
pairs and weeks under this promotion package. It is not a universal price
elasticity. For each pair, calculate the change in the treated-minus-control
weekly unit gap from pre to post. Divide incremental units by the treated
store's estimated post units without promotion. A random-effects
normal-normal empirical-Bayes approximation pools the noisy pair estimates;
pair bootstrap resampling gives an approximate 90% interval. The app displays
the unadjusted post-period treated/control ratio as a diagnostic baseline.

This design assumes no spillover across paired stores, stable measurement,
comparable common trends, and no unrecorded change that targets treatment
stores. Weekly autocorrelation, few pairs, intervention carryover, and
uncertain denominator can make the interval too narrow. Verify assignment,
retailer execution, stockouts, discount funding, and costs before using the
result commercially. Pair-specific shrinkage describes heterogeneity; it
does not identify an individual store's treatment effect.

## Reproduce and audit

```bash
python pilot_cli.py demo
python pilot_cli.py analyze path/to/local_pilot.csv --output-dir outputs/local_run
python -m unittest -v
```

`demo` writes `outputs/pilot_demo/synthetic_pilot.csv`,
`quality_report.json`, and `pilot_estimate.json`. The `analyze` command runs
locally and writes only a quality report if the gate fails. Output files are
ignored by Git, and the command refuses to overwrite existing artifacts.
No CSV upload is offered in the public Streamlit app. Keep private retailer
data off the public deployment.
