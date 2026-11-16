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


class CustomPortfolioRequest(StrictModel):
    """Schéma Pydantic pour une demande d'analyse de portefeuille personnalisé.

    Ce schéma valide les entrées de POST /api/custom-portfolio. Il s'assure que :
    1. Le persona_id est valide (amira, mateo, ou robert)
    2. Les poids totalisent exactement 100% (tolérance 1e-6)
    3. Chaque poids est entre 0 et 100, fini, et positif
    4. Les symboles sont des strings non vides (normalisés en UPPERCASE)
    5. Il y a entre 1 et 50 actifs (protection contre abus)

    SOURCES DE VALIDATION :
    -----------------------
    - persona_id : Validé par PersonaId (Literal["amira", "mateo", "robert"])
    - weights : Validé par validate_weights() (validator Pydantic)
    - Normalisation : Symboles convertis en UPPERCASE + strip()
    - Tolérance : math.isclose(total, 100.0, abs_tol=1e-6) pour gérer float rounding

    HYPOTHÈSES :
    ------------
    ⚠️ Les poids sont en POURCENTAGES (0-100), pas en décimales (0-1)
    ⚠️ Un poids de 0 est accepté (permet de retirer un actif)
    ⚠️ Les symboles ne sont PAS validés contre l'univers ici (délégué au backend)
    ⚠️ Pas de validation de diversification minimale (délégué au backend)

    LIMITES :
    ---------
    - Max 50 actifs : Protection contre portefeuilles aberrants (réaliste < 20)
    - Pas de validation de l'existence des symboles (backend le fait)
    - Pas de validation sémantique (ex: 100% sur un seul actif est accepté)

    Attributes:
        persona_id: Identifiant du persona ("amira", "mateo", ou "robert").
        weights: Dictionnaire {symbol: weight_pct} avec poids en pourcentages.
            - Clés : Symboles d'actifs (ex: "NVDA", "BTC-USD", "SHOP.TO")
            - Valeurs : Poids en % (ex: 15.0 pour 15%)
            - Contraintes : 1-50 actifs, poids totalisent 100%, chaque poids 0-100

    Examples:
        >>> # Valid request
        >>> request = CustomPortfolioRequest(
        ...     persona_id="amira",
        ...     weights={"SPY": 50.0, "QQQ": 30.0, "NVDA": 20.0}
        ... )

        >>> # Invalid: total !== 100%
        >>> request = CustomPortfolioRequest(
        ...     persona_id="mateo",
        ...     weights={"BTC-USD": 50.0, "ETH-USD": 40.0}  # Total 90%
        ... )
        # Raises: ValueError: Les poids doivent totaliser 100%, reçu 90.00%.

        >>> # Invalid: weight > 100%
        >>> request = CustomPortfolioRequest(
        ...     persona_id="robert",
        ...     weights={"AAPL": 150.0}  # Poids > 100%
        ... )
        # Raises: ValueError: Le poids de AAPL doit être entre 0 et 100.
    """
    persona_id: PersonaId
    weights: dict[str, float] = Field(
        min_length=1,
        max_length=50,
        description="Dictionnaire {symbol: weight_pct} des poids du portefeuille personnalisé"
    )

    @field_validator("weights")
    @classmethod
    def validate_weights(cls, values: dict[str, float]) -> dict[str, float]:
        """Valide et normalise les poids du portefeuille personnalisé.

        VALIDATION EFFECTUÉE :
        ----------------------
        1. **Symboles valides** :
           - Doivent être des strings non vides
           - Normalisés en UPPERCASE (ex: "nvda" → "NVDA")
           - Whitespace supprimé (ex: " AAPL " → "AAPL")

        2. **Poids valides** :
           - Doivent être des nombres finis (pas NaN, pas Inf)
           - Doivent être entre 0 et 100 (pourcentages)
           - Un poids de 0 est accepté (permet de retirer un actif)

        3. **Total = 100%** :
           - Somme des poids doit égaler 100.0
           - Tolérance : 1e-6 (pour gérer les erreurs de float rounding)
           - Exemple OK : 99.999999 accepté, 99.99 rejeté

        HYPOTHÈSES :
        ------------
        ⚠️ Les poids sont en POURCENTAGES (15.0 = 15%), pas décimales (0.15)
        ⚠️ Les symboles ne sont PAS validés contre l'univers d'actifs ici
           (c'est le rôle de agent.service.analyze_custom_portfolio())
        ⚠️ Pas de validation de diversification, liquidité, ou pertinence

        LIMITES :
        ---------
        - Pas de check d'existence du symbole dans market data
        - Pas de validation de la pertinence économique (100% sur un actif OK)
        - Pas de contraintes de diversification minimale

        Args:
            values: Dictionnaire brut {symbol: weight} de l'utilisateur.

        Returns:
            Dictionnaire normalisé avec symboles en UPPERCASE.

        Raises:
            ValueError: Si validation échoue (message explicite en français).

        Examples:
            >>> # Normalisation symboles
            >>> cls.validate_weights({"nvda": 50.0, " aapl ": 50.0})
            {"NVDA": 50.0, "AAPL": 50.0}

            >>> # Erreur : poids négatif
            >>> cls.validate_weights({"SPY": -10.0, "QQQ": 110.0})
            # Raises: ValueError: Le poids de SPY doit être entre 0 et 100.

            >>> # Erreur : total ≠ 100%
            >>> cls.validate_weights({"BTC-USD": 95.0})
            # Raises: ValueError: Les poids doivent totaliser 100%, reçu 95.00%.
        """
        # Valider et normaliser chaque paire (symbol, weight)
        normalized = {}
        for symbol, weight in values.items():
            # Validation symbole : doit être string non vide
            if not isinstance(symbol, str) or not symbol.strip():
                raise ValueError("Les symboles doivent être des textes non vides.")

            # Normalisation : UPPERCASE + strip whitespace
            normalized_symbol = symbol.strip().upper()

            # Validation poids : entre 0 et 100
            if weight < 0 or weight > 100:
                raise ValueError(f"Le poids de {normalized_symbol} doit être entre 0 et 100.")

            # Validation poids : doit être fini (pas NaN, pas Inf)
            if not math.isfinite(weight):
                raise ValueError(f"Le poids de {normalized_symbol} doit être fini.")

            normalized[normalized_symbol] = weight

        # Validation totale : somme des poids = 100%
        # Tolérance 1e-6 pour gérer les erreurs de float rounding
        # Exemple : 33.33 + 33.33 + 33.34 = 100.0 (OK)
        total = sum(normalized.values())
        if not math.isclose(total, 100.0, abs_tol=1e-6):
            raise ValueError(f"Les poids doivent totaliser 100%, reçu {total:.2f}%.")

        return normalized
