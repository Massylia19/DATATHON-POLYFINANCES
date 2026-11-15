import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from botocore.exceptions import NoCredentialsError

from agent.service import chat_with_persona
from api.main import app, store


class FakeClient:
    def __init__(self, text="Une réponse utile."):
        self.text = text
        self.calls = []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": self.text}],
                }
            }
        }


class ChatEngineTests(unittest.TestCase):
    def test_context_and_five_complete_exchanges_are_sent_in_role_order(self):
        client = FakeClient()
        history = []
        for index in range(7):
            history.extend(
                [
                    {"role": "user", "content": f"Question {index}"},
                    {"role": "assistant", "content": f"Réponse {index}"},
                ]
            )
        answer = chat_with_persona(
            "Et maintenant ?",
            {"id": "amira"},
            {"persona_id": "amira"},
            history=history,
            client=client,
            model_id="test-model",
        )
        self.assertEqual(answer, "Une réponse utile.")
        messages = client.calls[0]["messages"]
        self.assertEqual(len(messages), 11)
        self.assertEqual(
            [message["role"] for message in messages],
            ["user", "assistant"] * 5 + ["user"],
        )
        self.assertIn("contexte AlphaForge", messages[0]["content"][0]["text"])
        self.assertIn("Question 2", messages[0]["content"][0]["text"])

    def test_incomplete_history_is_not_sent_and_empty_response_fails(self):
        client = FakeClient("   ")
        with self.assertRaisesRegex(RuntimeError, "réponse vide"):
            chat_with_persona(
                "Pourquoi ?",
                {"id": "amira"},
                {"persona_id": "amira"},
                history=[{"role": "assistant", "content": "orphelin"}],
                client=client,
                model_id="test-model",
            )
        self.assertEqual(len(client.calls[0]["messages"]), 1)


class ChatApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_blank_question_and_invalid_history_are_rejected(self):
        blank = self.client.post(
            "/api/chat",
            json={"persona_id": "amira", "question": "   ", "history": []},
        )
        self.assertEqual(blank.status_code, 422)
        invalid = self.client.post(
            "/api/chat",
            json={
                "persona_id": "amira",
                "question": "Bonjour",
                "history": [{"role": "system", "content": "non"}],
            },
        )
        self.assertEqual(invalid.status_code, 422)

    def test_expired_analysis_and_wrong_persona_are_rejected(self):
        expired = self.client.post(
            "/api/chat",
            json={
                "persona_id": "amira",
                "question": "Bonjour",
                "analysis_id": "unknown-analysis-id",
                "history": [],
            },
        )
        self.assertEqual(expired.status_code, 404)
        analysis_id = store.put({}, {"persona_id": "amira"})
        mismatch = self.client.post(
            "/api/chat",
            json={
                "persona_id": "mateo",
                "question": "Bonjour",
                "analysis_id": analysis_id,
                "history": [],
            },
        )
        self.assertEqual(mismatch.status_code, 409)

    def test_service_failure_is_sanitized(self):
        with patch("api.main.chat", side_effect=RuntimeError("secret technique")):
            response = self.client.post(
                "/api/chat",
                json={"persona_id": "amira", "question": "Bonjour", "history": []},
            )
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("secret technique", response.text)

    def test_missing_aws_credentials_are_actionable(self):
        with patch("api.main.chat", side_effect=NoCredentialsError()):
            response = self.client.post(
                "/api/chat",
                json={"persona_id": "amira", "question": "Bonjour", "history": []},
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["code"], "CHAT_AWS_UNAVAILABLE")
        self.assertIn("Identifiants AWS", response.json()["detail"]["message"])


if __name__ == "__main__":
    unittest.main()
