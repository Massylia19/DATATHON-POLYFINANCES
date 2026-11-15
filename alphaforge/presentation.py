"""Libellés et formatage français pour la présentation des résultats."""

from __future__ import annotations

import re
from datetime import date
from typing import Any


STATUS_LABELS = {
    "consistent": "Aucune tension supplémentaire observée sur ce point",
    "tension": "Point de vigilance",
    "insufficient_information": "Informations insuffisantes",
}

MISSING_INFORMATION_LABELS = {
    "loss_absorption_capacity": "la perte {loss_clause} pourrait supporter",
    "liquidity_needs": "ses besoins d’argent à court terme",
    "planned_withdrawals": "ses retraits prévus",
    "etf_holdings": "la composition détaillée des fonds du portefeuille",
    "asset_specific_esg_evidence": (
        "des éléments propres à l’actif pour évaluer ses critères "
        "environnementaux, sociaux et de gouvernance"
    ),
    "independent_esg_assessment": (
        "une évaluation indépendante de ses critères environnementaux, "
        "sociaux et de gouvernance"
    ),
    "sector_exposures": "la répartition réelle des placements par secteur",
}

TOPIC_LABELS = {
    "performance": "Progression du portefeuille",
    "risk": "Fluctuations et baisses",
    "allocation": "Répartition du portefeuille",
    "concentration": "Concentration des placements",
    "diversification": "Répartition des placements",
    "etf_overlap": "Composition des fonds",
    "esg_compatibility": "Préférences environnementales, sociales et de gouvernance",
    "capital_preservation": "Préservation du capital",
}

CHECK_TITLE_LABELS = {
    "concentration": "Concentration des placements",
    "diversification": "Diversification économique",
    "etf_overlap": "Placements indirects dans les fonds",
    "esg_compatibility": "Préférences environnementales, sociales et de gouvernance",
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
        "title": "Gain sur la période",
        "technical": "Rendement total",
        "definition": (
            "Progression totale sur les dates étudiées, pas un gain annuel."
        ),
    },
    "annualized_volatility": {
        "title": "Ampleur des fluctuations",
        "technical": "Volatilité annualisée",
        "definition": (
            "Une valeur plus élevée indique des mouvements historiques plus "
            "importants. Ce n’est pas une perte prévue."
        ),
    },
    "max_drawdown": {
        "title": "Plus forte baisse observée",
        "technical": "Baisse maximale",
        "definition": (
            "Baisse la plus importante depuis un sommet pendant cette période. "
            "Des pertes futures pourraient être plus importantes."
        ),
    },
}

SOURCE_PRESENTATION = {
    "src_prices_daily": ("Yahoo Finance", "historique des prix"),
    "src_fx_usdcad": ("Banque du Canada", "taux de change"),
    "src_assets_universe": ("AlphaForge", "univers des actifs"),
    "src_personas": ("AlphaForge", "profils fictifs"),
    "src_portfolios": ("AlphaForge", "portefeuilles de démonstration"),
}

FRENCH_MONTHS = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)

UNSAFE_NARRATIVE_PATTERNS = (
    re.compile(r"\b(?:analysis|source)\.[\w.-]+", re.IGNORECASE),
    re.compile(
        r"\b(?:etf_holdings|sector_exposures|loss_absorption_capacity|"
        r"liquidity_needs|planned_withdrawals|asset_specific_esg_evidence|"
        r"independent_esg_assessment|equity|insufficient_information|"
        r"consistent|success|partial|error|simulate_portfolio_change|"
        r"check_profile|ESG|FNB|ETF)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b", re.IGNORECASE),
    re.compile(
        r"\b(?:adj_close|sqrt\s*\(\s*252\s*\)|intersection stricte|"
        r"biais du survivant|annualis\w*|volatilité|drawdown)\b",
        re.IGNORECASE,
    ),
)


def readable_label(value: str, mapping: dict[str, str]) -> str:
    """Traduit une clé connue sans exposer une clé inconnue."""
    if value in mapping:
        return mapping[value]
    return "Autre information à vérifier"


def persona_possessive(name: str) -> str:
    if name[:1].casefold() in "aàâäeéèêëiîïoôöuùûüyÿh":
        return f"d’{name}"
    return f"de {name}"


def format_date_fr(value: str) -> str:
    """Affiche une date ISO en français sans dépendre de la locale système."""
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        if len(value) == 7 and value[4] == "-":
            try:
                parsed = date.fromisoformat(f"{value}-01")
            except ValueError:
                return value
            return f"{FRENCH_MONTHS[parsed.month - 1]} {parsed.year}"
        return value
    return f"{parsed.day} {FRENCH_MONTHS[parsed.month - 1]} {parsed.year}"


def missing_information_phrases(
    items: list[str], persona_name: str
) -> list[str]:
    """Traduit et déduplique les champs manquants structurés."""
    unique_items = list(dict.fromkeys(items))
    phrases: list[str] = []
    grouped_fields = {"etf_holdings", "sector_exposures"}
    if grouped_fields.issubset(unique_items):
        phrases.append(
            "la composition des fonds, nécessaire pour connaître les placements "
            "indirects et leur répartition par secteur"
        )
        unique_items = [
            item for item in unique_items if item not in grouped_fields
        ]

    grouped_esg_fields = {
        "asset_specific_esg_evidence",
        "independent_esg_assessment",
    }
    grouped_esg_phrase = None
    if grouped_esg_fields.issubset(unique_items):
        grouped_esg_phrase = (
            "des preuves et une évaluation indépendante permettant de vérifier "
            "si l’actif respecte ses critères environnementaux, sociaux et de "
            "gouvernance"
        )
        unique_items = [
            item for item in unique_items if item not in grouped_esg_fields
        ]

    first_letter = persona_name[:1].casefold()
    loss_clause = (
        f"qu’{persona_name}"
        if first_letter in "aàâäeéèêëiîïoôöuùûüyÿh"
        else f"que {persona_name}"
    )
    for item in unique_items:
        template = MISSING_INFORMATION_LABELS.get(item)
        phrase = (
            template.format(loss_clause=loss_clause)
            if template
            else "d’autres informations utiles"
        )
        if phrase not in phrases:
            phrases.append(phrase)
    if grouped_esg_phrase:
        phrases.append(grouped_esg_phrase)
    return phrases


def join_french_list(items: list[str]) -> str:
    if len(items) < 2:
        return items[0] if items else ""
    if len(items) == 2:
        return f"{items[0]} et {items[1]}"
    return f"{', '.join(items[:-1])} et {items[-1]}"


def has_unsafe_main_narrative(value: Any) -> bool:
    """Repère les nombres ou identifiants internes sans réécrire la prose."""
    if not isinstance(value, str) or not value.strip():
        return True
    if any(character.isdigit() for character in value):
        return True
    return any(pattern.search(value) for pattern in UNSAFE_NARRATIVE_PATTERNS)


def _period_length_label(start: str, end: str) -> str:
    try:
        first = date.fromisoformat(start)
        last = date.fromisoformat(end)
    except ValueError:
        return "la période étudiée"
    years = last.year - first.year
    if (last.month, last.day) < (first.month, first.day):
        years -= 1
    if years < 1:
        return "la période étudiée"
    number_words = {
        1: "une",
        2: "deux",
        3: "trois",
        4: "quatre",
        5: "cinq",
        6: "six",
        7: "sept",
        8: "huit",
        9: "neuf",
        10: "dix",
    }
    year_count = number_words.get(years, str(years))
    return f"les {year_count} années étudiées"


def _metric_direction(delta: float) -> int:
    if abs(float(delta)) < 1e-15:
        return 0
    return 1 if delta > 0 else -1


def _structured_summary(
    analysis: dict, persona: dict, asset_name: str
) -> str:
    period = analysis["period"]
    metric_deltas = analysis["delta_after_minus_before"]["metrics"]
    performance = _metric_direction(metric_deltas["total_return"])
    if performance > 0:
        outcome = "a davantage progressé"
    elif performance < 0:
        outcome = "a moins progressé"
    else:
        outcome = "a évolué de façon similaire"

    risk_parts = []
    volatility_direction = _metric_direction(
        metric_deltas["annualized_volatility"]
    )
    if volatility_direction > 0:
        risk_parts.append("sa valeur a davantage fluctué")
    elif volatility_direction < 0:
        risk_parts.append("sa valeur a moins fluctué")

    drawdown_direction = _metric_direction(metric_deltas["max_drawdown"])
    if drawdown_direction < 0:
        risk_parts.append("sa plus forte baisse a été plus importante")
    elif drawdown_direction > 0:
        risk_parts.append("sa plus forte baisse a été moins importante")

    duration = _period_length_label(period["start"], period["end"])
    opening = (
        "Sur la période étudiée"
        if duration == "la période étudiée"
        else f"Sur {duration}"
    )
    sentences = [
        f"{opening}, le portefeuille avec {asset_name} {outcome}."
    ]
    if risk_parts:
        risk_sentence = (
            f"{risk_parts[0]} et {risk_parts[1]}."
            if len(risk_parts) == 2
            else risk_parts[0].capitalize() + "."
        )
        sentences.append(f"En contrepartie, {risk_sentence}")
    objective = persona.get("objective")
    if objective:
        objective = objective[:1].lower() + objective[1:]
        sentences.append(
            f"Ce compromis est à mettre en regard de l’objectif de {objective} "
            f"{persona_possessive(persona['name'])}."
        )
    return " ".join(sentences)


def build_main_summary(
    analysis: dict,
    persona: dict,
    asset_name: str,
    explanation: dict | None,
) -> str:
    """Privilégie le résumé qualitatif sûr de Claude, sinon les faits structurés."""
    candidate = (explanation or {}).get("summary")
    if not has_unsafe_main_narrative(candidate):
        candidate_text = candidate.strip()
        symbol = analysis.get("scenario", {}).get("added_symbol", "")
        if symbol and symbol.casefold() in candidate_text.casefold():
            return _structured_summary(analysis, persona, asset_name)
        useful_terms = (
            "portefeuille",
            "progress",
            "fluctu",
            "baisse",
            "compromis",
            "objectif",
            "profil",
            "risque",
        )
        if any(term in candidate_text.casefold() for term in useful_terms):
            profile_terms = (
                persona["name"].casefold(),
                "objectif",
                "profil",
                "préférence",
                "horizon",
            )
            if not any(term in candidate_text.casefold() for term in profile_terms):
                objective = persona.get("objective") or "ce profil"
                objective = objective[:1].lower() + objective[1:]
                candidate_text += (
                    f" Ce compromis est à mettre en regard de l’objectif de "
                        f"{objective} "
                        f"{persona_possessive(persona['name'])}."
                )
            return candidate_text
    return _structured_summary(analysis, persona, asset_name)


def _number_fr(value: float, decimals: int, *, signed: bool = False) -> str:
    rendered = f"{value:+.{decimals}f}" if signed else f"{value:.{decimals}f}"
    return rendered.replace("-", "−").replace(".", ",")


def format_rate(value: float) -> str:
    """Formate un taux stocké sous forme décimale, uniquement pour l’affichage."""
    return f"{_number_fr(float(value) * 100, 2)} %"


def format_weight(value: float) -> str:
    """Formate une pondération déjà exprimée en pourcentage."""
    value = float(value)
    decimals = 0 if value.is_integer() else 1
    return f"{_number_fr(value, decimals)} %"


def format_points(value: float) -> str:
    """Formate l’écart entre deux taux décimaux en points de pourcentage."""
    return f"{_number_fr(float(value) * 100, 2, signed=True)} points de pourcentage"


def format_weight_delta(value: float) -> str:
    """Formate un écart de pondération déjà exprimé en points."""
    value = float(value)
    label = "point de pourcentage" if abs(value) == 1 else "points de pourcentage"
    return f"{_number_fr(value, 1, signed=True)} {label}"


def describe_metric_change(metric: str, delta: float) -> str:
    """Explique le signe d’un écart sans transformer celui-ci en prévision."""
    if abs(float(delta)) < 1e-15:
        return "Aucun écart n’est observé sur cette mesure."
    if metric == "annualized_volatility":
        return (
            "La valeur du portefeuille a davantage fluctué."
            if delta > 0
            else "La valeur du portefeuille a moins fluctué."
        )
    if metric == "max_drawdown":
        return (
            "La plus forte baisse observée est moins importante."
            if delta > 0
            else "La plus forte baisse observée est plus importante."
        )
    return (
        "Le portefeuille a davantage progressé sur cette période."
        if delta > 0
        else "Le portefeuille a moins progressé sur cette période."
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
