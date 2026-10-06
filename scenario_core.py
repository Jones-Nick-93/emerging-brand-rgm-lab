"""Deterministic RGM promotion economics for explicit user assumptions.

No fitted observational elasticity is used here. Lift must come from a
scenario assumption or a separate, credible experiment.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromotionInputs:
    regular_price: float
    unit_cost: float
    baseline_units: float
    discount: float
    available_units: float
    activation_cost: float = 0.0
    funding_per_unit: float = 0.0
    displaced_units: float = 0.0
    displaced_unit_margin: float = 0.0

    def validate(self) -> None:
        if self.regular_price <= 0:
            raise ValueError("Regular price must be positive")
        if self.unit_cost < 0 or self.baseline_units <= 0 or self.available_units < 0:
            raise ValueError("Cost and available units cannot be negative; baseline units must be positive")
        if not 0 <= self.discount < 1:
            raise ValueError("Discount must be between 0% and 100%")
        if min(self.activation_cost, self.funding_per_unit, self.displaced_units,
               self.displaced_unit_margin) < 0:
            raise ValueError("Costs, funding, and displaced sales cannot be negative")

    @property
    def promo_price(self) -> float:
        return self.regular_price * (1 - self.discount)

    @property
    def promo_unit_contribution(self) -> float:
        return self.promo_price - self.unit_cost + self.funding_per_unit

    @property
    def baseline_contribution(self) -> float:
        return min(self.baseline_units, self.available_units) * (self.regular_price - self.unit_cost)

    @property
    def displaced_contribution(self) -> float:
        return self.displaced_units * self.displaced_unit_margin


def evaluate(inputs: PromotionInputs, lift: float) -> dict:
    """Compare a promotion to the same week at regular price."""
    inputs.validate()
    if lift < -1:
        raise ValueError("Unit lift cannot be below -100%")
    unconstrained_units = inputs.baseline_units * (1 + lift)
    sold_units = min(unconstrained_units, inputs.available_units)
    contribution = (sold_units * inputs.promo_unit_contribution -
                    inputs.activation_cost - inputs.displaced_contribution)
    return {"assumed_unit_lift": lift,
            "promo_price": round(inputs.promo_price, 2),
            "unconstrained_units": round(unconstrained_units, 2),
            "sold_units": round(sold_units, 2),
            "stock_limited": unconstrained_units > inputs.available_units,
            "promo_contribution": round(contribution, 2),
            "baseline_contribution": round(inputs.baseline_contribution, 2),
            "incremental_contribution": round(contribution - inputs.baseline_contribution, 2)}


def break_even_lift(inputs: PromotionInputs) -> float | None:
    """Minimum causal unit lift for nonnegative incremental contribution.

    None means the current inventory or unit economics make break-even
    impossible for any lift.
    """
    inputs.validate()
    margin = inputs.promo_unit_contribution
    target = inputs.baseline_contribution + inputs.activation_cost + inputs.displaced_contribution
    if margin <= 0:
        return None
    required_units = target / margin
    if required_units > inputs.available_units + 1e-9:
        return None
    return max(-1.0, required_units / inputs.baseline_units - 1)


def maximum_break_even_discount(inputs: PromotionInputs, lift: float) -> float | None:
    """Largest discount compatible with break-even at a supplied causal lift."""
    inputs.validate()
    if lift < -1:
        raise ValueError("Unit lift cannot be below -100%")
    sold_units = min(inputs.baseline_units * (1 + lift), inputs.available_units)
    if sold_units <= 0:
        return None
    required_price = (inputs.unit_cost - inputs.funding_per_unit +
                      (inputs.baseline_contribution + inputs.activation_cost +
                       inputs.displaced_contribution) / sold_units)
    largest_discount = 1 - required_price / inputs.regular_price
    if largest_discount < 0:
        return None
    return min(largest_discount, 1.0)


def decision_label(inputs: PromotionInputs, low_lift: float, high_lift: float,
                   evidence: str) -> str:
    """A review status, never an automatic promotion instruction."""
    low = evaluate(inputs, low_lift)["incremental_contribution"]
    high = evaluate(inputs, high_lift)["incremental_contribution"]
    if evidence != "Controlled pilot":
        return "EXPERIMENT FIRST"
    if high <= 0:
        return "REDESIGN PROMOTION"
    if low <= 0:
        return "REVIEW DOWNSIDE"
    return "CANDIDATE FOR REVIEW"


SYNTHETIC_EXAMPLE = PromotionInputs(
    regular_price=4.99,
    unit_cost=2.10,
    baseline_units=800,
    discount=0.10,
    available_units=1300,
    activation_cost=180,
    funding_per_unit=0.20,
    displaced_units=40,
    displaced_unit_margin=1.20,
)
