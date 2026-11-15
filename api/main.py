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
    result = run_custom_portfolio(payload.model_dump())
    if result.get("status") == "error":
        raise HTTPException(status_code=_http_status(result), detail=result["error"])
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
