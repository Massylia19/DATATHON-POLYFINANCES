import unittest

from alphaforge.presentation import (
    METRIC_PRESENTATION,
    MISSING_INFORMATION_LABELS,
    STATUS_LABELS,
    build_main_summary,
    describe_metric_change,
    format_date_fr,
    format_preferences,
    format_points,
    format_rate,
    format_weight,
    format_weight_delta,
    has_unsafe_main_narrative,
    join_french_list,
    missing_information_phrases,
    readable_label,
)


class PresentationTests(unittest.TestCase):
    def test_french_financial_formatting(self):
        self.assertEqual(format_rate(0.6621123813), "66,21 %")
        self.assertEqual(format_rate(0.1470250825), "14,70 %")
        self.assertEqual(format_rate(-0.1890765292), "−18,91 %")
        self.assertEqual(format_weight(10), "10 %")
        self.assertEqual(format_weight(32.5), "32,5 %")
        self.assertEqual(
            format_points(0.0505537343), "+5,06 points de pourcentage"
        )
        self.assertEqual(
            format_weight_delta(32.5), "+32,5 points de pourcentage"
        )

    def test_metric_definitions_are_precise_and_accessible(self):
        self.assertEqual(
            METRIC_PRESENTATION["total_return"]["definition"],
            "Progression totale sur les dates étudiées, pas un gain annuel.",
        )
        self.assertIn(
            "Ce n’est pas une perte prévue.",
            METRIC_PRESENTATION["annualized_volatility"]["definition"],
        )
        self.assertIn(
            "Des pertes futures pourraient être plus importantes.",
            METRIC_PRESENTATION["max_drawdown"]["definition"],
        )
        self.assertIn("davantage fluctué", describe_metric_change("annualized_volatility", 0.01))
        self.assertIn("plus importante", describe_metric_change("max_drawdown", -0.01))
        self.assertIn("moins importante", describe_metric_change("max_drawdown", 0.01))

    def test_structured_labels_never_expose_unknown_internal_keys(self):
        self.assertEqual(
            STATUS_LABELS["consistent"],
            "Aucune tension supplémentaire observée sur ce point",
        )
        self.assertEqual(STATUS_LABELS["tension"], "Point de vigilance")
        self.assertEqual(
            MISSING_INFORMATION_LABELS["loss_absorption_capacity"],
            "la perte {loss_clause} pourrait supporter",
        )
        self.assertEqual(
            readable_label("new_unknown_key", MISSING_INFORMATION_LABELS),
            "Autre information à vérifier",
        )

    def test_profile_card_labels_are_accessible_french(self):
        self.assertEqual(
            format_preferences(["ESG", "stabilité", "peu de spéculation"]),
            "critères environnementaux, sociaux et de gouvernance, stabilité "
            "et peu de placements spéculatifs",
        )

    def test_missing_information_is_personalized_grouped_and_deduplicated(self):
        items = missing_information_phrases(
            [
                "loss_absorption_capacity",
                "liquidity_needs",
                "planned_withdrawals",
                "etf_holdings",
                "sector_exposures",
                "etf_holdings",
            ],
            "Amira",
        )
        self.assertEqual(
            items,
            [
                "la composition des fonds, nécessaire pour connaître les "
                "placements indirects et leur répartition par secteur",
                "la perte qu’Amira pourrait supporter",
                "ses besoins d’argent à court terme",
                "ses retraits prévus",
            ],
        )
        self.assertEqual(
            join_french_list(items[1:]),
            "la perte qu’Amira pourrait supporter, ses besoins d’argent à court "
            "terme et ses retraits prévus",
        )

    def test_esg_missing_evidence_is_grouped_without_repeating_the_same_gap(self):
        phrases = missing_information_phrases(
            [
                "asset_specific_esg_evidence",
                "independent_esg_assessment",
                "asset_specific_esg_evidence",
            ],
            "Mateo",
        )

        self.assertEqual(
            phrases,
            [
                "des preuves et une évaluation indépendante permettant de "
                "vérifier si l’actif respecte ses critères environnementaux, "
                "sociaux et de gouvernance"
            ],
        )

    def test_dates_and_model_prose_safety(self):
        self.assertEqual(format_date_fr("2021-11-12"), "12 novembre 2021")
        self.assertEqual(format_date_fr("2026-08"), "août 2026")
        self.assertFalse(
            has_unsafe_main_narrative(
                "Le portefeuille a progressé, mais ses fluctuations augmentent."
            )
        )
        for unsafe in (
            "Rendement : 0.7367442289",
            "loss_absorption_capacity",
            "analysis.after.metrics.total_return",
            "check_profile a retourné success",
            "La volatilité annualisée a augmenté.",
        ):
            self.assertTrue(has_unsafe_main_narrative(unsafe), unsafe)

    def test_unsafe_summary_uses_structured_comparisons_not_model_numbers(self):
        analysis = {
            "period": {"start": "2021-11-12", "end": "2026-11-12"},
            "scenario": {"added_symbol": "NVDA"},
            "before": {
                "metrics": {
                    "total_return": 0.7367442289,
                    "annualized_volatility": 0.2179988349,
                    "max_drawdown": -0.3864223762,
                }
            },
            "after": {
                "metrics": {
                    "total_return": 1.1862126991,
                    "annualized_volatility": 0.255958911,
                    "max_drawdown": -0.4004060225,
                }
            },
            "delta_after_minus_before": {
                "metrics": {
                    "total_return": 0.4494684702,
                    "annualized_volatility": 0.0379600761,
                    "max_drawdown": -0.0139836463,
                }
            },
        }
        summary = build_main_summary(
            analysis,
            {
                "name": "Amira",
                "objective": "Croissance à long terme",
            },
            "NVIDIA",
            {"summary": "Rendement total : 0.7367442289, analysis.after.metrics.total_return"},
        )
        self.assertEqual(
            summary,
            "Sur les cinq années étudiées, le portefeuille avec NVIDIA a "
            "davantage progressé. En contrepartie, sa valeur a davantage "
            "fluctué et sa plus forte baisse a été plus importante. Ce "
            "compromis est à mettre en regard de l’objectif de croissance à "
            "long terme d’Amira.",
        )

    def test_safe_claude_summary_is_preserved_and_linked_to_the_profile(self):
        analysis = {
            "period": {"start": "2021-11-12", "end": "2026-11-12"},
            "scenario": {"added_symbol": "NVDA"},
            "before": {"metrics": {}},
            "after": {"metrics": {}},
            "delta_after_minus_before": {
                "metrics": {
                    "total_return": 0.1,
                    "annualized_volatility": 0.02,
                    "max_drawdown": -0.01,
                }
            },
        }
        claude_summary = (
            "Le portefeuille progresse davantage, mais ses fluctuations augmentent."
        )
        summary = build_main_summary(
            analysis,
            {"name": "Amira", "objective": "Croissance à long terme"},
            "NVIDIA",
            {"summary": claude_summary},
        )
        self.assertTrue(summary.startswith(claude_summary))
        self.assertIn("objectif de croissance à long terme d’Amira", summary)


if __name__ == "__main__":
    unittest.main()
