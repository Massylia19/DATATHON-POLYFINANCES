
"""Détection des contradictions dans les déclarations du profil."""

from typing import Any


def detect_profile_contradictions(
    profile: dict[str, Any],
) -> list[dict[str, Any]]:
    """Repère les contradictions explicites entre les préférences."""

    findings = []

    preferences = [
        str(item).lower()
        for item in profile.get("preferences", [])
    ]

    objective = str(profile.get("objective", "")).lower()
    risk_level = profile.get("risk_level")

    likes_speculation = any(
        term in preferences
        for term in ("crypto", "spéculation", "speculation")
    )

    avoids_speculation = any(
        term in preference
        for preference in preferences
        for term in (
            "peu de spéculation",
            "peu de crypto",
            "éviter la spéculation",
        )
    )

    if likes_speculation and avoids_speculation:
        findings.append({
            "id": "speculation_preference_conflict",
            "topic": "speculation_preference_conflict",
            "status": "tension",
            "title": "Préférences contradictoires",
            "message": (
                "Le profil exprime à la fois un intérêt pour les actifs "
                "spéculatifs et une volonté de limiter la spéculation."
            ),
            "evidence_refs": [],
            "missing_information": [],
            "evidence": {
                "preferences": preferences,
            },
        })

    capital_preservation = (
        "préservation du capital" in objective
        or "preservation du capital" in objective
    )

    if capital_preservation and risk_level == "high":
        findings.append({
            "id": "risk_objective_conflict",
            "topic": "risk_objective_conflict",
            "status": "tension",
            "title": "Risque et objectif à clarifier",
            "message": (
                "Le profil combine une tolérance au risque élevée "
                "avec un objectif de préservation du capital."
            ),
            "evidence_refs": [],
            "missing_information": [],
            "evidence": {
                "risk_level": risk_level,
                "objective": objective,
            },
        })

    return findings
