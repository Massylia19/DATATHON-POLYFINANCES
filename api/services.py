"""Adaptation des services métier existants pour HTTP."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from agent.service import (
    analyze_comparison,
    analyze_request,
    answer_follow_up,
    interpret_scenario_request,
)
from alphaforge.engine import load_asset_universe

from .presentation import asset_for_client, enrich_analysis_response, presentation_metadata

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
