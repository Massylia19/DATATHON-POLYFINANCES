"""Libellés et formatage français pour la présentation des résultats."""

from __future__ import annotations

from typing import Any


STATUS_LABELS = {
    "consistent": "Cohérent sur ce point",
    "tension": "Point de vigilance",
    "insufficient_information": "Informations insuffisantes",
}

MISSING_INFORMATION_LABELS = {
    "loss_absorption_capacity": "La perte que vous pourriez supporter",
    "liquidity_needs": "Vos besoins d’argent à court terme",
    "planned_withdrawals": "Vos retraits prévus",
    "etf_holdings": "La composition détaillée des fonds",
    "asset_specific_esg_evidence": "Des informations ESG propres à cet actif",
    "independent_esg_assessment": "Une évaluation ESG indépendante",
    "sector_exposures": "La répartition réelle par secteur d’activité",
}

TOPIC_LABELS = {
    "performance": "Évolution de la valeur",
    "risk": "Fluctuations et baisses",
    "allocation": "Répartition du portefeuille",
    "concentration": "Concentration",
    "diversification": "Diversification",
    "etf_overlap": "Placements détenus indirectement par les fonds",
    "esg_compatibility": "Préférences ESG",
    "capital_preservation": "Préservation du capital",
}

CHECK_TITLE_LABELS = {
    "concentration": "Concentration du portefeuille",
    "diversification": "Répartition des placements",
    "etf_overlap": "Placements détenus par les fonds",
    "esg_compatibility": "Critères environnementaux, sociaux et de gouvernance",
    "capital_preservation": "Préservation du capital",
}

ASSET_CLASS_LABELS = {
    "equity": "Actions",
    "etf_equity": "Fonds d’actions",
    "etf_bond": "Fonds d’obligations",
    "etf_commodity": "Fonds de matières premières",
    "fixed_income": "Titres à revenu fixe",
    "etf_fixed_income": "Fonds de titres à revenu fixe",
    "commodity": "Matières premières",
    "crypto": "Cryptoactifs",
    "cash": "Liquidités",
}

METRIC_PRESENTATION = {
    "total_return": {
        "title": "Rendement sur la période",
        "technical": "Rendement total",
        "definition": "Gain ou perte total sur la période historique affichée. Ce n’est pas un rendement annuel.",
    },
    "annualized_volatility": {
        "title": "Variations du portefeuille",
        "technical": "Volatilité annualisée",
        "definition": "Mesure l’ampleur des fluctuations historiques. Ce n’est ni une perte prévue ni une probabilité de perdre.",
    },
    "max_drawdown": {
        "title": "Plus forte baisse historique",
        "technical": "Baisse maximale",
        "definition": "Plus grande baisse observée depuis un sommet sur les dates retenues. Ce n’est pas la perte maximale possible dans le futur.",
    },
}


def readable_label(value: str, mapping: dict[str, str]) -> str:
    """Traduit une clé interne ou produit un libellé de repli lisible."""
    if value in mapping:
        return mapping[value]
    return str(value).replace("_", " ").strip().capitalize()


def _number_fr(value: float, decimals: int, *, signed: bool = False) -> str:
    rendered = f"{value:+.{decimals}f}" if signed else f"{value:.{decimals}f}"
    return rendered.replace("-", "−").replace(".", ",")


def format_rate(value: float) -> str:
    """Formate un taux stocké sous forme décimale, uniquement pour l’affichage."""
    return f"{_number_fr(float(value) * 100, 2)} %"


def format_weight(value: float) -> str:
    """Formate une pondération déjà exprimée en pourcentage."""
    return f"{_number_fr(float(value), 1)} %"


def format_points(value: float) -> str:
    """Formate l’écart entre deux taux décimaux en points de pourcentage."""
    return f"{_number_fr(float(value) * 100, 2, signed=True)} points de pourcentage"


def format_weight_delta(value: float) -> str:
    """Formate un écart de pondération déjà exprimé en points."""
    return f"{_number_fr(float(value), 1, signed=True)} point(s)"


def describe_metric_change(metric: str, delta: float) -> str:
    """Explique le signe d’un écart sans transformer celui-ci en prévision."""
    if abs(float(delta)) < 1e-15:
        return "Aucun écart n’est observé sur cette mesure."
    if metric == "annualized_volatility":
        return (
            "Les fluctuations historiques sont plus importantes."
            if delta > 0
            else "Les fluctuations historiques sont moins importantes."
        )
    if metric == "max_drawdown":
        return (
            "La baisse historique observée est moins profonde."
            if delta > 0
            else "La baisse historique observée est plus profonde."
        )
    return (
        "Le rendement historique sur la période est plus élevé."
        if delta > 0
        else "Le rendement historique sur la période est moins élevé."
    )


def evidence_value_for_display(reference: str, value: Any, unit: str) -> str:
    """Formate une preuve résolue sans modifier sa valeur brute."""
    if unit == "decimal_ratio" and isinstance(value, (int, float)):
        return format_rate(value)
    if unit == "percentage" and isinstance(value, (int, float)):
        return format_weight(value)
    if isinstance(value, str):
        return value
    return str(value)
