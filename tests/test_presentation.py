import unittest

from alphaforge.presentation import (
    METRIC_PRESENTATION,
    MISSING_INFORMATION_LABELS,
    STATUS_LABELS,
    describe_metric_change,
    format_points,
    format_rate,
    format_weight,
    format_weight_delta,
    readable_label,
)


class PresentationTests(unittest.TestCase):
    def test_french_financial_formatting(self):
        self.assertEqual(format_rate(0.6621123813), "66,21 %")
        self.assertEqual(format_rate(0.1470250825), "14,70 %")
        self.assertEqual(format_rate(-0.1890765292), "−18,91 %")
        self.assertEqual(format_weight(32.5), "32,5 %")
        self.assertEqual(
            format_points(0.0505537343), "+5,06 points de pourcentage"
        )
        self.assertEqual(format_weight_delta(32.5), "+32,5 point(s)")

    def test_metric_definitions_are_precise_and_accessible(self):
        self.assertIn("pas un rendement annuel", METRIC_PRESENTATION["total_return"]["definition"])
        self.assertIn("ni une perte prévue", METRIC_PRESENTATION["annualized_volatility"]["definition"])
        self.assertIn("pas la perte maximale possible", METRIC_PRESENTATION["max_drawdown"]["definition"])
        self.assertIn("plus importantes", describe_metric_change("annualized_volatility", 0.01))
        self.assertIn("plus profonde", describe_metric_change("max_drawdown", -0.01))
        self.assertIn("moins profonde", describe_metric_change("max_drawdown", 0.01))

    def test_internal_labels_have_french_display_values_and_fallback(self):
        self.assertEqual(STATUS_LABELS["consistent"], "Cohérent sur ce point")
        self.assertEqual(STATUS_LABELS["tension"], "Point de vigilance")
        self.assertEqual(
            MISSING_INFORMATION_LABELS["loss_absorption_capacity"],
            "La perte que vous pourriez supporter",
        )
        self.assertEqual(
            readable_label("new_unknown_key", MISSING_INFORMATION_LABELS),
            "New unknown key",
        )


if __name__ == "__main__":
    unittest.main()
