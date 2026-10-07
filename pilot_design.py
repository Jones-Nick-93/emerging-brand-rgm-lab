"""Illustrative matched-store pilot sizing from pre-period variation only.

The normal approximation assumes independent pairs and weeks, stable noise,
and a user-supplied between-pair treatment-effect standard deviation. It is
an experiment planning calculation, not a post-pilot inference procedure.
"""

from __future__ import annotations

import math
import csv
from datetime import date, datetime, timedelta, timezone
from io import StringIO
from statistics import mean, variance


ONE_SIDED_95_Z = 1.6448536269514722
DESIGN_FIELDS = (
    "product_id", "store_id", "pair_id", "week_index", "week_start",
    "assigned_promo", "units", "available_units", "stockout",
    "source_published_at", "ingested_at",
)


def _normal_cdf(value: float) -> float:
    return 0.5 * (1 + math.erf(value / math.sqrt(2)))


def baseline_rows_to_csv(rows: list[dict]) -> str:
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=DESIGN_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows({field: row[field] for field in DESIGN_FIELDS}
                     for row in rows if row.get("period", "pre") == "pre")
    return output.getvalue()


def _validate_baseline(rows: list[dict], as_of: datetime | None) -> tuple[list[dict], dict]:
    as_of = as_of or datetime.now(timezone.utc)
    if as_of.tzinfo is None:
        raise ValueError("as_of needs a timezone")
    if not rows:
        raise ValueError("No baseline rows supplied")
    parsed = []
    keys = set()
    by_store: dict[str, list[dict]] = {}
    by_pair: dict[str, set[str]] = {}
    by_week: dict[int, set[date]] = {}
    for number, row in enumerate(rows, 1):
        if any(field not in row or row[field] in (None, "") for field in DESIGN_FIELDS):
            raise ValueError(f"Row {number}: missing baseline contract field")
        try:
            week_number = float(row["week_index"])
            assigned = float(row["assigned_promo"])
            stockout = float(row["stockout"])
            units = float(row["units"])
            available = float(row["available_units"])
            week_start = date.fromisoformat(str(row["week_start"]))
            published = datetime.fromisoformat(str(row["source_published_at"]).replace("Z", "+00:00"))
            ingested = datetime.fromisoformat(str(row["ingested_at"]).replace("Z", "+00:00"))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Row {number}: malformed baseline value: {exc}") from exc
        if not math.isfinite(week_number) or not week_number.is_integer() or week_number >= 0:
            raise ValueError(f"Row {number}: baseline week_index must be a negative integer")
        if assigned not in (0, 1) or stockout not in (0, 1):
            raise ValueError(f"Row {number}: assignment and stockout must be 0 or 1")
        if not all(math.isfinite(value) for value in (units, available)) or units < 0 or available < units:
            raise ValueError(f"Row {number}: impossible units or available inventory")
        if stockout:
            raise ValueError(f"Row {number}: stockout censors baseline demand")
        if published.tzinfo is None or ingested.tzinfo is None:
            raise ValueError(f"Row {number}: timestamps need timezones")
        if published.date() < week_start + timedelta(days=7) or not published <= ingested <= as_of:
            raise ValueError(f"Row {number}: impossible source, ingestion, or as-of order")
        product = str(row["product_id"]).strip()
        store = str(row["store_id"]).strip()
        pair = str(row["pair_id"]).strip()
        if not product or not store or not pair:
            raise ValueError(f"Row {number}: blank product, store, or pair ID")
        week = int(week_number)
        key = (store, week)
        if key in keys:
            raise ValueError(f"Duplicate store-week: {store}, {week}")
        keys.add(key)
        item = {"product_id": product, "store_id": store, "pair_id": pair,
                "week_index": week, "week_start": week_start,
                "assigned_promo": int(assigned), "units": units}
        parsed.append(item)
        by_store.setdefault(store, []).append(item)
        by_pair.setdefault(pair, set()).add(store)
        by_week.setdefault(week, set()).add(week_start)
    weeks = set(by_week)
    if len(weeks) < 4 or sorted(weeks) != list(range(min(weeks), 0)):
        raise ValueError("At least four contiguous pre-period week indices are required")
    if len(by_pair) < 4 or any(len(stores) != 2 for stores in by_pair.values()):
        raise ValueError("At least four pairs with exactly two stores each are required")
    if any(len(dates) != 1 for dates in by_week.values()):
        raise ValueError("Each week_index must map to one week_start")
    dates = [next(iter(by_week[week])) for week in sorted(weeks)]
    if any(later - earlier != timedelta(days=7)
           for earlier, later in zip(dates, dates[1:])):
        raise ValueError("Calendar weeks must be contiguous")
    if len({item["product_id"] for item in parsed}) != 1:
        raise ValueError("This design version requires one product")
    for store, items in by_store.items():
        if {item["week_index"] for item in items} != weeks:
            raise ValueError(f"Store {store}: missing weeks")
        if len({item["pair_id"] for item in items}) != 1 or len({item["assigned_promo"] for item in items}) != 1:
            raise ValueError(f"Store {store}: pair or assignment changes")
    for pair, stores in by_pair.items():
        if sum(by_store[store][0]["assigned_promo"] for store in stores) != 1:
            raise ValueError(f"Pair {pair}: expected one prospective treatment and one control store")
    return parsed, {"source_pairs": len(by_pair), "source_pre_weeks": len(weeks),
                    "source_rows": len(parsed), "as_of": as_of.isoformat()}


def plan_pilot(
    rows: list[dict], *, break_even_lift: float, target_lift: float,
    planned_pre_weeks: int = 6, planned_post_weeks: int = 6,
    heterogeneity_sd: float = 0.08, target_power: float = 0.80,
    max_pairs: int = 200, as_of: datetime | None = None,
) -> dict:
    """Size a future paired pilot to clear a specified contribution hurdle.

    Only pre-period rows enter. Full pilot rows may be passed for the public
    demo, but post rows are discarded before validation and estimation.
    """
    for label, value in (("break_even_lift", break_even_lift),
                         ("target_lift", target_lift),
                         ("heterogeneity_sd", heterogeneity_sd),
                         ("target_power", target_power)):
        if not math.isfinite(value):
            raise ValueError(f"{label} must be finite")
    if break_even_lift < -1 or target_lift < -1:
        raise ValueError("Lift cannot be below -100%")
    if heterogeneity_sd < 0:
        raise ValueError("Heterogeneity standard deviation cannot be negative")
    if not 0.5 < target_power < 1:
        raise ValueError("Target power must be between 50% and 100%")
    if min(planned_pre_weeks, planned_post_weeks) < 4 or max_pairs < 4:
        raise ValueError("Plan at least four weeks per period and four pairs")

    baseline_rows = [row for row in rows if row.get("period", "pre") == "pre"]
    parsed, quality = _validate_baseline(baseline_rows, as_of)
    by_pair: dict[str, dict[int, dict[int, float]]] = {}
    treated_pre_units = []
    for item in parsed:
        by_pair.setdefault(item["pair_id"], {}).setdefault(item["week_index"], {})[
            item["assigned_promo"]] = item["units"]
        if item["assigned_promo"]:
            treated_pre_units.append(item["units"])
    pair_week_variances = []
    for weeks in by_pair.values():
        differences = [stores[1] - stores[0] for stores in weeks.values()]
        pair_week_variances.append(variance(differences))
    baseline = mean(treated_pre_units)
    # This variance is for the treated-minus-control change within a pair.
    weekly_difference_sd = math.sqrt(mean(pair_week_variances))
    pair_measurement_variance = ((weekly_difference_sd / baseline) ** 2 *
                                 (1 / planned_pre_weeks + 1 / planned_post_weeks))
    pair_total_variance = pair_measurement_variance + heterogeneity_sd ** 2

    def probability(pair_count: int) -> float:
        if pair_total_variance == 0:
            return float(target_lift > break_even_lift)
        standard_error = math.sqrt(pair_total_variance / pair_count)
        return _normal_cdf((target_lift - break_even_lift) / standard_error -
                           ONE_SIDED_95_Z)

    required = next((count for count in range(4, max_pairs + 1)
                     if probability(count) >= target_power), None)
    return {
        "data_label": "DESIGN ILLUSTRATION; source data may be synthetic",
        **quality,
        "weekly_pair_difference_sd_units": weekly_difference_sd,
        "baseline_treated_units_per_store_week": baseline,
        "planned_pre_weeks": planned_pre_weeks,
        "planned_post_weeks": planned_post_weeks,
        "assumed_effect_heterogeneity_sd": heterogeneity_sd,
        "break_even_lift": break_even_lift,
        "target_lift": target_lift,
        "target_power": target_power,
        "one_sided_alpha": 0.05,
        "required_pairs": required,
        "max_pairs_searched": max_pairs,
        "power_at_source_pairs": probability(quality["source_pairs"]),
        "power_curve": [
            {"pairs": count, "probability_clearing_hurdle": probability(count)}
            for count in range(4, max_pairs + 1)
        ],
        "assumptions": [
            "Pre-period paired weekly differences represent future noise.",
            "Store pairs and weeks are independent; no spillovers or carryover.",
            "Between-pair effect variation is supplied by the user.",
            "Normal one-sided test is an approximation; no real-world calibration.",
        ],
    }
