"""Liste les profils d'inférence US dont le nom ou l'identifiant contient Opus."""

from __future__ import annotations

import sys
from typing import Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError, EndpointConnectionError

if __package__:
    from .aws_support import AWS_REGION, explain_aws_error, require_temporary_credentials
else:
    from aws_support import AWS_REGION, explain_aws_error, require_temporary_credentials


def _is_us_opus_profile(summary: dict) -> bool:
    name = str(summary.get("inferenceProfileName", ""))
    identifier = str(summary.get("inferenceProfileId", ""))
    searchable = f"{name} {identifier}".casefold()
    normalized_name = name.casefold().strip()
    return "opus" in searchable and (
        identifier.casefold().startswith("us.") or normalized_name.startswith("us ")
    )


def list_all_system_profiles(client) -> list[dict]:
    """Parcourt explicitement toutes les pages de ListInferenceProfiles."""

    profiles: list[dict] = []
    next_token: Optional[str] = None
    while True:
        request = {"typeEquals": "SYSTEM_DEFINED", "maxResults": 100}
        if next_token:
            request["nextToken"] = next_token
        response = client.list_inference_profiles(**request)
        profiles.extend(response.get("inferenceProfileSummaries", []))
        next_token = response.get("nextToken")
        if not next_token:
            return profiles


def main() -> int:
    if not require_temporary_credentials():
        return 2
    try:
        client = boto3.client("bedrock", region_name=AWS_REGION)
        matches = [
            profile
            for profile in list_all_system_profiles(client)
            if _is_us_opus_profile(profile)
        ]
    except (ClientError, EndpointConnectionError, BotoCoreError) as error:
        print(explain_aws_error(error), file=sys.stderr)
        return 1

    if not matches:
        print("Aucun profil d’inférence US contenant « Opus » n’a été trouvé.")
        return 0

    for profile in sorted(matches, key=lambda item: item.get("inferenceProfileName", "")):
        print(f"{profile['inferenceProfileName']}\t{profile['inferenceProfileId']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
