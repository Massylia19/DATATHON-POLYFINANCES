import unittest
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError, EndpointConnectionError

from scripts.aws_support import explain_aws_error, text_blocks
from scripts.list_bedrock_profiles import _is_us_opus_profile, list_all_system_profiles
from scripts import test_bedrock_converse


class FakeBedrockClient:
    def __init__(self):
        self.requests = []

    def list_inference_profiles(self, **request):
        self.requests.append(request)
        if "nextToken" not in request:
            return {
                "inferenceProfileSummaries": [{"inferenceProfileId": "us.first"}],
                "nextToken": "page-2",
            }
        return {"inferenceProfileSummaries": [{"inferenceProfileId": "us.second"}]}


class ProfileListingTests(unittest.TestCase):
    def test_all_pages_are_requested(self):
        client = FakeBedrockClient()
        profiles = list_all_system_profiles(client)
        self.assertEqual(
            [item["inferenceProfileId"] for item in profiles],
            ["us.first", "us.second"],
        )
        self.assertEqual(client.requests[1]["nextToken"], "page-2")

    def test_only_us_opus_profiles_match(self):
        self.assertTrue(
            _is_us_opus_profile(
                {
                    "inferenceProfileName": "US Example Opus",
                    "inferenceProfileId": "us.vendor.example-opus-v1:0",
                }
            )
        )
        self.assertFalse(
            _is_us_opus_profile(
                {
                    "inferenceProfileName": "EU Example Opus",
                    "inferenceProfileId": "eu.vendor.example-opus-v1:0",
                }
            )
        )

    def test_text_blocks_ignores_non_text_content(self):
        self.assertEqual(text_blocks([{"text": "ok"}, {"image": {}}]), "ok")

    def test_expected_aws_errors_have_safe_messages(self):
        expired = ClientError(
            {"Error": {"Code": "ExpiredToken", "Message": "sensitive detail"}},
            "Converse",
        )
        denied = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "detail"}},
            "ListInferenceProfiles",
        )
        invalid = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "detail"}},
            "Converse",
        )
        offline = EndpointConnectionError(endpoint_url="https://example.invalid")

        self.assertIn("expiré", explain_aws_error(expired))
        self.assertIn("Accès refusé", explain_aws_error(denied))
        self.assertIn(
            "incompatible avec Converse",
            explain_aws_error(invalid, invalid_model_is_possible=True),
        )
        self.assertIn("inaccessible", explain_aws_error(offline))

    def test_converse_request_omits_temperature(self):
        client = Mock()
        client.converse.return_value = {
            "output": {"message": {"content": [{"text": "ok"}]}}
        }
        temporary_credentials = {
            "AWS_ACCESS_KEY_ID": "test-placeholder",
            "AWS_SECRET_ACCESS_KEY": "test-placeholder",
            "AWS_SESSION_TOKEN": "test-placeholder",
        }

        with patch.dict("os.environ", temporary_credentials, clear=False), patch.object(
            test_bedrock_converse.boto3, "client", return_value=client
        ), patch(
            "sys.argv", ["test_bedrock_converse.py", "us.test-profile"]
        ), patch("builtins.print"):
            exit_code = test_bedrock_converse.main()

        self.assertEqual(exit_code, 0)
        request = client.converse.call_args.kwargs
        self.assertEqual(request["inferenceConfig"], {"maxTokens": 64})
        self.assertNotIn("temperature", request["inferenceConfig"])


if __name__ == "__main__":
    unittest.main()
