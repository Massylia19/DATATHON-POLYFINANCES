"""Application FastAPI AlphaForge."""

from __future__ import annotations

import os
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .analysis_store import AnalysisStore
from .schemas import (
    AnalysisRequest,
    ChatRequest,
    ComparisonRequest,
    CustomPortfolioRequest,
    EvidenceRequest,
    FollowUpRequest,
    InterpretRequest,
)
from .services import (
    bootstrap,
    chat,
    follow_up,
    interpret,
    resolve_public_evidence,
    run_analysis,
    run_comparison,
    run_custom_portfolio,
)
from scripts.aws_support import explain_aws_error

app = FastAPI(title="AlphaForge API", version="1.0.0")
_default_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
_configured_origins = [
    origin.strip().rstrip("/")
    for origin in os.environ.get("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_configured_origins or _default_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
store = AnalysisStore()


def _http_status(result: dict[str, Any]) -> int:
    code = result.get("error", {}).get("code")
    if code in {"INVALID_PERSONA", "UNKNOWN_SYMBOL", "INVALID_WEIGHT", "ASSET_ALREADY_HELD", "IDENTICAL_VARIANTS", "INVALID_COMPARISON"}:
        return 400
    if code in {"INSUFFICIENT_DATA", "INCOMPARABLE_PERIODS"}:
        return 422
    return 500


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "alphaforge-api", "bedrock": "not_checked"}


@app.get("/api/bootstrap")
def get_bootstrap() -> dict[str, Any]:
    return bootstrap()


@app.post("/api/analyses")
def create_analysis(payload: AnalysisRequest) -> dict[str, Any]:
    request = payload.model_dump()
    result = run_analysis(request)
    if result.get("status") == "error":
        raise HTTPException(status_code=_http_status(result), detail=result["error"])
    analysis_id = store.put(result, request)
    return {**result, "analysis_id": analysis_id, "request": request}


@app.post("/api/comparisons")
def create_comparison(payload: ComparisonRequest) -> dict[str, Any]:
    result = run_comparison(payload.model_dump())
    if result.get("status") == "error":
        raise HTTPException(status_code=_http_status(result), detail=result["error"])
    return result


@app.post("/api/custom-portfolio")
def create_custom_portfolio_analysis(payload: CustomPortfolioRequest) -> dict[str, Any]:
    """Endpoint FastAPI pour analyser un portefeuille personnalisé avec modifications multiples.

    POST /api/custom-portfolio
    -------------------------
    Permet à l'utilisateur de soumettre un portefeuille personnalisé complet
    (avec ajouts, retraits, et modifications de poids) et d'obtenir une analyse
    comparative détaillée entre le portefeuille initial du persona et le portefeuille
    personnalisé.

    ARCHITECTURE :
    --------------
    ┌─────────────────────────────────────────────────────────────────────────┐
    │ 1. Validation (Pydantic)                                                 │
    │    → CustomPortfolioRequest valide persona_id, weights                   │
    │    → Normalise symboles (UPPERCASE), vérifie total = 100%                │
    └─────────────────────────────────────────────────────────────────────────┘
                                  ↓
    ┌─────────────────────────────────────────────────────────────────────────┐
    │ 2. Orchestration (api/services.py::run_custom_portfolio)                │
    │    → Mappe persona_id + weights vers analyze_custom_portfolio()          │
    └─────────────────────────────────────────────────────────────────────────┘
                                  ↓
    ┌─────────────────────────────────────────────────────────────────────────┐
    │ 3. Backend Logic (agent/service.py::analyze_custom_portfolio)           │
    │    → Charge données (personas, portfolios, market)                       │
    │    → Simule AVANT (portefeuille initial)                                 │
    │    → Simule APRÈS (portefeuille personnalisé)                            │
    │    → Calcule métriques (rendement, volatilité, drawdown)                 │
    │    → Retourne analyse structurée                                         │
    └─────────────────────────────────────────────────────────────────────────┘
                                  ↓
    ┌─────────────────────────────────────────────────────────────────────────┐
    │ 4. Response Handling (api/main.py::create_custom_portfolio_analysis)    │
    │    → Si status = "error" : HTTPException avec status code approprié     │
    │    → Si status = "success" : Retourne JSON complet                       │
    └─────────────────────────────────────────────────────────────────────────┘

    SOURCES :
    ---------
    - Validation : api/schemas.py::CustomPortfolioRequest
    - Service : api/services.py::run_custom_portfolio()
    - Backend : agent/service.py::analyze_custom_portfolio()
    - Données : data/personas.json, data/portfolios.json, data/market/

    HYPOTHÈSES :
    ------------
    ⚠️ Les poids sont en POURCENTAGES (15.0 = 15%), pas décimales
    ⚠️ Le backend fait la vérification d'existence des symboles dans market data
    ⚠️ Toutes les hypothèses de analyze_custom_portfolio() s'appliquent :
       - Buy-and-hold strict (pas de rééquilibrage)
       - Historique ≠ futur (pas de prévision)
       - Coûts de transaction exclus
       - Biais du survivant
       - Voir docstring de analyze_custom_portfolio() pour détails complets

    LIMITES :
    ---------
    - Pas d'authentification (endpoint ouvert, localhost only)
    - Pas de rate limiting (protection DoS à ajouter en prod)
    - Synchrone (blocking, 2-5s de calcul) → considérer async ou task queue
    - Pas de cache (chaque requête recalcule tout)
    - Pas de webhook/streaming (utilisateur attend la réponse complète)

    VALIDATION :
    ------------
    ✅ Validation Pydantic automatique (400 Bad Request si échoue)
    ✅ Validation backend (symboles, données) → 400 ou 500 si échoue
    ✅ CORS configuré (autorise localhost:5173 en dev)

    CODES DE STATUT HTTP :
    ----------------------
    200 OK : Analyse réussie (status="success")
    400 Bad Request : Validation échouée (Pydantic ou backend)
        - Exemples : total ≠ 100%, symbole invalide, persona inconnu
    500 Internal Server Error : Erreur interne backend
        - Exemples : données corrompues, calcul échoué

    Args:
        payload: CustomPortfolioRequest validé par Pydantic.
            - persona_id : "amira" | "mateo" | "robert"
            - weights : dict[str, float] avec poids en %

    Returns:
        dict avec structure suivante :

        **Succès (status="success")** :
        {
            "status": "success",
            "before": {
                "weights_by_asset_pct": {...},
                "metrics": {
                    "total_return": 0.523,
                    "annualized_volatility": 0.18,
                    "max_drawdown": -0.25
                }
            },
            "after": { ... },  # Même structure
            "delta_after_minus_before": { ... },  # Différences
            "series": {
                "dates": ["2021-11-12", ...],
                "before": [100.0, 101.2, ...],
                "after": [100.0, 102.5, ...]
            },
            "period": {
                "start": "2021-11-12",
                "end": "2024-12-09",
                "common_observations": 756
            }
        }

    Raises:
        HTTPException: Si status = "error" (400 ou 500 selon code d'erreur).

    Examples:
        >>> # curl example
        >>> curl -X POST http://localhost:8000/api/custom-portfolio \\
        ...   -H "Content-Type: application/json" \\
        ...   -d '{
        ...     "persona_id": "amira",
        ...     "weights": {
        ...       "SPY": 30.0,
        ...       "QQQ": 25.0,
        ...       "SHOP.TO": 15.0,
        ...       "BTC-USD": 10.0,
        ...       "NVDA": 20.0
        ...     }
        ...   }'

        >>> # Python requests example
        >>> import requests
        >>> response = requests.post(
        ...     "http://localhost:8000/api/custom-portfolio",
        ...     json={
        ...         "persona_id": "mateo",
        ...         "weights": {"AAPL": 50.0, "GOOGL": 30.0, "MSFT": 20.0}
        ...     }
        ... )
        >>> if response.status_code == 200:
        ...     result = response.json()
        ...     print(result["after"]["metrics"]["total_return"])

    See Also:
        - api/schemas.py::CustomPortfolioRequest : Schéma de validation
        - api/services.py::run_custom_portfolio : Orchestration
        - agent/service.py::analyze_custom_portfolio : Backend logic
        - tests/test_custom_portfolio.py : Tests backend (40+ cas)
    """
    # Orchestration : Délègue à run_custom_portfolio() (api/services.py)
    result = run_custom_portfolio(payload.model_dump())

    # Gestion d'erreur : Si backend retourne status="error", lever HTTPException
    # _http_status() mappe le code d'erreur vers un status code HTTP approprié
    if result.get("status") == "error":
        raise HTTPException(status_code=_http_status(result), detail=result["error"])

    # Succès : Retourner le JSON complet (status="success")
    return result


@app.post("/api/interpret")
def interpret_request(payload: InterpretRequest) -> dict[str, Any]:
    values = payload.model_dump(exclude_none=True)
    return interpret(values)


@app.post("/api/follow-ups")
def create_follow_up(payload: FollowUpRequest) -> dict[str, Any]:
    stored = store.get(payload.analysis_id)
    if stored is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "ANALYSIS_EXPIRED",
                "message": "Cette analyse est inconnue ou expirée. Relancez la simulation.",
            },
        )
    return follow_up(payload.question, stored.response, stored.request)


@app.post("/api/chat")
def create_chat(payload: ChatRequest) -> dict[str, Any]:
    analysis = None
    if payload.analysis_id is not None:
        stored = store.get(payload.analysis_id)
        if stored is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "ANALYSIS_EXPIRED",
                    "message": "Cette analyse est inconnue ou expirée. Relancez la simulation.",
                },
            )
        if stored.request.get("persona_id") != payload.persona_id:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "PERSONA_MISMATCH",
                    "message": "Cette analyse appartient à un autre profil fictif.",
                },
            )
        analysis = stored.response
    try:
        answer = chat(
            payload.persona_id,
            payload.question,
            [message.model_dump() for message in payload.history],
            analysis,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_CHAT", "message": str(exc)},
        ) from exc
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "CHAT_AWS_UNAVAILABLE",
                "message": explain_aws_error(exc, invalid_model_is_possible=True),
            },
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "CHAT_UNAVAILABLE",
                "message": "L'assistant est temporairement indisponible. Réessayez.",
            },
        ) from exc
    return {
        "status": "success",
        "answer": answer,
        "persona_id": payload.persona_id,
        "analysis_id": payload.analysis_id,
    }


@app.post("/api/evidence")
def get_evidence(payload: EvidenceRequest) -> dict[str, Any]:
    stored = store.get(payload.analysis_id)
    if stored is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "ANALYSIS_EXPIRED",
                "message": "Cette analyse est inconnue ou expirée. Relancez la simulation.",
            },
        )
    try:
        evidence = resolve_public_evidence(
            stored.response, stored.request, payload.references
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_EVIDENCE", "message": str(exc)},
        ) from exc
    return {"analysis_id": payload.analysis_id, "evidence": evidence}
