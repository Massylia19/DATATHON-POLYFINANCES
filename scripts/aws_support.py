"""Utilitaires sûrs partagés par les diagnostics AWS.

Ce module ne lit jamais ni n'affiche la valeur des identifiants temporaires.
Il vérifie seulement que les trois noms de variables attendus sont présents.
"""

from __future__ import annotations

import os
import sys
from typing import Iterable


AWS_REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
REQUIRED_AWS_ENV_VARS = (
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
)


def missing_credential_variables() -> list[str]:
    """Retourne les noms des variables absentes ou vides, jamais leurs valeurs."""

    return [name for name in REQUIRED_AWS_ENV_VARS if not os.environ.get(name)]


def require_temporary_credentials() -> bool:
    missing = missing_credential_variables()
    if not missing:
        return True
    print(
        "Identifiants AWS temporaires absents. Variables manquantes : "
        + ", ".join(missing),
        file=sys.stderr,
    )
    return False


def client_error_code(error: Exception) -> str:
    response = getattr(error, "response", {})
    return str(response.get("Error", {}).get("Code", "Unknown"))


def explain_aws_error(error: Exception, *, invalid_model_is_possible: bool = False) -> str:
    """Transforme une exception AWS en message utile sans détails sensibles."""

    error_type = error.__class__.__name__
    if error_type in {"NoCredentialsError", "PartialCredentialsError"}:
        return "Identifiants AWS absents ou incomplets."
    if error_type in {
        "EndpointConnectionError",
        "ConnectTimeoutError",
        "ReadTimeoutError",
    }:
        return "Point de terminaison AWS indisponible ou inaccessible depuis le réseau actuel."

    code = client_error_code(error)
    if code in {"ExpiredToken", "ExpiredTokenException", "RequestExpired"}:
        return "Les identifiants AWS temporaires ont expiré."
    if code in {
        "InvalidClientTokenId",
        "UnrecognizedClientException",
        "SignatureDoesNotMatch",
    }:
        return "Les identifiants AWS sont invalides ou expirés."
    if code in {"AccessDenied", "AccessDeniedException", "UnauthorizedOperation"}:
        return "Accès refusé par IAM. Aucune permission n’a été modifiée."
    if code == "ValidationException":
        return "Requête AWS invalide : vérifier les paramètres et le message détaillé."
    if invalid_model_is_possible and code == "ResourceNotFoundException":
        return "Modèle ou profil introuvable dans la région configurée."
    if code in {
        "ServiceUnavailable",
        "ServiceUnavailableException",
        "ModelNotReadyException",
        "InternalServerException",
        "ThrottlingException",
        "TooManyRequestsException",
    }:
        return f"Service AWS ou modèle temporairement indisponible ({code})."
    return f"Échec de l’appel AWS ({code})."


def text_blocks(content: Iterable[dict]) -> str:
    return "".join(str(block["text"]) for block in content if "text" in block).strip()
