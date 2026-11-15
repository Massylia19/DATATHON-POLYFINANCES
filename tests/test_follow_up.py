import json
import os
import unittest
from unittest.mock import patch

from botocore.exceptions import NoCredentialsError

from agent.service import DEFAULT_MODEL_ID, answer_follow_up
from alphaforge.engine import PROJECT_ROOT, run_analysis
from alphaforge.profile_checks import validate_profile


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


def current_result(persona_id="amira", symbol="NVDA", weight=10):
    analysis = run_analysis(persona_id, symbol, weight, root=PROJECT_ROOT)
    with (PROJECT_ROOT / "data" / "personas.json").open(encoding="utf-8") as handle:
        personas = json.load(handle)["personas"]
    persona = next(item for item in personas if item["id"] == persona_id)
    checks = validate_profile(
        persona,
        {"symbol": symbol, "target_weight_pct": weight},
        analysis,
        PROJECT_ROOT / "data",
    )
    return {"analysis": analysis, "checks": checks}


class FollowUpTests(unittest.TestCase):
    def test_answer_uses_current_scenario_and_resolved_evidence(self):
        response = current_result()
        request = {
            "persona_id": "amira",
            "symbol": "NVDA",
            "target_weight_pct": 10.0,
        }
        client = FakeClient(
            {
                "answer": (
                    "Les fluctuations observées reflètent des mouvements "
                    "historiques et ne prédisent pas une perte future."
                ),
                "evidence_refs": ["analysis.after.metrics.annualized_volatility"],
            }
        )
        result = answer_follow_up(
            "Pourquoi le risque change-t-il ?",
            response,
            request,
            client=client,
            model_id="test-model",
            root=PROJECT_ROOT,
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(
            result["evidence_refs"],
            ["analysis.after.metrics.annualized_volatility"],
        )
        self.assertEqual(len(client.calls), 1)

    def test_unsupported_numbers_and_references_are_not_displayable(self):
        response = current_result()
        request = {
            "persona_id": "amira",
            "symbol": "NVDA",
            "target_weight_pct": 10.0,
        }
        for value in (
            {
                "answer": "Le portefeuille progresse de 20 %.",
                "evidence_refs": ["analysis.after.metrics.total_return"],
            },
            {
                "answer": "Les données disponibles ne permettent pas de conclure.",
                "evidence_refs": ["analysis.internal.secret"],
            },
        ):
            with self.subTest(value=value):
                result = answer_follow_up(
                    "Pourquoi le risque change-t-il ?",
                    response,
                    request,
                    client=FakeClient(value),
                    model_id="test-model",
                    root=PROJECT_ROOT,
                )
                self.assertEqual(result["status"], "unavailable")

    def test_insufficient_evidence_is_explained_as_an_unknown(self):
        response = current_result()
        client = FakeClient(
            {
                "answer": (
                    "La composition des fonds n’est pas disponible; la part "
                    "indirecte de NVIDIA ne peut donc pas être établie."
                ),
                "evidence_refs": ["analysis.limitations"],
            }
        )
        result = answer_follow_up(
            "Quelle part de NVIDIA est déjà détenue dans les fonds ?",
            response,
            {
                "persona_id": "amira",
                "symbol": "NVDA",
                "target_weight_pct": 10.0,
            },
            client=client,
            model_id="test-model",
            root=PROJECT_ROOT,
        )
        self.assertEqual(result["status"], "success")
        self.assertIn("ne peut donc pas être établie", result["answer"])

    def test_mismatched_response_is_rejected_without_model_call(self):
        client = FakeClient({})
        result = answer_follow_up(
            "Pourquoi le risque change-t-il ?",
            current_result(),
            {
                "persona_id": "robert",
                "symbol": "TSLA",
                "target_weight_pct": 5.0,
            },
            client=client,
            model_id="test-model",
            root=PROJECT_ROOT,
        )
        self.assertEqual(result["status"], "error")
        self.assertEqual(client.calls, [])

    def test_missing_model_configuration_is_explicit(self):
        client = FakeClient({})
        with patch.dict(os.environ, {"BEDROCK_MODEL_ID": ""}):
            result = answer_follow_up(
                "Pourquoi le risque change-t-il ?",
                current_result(),
                {
                    "persona_id": "amira",
                    "symbol": "NVDA",
                    "target_weight_pct": 10.0,
                },
                client=client,
                root=PROJECT_ROOT,
            )
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(client.calls, [])

    def test_default_model_is_used_when_no_override_is_configured(self):
        response = current_result()
        request = {
            "persona_id": "amira",
            "symbol": "NVDA",
            "target_weight_pct": 10.0,
        }
        client = FakeClient(
            {
                "answer": (
                    "Les fluctuations observées sont historiques et ne prédisent "
                    "pas une perte future."
                ),
                "evidence_refs": ["analysis.after.metrics.annualized_volatility"],
            }
        )
        with patch.dict(os.environ, {}, clear=True):
            result = answer_follow_up(
                "Pourquoi le risque change-t-il ?",
                response,
                request,
                client=client,
                root=PROJECT_ROOT,
            )

        self.assertEqual(result["status"], "success")
        self.assertEqual(client.calls[0]["modelId"], DEFAULT_MODEL_ID)

    def test_missing_aws_credentials_are_reported_actionably(self):
        response = current_result()
        request = {
            "persona_id": "amira",
            "symbol": "NVDA",
            "target_weight_pct": 10.0,
        }

        class MissingCredentialsClient:
            def converse(self, **kwargs):
                raise NoCredentialsError()

        with patch.dict(os.environ, {}, clear=True):
            result = answer_follow_up(
                "Pourquoi le risque change-t-il ?",
                response,
                request,
                client=MissingCredentialsClient(),
                root=PROJECT_ROOT,
            )

        self.assertEqual(result["status"], "unavailable")
        self.assertIn("Identifiants AWS absents ou incomplets", result["message"])


if __name__ == "__main__":
    unittest.main()
