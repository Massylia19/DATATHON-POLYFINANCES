"""Outils déterministes destinés à la future boucle Bedrock Converse."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from typing import Any

from agent.context import RequestContext, _normalize_request
from alphaforge.engine import EngineError, run_analysis
from alphaforge.profile_checks import validate_profile


REQUEST_PROPERTIES = {
    "persona_id": {
        "type": "string",
        "enum": ["amira", "mateo", "robert"],
        "description": "Identifiant du persona de la demande initiale.",
    },
    "symbol": {
        "type": "string",
        "minLength": 1,
        "description": "Symbole exact de l'actif ajouté.",
    },
    "target_weight_pct": {
        "type": "number",
        "exclusiveMinimum": 0,
        "exclusiveMaximum": 100,
        "description": "Poids cible en pourcentage; 10 signifie 10 %.",
    },
}


def _request_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": deepcopy(REQUEST_PROPERTIES),
        "required": ["persona_id", "symbol", "target_weight_pct"],
        "additionalProperties": False,
    }


TOOL_SPECS = [
    {
        "toolSpec": {
            "name": "simulate_portfolio_change",
            "description": (
                "Calcule la comparaison historique réelle avant/après pour la "
                "demande initiale validée. Utiliser avant toute conclusion chiffrée."
            ),
            "inputSchema": {"json": _request_schema()},
        }
    },
    {
        "toolSpec": {
            "name": "check_profile",
            "description": (
                "Exécute les contrôles du profil sur la simulation réussie déjà "
                "stockée. N'accepte aucune métrique fournie par le modèle."
            ),
            "inputSchema": {"json": _request_schema()},
        }
    },
]


class ToolFailure(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        arguments: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.arguments = arguments


def _trace(
    context: RequestContext,
    tool: str,
    arguments: dict[str, Any],
    status: str,
    *,
    result: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
) -> None:
    entry: dict[str, Any] = {
        "tool": tool,
        "arguments": deepcopy(arguments),
        "status": status,
    }
    if result is not None:
        entry["result"] = deepcopy(result)
    if error is not None:
        entry["error"] = deepcopy(error)
    context.tool_trace.append(entry)


def _safe_invalid_arguments(arguments: Any) -> dict[str, Any]:
    if isinstance(arguments, Mapping):
        return {"provided_keys": sorted(str(key) for key in arguments)}
    return {"received_type": type(arguments).__name__}


def _validate_bound_arguments(
    context: RequestContext, arguments: Any
) -> dict[str, Any]:
    if not isinstance(arguments, Mapping):
        raise ToolFailure("INVALID_TOOL_ARGUMENTS", "Les arguments doivent être un objet JSON.")
    required = {"persona_id", "symbol", "target_weight_pct"}
    keys = set(arguments)
    missing = required - keys
    unexpected = keys - required
    if missing or unexpected:
        details = []
        if missing:
            details.append("champs manquants: " + ", ".join(sorted(missing)))
        if unexpected:
            details.append("champs inattendus: " + ", ".join(sorted(unexpected)))
        raise ToolFailure("INVALID_TOOL_ARGUMENTS", "; ".join(details))
    try:
        normalized = _normalize_request(
            arguments["persona_id"],
            arguments["symbol"],
            arguments["target_weight_pct"],
        )
    except EngineError as exc:
        raise ToolFailure(exc.code, exc.message) from exc
    if normalized != context.request:
        raise ToolFailure(
            "REQUEST_MISMATCH",
            "Les arguments de l'outil diffèrent de la demande initiale validée.",
            arguments=normalized.as_dict(),
        )
    return normalized.as_dict()


def simulate_portfolio_change(
    context: RequestContext, arguments: Any
) -> dict[str, Any]:
    """Exécute le moteur et stocke son résultat dans le contexte de la demande."""
    tool_name = "simulate_portfolio_change"
    try:
        validated = _validate_bound_arguments(context, arguments)
    except ToolFailure as exc:
        error = {"code": exc.code, "message": exc.message}
        _trace(
            context,
            tool_name,
            exc.arguments or _safe_invalid_arguments(arguments),
            "error",
            error=error,
        )
        return {"status": "error", "error": error}

    try:
        analysis = run_analysis(
            validated["persona_id"],
            validated["symbol"],
            validated["target_weight_pct"],
            root=context.root,
        )
    except EngineError as exc:
        error = {"code": exc.code, "message": exc.message}
        _trace(context, tool_name, validated, "error", error=error)
        return {"status": "error", "error": error}
    except (OSError, KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        error = {"code": "ENGINE_ERROR", "message": str(exc)}
        _trace(context, tool_name, validated, "error", error=error)
        return {"status": "error", "error": error}
    except Exception as exc:  # pragma: no cover - garde-fou pour la future boucle
        error = {"code": "INTERNAL_ERROR", "message": type(exc).__name__}
        _trace(context, tool_name, validated, "error", error=error)
        return {"status": "error", "error": error}

    context.analysis = analysis
    context.checks = None
    _trace(
        context,
        tool_name,
        validated,
        "success",
        result={
            "internal_reference": "context.analysis",
            "scenario": deepcopy(analysis["scenario"]),
            "period": deepcopy(analysis["period"]),
            "currency": analysis["currency"],
        },
    )
    return {"status": "success", "result": analysis}


def check_profile(context: RequestContext, arguments: Any) -> dict[str, Any]:
    """Exécute les contrôles sur le profil et l'analyse stockés par l'application."""
    tool_name = "check_profile"
    try:
        validated = _validate_bound_arguments(context, arguments)
    except ToolFailure as exc:
        error = {"code": exc.code, "message": exc.message}
        _trace(
            context,
            tool_name,
            exc.arguments or _safe_invalid_arguments(arguments),
            "error",
            error=error,
        )
        return {"status": "error", "error": error}

    if context.analysis is None:
        error = {
            "code": "SIMULATION_REQUIRED",
            "message": "Une simulation réussie est requise avant le contrôle du profil.",
        }
        _trace(context, tool_name, validated, "error", error=error)
        return {"status": "error", "error": error}

    scenario = {
        "persona_id": context.request.persona_id,
        "symbol": context.request.symbol,
        "target_weight_pct": context.request.target_weight_pct,
    }
    try:
        checks = validate_profile(
            context.profile,
            scenario,
            context.analysis,
            context.root / "data",
        )
    except (OSError, KeyError, TypeError, ValueError) as exc:
        error = {"code": "PROFILE_CHECK_ERROR", "message": str(exc)}
        _trace(context, tool_name, validated, "error", error=error)
        return {"status": "error", "error": error}
    except Exception as exc:  # pragma: no cover - garde-fou pour la future boucle
        error = {"code": "INTERNAL_ERROR", "message": type(exc).__name__}
        _trace(context, tool_name, validated, "error", error=error)
        return {"status": "error", "error": error}

    context.checks = checks
    _trace(
        context,
        tool_name,
        validated,
        "success",
        result={
            "internal_reference": "context.checks",
            "check_ids": [check["id"] for check in checks],
            "statuses": [check["status"] for check in checks],
        },
    )
    return {"status": "success", "result": checks}


TOOL_DISPATCH: dict[str, Callable[[RequestContext, Any], dict[str, Any]]] = {
    "simulate_portfolio_change": simulate_portfolio_change,
    "check_profile": check_profile,
}


def dispatch_tool(
    context: RequestContext, tool_name: str, arguments: Any
) -> dict[str, Any]:
    """Exécute uniquement un outil explicitement autorisé."""
    tool = TOOL_DISPATCH.get(tool_name)
    if tool is None:
        error = {
            "code": "UNKNOWN_TOOL",
            "message": f"Outil non autorisé: {tool_name}",
        }
        _trace(
            context,
            str(tool_name),
            _safe_invalid_arguments(arguments),
            "error",
            error=error,
        )
        return {"status": "error", "error": error}
    return tool(context, arguments)
