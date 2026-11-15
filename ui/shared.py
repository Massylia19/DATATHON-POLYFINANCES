"""Configuration et utilitaires partagés par les pages Streamlit."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ASSETS_PATH = DATA_DIR / "market" / "assets_universe.csv"
CSS_PATH = ROOT / "styles" / "style.css"

THEMES = {
    "Sombre": {"page-bg": "#0B1F14", "page-glow": "#1D4A30", "surface-bg": "#12331F", "surface-bg-2": "#0E2818", "text-color": "#F2F7F3", "secondary-text": "#A8BDAF", "border-color": "#2C4B39", "accent": "#B7F05A", "button-bg": "#B7F05A", "button-text": "#0B1F14", "input-bg": "#0F2A1B"},
    "Clair": {"page-bg": "#F4F9E8", "page-glow": "#E3F2B8", "surface-bg": "#FFFFFF", "surface-bg-2": "#F1F7E0", "text-color": "#0B1F14", "secondary-text": "#4A5F52", "border-color": "#C9DBB0", "accent": "#2E7D32", "button-bg": "#123524", "button-text": "#DFFF00", "input-bg": "#FFFFFF"},
}


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def asset_weights(portfolio: dict) -> dict[str, float]:
    return {item["symbol"]: float(item["weight_pct"]) for item in portfolio["positions"]}


def request_key(persona_id: str, symbol: str, weight: float) -> dict:
    return {"persona_id": persona_id, "symbol": symbol, "target_weight_pct": float(weight)}


def select_persona(persona_id: str, scenarios: dict[str, dict]) -> None:
    scenario = scenarios[persona_id]
    st.session_state["selected_persona_id"] = persona_id
    st.session_state["selected_symbol"] = scenario["symbol"]
    st.session_state["target_weight"] = float(scenario["target_weight_pct"])
    st.session_state["_symbol_input"] = scenario["symbol"]
    st.session_state["_weight_input"] = float(scenario["target_weight_pct"])


def apply_intent_request(request: dict) -> None:
    st.session_state["selected_persona_id"] = request["persona_id"]
    st.session_state["selected_symbol"] = request["symbol"]
    st.session_state["target_weight"] = float(request["target_weight_pct"])
    st.session_state["_persona_selector"] = request["persona_id"]
    st.session_state["_symbol_input"] = request["symbol"]
    st.session_state["_weight_input"] = float(request["target_weight_pct"])
    st.session_state["pending_intent"] = request
