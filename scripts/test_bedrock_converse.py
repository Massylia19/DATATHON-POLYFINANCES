"""Effectue un appel Bedrock Converse court avec un profil fourni explicitement."""

from __future__ import annotations

import argparse
import sys

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError, EndpointConnectionError

if __package__:
    from .aws_support import (
        AWS_REGION,
        explain_aws_error,
        require_temporary_credentials,
        text_blocks,
    )
else:
    from aws_support import (
        AWS_REGION,
        explain_aws_error,
        require_temporary_credentials,
        text_blocks,
    )


TEST_MESSAGE = "Réponds uniquement : Connexion Bedrock depuis Python réussie."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Teste Bedrock Converse avec l’identifiant exact d’un profil."
    )
    parser.add_argument(
        "inference_profile_id",
        help="Identifiant exact retourné par list_bedrock_profiles.py",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not require_temporary_credentials():
        return 2

    config = Config(
        connect_timeout=10,
        read_timeout=60,
        retries={"max_attempts": 2, "mode": "standard"},
    )
    try:
        client = boto3.client("bedrock-runtime", region_name=AWS_REGION, config=config)
        response = client.converse(
            modelId=args.inference_profile_id,
            messages=[{"role": "user", "content": [{"text": TEST_MESSAGE}]}],
            inferenceConfig={"maxTokens": 64},
        )
        returned_text = text_blocks(response["output"]["message"]["content"])
        if not returned_text:
            print("Bedrock a répondu sans bloc de texte exploitable.", file=sys.stderr)
            return 1
    except ClientError as error:
        error_details = error.response.get("Error", {})
        response_metadata = error.response.get("ResponseMetadata", {})
        print(f"Code: {error_details.get('Code')}", file=sys.stderr)
        print(f"Message: {error_details.get('Message')}", file=sys.stderr)
        print(f"RequestId: {response_metadata.get('RequestId')}", file=sys.stderr)
        return 1
    except (EndpointConnectionError, BotoCoreError) as error:
        print(
            explain_aws_error(error, invalid_model_is_possible=True),
            file=sys.stderr,
        )
        return 1
    except (KeyError, TypeError):
        print("La réponse Bedrock ne respecte pas la structure Converse attendue.", file=sys.stderr)
        return 1

    print(returned_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
