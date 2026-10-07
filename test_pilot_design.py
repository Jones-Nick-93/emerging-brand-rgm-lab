import copy
import unittest
from datetime import datetime, timezone

from pilot_core import synthetic_pilot
from pilot_design import baseline_rows_to_csv, plan_pilot


class PilotDesignTests(unittest.TestCase):
    AS_OF = datetime(2026, 1, 1, tzinfo=timezone.utc)
    @classmethod
    def setUpClass(cls):
        cls.rows, _ = synthetic_pilot()

    def test_larger_effect_and_longer_pilot_need_no_more_pairs(self):
        base = plan_pilot(self.rows, break_even_lift=0.15, target_lift=0.25)
        stronger = plan_pilot(self.rows, break_even_lift=0.15, target_lift=0.35)
        longer = plan_pilot(self.rows, break_even_lift=0.15, target_lift=0.25,
                            planned_post_weeks=12)
        self.assertIsNotNone(base["required_pairs"])
        self.assertLessEqual(stronger["required_pairs"], base["required_pairs"])
        self.assertLessEqual(longer["required_pairs"], base["required_pairs"])

    def test_post_outcomes_cannot_change_preperiod_noise_or_sizing(self):
        changed = copy.deepcopy(self.rows)
        for row in changed:
            if row["period"] == "post":
                row["units"] += 50
        before = plan_pilot(self.rows, break_even_lift=0.15, target_lift=0.25,
                            as_of=self.AS_OF)
        after = plan_pilot(changed, break_even_lift=0.15, target_lift=0.25,
                           as_of=self.AS_OF)
        self.assertEqual(before, after)

    def test_preperiod_only_csv_supports_prospective_design(self):
        import csv
        import io

        baseline = list(csv.DictReader(io.StringIO(baseline_rows_to_csv(self.rows))))
        complete = plan_pilot(self.rows, break_even_lift=0.15, target_lift=0.25,
                              as_of=self.AS_OF)
        prospective = plan_pilot(baseline, break_even_lift=0.15, target_lift=0.25,
                                 as_of=self.AS_OF)
        self.assertEqual(complete, prospective)
        self.assertEqual(prospective["source_rows"], 144)

    def test_target_below_hurdle_has_no_spurious_sample_size(self):
        result = plan_pilot(self.rows, break_even_lift=0.30, target_lift=0.20)
        self.assertIsNone(result["required_pairs"])
        self.assertLess(result["power_at_source_pairs"], 0.05)

    def test_invalid_contract_and_assumptions_are_rejected(self):
        invalid = copy.deepcopy(self.rows)
        invalid[0]["stockout"] = 1
        with self.assertRaisesRegex(ValueError, "stockout"):
            plan_pilot(invalid, break_even_lift=0.15, target_lift=0.25)
        with self.assertRaisesRegex(ValueError, "Heterogeneity"):
            plan_pilot(self.rows, break_even_lift=0.15, target_lift=0.25,
                       heterogeneity_sd=-0.1)
        baseline = [row for row in self.rows if row["period"] == "pre"]
        with self.assertRaisesRegex(ValueError, "Duplicate store-week"):
            plan_pilot(baseline + [baseline[0]], break_even_lift=0.15,
                       target_lift=0.25)
        missing = copy.deepcopy(baseline)
        missing.pop(0)
        with self.assertRaisesRegex(ValueError, "missing weeks"):
            plan_pilot(missing, break_even_lift=0.15, target_lift=0.25)


if __name__ == "__main__":
    unittest.main()
