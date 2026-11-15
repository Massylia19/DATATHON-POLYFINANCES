"""Adaptation des services métier existants pour HTTP."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from agent.context import create_request_context
from agent.evidence import build_public_evidence_catalog, resolve_evidence_reference
from agent.service import (
    analyze_comparison,
    analyze_request,
    answer_follow_up,
    chat_with_persona,
    interpret_scenario_request,
)
from alphaforge.engine import load_asset_universe
from alphaforge.presentation import format_date_fr

from .presentation import (
    asset_for_client,
    enrich_analysis_response,
    presentation_metadata,
)

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


def _json(name: str) -> Any:
    with (DATA_DIR / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def bootstrap() -> dict[str, Any]:
    assets = load_asset_universe(DATA_DIR / "market" / "assets_universe.csv")
    return {
        "personas": _json("personas.json")["personas"],
        "portfolios": _json("portfolios.json")["portfolios"],
        "scenarios": _json("scenarios.json")["scenarios"],
        "assets": [asset_for_client({"ticker": symbol, **asset}) for symbol, asset in assets.items()],
        "presentation": presentation_metadata(),
    }


def run_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    return enrich_analysis_response(analyze_request(root=ROOT, **payload))


def run_comparison(payload: dict[str, Any]) -> dict[str, Any]:
    result = analyze_comparison(root=ROOT, **payload)
    if isinstance(result.get("variants"), list):
        weights = (payload["weight_a_pct"], payload["weight_b_pct"])
        result["variants"] = [
            {
                **enrich_analysis_response(variant),
                "request": {
                    "persona_id": payload["persona_id"],
                    "symbol": payload["symbol"],
                    "target_weight_pct": weights[index],
                },
            }
            for index, variant in enumerate(result["variants"])
        ]
    return result


def interpret(payload: dict[str, Any]) -> dict[str, Any]:
    return interpret_scenario_request(root=ROOT, **payload)


def follow_up(
    question: str, response: dict[str, Any], request: dict[str, Any]
) -> dict[str, Any]:
    return answer_follow_up(question, response, request, root=ROOT)


def chat(
    persona_id: str,
    question: str,
    history: list[dict[str, str]],
    analysis_response: dict[str, Any] | None = None,
) -> str:
    personas = _json("personas.json")["personas"]
    portfolios = _json("portfolios.json")["portfolios"]
    persona = next((item for item in personas if item["id"] == persona_id), None)
    portfolio = next(
        (item for item in portfolios if item["persona_id"] == persona_id), None
    )
    if persona is None or portfolio is None:
        raise ValueError("Le profil ou son portefeuille est introuvable.")
    return chat_with_persona(
        question,
        persona,
        portfolio,
        analysis_response=analysis_response,
        history=history,
    )


_METRIC_EVIDENCE_LABELS = {
    "total_return": "Gain historique",
    "annualized_volatility": "Ampleur des fluctuations",
    "max_drawdown": "Plus forte baisse observée",
}


def _evidence_label(reference: str, assets: dict[str, dict[str, str]]) -> str:
    if reference.startswith("source."):
        return "Source de données"
    parts = reference.split(".")
    if len(parts) == 4 and parts[0] == "analysis" and parts[2] == "metrics":
        metric_label = _METRIC_EVIDENCE_LABELS.get(parts[3])
        if metric_label and parts[1] in {"before", "after"}:
            side = "avant" if parts[1] == "before" else "après"
            return f"{metric_label} — portefeuille {side}"
    if len(parts) == 4 and parts[0] == "analysis" and parts[2] == "weights_by_asset_pct":
        symbol = parts[3]
        side = "initiale" if parts[1] == "before" else "après l’ajout"
        asset_name = assets.get(symbol, {}).get("name", symbol)
        return f"Pondération de {asset_name} — {side}"
    labels = {
        "analysis.period.start": "Début de la période étudiée",
        "analysis.period.end": "Fin de la période étudiée",
        "analysis.period.common_observations": "Nombre de dates communes",
        "analysis.scenario.added_symbol": "Placement ajouté",
        "analysis.scenario.target_weight_pct": "Part attribuée au nouvel actif",
        "analysis.currency": "Devise des résultats",
    }
    return labels.get(reference, "Élément vérifié dans la simulation")


def _evidence_value(
    value: Any, unit: str, assets: dict[str, dict[str, str]]
) -> str:
    if unit == "decimal_ratio" and isinstance(value, (int, float)):
        return f"{value * 100:,.2f} %".replace(",", " ").replace(".", ",")
    if unit == "percentage" and isinstance(value, (int, float)):
        return f"{value:,.2f} %".replace(",", " ").replace(".", ",")
    if unit == "iso_date" and isinstance(value, str):
        return format_date_fr(value)
    if unit == "count" and isinstance(value, (int, float)):
        return str(int(value))
    if unit == "currency_code" and value == "CAD":
        return "Dollars canadiens (CAD)"
    if unit == "percentage_map" and isinstance(value, dict):
        labels = []
        for symbol, weight in value.items():
            if isinstance(weight, (int, float)):
                asset_name = assets.get(symbol, {}).get("name", symbol)
                labels.append(
                    f"{asset_name} : {weight:,.1f} %"
                    .replace(",", " ")
                    .replace(".", ",")
                )
        return " · ".join(labels)
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "Oui" if value else "Non"
    if isinstance(value, dict):
        return "Donnée structurée vérifiée dans le détail technique."
    if isinstance(value, list):
        return f"{len(value)} élément(s) vérifié(s)."
    return str(value)


def resolve_public_evidence(
    response: dict[str, Any],
    request: dict[str, Any],
    references: list[str],
) -> list[dict[str, Any]]:
    """Résout uniquement les preuves présentes dans l'analyse stockée."""
    context = create_request_context(
        request["persona_id"],
        request["symbol"],
        request["target_weight_pct"],
        root=ROOT,
    )
    context.analysis = response.get("analysis")
    context.checks = response.get("checks")
    catalog = {
        item["reference"]: item
        for item in build_public_evidence_catalog(context)
    }
    allowed = set(catalog)
    if not set(references).issubset(allowed):
        raise ValueError("Une preuve demandée ne correspond pas à cette analyse.")
    assets = load_asset_universe(DATA_DIR / "market" / "assets_universe.csv")
    items = []
    for reference in dict.fromkeys(references):
        resolved = resolve_evidence_reference(context, reference)
        if resolved.get("status") != "resolved":
            raise ValueError("Une preuve demandée n’est plus disponible.")
        value = resolved["value"]
        if reference.startswith("source.") and isinstance(value, dict):
            source_id = reference.removeprefix("source.")
            source_names = {
                "src_prices_daily": ("Yahoo Finance", "Historique des prix"),
                "src_fx_usdcad": ("Banque du Canada", "Taux de change"),
                "src_assets_universe": ("AlphaForge", "Univers des placements"),
            }
            provider, role = source_names.get(
                source_id, (str(value.get("source", "Source")), "Donnée de référence")
            )
            items.append(
                {
                    "label": str(value.get("source", provider)),
                    "value": str(value.get("file", "Document source")),
                    "source": provider,
                    "role": role,
                    "date": value.get("retrieved_on"),
                    "url": (
                        value.get("source_url")
                        if str(value.get("source_url", "")).startswith("https://")
                        else None
                    ),
                }
            )
            continue
        unit = catalog[reference]["unit"]
        items.append(
            {
                "label": _evidence_label(reference, assets),
                "value": _evidence_value(value, unit, assets),
                "source": "Moteur de simulation AlphaForge",
            }
        )
    return items
