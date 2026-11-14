"""Orchestration Bedrock Converse pour l'agent AlphaForge."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config

from agent.context import RequestContext, create_request_context
from agent.evidence import build_evidence_bundle, resolve_evidence_reference
from agent.prompts import MODEL_EXPLANATION_FORMAT, SYSTEM_INSTRUCTIONS
from agent.tools import TOOL_SPECS, dispatch_tool
from alphaforge.engine import EngineError, PROJECT_ROOT
from scripts.aws_support import AWS_REGION, explain_aws_error


MODEL_ID_ENV = "BEDROCK_MODEL_ID"
MAX_CONVERSE_CALLS = 8
MAX_TOOL_EXECUTIONS = 12
MAX_OUTPUT_TOKENS = 2048
MAX_REPAIR_ATTEMPTS = 1


def _bedrock_client() -> Any:
    config = Config(
        connect_timeout=5,
        read_timeout=60,
        retries={"max_attempts": 3, "mode": "standard"},
    )
    return boto3.client("bedrock-runtime", region_name=AWS_REGION, config=config)


def _error_response(code: str, message: str) -> dict[str, Any]:
    return {
        "status": "error",
        "analysis": None,
        "checks": [],
        "explanation": None,
        "warnings": [],
        "tool_trace": [],
        "error": {"code": code, "message": message},
    }


def _partial_response(
    context: RequestContext,
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "status": "partial",
        "analysis": deepcopy(context.analysis),
        "checks": deepcopy(context.checks or []),
        "explanation": None,
        "warnings": warnings,
        "tool_trace": deepcopy(context.tool_trace),
    }


def _mark_trace_origin(
    context: RequestContext, start_index: int, execution_origin: str
) -> None:
    for entry in context.tool_trace[start_index:]:
        entry["execution_origin"] = execution_origin


def _dispatch(
    context: RequestContext,
    tool_name: str,
    arguments: Any,
    *,
    execution_origin: str,
) -> dict[str, Any]:
    start_index = len(context.tool_trace)
    result = dispatch_tool(context, tool_name, arguments)
    _mark_trace_origin(context, start_index, execution_origin)
    return result


def _ensure_local_results(
    context: RequestContext,
    warnings: list[str],
) -> dict[str, Any] | None:
    """Complète localement les calculs après un échec AWS, sans simuler AWS."""
    arguments = context.request.as_dict()
    if context.analysis is None:
        simulation = _dispatch(
            context,
            "simulate_portfolio_change",
            arguments,
            execution_origin="local_fallback",
        )
        if simulation["status"] == "error":
            return _error_response(
                simulation["error"]["code"], simulation["error"]["message"]
            )
        warnings.append(
            "La simulation a été calculée localement après l'indisponibilité AWS."
        )
    if context.checks is None:
        checks = _dispatch(
            context,
            "check_profile",
            arguments,
            execution_origin="local_fallback",
        )
        if checks["status"] == "error":
            warnings.append(
                "Les contrôles de profil n'ont pas pu être produits: "
                + checks["error"]["message"]
            )
        else:
            warnings.append(
                "Les contrôles ont été exécutés localement, sans réponse du modèle."
            )
    return None


def _initial_user_message(context: RequestContext) -> dict[str, Any]:
    request_json = json.dumps(context.request.as_dict(), ensure_ascii=False)
    return {
        "role": "user",
        "content": [
            {
                "text": (
                    "Analyse cette demande AlphaForge en utilisant les deux outils "
                    f"dans l'ordre requis. Demande normalisée: {request_json}. "
                    "Retourne ensuite uniquement le JSON structuré demandé."
                )
            }
        ],
    }


def _converse_arguments(
    model_id: str, messages: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "modelId": model_id,
        "system": [{"text": SYSTEM_INSTRUCTIONS}],
        "messages": messages,
        "toolConfig": {"tools": TOOL_SPECS},
        "inferenceConfig": {"maxTokens": MAX_OUTPUT_TOKENS},
    }


def _assistant_message(response: dict[str, Any]) -> dict[str, Any]:
    message = response.get("output", {}).get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), list):
        raise ValueError("Réponse Converse sans message assistant valide.")
    return message


def _tool_uses(message: dict[str, Any]) -> list[dict[str, Any]]:
    uses = []
    for index, block in enumerate(message.get("content", [])):
        tool_use = block.get("toolUse") if isinstance(block, dict) else None
        if isinstance(tool_use, dict):
            uses.append({"index": index, **tool_use})
    priorities = {"simulate_portfolio_change": 0, "check_profile": 1}
    return sorted(
        uses,
        key=lambda item: (priorities.get(str(item.get("name")), 2), item["index"]),
    )


def _model_tool_payload(
    context: RequestContext, dispatcher_result: dict[str, Any]
) -> dict[str, Any]:
    if dispatcher_result["status"] == "error":
        return dispatcher_result
    return {"status": "success", "result": build_evidence_bundle(context)}


def _tool_result_message(
    tool_results: list[tuple[str, dict[str, Any]]]
) -> dict[str, Any]:
    content = []
    for tool_use_id, result in tool_results:
        content.append(
            {
                "toolResult": {
                    "toolUseId": tool_use_id,
                    "content": [{"json": result}],
                    "status": "success" if result["status"] == "success" else "error",
                }
            }
        )
    return {"role": "user", "content": content}


def _text_from_message(message: dict[str, Any]) -> str:
    return "".join(
        str(block["text"])
        for block in message.get("content", [])
        if isinstance(block, dict) and "text" in block
    ).strip()


def _parse_json_text(text: str) -> Any:
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        stripped = "\n".join(lines[1:-1]).strip()
    return json.loads(stripped)


def _validate_string_list(value: Any, path: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{path} doit être une liste de textes.")
    return value


def _validate_model_explanation(
    value: Any, context: RequestContext
) -> dict[str, Any]:
    """Valide la structure et les références, pas l'exactitude de toute la prose."""
    if not isinstance(value, dict):
        raise ValueError("L'explication doit être un objet JSON.")
    allowed = set(MODEL_EXPLANATION_FORMAT["properties"])
    required = set(MODEL_EXPLANATION_FORMAT["required"])
    keys = set(value)
    if "tool_trace" in keys:
        raise ValueError("Le modèle ne doit pas produire tool_trace.")
    if missing := required - keys:
        raise ValueError("Champs obligatoires absents: " + ", ".join(sorted(missing)))
    if unexpected := keys - allowed:
        raise ValueError("Champs inattendus: " + ", ".join(sorted(unexpected)))
    if not isinstance(value["summary"], str):
        raise ValueError("summary doit être un texte.")
    if not isinstance(value["changes"], list):
        raise ValueError("changes doit être une liste.")
    if not isinstance(value["profile_assessment"], list):
        raise ValueError("profile_assessment doit être une liste.")
    _validate_string_list(value["uncertainties"], "uncertainties")
    all_references = list(
        _validate_string_list(value["evidence_refs"], "evidence_refs")
    )

    for index, change in enumerate(value["changes"]):
        if not isinstance(change, dict) or set(change) != {"message", "evidence_refs"}:
            raise ValueError(f"changes[{index}] ne respecte pas le format attendu.")
        if not isinstance(change["message"], str):
            raise ValueError(f"changes[{index}].message doit être un texte.")
        all_references.extend(
            _validate_string_list(
                change["evidence_refs"], f"changes[{index}].evidence_refs"
            )
        )

    real_checks = {check["id"]: check for check in context.checks or []}
    model_checks: dict[str, str] = {}
    for index, assessment in enumerate(value["profile_assessment"]):
        expected_keys = {"check_id", "status", "message", "evidence_refs"}
        if not isinstance(assessment, dict) or set(assessment) != expected_keys:
            raise ValueError(
                f"profile_assessment[{index}] ne respecte pas le format attendu."
            )
        check_id = assessment["check_id"]
        status = assessment["status"]
        if not isinstance(check_id, str) or not isinstance(status, str):
            raise ValueError("check_id et status doivent être des textes.")
        if not isinstance(assessment["message"], str):
            raise ValueError("Le message d'un contrôle doit être un texte.")
        if check_id in model_checks:
            raise ValueError(f"Contrôle dupliqué dans l'explication: {check_id}")
        model_checks[check_id] = status
        all_references.extend(
            _validate_string_list(
                assessment["evidence_refs"],
                f"profile_assessment[{index}].evidence_refs",
            )
        )

    expected_checks = {key: check["status"] for key, check in real_checks.items()}
    if model_checks != expected_checks:
        raise ValueError(
            "Les check_id ou statuts ne correspondent pas aux contrôles exécutés."
        )
    for reference in dict.fromkeys(all_references):
        resolution = resolve_evidence_reference(context, reference)
        if resolution["status"] != "resolved":
            raise ValueError(f"Référence de preuve introuvable: {reference}")
    return deepcopy(value)


def _correction_message(context: RequestContext, reason: str) -> dict[str, Any]:
    payload = json.dumps(build_evidence_bundle(context), ensure_ascii=False)
    return {
        "role": "user",
        "content": [
            {
                "text": (
                    "La réponse est incomplète ou invalide: "
                    f"{reason} Corrige-la et retourne uniquement le JSON demandé. "
                    f"Contexte de preuves condensé: {payload}"
                )
            }
        ],
    }


def analyze_request(
    persona_id: str,
    symbol: str,
    target_weight_pct: float,
    *,
    client: Any | None = None,
    root: Path = PROJECT_ROOT,
    model_id: str | None = None,
    max_converse_calls: int = MAX_CONVERSE_CALLS,
    max_tool_executions: int = MAX_TOOL_EXECUTIONS,
) -> dict[str, Any]:
    """Analyse une demande avec Converse et les outils déterministes AlphaForge."""
    try:
        context = create_request_context(
            persona_id, symbol, target_weight_pct, root=root
        )
    except EngineError as exc:
        return _error_response(exc.code, exc.message)
    except (OSError, KeyError, TypeError, ValueError) as exc:
        return _error_response("INTERNAL_ERROR", str(exc))

    warnings: list[str] = []
    selected_model = model_id or os.environ.get(MODEL_ID_ENV)
    if not selected_model:
        warnings.append(
            "BEDROCK_MODEL_ID est absent; aucune explication AWS n'a été produite."
        )
        blocking = _ensure_local_results(context, warnings)
        return blocking or _partial_response(context, warnings)

    if client is None:
        try:
            client = _bedrock_client()
        except Exception as exc:
            warnings.append(explain_aws_error(exc, invalid_model_is_possible=True))
            blocking = _ensure_local_results(context, warnings)
            return blocking or _partial_response(context, warnings)

    messages = [_initial_user_message(context)]
    tool_executions = 0
    repair_attempts = 0

    for _call_index in range(max_converse_calls):
        try:
            response = client.converse(**_converse_arguments(selected_model, messages))
            assistant = _assistant_message(response)
        except Exception as exc:
            warnings.append(explain_aws_error(exc, invalid_model_is_possible=True))
            blocking = _ensure_local_results(context, warnings)
            return blocking or _partial_response(context, warnings)

        messages.append(assistant)
        stop_reason = response.get("stopReason")
        uses = _tool_uses(assistant)
        if uses:
            if tool_executions + len(uses) > max_tool_executions:
                warnings.append("La limite d'exécutions d'outils a été atteinte.")
                blocking = _ensure_local_results(context, warnings)
                return blocking or _partial_response(context, warnings)
            results = []
            for tool_use in uses:
                tool_executions += 1
                dispatcher_result = _dispatch(
                    context,
                    str(tool_use.get("name", "")),
                    tool_use.get("input"),
                    execution_origin="bedrock_tool_request",
                )
                results.append(
                    (
                        str(tool_use.get("toolUseId", "")),
                        _model_tool_payload(context, dispatcher_result),
                    )
                )
            messages.append(_tool_result_message(results))
            continue

        if stop_reason != "end_turn":
            messages.append(
                _correction_message(
                    context,
                    f"La réponse s'est arrêtée avec stopReason={stop_reason!r}.",
                )
            )
            continue

        if context.analysis is None or context.checks is None:
            messages.append(
                _correction_message(
                    context,
                    "La simulation et les contrôles doivent réussir avant la conclusion.",
                )
            )
            continue

        text = _text_from_message(assistant)
        try:
            explanation = _validate_model_explanation(
                _parse_json_text(text), context
            )
        except (json.JSONDecodeError, ValueError) as exc:
            if repair_attempts < MAX_REPAIR_ATTEMPTS:
                repair_attempts += 1
                messages.append(_correction_message(context, str(exc)))
                continue
            warnings.append(
                "L'explication Bedrock est restée invalide après une tentative de réparation."
            )
            return _partial_response(context, warnings)

        explanation["tool_trace"] = deepcopy(context.tool_trace)
        return {
            "status": "success",
            "analysis": deepcopy(context.analysis),
            "checks": deepcopy(context.checks),
            "explanation": explanation,
            "warnings": warnings,
            "tool_trace": deepcopy(context.tool_trace),
        }

    warnings.append("La limite d'appels Converse a été atteinte.")
    blocking = _ensure_local_results(context, warnings)
    return blocking or _partial_response(context, warnings)
