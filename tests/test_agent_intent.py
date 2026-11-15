import json
import os
import unittest
from unittest.mock import patch

from botocore.exceptions import NoCredentialsError

from agent.service import DEFAULT_MODEL_ID, interpret_scenario_request
from alphaforge.engine import PROJECT_ROOT


class FakeClient:
    def __init__(self, value):
        self.value = value
        self.calls = []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "stopReason": "end_turn",
            "output": {
                "message": {
                    "content": [{"text": json.dumps(self.value)}],
                }
            },
        }


class ScenarioIntentTests(unittest.TestCase):
    def test_explicit_request_is_interpreted_and_validated(self):
        client = FakeClient(
            {
                "persona_id": "amira",
                "symbol": "NVDA",
                "target_weight_pct": 15,
            }
        )
        result = interpret_scenario_request(
            "Pour Amira, je veux tester 15 % de NVIDIA.",
            client=client,
            model_id="test-model",
            root=PROJECT_ROOT,
        )

        self.assertEqual(result["status"], "ready")
        self.assertEqual(
            result["request"],
            {
                "persona_id": "amira",
                "symbol": "NVDA",
                "target_weight_pct": 15.0,
            },
        )
        self.assertEqual(len(client.calls), 1)

    def test_explicit_requests_for_each_persona(self):
        requests = (
            (
                "Pour Mateo, tester 12,5 % de XOM",
                "mateo",
                "XOM",
                12.5,
            ),
            ("Pour Robert, tester 5 % de Tesla", "robert", "TSLA", 5),
        )
        for text, persona_id, symbol, weight in requests:
            with self.subTest(persona=persona_id):
                client = FakeClient(
                    {
                        "persona_id": persona_id,
                        "symbol": symbol,
                        "target_weight_pct": weight,
                    }
                )
                result = interpret_scenario_request(
                    text,
                    client=client,
                    model_id="test-model",
                    root=PROJECT_ROOT,
                )
                self.assertEqual(result["status"], "ready")
                self.assertEqual(result["request"]["persona_id"], persona_id)
                self.assertEqual(result["request"]["symbol"], symbol)
                self.assertEqual(result["request"]["target_weight_pct"], weight)

    def test_follow_up_can_reuse_current_person_and_asset_but_not_guess_weight(self):
        client = FakeClient(
            {
                "persona_id": "amira",
                "symbol": "NVDA",
                "target_weight_pct": 5,
            }
        )
        result = interpret_scenario_request(
            "Et avec 5 % ?",
            client=client,
            model_id="test-model",
            root=PROJECT_ROOT,
            current_request={
                "persona_id": "amira",
                "symbol": "NVDA",
                "target_weight_pct": 10,
            },
        )

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["request"]["target_weight_pct"], 5.0)

    def test_missing_or_multiple_percentages_request_clarification_without_model(self):
        client = FakeClient({})
        for text in (
            "Pour Amira, tester NVIDIA",
            "Pour Amira, tester 5 % ou 10 % de NVIDIA",
        ):
            with self.subTest(text=text):
                result = interpret_scenario_request(
                    text,
                    client=client,
                    model_id="test-model",
                    root=PROJECT_ROOT,
                )
                self.assertEqual(result["status"], "clarification")
        self.assertEqual(client.calls, [])

    def test_invalid_weight_unknown_asset_and_ambiguous_profile_are_not_sent(self):
        client = FakeClient({})
        invalid_weight = interpret_scenario_request(
            "Pour Amira, tester 100 % de NVIDIA",
            client=client,
            model_id="test-model",
            root=PROJECT_ROOT,
        )
        unknown_asset = interpret_scenario_request(
            "Pour Amira, tester 10 % de UNKNOWNCOIN",
            client=client,
            model_id="test-model",
            root=PROJECT_ROOT,
        )
        ambiguous_profile = interpret_scenario_request(
            "Pour Amira et Mateo, tester 10 % de NVIDIA",
            client=client,
            model_id="test-model",
            root=PROJECT_ROOT,
        )

        self.assertEqual(invalid_weight["error"]["code"], "INVALID_WEIGHT")
        self.assertEqual(unknown_asset["status"], "clarification")
        self.assertEqual(ambiguous_profile["status"], "clarification")
        self.assertEqual(client.calls, [])

    def test_model_cannot_change_explicit_parameters_or_add_an_existing_asset(self):
        wrong_weight = FakeClient(
            {
                "persona_id": "amira",
                "symbol": "NVDA",
                "target_weight_pct": 20,
            }
        )
        result = interpret_scenario_request(
            "Pour Amira, tester 15 % de NVIDIA",
            client=wrong_weight,
            model_id="test-model",
            root=PROJECT_ROOT,
        )
        self.assertEqual(result["status"], "clarification")

        held_asset = FakeClient(
            {
                "persona_id": "amira",
                "symbol": "SPY",
                "target_weight_pct": 15,
            }
        )
        result = interpret_scenario_request(
            "Pour Amira, tester 15 % de SPY",
            client=held_asset,
            model_id="test-model",
            root=PROJECT_ROOT,
        )
        self.assertEqual(result["status"], "clarification")

    def test_missing_model_configuration_is_explicit(self):
        client = FakeClient({})
        with patch.dict(os.environ, {"BEDROCK_MODEL_ID": ""}):
            result = interpret_scenario_request(
                "Pour Amira, tester 15 % de NVIDIA",
                client=client,
                root=PROJECT_ROOT,
            )
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(client.calls, [])

    def test_default_model_is_used_when_no_override_is_configured(self):
        client = FakeClient(
            {
                "persona_id": "amira",
                "symbol": "NVDA",
                "target_weight_pct": 15,
            }
        )
        with patch.dict(os.environ, {}, clear=True):
            result = interpret_scenario_request(
                "Pour Amira, tester 15 % de NVIDIA",
                client=client,
                root=PROJECT_ROOT,
            )

        self.assertEqual(result["status"], "ready")
        self.assertEqual(client.calls[0]["modelId"], DEFAULT_MODEL_ID)

    def test_missing_aws_credentials_are_reported_actionably(self):
        class MissingCredentialsClient:
            def converse(self, **kwargs):
                raise NoCredentialsError()

        with patch.dict(os.environ, {}, clear=True):
            result = interpret_scenario_request(
                "Pour Amira, tester 15 % de NVIDIA",
                client=MissingCredentialsClient(),
                root=PROJECT_ROOT,
            )

        self.assertEqual(result["status"], "unavailable")
        self.assertIn("Identifiants AWS absents ou incomplets", result["message"])


if __name__ == "__main__":
    unittest.main()
