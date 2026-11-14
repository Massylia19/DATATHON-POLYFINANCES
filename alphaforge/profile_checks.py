"""Contrôles explicables reliant les résultats du moteur aux profils fictifs."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


VALID_STATUSES = {"consistent", "tension", "insufficient_information"}


def _finding(
    check_id: str,
    status: str,
    title: str,
    message: str,
    evidence_refs: list[str],
    missing_information: list[str],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    """Construit un constat conforme au contrat commun du projet."""
    if status not in VALID_STATUSES:
        raise ValueError(f"Statut de contrôle invalide: {status}")
    return {
        "id": check_id,
        "topic": check_id,
        "status": status,
        "title": title,
        "message": message,
        "evidence_refs": evidence_refs,
        "missing_information": missing_information,
        "evidence": evidence,
    }


def _get_metric_delta(engine_results: dict[str, Any], metric: str) -> Any:
    return (
        engine_results.get("delta_after_minus_before", {})
        .get("metrics", {})
        .get(metric)
    )


def validate_profile(
    profile: dict[str, Any],
    scenario: dict[str, Any],
    engine_results: dict[str, Any],
    data_dir: Path,
) -> list[dict[str, Any]]:
    """Analyse un scénario sans transformer les préférences en verdict financier."""
    findings: list[dict[str, Any]] = []
    persona_id = profile.get("id")
    symbol = scenario.get("symbol") or engine_results.get("scenario", {}).get(
        "added_symbol"
    )

    if persona_id == "amira":
        before = engine_results.get("before", {})
        after = engine_results.get("after", {})
        before_weights = before.get("weights_by_asset_pct", {})
        after_weights = after.get("weights_by_asset_pct", {})
        before_equity = before.get("weights_by_class_pct", {}).get("equity", 0)
        after_equity = after.get("weights_by_class_pct", {}).get("equity", 0)

        findings.append(
            _finding(
                "concentration",
                "insufficient_information",
                "Concentration technologique",
                (
                    "L'ajout et l'exposition directe aux actions sont mesurables, "
                    "mais la concentration technologique totale ne l'est pas sans "
                    "la composition datée des FNB."
                ),
                [
                    f"analysis.after.weights_by_asset_pct.{symbol}",
                    "analysis.before.weights_by_class_pct.equity",
                    "analysis.after.weights_by_class_pct.equity",
                ],
                ["etf_holdings"],
                {
                    "added_asset": symbol,
                    "added_weight_pct": after_weights.get(symbol),
                    "equity_weight_before_pct": before_equity,
                    "equity_weight_after_pct": after_equity,
                    "equity_weight_change_pp": after_equity - before_equity,
                },
            )
        )

        asset_weight_changes = {
            asset: after_weights.get(asset, 0) - before_weights.get(asset, 0)
            for asset in set(before_weights) | set(after_weights)
        }
        findings.append(
            _finding(
                "diversification",
                "insufficient_information",
                "Diversification du portefeuille",
                (
                    "Le nombre d'actifs et leurs poids décrivent la répartition, "
                    "mais pas la diversification économique réelle."
                ),
                [
                    "analysis.before.weights_by_asset_pct",
                    "analysis.after.weights_by_asset_pct",
                ],
                ["sector_exposures", "etf_holdings"],
                {
                    "asset_count_before": len(before_weights),
                    "asset_count_after": len(after_weights),
                    "asset_count_change": len(after_weights) - len(before_weights),
                    "asset_weight_changes_pp": asset_weight_changes,
                },
            )
        )

        findings.append(
            _finding(
                "etf_overlap",
                "insufficient_information",
                "Chevauchement avec les FNB",
                (
                    f"Le chevauchement indirect entre {symbol} et les FNB du "
                    "portefeuille ne peut pas être quantifié avec les seuls prix."
                ),
                [f"analysis.after.weights_by_asset_pct.{symbol}"],
                ["etf_holdings"],
                {"added_asset": symbol, "existing_etfs": ["SPY", "QQQ"]},
            )
        )

    elif persona_id == "mateo":
        evidence_path = Path(data_dir) / "esg_evidence.json"
        with evidence_path.open(encoding="utf-8") as file:
            esg_data = json.load(file)

        asset_evidence = esg_data.get(symbol, [])
        assessed_evidence = []
        for item in asset_evidence:
            evidence_date = item.get("published_on") or item.get("accessed_on")
            try:
                date.fromisoformat(evidence_date)
                valid_date = True
            except (ValueError, TypeError):
                valid_date = False
            assessed_evidence.append(
                {
                    "id": item.get("id"),
                    "topic": item.get("topic"),
                    "claim": item.get("claim"),
                    "publisher": item.get("publisher"),
                    "url": item.get("url"),
                    "date": evidence_date,
                    "date_type": (
                        "publication" if item.get("published_on") else "consultation"
                    ),
                    "valid_date": valid_date,
                    "company_published_source": item.get("publisher") == "ExxonMobil",
                    "limitation": item.get("limitation"),
                }
            )

        evidence_refs = [
            f"source.{item['id']}"
            for item in assessed_evidence
            if item.get("id") and item.get("valid_date")
        ]
        missing = [] if assessed_evidence else ["asset_specific_esg_evidence"]
        missing.append("independent_esg_assessment")
        findings.append(
            _finding(
                "esg_compatibility",
                "insufficient_information",
                "Compatibilité avec les préférences ESG",
                (
                    "Des éléments datés propres à l'actif sont disponibles, mais "
                    "ils ne suffisent pas à établir sa compatibilité globale avec "
                    "les préférences ESG de Mateo."
                    if assessed_evidence
                    else "Aucune preuve ESG propre à cet actif ne permet de conclure."
                ),
                evidence_refs,
                missing,
                {
                    "added_asset": symbol,
                    "esg_evidence_available": bool(asset_evidence),
                    "evidence_count": len(asset_evidence),
                    "assessed_evidence": assessed_evidence,
                },
            )
        )

    elif persona_id == "robert":
        before_metrics = engine_results.get("before", {}).get("metrics", {})
        after_metrics = engine_results.get("after", {}).get("metrics", {})
        volatility_before = before_metrics.get("annualized_volatility")
        volatility_after = after_metrics.get("annualized_volatility")
        drawdown_before = before_metrics.get("max_drawdown")
        drawdown_after = after_metrics.get("max_drawdown")
        volatility_delta = _get_metric_delta(
            engine_results, "annualized_volatility"
        )
        drawdown_delta = _get_metric_delta(engine_results, "max_drawdown")
        metrics = (
            volatility_before,
            volatility_after,
            drawdown_before,
            drawdown_after,
            volatility_delta,
            drawdown_delta,
        )

        if any(value is None for value in metrics):
            status = "insufficient_information"
            message = "Les métriques nécessaires au contrôle sont incomplètes."
        elif volatility_delta > 0 or drawdown_delta < 0:
            status = "tension"
            message = (
                "Les observations historiques montrent une hausse de volatilité "
                "ou une baisse maximale plus profonde; cela crée une tension à "
                "examiner avec l'objectif de préservation du capital."
            )
        else:
            status = "consistent"
            message = (
                "Les métriques historiques examinées ne montrent pas de tension "
                "supplémentaire sur ce point précis; cela ne certifie pas le portefeuille."
            )

        findings.append(
            _finding(
                "capital_preservation",
                status,
                "Préservation du capital",
                message,
                [
                    "analysis.before.metrics.annualized_volatility",
                    "analysis.after.metrics.annualized_volatility",
                    "analysis.before.metrics.max_drawdown",
                    "analysis.after.metrics.max_drawdown",
                ],
                list(profile.get("missing_information", [])),
                {
                    "added_asset": symbol,
                    "target_weight_pct": scenario.get("target_weight_pct"),
                    "horizon_years_min": profile.get("horizon_years_min"),
                    "horizon_years_max": profile.get("horizon_years_max"),
                    "investor_objective": profile.get("objective"),
                    "annualized_volatility": {
                        "before": volatility_before,
                        "after": volatility_after,
                        "change": volatility_delta,
                    },
                    "max_drawdown": {
                        "before": drawdown_before,
                        "after": drawdown_after,
                        "change": drawdown_delta,
                    },
                },
            )
        )

    return findings
