import unittest
from pathlib import Path

from alphaforge.engine import compare_case, load_case
from alphaforge.profile_checks import VALID_STATUSES, validate_profile


ROOT = Path(__file__).resolve().parents[1]


class ProfileCheckTests(unittest.TestCase):
    def test_three_personas_follow_the_common_contract(self):
        cases = (
            ("amira", {"concentration", "diversification", "etf_overlap"}),
            ("mateo", {"esg_compatibility"}),
            ("robert", {"capital_preservation"}),
        )
        required = {
            "id",
            "status",
            "title",
            "message",
            "evidence_refs",
            "missing_information",
        }

        for persona_id, expected_ids in cases:
            with self.subTest(persona_id=persona_id):
                profile, _portfolio, scenario = load_case(ROOT / "data", persona_id)
                analysis = compare_case(ROOT, persona_id)
                findings = validate_profile(
                    profile, scenario, analysis, ROOT / "data"
                )

                self.assertEqual({item["id"] for item in findings}, expected_ids)
                for finding in findings:
                    self.assertTrue(required.issubset(finding))
                    self.assertIn(finding["status"], VALID_STATUSES)
                    self.assertIsInstance(finding["evidence_refs"], list)
                    self.assertIsInstance(finding["missing_information"], list)

    def test_mateo_uses_dated_asset_specific_evidence(self):
        profile, _portfolio, scenario = load_case(ROOT / "data", "mateo")
        analysis = compare_case(ROOT, "mateo")
        finding = validate_profile(
            profile, scenario, analysis, ROOT / "data"
        )[0]

        self.assertEqual(finding["status"], "insufficient_information")
        self.assertTrue(finding["evidence"]["esg_evidence_available"])
        self.assertGreater(finding["evidence"]["evidence_count"], 0)
        self.assertTrue(finding["evidence_refs"])
        for evidence in finding["evidence"]["assessed_evidence"]:
            self.assertTrue(evidence["valid_date"])
            self.assertTrue(evidence["id"])

    def test_robert_status_is_derived_from_metrics(self):
        profile, _portfolio, scenario = load_case(ROOT / "data", "robert")
        analysis = compare_case(ROOT, "robert")

        actual = validate_profile(profile, scenario, analysis, ROOT / "data")[0]
        expected = (
            "tension"
            if (
                analysis["delta_after_minus_before"]["metrics"][
                    "annualized_volatility"
                ]
                > 0
                or analysis["delta_after_minus_before"]["metrics"]["max_drawdown"]
                < 0
            )
            else "consistent"
        )
        self.assertEqual(actual["status"], expected)


if __name__ == "__main__":
    unittest.main()
