# Matched-store pilot sizing illustration

This feature helps frame an experiment before an emerging brand asks a retailer
for stores. It is a planning calculation, not evidence of promotion lift or a
validated sample-size recommendation. The public app uses **synthetic** sales.

## Decision and calculation

The decision is whether a one-sided 95% lower bound for causal unit lift could
exceed the contribution break-even lift from the current commercial inputs.
The user supplies the lift they hope to detect, planned pre/post weeks, and an
assumed standard deviation for genuine effect differences between store pairs.
The tool finds the smallest count from 4 to 200 matched pairs with at least the
selected power under a normal approximation. It returns no count when none
qualifies. One pair requires one assigned promotion store and one control store.

For each source pair, we calculate the pre-period weekly difference in units
between assigned treatment and control stores. We average the within-pair
sample variances, take its square root, and divide by average pre-period units
in the assigned stores. For a new pilot, the pair-level lift variance is

```text
(weekly difference SD / baseline units)^2 × (1/pre weeks + 1/post weeks)
    + assumed effect heterogeneity SD^2
```

Dividing by the number of pairs gives the variance of the mean lift estimate.
The probability of clearing the economic hurdle is the probability that an
estimated effect exceeds `break-even lift + 1.645 × standard error`, given
the user-entered true-effect scenario. The 1.645 multiplier corresponds to a
one-sided 5% normal test. At the hurdle, the modeled chance is 5% when variance
is positive; this is a test error rate, not a business success probability.

## Data boundary and assumptions

`pilot_design.py` accepts a **pre-period-only** store-week CSV. Its required
fields are `product_id`, `store_id`, `pair_id`, `week_index`, `week_start`,
`assigned_promo`, `units`, `available_units`, `stockout`,
`source_published_at`, and `ingested_at`. `week_index` must be a contiguous
negative sequence ending at -1. Within each pair, designate one proposed
promotion store and one proposed control store using `assigned_promo`; this
is a prospective label, not a claim that treatment has already occurred.
The validator requires four or more complete pairs, four or more pre weeks,
no recorded stockouts, consistent pair assignments, and correctly ordered timezone
timestamps. The public app's full synthetic fixture is filtered to pre weeks
before this validation; post outcomes cannot affect its sizing result.

Run a synthetic local demo with `python pilot_design_cli.py demo`. For a local
baseline CSV, use for example:

```bash
python pilot_design_cli.py plan baseline.csv --break-even-lift 0.225 --target-lift 0.30 --output-dir outputs/my_design
```

The break-even lift must come from independently verified commercial inputs.
The local command writes an audit JSON and does not upload the baseline CSV.
The app's default fixture has 12 synthetic pairs and six pre weeks. With
default economics, a 30% target lift, six pre and six post weeks,
eight percentage points of assumed effect variation, and 80% target power,
the illustration requests eight pairs; the modeled chance at 12 pairs is 93%.

The approximation assumes stable pre-to-post noise, independent weeks and
store pairs, no customer spillovers or carryover, and a credible effect
heterogeneity input. It ignores retailer clustering, seasonality shifts,
assignment restrictions, execution failure, multiple tested tactics, and
inventory-driven demand censoring. Real stores need their own pre-period
data, an assignment and exclusion plan, feasibility checks, and statistical
review before a sample-size commitment. A larger pair count cannot rescue an
unprofitable promotion if the target lift is below its break-even hurdle.

The output is downloadable JSON with inputs, noise estimate, power curve,
assumptions, and the pair-count result. No real retailer data are uploaded to
the public app.
