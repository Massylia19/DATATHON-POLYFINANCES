import json
import os
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from botocore.exceptions import EndpointConnectionError

from agent.service import analyze_request


ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = "test.inference-profile"
REQUEST = {"persona_id": "amira", "symbol": "NVDA", "target_weight_pct": 10}


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
            {"message": "Le rendement historique change.", "evidence_refs": [reference]}
        ],
        "profile_assessment": [
            {
                "check_id": check_id,
                "status": "insufficient_information",
                "message": "Des informations complémentaires sont nécessaires.",
                "evidence_refs": [],
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

    def test_model_cannot_fabricate_tool_trace(self):
        invalid = valid_amira_explanation()
        invalid["tool_trace"] = [{"tool": "invented"}]
        client = FakeConverseClient(
            sequential_success_responses(final=invalid) + [text_response(invalid)]
        )

        result = self.analyze(client)

        self.assertEqual(result["status"], "partial")
        correction = client.calls[3]["messages"][-1]["content"][0]["text"]
        self.assertIn("ne doit pas produire tool_trace", correction)
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
        self.assertIn("Référence de preuve introuvable", correction)

    def test_wrong_check_id_or_status_is_rejected(self):
        invalid = valid_amira_explanation()
        invalid["profile_assessment"][0]["status"] = "consistent"
        client = FakeConverseClient(
            sequential_success_responses(final=invalid) + [text_response(invalid)]
        )
        result = self.analyze(client)
        self.assertEqual(result["status"], "partial")
        self.assertIn(
            "check_id ou statuts", client.calls[3]["messages"][-1]["content"][0]["text"]
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
        for call in client.calls:
            self.assertNotIn("temperature", call.get("inferenceConfig", {}))
            self.assertEqual(call["modelId"], MODEL_ID)
            self.assertEqual(call["inferenceConfig"]["maxTokens"], 2048)


if __name__ == "__main__":
    unittest.main()
