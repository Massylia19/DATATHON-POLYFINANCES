"""Résolution locale des preuves utilisées par les futurs messages Converse."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from agent.context import RequestContext


def _resolve_path(value: Any, path: list[str]) -> tuple[bool, Any]:
    current = value
    index = 0
    while index < len(path):
        if not isinstance(current, dict):
            return False, None
        part = path[index]
        if part in current:
            current = current[part]
            index += 1
            continue
        dotted_key = ".".join(path[index:])
        if dotted_key in current:
            return True, current[dotted_key]
        return False, None
    return True, current


def _source_index(context: RequestContext) -> dict[str, dict[str, Any]]:
    sources = {
        source["id"]: source
        for source in (context.analysis or {}).get("sources", [])
        if source.get("id")
    }
    evidence_path = context.root / "data" / "esg_evidence.json"
    if evidence_path.exists():
        with evidence_path.open(encoding="utf-8") as handle:
            esg_data = json.load(handle)
        for items in esg_data.values():
            for source in items:
                if source.get("id"):
                    sources[source["id"]] = source
    return sources


def resolve_evidence_reference(
    context: RequestContext, reference: str
) -> dict[str, Any]:
    """Résout une référence existante sans fabriquer de valeur absente."""
    if not isinstance(reference, str) or not reference:
        return {
            "reference": reference,
            "status": "missing",
            "reason": "Référence vide ou mal formée.",
        }
    if reference.startswith("analysis."):
        if context.analysis is None:
            return {
                "reference": reference,
                "status": "missing",
                "reason": "Aucune analyse réussie n'est disponible.",
            }
        found, value = _resolve_path(context.analysis, reference.split(".")[1:])
        if found:
            return {"reference": reference, "status": "resolved", "value": value}
    elif reference.startswith("source."):
        source_id = reference.removeprefix("source.")
        source = _source_index(context).get(source_id)
        if source is not None:
            return {
                "reference": reference,
                "status": "resolved",
                "value": source,
            }
    return {
        "reference": reference,
        "status": "missing",
        "reason": "La référence ne correspond à aucune analyse ou source connue.",
    }


def public_reference_unit(reference: str, value: Any) -> str:
    """Retourne l'unité publique associée à une preuve déjà résolue."""
    if reference.startswith("source."):
        return "source_record"
    if isinstance(value, (dict, list)):
        if ".weights_by_" in reference:
            return "percentage_map"
        return "structured_data"
    if ".metrics." in reference:
        return "decimal_ratio"
    if ".weights_by_" in reference or reference.endswith("target_weight_pct"):
        return "percentage"
    if reference.endswith("common_observations"):
        return "count"
    if reference.endswith((".start", ".end")) and "analysis.period." in reference:
        return "iso_date"
    if reference.endswith(".currency"):
        return "currency_code"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "text"
    return "structured_data"


def public_reference_category(reference: str) -> str:
    """Classe une preuve publique selon son usage sémantique autorisé."""
    if reference == "analysis.currency":
        return "currency"
    if reference.startswith("analysis.period."):
        return "period"
    if reference.startswith(("analysis.methodology", "analysis.limitations")):
        return "methodology"
    if ".metrics.total_return" in reference:
        return "performance"
    if any(
        fragment in reference
        for fragment in (
            ".metrics.annualized_volatility",
            ".metrics.max_drawdown",
        )
    ):
        return "risk"
    if ".weights_by_" in reference or reference.startswith("analysis.scenario."):
        return "allocation"
    if reference.startswith("source."):
        return "source"
    return "metadata"


def _public_reference_candidates(context: RequestContext) -> list[str]:
    analysis = context.analysis or {}
    references: list[str] = []
    for section in ("before", "after", "delta_after_minus_before"):
        section_value = analysis.get(section, {})
        for group in ("metrics", "weights_by_asset_pct", "weights_by_class_pct"):
            for key in section_value.get(group, {}):
                references.append(f"analysis.{section}.{group}.{key}")
    for key in analysis.get("scenario", {}):
        references.append(f"analysis.scenario.{key}")
    for key in analysis.get("period", {}):
        references.append(f"analysis.period.{key}")
    if "currency" in analysis:
        references.append("analysis.currency")
    for key in ("methodology", "limitations"):
        if key in analysis:
            references.append(f"analysis.{key}")
    for check in context.checks or []:
        references.extend(check.get("evidence_refs", []))
    source_ids = _source_index(context)
    references.extend(f"source.{source_id}" for source_id in source_ids)
    return list(dict.fromkeys(references))


def build_public_evidence_catalog(context: RequestContext) -> list[dict[str, Any]]:
    """Catalogue concis des seules références publiques réellement résolues."""
    catalog = []
    for reference in _public_reference_candidates(context):
        resolution = resolve_evidence_reference(context, reference)
        if resolution["status"] != "resolved":
            continue
        value = resolution["value"]
        catalog.append(
            {
                "reference": reference,
                "value": deepcopy(value),
                "unit": public_reference_unit(reference, value),
                "category": public_reference_category(reference),
            }
        )
    return catalog


def _example_explanation(context: RequestContext) -> dict[str, Any] | None:
    """Exemple valide construit avec les données réelles de la demande."""
    if context.analysis is None or context.checks is None:
        return None
    before_ref = "analysis.before.metrics.total_return"
    after_ref = "analysis.after.metrics.total_return"
    before = resolve_evidence_reference(context, before_ref)
    after = resolve_evidence_reference(context, after_ref)
    if before["status"] != "resolved" or after["status"] != "resolved":
        return None
    missing = list(
        dict.fromkeys(
            item
            for check in context.checks
            for item in check.get("missing_information", [])
        )
    )
    return {
        "summary": (
            "Cette simulation compare le portefeuille avant et après l’ajout. "
            "Elle met en évidence les changements historiques et les limites "
            "importantes pour interpréter le résultat."
        ),
        "changes": [
            {
                "topic": "performance",
                "message": "Le rendement total historique est comparé avant et après.",
                "evidence_refs": [before_ref, after_ref],
                "metrics": [
                    {
                        "evidence_ref": before_ref,
                        "value": before["value"],
                        "unit": public_reference_unit(before_ref, before["value"]),
                    },
                    {
                        "evidence_ref": after_ref,
                        "value": after["value"],
                        "unit": public_reference_unit(after_ref, after["value"]),
                    },
                ],
            }
        ],
        "profile_assessment": [
            {
                "check_id": check["id"],
                "status": check["status"],
                "message": "Ce statut provient du contrôle déterministe exécuté.",
                "evidence_refs": deepcopy(check.get("evidence_refs", [])),
                "metrics": [],
            }
            for check in context.checks
        ],
        "uncertainties": [
            f"Information manquante: {item}." for item in missing
        ],
        "evidence_refs": [before_ref, after_ref],
    }


def build_evidence_bundle(context: RequestContext) -> dict[str, Any]:
    """Prépare le contexte concis destiné au modèle, sans longues séries."""
    analysis = deepcopy(context.analysis)
    if analysis is None:
        analysis_for_model = None
        series_summary = None
    else:
        series = analysis.pop("series", None)
        analysis_for_model = analysis
        series_summary = None
        if series and series.get("dates"):
            series_summary = {
                "observations": len(series["dates"]),
                "start": series["dates"][0],
                "end": series["dates"][-1],
                "before_start": series["before"][0],
                "before_end": series["before"][-1],
                "after_start": series["after"][0],
                "after_end": series["after"][-1],
            }

    references = []
    for check in context.checks or []:
        references.extend(check.get("evidence_refs", []))
    unique_references = list(dict.fromkeys(references))
    resolved = [
        resolve_evidence_reference(context, reference)
        for reference in unique_references
    ]
    source_index = _source_index(context) if context.analysis else {}
    referenced_source_ids = {
        reference.removeprefix("source.")
        for reference in unique_references
        if reference.startswith("source.")
    }
    return {
        "request": context.request.as_dict(),
        "analysis": analysis_for_model,
        "series_summary": series_summary,
        "checks": deepcopy(context.checks),
        "public_reference_policy": {
            "allowed_prefixes": ["analysis.", "source."],
            "forbidden_prefixes": ["context."],
            "metric_membership_rule": (
                "Chaque metrics[].evidence_ref doit aussi figurer dans "
                "evidence_refs du même constat."
            ),
            "changes_purpose": (
                "Réserver changes aux différences avant/après de performance, "
                "risque ou allocation."
            ),
            "metadata_usage": (
                "La devise, la période et la méthode sont des métadonnées "
                "communes à mentionner dans le résumé ou les incertitudes; elles "
                "ne constituent pas un changement causé par l'actif ajouté."
            ),
        },
        "public_evidence_catalog": build_public_evidence_catalog(context),
        "example_explanation": _example_explanation(context),
        "resolved_evidence": resolved,
        "referenced_esg_sources": [
            source_index[source_id]
            for source_id in referenced_source_ids
            if source_id in source_index
        ],
    }


def build_interface_payload(context: RequestContext) -> dict[str, Any]:
    """Retourne les données complètes pour l'application, séries comprises."""
    return {
        "request": context.request.as_dict(),
        "analysis": deepcopy(context.analysis),
        "checks": deepcopy(context.checks),
        "tool_trace": deepcopy(context.tool_trace),
    }
