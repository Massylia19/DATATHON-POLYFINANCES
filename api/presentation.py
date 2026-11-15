"""Adaptateur de présentation neutre, sans dépendance Streamlit."""

from __future__ import annotations

from typing import Any

from alphaforge.presentation import (
    ASSET_CLASS_LABELS,
    CHECK_TITLE_LABELS,
    METRIC_PRESENTATION,
    STATUS_LABELS,
    build_main_summary,
    readable_label,
)


def presentation_metadata() -> dict[str, Any]:
    return {
        "metrics": METRIC_PRESENTATION,
        "statuses": STATUS_LABELS,
        "check_titles": CHECK_TITLE_LABELS,
        "asset_classes": ASSET_CLASS_LABELS,
    }


def enrich_analysis_response(response: dict[str, Any]) -> dict[str, Any]:
    analysis = response.get("analysis")
    if not isinstance(analysis, dict):
        return response
    symbol = analysis.get("scenario", {}).get("added_symbol", "")
    explanation = response.get("explanation")
    summary = build_main_summary(
        analysis,
        analysis.get("persona", {}),
        symbol,
        explanation if isinstance(explanation, dict) else None,
    )
    return {
        **response,
        "presentation": {
            "summary": summary,
            "metric_definitions": METRIC_PRESENTATION,
            "check_status_labels": STATUS_LABELS,
        },
    }


def asset_for_client(asset: dict[str, str]) -> dict[str, str]:
    return {
        **asset,
        "asset_class_label": readable_label(
            asset.get("asset_class", ""), ASSET_CLASS_LABELS
        ),
    }
