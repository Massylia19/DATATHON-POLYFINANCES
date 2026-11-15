"""Orchestration Bedrock Converse pour l'agent AlphaForge."""

from __future__ import annotations

import json
import math
import os
import re
from importlib import import_module
from copy import deepcopy
from numbers import Real
from pathlib import Path
from typing import Any

try:
    _boto3: Any = import_module("boto3")
    _botocore_config: Any = import_module("botocore.config")
except ModuleNotFoundError as exc:  # Le moteur local reste utilisable sans AWS.
    if exc.name not in {"boto3", "botocore"}:
        raise
    _boto3 = None
    _botocore_config = None

from agent.context import RequestContext, create_request_context
from agent.evidence import (
    build_public_evidence_catalog,
    build_evidence_bundle,
    public_reference_category,
    public_reference_unit,
    resolve_evidence_reference,
)
from agent.prompts import CHANGE_TOPICS, MODEL_EXPLANATION_FORMAT, SYSTEM_INSTRUCTIONS
from agent.tools import TOOL_SPECS, dispatch_tool
from alphaforge.engine import EngineError, PROJECT_ROOT
from scripts.aws_support import AWS_REGION, explain_aws_error


MODEL_ID_ENV = "BEDROCK_MODEL_ID"
MAX_CONVERSE_CALLS = 8
MAX_TOOL_EXECUTIONS = 12
MAX_OUTPUT_TOKENS = 2048
MAX_REPAIR_ATTEMPTS = 1

_NUMBER_PATTERN = re.compile(
    r"(?<![\w.])[+-]?(?:\d+(?:[.,]\d+)?|[.,]\d+)\s*(?:%|points?)?",
    re.IGNORECASE,
)
_PROHIBITED_LANGUAGE = [
    re.compile(r"\b(?:rendement|profit|gain)s?\s+garanti(?:e|s|es)?\b", re.I),
    re.compile(
        r"\bgaranti(?:t|ra|e|s|es)?\s+(?:un\s+)?(?:rendement|profit|gain)\b",
        re.I,
    ),
    re.compile(r"\bsans\s+(?:aucun\s+)?risque\b", re.I),
    re.compile(
        r"\b(?:va|vont|devrait|doit)\s+(?:certainement\s+)?"
        r"(?:monter|augmenter|rapporter|gagner)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:achetez|vendez|il faut acheter|je recommande d['’]acheter)\b",
        re.I,
    ),
]


class ExplanationValidationError(ValueError):
    """Erreur publique et concise, sans contenu de conversation ni secret."""

    def __init__(
        self,
        field: str,
        rule: str,
        references: list[str] | tuple[str, ...] = (),
    ) -> None:
        super().__init__(rule)
        self.field = field
        self.rule = rule
        self.references = list(dict.fromkeys(references))

    def public_message(self, stage: str) -> str:
        references = (
            ", ".join(self.references) if self.references else "aucune"
        )
        return (
            f"Validation de l'explication ({stage}) — champ: {self.field}; "
            f"règle: {self.rule}; références: {references}."
        )


def _bedrock_client() -> Any:
    if _boto3 is None or _botocore_config is None:
        raise RuntimeError(
            "boto3 n'est pas installé; l'explication AWS est indisponible."
        )
    config = _botocore_config.Config(
        connect_timeout=5,
        read_timeout=60,
        retries={"max_attempts": 3, "mode": "standard"},
    )
    return _boto3.client("bedrock-runtime", region_name=AWS_REGION, config=config)


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
    format_json = json.dumps(MODEL_EXPLANATION_FORMAT, ensure_ascii=False)
    return {
        "role": "user",
        "content": [
            {
                "text": (
                    "Analyse cette demande AlphaForge en utilisant les deux outils "
                    f"dans l'ordre requis. Demande normalisée: {request_json}. "
                    "Retourne ensuite uniquement le JSON structuré demandé. "
                    f"Schéma JSON exact: {format_json}"
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
        raise ExplanationValidationError(path, "doit être une liste de textes")
    if any(not item.strip() for item in value):
        raise ExplanationValidationError(
            path, "ne doit pas contenir de texte vide"
        )
    return value


def _validate_nonempty_text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExplanationValidationError(path, "doit être un texte non vide")
    return value


def _reference_matches_topic(reference: str, topic: str) -> bool:
    return public_reference_category(reference) == topic


def _topic_mismatch_error(
    field: str, reference: str, topic: str, context: RequestContext
) -> ExplanationValidationError:
    actual_category = public_reference_category(reference)
    compatible = [
        entry["reference"]
        for entry in build_public_evidence_catalog(context)
        if entry["category"] == topic
    ]
    available = ", ".join(compatible[:8]) or "aucune référence disponible"
    return ExplanationValidationError(
        field,
        f"topic reçu {topic!r}; la référence incompatible {reference!r} est "
        f"classée {actual_category!r}. Références compatibles disponibles pour "
        f"{topic!r}: {available}. Réserver changes aux différences avant/après; "
        "devise, période et méthode sont des métadonnées communes à placer dans "
        "le résumé ou les incertitudes, sans changer arbitrairement le topic",
        [reference, *compatible[:8]],
    )


def _missing_reference_error(
    field: str, reference: str, context: RequestContext
) -> ExplanationValidationError:
    if reference.startswith("context.analysis."):
        public_reference = reference.removeprefix("context.")
        resolution = resolve_evidence_reference(context, public_reference)
        if resolution["status"] == "resolved":
            return ExplanationValidationError(
                field,
                f"utiliser le chemin public attendu {public_reference} au lieu "
                f"du chemin interne interdit {reference}",
                [public_reference],
            )
    if reference.startswith("context."):
        return ExplanationValidationError(
            field,
            "les préfixes context.* sont internes et interdits; choisir une "
            "référence analysis.* ou source.* du catalogue public",
        )
    return ExplanationValidationError(
        field,
        "la référence de preuve est introuvable dans le catalogue public",
        [reference],
    )


def _validate_metric_citations(
    value: Any,
    *,
    path: str,
    evidence_refs: list[str],
    context: RequestContext,
    topic: str | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ExplanationValidationError(path, "doit être une liste")
    for index, citation in enumerate(value):
        citation_path = f"{path}[{index}]"
        if not isinstance(citation, dict) or set(citation) != {
            "evidence_ref",
            "value",
            "unit",
        }:
            raise ExplanationValidationError(
                citation_path,
                "doit contenir exactement evidence_ref, value et unit",
            )
        reference = _validate_nonempty_text(
            citation["evidence_ref"], f"{citation_path}.evidence_ref"
        )
        if not reference.startswith(("analysis.", "source.")):
            raise _missing_reference_error(
                f"{citation_path}.evidence_ref", reference, context
            )
        resolution = resolve_evidence_reference(context, reference)
        if resolution["status"] != "resolved":
            raise _missing_reference_error(
                f"{citation_path}.evidence_ref", reference, context
            )
        if reference not in evidence_refs:
            owner_path = path.removesuffix(".metrics")
            raise ExplanationValidationError(
                f"{citation_path}.evidence_ref",
                f"ajouter la référence publique {reference} à "
                f"{owner_path}.evidence_refs; metrics[].evidence_ref doit aussi "
                "figurer dans evidence_refs du même constat",
                [reference],
            )
        if topic is not None and not _reference_matches_topic(reference, topic):
            raise _topic_mismatch_error(
                f"{citation_path}.evidence_ref", reference, topic, context
            )
        real_value = resolution["value"]
        stated_value = citation["value"]
        if (
            isinstance(real_value, bool)
            or not isinstance(real_value, Real)
            or isinstance(stated_value, bool)
            or not isinstance(stated_value, Real)
            or not math.isfinite(float(stated_value))
        ):
            raise ExplanationValidationError(
                f"{citation_path}.value",
                "doit référencer un nombre réel et fini",
                [reference],
            )
        if not math.isclose(
            float(stated_value), float(real_value), rel_tol=1e-12, abs_tol=1e-12
        ):
            raise ExplanationValidationError(
                f"{citation_path}.value",
                "ne correspond pas à la valeur structurée du moteur",
                [reference],
            )
        expected_unit = public_reference_unit(reference, real_value)
        if citation["unit"] != expected_unit:
            raise ExplanationValidationError(
                f"{citation_path}.unit",
                f"doit être {expected_unit!r}",
                [reference],
            )
    return value


def _validate_model_language(texts: list[tuple[str, str]]) -> None:
    for field, text in texts:
        for pattern in _PROHIBITED_LANGUAGE:
            if pattern.search(text):
                raise ExplanationValidationError(
                    field,
                    "contient une promesse, une prédiction ou une recommandation "
                    "catégorique interdite",
                )


def _validate_model_explanation(
    value: Any, context: RequestContext
) -> dict[str, Any]:
    """Valide la structure et les références, pas l'exactitude de toute la prose."""
    if not isinstance(value, dict):
        raise ExplanationValidationError("$", "doit être un objet JSON")
    allowed = set(MODEL_EXPLANATION_FORMAT["properties"])
    required = set(MODEL_EXPLANATION_FORMAT["required"])
    keys = set(value)
    if "tool_trace" in keys:
        raise ExplanationValidationError(
            "tool_trace", "doit être ajouté uniquement par l'application"
        )
    if missing := required - keys:
        raise ExplanationValidationError(
            "$", "champs obligatoires absents: " + ", ".join(sorted(missing))
        )
    if unexpected := keys - allowed:
        raise ExplanationValidationError(
            "$", "champs inattendus: " + ", ".join(sorted(unexpected))
        )
    summary = _validate_nonempty_text(value["summary"], "summary")
    if _NUMBER_PATTERN.search(summary):
        raise ExplanationValidationError(
            "summary",
            "doit rester qualitatif; les chiffres appartiennent aux constats sourcés",
        )
    if not isinstance(value["changes"], list):
        raise ExplanationValidationError("changes", "doit être une liste")
    if not isinstance(value["profile_assessment"], list):
        raise ExplanationValidationError(
            "profile_assessment", "doit être une liste"
        )
    uncertainties = _validate_string_list(value["uncertainties"], "uncertainties")
    all_references = list(
        _validate_string_list(value["evidence_refs"], "evidence_refs")
    )

    model_texts = [("summary", summary)]
    model_texts.extend(
        (f"uncertainties[{index}]", text)
        for index, text in enumerate(uncertainties)
    )
    for index, change in enumerate(value["changes"]):
        expected_keys = {"topic", "message", "evidence_refs", "metrics"}
        if not isinstance(change, dict) or set(change) != expected_keys:
            raise ExplanationValidationError(
                f"changes[{index}]",
                "doit contenir exactement topic, message, evidence_refs et metrics",
            )
        topic = change["topic"]
        if topic not in CHANGE_TOPICS:
            candidate_references = change.get("evidence_refs")
            if (
                topic in {"period", "methodology", "source", "currency"}
                and isinstance(candidate_references, list)
            ):
                incompatible = next(
                    (
                        reference
                        for reference in candidate_references
                        if isinstance(reference, str)
                        and public_reference_category(reference) != topic
                    ),
                    None,
                )
                if incompatible is not None:
                    raise _topic_mismatch_error(
                        f"changes[{index}].evidence_refs",
                        incompatible,
                        topic,
                        context,
                    )
            raise ExplanationValidationError(
                f"changes[{index}].topic",
                "doit appartenir aux topics de changement autorisés: "
                "performance, risk ou allocation; devise, période, méthode et "
                "sources sont des métadonnées communes",
            )
        message = _validate_nonempty_text(
            change["message"], f"changes[{index}].message"
        )
        model_texts.append((f"changes[{index}].message", message))
        references = _validate_string_list(
            change["evidence_refs"], f"changes[{index}].evidence_refs"
        )
        if not references:
            raise ExplanationValidationError(
                f"changes[{index}].evidence_refs",
                "doit référencer au moins une preuve",
            )
        for reference in references:
            resolution = resolve_evidence_reference(context, reference)
            if resolution["status"] != "resolved":
                raise _missing_reference_error(
                    f"changes[{index}].evidence_refs", reference, context
                )
            if not _reference_matches_topic(reference, topic):
                raise _topic_mismatch_error(
                    f"changes[{index}].evidence_refs", reference, topic, context
                )
        metrics = _validate_metric_citations(
            change["metrics"],
            path=f"changes[{index}].metrics",
            evidence_refs=references,
            context=context,
            topic=topic,
        )
        if _NUMBER_PATTERN.search(message) and not metrics:
            raise ExplanationValidationError(
                f"changes[{index}].metrics",
                "un message chiffré exige une métrique structurée",
                references,
            )
        all_references.extend(references)

    real_checks = {check["id"]: check for check in context.checks or []}
    model_checks: dict[str, str] = {}
    for index, assessment in enumerate(value["profile_assessment"]):
        expected_keys = {"check_id", "status", "message", "evidence_refs", "metrics"}
        if not isinstance(assessment, dict) or set(assessment) != expected_keys:
            raise ExplanationValidationError(
                f"profile_assessment[{index}]",
                "doit contenir exactement check_id, status, message, "
                "evidence_refs et metrics",
            )
        check_id = assessment["check_id"]
        status = assessment["status"]
        if not isinstance(check_id, str) or not isinstance(status, str):
            raise ExplanationValidationError(
                f"profile_assessment[{index}]",
                "check_id et status doivent être des textes",
            )
        message = _validate_nonempty_text(
            assessment["message"], f"profile_assessment[{index}].message"
        )
        model_texts.append((f"profile_assessment[{index}].message", message))
        if check_id in model_checks:
            raise ExplanationValidationError(
                f"profile_assessment[{index}].check_id",
                "un contrôle ne peut apparaître qu'une fois",
                list(real_checks.get(check_id, {}).get("evidence_refs", [])),
            )
        model_checks[check_id] = status
        references = _validate_string_list(
            assessment["evidence_refs"],
            f"profile_assessment[{index}].evidence_refs",
        )
        real_check = real_checks.get(check_id)
        if real_check is not None:
            allowed_references = set(real_check.get("evidence_refs", []))
            if not set(references).issubset(allowed_references):
                raise ExplanationValidationError(
                    f"profile_assessment[{index}].evidence_refs",
                    f"les preuves doivent provenir du contrôle réel {check_id}",
                    references,
                )
        metrics = _validate_metric_citations(
            assessment["metrics"],
            path=f"profile_assessment[{index}].metrics",
            evidence_refs=references,
            context=context,
        )
        if _NUMBER_PATTERN.search(message) and not metrics:
            raise ExplanationValidationError(
                f"profile_assessment[{index}].metrics",
                "un message chiffré exige une métrique structurée",
                references,
            )
        all_references.extend(references)

    expected_checks = {key: check["status"] for key, check in real_checks.items()}
    if model_checks != expected_checks:
        relevant_references = [
            reference
            for check in real_checks.values()
            for reference in check.get("evidence_refs", [])
        ]
        raise ExplanationValidationError(
            "profile_assessment",
            "les check_id et statuts doivent correspondre exactement aux contrôles exécutés",
            relevant_references,
        )
    for reference in dict.fromkeys(all_references):
        resolution = resolve_evidence_reference(context, reference)
        if resolution["status"] != "resolved":
            raise _missing_reference_error("evidence_refs", reference, context)
    _validate_model_language(model_texts)
    validated = deepcopy(value)
    for assessment in validated["profile_assessment"]:
        assessment["missing_information"] = deepcopy(
            real_checks[assessment["check_id"]].get("missing_information", [])
        )
    return validated


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


def _validation_failure(exc: Exception) -> ExplanationValidationError:
    if isinstance(exc, ExplanationValidationError):
        return exc
    if isinstance(exc, json.JSONDecodeError):
        return ExplanationValidationError(
            "$",
            f"JSON invalide à la ligne {exc.lineno}, colonne {exc.colno}",
        )
    return ExplanationValidationError("$", str(exc))


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
            "BEDROCK_MODEL_ID est absent; aucune explication AWS n'a été produite. "
            "Dans le même PowerShell que Streamlit, définissez "
            "$env:BEDROCK_MODEL_ID = \"us.anthropic.claude-opus-5-5\" puis "
            "relancez l'application (voir docs/aws_bedrock_diagnostic.md)."
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
    validation_failures: list[ExplanationValidationError] = []

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
            failure = _validation_failure(exc)
            validation_failures.append(failure)
            if repair_attempts < MAX_REPAIR_ATTEMPTS:
                repair_attempts += 1
                messages.append(
                    _correction_message(
                        context, failure.public_message("premier rejet")
                    )
                )
                continue
            stages = ["premier rejet", "rejet après réparation"]
            warnings.extend(
                item.public_message(
                    stages[index] if index < len(stages) else f"rejet {index + 1}"
                )
                for index, item in enumerate(validation_failures)
            )
            warnings.append(
                "L'explication Bedrock est restée invalide après une tentative "
                "de réparation; les calculs et contrôles sont conservés."
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
