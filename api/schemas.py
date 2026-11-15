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


class ChatMessage(StrictModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)

    @field_validator("content")
    @classmethod
    def nonempty_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Le message ne peut pas être vide.")
        return value.strip()


class ChatRequest(StrictModel):
    persona_id: PersonaId
    question: str = Field(min_length=1, max_length=2000)
    analysis_id: Optional[str] = Field(default=None, min_length=16, max_length=128)
    history: list[ChatMessage] = Field(default_factory=list, max_length=10)

    @field_validator("question")
    @classmethod
    def nonempty_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("La question ne peut pas être vide.")
        return value.strip()


class EvidenceRequest(StrictModel):
    analysis_id: str = Field(min_length=16, max_length=128)
    references: list[str] = Field(min_length=1, max_length=100)

    @field_validator("references")
    @classmethod
    def public_references_only(cls, values: list[str]) -> list[str]:
        if any(not value.startswith(("analysis.", "source.")) for value in values):
            raise ValueError("Seules les preuves publiques peuvent être consultées.")
        return list(dict.fromkeys(values))
