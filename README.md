# Emerging Brand RGM Lab

**Live app:** https://emerging-brand-rgm-lab.streamlit.app/

An interactive promotion economics calculator for emerging grocery brands.
Enter shelf price, unit cost, baseline volume, inventory, vendor funding,
activation spend, and displaced sales. The app shows the **causal unit lift
required to break even**, contribution under downside/planning/upside scenarios,
and the maximum discount that breaks even at a supplied lift. A second tab
demonstrates a **randomized matched-store pilot** on generated data: a contract
gate, store-pair difference-in-differences, empirical-Bayes pooling of noisy
pair results, a pair-bootstrap interval, and a contribution stress test.
It also outlines a real store pilot that could measure lift.
An experiment-planning tab connects the contribution break-even hurdle to an
illustrative matched-store pair count and power curve, using only synthetic
pre-period sales noise. See [the sizing method](docs/PILOT_DESIGN.md).

**Try it locally**

```bash
python -m pip install -r requirements.txt
streamlit run streamlit_app.py
```

Run the deterministic calculation tests:

```bash
python -m unittest -v
```

Generate the fixed synthetic pilot and machine-readable audit artifacts:

```bash
python pilot_cli.py demo
```

For a genuine local pilot, follow [the store-week data contract](docs/PILOT_DATA_CONTRACT.md)
and run `python pilot_cli.py analyze path/to/local_pilot.csv --output-dir outputs/local_run`.
The local command does not upload data. Its gate checks structure and execution
but cannot prove that random assignment really occurred; preserve the
original assignment log. The public app accepts no CSV uploads.
The [model card](docs/MODEL_CARD.md) records the estimand, synthetic checks,
uncertainty, and limits.
The [pilot design note](docs/PILOT_DESIGN.md) records the sample-size
approximation and assumptions.
Run `python pilot_design_cli.py demo` to generate an auditable pre-period
fixture and sizing JSON. A local pre-period-only CSV can be analyzed with
`python pilot_design_cli.py plan baseline.csv --break-even-lift 0.225 --target-lift 0.30`.

The starting numbers are invented. This app does not estimate causal
elasticity or promotion lift from observational scanner data. The pilot tab
uses invented randomized assignments and outcomes; its recovered effect is
**method demonstration, not validated real-world performance**. In the
economics tab, all lift values are user assumptions unless the user has run a
controlled pilot; selecting "Controlled pilot" is a self declaration, not
verification by the app. Every status requires human review. Do not enter
confidential commercial inputs into a public deployment.

The accompanying research project examined historical [Dominick's grocery
scanner data](https://www.chicagobooth.edu/research/kilts/research-data/dominicks)
for academic research. Those data and fitted coefficients are not included
here. Forecasting sales under familiar conditions is a separate task from
estimating the causal effect of a new discount.

## Calculation contract

- Baseline contribution: `min(baseline units, available units) × (regular price − unit cost)`.
- Promotion contribution: `min(baseline units × (1 + assumed lift), available units) × (discounted price − unit cost + funding per unit) − activation cost − displaced units × displaced unit margin`.
- Incremental contribution: promotion contribution minus baseline contribution.
- Break-even lift: the smallest assumed lift with nonnegative incremental contribution, or infeasible if inventory or unit economics prevent it.

The calculator assumes funding applies to every promoted unit, fixed activation
cost is paid once for the period, and both plans face the same inventory cap.
It omits competitor response, stockout spillovers, changes after the promotion,
returns, and uncertainty in the supplied baseline. Confirm those inputs before
spending money.
