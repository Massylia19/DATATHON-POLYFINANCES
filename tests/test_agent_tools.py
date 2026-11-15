import unittest
from pathlib import Path
from unittest.mock import patch

from agent import (
    EXPLANATION_FORMAT,
    MODEL_EXPLANATION_FORMAT,
    SYSTEM_INSTRUCTIONS,
    TOOL_SPECS,
    build_evidence_bundle,
    build_interface_payload,
    create_request_context,
    dispatch_tool,
    resolve_evidence_reference,
)
from alphaforge.engine import run_analysis
from alphaforge.engine import EngineError


ROOT = Path(__file__).resolve().parents[1]


def arguments(persona_id: str, symbol: str, weight: float) -> dict:
    return {
        "persona_id": persona_id,
        "symbol": symbol,
        "target_weight_pct": weight,
    }


class AgentToolTests(unittest.TestCase):
    def test_real_amira_simulation_and_argument_forwarding(self):
        context = create_request_context("amira", "nvda", 10, root=ROOT)
        payload = arguments("amira", "NVDA", 10)

        with patch("agent.tools.run_analysis", wraps=run_analysis) as mocked:
            response = dispatch_tool(
                context, "simulate_portfolio_change", payload
            )

        self.assertEqual(response["status"], "success")
        mocked.assert_called_once_with("amira", "NVDA", 10.0, root=ROOT.resolve())
        analysis = response["result"]
        self.assertEqual(analysis["scenario"]["added_symbol"], "NVDA")
        self.assertEqual(analysis["scenario"]["target_weight_pct"], 10.0)
        self.assertEqual(analysis["series"]["before"][0], 100.0)
        self.assertIs(context.analysis, analysis)

    def test_simulation_then_checks_for_all_personas(self):
        cases = (
            ("amira", "NVDA", 10),
            ("mateo", "XOM", 10),
            ("robert", "TSLA", 5),
        )
        for persona_id, symbol, weight in cases:
            with self.subTest(persona_id=persona_id):
                context = create_request_context(
                    persona_id, symbol, weight, root=ROOT
                )
                payload = arguments(persona_id, symbol, weight)
                self.assertEqual(
                    dispatch_tool(
                        context, "simulate_portfolio_change", payload
                    )["status"],
                    "success",
                )
                response = dispatch_tool(context, "check_profile", payload)
                self.assertEqual(response["status"], "success")
                self.assertTrue(response["result"])
                self.assertEqual(context.checks, response["result"])
                self.assertTrue(
                    all(
                        check["status"]
                        in {"consistent", "tension", "insufficient_information"}
                        for check in response["result"]
                    )
                )

    def test_check_requires_successful_simulation(self):
        context = create_request_context("amira", "NVDA", 10, root=ROOT)
        response = dispatch_tool(
            context, "check_profile", arguments("amira", "NVDA", 10)
        )
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["error"]["code"], "SIMULATION_REQUIRED")

    def test_unknown_tool_and_malformed_arguments_are_rejected(self):
        context = create_request_context("amira", "NVDA", 10, root=ROOT)
        unknown = dispatch_tool(context, "read_arbitrary_file", {})
        malformed = dispatch_tool(
            context,
            "simulate_portfolio_change",
            {**arguments("amira", "NVDA", 10), "engine_results": {}},
        )
        wrong_type = dispatch_tool(
            context, "simulate_portfolio_change", ["amira", "NVDA", 10]
        )

        self.assertEqual(unknown["error"]["code"], "UNKNOWN_TOOL")
        self.assertEqual(malformed["error"]["code"], "INVALID_TOOL_ARGUMENTS")
        self.assertEqual(wrong_type["error"]["code"], "INVALID_TOOL_ARGUMENTS")

    def test_request_cannot_be_changed_by_a_tool_call(self):
        context = create_request_context("amira", "NVDA", 10, root=ROOT)
        for changed in (
            arguments("mateo", "NVDA", 10),
            arguments("amira", "TSLA", 10),
            arguments("amira", "NVDA", 20),
        ):
            with self.subTest(changed=changed):
                response = dispatch_tool(
                    context, "simulate_portfolio_change", changed
                )
                self.assertEqual(response["error"]["code"], "REQUEST_MISMATCH")
        self.assertIsNone(context.analysis)

    def test_engine_and_profile_check_errors_are_not_successes(self):
        context = create_request_context("amira", "NVDA", 10, root=ROOT)
        payload = arguments("amira", "NVDA", 10)
        with patch(
            "agent.tools.run_analysis",
            side_effect=EngineError("INSUFFICIENT_DATA", "Données insuffisantes"),
        ):
            engine_response = dispatch_tool(
                context, "simulate_portfolio_change", payload
            )
        self.assertEqual(engine_response["status"], "error")
        self.assertEqual(engine_response["error"]["code"], "INSUFFICIENT_DATA")
        self.assertEqual(context.tool_trace[-1]["status"], "error")

        dispatch_tool(context, "simulate_portfolio_change", payload)
        with patch(
            "agent.tools.validate_profile", side_effect=ValueError("contrôle invalide")
        ):
            check_response = dispatch_tool(context, "check_profile", payload)
        self.assertEqual(check_response["status"], "error")
        self.assertEqual(check_response["error"]["code"], "PROFILE_CHECK_ERROR")
        self.assertEqual(context.tool_trace[-1]["status"], "error")

    def test_request_contexts_are_isolated(self):
        first = create_request_context("amira", "NVDA", 10, root=ROOT)
        second = create_request_context("robert", "TSLA", 5, root=ROOT)
        dispatch_tool(
            first,
            "simulate_portfolio_change",
            arguments("amira", "NVDA", 10),
        )

        self.assertIsNotNone(first.analysis)
        self.assertIsNone(second.analysis)
        self.assertTrue(first.tool_trace)
        self.assertEqual(second.tool_trace, [])
        self.assertIsNot(first.tool_trace, second.tool_trace)

    def test_evidence_resolution_and_missing_references(self):
        context = create_request_context("mateo", "XOM", 10, root=ROOT)
        payload = arguments("mateo", "XOM", 10)
        dispatch_tool(context, "simulate_portfolio_change", payload)
        dispatch_tool(context, "check_profile", payload)

        metric = resolve_evidence_reference(
            context, "analysis.after.metrics.annualized_volatility"
        )
        esg = resolve_evidence_reference(
            context, "source.src_xom_sustainability_metrics_2026"
        )
        missing = resolve_evidence_reference(
            context, "analysis.after.metrics.does_not_exist"
        )
        bundle = build_evidence_bundle(context)
        interface = build_interface_payload(context)

        self.assertEqual(metric["status"], "resolved")
        self.assertEqual(esg["status"], "resolved")
        self.assertEqual(missing["status"], "missing")
        self.assertNotIn("series", bundle["analysis"])
        self.assertNotIn("tool_trace", bundle)
        self.assertIn("series_summary", bundle)
        self.assertIn("series", interface["analysis"])
        self.assertTrue(bundle["referenced_esg_sources"])

    def test_trace_records_real_calls_without_series_duplication(self):
        context = create_request_context("amira", "NVDA", 10, root=ROOT)
        payload = arguments("amira", "NVDA", 10)
        dispatch_tool(context, "simulate_portfolio_change", payload)
        dispatch_tool(context, "check_profile", payload)

        self.assertEqual(
            [entry["tool"] for entry in context.tool_trace],
            ["simulate_portfolio_change", "check_profile"],
        )
        self.assertTrue(all(entry["status"] == "success" for entry in context.tool_trace))
        self.assertEqual(context.tool_trace[0]["arguments"], payload)
        self.assertNotIn("series", context.tool_trace[0]["result"])
        self.assertEqual(
            context.tool_trace[0]["result"]["internal_reference"],
            "context.analysis",
        )

    def test_converse_schemas_and_prompt_contract(self):
        self.assertEqual(
            {item["toolSpec"]["name"] for item in TOOL_SPECS},
            {"simulate_portfolio_change", "check_profile"},
        )
        for item in TOOL_SPECS:
            schema = item["toolSpec"]["inputSchema"]["json"]
            self.assertFalse(schema["additionalProperties"])
            self.assertEqual(
                set(schema["required"]),
                {"persona_id", "symbol", "target_weight_pct"},
            )
            self.assertNotIn("engine_results", schema["properties"])
        self.assertIn("français", SYSTEM_INSTRUCTIONS)
        self.assertIn("tool_trace", SYSTEM_INSTRUCTIONS)
        self.assertNotIn("tool_trace", MODEL_EXPLANATION_FORMAT["properties"])
        self.assertIn("tool_trace", EXPLANATION_FORMAT["properties"])
        self.assertIn("tool_trace", EXPLANATION_FORMAT["required"])
        change_schema = MODEL_EXPLANATION_FORMAT["properties"]["changes"]["items"]
        self.assertIn("topic", change_schema["required"])
        self.assertIn("metrics", change_schema["required"])
        self.assertEqual(
            change_schema["properties"]["evidence_refs"]["minItems"], 1
        )
        assessment_schema = EXPLANATION_FORMAT["properties"][
            "profile_assessment"
        ]["items"]
        self.assertIn("missing_information", assessment_schema["required"])
        self.assertIn("rendement", SYSTEM_INSTRUCTIONS)
        self.assertIn("garantis", SYSTEM_INSTRUCTIONS)
        self.assertIn("phrases courtes", SYSTEM_INSTRUCTIONS)
        self.assertIn("deux ou trois phrases", SYSTEM_INSTRUCTIONS)
        self.assertIn("n'affiche jamais de clé informatique", SYSTEM_INSTRUCTIONS)
        self.assertIn("ni emoji", SYSTEM_INSTRUCTIONS)
        self.assertIn("améliore automatiquement", SYSTEM_INSTRUCTIONS)


if __name__ == "__main__":
    unittest.main()
