"""Moteur déterministe de comparaison historique de portefeuilles.

Le moteur utilise uniquement la bibliothèque standard Python. Les prix sont
convertis en CAD, alignés sur l'intersection des dates de cotation de tous les
actifs comparés, puis simulés selon une stratégie acheter-et-conserver.
"""

from __future__ import annotations

import bisect
import csv
import json
import math
import numbers
import statistics
from collections import defaultdict
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any, Iterable


WEIGHT_TOLERANCE = 1e-9

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class EngineError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _validate_weight(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise EngineError("INVALID_WEIGHT", "Le poids cible doit être un nombre")
    weight = float(value)
    if not math.isfinite(weight):
        raise EngineError("INVALID_WEIGHT", "Le poids cible doit être un nombre fini")
    if not 0 < weight < 100:
        raise EngineError(
            "INVALID_WEIGHT", "Le poids cible doit être strictement entre 0 et 100"
        )
    return weight


def _normalize_symbol(symbol: Any, assets: dict[str, dict[str, str]]) -> str:
    if not isinstance(symbol, str) or not symbol.strip():
        raise EngineError("UNKNOWN_SYMBOL", "Le symbole doit être un texte non vide")
    normalized = symbol.strip().upper()
    if normalized not in assets:
        raise EngineError(
            "UNKNOWN_SYMBOL", f"Cet actif est absent du jeu de données: {normalized}"
        )
    return normalized


def _weight_map(portfolio: dict[str, Any]) -> dict[str, float]:
    weights: dict[str, float] = {}
    for position in portfolio["positions"]:
        symbol = position["symbol"]
        if symbol in weights:
            raise ValueError(f"Symbole en double dans le portefeuille: {symbol}")
        weight = float(position["weight_pct"])
        if weight < 0:
            raise ValueError(f"Pondération négative pour {symbol}")
        weights[symbol] = weight

    if not math.isclose(sum(weights.values()), 100.0, abs_tol=WEIGHT_TOLERANCE):
        raise ValueError("Les pondérations du portefeuille doivent totaliser 100 %")
    return weights


def apply_scenario(
    portfolio: dict[str, Any], scenario: dict[str, Any]
) -> dict[str, Any]:
    """Ajoute l'actif du scénario et réduit proportionnellement les positions.

    Par exemple, un poids cible de 10 % multiplie chaque poids initial par 0,90.
    Le scénario doit viser le même persona et un symbole absent du portefeuille.
    """

    if portfolio["persona_id"] != scenario["persona_id"]:
        raise ValueError("Le scénario et le portefeuille visent des personas différents")

    initial_weights = _weight_map(portfolio)
    new_symbol = scenario["symbol"]
    if new_symbol in initial_weights:
        raise EngineError(
            "ASSET_ALREADY_HELD", f"L'actif du scénario existe déjà: {new_symbol}"
        )

    target_weight = _validate_weight(scenario["target_weight_pct"])

    scale = 1.0 - target_weight / 100.0
    result = deepcopy(portfolio)
    result["positions"] = [
        {
            **position,
            "weight_pct": float(position["weight_pct"]) * scale,
        }
        for position in portfolio["positions"]
    ]
    result["positions"].append(
        {"symbol": new_symbol, "weight_pct": target_weight}
    )
    result["applied_scenario_id"] = scenario.get("scenario_id")
    _weight_map(result)
    return result


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_case(
    data_dir: Path, persona_id: str
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    personas = _read_json(data_dir / "personas.json")["personas"]
    portfolios = _read_json(data_dir / "portfolios.json")["portfolios"]
    scenarios = _read_json(data_dir / "scenarios.json")["scenarios"]

    def find(items: list[dict[str, Any]], label: str) -> dict[str, Any]:
        matches = [item for item in items if item["id" if label == "persona" else "persona_id"] == persona_id]
        if len(matches) != 1:
            raise ValueError(f"Il faut exactement un {label} pour {persona_id}")
        return matches[0]

    return find(personas, "persona"), find(portfolios, "portefeuille"), find(
        scenarios, "scénario"
    )


def load_persona_and_portfolio(
    data_dir: Path, persona_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    personas = _read_json(data_dir / "personas.json")["personas"]
    portfolios = _read_json(data_dir / "portfolios.json")["portfolios"]

    persona_matches = [item for item in personas if item["id"] == persona_id]
    if len(persona_matches) != 1:
        raise EngineError("INVALID_PERSONA", f"Persona inconnu: {persona_id}")
    portfolio_matches = [item for item in portfolios if item["persona_id"] == persona_id]
    if len(portfolio_matches) != 1:
        raise ValueError(f"Il faut exactement un portefeuille pour {persona_id}")
    return persona_matches[0], portfolio_matches[0]


def load_asset_universe(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assets = {row["ticker"]: row for row in rows}
    if len(assets) != len(rows):
        raise ValueError("L'univers contient des tickers en double")
    return assets


def load_fx_usdcad(path: Path) -> tuple[list[date], list[float]]:
    """Charge USD/CAD, exprimé en CAD pour 1 USD, et valide son inverse."""

    observations: list[tuple[date, float]] = []
    seen: set[date] = set()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            current_date = date.fromisoformat(row["date"])
            if current_date in seen:
                raise ValueError(f"Date FX en double: {current_date}")
            seen.add(current_date)
            usdcad = float(row["usdcad"])
            cadusd = float(row["cadusd"])
            if usdcad <= 0 or cadusd <= 0:
                raise ValueError(f"Taux FX non positif le {current_date}")
            if not math.isclose(usdcad * cadusd, 1.0, rel_tol=2e-6):
                raise ValueError(f"Sens de cotation FX incohérent le {current_date}")
            observations.append((current_date, usdcad))

    observations.sort()
    return [item[0] for item in observations], [item[1] for item in observations]


def _asof_fx(target: date, fx_dates: list[date], fx_rates: list[float]) -> float:
    index = bisect.bisect_right(fx_dates, target) - 1
    if index < 0:
        raise ValueError(f"Aucun taux USD/CAD disponible au {target} ou avant")
    return fx_rates[index]


def load_prices_in_cad(
    prices_path: Path,
    symbols: Iterable[str],
    assets: dict[str, dict[str, str]],
    fx_dates: list[date],
    fx_rates: list[float],
) -> dict[str, dict[date, float]]:
    """Charge adj_close et convertit les prix USD en CAD avec USD/CAD."""

    requested = set(symbols)
    missing_assets = requested.difference(assets)
    if missing_assets:
        raise EngineError(
            "UNKNOWN_SYMBOL", f"Symboles absents de l'univers: {sorted(missing_assets)}"
        )

    series: dict[str, dict[date, float]] = {symbol: {} for symbol in requested}
    with prices_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            symbol = row["ticker"]
            if symbol not in requested:
                continue
            current_date = date.fromisoformat(row["date"])
            if current_date in series[symbol]:
                raise ValueError(f"Prix en double pour {symbol} le {current_date}")
            price = float(row["adj_close"])
            if price <= 0:
                raise ValueError(f"adj_close non positif pour {symbol} le {current_date}")

            currency = row["currency"]
            if currency != assets[symbol]["currency"]:
                raise ValueError(f"Devise incohérente pour {symbol}: {currency}")
            if currency == "USD":
                price *= _asof_fx(current_date, fx_dates, fx_rates)
            elif currency != "CAD":
                raise ValueError(f"Devise non prise en charge pour {symbol}: {currency}")
            series[symbol][current_date] = price

    missing_prices = [symbol for symbol, values in series.items() if not values]
    if missing_prices:
        raise ValueError(f"Aucun prix trouvé pour: {missing_prices}")
    return series


def align_on_common_dates(
    series: dict[str, dict[date, float]],
) -> tuple[list[date], dict[str, list[float]]]:
    """Conserve uniquement l'intersection des dates de tous les actifs."""

    common_dates = set.intersection(*(set(values) for values in series.values()))
    dates = sorted(common_dates)
    if len(dates) < 2:
        raise EngineError(
            "INSUFFICIENT_DATA", "Moins de deux dates communes entre les actifs"
        )
    return dates, {
        symbol: [values[current_date] for current_date in dates]
        for symbol, values in series.items()
    }


def simulate_buy_and_hold(
    weights_pct: dict[str, float], prices: dict[str, list[float]]
) -> list[float]:
    """Investit une valeur initiale de 1 et conserve des quantités fixes."""

    if set(weights_pct) - set(prices):
        raise ValueError("Il manque des séries de prix pour le portefeuille")
    shares = {
        symbol: (weight / 100.0) / prices[symbol][0]
        for symbol, weight in weights_pct.items()
    }
    observation_count = len(next(iter(prices.values())))
    values = [
        sum(shares[symbol] * prices[symbol][index] for symbol in weights_pct)
        for index in range(observation_count)
    ]
    if not math.isclose(values[0], 1.0, abs_tol=WEIGHT_TOLERANCE):
        raise AssertionError("La valeur initiale simulée doit être 1")
    return values


def calculate_metrics(values: list[float], annualization_factor: int = 252) -> dict[str, float]:
    if len(values) < 2:
        raise ValueError("Au moins deux valeurs sont nécessaires")
    returns = [values[index] / values[index - 1] - 1.0 for index in range(1, len(values))]
    volatility = (
        statistics.stdev(returns) * math.sqrt(annualization_factor)
        if len(returns) > 1
        else 0.0
    )
    peak = values[0]
    max_drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        max_drawdown = min(max_drawdown, value / peak - 1.0)
    return {
        "total_return": values[-1] / values[0] - 1.0,
        "annualized_volatility": volatility,
        "max_drawdown": max_drawdown,
    }


def aggregate_weights_by_class(
    weights: dict[str, float], assets: dict[str, dict[str, str]]
) -> dict[str, float]:
    totals: defaultdict[str, float] = defaultdict(float)
    for symbol, weight in weights.items():
        totals[assets[symbol]["asset_class"]] += weight
    return dict(sorted(totals.items()))


def load_sources(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    wanted = {
        "assets_universe.csv": "src_assets_universe",
        "prices_daily.csv": "src_prices_daily",
        "fx_usdcad_daily.csv": "src_fx_usdcad",
    }
    return [
        {
            "id": wanted[row["file"]],
            "file": row["file"],
            "source": row["source"],
            "source_url": row["source_url"],
            "retrieved_on": row["retrieved_on"],
            "limitations": row["limitations"],
        }
        for row in rows
        if row["file"] in wanted
    ]


def team_sources() -> list[dict[str, Any]]:
    return [
        {
            "id": "src_personas",
            "file": "data/personas.json",
            "source": "Équipe AlphaForge: profils fictifs inspirés du cas officiel",
            "source_url": None,
            "retrieved_on": None,
            "limitations": "Profils de démonstration; capacité de perte, besoins de liquidités et retraits prévus inconnus.",
        },
        {
            "id": "src_portfolios",
            "file": "data/portfolios.json",
            "source": "Équipe AlphaForge: portefeuilles fictifs de démonstration",
            "source_url": None,
            "retrieved_on": None,
            "limitations": "Hypothèses de démonstration, pas des allocations recommandées ni des conseils en placement.",
        },
    ]


def _rounded(value: float) -> float:
    return round(value, 10)


def run_analysis(
    persona_id: str,
    symbol: str,
    target_weight_pct: float,
    root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    if not isinstance(persona_id, str):
        raise EngineError("INVALID_PERSONA", "Le persona doit être un texte")
    persona, initial = load_persona_and_portfolio(root / "data", persona_id)
    assets = load_asset_universe(root / "data" / "market" / "assets_universe.csv")
    symbol = _normalize_symbol(symbol, assets)
    weight = _validate_weight(target_weight_pct)
    scenario = {
        "persona_id": persona_id,
        "scenario_id": f"{persona_id}_add_{symbol.lower()}",
        "symbol": symbol,
        "target_weight_pct": weight,
    }
    return _compare(root, persona, initial, scenario)


def compare_case(root: Path, persona_id: str) -> dict[str, Any]:
    persona, initial, scenario = load_case(root / "data", persona_id)
    return _compare(root, persona, initial, scenario)


def _compare(
    root: Path,
    persona: dict[str, Any],
    initial: dict[str, Any],
    scenario: dict[str, Any],
) -> dict[str, Any]:
    dataset_dir = root / "data" / "market"
    modified = apply_scenario(initial, scenario)

    before_weights = _weight_map(initial)
    after_weights = _weight_map(modified)
    all_symbols = sorted(set(before_weights) | set(after_weights))

    assets = load_asset_universe(dataset_dir / "assets_universe.csv")
    fx_dates, fx_rates = load_fx_usdcad(dataset_dir / "fx_usdcad_daily.csv")
    raw_series = load_prices_in_cad(
        dataset_dir / "prices_daily.csv",
        all_symbols,
        assets,
        fx_dates,
        fx_rates,
    )
    dates, prices = align_on_common_dates(raw_series)

    before_values = simulate_buy_and_hold(before_weights, prices)
    after_values = simulate_buy_and_hold(after_weights, prices)
    before_metrics = calculate_metrics(before_values)
    after_metrics = calculate_metrics(after_values)

    metric_deltas = {
        metric: _rounded(after_metrics[metric] - before_metrics[metric])
        for metric in before_metrics
    }
    return {
        "analysis_type": "hypothetical_historical_comparison",
        "persona": deepcopy(persona),
        "scenario": {
            "scenario_id": scenario["scenario_id"],
            "added_symbol": scenario["symbol"],
            "target_weight_pct": scenario["target_weight_pct"],
            "funding_rule": "proportional_reduction",
        },
        "period": {
            "start": dates[0].isoformat(),
            "end": dates[-1].isoformat(),
            "common_observations": len(dates),
        },
        "currency": "CAD",
        "methodology": {
            "price_field": "adj_close",
            "fx_conversion": "Prix USD multiplié par USD/CAD (CAD pour 1 USD); dernier taux connu reporté si absent.",
            "calendar_alignment": "Intersection stricte des dates ayant un prix pour tous les actifs avant et après.",
            "simulation": "Achat aux pondérations initiales, quantités fixes, distributions reflétées par adj_close, aucun rééquilibrage périodique.",
            "volatility": "Écart-type échantillonnal des rendements entre observations communes, annualisé avec sqrt(252).",
            "funding": "Pour un poids cible p, chaque poids existant est multiplié par (1 - p/100), puis p % est attribué au nouvel actif.",
            "series_base": "Les courbes valent 100 à la première date commune et représentent la valeur du portefeuille simulé.",
            "annualization_note": "sqrt(252) est une convention approximative: l'intersection des calendriers rend les intervalles entre observations irréguliers.",
            "max_drawdown": "Plus forte baisse depuis un sommet, mesurée uniquement sur les observations retenues; une baisse entre ces dates peut être omise.",
            "weights_shown": "Les pondérations avant/après sont les allocations initiales des simulations; elles dérivent ensuite avec les performances.",
            "costs": "Frais, taxes et coûts de transaction exclus de la simulation.",
        },
        "series": {
            "dates": [current_date.isoformat() for current_date in dates],
            "before": [value * 100.0 for value in before_values],
            "after": [value * 100.0 for value in after_values],
        },
        "before": {
            "weights_by_asset_pct": before_weights,
            "weights_by_class_pct": aggregate_weights_by_class(before_weights, assets),
            "metrics": {key: _rounded(value) for key, value in before_metrics.items()},
        },
        "after": {
            "weights_by_asset_pct": after_weights,
            "weights_by_class_pct": aggregate_weights_by_class(after_weights, assets),
            "metrics": {key: _rounded(value) for key, value in after_metrics.items()},
        },
        "delta_after_minus_before": {
            "metrics": metric_deltas,
            "weights_by_asset_pct": {
                symbol: _rounded(after_weights.get(symbol, 0.0) - before_weights.get(symbol, 0.0))
                for symbol in all_symbols
            },
        },
        "sources": load_sources(dataset_dir / "sources_metadata.csv") + team_sources(),
        "limitations": [
            "Comparaison historique hypothétique; ce n'est ni une prévision ni une recommandation.",
            "Le biais du survivant de l'univers choisi en 2026 demeure présent.",
            "L'intersection stricte retire les fins de semaine crypto et les dates où un marché est fermé.",
            "Le report du taux FX concerne uniquement la conversion, jamais les prix des actifs.",
            "Les classes et secteurs décrivent les instruments de premier niveau; aucune composition interne de SPY ou QQQ n'est utilisée.",
            "La méthode acheter-et-conserver laisse les pondérations dériver après la date initiale.",
            "Les rendements historiques ne préjugent pas des rendements futurs.",
            "Frais, taxes et coûts de transaction ne sont pas modélisés.",
            "La volatilité annualisée avec sqrt(252) est approximative car les intervalles entre observations sont irréguliers.",
            "La baisse maximale peut omettre des baisses survenues entre les observations retenues.",
        ],
    }


def write_result(result: dict[str, Any], output_path: Path) -> None:
    text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.write("\n")
