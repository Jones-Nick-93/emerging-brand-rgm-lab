import copy
import csv
import io
import unittest
from datetime import datetime, timezone

from pilot_core import (analyze_pilot, rows_to_csv, synthetic_pilot,
                        transfer_blockers, validate_pilot)


class PilotCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.truth = synthetic_pilot()

    def test_synthetic_pilot_passes_contract_and_recovers_known_effect(self):
        quality = validate_pilot(self.rows)
        self.assertTrue(quality.ready, quality.blockers)
        self.assertEqual((quality.pairs, quality.stores, quality.rows), (12, 24, 288))
        estimate = analyze_pilot(self.rows)
        self.assertLess(abs(estimate["pooled_lift"] - self.truth["true_mean_assigned_lift"]), 0.05)
        self.assertLess(estimate["interval_90"][0], self.truth["true_mean_assigned_lift"])
        self.assertGreater(estimate["interval_90"][1], self.truth["true_mean_assigned_lift"])

    def test_matched_change_removes_fixed_store_imbalance(self):
        estimate = analyze_pilot(self.rows, bootstrap_samples=100)
        shifted = copy.deepcopy(self.rows)
        for row in shifted:
            if row["assigned_promo"]:
                row["units"] += 35
        shifted_estimate = analyze_pilot(shifted, bootstrap_samples=100)
        for before, after in zip(estimate["pair_results"], shifted_estimate["pair_results"]):
            self.assertAlmostEqual(before["effect_units_per_store_week"],
                                   after["effect_units_per_store_week"], places=5)
        self.assertGreater(shifted_estimate["naive_post_ratio"] - estimate["naive_post_ratio"], 0.10)

    def test_pair_shrinkage_and_bootstrap_are_reproducible(self):
        first = analyze_pilot(self.rows, bootstrap_samples=100, seed=9)
        second = analyze_pilot(self.rows, bootstrap_samples=100, seed=9)
        self.assertEqual(first["interval_90"], second["interval_90"])
        self.assertTrue(any(abs(item["pooled_pair_lift"] - first["pooled_lift"]) <
                            abs(item["lift"] - first["pooled_lift"])
                            for item in first["pair_results"]))

    def test_duplicate_missing_stockout_and_execution_errors_block(self):
        cases = []
        cases.append(self.rows + [self.rows[0]])
        missing = copy.deepcopy(self.rows)
        missing.pop(0)
        cases.append(missing)
        stockout = copy.deepcopy(self.rows)
        stockout[0]["stockout"] = 1
        cases.append(stockout)
        mismatch = copy.deepcopy(self.rows)
        for row in mismatch:
            if row["period"] == "post" and row["assigned_promo"]:
                row["executed_promo"] = 0
                break
        cases.append(mismatch)
        for rows in cases:
            with self.subTest(case=len(rows), first=rows[0]):
                self.assertFalse(validate_pilot(rows).ready)
                with self.assertRaises(ValueError):
                    analyze_pilot(rows, bootstrap_samples=100)

    def test_as_of_fields_and_numeric_contract_block_bad_rows(self):
        rows = copy.deepcopy(self.rows)
        rows[0]["ingested_at"] = "2024-01-01T00:00:00+00:00"
        self.assertFalse(validate_pilot(rows).ready)
        rows = copy.deepcopy(self.rows)
        rows[0]["units"] = "nan"
        self.assertFalse(validate_pilot(rows).ready)

    def test_csv_round_trip_is_analysis_equivalent(self):
        text = rows_to_csv(self.rows)
        loaded = list(csv.DictReader(io.StringIO(text)))
        self.assertTrue(validate_pilot(loaded).ready)
        self.assertAlmostEqual(analyze_pilot(loaded, bootstrap_samples=100)["pooled_lift"],
                               analyze_pilot(self.rows, bootstrap_samples=100)["pooled_lift"])

    def test_untested_price_or_discount_blocks_scenario_transfer(self):
        pilot = analyze_pilot(self.rows, bootstrap_samples=100)
        self.assertEqual(transfer_blockers(pilot, "SYNTHETIC-SKU", 4.99, 0.10), [])
        self.assertTrue(transfer_blockers(pilot, "OTHER-SKU", 4.99, 0.10))
        self.assertTrue(transfer_blockers(pilot, "SYNTHETIC-SKU", 5.99, 0.10))
        self.assertTrue(transfer_blockers(pilot, "SYNTHETIC-SKU", 4.99, 0.20))

    def test_fractional_assignment_and_week_index_are_rejected(self):
        rows = copy.deepcopy(self.rows)
        rows[0]["assigned_promo"] = 0.5
        self.assertFalse(validate_pilot(rows).ready)
        rows = copy.deepcopy(self.rows)
        rows[0]["week_index"] = -5.5
        self.assertFalse(validate_pilot(rows).ready)

    def test_future_ingestion_is_blocked_by_as_of_cutoff(self):
        cutoff = datetime(2025, 3, 1, tzinfo=timezone.utc)
        self.assertFalse(validate_pilot(self.rows, as_of=cutoff).ready)


if __name__ == "__main__":
    unittest.main()
