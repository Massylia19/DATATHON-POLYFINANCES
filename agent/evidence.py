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
                "reference": "context.analysis.series",
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
