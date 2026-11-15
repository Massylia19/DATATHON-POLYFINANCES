import json
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from alphaforge.engine import run_analysis
from alphaforge.profile_checks import validate_profile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"


def response_for(persona_id="amira", symbol="NVDA", weight=10, status="success"):
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
        "summary": "Comparaison historique hypothétique validée.",
        "changes": [{
            "topic": "performance",
            "message": "Le rendement historique diffère avant et après.",
            "evidence_refs": ["analysis.after.metrics.total_return"],
            "metrics": [],
        }],
        "profile_assessment": [{
            "check_id": check["id"],
            "status": check["status"],
            "message": check["message"],
            "evidence_refs": check.get("evidence_refs", []),
            "metrics": [],
            "missing_information": check.get("missing_information", []),
        } for check in checks],
        "uncertainties": ["Les performances historiques ne prédisent pas l’avenir."],
        "evidence_refs": ["analysis.after.metrics.total_return"],
        "tool_trace": [],
    }
    return {
        "status": status,
        "analysis": analysis,
        "checks": checks,
        "explanation": explanation if status == "success" else None,
        "warnings": [] if status == "success" else ["Explication IA indisponible."],
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


class StreamlitAppTests(unittest.TestCase):
    def app(self):
        return AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=60)

    def test_no_service_call_before_submit_then_one_call_and_no_rerun(self):
        with patch("agent.service.analyze_request") as service:
            service.return_value = response_for()
            app = self.app().run()
            self.assertFalse(app.exception)
            service.assert_not_called()
            app.button[0].click().run()
            service.assert_called_once_with("amira", "NVDA", 10.0)
            self.assertTrue(any("Bedrock terminées" in item.value for item in app.success))
            app.run()
            self.assertEqual(service.call_count, 1)

    def test_success_renders_analysis_checks_explanation_evidence_and_trace(self):
        with patch("agent.service.analyze_request") as service:
            service.return_value = response_for()
            app = self.app().run()
            app.button[0].click().run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.metric), 3)
            page_text = " ".join(item.value for item in app.markdown)
            self.assertIn("Contrôles du profil", page_text)
            self.assertIn("Changement — performance", page_text)
            self.assertTrue(any("AWS Bedrock" in item.value for item in app.caption))
            self.assertTrue(any("Preuves consultables" in item.label for item in app.expander))
            self.assertTrue(any("Traces factuelles" in item.label for item in app.expander))

    def test_partial_preserves_calculations_without_claiming_ai_explanation(self):
        with patch("agent.service.analyze_request") as service:
            service.return_value = response_for(status="partial")
            app = self.app().run()
            app.button[0].click().run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.metric), 3)
            warnings = " ".join(item.value for item in app.warning)
            self.assertIn("Analyse partielle", warnings)
            self.assertTrue(any("validée indisponible" in item.value for item in app.info))
            self.assertFalse(any("AWS Bedrock" in item.value for item in app.caption))

    def test_error_response_is_displayed_without_old_success(self):
        with patch("agent.service.analyze_request") as service:
            service.return_value = {
                "status": "error",
                "error": {"code": "UNKNOWN_SYMBOL", "message": "Actif inconnu."},
            }
            app = self.app().run()
            app.button[0].click().run()
            self.assertFalse(app.exception)
            self.assertTrue(any("UNKNOWN_SYMBOL" in item.value for item in app.error))
            self.assertEqual(len(app.metric), 0)

    def test_theme_rerun_keeps_result_without_service_call(self):
        with patch("agent.service.analyze_request") as service:
            service.return_value = response_for()
            app = self.app().run()
            app.button[0].click().run()
            app.radio[0].set_value("Sombre").run()
            self.assertFalse(app.exception)
            self.assertEqual(service.call_count, 1)
            self.assertEqual(len(app.metric), 3)
            self.assertTrue(any("amira / NVDA / 10 %" in item.value for item in app.markdown))

    def test_mateo_esg_evidence_dates_and_links_are_rendered(self):
        with patch("agent.service.analyze_request") as service:
            service.return_value = response_for("mateo", "XOM", 10)
            app = self.app().run()
            app.selectbox[0].set_value("Mateo").run()
            app.selectbox[1].set_value("XOM")
            app.slider[0].set_value(10.0)
            app.button[0].click().run()

            self.assertFalse(app.exception)
            service.assert_called_once_with("mateo", "XOM", 10.0)
            page_text = " ".join(item.value for item in app.markdown)
            self.assertIn("ExxonMobil", page_text)
            self.assertIn("2026-05-05", page_text)
            self.assertIn("Consulter la source", page_text)

    def test_changed_form_identifies_stored_scenario_and_new_submit_calls_again(self):
        def fake_service(persona_id, symbol, weight):
            return deepcopy(response_for(persona_id, symbol, weight))

        with patch("agent.service.analyze_request", side_effect=fake_service) as service:
            app = self.app().run()
            app.button[0].click().run()
            app.selectbox[0].set_value("Robert").run()
            self.assertEqual(service.call_count, 1)
            self.assertTrue(any("un autre scénario" in item.value for item in app.warning))
            self.assertTrue(any("amira / NVDA / 10 %" in item.value for item in app.markdown))
            app.selectbox[1].set_value("TSLA")
            app.slider[0].set_value(5.0)
            app.button[0].click().run()
            self.assertEqual(service.call_count, 2)
            service.assert_called_with("robert", "TSLA", 5.0)
            self.assertTrue(any("robert / TSLA / 5 %" in item.value for item in app.markdown))


if __name__ == "__main__":
    unittest.main()
