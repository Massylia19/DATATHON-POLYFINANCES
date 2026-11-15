import os
import unittest
from unittest.mock import patch

from agent.service import analyze_comparison
from alphaforge.engine import PROJECT_ROOT


class ComparisonTests(unittest.TestCase):
    def test_same_asset_variants_use_identical_dates_and_real_calculations(self):
        with patch.dict(os.environ, {"BEDROCK_MODEL_ID": ""}):
            result = analyze_comparison(
                "amira",
                "NVDA",
                5,
                20,
                root=PROJECT_ROOT,
            )

        self.assertEqual(result["status"], "partial")
        first, second = result["variants"]
        first_analysis = first["analysis"]
        second_analysis = second["analysis"]
        self.assertEqual(
            first_analysis["series"]["dates"],
            second_analysis["series"]["dates"],
        )
        self.assertEqual(first_analysis["period"], second_analysis["period"])
        self.assertNotEqual(
            first_analysis["after"]["metrics"],
            second_analysis["after"]["metrics"],
        )

    def test_identical_weights_are_rejected_without_running_analysis(self):
        with patch("agent.service.analyze_request") as analyze:
            result = analyze_comparison("amira", "NVDA", 10, 10)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "IDENTICAL_VARIANTS")
        analyze.assert_not_called()

    def test_invalid_variant_is_rejected_before_bedrock_analysis(self):
        with patch("agent.service.analyze_request") as analyze:
            result = analyze_comparison("amira", "NVDA", 5, 100)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "INVALID_WEIGHT")
        analyze.assert_not_called()

    def test_different_date_series_block_the_comparison(self):
        def fake_response(start, dates):
            return {
                "status": "partial",
                "analysis": {
                    "period": {
                        "start": start,
                        "end": dates[-1],
                        "common_observations": len(dates),
                    },
                    "series": {"dates": dates},
                },
                "warnings": [],
            }

        with patch(
            "agent.service.analyze_request",
            side_effect=[
                fake_response("2021-11-12", ["2021-11-12", "2021-11-15"]),
                fake_response("2021-11-15", ["2021-11-15", "2021-11-16"]),
            ],
        ):
            result = analyze_comparison("amira", "NVDA", 5, 20)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "INCOMPARABLE_PERIODS")


if __name__ == "__main__":
    unittest.main()
