"""Vérifie les identifiants temporaires avec STS sans afficher l'identité."""

from __future__ import annotations

import sys

import boto3
from botocore.exceptions import BotoCoreError, ClientError, EndpointConnectionError

if __package__:
    from .aws_support import AWS_REGION, explain_aws_error, require_temporary_credentials
else:
    from aws_support import AWS_REGION, explain_aws_error, require_temporary_credentials


def main() -> int:
    if not require_temporary_credentials():
        return 2
    try:
        boto3.client("sts", region_name=AWS_REGION).get_caller_identity()
    except (ClientError, EndpointConnectionError, BotoCoreError) as error:
        print(explain_aws_error(error), file=sys.stderr)
        return 1
    print("Authentification AWS réussie.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
