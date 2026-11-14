
from pathlib import Path

import pytest

from alphaforge.engine import compare_case, load_case
from alphaforge.profile_checks import validate_profile


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "persona_id, expected_topics",
    [
        ("amira", {"concentration", "diversification", "etf_overlap"}),        ("mateo", {"esg_compatibility"}),
        ("robert", {"capital_preservation"}),
    ],
)
def test_validate_profile(persona_id, expected_topics):
    # Charger les données du profil, du portefeuille et du scénario
    profile, portfolio, scenario = load_case(
        ROOT / "data", persona_id
    )

    # Obtenir les résultats du moteur
    engine_results = compare_case(ROOT, persona_id)

    # Exécuter les contrôles du profil
    findings = validate_profile(
        profile,
        scenario,
        engine_results,
        ROOT / "data"
    )

    # Vérifier que des constats sont retournés
    assert findings

    # Vérifier les sujets analysés
    actual_topics = {
        finding["topic"] for finding in findings
    }
    assert actual_topics == expected_topics

    # Vérifier que les statuts sont valides
    valid_statuses = {
        "coherent",
        "tension_identified",
        "insufficient_information",
    }

    for finding in findings:
        assert finding["status"] in valid_statuses
        assert "evidence" in finding
        assert "limitation" in finding

    # Vérifier que les preuves ESG de Mateo sont chargées
    if persona_id == "mateo":
        esg_evidence = findings[0]["evidence"]

        assert esg_evidence["esg_evidence_available"] is True
        assert len(esg_evidence["evidence"]) > 0
