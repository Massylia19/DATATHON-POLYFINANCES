"""État isolé d'une future requête agent AlphaForge."""

from __future__ import annotations

import math
import numbers
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from alphaforge.engine import (
    EngineError,
    PROJECT_ROOT,
    load_asset_universe,
    load_persona_and_portfolio,
)


@dataclass(frozen=True)
class RequestSpec:
    persona_id: str
    symbol: str
    target_weight_pct: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "persona_id": self.persona_id,
            "symbol": self.symbol,
            "target_weight_pct": self.target_weight_pct,
        }


@dataclass
class RequestContext:
    """Conserve uniquement l'état d'une demande; aucune instance n'est globale."""

    request: RequestSpec
    root: Path
    profile: dict[str, Any]
    analysis: dict[str, Any] | None = None
    checks: list[dict[str, Any]] | None = None
    tool_trace: list[dict[str, Any]] = field(default_factory=list)


def _normalize_request(
    persona_id: Any,
    symbol: Any,
    target_weight_pct: Any,
) -> RequestSpec:
    if not isinstance(persona_id, str) or not persona_id.strip():
        raise EngineError("INVALID_PERSONA", "Le persona doit être un texte non vide")
    if not isinstance(symbol, str) or not symbol.strip():
        raise EngineError("UNKNOWN_SYMBOL", "Le symbole doit être un texte non vide")
    if isinstance(target_weight_pct, bool) or not isinstance(
        target_weight_pct, numbers.Real
    ):
        raise EngineError("INVALID_WEIGHT", "Le poids cible doit être un nombre")

    weight = float(target_weight_pct)
    if not math.isfinite(weight) or not 0 < weight < 100:
        raise EngineError(
            "INVALID_WEIGHT",
            "Le poids cible doit être fini et strictement entre 0 et 100",
        )
    return RequestSpec(
        persona_id=persona_id.strip().lower(),
        symbol=symbol.strip().upper(),
        target_weight_pct=weight,
    )


def create_request_context(
    persona_id: str,
    symbol: str,
    target_weight_pct: float,
    *,
    root: Path = PROJECT_ROOT,
) -> RequestContext:
    """Valide et fige la demande initiale sans lancer la simulation."""
    root = Path(root).resolve()
    request = _normalize_request(persona_id, symbol, target_weight_pct)
    profile, portfolio = load_persona_and_portfolio(root / "data", request.persona_id)
    assets = load_asset_universe(root / "data" / "market" / "assets_universe.csv")
    if request.symbol not in assets:
        raise EngineError(
            "UNKNOWN_SYMBOL", f"Cet actif est absent du jeu de données: {request.symbol}"
        )
    held_symbols = {position["symbol"] for position in portfolio["positions"]}
    if request.symbol in held_symbols:
        raise EngineError(
            "ASSET_ALREADY_HELD",
            f"L'actif du scénario existe déjà: {request.symbol}",
        )
    return RequestContext(request=request, root=root, profile=profile)
