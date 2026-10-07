"""Public synthetic RGM decision lab; no licensed scanner rows are loaded."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from pilot_core import analyze_pilot, rows_to_csv, synthetic_pilot, transfer_blockers
from pilot_design import plan_pilot
from scenario_core import (PromotionInputs, SYNTHETIC_EXAMPLE,
                           break_even_lift, decision_label, evaluate,
                           maximum_break_even_discount)


st.set_page_config(page_title="Emerging Brand RGM Lab", page_icon="📊", layout="wide")
st.markdown("""
<style>
.block-container {max-width: 1200px; padding-top: 1.8rem;}
.rgm-hero {background: linear-gradient(115deg, #103932, #155b51 58%, #127968);
  border-radius: 18px; padding: 1.8rem 2rem; color: white; margin-bottom: 1.2rem;}
.rgm-hero h1 {color: white; font-size: 2.2rem; margin: 0 0 .3rem 0;}
.rgm-hero p {color: #d8f2ea; margin: 0; font-size: 1.05rem;}
.rgm-note {border-left: 4px solid #20a483; padding: .65rem 1rem;
  background: #f1faf6; border-radius: 0 8px 8px 0;}
</style>
<div class="rgm-hero"><h1>Emerging Brand RGM Lab</h1>
<p>Promotion economics, store-pooled pilot evidence, and experiment planning</p></div>
""", unsafe_allow_html=True)
st.caption("Synthetic starting values · calculations use only the inputs on this page · no scanner data is loaded")

decision_tab, pilot_tab, experiment_tab, evidence_tab = st.tabs(
    ["Promotion decision lab", "Pilot evidence demo", "Experiment brief", "What the evidence supports"]
)

with decision_tab:
    st.markdown("### Set the commercial facts")
    st.write("Use **non-confidential values** in a public deployment. The default numbers are invented examples.")
    price_col, volume_col, cost_col = st.columns(3)
    with price_col:
        product_id = st.text_input("Product ID (non-confidential)", value="SYNTHETIC-SKU")
        regular_price = st.number_input("Regular shelf price ($)", min_value=0.01,
                                        value=SYNTHETIC_EXAMPLE.regular_price, step=0.10)
        unit_cost = st.number_input("Unit replacement cost ($)", min_value=0.0,
                                    value=SYNTHETIC_EXAMPLE.unit_cost, step=0.10)
        discount_pct = st.slider("Proposed discount (%)", min_value=0, max_value=60, value=10)
    with volume_col:
        baseline_units = st.number_input("Expected units without promotion", min_value=1.0,
                                         value=float(SYNTHETIC_EXAMPLE.baseline_units), step=25.0)
        available_units = st.number_input("Units available to sell", min_value=0.0,
                                          value=float(SYNTHETIC_EXAMPLE.available_units), step=25.0)
        activation_cost = st.number_input("Fixed activation cost ($)", min_value=0.0,
                                          value=float(SYNTHETIC_EXAMPLE.activation_cost), step=25.0)
    with cost_col:
        funding_per_unit = st.number_input("Vendor funding per promoted unit ($)", min_value=0.0,
                                           value=SYNTHETIC_EXAMPLE.funding_per_unit, step=0.05)
        displaced_units = st.number_input("Units displaced from other products", min_value=0.0,
                                          value=float(SYNTHETIC_EXAMPLE.displaced_units), step=10.0)
        displaced_margin = st.number_input("Contribution lost per displaced unit ($)", min_value=0.0,
                                           value=SYNTHETIC_EXAMPLE.displaced_unit_margin, step=0.10)

    assumptions = PromotionInputs(regular_price=regular_price, unit_cost=unit_cost,
                                  baseline_units=baseline_units, discount=discount_pct / 100,
                                  available_units=available_units, activation_cost=activation_cost,
                                  funding_per_unit=funding_per_unit, displaced_units=displaced_units,
                                  displaced_unit_margin=displaced_margin)
    st.markdown("### Set the *causal* unit-lift range")
    st.caption("Lift means incremental units caused by the promotion relative to the same week without it. Historical price correlations do not supply this number.")
    lift_low_col, lift_base_col, lift_high_col, source_col = st.columns(4)
    with lift_low_col:
        low_pct = st.number_input("Downside lift (%)", min_value=-100, max_value=500, value=5, step=5)
    with lift_base_col:
        base_pct = st.number_input("Planning lift (%)", min_value=-100, max_value=500, value=25, step=5)
    with lift_high_col:
        high_pct = st.number_input("Upside lift (%)", min_value=-100, max_value=500, value=45, step=5)
    with source_col:
        evidence = st.selectbox("Lift evidence", ["Assumption", "Controlled pilot"])
    if not low_pct <= base_pct <= high_pct:
        st.error("Set downside lift ≤ planning lift ≤ upside lift.")
        st.stop()

    low, base, high = (evaluate(assumptions, pct / 100)
                       for pct in (low_pct, base_pct, high_pct))
    threshold = break_even_lift(assumptions)
    max_discount = maximum_break_even_discount(assumptions, base_pct / 100)
    status = decision_label(assumptions, low_pct / 100, high_pct / 100, evidence)

    st.markdown("### Read the decision")
    status_col, break_col, delta_col = st.columns(3)
    with status_col:
        st.metric("Decision status", status)
    with break_col:
        st.metric("Break-even unit lift",
                  "Not feasible" if threshold is None else f"{threshold:.1%}")
    with delta_col:
        st.metric("Planning contribution change", f"${base['incremental_contribution']:,.0f}")
    if status == "EXPERIMENT FIRST":
        st.info("Lift is an assumption. Use this result to set a pilot hurdle, then measure the actual incremental effect.")
    elif status == "CANDIDATE FOR REVIEW":
        st.success("Even the stated downside clears the modeled hurdle. Verify pilot design, costs, inventory, and displacement before spending.")
    else:
        st.warning("The modeled downside or upside does not support a confident promotion decision. Revise the plan or test it first.")
    if threshold is None:
        st.warning("Given the price, costs, and inventory entered, no amount of unit lift can reach break-even.")

    scenario_rows = [
        {"Scenario": name, "Assumed lift": f"{pct}%", "Units sold": result["sold_units"],
         "Inventory limited": result["stock_limited"],
         "Promo contribution ($)": result["promo_contribution"],
         "Change vs no promotion ($)": result["incremental_contribution"]}
        for name, pct, result in (("Downside", low_pct, low),
                                  ("Planning", base_pct, base),
                                  ("Upside", high_pct, high))
    ]
    st.dataframe(scenario_rows, width="stretch", hide_index=True)
    st.caption("Contribution = sold units × (promoted price − replacement cost + vendor funding) − activation cost − displaced-product contribution. Both plans respect the same inventory cap.")

    graph_max = max(100, high_pct + 20)
    graph_min = min(-20, low_pct - 10)
    sensitivity = pd.DataFrame([
        {"Assumed unit lift (%)": lift,
         "Contribution change ($)": evaluate(assumptions, lift / 100)["incremental_contribution"],
         "Break-even line ($)": 0.0}
        for lift in range(graph_min, graph_max + 1, 5)
    ])
    st.line_chart(sensitivity, x="Assumed unit lift (%)",
                  y=["Contribution change ($)", "Break-even line ($)"],
                  width="stretch")
    st.caption("The curve is a sensitivity calculation under your inputs; it is not a predicted response curve.")
    st.write("**Maximum discount at planning lift:** " +
             ("No discount breaks even" if max_discount is None else f"{max_discount:.1%}"))

    memo = {"data_label": "SYNTHETIC STARTING VALUES OR USER-ENTERED ASSUMPTIONS",
            "product_id": product_id,
            "lift_evidence_self_declared": evidence,
            "inputs": assumptions.__dict__,
            "scenarios": {"downside": low, "planning": base, "upside": high},
            "break_even_lift": threshold,
            "maximum_discount_at_planning_lift": max_discount,
            "decision_status": status,
            "limits": ["No causal lift is inferred from historical scanner data.",
                       "No competitor response, future demand shift, or validated displacement model.",
                       "Requires human review and verified costs before action."]}
    st.download_button("Download scenario brief (JSON)",
                       data=json.dumps(memo, indent=2),
                       file_name="rgm_scenario_brief.json", mime="application/json")

with pilot_tab:
    st.markdown("### From randomized stores to a decision hurdle")
    st.warning("**Synthetic demonstration only.** These stores, assignments, prices, and sales were generated by code. The estimated lift is not evidence that a real brand promotion will work.")
    pilot_rows, pilot_truth = synthetic_pilot()
    pilot = analyze_pilot(pilot_rows)
    quality = pilot["quality"]
    st.markdown("#### Data readiness")
    quality_columns = st.columns(4)
    for column, label, value in zip(
        quality_columns,
        ("Contract gate", "Matched pairs", "Store-weeks", "Pre / post weeks"),
        ("PASS" if quality["ready"] else "BLOCK", quality["pairs"], quality["rows"],
         f"{quality['pre_weeks']} / {quality['post_weeks']}")
    ):
        column.metric(label, value)
    st.caption("Duplicate rows, missing weeks, stockouts, mismatched execution, and impossible timestamps block estimation. Assignment authenticity still needs an external randomization log.")

    st.markdown("#### Compare the estimate with the known synthetic truth")
    interval_low, interval_high = pilot["interval_90"]
    estimate_columns = st.columns(4)
    estimate_columns[0].metric("Pooled unit lift", f"{pilot['pooled_lift']:.1%}")
    estimate_columns[1].metric("Approx. 90% range", f"{interval_low:.1%}–{interval_high:.1%}")
    estimate_columns[2].metric("Naive post-only comparison", f"{pilot['naive_post_ratio']:.1%}")
    estimate_columns[3].metric("Generator's true mean", f"{pilot_truth['true_mean_assigned_lift']:.1%}")
    st.caption("Matched-pair difference-in-differences removes fixed store imbalance. An empirical-Bayes model shrinks noisy pair estimates toward a shared lift; a pair bootstrap supplies the approximate range. The true value is visible only because this dataset is synthetic.")

    pair_frame = pd.DataFrame([
        {"Pair": item["pair_id"], "Raw pair lift": f"{item['lift']:.1%}",
         "Pooled pair lift": f"{item['pooled_pair_lift']:.1%}",
         "Estimated extra units / store-week": item["effect_units_per_store_week"]}
        for item in pilot["pair_results"]
    ])
    st.dataframe(pair_frame, width="stretch", hide_index=True)
    st.caption("Pair-specific estimates describe variation between matched pairs; a single store effect is not identified in this design.")

    st.markdown("#### Stress-test the current commercial inputs")
    st.caption(f"The synthetic pilot tested {pilot['tested_product_id']} at a ${pilot['tested_regular_price']:.2f} regular price and {pilot['tested_discount']:.1%} discount. Lift cannot be reused for an untested product or price. Even a match needs review for different stores and dates.")
    transfer_issues = transfer_blockers(pilot, product_id, regular_price, discount_pct / 100)
    if transfer_issues:
        st.error("Scenario transfer blocked: " + "; ".join(transfer_issues) + ".")
    else:
        pilot_scenarios = [
            {"Synthetic lift": label, "Lift": f"{lift:.1%}",
             "Contribution change ($)": evaluate(assumptions, lift)["incremental_contribution"]}
            for label, lift in (("Downside", interval_low), ("Pooled", pilot["pooled_lift"]),
                                ("Upside", interval_high))
        ]
        st.dataframe(pilot_scenarios, width="stretch", hide_index=True)
        if threshold is None:
            st.error("The current economics cannot break even at any lift within the inventory cap.")
        elif interval_high < threshold:
            st.warning("In this synthetic case, even the upside is below the break-even hurdle. Redesign the promotion.")
        elif interval_low <= threshold:
            st.warning("In this synthetic case, the range crosses the break-even hurdle. Investigate downside before deciding.")
        else:
            st.info("In this synthetic case, the downside clears the modeled hurdle. A real pilot and verified costs would still need review.")
    st.download_button("Download synthetic pilot CSV", rows_to_csv(pilot_rows),
                       file_name="synthetic_store_pilot.csv", mime="text/csv")
    st.download_button("Download quality and model report (JSON)",
                       json.dumps({"data_label": pilot_truth["label"],
                                   "synthetic_truth": pilot_truth, **pilot}, indent=2),
                       file_name="synthetic_pilot_report.json", mime="application/json")

with experiment_tab:
    st.markdown("### Turn the assumption into evidence")
    st.markdown("#### Size a matched-store pilot against the contribution hurdle")
    st.warning("**Synthetic planning illustration.** Noise is measured from the generated stores' pre-promotion weeks. It is not a sample-size promise for a real retailer.")
    design_a, design_b, design_c = st.columns(3)
    with design_a:
        design_target_pct = st.number_input("Lift to detect (%)", min_value=-100,
                                            max_value=500, value=30, step=5)
        design_heterogeneity_pct = st.number_input(
            "Assumed store-pair effect variation (percentage points)",
            min_value=0, max_value=100, value=8, step=1)
    with design_b:
        design_pre_weeks = st.number_input("Planned pre-promotion weeks", min_value=4,
                                           max_value=52, value=6)
        design_post_weeks = st.number_input("Planned promotion weeks", min_value=4,
                                            max_value=52, value=6)
    with design_c:
        design_power_pct = st.slider("Chance of clearing hurdle if target lift is real (%)",
                                     min_value=55, max_value=95, value=80, step=5)
        st.metric("Contribution break-even hurdle",
                  "Not feasible" if threshold is None else f"{threshold:.1%}")
    if threshold is None:
        st.error("This promotion cannot break even with the entered inventory and unit economics. Redesign it before sizing a pilot.")
    else:
        design = plan_pilot(
            pilot_rows, break_even_lift=threshold,
            target_lift=design_target_pct / 100,
            planned_pre_weeks=int(design_pre_weeks),
            planned_post_weeks=int(design_post_weeks),
            heterogeneity_sd=design_heterogeneity_pct / 100,
            target_power=design_power_pct / 100,
        )
        if design["required_pairs"] is None:
            st.warning("No design within 200 matched pairs reaches the target chance under these assumptions. Increase the expected effect, change the economics, or revisit feasibility.")
        else:
            st.metric("Illustrative matched pairs needed",
                      design["required_pairs"],
                      help="One promoted and one control store per pair. This count uses a one-sided 5% test and a normal approximation.")
        st.caption(f"At {design['source_pairs']} pairs, the modeled chance of clearing the hurdle is {design['power_at_source_pairs']:.0%}. This probability assumes the entered lift is the true average effect; it is not the probability the promotion will work.")
        curve = pd.DataFrame(design["power_curve"])
        st.line_chart(curve, x="pairs", y="probability_clearing_hurdle",
                      width="stretch")
        st.caption("The calculation uses only pre-period paired sales variation; post-promotion outcomes do not set the sample size. It assumes independent stores and weeks, stable noise, no spillovers, and the entered effect variation. A real pilot needs its own baseline data and a reviewed design.")
        st.download_button("Download pilot sizing assumptions (JSON)",
                           json.dumps(design, indent=2),
                           file_name="synthetic_pilot_design.json",
                           mime="application/json")

    st.markdown("#### Execution checklist")
    st.markdown("""
    1. **Choose the decision first.** Record the planned discount, funding,
       activation spend, eligible stores, and the contribution-profit hurdle.
    2. **Assign comparable stores at random.** Keep a no-promotion control group
       over the same weeks. Record deviations from the assigned treatment.
    3. **Check execution.** Capture actual shelf price, display and feature
       placement, stock availability, returns, competitor activity, and
       supplier funding by store-week.
    4. **Measure incremental contribution.** Compare treatment and control
       changes after checking pre-period balance and missing data. Include
       displaced sales from related products.
    5. **Decide with uncertainty.** Report the effect range and downside,
       then run the scenario lab with the pilot estimate. Do not choose a
       winner from a point estimate alone.
    """)
    st.info("The pilot tab demonstrates estimation on generated randomized data. The sizing tool is an illustrative normal approximation; a real pilot requires retailer-specific pre-period data and a power review.")

with evidence_tab:
    st.markdown("### Where RGM is possible today")
    st.markdown("""
    **Demand forecast** = estimate likely units under familiar conditions.
    Our separate historical research showed that store-level calibration can
    improve forecast error on one held-out grocery category. It does not show
    that changing a price will cause the same response.

    **Pilot measurement** = compare randomized matched stores over the same
    weeks and pool noisy pair estimates. The pilot tab demonstrates this on
    synthetic data; a real experiment needs an auditable assignment log.

    **Promotion economics** = calculate contribution, inventory limits,
    break-even lift, and funding needs from verified commercial inputs. This
    page does that math with explicit assumptions.

    **Optimization** = choose among actions after credible causal lift ranges,
    costs, substitution, and execution constraints are measured. The current
    historical data do not meet that bar.
    """)
    st.markdown("<div class='rgm-note'><strong>Data boundary:</strong> This public demo contains no Dominick's scanner rows, UPC-level outputs, or fitted coefficients. It starts with invented numbers and keeps calculations in the app session.</div>",
                unsafe_allow_html=True)
    st.caption("The separate scanner study uses historical Chicago Booth data for academic research only; [source and terms](https://www.chicagobooth.edu/research/kilts/research-data/dominicks).")
