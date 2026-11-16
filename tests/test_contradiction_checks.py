
from alphaforge.contradiction_checks import detect_profile_contradictions

def test_detects_conflicting_speculation_preferences():
    profile = {
        "preferences": ["crypto", "peu de spéculation"],
        "objective": "croissance à long terme",
        "risk_level": "high",
    }

    findings = detect_profile_contradictions(profile)

    assert len(findings) == 1
    assert findings[0]["id"] == "speculation_preference_conflict"
    assert findings[0]["status"] == "tension"


def test_detects_conflicting_risk_and_objective():
    profile = {
        "preferences": [],
        "objective": "préservation du capital",
        "risk_level": "high",
    }

    findings = detect_profile_contradictions(profile)

    assert len(findings) == 1
    assert findings[0]["id"] == "risk_objective_conflict"
    assert findings[0]["status"] == "tension"


def test_no_contradiction_for_consistent_profile():
    profile = {
        "preferences": ["technologies", "diversification"],
        "objective": "croissance à long terme",
        "risk_level": "high",
    }

    findings = detect_profile_contradictions(profile)

    assert findings == []

def test_no_false_contradictions_for_team_personas():
    personas = [
        {
            "preferences": ["AI", "technologies", "crypto", "diversification"],
            "objective": "croissance à long terme",
            "risk_level": "high",
        },
        {
            "preferences": ["ESG", "stabilité", "peu de spéculation"],
            "objective": "croissance équilibrée",
            "risk_level": "moderate",
        },
        {
            "preferences": ["préservation du capital", "croissance"],
            "objective": "préservation du capital",
            "risk_level": "low-to-moderate",
        },
    ]

    for persona in personas:
        assert detect_profile_contradictions(persona) == []