# Emerging Brand RGM Lab

An interactive promotion economics calculator for emerging grocery brands.
Enter shelf price, unit cost, baseline volume, inventory, vendor funding,
activation spend, and displaced sales. The app shows the **causal unit lift
required to break even**, contribution under downside/planning/upside scenarios,
and the maximum discount that breaks even at a supplied lift. It also outlines
a store pilot that could measure lift.

**Try it locally**

```bash
python -m pip install -r requirements.txt
streamlit run streamlit_app.py
```

Run the deterministic calculation tests:

```bash
python -m unittest -v
```

The starting numbers are invented. This app does not estimate causal
elasticity or promotion lift from observational scanner data. All lift values
are user assumptions unless the user has run a controlled pilot; selecting
"Controlled pilot" is a self declaration, not verification by the app. The
decision status always requires human review. Do not enter confidential
commercial inputs into a public deployment.

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
