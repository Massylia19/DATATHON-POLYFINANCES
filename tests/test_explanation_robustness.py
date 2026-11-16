"""Tests exhaustifs pour l'explication d'AlphaForge et la robustesse face aux pannes.

Couvre tous les scénarios de panne AWS, validation Bedrock, et comportements extrêmes.
"""

import json
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock

from agent.service import (
    analyze_request,
    answer_follow_up,
    interpret_scenario_request,
)
from botocore.exceptions import (
    ClientError,
    BotoCoreError,
    NoCredentialsError,
    PartialCredentialsError,
    ReadTimeoutError,
    ConnectTimeoutError,
)


ROOT = Path(__file__).resolve().parents[1]


class AWSAvailabilityTests(unittest.TestCase):
    """Tests des pannes AWS et indisponibilité."""

    @patch("agent.service._bedrock_client")
    def test_aws_credentials_missing(self, mock_client):
        """Credentials AWS manquants."""
        mock_client.side_effect = NoCredentialsError()
        result = analyze_request("amira", "NVDA", 10.0, root=ROOT)

        self.assertEqual(result["status"], "partial")
        self.assertIn("analysis", result)  # Les calculs doivent fonctionner
        self.assertIsNone(result.get("explanation"))  # Pas d'explication
        self.assertTrue(any("AWS" in w for w in result.get("warnings", [])))

    @patch("agent.service._bedrock_client")
    def test_aws_credentials_partial(self, mock_client):
        """Credentials AWS incomplets."""
        mock_client.side_effect = PartialCredentialsError(
            provider="env",
            cred_var="AWS_SECRET_ACCESS_KEY"
        )
        result = analyze_request("amira", "NVDA", 10.0, root=ROOT)

        self.assertEqual(result["status"], "partial")
        self.assertIn("warnings", result)

    @patch("agent.service._bedrock_client")
    def test_aws_service_unavailable(self, mock_client):
        """Service AWS indisponible."""
        mock_client.side_effect = ClientError(
            {"Error": {"Code": "ServiceUnavailable", "Message": "Service unavailable"}},
            "InvokeModel"
        )
        result = analyze_request("amira", "NVDA", 10.0, root=ROOT)

        self.assertEqual(result["status"], "partial")

    @patch("agent.service._bedrock_client")
    def test_aws_timeout(self, mock_client):
        """Timeout lors de l'appel AWS."""
        mock_client.return_value.converse.side_effect = ReadTimeoutError(
            endpoint_url="https://bedrock-runtime.us-east-1.amazonaws.com"
        )
        result = analyze_request("amira", "NVDA", 10.0, root=ROOT)

        self.assertEqual(result["status"], "partial")

    @patch("agent.service._bedrock_client")
    def test_aws_connection_timeout(self, mock_client):
        """Timeout de connexion AWS."""
        mock_client.return_value.converse.side_effect = ConnectTimeoutError(
            endpoint_url="https://bedrock-runtime.us-east-1.amazonaws.com"
        )
        result = analyze_request("amira", "NVDA", 10.0, root=ROOT)

        self.assertEqual(result["status"], "partial")

    @patch("agent.service._bedrock_client")
    def test_aws_access_denied(self, mock_client):
        """Accès refusé par IAM."""
        mock_client.return_value.converse.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}},
            "InvokeModel"
        )
        result = analyze_request("amira", "NVDA", 10.0, root=ROOT)

        self.assertEqual(result["status"], "partial")

    @patch("agent.service._bedrock_client")
    def test_aws_throttling(self, mock_client):
        """Rate limiting AWS."""
        mock_client.return_value.converse.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "InvokeModel"
        )
        result = analyze_request("amira", "NVDA", 10.0, root=ROOT)

        self.assertEqual(result["status"], "partial")

    @patch("agent.service._bedrock_client")
    def test_bedrock_model_not_found(self, mock_client):
        """Modèle Bedrock introuvable."""
        mock_client.return_value.converse.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Model not found"}},
            "InvokeModel"
        )
        result = analyze_request("amira", "NVDA", 10.0, root=ROOT)

        self.assertEqual(result["status"], "partial")

    @patch("agent.service._bedrock_client")
    def test_aws_region_unavailable(self, mock_client):
        """Région AWS indisponible."""
        mock_client.return_value.converse.side_effect = ClientError(
            {"Error": {"Code": "InvalidRegion", "Message": "Region not available"}},
            "InvokeModel"
        )
        result = analyze_request("amira", "NVDA", 10.0, root=ROOT)

        self.assertEqual(result["status"], "partial")

    @patch("agent.service._bedrock_client")
    def test_aws_network_error(self, mock_client):
        """Erreur réseau lors de l'appel AWS."""
        mock_client.return_value.converse.side_effect = BotoCoreError()
        result = analyze_request("amira", "NVDA", 10.0, root=ROOT)

        self.assertEqual(result["status"], "partial")


class BedrockValidationTests(unittest.TestCase):
    """Tests de validation des réponses Bedrock."""

    @patch("agent.service._bedrock_client")
    def test_bedrock_invalid_json(self, mock_client):
        """Réponse Bedrock avec JSON invalide."""
        mock_response = {
            "stopReason": "end_turn",
            "output": {"message": {"content": [{"text": "Ceci n'est pas du JSON"}]}}
        }
        mock_client.return_value.converse.return_value = mock_response

        result = analyze_request("amira", "NVDA", 10.0, root=ROOT)
        self.assertEqual(result["status"], "partial")

    @patch("agent.service._bedrock_client")
    def test_bedrock_malformed_response(self, mock_client):
        """Réponse Bedrock malformée."""
        mock_response = {
            "stopReason": "end_turn",
            "output": {}  # Structure incorrecte
        }
        mock_client.return_value.converse.return_value = mock_response

        result = analyze_request("amira", "NVDA", 10.0, root=ROOT)
        self.assertEqual(result["status"], "partial")

    @patch("agent.service._bedrock_client")
    def test_bedrock_missing_required_fields(self, mock_client):
        """Réponse Bedrock sans champs requis."""
        incomplete_explanation = {
            "summary": "Test",
            # Champs manquants: changes, profile_assessment, uncertainties, evidence_refs
        }
        mock_response = {
            "stopReason": "end_turn",
            "output": {"message": {"content": [{"text": json.dumps(incomplete_explanation)}]}}
        }
        mock_client.return_value.converse.return_value = mock_response

        result = analyze_request("amira", "NVDA", 10.0, root=ROOT)
        self.assertEqual(result["status"], "partial")

    @patch("agent.service._bedrock_client")
    def test_bedrock_prohibited_language(self, mock_client):
        """Réponse Bedrock avec langage interdit (garanties, etc.)."""
        explanation_with_prohibited = {
            "summary": "Rendement garanti sans aucun risque",  # Interdit !
            "changes": [],
            "profile_assessment": [],
            "uncertainties": [],
            "evidence_refs": []
        }
        mock_response = {
            "stopReason": "end_turn",
            "output": {"message": {"content": [{"text": json.dumps(explanation_with_prohibited)}]}}
        }
        mock_client.return_value.converse.return_value = mock_response

        result = analyze_request("amira", "NVDA", 10.0, root=ROOT)
        self.assertEqual(result["status"], "partial")

    @patch("agent.service._bedrock_client")
    def test_bedrock_stop_reason_not_end_turn(self, mock_client):
        """Réponse Bedrock avec stopReason différent."""
        mock_response = {
            "stopReason": "max_tokens",  # Pas "end_turn"
            "output": {"message": {"content": [{"text": "{}"}]}}
        }
        mock_client.return_value.converse.return_value = mock_response

        result = analyze_request("amira", "NVDA", 10.0, root=ROOT)
        self.assertEqual(result["status"], "partial")

    @patch("agent.service._bedrock_client")
    def test_bedrock_empty_response(self, mock_client):
        """Réponse Bedrock vide."""
        mock_response = {
            "stopReason": "end_turn",
            "output": {"message": {"content": []}}
        }
        mock_client.return_value.converse.return_value = mock_response

        result = analyze_request("amira", "NVDA", 10.0, root=ROOT)
        self.assertEqual(result["status"], "partial")


class EvidenceAndReferencesTests(unittest.TestCase):
    """Tests des preuves et références."""

    def test_evidence_references_are_valid(self):
        """Vérifier que les références de preuves sont valides."""
        result = analyze_request("amira", "NVDA", 10.0, root=ROOT)

        if result["status"] == "success" and result.get("explanation"):
            evidence_refs = result["explanation"].get("evidence_refs", [])
            for ref in evidence_refs:
                self.assertIsInstance(ref, str)
                self.assertTrue(
                    ref.startswith(("analysis.", "source.", "check."))
                )

    @patch("agent.service._bedrock_client")
    def test_explanation_with_invalid_evidence_refs(self, mock_client):
        """Explication avec références invalides."""
        explanation_invalid_refs = {
            "summary": "Test",
            "changes": [],
            "profile_assessment": [],
            "uncertainties": [],
            "evidence_refs": ["invalid.reference.format"]  # Format invalide
        }
        mock_response = {
            "stopReason": "end_turn",
            "output": {"message": {"content": [{"text": json.dumps(explanation_invalid_refs)}]}}
        }
        mock_client.return_value.converse.return_value = mock_response

        result = analyze_request("amira", "NVDA", 10.0, root=ROOT)
        # Devrait échouer la validation
        self.assertEqual(result["status"], "partial")


class FollowUpTests(unittest.TestCase):
    """Tests des questions de suivi."""

    def test_follow_up_with_valid_question(self):
        """Question de suivi valide."""
        # D'abord, obtenir un résultat d'analyse
        analysis_result = analyze_request("amira", "NVDA", 10.0, root=ROOT)
        request = {"persona_id": "amira", "symbol": "NVDA", "target_weight_pct": 10.0}

        if analysis_result["status"] in ["success", "partial"]:
            follow_up_result = answer_follow_up(
                "Pourquoi le risque change-t-il ?",
                analysis_result,
                request,
                root=ROOT
            )
            self.assertIn("status", follow_up_result)

    def test_follow_up_with_empty_question(self):
        """Question de suivi vide."""
        analysis_result = analyze_request("amira", "NVDA", 10.0, root=ROOT)
        request = {"persona_id": "amira", "symbol": "NVDA", "target_weight_pct": 10.0}

        follow_up_result = answer_follow_up(
            "",
            analysis_result,
            request,
            root=ROOT
        )
        self.assertIn(follow_up_result["status"], ["unavailable", "error"])

    def test_follow_up_with_very_long_question(self):
        """Question de suivi très longue."""
        analysis_result = analyze_request("amira", "NVDA", 10.0, root=ROOT)
        request = {"persona_id": "amira", "symbol": "NVDA", "target_weight_pct": 10.0}

        long_question = "Pourquoi " + "très " * 500 + "long?"
        follow_up_result = answer_follow_up(
            long_question,
            analysis_result,
            request,
            root=ROOT
        )
        self.assertIn("status", follow_up_result)

    @patch("agent.service._bedrock_client")
    def test_follow_up_aws_failure(self, mock_client):
        """Question de suivi avec panne AWS."""
        mock_client.return_value.converse.side_effect = ClientError(
            {"Error": {"Code": "ServiceUnavailable", "Message": "Service unavailable"}},
            "InvokeModel"
        )

        analysis_result = analyze_request("amira", "NVDA", 10.0, root=ROOT)
        request = {"persona_id": "amira", "symbol": "NVDA", "target_weight_pct": 10.0}

        follow_up_result = answer_follow_up(
            "Test question",
            analysis_result,
            request,
            root=ROOT
        )
        self.assertEqual(follow_up_result["status"], "unavailable")


class InterpretScenarioTests(unittest.TestCase):
    """Tests d'interprétation de scénarios en langage naturel."""

    def test_interpret_valid_scenario(self):
        """Interpréter un scénario valide."""
        result = interpret_scenario_request(
            "Pour Amira, tester 15% de NVIDIA",
            root=ROOT
        )
        self.assertIn("status", result)

    def test_interpret_empty_text(self):
        """Interpréter un texte vide."""
        result = interpret_scenario_request("", root=ROOT)
        self.assertIn("status", result)

    def test_interpret_gibberish(self):
        """Interpréter du texte incompréhensible."""
        result = interpret_scenario_request(
            "jklfsjdf slkdjf lksdjflskdjf",
            root=ROOT
        )
        self.assertIn("status", result)

    def test_interpret_very_long_text(self):
        """Interpréter un texte très long."""
        long_text = "Pour Amira, " + "je veux " * 200 + "NVDA"
        result = interpret_scenario_request(long_text, root=ROOT)
        self.assertIn("status", result)

    @patch("agent.service._bedrock_client")
    def test_interpret_with_aws_failure(self, mock_client):
        """Interpréter avec panne AWS."""
        mock_client.return_value.converse.side_effect = ClientError(
            {"Error": {"Code": "ServiceUnavailable", "Message": "Service unavailable"}},
            "InvokeModel"
        )

        result = interpret_scenario_request(
            "Pour Amira, tester 15% de NVIDIA",
            root=ROOT
        )
        self.assertIn("status", result)


class ExplanationContentTests(unittest.TestCase):
    """Tests du contenu de l'explication."""

    def test_explanation_has_summary(self):
        """L'explication doit avoir un résumé."""
        result = analyze_request("amira", "NVDA", 10.0, root=ROOT)

        if result["status"] == "success" and result.get("explanation"):
            self.assertIn("summary", result["explanation"])
            self.assertIsInstance(result["explanation"]["summary"], str)
            self.assertGreater(len(result["explanation"]["summary"]), 0)

    def test_explanation_has_changes(self):
        """L'explication doit décrire les changements."""
        result = analyze_request("amira", "NVDA", 10.0, root=ROOT)

        if result["status"] == "success" and result.get("explanation"):
            self.assertIn("changes", result["explanation"])
            self.assertIsInstance(result["explanation"]["changes"], list)

    def test_explanation_has_uncertainties(self):
        """L'explication doit mentionner les incertitudes."""
        result = analyze_request("amira", "NVDA", 10.0, root=ROOT)

        if result["status"] == "success" and result.get("explanation"):
            self.assertIn("uncertainties", result["explanation"])
            self.assertIsInstance(result["explanation"]["uncertainties"], list)

    def test_explanation_has_profile_assessment(self):
        """L'explication doit évaluer la cohérence avec le profil."""
        result = analyze_request("amira", "NVDA", 10.0, root=ROOT)

        if result["status"] == "success" and result.get("explanation"):
            self.assertIn("profile_assessment", result["explanation"])
            self.assertIsInstance(result["explanation"]["profile_assessment"], list)


class PartialResultsTests(unittest.TestCase):
    """Tests des résultats partiels (calculs OK mais pas d'explication)."""

    @patch("agent.service._selected_model_id")
    def test_partial_when_bedrock_disabled(self, mock_model):
        """Résultat partiel quand Bedrock est désactivé."""
        mock_model.return_value = None

        result = analyze_request("amira", "NVDA", 10.0, root=ROOT)

        self.assertEqual(result["status"], "partial")
        self.assertIn("analysis", result)  # Les calculs doivent fonctionner
        self.assertIsNone(result.get("explanation"))
        self.assertIn("warnings", result)

    def test_partial_results_have_calculations(self):
        """Les résultats partiels doivent avoir les calculs."""
        # Forcer un résultat partiel en désactivant Bedrock
        with patch("agent.service._selected_model_id", return_value=None):
            result = analyze_request("amira", "NVDA", 10.0, root=ROOT)

            self.assertEqual(result["status"], "partial")
            self.assertIn("analysis", result)
            self.assertIn("checks", result)
            self.assertIn("tool_trace", result)


class RobustnessTests(unittest.TestCase):
    """Tests de robustesse générale."""

    def test_repeated_same_request(self):
        """Répéter la même requête plusieurs fois."""
        for _ in range(3):
            result = analyze_request("amira", "NVDA", 10.0, root=ROOT)
            self.assertIn(result["status"], ["success", "partial"])

    def test_alternating_requests(self):
        """Alterner entre différentes requêtes."""
        personas = ["amira", "mateo", "robert"]
        symbols = ["NVDA", "AAPL", "MSFT"]
        weights = [10.0, 15.0, 20.0]

        for persona, symbol, weight in zip(personas, symbols, weights):
            result = analyze_request(persona, symbol, weight, root=ROOT)
            self.assertIn(result["status"], ["success", "partial", "error"])

    @patch("agent.service.MAX_CONVERSE_CALLS", 1)
    def test_max_calls_limit_reached(self, ):
        """Limite d'appels Converse atteinte."""
        result = analyze_request("amira", "NVDA", 10.0, root=ROOT)
        # Devrait retourner un résultat partiel si la limite est atteinte
        self.assertIn(result["status"], ["success", "partial"])


if __name__ == "__main__":
    unittest.main()
