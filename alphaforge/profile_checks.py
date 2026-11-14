
import json
from pathlib import Path
from datetime import date


def _finding(topic, status, evidence, limitation=None):
    """Construit un constat dans un format uniforme."""
    return {
        "topic": topic,
        "status": status,
        "evidence": evidence,
        "limitation": limitation
    }


def _get_metric_delta(engine_results, metric):
    """Récupère la variation d'une métrique entre avant et après."""
    return (
        engine_results
        .get("delta_after_minus_before", {})
        .get("metrics", {})
        .get(metric)
    )


def validate_profile(profile, scenario, engine_results, data_dir):
    """
    Analyse la cohérence d'un scénario avec le profil d'un investisseur.

    Retourne une liste de constats structurés.
    """
    findings = []

    persona_id = profile.get("id")

    # Le moteur utilise added_symbol dans ses résultats.
    symbol = scenario.get("symbol") or engine_results.get(
        "scenario", {}
    ).get("added_symbol")

    # --------------------------------------------------
    # AMIRA : concentration et diversification
    # --------------------------------------------------
    if persona_id == "amira":
        before = engine_results.get("before", {})
        after = engine_results.get("after", {})

        before_weights = before.get("weights_by_asset_pct", {})
        after_weights = after.get("weights_by_asset_pct", {})

        before_equity = before.get(
            "weights_by_class_pct", {}
        ).get("equity", 0)

        after_equity = after.get(
            "weights_by_class_pct", {}
        ).get("equity", 0)

        added_weight = after_weights.get(symbol)

        findings.append(
            _finding(
                topic="concentration",
                status="insufficient_information",
                evidence={
                    "added_asset": symbol,
                    "added_weight_pct": added_weight,
                    "equity_weight_before_pct": before_equity,
                    "equity_weight_after_pct": after_equity,
                    "equity_weight_change_pp": (
                        after_equity - before_equity
                    )
                },
                limitation=(
                    "La classe equity regroupe plusieurs secteurs. "
                    "Le moteur ne fournit pas la concentration technologique "
                    "ni la composition interne des FNB."
                )
            )
        )

        asset_count_before = len(before_weights)
        asset_count_after = len(after_weights)

        asset_weight_changes = {
            asset: after_weights.get(asset, 0)
            - before_weights.get(asset, 0)
            for asset in set(before_weights) | set(after_weights)
        }

        findings.append(
            _finding(
                topic="diversification",
                status="insufficient_information",
                evidence={
                    "asset_count_before": asset_count_before,
                    "asset_count_after": asset_count_after,
                    "asset_count_change": (
                        asset_count_after - asset_count_before
                    ),
                    "asset_weight_changes_pp": asset_weight_changes
                },
                limitation=(
                    "Le nombre d'actifs et leurs poids permettent de mesurer "
                    "la répartition du portefeuille, mais pas sa diversification "
                    "économique réelle. Les secteurs et les compositions internes "
                    "des FNB ne sont pas disponibles."
                )
            )
        )

        findings.append(
            _finding(
                topic="etf_overlap",
                status="insufficient_information",
                evidence={
                    "added_asset": symbol,
                    "existing_etf": "QQQ"
                },
                limitation=(
                    "La composition détaillée de QQQ n'est pas fournie. "
                    "Le chevauchement réel avec NVDA ne peut donc pas "
                    "être calculé."
                )
            )
        )

    # --------------------------------------------------
    # MATEO : compatibilité ESG
    # --------------------------------------------------
    elif persona_id == "mateo":
        evidence_path = Path(data_dir) / "esg_evidence.json"

        with evidence_path.open(encoding="utf-8") as file:
            esg_data = json.load(file)

        asset_evidence = esg_data.get(symbol, [])
        assessed_evidence = []

        for item in asset_evidence:
            publisher = item.get("publisher")
            published_on = item.get("published_on")
            accessed_on = item.get("accessed_on")

            evidence_date = published_on or accessed_on

            date_type = (
                "publication"
                if published_on
                else "consultation"
                if accessed_on
                else None
            )

            try:
                date.fromisoformat(evidence_date)
                valid_date = True
            except (ValueError, TypeError):
                valid_date = False

            assessed_evidence.append({
                "topic": item.get("topic"),
                "claim": item.get("claim"),
                "publisher": publisher,
                "date": evidence_date,
                "date_type": date_type,
                "valid_date": valid_date,
                "company_published_source": (
                    publisher == "ExxonMobil"
                ),
                "limitation": item.get("limitation")
            })

        findings.append(
            _finding(
                topic="esg_compatibility",
                status="insufficient_information",
                evidence={
                    "added_asset": symbol,
                    "esg_evidence_available": bool(asset_evidence),
                    "evidence_count": len(asset_evidence),
                    "evidence": assessed_evidence,
                    "assessed_evidence": assessed_evidence
                },
                limitation=(
                    "Les preuves permettent d'identifier des affirmations "
                    "environnementales et de gouvernance datées. Toutefois, "
                    "elles proviennent de l'entreprise elle-même et ne "
                    "constituent pas une évaluation indépendante. La date "
                    "de consultation ne remplace pas la date de publication. "
                    "La compatibilité complète avec les préférences ESG "
                    "de Mateo ne peut donc pas être établie."
                )
            )
        )

    # --------------------------------------------------
    # ROBERT : préservation du capital
    # --------------------------------------------------
    elif persona_id == "robert":
        before_metrics = engine_results.get(
            "before", {}
        ).get("metrics", {})

        after_metrics = engine_results.get(
            "after", {}
        ).get("metrics", {})

        volatility_before = before_metrics.get(
            "annualized_volatility"
        )
        volatility_after = after_metrics.get(
            "annualized_volatility"
        )

        drawdown_before = before_metrics.get("max_drawdown")
        drawdown_after = after_metrics.get("max_drawdown")

        volatility_delta = _get_metric_delta(
            engine_results, "annualized_volatility"
        )
        drawdown_delta = _get_metric_delta(
            engine_results, "max_drawdown"
        )

        # Vérifier que toutes les données nécessaires sont disponibles.
        if (
            volatility_before is None
            or volatility_after is None
            or drawdown_before is None
            or drawdown_after is None
            or volatility_delta is None
            or drawdown_delta is None
        ):
            status = "insufficient_information"

        # Une hausse de volatilité ou un drawdown plus négatif
        # indique une détérioration historique.
        elif volatility_delta > 0 or drawdown_delta < 0:
            status = "tension_identified"

        else:
            status = "coherent"

        findings.append(
            _finding(
                topic="capital_preservation",
                status=status,
                evidence={
                    "added_asset": symbol,
                    "target_weight_pct": scenario.get(
                        "target_weight_pct"
                    ),
                    "investor_horizon": (
                        profile.get("investment_horizon")
                        or profile.get("horizon")
                    ),
                    "investor_objective": profile.get("objective"),
                    "annualized_volatility": {
                        "before": volatility_before,
                        "after": volatility_after,
                        "change": volatility_delta
                    },
                    "max_drawdown": {
                        "before": drawdown_before,
                        "after": drawdown_after,
                        "change": drawdown_delta
                    }
                },
                limitation=(
                    "Les métriques décrivent le comportement historique "
                    "du portefeuille et ne prédisent pas les pertes futures. "
                    "Une détérioration historique indique une tension avec "
                    "l'objectif de préservation du capital, mais ne suffit "
                    "pas à déterminer si le portefeuille convient à Robert. "
                    "L'horizon de placement et la tolérance réelle aux pertes "
                    "doivent également être considérés."
                )
            )
        )

    return findings
