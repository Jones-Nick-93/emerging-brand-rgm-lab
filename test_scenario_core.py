import math
import unittest

from scenario_core import (PromotionInputs, break_even_lift, decision_label,
                           evaluate, maximum_break_even_discount)


class ScenarioCoreTests(unittest.TestCase):
    def test_break_even_lift_makes_incremental_contribution_zero(self):
        assumptions = PromotionInputs(regular_price=5, unit_cost=2, baseline_units=100,
                                      discount=0.1, available_units=300, activation_cost=25)
        lift = break_even_lift(assumptions)
        self.assertIsNotNone(lift)
        self.assertAlmostEqual(evaluate(assumptions, lift)["incremental_contribution"], 0, places=2)
        self.assertLess(evaluate(assumptions, lift - 0.05)["incremental_contribution"], 0)

    def test_inventory_or_negative_unit_margin_can_block_break_even(self):
        low_stock = PromotionInputs(5, 2, 100, 0.2, 90, activation_cost=30)
        self.assertIsNone(break_even_lift(low_stock))
        negative_margin = PromotionInputs(5, 4.5, 100, 0.2, 300)
        self.assertIsNone(break_even_lift(negative_margin))

    def test_maximum_discount_is_break_even_at_supplied_lift(self):
        assumptions = PromotionInputs(5, 2, 100, 0.1, 300, funding_per_unit=0.3)
        max_discount = maximum_break_even_discount(assumptions, 0.25)
        self.assertIsNotNone(max_discount)
        at_boundary = PromotionInputs(5, 2, 100, max_discount, 300, funding_per_unit=0.3)
        self.assertAlmostEqual(evaluate(at_boundary, 0.25)["incremental_contribution"], 0, places=2)

    def test_displaced_sales_and_funding_change_promotion_economics(self):
        base = PromotionInputs(5, 2, 100, 0.1, 300)
        funded = PromotionInputs(5, 2, 100, 0.1, 300, funding_per_unit=0.5)
        displaced = PromotionInputs(5, 2, 100, 0.1, 300, displaced_units=20,
                                    displaced_unit_margin=1.5)
        self.assertGreater(evaluate(funded, 0.2)["incremental_contribution"],
                           evaluate(base, 0.2)["incremental_contribution"])
        self.assertLess(evaluate(displaced, 0.2)["incremental_contribution"],
                        evaluate(base, 0.2)["incremental_contribution"])

    def test_scenario_assumptions_do_not_become_an_automatic_decision(self):
        assumptions = PromotionInputs(5, 2, 100, 0.05, 300)
        self.assertEqual(decision_label(assumptions, 0.0, 0.5, "Assumption"),
                         "EXPERIMENT FIRST")
        self.assertNotEqual(decision_label(assumptions, 0.5, 1.0, "Controlled pilot"),
                            "APPROVED")

    def test_invalid_inputs_rejected(self):
        with self.assertRaises(ValueError):
            evaluate(PromotionInputs(5, 2, 100, 1.0, 300), 0.2)
        with self.assertRaises(ValueError):
            evaluate(PromotionInputs(5, 2, 100, 0.1, 300), -1.1)


if __name__ == "__main__":
    unittest.main()
