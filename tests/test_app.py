import json
import re
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from alphaforge.engine import run_analysis
from alphaforge.profile_checks import validate_profile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

RAW_SUMMARY = (
    "Rendement total : 0.7367442289 avant, puis 1.1862126991 après "
    "via analysis.after.metrics.total_return."
)
RAW_MESSAGE = (
    "loss_absorption_capacity; analysis.before.metrics.total_return; "
    "0.7367442289; check_profile success."
)


def response_for(
    persona_id="amira",
    symbol="NVDA",
    weight=10,
    status="success",
    summary=RAW_SUMMARY,
):
    analysis = run_analysis(persona_id, symbol, weight, root=PROJECT_ROOT)
    with (DATA_DIR / "personas.json").open(encoding="utf-8") as handle:
        personas = json.load(handle)["personas"]
    persona = next(item for item in personas if item["id"] == persona_id)
    checks = validate_profile(
        persona,
        {"symbol": symbol, "target_weight_pct": weight},
        analysis,
        DATA_DIR,
    )
    explanation = {
        "summary": summary,
        "changes": [{
            "topic": "performance",
            "message": RAW_MESSAGE,
            "evidence_refs": [
                "analysis.before.metrics.total_return",
                "analysis.after.metrics.total_return",
            ],
            "metrics": [
                {
                    "evidence_ref": "analysis.before.metrics.total_return",
                    "value": analysis["before"]["metrics"]["total_return"],
                    "unit": "decimal_ratio",
                },
                {
                    "evidence_ref": "analysis.after.metrics.total_return",
                    "value": analysis["after"]["metrics"]["total_return"],
                    "unit": "decimal_ratio",
                },
            ],
        }],
        "profile_assessment": [{
            "check_id": check["id"],
            "status": check["status"],
            "message": RAW_MESSAGE,
            "evidence_refs": check.get("evidence_refs", []),
            "metrics": [],
            "missing_information": check.get("missing_information", []),
        } for check in checks],
        "uncertainties": [
            "loss_absorption_capacity",
            "analysis.before.metrics.total_return",
        ],
        "evidence_refs": ["analysis.after.metrics.total_return"],
        "tool_trace": [],
    }
    return {
        "status": status,
        "analysis": analysis,
        "checks": checks,
        "explanation": explanation if status == "success" else None,
        "warnings": [] if status == "success" else ["Explication automatique indisponible."],
        "tool_trace": [{
            "tool": "simulate_portfolio_change",
            "arguments": {
                "persona_id": persona_id,
                "symbol": symbol,
                "target_weight_pct": float(weight),
            },
            "status": "success",
            "execution_origin": "bedrock_tool_request",
        }],
    }


def rendered_text(app):
    element_names = (
        "markdown",
        "caption",
        "subheader",
        "header",
        "info",
        "warning",
        "success",
        "error",
    )
    text = [
        str(element.value)
        for name in element_names
        for element in getattr(app, name, [])
    ]
    text.extend(
        "\n".join(
            str(value)
            for value in (
                metric.label,
                metric.value,
                getattr(metric, "help", ""),
            )
        )
        for metric in app.metric
    )
    return "\n".join(text)


class StreamlitAppTests(unittest.TestCase):
    def app(self):
        return AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=60)

    def click_button(self, app, label):
        matching = [button for button in app.button if button.label == label]
        self.assertEqual(len(matching), 1, f"Expected one button labelled {label!r}")
        matching[0].click().run()

    def test_branding_identifies_agent_instead_of_mock_data(self):
        app = self.app().run()
        text = rendered_text(app)

        self.assertIn("Simulation fictive · aucune transaction réelle.", text)
        self.assertNotIn("Maquette · données fictives", text)

    def run_scenario(self, persona_name, symbol, weight):
        app = self.app().run()
        if persona_name != "Amira":
            self.click_button(app, f"Choisir {persona_name}")
        app.selectbox[0].set_value(symbol)
        app.slider[0].set_value(float(weight))
        self.click_button(app, "Analyser le scénario")
        self.assertFalse(app.exception)
        return app

    def test_no_service_call_before_submit_then_one_call_and_no_rerun(self):
        with patch("agent.service.analyze_request") as service:
            service.return_value = response_for()
            app = self.app().run()
            self.assertFalse(app.exception)
            service.assert_not_called()
            self.click_button(app, "Analyser le scénario")
            service.assert_called_once_with("amira", "NVDA", 10.0)
            self.assertTrue(any("explication Bedrock validée" in item.value for item in app.success))
            app.run()
            self.assertEqual(service.call_count, 1)

    def test_comparison_runs_only_on_request_and_keeps_a_common_period(self):
        first = response_for("amira", "NVDA", 5, status="partial")
        second = response_for("amira", "NVDA", 20, status="partial")
        comparison = {
            "status": "partial",
            "period": first["analysis"]["period"],
            "variants": [first, second],
            "warnings": [],
        }
        with patch("agent.service.analyze_comparison") as service:
            service.return_value = comparison
            app = self.app().run()
            service.assert_not_called()
            self.click_button(app, "Comparer les variantes")
            service.assert_called_once_with("amira", "NVDA", 5.0, 20.0)
            self.assertTrue(
                any("mêmes dates" in item.value for item in app.caption)
            )
            app.radio[0].set_value("Clair").run()
            self.assertEqual(service.call_count, 1)

    def test_natural_language_parameters_require_a_separate_analysis_click(self):
        parsed_request = {
            "persona_id": "amira",
            "symbol": "NVDA",
            "target_weight_pct": 15.0,
        }
        with (
            patch("agent.service.interpret_scenario_request") as interpreter,
            patch("agent.service.analyze_request") as service,
        ):
            interpreter.return_value = {
                "status": "ready",
                "request": parsed_request,
            }
            service.return_value = response_for("amira", "NVDA", 15)
            app = self.app().run()
            app.text_input[0].set_value(
                "Pour Amira, tester 15 % de NVIDIA."
            ).run()
            self.click_button(app, "Comprendre la demande")
            interpreter.assert_called_once_with(
                "Pour Amira, tester 15 % de NVIDIA.",
                root=PROJECT_ROOT,
            )
            service.assert_not_called()
            self.assertTrue(
                any("Paramètres compris" in item.value for item in app.success)
            )
            self.click_button(app, "Analyser le scénario")
            service.assert_called_once_with("amira", "NVDA", 15.0)

    def test_follow_up_percentage_requires_recalculation_after_confirmation(self):
        follow_up = {
            "status": "ready",
            "request": {
                "persona_id": "amira",
                "symbol": "NVDA",
                "target_weight_pct": 5.0,
            },
        }
        with (
            patch("agent.service.interpret_scenario_request") as interpreter,
            patch("agent.service.answer_follow_up") as answer,
            patch("agent.service.analyze_request") as service,
        ):
            interpreter.return_value = follow_up
            service.return_value = response_for("amira", "NVDA", 10)
            app = self.run_scenario("Amira", "NVDA", 10)
            app.text_input[1].set_value("Et avec 5 % ?").run()
            self.click_button(app, "Répondre à ma question")
            interpreter.assert_called_once()
            answer.assert_not_called()
            service.assert_called_once_with("amira", "NVDA", 10.0)
            self.assertTrue(
                any("Nouvelle variante comprise" in item.value for item in app.info)
            )
            self.click_button(app, "Utiliser cette variante")
            self.assertEqual(service.call_count, 1)
            self.assertEqual(app.slider[0].value, 5.0)

    def test_follow_up_answer_uses_current_report_without_reanalysis(self):
        response = response_for("amira", "NVDA", 10)
        with (
            patch("agent.service.answer_follow_up") as answer,
            patch("agent.service.analyze_request") as service,
        ):
            service.return_value = response
            answer.return_value = {
                "status": "success",
                "answer": (
                    "Les fluctuations observées reflètent des mouvements "
                    "historiques et ne prédisent pas une perte future."
                ),
                "evidence_refs": ["analysis.after.metrics.annualized_volatility"],
                "origin": "bedrock_converse",
            }
            app = self.run_scenario("Amira", "NVDA", 10)
            app.text_input[1].set_value("Pourquoi le risque change-t-il ?").run()
            self.click_button(app, "Répondre à ma question")
            answer.assert_called_once()
            service.assert_called_once_with("amira", "NVDA", 10.0)
            self.assertIn("ne prédisent pas une perte future", rendered_text(app))
            app.radio[0].set_value("Clair").run()
            self.assertEqual(answer.call_count, 1)
            self.assertEqual(service.call_count, 1)

    def test_main_view_filters_raw_prose_and_uses_structured_comparisons(self):
        with patch("agent.service.analyze_request") as service:
            service.return_value = response_for()
            app = self.run_scenario("Amira", "NVDA", 10)
            page_text = rendered_text(app)
            self.assertEqual(len(app.metric), 3)

            for heading in (
                "Scénario analysé",
                "En quelques mots",
                "Comparaisons avant/après",
                "Ce que cela signifie pour le profil",
                "Les informations qui manquent",
            ):
                self.assertIn(heading, [item.value for item in app.subheader])
            self.assertIn(
                "Dans cette simulation, Amira consacre **10 %** de son portefeuille "
                "à **NVIDIA — NVDA**. Les autres positions diminuent proportionnellement.",
                page_text,
            )
            self.assertIn("12 novembre 2021", page_text)
            self.assertIn("12 novembre 2026", page_text)
            self.assertIn(
                "Sur les cinq années étudiées, le portefeuille avec NVIDIA a "
                "davantage progressé. En contrepartie, sa valeur a davantage "
                "fluctué et sa plus forte baisse a été plus importante.",
                page_text,
            )
            self.assertIn("73,67 % avant / 118,62 % après", page_text)
            self.assertIn("21,80 % avant / 25,60 % après", page_text)
            self.assertIn("−38,64 % avant / −40,04 % après", page_text)
            self.assertEqual(page_text.count("73,67 % avant / 118,62 % après"), 1)
            self.assertEqual(page_text.count("Gain sur la période"), 1)
            self.assertIn(
                "Nous ne savons pas quelle part de NVIDIA est déjà détenue à "
                "travers les fonds du portefeuille.",
                page_text,
            )
            self.assertNotIn("diversification économique réelle", page_text)
            self.assertIn(
                "Nous ne connaissons pas encore : la perte qu’Amira pourrait "
                "supporter, ses besoins d’argent à court terme et ses retraits "
                "prévus.",
                page_text,
            )
            self.assertEqual(page_text.count("quelle part de NVIDIA"), 1)
            self.assertNotIn("0.7367442289", page_text)
            self.assertNotIn("1.1862126991", page_text)
            for internal in (
                "etf_holdings",
                "sector_exposures",
                "loss_absorption_capacity",
                "liquidity_needs",
                "planned_withdrawals",
                "analysis.",
                "source.",
                "equity",
                "check_profile",
                "simulate_portfolio_change",
                "insufficient_information",
            ):
                self.assertNotIn(internal, page_text)
            self.assertIs(app.toggle[0].value, False)
            self.assertFalse(any("Détails techniques" == item.label for item in app.expander))
            self.assertTrue(any(item.label == "Consulter les sources" for item in app.expander))
            self.assertTrue(any(item.label == "Comprendre le calcul" for item in app.expander))
            self.assertTrue(any(item.label == "Pondérations détaillées" for item in app.expander))
            self.assertEqual(service.call_count, 1)

    def test_partial_keeps_calculations_and_error_is_not_a_success(self):
        with patch("agent.service.analyze_request") as service:
            service.return_value = response_for(status="partial")
            partial = self.run_scenario("Amira", "NVDA", 10)
            self.assertTrue(any("calculs sont disponibles" in item.value for item in partial.warning))
            self.assertEqual(partial.metric[0].label, "Gain sur la période")
            self.assertEqual(len(partial.metric), 3)
            self.assertFalse(any("rapport est prêt" in item.value for item in partial.success))

        with patch("agent.service.analyze_request") as service:
            service.return_value = {
                "status": "error",
                "error": {"code": "UNKNOWN_SYMBOL", "message": "Actif inconnu."},
            }
            app = self.app().run()
            self.click_button(app, "Analyser le scénario")
            self.assertFalse(app.exception)
            self.assertTrue(any("réessayez" in item.value for item in app.error))
            self.assertFalse(any("Détails techniques" == item.label for item in app.expander))
            self.assertEqual(len(app.metric), 0)
            app.toggle[0].set_value(True).run()
            self.assertTrue(
                any(
                    "UNKNOWN_SYMBOL" in str(item.value)
                    for item in app.json
                )
            )

    def test_technical_mode_exposes_real_controls_without_reanalysis(self):
        with patch("agent.service.analyze_request") as service:
            service.return_value = response_for()
            app = self.run_scenario("Amira", "NVDA", 10)
            self.assertEqual(service.call_count, 1)
            app.toggle[0].set_value(True).run()
            self.assertFalse(app.exception)
            self.assertEqual(service.call_count, 1)
            self.assertTrue(any(item.label == "Détails techniques" for item in app.expander))
            self.assertEqual(
                sum(
                    "Informations insuffisantes" in item.value
                    for item in app.markdown
                ),
                3,
            )
            self.assertIn("analysis.after.weights_by_asset_pct.NVDA", rendered_text(app))
            self.assertTrue(
                any(
                    "insufficient_information" in str(item.value)
                    for item in app.json
                )
            )

    def test_theme_rerun_keeps_result_without_service_call(self):
        with patch("agent.service.analyze_request") as service:
            service.return_value = response_for()
            app = self.app().run()
            self.click_button(app, "Analyser le scénario")
            app.radio[0].set_value("Clair").run()
            self.assertFalse(app.exception)
            self.assertEqual(service.call_count, 1)
            self.assertIn("NVIDIA", rendered_text(app))
            self.assertEqual(len(app.metric), 3)

    def test_sources_keep_titles_links_and_french_dates(self):
        with patch("agent.service.analyze_request") as service:
            service.return_value = response_for("mateo", "XOM", 10)
            app = self.run_scenario("Mateo", "XOM", 10)
            page_text = rendered_text(app)
            self.assertIn("Yahoo Finance — historique des prix", page_text)
            self.assertIn("Banque du Canada — taux de change", page_text)
            self.assertIn("ExxonMobil", page_text)
            self.assertIn("2026 Sustainability Report - Metrics and Data", page_text)
            self.assertIn("Advocacy Report", page_text)
            self.assertIn("5 mai 2026", page_text)
            self.assertNotIn("2026-05-05", page_text)

    def test_mateo_esg_missing_information_is_grouped_once_in_main_report(self):
        with patch("agent.service.analyze_request") as service:
            service.return_value = response_for("mateo", "AAPL", 32.5)
            app = self.run_scenario("Mateo", "AAPL", 32.5)
            page_text = rendered_text(app)

        grouped_information = (
            "des preuves et une évaluation indépendante permettant de vérifier "
            "si l’actif respecte ses critères environnementaux, sociaux et de "
            "gouvernance"
        )
        self.assertIn(grouped_information, page_text)
        self.assertEqual(page_text.count(grouped_information), 1)
        self.assertNotIn("ne permettent pas d’établir", page_text)
        self.assertNotIn("asset_specific_esg_evidence", page_text)

    def test_three_requested_scenarios_render_structured_results(self):
        scenarios = [
            (
                "Amira",
                "amira",
                "NVDA",
                10.0,
                (
                    "73,67 % avant / 118,62 % après",
                    "21,80 % avant / 25,60 % après",
                    "−38,64 % avant / −40,04 % après",
                ),
            ),
            (
                "Mateo",
                "mateo",
                "AAPL",
                32.5,
                (
                    "66,21 % avant / 101,57 % après",
                    "9,65 % avant / 14,70 % après",
                    "−16,21 % avant / −18,91 % après",
                ),
            ),
            (
                "Robert",
                "robert",
                "TSLA",
                5.0,
                (
                    "41,46 % avant / 40,93 % après",
                    "6,15 % avant / 6,74 % après",
                    "−7,33 % avant / −8,30 % après",
                ),
            ),
        ]
        for display_name, persona_id, symbol, weight, expected_metrics in scenarios:
            with self.subTest(persona=display_name, asset=symbol):
                with patch("agent.service.analyze_request") as service:
                    service.return_value = response_for(persona_id, symbol, weight)
                    app = self.run_scenario(display_name, symbol, weight)
                    service.assert_called_once_with(persona_id, symbol, weight)
                    text = rendered_text(app)
                    self.assertIn("Gain sur la période", text)
                    self.assertIn("Ampleur des fluctuations", text)
                    self.assertIn("Plus forte baisse observée", text)
                    for metric_text in expected_metrics:
                        self.assertIn(metric_text, text)
                    self.assertNotRegex(text, re.compile(r"\b\d+\.\d+\b"))

    def test_changed_form_identifies_stored_scenario_and_reanalyzes_only_on_submit(self):
        def fake_service(persona_id, symbol, weight):
            return deepcopy(response_for(persona_id, symbol, weight))

        with patch("agent.service.analyze_request", side_effect=fake_service) as service:
            app = self.app().run()
            self.click_button(app, "Analyser le scénario")
            self.click_button(app, "Choisir Robert")
            self.assertEqual(service.call_count, 1)
            self.assertTrue(any("rapport précédent" in item.value for item in app.warning))
            self.assertFalse(any(item.label == "Gain sur la période" for item in app.metric))
            app.selectbox[0].set_value("TSLA")
            app.slider[0].set_value(5.0)
            self.click_button(app, "Analyser le scénario")
            self.assertEqual(service.call_count, 2)
            service.assert_called_with("robert", "TSLA", 5.0)
            self.assertIn(
                "Dans cette simulation, Robert consacre **5 %** de son portefeuille "
                "à **Tesla — TSLA**.",
                rendered_text(app),
            )


if __name__ == "__main__":
    unittest.main()
