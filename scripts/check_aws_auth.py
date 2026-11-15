"""Vérifie les identifiants temporaires avec STS sans afficher l'identité."""

from __future__ import annotations

import sys

import boto3
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    EndpointConnectionError,
    NoCredentialsError,
)

if __package__:
    from .aws_support import AWS_REGION, explain_aws_error
else:
    from aws_support import AWS_REGION, explain_aws_error


def main() -> int:
    session = boto3.Session()
    if session.get_credentials() is None:
        print(
            "Identifiants AWS introuvables. Enregistrez le profil [default] "
            "dans %USERPROFILE%\\.aws\\credentials.",
            file=sys.stderr,
        )
        return 2
    try:
        session.client("sts", region_name=AWS_REGION).get_caller_identity()
    except (ClientError, EndpointConnectionError, BotoCoreError, NoCredentialsError) as error:
        print(explain_aws_error(error), file=sys.stderr)
        return 1
    print("Authentification AWS réussie.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
