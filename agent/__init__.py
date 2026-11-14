"""Fondations locales de l'agent AlphaForge, sans appel AWS."""

from agent.context import RequestContext, RequestSpec, create_request_context
from agent.evidence import (
    build_evidence_bundle,
    build_interface_payload,
    resolve_evidence_reference,
)
from agent.prompts import EXPLANATION_FORMAT, MODEL_EXPLANATION_FORMAT, SYSTEM_INSTRUCTIONS
from agent.service import analyze_request
from agent.tools import (
    TOOL_SPECS,
    check_profile,
    dispatch_tool,
    simulate_portfolio_change,
)

__all__ = [
    "EXPLANATION_FORMAT",
    "MODEL_EXPLANATION_FORMAT",
    "RequestContext",
    "RequestSpec",
    "SYSTEM_INSTRUCTIONS",
    "TOOL_SPECS",
    "build_evidence_bundle",
    "build_interface_payload",
    "check_profile",
    "analyze_request",
    "create_request_context",
    "dispatch_tool",
    "resolve_evidence_reference",
    "simulate_portfolio_change",
]
