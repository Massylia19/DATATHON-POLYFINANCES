"""Contrats HTTP stricts de l'API AlphaForge."""

from __future__ import annotations

import math
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

PersonaId = Literal["amira", "mateo", "robert"]
FiniteWeight = Annotated[float, Field(ge=1, le=50)]


def _validate_ui_weight(value: float) -> float:
    if isinstance(value, bool) or not math.isfinite(value):
        raise ValueError("La pondération doit être un nombre fini.")
    if not math.isclose((value - 1) * 2, round((value - 1) * 2), abs_tol=1e-9):
        raise ValueError("La pondération doit avancer par pas de 0,5 %.")
    return value


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class AnalysisRequest(StrictModel):
    persona_id: PersonaId
    symbol: str = Field(min_length=1, max_length=32)
    target_weight_pct: FiniteWeight

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        symbol = value.strip().upper()
        if not symbol:
            raise ValueError("Le symbole est requis.")
        return symbol

    @field_validator("target_weight_pct")
    @classmethod
    def finite_weight(cls, value: float) -> float:
        return _validate_ui_weight(value)


class ComparisonRequest(StrictModel):
    persona_id: PersonaId
    symbol: str = Field(min_length=1, max_length=32)
    weight_a_pct: FiniteWeight
    weight_b_pct: FiniteWeight

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("weight_a_pct", "weight_b_pct")
    @classmethod
    def finite_weights(cls, value: float) -> float:
        return _validate_ui_weight(value)


class ScenarioKey(StrictModel):
    persona_id: PersonaId
    symbol: str = Field(min_length=1, max_length=32)
    target_weight_pct: FiniteWeight

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        symbol = value.strip().upper()
        if not symbol:
            raise ValueError("Le symbole est requis.")
        return symbol

    @field_validator("target_weight_pct")
    @classmethod
    def valid_scenario_weight(cls, value: float) -> float:
        return _validate_ui_weight(value)


class InterpretRequest(StrictModel):
    # Le service métier retourne une clarification lisible pour une chaîne vide.
    # On conserve seulement la limite de sécurité au niveau HTTP.
    text: str = Field(max_length=500)
    current_request: Optional[ScenarioKey] = None


class FollowUpRequest(StrictModel):
    analysis_id: str = Field(min_length=16, max_length=128)
    question: str = Field(min_length=1, max_length=500)


class EvidenceRequest(StrictModel):
    analysis_id: str = Field(min_length=16, max_length=128)
    references: list[str] = Field(min_length=1, max_length=100)

    @field_validator("references")
    @classmethod
    def public_references_only(cls, values: list[str]) -> list[str]:
        if any(not value.startswith(("analysis.", "source.")) for value in values):
            raise ValueError("Seules les preuves publiques peuvent être consultées.")
        return list(dict.fromkeys(values))


class CustomPortfolioRequest(StrictModel):
    persona_id: PersonaId
    weights: dict[str, float] = Field(min_length=1, max_length=50)

    @field_validator("weights")
    @classmethod
    def validate_weights(cls, values: dict[str, float]) -> dict[str, float]:
        # Valider que les symboles sont valides
        normalized = {}
        for symbol, weight in values.items():
            if not isinstance(symbol, str) or not symbol.strip():
                raise ValueError("Les symboles doivent être des textes non vides.")
            normalized_symbol = symbol.strip().upper()
            if weight < 0 or weight > 100:
                raise ValueError(f"Le poids de {normalized_symbol} doit être entre 0 et 100.")
            if not math.isfinite(weight):
                raise ValueError(f"Le poids de {normalized_symbol} doit être fini.")
            normalized[normalized_symbol] = weight

        # Valider que le total est proche de 100%
        total = sum(normalized.values())
        if not math.isclose(total, 100.0, abs_tol=1e-6):
            raise ValueError(f"Les poids doivent totaliser 100%, reçu {total:.2f}%.")

        return normalized
