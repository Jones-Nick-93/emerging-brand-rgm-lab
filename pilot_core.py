"""Auditable matched-store promotion pilot demo.

The generator is synthetic. The estimator only makes a causal claim when the
supplied assignment and execution fields describe a genuine randomized pilot.
It cannot verify that randomization actually occurred outside this program.
"""

from __future__ import annotations

import csv
import math
import random
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from io import StringIO
from statistics import mean, variance


FIELDS = (
    "product_id", "store_id", "pair_id", "week_index", "week_start", "period",
    "assigned_promo", "executed_promo", "units", "regular_price",
    "observed_price", "unit_cost", "available_units", "stockout",
    "source_published_at", "ingested_at",
)


@dataclass(frozen=True)
class PilotQuality:
    ready: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    rows: int
    stores: int
    pairs: int
    pre_weeks: int
    post_weeks: int
    as_of: str

    def to_dict(self) -> dict:
        return asdict(self)


def _parse_row(row: dict) -> dict:
    parsed = dict(row)
    parsed["product_id"] = str(row["product_id"]).strip()
    parsed["store_id"] = str(row["store_id"]).strip()
    parsed["pair_id"] = str(row["pair_id"]).strip()
    week_number = float(row["week_index"])
    if not math.isfinite(week_number) or not week_number.is_integer():
        raise ValueError("week_index must be an integer")
    parsed["week_index"] = int(week_number)
    for field in ("assigned_promo", "executed_promo", "stockout"):
        numeric = float(row[field])
        if not math.isfinite(numeric) or numeric not in (0.0, 1.0):
            raise ValueError(f"{field} must be 0 or 1")
        parsed[field] = int(numeric)
    for field in ("units", "regular_price", "observed_price", "unit_cost",
                  "available_units"):
        value = float(row[field])
        if not math.isfinite(value):
            raise ValueError(f"{field} must be finite")
        parsed[field] = value
    parsed["week_start"] = date.fromisoformat(str(row["week_start"]))
    for field in ("source_published_at", "ingested_at"):
        timestamp = datetime.fromisoformat(str(row[field]).replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            raise ValueError(f"{field} needs a timezone")
        parsed[field] = timestamp
    return parsed


def _validate_and_parse(rows: list[dict], as_of: datetime | None = None) -> tuple[PilotQuality, list[dict]]:
    as_of = as_of or datetime.now(timezone.utc)
    if as_of.tzinfo is None:
        raise ValueError("as_of needs a timezone")
    blockers: list[str] = []
    warnings: list[str] = []
    parsed: list[dict] = []
    if not rows:
        blockers.append("No pilot rows supplied")
    for number, row in enumerate(rows, 1):
        missing = [field for field in FIELDS if field not in row or row[field] in (None, "")]
        if missing:
            blockers.append(f"Row {number}: missing {', '.join(missing)}")
            continue
        try:
            item = _parse_row(row)
        except (ValueError, TypeError) as exc:
            blockers.append(f"Row {number}: {exc}")
            continue
        if not item["product_id"] or not item["store_id"] or not item["pair_id"]:
            blockers.append(f"Row {number}: blank product, store, or pair ID")
        if item["period"] not in ("pre", "post") or (item["week_index"] < 0) != (item["period"] == "pre"):
            blockers.append(f"Row {number}: period and week_index disagree")
        if item["units"] < 0 or item["available_units"] < 0 or item["unit_cost"] < 0:
            blockers.append(f"Row {number}: negative units, inventory, or cost")
        if item["regular_price"] <= 0 or item["observed_price"] <= 0:
            blockers.append(f"Row {number}: price must be positive")
        if item["units"] > item["available_units"] + 1e-9:
            blockers.append(f"Row {number}: units exceed available inventory")
        if item["stockout"]:
            blockers.append(f"Row {number}: stockout censors demand")
        if item["source_published_at"].date() < item["week_start"] + timedelta(days=7):
            blockers.append(f"Row {number}: source published before week closed")
        if item["ingested_at"] < item["source_published_at"]:
            blockers.append(f"Row {number}: ingestion precedes publication")
        if item["ingested_at"] > as_of:
            blockers.append(f"Row {number}: ingestion is after analysis as-of time")
        if item["period"] == "pre" and item["executed_promo"]:
            blockers.append(f"Row {number}: treatment executed in pre-period")
        if item["period"] == "post" and item["executed_promo"] != item["assigned_promo"]:
            blockers.append(f"Row {number}: assignment and execution differ")
        if item["executed_promo"]:
            if item["observed_price"] >= item["regular_price"]:
                blockers.append(f"Row {number}: executed promotion has no price discount")
        elif abs(item["observed_price"] - item["regular_price"]) > 0.011:
            blockers.append(f"Row {number}: untreated price differs from regular price")
        parsed.append(item)

    by_store: dict[str, list[dict]] = {}
    by_pair: dict[str, set[str]] = {}
    by_week: dict[int, set[date]] = {}
    keys: set[tuple[str, int]] = set()
    for item in parsed:
        key = (item["store_id"], item["week_index"])
        if key in keys:
            blockers.append(f"Duplicate store-week: {key[0]}, {key[1]}")
        keys.add(key)
        by_store.setdefault(item["store_id"], []).append(item)
        by_pair.setdefault(item["pair_id"], set()).add(item["store_id"])
        by_week.setdefault(item["week_index"], set()).add(item["week_start"])

    all_weeks = {item["week_index"] for item in parsed}
    pre_weeks = len({week for week in all_weeks if week < 0})
    post_weeks = len({week for week in all_weeks if week >= 0})
    if pre_weeks < 4 or post_weeks < 4:
        blockers.append("At least four shared pre and post weeks are required")
    if any(len(dates) != 1 for dates in by_week.values()):
        blockers.append("week_index maps to different week_start dates")
    ordered_dates = [next(iter(by_week[week])) for week in sorted(by_week) if len(by_week[week]) == 1]
    if len(ordered_dates) == len(by_week) and any(
        later - earlier != timedelta(days=7)
        for earlier, later in zip(ordered_dates, ordered_dates[1:])
    ):
        blockers.append("Calendar weeks are not contiguous")
    for store, items in by_store.items():
        if {item["week_index"] for item in items} != all_weeks:
            blockers.append(f"Store {store}: missing or extra weeks")
        if len({item["pair_id"] for item in items}) != 1:
            blockers.append(f"Store {store}: pair ID changes")
        if len({item["assigned_promo"] for item in items}) != 1:
            blockers.append(f"Store {store}: assignment changes")
    for pair, stores in by_pair.items():
        if len(stores) != 2:
            blockers.append(f"Pair {pair}: expected two stores")
        elif sum(by_store[store][0]["assigned_promo"] for store in stores) != 1:
            blockers.append(f"Pair {pair}: expected one treated and one control store")
    if len(by_pair) < 4:
        blockers.append("At least four randomized store pairs are required")
    if len({item["product_id"] for item in parsed}) > 1:
        blockers.append("This pilot version requires one product ID")
    regular_prices = {round(item["regular_price"], 2) for item in parsed}
    promo_prices = {round(item["observed_price"], 2) for item in parsed if item["executed_promo"]}
    if len(regular_prices) > 1 or len(promo_prices) > 1:
        blockers.append("This pilot version requires one regular and one promoted price")
    if not blockers:
        warnings.append("Assignment and commercial costs are self-reported; verify the original randomization log")
        warnings.append("Pair bootstrap intervals are approximate with few stores or correlated weeks")
    report = PilotQuality(not blockers, tuple(blockers), tuple(warnings), len(rows),
                          len(by_store), len(by_pair), pre_weeks, post_weeks,
                          as_of.isoformat())
    return report, parsed


def validate_pilot(rows: list[dict], *, as_of: datetime | None = None) -> PilotQuality:
    return _validate_and_parse(rows, as_of)[0]


def _random_effects(pair_results: list[dict]) -> tuple[float, float, list[dict]]:
    """Normal-normal empirical Bayes pooling of paired lift estimates."""
    weights_fixed = [1 / item["se_lift"] ** 2 for item in pair_results]
    fixed_mean = sum(w * item["lift"] for w, item in zip(weights_fixed, pair_results)) / sum(weights_fixed)
    q = sum(w * (item["lift"] - fixed_mean) ** 2 for w, item in zip(weights_fixed, pair_results))
    c = sum(weights_fixed) - sum(w * w for w in weights_fixed) / sum(weights_fixed)
    tau2 = max(0.0, (q - (len(pair_results) - 1)) / c) if c > 0 else 0.0
    weights = [1 / (item["se_lift"] ** 2 + tau2) for item in pair_results]
    pooled = sum(w * item["lift"] for w, item in zip(weights, pair_results)) / sum(weights)
    enriched = []
    for item in pair_results:
        shrink = tau2 / (tau2 + item["se_lift"] ** 2) if tau2 else 0.0
        enriched.append({**item, "pooled_pair_lift": pooled + shrink * (item["lift"] - pooled)})
    return pooled, math.sqrt(tau2), enriched


def analyze_pilot(rows: list[dict], *, bootstrap_samples: int = 600, seed: int = 42,
                  as_of: datetime | None = None) -> dict:
    quality, parsed = _validate_and_parse(rows, as_of)
    if not quality.ready:
        raise ValueError("Pilot quality gate failed: " + "; ".join(quality.blockers[:5]))
    if bootstrap_samples < 100:
        raise ValueError("At least 100 pair bootstrap samples are required")
    product_id = next(item["product_id"] for item in parsed)
    regular_price = next(item["regular_price"] for item in parsed)
    promo_price = next(item["observed_price"] for item in parsed if item["executed_promo"])
    grouped: dict[str, dict[int, dict[str, dict]]] = {}
    for item in parsed:
        grouped.setdefault(item["pair_id"], {}).setdefault(item["week_index"], {})[
            "treated" if item["assigned_promo"] else "control"] = item
    pair_results: list[dict] = []
    naive_treated = naive_control = 0.0
    for pair, weeks in sorted(grouped.items()):
        pre = [weeks[week] for week in sorted(weeks) if week < 0]
        post = [weeks[week] for week in sorted(weeks) if week >= 0]
        pre_diffs = [week["treated"]["units"] - week["control"]["units"] for week in pre]
        post_diffs = [week["treated"]["units"] - week["control"]["units"] for week in post]
        treated_pre = mean(week["treated"]["units"] for week in pre)
        control_pre = mean(week["control"]["units"] for week in pre)
        treated_post = mean(week["treated"]["units"] for week in post)
        control_post = mean(week["control"]["units"] for week in post)
        counterfactual = treated_pre + control_post - control_pre
        if counterfactual <= 0:
            raise ValueError(f"Pair {pair}: nonpositive no-promotion counterfactual")
        effect_units = mean(post_diffs) - mean(pre_diffs)
        se_units = math.sqrt(variance(pre_diffs) / len(pre_diffs) +
                             variance(post_diffs) / len(post_diffs))
        pair_results.append({"pair_id": pair, "lift": effect_units / counterfactual,
                             "se_lift": max(se_units / counterfactual, 0.01),
                             "effect_units_per_store_week": effect_units,
                             "counterfactual_units_per_store_week": counterfactual})
        naive_treated += treated_post
        naive_control += control_post
    pooled, tau, enriched = _random_effects(pair_results)
    rng = random.Random(seed)
    draws = []
    for _ in range(bootstrap_samples):
        sample = [rng.choice(pair_results) for _ in pair_results]
        draws.append(_random_effects(sample)[0])
    draws.sort()
    lower = draws[int(0.05 * bootstrap_samples)]
    upper = draws[int(0.95 * bootstrap_samples) - 1]
    return {"quality": quality.to_dict(), "pooled_lift": pooled,
            "interval_90": [lower, upper], "heterogeneity_sd": tau,
            "tested_product_id": product_id,
            "tested_regular_price": regular_price,
            "tested_discount": 1 - promo_price / regular_price,
            "naive_post_ratio": naive_treated / naive_control - 1,
            "pair_results": enriched, "bootstrap_samples": bootstrap_samples,
            "method": "Matched-pair difference-in-differences; random-effects empirical Bayes pooling; pair bootstrap"}


def transfer_blockers(pilot: dict, product_id: str, regular_price: float,
                      discount: float) -> list[str]:
    """Block mechanical reuse of lift for an untested product or price."""
    reasons = []
    if product_id != pilot["tested_product_id"]:
        reasons.append("Product ID differs from the tested product")
    if abs(regular_price - pilot["tested_regular_price"]) > 0.011:
        reasons.append("Shelf price differs from the tested regular price")
    if abs(discount - pilot["tested_discount"]) > 0.005:
        reasons.append("Discount differs from the tested promotion")
    return reasons


def synthetic_pilot(*, pairs: int = 12, pre_weeks: int = 6,
                    post_weeks: int = 6, seed: int = 19) -> tuple[list[dict], dict]:
    """Generate fixed, labeled synthetic randomized store pairs."""
    if pairs < 4 or pre_weeks < 4 or post_weeks < 4:
        raise ValueError("Use at least four pairs and four weeks in each period")
    rng = random.Random(seed)
    first_week = date(2025, 1, 6)
    week_indices = list(range(-pre_weeks, post_weeks))
    common_factors = {week: 1 + rng.gauss(0, 0.035) for week in week_indices}
    rows: list[dict] = []
    true_lifts = []
    for pair_number in range(1, pairs + 1):
        pair_id = f"P{pair_number:02d}"
        pair_base = rng.uniform(110, 210)
        treated_index = rng.randrange(2)
        true_lift = max(0.05, rng.gauss(0.27, 0.075))
        true_lifts.append(true_lift)
        for store_number in range(2):
            store_id = f"{pair_id}-S{store_number + 1}"
            assigned = int(store_number == treated_index)
            store_base = pair_base * rng.uniform(0.86, 1.14)
            for week in week_indices:
                post = week >= 0
                executed = int(bool(assigned and post))
                natural_units = max(1, store_base * common_factors[week] *
                                    (1 + (0.035 if post else 0)) + rng.gauss(0, 5))
                units = round(max(0, natural_units * (1 + true_lift * executed)), 2)
                week_start = first_week + timedelta(weeks=week + pre_weeks)
                published = datetime.combine(week_start + timedelta(days=8),
                                             datetime.min.time(), timezone.utc)
                rows.append({"product_id": "SYNTHETIC-SKU", "store_id": store_id,
                             "pair_id": pair_id,
                             "week_index": week, "week_start": week_start.isoformat(),
                             "period": "post" if post else "pre",
                             "assigned_promo": assigned, "executed_promo": executed,
                             "units": units, "regular_price": 4.99,
                             "observed_price": 4.49 if executed else 4.99,
                             "unit_cost": 2.10, "available_units": 1000,
                             "stockout": 0,
                             "source_published_at": published.isoformat(),
                             "ingested_at": (published + timedelta(hours=2)).isoformat()})
    return rows, {"label": "SYNTHETIC RANDOMIZED DEMO", "seed": seed,
                  "pairs": pairs, "true_mean_assigned_lift": mean(true_lifts)}


def rows_to_csv(rows: list[dict]) -> str:
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()
