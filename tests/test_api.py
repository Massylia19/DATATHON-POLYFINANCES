import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.analysis_store import AnalysisStore
from api.main import app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_does_not_claim_bedrock_connection(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["bedrock"], "not_checked")

    def test_bootstrap_contains_real_profiles_and_no_market_series(self):
        response = self.client.get("/api/bootstrap")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual([item["id"] for item in body["personas"]], ["amira", "mateo", "robert"])
        self.assertIn("NVDA", [item["ticker"] for item in body["assets"]])
        self.assertNotIn("prices", body)

    def test_invalid_boolean_and_extra_fields_are_rejected(self):
        response = self.client.post("/api/analyses", json={"persona_id": "amira", "symbol": "NVDA", "target_weight_pct": True})
        self.assertEqual(response.status_code, 422)
        response = self.client.post("/api/analyses", json={"persona_id": "amira", "symbol": "NVDA", "target_weight_pct": 10, "secret": "no"})
        self.assertEqual(response.status_code, 422)

    def test_real_local_analysis_is_available_without_bedrock(self):
        with patch.dict("os.environ", {"BEDROCK_MODEL_ID": ""}):
            response = self.client.post("/api/analyses", json={"persona_id": "amira", "symbol": "NVDA", "target_weight_pct": 10})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "partial")
        self.assertEqual(body["analysis"]["currency"], "CAD")
        self.assertTrue(body["analysis_id"])

    def test_expired_analysis_id_is_actionable(self):
        response = self.client.post("/api/follow-ups", json={"analysis_id": "unknown-analysis-id", "question": "Pourquoi ?"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"]["code"], "ANALYSIS_EXPIRED")

    def test_public_evidence_is_resolved_and_internal_paths_are_not_returned(self):
        with patch.dict("os.environ", {"BEDROCK_MODEL_ID": ""}):
            analysis_response = self.client.post(
                "/api/analyses",
                json={
                    "persona_id": "amira",
                    "symbol": "NVDA",
                    "target_weight_pct": 10,
                },
            )
        self.assertEqual(analysis_response.status_code, 200)
        analysis_id = analysis_response.json()["analysis_id"]
        response = self.client.post(
            "/api/evidence",
            json={
                "analysis_id": analysis_id,
                "references": [
                    "analysis.after.metrics.total_return",
                    "source.src_prices_daily",
                ],
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["analysis_id"], analysis_id)
        self.assertEqual(len(body["evidence"]), 2)
        self.assertIn("118", body["evidence"][0]["value"])
        self.assertIn("Yahoo Finance", body["evidence"][1]["source"])
        self.assertNotIn("analysis.after", str(body))

    def test_unknown_evidence_reference_is_rejected(self):
        with patch.dict("os.environ", {"BEDROCK_MODEL_ID": ""}):
            analysis_response = self.client.post(
                "/api/analyses",
                json={
                    "persona_id": "amira",
                    "symbol": "NVDA",
                    "target_weight_pct": 10,
                },
            )
        response = self.client.post(
            "/api/evidence",
            json={
                "analysis_id": analysis_response.json()["analysis_id"],
                "references": ["analysis.internal.secret"],
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_interpret_validation_accepts_frontend_context_and_blank_clarifies(self):
        with patch("api.main.interpret") as service:
            service.return_value = {
                "status": "clarification",
                "message": "Précisez votre demande.",
            }
            response = self.client.post(
                "/api/interpret",
                json={
                    "text": "Pour Amira, tester 15 % de NVIDIA.",
                    "current_request": {
                        "persona_id": "amira",
                        "symbol": "NVDA",
                        "target_weight_pct": 10,
                    },
                },
            )
            self.assertEqual(response.status_code, 200)
            response = self.client.post("/api/interpret", json={"text": ""})
            self.assertEqual(response.status_code, 200)

    def test_store_is_bounded_and_expires(self):
        store = AnalysisStore(max_entries=1, ttl_seconds=0)
        identifier = store.put({"status": "partial"}, {"persona_id": "amira"})
        self.assertIsNone(store.get(identifier))


if __name__ == "__main__":
    unittest.main()
