# Model card: matched-store pilot estimator (v1)

## Summary

This demonstration estimates incremental **unit lift** for one price-promotion
package in a matched-pair store experiment. The [public app](https://emerging-brand-rgm-lab.streamlit.app/)
uses generated data only. `pilot_core.py` validates store-week records,
computes a paired change estimate, pools pair estimates with an empirical-Bayes
random-effects approximation, and produces an approximate 90% pair-bootstrap
interval. This is not a trained model of universal price elasticity.

## Intended and prohibited use

Intended users are analysts planning or auditing a store pilot. The output can
set a promotion contribution hurdle for **the same product, regular price,
discount, and promotion package**, subject to review of execution and costs.
Do not use the public synthetic result to set a real price, claim profit lift,
or extrapolate to untested discounts, products, stores, or periods. The
calculator's "Controlled pilot" selector is self-declared; it does not verify
experimental provenance.

## Data and timing

The published fixture has 12 randomized matched pairs, 24 stores, six pre
weeks, six post weeks, and 288 store-week rows. The seed is 19, and the
generator's mean assigned effect is 27.6%. Store assignments are fixed before
post-period outcomes are generated. See [the field contract](PILOT_DATA_CONTRACT.md)
for identifiers, units, execution, stockouts, event time, source publication,
ingestion, and as-of rules. No Dominick's rows or fitted coefficients are
present in this public repo. The local CSV command can analyze a real pilot,
but the structural gate cannot establish that assignment was genuinely random.

## Training and evaluation

The model has no learned parameters trained on a historical scanner dataset.
It estimates the mean treatment effect from the supplied pilot, with pair
heterogeneity estimated from those same pairs. For the fixed synthetic seed,
pooled lift is 27.9%; the approximate 90% interval is 23.5%–32.0%, and it
contains the 27.6% generator truth. This is an in-simulator recovery check,
not independent validation. Across 100 generated seeds, mean signed
error was 0.09 percentage points and the interval contained the generated
mean in 100 of 100 cases (including the fixed demo seed). Those seeds share
the same data-generating process,
so this does **not** demonstrate real-world calibration or generalization.

## Baselines, metrics, calibration, uncertainty

The displayed baseline is the unadjusted post-period treated/control unit
ratio. The paired model corrects fixed pre-period differences between the
stores. Pair estimates are pooled using a normal-normal empirical-Bayes
random-effects approximation; higher-noise pairs are pulled more strongly
toward the shared mean. A deterministic bootstrap resamples entire pairs.
The interval ignores some uncertainty in the ratio denominator and may be
miscalibrated with few pairs, correlated weeks, or heterogeneous trends.
Real-data calibration has **not** been evaluated.

## Execution assumptions

One store per pair is assigned the promotion; controls remain untreated.
Treatment execution and price are recorded by store-week. The v1 gate blocks
duplicates, missing weeks, execution mismatch, stockouts, impossible prices,
and future-ingested rows. It requires one product and one regular/promoted
price. Scenario transfer is blocked when product, price, or discount differs.
Passing this gate means the CSV is structurally analyzable, not that a
commercial recommendation is approved.

## Limitations and failure modes

The estimate can fail if stores influence one another, customers shift
between stores, promotions have carryover, a treated store has an unrelated
post-period trend, or other marketing tactics change alongside the discount.
Price and display effects cannot be separated if both change together.
Pair-specific values are not identified individual-store effects. Costs,
vendor funding, substitution, and inventory used by the decision calculator
are separate inputs; they are not learned by the pilot estimator.

The separate [pilot sizing illustration](PILOT_DESIGN.md) uses pre-period
variation and a user-supplied effect-heterogeneity assumption. Its power curve
is a normal approximation conditional on an assumed true effect; it is not a
prediction that any real promotion will succeed. No real retailer baseline or
experimental power calibration has been evaluated.

## Monitoring, fallback, retirement

For any real pilot, archive the assignment log, freeze eligible stores and
weeks before outcome review, check pre-period balance and execution, and
review the quality report before estimation. If the contract gate fails,
withhold the lift estimate and use the break-even calculator with explicitly
labeled assumptions. Re-evaluate the method before use on another product,
retailer, promotion tactic, or period. Retire this version for commercial use
if assignment cannot be verified or pre/post comparability fails.
