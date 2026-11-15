import json
import os
import unittest
from copy import deepcopy
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from botocore.exceptions import EndpointConnectionError

from agent.service import analyze_request
from agent.demo import _print_result
from agent.context import create_request_context
from agent.evidence import build_evidence_bundle
from agent.tools import dispatch_tool
from alphaforge.engine import run_analysis


ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = "test.inference-profile"
REQUEST = {"persona_id": "amira", "symbol": "NVDA", "target_weight_pct": 10}
MATEO_REQUEST = {"persona_id": "mateo", "symbol": "XOM", "target_weight_pct": 10}
ROBERT_REQUEST = {"persona_id": "robert", "symbol": "TSLA", "target_weight_pct": 5}


class FakeConverseClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def converse(self, **kwargs):
        self.calls.append(deepcopy(kwargs))
        if not self.responses:
            raise AssertionError("Aucune réponse Converse simulée restante")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def tool_response(*uses):
    return {
        "stopReason": "tool_use",
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "toolUse": {
                            "toolUseId": tool_use_id,
                            "name": name,
                            "input": payload,
                        }
                    }
                    for tool_use_id, name, payload in uses
                ],
            }
        },
    }


def text_response(value, *, stop_reason="end_turn"):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return {
        "stopReason": stop_reason,
        "output": {
            "message": {"role": "assistant", "content": [{"text": text}]}
        },
    }


def valid_amira_explanation(*, reference="analysis.after.metrics.total_return"):
    return {
        "summary": "Comparaison historique du portefeuille d'Amira.",
        "changes": [
            {
                "topic": "performance",
                "message": "Le rendement historique change.",
                "evidence_refs": [reference],
                "metrics": [],
            }
        ],
        "profile_assessment": [
            {
                "check_id": check_id,
                "status": "insufficient_information",
                "message": "Des informations complémentaires sont nécessaires.",
                "evidence_refs": [],
                "metrics": [],
            }
            for check_id in ("concentration", "diversification", "etf_overlap")
        ],
        "uncertainties": ["Les compositions datées des FNB sont absentes."],
        "evidence_refs": [reference],
    }


def sequential_success_responses(final=None):
    return [
        tool_response(("sim-1", "simulate_portfolio_change", REQUEST)),
        tool_response(("check-1", "check_profile", REQUEST)),
        text_response(final or valid_amira_explanation()),
    ]


def valid_explanation_for(persona_id, symbol, target_weight_pct):
    context = create_request_context(
        persona_id, symbol, target_weight_pct, root=ROOT
    )
    arguments = context.request.as_dict()
    dispatch_tool(context, "simulate_portfolio_change", arguments)
    dispatch_tool(context, "check_profile", arguments)
    return deepcopy(build_evidence_bundle(context)["example_explanation"])


class AgentServiceTests(unittest.TestCase):
    def analyze(self, client, **kwargs):
        return analyze_request(
            "amira",
            "NVDA",
            10,
            client=client,
            root=ROOT,
            model_id=MODEL_ID,
            **kwargs,
        )

    def analyze_mateo(self, client, **kwargs):
        return analyze_request(
            "mateo",
            "XOM",
            10,
            client=client,
            root=ROOT,
            model_id=MODEL_ID,
            **kwargs,
        )

    def analyze_robert(self, client, **kwargs):
        return analyze_request(
            "robert",
            "TSLA",
            5,
            client=client,
            root=ROOT,
            model_id=MODEL_ID,
            **kwargs,
        )

    def test_currency_reference_rejected_for_period_then_methodology_globally(self):
        for persona_id, request, analyze in (
            ("amira", REQUEST, self.analyze),
            ("robert", ROBERT_REQUEST, self.analyze_robert),
        ):
            with self.subTest(persona_id=persona_id):
                symbol = request["symbol"]
                weight = request["target_weight_pct"]
                valid = valid_explanation_for(persona_id, symbol, weight)
                invalid_period = deepcopy(valid)
                invalid_period["changes"][0] = {
                    "topic": "period",
                    "message": "La comparaison est exprimée en CAD.",
                    "evidence_refs": ["analysis.currency"],
                    "metrics": [],
                }
                invalid_methodology = deepcopy(valid)
                invalid_methodology["changes"][0] = {
                    "topic": "methodology",
                    "message": "La comparaison est exprimée en CAD.",
                    "evidence_refs": ["analysis.currency"],
                    "metrics": [],
                }
                client = FakeConverseClient(
                    [
                        tool_response(("sim", "simulate_portfolio_change", request)),
                        tool_response(("check", "check_profile", request)),
                        text_response(invalid_period),
                        text_response(invalid_methodology),
                    ]
                )

                result = analyze(client)

                self.assertEqual(result["status"], "partial")
                self.assertIsNone(result["explanation"])
                warning = " ".join(result["warnings"])
                self.assertIn("topic reçu 'period'", warning)
                self.assertIn("topic reçu 'methodology'", warning)
                self.assertIn("analysis.currency", warning)
                self.assertIn("classée 'currency'", warning)
                first_repair = client.calls[3]["messages"][-1]["content"][0]["text"]
                self.assertIn("Références compatibles disponibles", first_repair)
                self.assertIn("analysis.period.start", first_repair)
                self.assertIn("sans changer arbitrairement le topic", first_repair)

    def test_valid_examples_for_all_profiles_and_currency_is_metadata(self):
        cases = (
            ("amira", REQUEST, self.analyze),
            ("mateo", MATEO_REQUEST, self.analyze_mateo),
            ("robert", ROBERT_REQUEST, self.analyze_robert),
        )
        for persona_id, request, analyze in cases:
            with self.subTest(persona_id=persona_id):
                valid = valid_explanation_for(
                    persona_id, request["symbol"], request["target_weight_pct"]
                )
                self.assertNotIn("CAD", valid["summary"])
                self.assertGreaterEqual(valid["summary"].count("."), 2)
                self.assertNotIn(
                    "analysis.currency",
                    [
                        reference
                        for change in valid["changes"]
                        for reference in change["evidence_refs"]
                    ],
                )
                client = FakeConverseClient(
                    [
                        tool_response(("sim", "simulate_portfolio_change", request)),
                        tool_response(("check", "check_profile", request)),
                        text_response(valid),
                    ]
                )

                result = analyze(client)

                self.assertEqual(result["status"], "success")
                if persona_id == "robert":
                    self.assertIn("tension", {c["status"] for c in result["checks"]})

    def test_mateo_internal_reference_gets_actionable_public_path_repair(self):
        corrected = valid_explanation_for("mateo", "XOM", 10)
        invalid = deepcopy(corrected)
        invalid["changes"][0]["evidence_refs"][1] = (
            "context.analysis.after.metrics.total_return"
        )
        client = FakeConverseClient(
            [
                tool_response(
                    ("sim-mateo", "simulate_portfolio_change", MATEO_REQUEST)
                ),
                tool_response(("check-mateo", "check_profile", MATEO_REQUEST)),
                text_response(invalid),
                text_response(corrected),
            ]
        )

        result = self.analyze_mateo(client)

        self.assertEqual(result["status"], "success")
        repair = client.calls[3]["messages"][-1]["content"][0]["text"]
        self.assertIn(
            "utiliser le chemin public attendu "
            "analysis.after.metrics.total_return",
            repair,
        )
        self.assertIn(
            "chemin interne interdit "
            "context.analysis.after.metrics.total_return",
            repair,
        )

    def test_mateo_missing_metric_membership_gets_actionable_repair(self):
        corrected = valid_explanation_for("mateo", "XOM", 10)
        invalid = deepcopy(corrected)
        missing_reference = "analysis.before.metrics.total_return"
        invalid["changes"][0]["evidence_refs"].remove(missing_reference)
        client = FakeConverseClient(
            [
                tool_response(
                    ("sim-mateo", "simulate_portfolio_change", MATEO_REQUEST)
                ),
                tool_response(("check-mateo", "check_profile", MATEO_REQUEST)),
                text_response(invalid),
                text_response(corrected),
            ]
        )

        result = self.analyze_mateo(client)

        self.assertEqual(result["status"], "success")
        repair = client.calls[3]["messages"][-1]["content"][0]["text"]
        self.assertIn(
            f"ajouter la référence publique {missing_reference} à "
            "changes[0].evidence_refs",
            repair,
        )

    def test_model_payload_has_public_catalog_and_valid_before_after_example(self):
        corrected = valid_explanation_for("mateo", "XOM", 10)
        client = FakeConverseClient(
            [
                tool_response(
                    ("sim-mateo", "simulate_portfolio_change", MATEO_REQUEST)
                ),
                tool_response(("check-mateo", "check_profile", MATEO_REQUEST)),
                text_response(corrected),
            ]
        )

        result = self.analyze_mateo(client)

        self.assertEqual(result["status"], "success")
        tool_payload = client.calls[2]["messages"][-1]["content"][0][
            "toolResult"
        ]["content"][0]["json"]["result"]
        catalog = {
            entry["reference"]: entry
            for entry in tool_payload["public_evidence_catalog"]
        }
        before_ref = "analysis.before.metrics.total_return"
        after_ref = "analysis.after.metrics.total_return"
        self.assertEqual(catalog[before_ref]["unit"], "decimal_ratio")
        self.assertEqual(catalog[after_ref]["unit"], "decimal_ratio")
        self.assertEqual(catalog[before_ref]["category"], "performance")
        self.assertEqual(catalog["analysis.currency"]["category"], "currency")
        self.assertEqual(catalog["analysis.period.start"]["category"], "period")
        self.assertEqual(
            catalog["analysis.methodology"]["category"], "methodology"
        )
        example_change = tool_payload["example_explanation"]["changes"][0]
        self.assertEqual(example_change["evidence_refs"], [before_ref, after_ref])
        self.assertEqual(
            [metric["evidence_ref"] for metric in example_change["metrics"]],
            [before_ref, after_ref],
        )
        self.assertNotIn("context.analysis", json.dumps(tool_payload))

    def test_mateo_truly_unknown_public_reference_is_still_rejected(self):
        invalid = valid_explanation_for("mateo", "XOM", 10)
        invalid["changes"][0]["evidence_refs"][0] = (
            "analysis.before.metrics.unknown_metric"
        )
        client = FakeConverseClient(
            [
                tool_response(
                    ("sim-mateo", "simulate_portfolio_change", MATEO_REQUEST)
                ),
                tool_response(("check-mateo", "check_profile", MATEO_REQUEST)),
                text_response(invalid),
                text_response(invalid),
            ]
        )

        result = self.analyze_mateo(client)

        self.assertEqual(result["status"], "partial")
        self.assertIsNone(result["explanation"])
        self.assertIn(
            "introuvable dans le catalogue public", result["warnings"][0]
        )

    def test_complete_simulation_checks_and_explanation(self):
        client = FakeConverseClient(sequential_success_responses())
        result = self.analyze(client)

        self.assertEqual(result["status"], "success")
        self.assertIsNotNone(result["analysis"])
        self.assertEqual(len(result["checks"]), 3)
        self.assertEqual(len(result["explanation"]["tool_trace"]), 2)
        self.assertEqual(
            result["explanation"]["evidence_refs"],
            ["analysis.after.metrics.total_return"],
        )
        self.assertEqual(
            {entry["execution_origin"] for entry in result["tool_trace"]},
            {"bedrock_tool_request"},
        )
        expected_missing = {
            check["id"]: check["missing_information"] for check in result["checks"]
        }
        self.assertEqual(
            {
                assessment["check_id"]: assessment["missing_information"]
                for assessment in result["explanation"]["profile_assessment"]
            },
            expected_missing,
        )

    def test_empty_summary_is_rejected(self):
        invalid = valid_amira_explanation()
        invalid["summary"] = "   "
        client = FakeConverseClient(
            sequential_success_responses(final=invalid) + [text_response(invalid)]
        )

        result = self.analyze(client)

        self.assertEqual(result["status"], "partial")
        self.assertIsNone(result["explanation"])

    def test_numeric_change_without_evidence_is_rejected(self):
        invalid = valid_amira_explanation()
        invalid["changes"] = [
            {
                "topic": "performance",
                "message": "Le rendement augmente de 12 %.",
                "evidence_refs": [],
                "metrics": [],
            }
        ]
        client = FakeConverseClient(
            sequential_success_responses(final=invalid) + [text_response(invalid)]
        )

        result = self.analyze(client)

        self.assertEqual(result["status"], "partial")
        self.assertIsNone(result["explanation"])

    def test_guaranteed_return_promise_is_rejected(self):
        invalid = valid_amira_explanation()
        invalid["summary"] = "Ce placement garantit un rendement futur positif."
        client = FakeConverseClient(
            sequential_success_responses(final=invalid) + [text_response(invalid)]
        )

        result = self.analyze(client)

        self.assertEqual(result["status"], "partial")
        self.assertIsNone(result["explanation"])

    def test_empty_change_and_assessment_messages_are_rejected(self):
        for field in ("changes", "profile_assessment"):
            with self.subTest(field=field):
                invalid = valid_amira_explanation()
                invalid[field][0]["message"] = "  "
                client = FakeConverseClient(
                    sequential_success_responses(final=invalid)
                    + [text_response(invalid)]
                )

                result = self.analyze(client)

                self.assertEqual(result["status"], "partial")
                self.assertIsNone(result["explanation"])

    def test_evidence_must_match_change_topic(self):
        invalid = valid_amira_explanation(
            reference="analysis.after.metrics.annualized_volatility"
        )
        client = FakeConverseClient(
            sequential_success_responses(final=invalid) + [text_response(invalid)]
        )

        result = self.analyze(client)

        self.assertEqual(result["status"], "partial")
        correction = client.calls[3]["messages"][-1]["content"][0]["text"]
        self.assertIn("topic reçu 'performance'", correction)
        self.assertIn("classée 'risk'", correction)
        self.assertIn("analysis.after.metrics.total_return", correction)

    def test_structured_metric_value_must_match_engine(self):
        invalid = valid_amira_explanation()
        invalid["changes"][0]["message"] = "Le rendement historique vaut 999 %."
        invalid["changes"][0]["metrics"] = [
            {
                "evidence_ref": "analysis.after.metrics.total_return",
                "value": 999,
                "unit": "decimal_ratio",
            }
        ]
        client = FakeConverseClient(
            sequential_success_responses(final=invalid) + [text_response(invalid)]
        )

        result = self.analyze(client)

        self.assertEqual(result["status"], "partial")
        correction = client.calls[3]["messages"][-1]["content"][0]["text"]
        self.assertIn("ne correspond pas à la valeur structurée du moteur", correction)

    def test_correctly_sourced_structured_metric_is_accepted(self):
        expected = run_analysis("amira", "NVDA", 10, root=ROOT)
        value = expected["after"]["metrics"]["total_return"]
        valid = valid_amira_explanation()
        valid["changes"][0]["message"] = "Le rendement total historique est chiffré."
        valid["changes"][0]["metrics"] = [
            {
                "evidence_ref": "analysis.after.metrics.total_return",
                "value": value,
                "unit": "decimal_ratio",
            }
        ]
        client = FakeConverseClient(sequential_success_responses(final=valid))

        result = self.analyze(client)

        self.assertEqual(result["status"], "success")
        self.assertEqual(
            result["explanation"]["changes"][0]["metrics"][0]["value"], value
        )

    def test_invalid_explanation_can_be_repaired_once(self):
        invalid = valid_amira_explanation()
        invalid["summary"] = ""
        client = FakeConverseClient(
            sequential_success_responses(final=invalid)
            + [text_response(valid_amira_explanation())]
        )

        result = self.analyze(client)

        self.assertEqual(result["status"], "success")
        self.assertEqual(len(client.calls), 4)
        self.assertIn(
            "champ: summary; règle: doit être un texte non vide",
            client.calls[3]["messages"][-1]["content"][0]["text"],
        )

    def test_multiple_tool_uses_are_ordered_and_ids_match_results(self):
        client = FakeConverseClient(
            [
                tool_response(
                    ("check-first", "check_profile", REQUEST),
                    ("simulate-second", "simulate_portfolio_change", REQUEST),
                ),
                text_response(valid_amira_explanation()),
            ]
        )
        result = self.analyze(client)

        self.assertEqual(result["status"], "success")
        result_blocks = client.calls[1]["messages"][-1]["content"]
        result_ids = [block["toolResult"]["toolUseId"] for block in result_blocks]
        self.assertEqual(result_ids, ["simulate-second", "check-first"])
        self.assertTrue(
            all(block["toolResult"]["status"] == "success" for block in result_blocks)
        )

    def test_tool_error_can_be_corrected_by_model(self):
        client = FakeConverseClient(
            [
                tool_response(("early-check", "check_profile", REQUEST)),
                tool_response(("sim", "simulate_portfolio_change", REQUEST)),
                tool_response(("check", "check_profile", REQUEST)),
                text_response(valid_amira_explanation()),
            ]
        )
        result = self.analyze(client)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["tool_trace"][0]["error"]["code"], "SIMULATION_REQUIRED")
        first_tool_result = client.calls[1]["messages"][-1]["content"][0]["toolResult"]
        self.assertEqual(first_tool_result["toolUseId"], "early-check")
        self.assertEqual(first_tool_result["status"], "error")

    def test_premature_answer_is_corrected(self):
        client = FakeConverseClient(
            [
                text_response(valid_amira_explanation()),
                tool_response(
                    ("sim", "simulate_portfolio_change", REQUEST),
                    ("check", "check_profile", REQUEST),
                ),
                text_response(valid_amira_explanation()),
            ]
        )
        result = self.analyze(client)
        self.assertEqual(result["status"], "success")
        correction = client.calls[1]["messages"][-1]["content"][0]["text"]
        self.assertIn("simulation et les contrôles", correction)

    def test_converse_and_tool_limits_return_partial_local_results(self):
        turns = FakeConverseClient(
            [text_response("pas encore") for _ in range(2)]
        )
        turn_result = self.analyze(turns, max_converse_calls=2)
        self.assertEqual(turn_result["status"], "partial")
        self.assertIsNotNone(turn_result["analysis"])
        self.assertTrue(turn_result["checks"])
        self.assertIn("limite d'appels Converse", " ".join(turn_result["warnings"]))

        tools = FakeConverseClient(
            [
                tool_response(
                    ("one", "simulate_portfolio_change", REQUEST),
                    ("two", "check_profile", REQUEST),
                    ("three", "check_profile", REQUEST),
                )
            ]
        )
        tool_result = self.analyze(tools, max_tool_executions=2)
        self.assertEqual(tool_result["status"], "partial")
        self.assertIn("limite d'exécutions", " ".join(tool_result["warnings"]))

    def test_invalid_json_after_one_repair_is_partial(self):
        client = FakeConverseClient(
            sequential_success_responses(final="pas du json")
            + [text_response("toujours invalide")]
        )
        result = self.analyze(client)
        self.assertEqual(result["status"], "partial")
        self.assertIsNone(result["explanation"])
        self.assertIsNotNone(result["analysis"])
        self.assertTrue(result["checks"])

    def test_partial_preserves_both_validation_reasons(self):
        first_invalid = valid_amira_explanation()
        first_invalid["summary"] = ""
        second_invalid = valid_amira_explanation(
            reference="analysis.after.metrics.annualized_volatility"
        )
        client = FakeConverseClient(
            sequential_success_responses(final=first_invalid)
            + [text_response(second_invalid)]
        )

        result = self.analyze(client)

        self.assertEqual(result["status"], "partial")
        self.assertIsNone(result["explanation"])
        self.assertIn("premier rejet", result["warnings"][0])
        self.assertIn("champ: summary", result["warnings"][0])
        self.assertIn("doit être un texte non vide", result["warnings"][0])
        self.assertIn("références: aucune", result["warnings"][0])
        self.assertIn("rejet après réparation", result["warnings"][1])
        self.assertIn("champ: changes[0].evidence_refs", result["warnings"][1])
        self.assertIn("topic reçu 'performance'", result["warnings"][1])
        self.assertIn("classée 'risk'", result["warnings"][1])
        self.assertIn(
            "analysis.after.metrics.annualized_volatility", result["warnings"][1]
        )
        output = StringIO()
        with redirect_stdout(output):
            _print_result(result)
        self.assertIn("Avertissements et diagnostics", output.getvalue())
        self.assertIn(result["warnings"][0], output.getvalue())
        self.assertIn(result["warnings"][1], output.getvalue())

    def test_model_cannot_fabricate_tool_trace(self):
        invalid = valid_amira_explanation()
        invalid["tool_trace"] = [{"tool": "invented"}]
        client = FakeConverseClient(
            sequential_success_responses(final=invalid) + [text_response(invalid)]
        )

        result = self.analyze(client)

        self.assertEqual(result["status"], "partial")
        correction = client.calls[3]["messages"][-1]["content"][0]["text"]
        self.assertIn("champ: tool_trace", correction)
        self.assertIn("uniquement par l'application", correction)
        self.assertEqual(
            [entry["tool"] for entry in result["tool_trace"]],
            ["simulate_portfolio_change", "check_profile"],
        )

    def test_missing_evidence_reference_is_rejected(self):
        invalid = valid_amira_explanation(reference="analysis.missing.value")
        client = FakeConverseClient(
            sequential_success_responses(final=invalid) + [text_response(invalid)]
        )
        result = self.analyze(client)
        self.assertEqual(result["status"], "partial")
        correction = client.calls[3]["messages"][-1]["content"][0]["text"]
        self.assertIn("la référence de preuve est introuvable", correction)

    def test_wrong_check_id_or_status_is_rejected(self):
        invalid = valid_amira_explanation()
        invalid["profile_assessment"][0]["status"] = "consistent"
        client = FakeConverseClient(
            sequential_success_responses(final=invalid) + [text_response(invalid)]
        )
        result = self.analyze(client)
        self.assertEqual(result["status"], "partial")
        self.assertIn(
            "check_id et statuts", client.calls[3]["messages"][-1]["content"][0]["text"]
        )

    def test_aws_failure_before_tools_uses_local_fallback(self):
        client = FakeConverseClient(
            [EndpointConnectionError(endpoint_url="https://example.invalid")]
        )
        result = self.analyze(client)

        self.assertEqual(result["status"], "partial")
        self.assertIsNotNone(result["analysis"])
        self.assertTrue(result["checks"])
        self.assertIsNone(result["explanation"])
        self.assertEqual(
            {entry["execution_origin"] for entry in result["tool_trace"]},
            {"local_fallback"},
        )

    def test_aws_failure_after_simulation_preserves_analysis(self):
        client = FakeConverseClient(
            [
                tool_response(("sim", "simulate_portfolio_change", REQUEST)),
                EndpointConnectionError(endpoint_url="https://example.invalid"),
            ]
        )
        result = self.analyze(client)

        self.assertEqual(result["status"], "partial")
        self.assertIsNotNone(result["analysis"])
        self.assertTrue(result["checks"])
        self.assertEqual(
            [entry["execution_origin"] for entry in result["tool_trace"]],
            ["bedrock_tool_request", "local_fallback"],
        )

    def test_missing_model_configuration_is_explicit_and_does_not_call_client(self):
        client = FakeConverseClient([])
        with patch.dict(os.environ, {}, clear=True):
            result = analyze_request(
                "amira", "NVDA", 10, client=client, root=ROOT
            )

        self.assertEqual(result["status"], "partial")
        self.assertIn("BEDROCK_MODEL_ID", " ".join(result["warnings"]))
        self.assertEqual(client.calls, [])

    def test_input_validation_happens_before_aws(self):
        client = FakeConverseClient([])
        result = analyze_request(
            "unknown", "NVDA", 10, client=client, root=ROOT, model_id=MODEL_ID
        )
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "INVALID_PERSONA")
        self.assertEqual(client.calls, [])

    def test_calls_never_send_temperature(self):
        client = FakeConverseClient(sequential_success_responses())
        self.analyze(client)
        initial_text = client.calls[0]["messages"][0]["content"][0]["text"]
        self.assertIn('"topic"', initial_text)
        self.assertIn('"metrics"', initial_text)
        for call in client.calls:
            self.assertNotIn("temperature", call.get("inferenceConfig", {}))
            self.assertEqual(call["modelId"], MODEL_ID)
            self.assertEqual(call["inferenceConfig"]["maxTokens"], 2048)


if __name__ == "__main__":
    unittest.main()
