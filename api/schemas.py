"""Contrats HTTP stricts de l'API AlphaForge."""

from __future__ import annotations

import math
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

PersonaId = Literal["amira", "mateo", "robert"]
FiniteWeight = Annotated[float, Field(gt=0, lt=100)]


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
        if isinstance(value, bool) or not math.isfinite(value):
            raise ValueError("La pondération doit être un nombre fini.")
        return value


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
        if isinstance(value, bool) or not math.isfinite(value):
            raise ValueError("La pondération doit être un nombre fini.")
        return value


class ScenarioKey(StrictModel):
    persona_id: PersonaId
    symbol: str
    target_weight_pct: FiniteWeight


class InterpretRequest(StrictModel):
    text: str = Field(min_length=1, max_length=500)
    current_request: Optional[ScenarioKey] = None


class FollowUpRequest(StrictModel):
    analysis_id: str = Field(min_length=16, max_length=128)
    question: str = Field(min_length=1, max_length=500)
