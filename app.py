"""Interface Streamlit de simulation des portefeuilles AlphaForge."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

try:
    from alphaforge.engine import run_analysis, load_asset_universe

    ENGINE_AVAILABLE = True
except ImportError:
    ENGINE_AVAILABLE = False


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
ASSETS_PATH = DATA_DIR / "market" / "assets_universe.csv"
CSS_PATH = ROOT / "styles" / "style.css"

# Variables de couleur par thème. "Système" n'est pas listé : le thème
# Streamlit par défaut est conservé tel quel.
THEMES = {
    "Clair": {
        "page-bg": "#DFFF00",
        "surface-bg": "#F4FFB3",
        "text-color": "#000000",
        "secondary-text": "#333333",
        "border-color": "#829900",
        "button-bg": "#000000",
        "button-text": "#DFFF00",
        "input-bg": "#F4FFB3",
    },
    "Sombre": {
        "page-bg": "#123524",
        "surface-bg": "#1B4933",
        "text-color": "#FFFFFF",
        "secondary-text": "#D0DED4",
        "border-color": "#527A62",
        "button-bg": "#FFFFFF",
        "button-text": "#123524",
        "input-bg": "#1B4933",
    },
}


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def format_pct(value: float, signed: bool = False) -> str:
    return f"{value:+.2%}" if signed else f"{value:.2%}"


def format_points(value: float) -> str:
    return f"{value * 100:+.2f} points"


def asset_weights(portfolio: dict) -> dict[str, float]:
    return {
        position["symbol"]: float(position["weight_pct"])
        for position in portfolio["positions"]
    }


def fallback_explanation(persona: dict, result: dict) -> str:
    metrics = result["after"]["metrics"]
    delta = result["delta_after_minus_before"]["metrics"]
    symbol = result["scenario"]["added_symbol"]
    target = result["scenario"]["target_weight_pct"]
    return (
        f"Le scénario ajoute {symbol} à {target:g} % au portefeuille de "
        f"{persona['name']}, dont l’objectif est « {persona['objective']} ». "
        f"Dans la période observée, le rendement total est de "
        f"{format_pct(metrics['total_return'])} ({format_points(delta['total_return'])} "
        f"par rapport au portefeuille initial), la volatilité annualisée de "
        f"{format_pct(metrics['annualized_volatility'])} "
        f"({format_points(delta['annualized_volatility'])} d’écart) et le recul "
        f"maximal de {format_pct(metrics['max_drawdown'])} "
        f"({format_points(delta['max_drawdown'])} d’écart). Ces constats décrivent "
        "la période historique simulée et ne préjugent pas des résultats futurs."
    )


st.set_page_config(
    page_title="AlphaForge AI - Datathon Polyfinances", layout="wide")

# Sélection du thème
theme = st.radio(
    "Thème de l’interface",
    ["Système", "Clair", "Sombre"],
    horizontal=True,
    key="app_theme"
)

# Injection du thème : les variables CSS sont définies ici, depuis la valeur
# choisie, plutôt que de deviner l'état du bouton radio dans le DOM.
if theme in THEMES:
    css_variables = "\n".join(
        f"--{name}: {value};" for name, value in THEMES[theme].items()
    )
    css = CSS_PATH.read_text(encoding="utf-8")
    st.markdown(
        f"<style>:root {{\n{css_variables}\n}}\n{css}</style>",
        unsafe_allow_html=True,
    )

st.title("AlphaForge AI : comparaison de portefeuilles")
st.write(
    "Simulez l’ajout d’un actif au portefeuille fictif d’un persona et comparez "
    "les résultats historiques."
)

try:
    personas = read_json(DATA_DIR / "personas.json")["personas"]
    portfolios_by_id = {
        portfolio["persona_id"]: portfolio
        for portfolio in read_json(DATA_DIR / "portfolios.json")["portfolios"]
    }
    scenarios_by_id = {
        scenario["persona_id"]: scenario
        for scenario in read_json(DATA_DIR / "scenarios.json")["scenarios"]
    }
    assets = load_asset_universe(ASSETS_PATH) if ENGINE_AVAILABLE else {}
except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
    st.error(f"Impossible de charger les données du projet : {exc}")
    st.stop()

persona_by_name = {persona["name"]: persona for persona in personas}
persona = persona_by_name[st.selectbox(
    "Choisissez un persona", list(persona_by_name))]
portfolio = portfolios_by_id[persona["id"]]
scenario = scenarios_by_id[persona["id"]]
starting_weights = asset_weights(portfolio)

st.subheader(f"Profil : {persona['name']}")
st.write(f"**Objectif :** {persona['objective']}")
horizon_end = persona["horizon_years_max"]
horizon = (
    f"{persona['horizon_years_min']}–{horizon_end} ans"
    if horizon_end is not None
    else f"{persona['horizon_years_min']} ans et plus"
)
st.write(f"**Horizon :** {horizon}")
st.write("**Préférences :** " + ", ".join(persona["preferences"]))
st.write(
    "**Informations inconnues :** "
    + (", ".join(persona.get("missing_information", [])) or "Aucune indiquée.")
)
st.markdown("**Portefeuille fictif initial**")
st.dataframe(
    [{"Actif": symbol, "Pondération": f"{weight:.1f} %"}
     for symbol, weight in starting_weights.items()],
    hide_index=True,
    width="stretch",
)
st.caption(portfolio.get("construction_note", "Hypothèse pédagogique."))
if portfolio.get("esg_evidence_limitations"):
    st.warning(portfolio["esg_evidence_limitations"])

st.info(
    "Le scénario est une hypothèse pédagogique, pas une recommandation. "
    "Le poids ajouté est financé par une réduction proportionnelle des positions initiales."
)

available_symbols = sorted(set(assets) - set(starting_weights))
if not ENGINE_AVAILABLE:
    st.error("Le moteur local est indisponible; les scénarios personnalisés ne peuvent pas être calculés.")
    st.stop()
if not available_symbols:
    st.error("Aucun actif disponible à ajouter au portefeuille.")
    st.stop()

default_symbol = scenario["symbol"]
default_index = available_symbols.index(
    default_symbol) if default_symbol in available_symbols else 0
with st.form("custom_scenario_form"):
    col_symbol, col_weight = st.columns(2)
    with col_symbol:
        selected_symbol = st.selectbox(
            "Actif à ajouter", available_symbols, index=default_index
        )
    with col_weight:
        target_weight = st.slider(
            "Poids cible (%)", min_value=1.0, max_value=50.0,
            value=float(scenario["target_weight_pct"]), step=0.5,
        )
    submitted = st.form_submit_button("Analyser le changement", type="primary")

if submitted:
    try:
        with st.spinner("Calcul de la simulation historique…"):
            result = run_analysis(
                persona["id"],
                selected_symbol,
                target_weight,
                root=ROOT,
            )
    except (OSError, KeyError, ValueError, ZeroDivisionError) as exc:
        st.error(f"Le calcul n’a pas pu être effectué : {exc}")
        st.stop()

    st.success("Simulation historique calculée.")
    st.caption(
        f"Période : {result['period']['start']} au {result['period']['end']} · "
        f"{result['period']['common_observations']:,} dates communes · devise : {result['currency']}"
    )
    before, after = result["before"], result["after"]
    metric_deltas = result["delta_after_minus_before"]["metrics"]
    metric_labels = {
        "total_return": "Rendement total",
        "annualized_volatility": "Volatilité annualisée",
        "max_drawdown": "Recul maximal",
    }
    metric_columns = st.columns(3)
    for column, key in zip(metric_columns, metric_labels):
        column.metric(
            metric_labels[key], format_pct(after["metrics"][key]),
            delta=format_points(metric_deltas[key]),
            delta_color=(
                "inverse" if key == "annualized_volatility" else "normal"
            ),
            help="Écart après moins avant, en points de pourcentage.",
        )
    st.dataframe(
        [
            {
                "Indicateur": label,
                "Avant": format_pct(before["metrics"][key]),
                "Après": format_pct(after["metrics"][key]),
                "Écart": format_points(metric_deltas[key]),
            }
            for key, label in metric_labels.items()
        ],
        hide_index=True,
        width="stretch",
    )

    st.subheader("Pondérations avant et après")
    union = sorted(set(before["weights_by_asset_pct"])
                   | set(after["weights_by_asset_pct"]))
    rows = []
    for symbol in union:
        old = before["weights_by_asset_pct"].get(symbol, 0.0)
        new = after["weights_by_asset_pct"].get(symbol, 0.0)
        rows.append({
            "Actif": symbol, "Avant (%)": f"{old:.1f}",
            "Après (%)": f"{new:.1f}", "Écart (points)": f"{new - old:+.1f}",
        })
    st.dataframe(rows, hide_index=True, width="stretch")

    st.subheader("Évolution historique (base 100)")
    series = result.get("series")
    if series:
        st.line_chart(
            {
                "Date": series["dates"],
                "Portefeuille initial": series["before"],
                "Après scénario": series["after"],
            },
            x="Date",
            y=["Portefeuille initial", "Après scénario"],
            x_label="Date", y_label="Valeur de 100 $ investis (CAD)",
        )
    else:
        st.warning(
            "Les séries temporelles ne sont pas incluses dans ce résultat; courbe indisponible.")

    st.subheader("Explication et alertes")
    st.write(fallback_explanation(persona, result))
    st.caption(
        "Explication locale déterministe. "
        "L’agent IA et les contrôles des profils restent à intégrer."
    )

    if persona["id"] == "mateo" and selected_symbol in {"XOM", "TSLA", "CNQ.TO", "ENB.TO"}:
        st.warning(
            f"La compatibilité ESG de {selected_symbol} demande une vérification avec des preuves datées; "
            "le jeu de prix ne permet pas de conclure sur ce point."
        )
    if persona["id"] == "robert" and selected_symbol in {"BTC-USD", "ETH-USD", "NVDA", "TSLA"}:
        st.warning(
            f"L’ajout de {selected_symbol} mérite un examen particulier au regard de l’objectif "
            "de préservation du capital de Robert. Cette alerte ne constitue pas une mesure ESG ou un blocage automatique."
        )

    with st.expander("Méthode, sources et limites"):
        st.write(result["methodology"]["simulation"])
        st.write(result["methodology"]["calendar_alignment"])
        st.write(result["methodology"]["fx_conversion"])
        st.markdown("**Sources**")
        for source in result["sources"]:
            label = f"{source['file']} — {source['source']} (extrait le {source['retrieved_on']})"
            if source.get("source_url") and source["source_url"] != "n/a":
                st.markdown(f"- [{label}]({source['source_url']})")
            else:
                st.markdown(f"- {label}")
            if source.get("limitations"):
                st.caption(source["limitations"])
        st.markdown("**Limites de l’analyse**")
        for limitation in result["limitations"]:
            st.markdown(f"- {limitation}")

st.caption(
    "Simulation académique historique, pas une prévision ni un conseil en placement. "
    "Aucune transaction n’est exécutée."
)
