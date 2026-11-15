"""Interface Streamlit de simulation des portefeuilles AlphaForge."""

from __future__ import annotations

import json
import re
from pathlib import Path
import streamlit as st

try:
    from agent.context import create_request_context
    from agent.evidence import resolve_evidence_reference
    from agent.service import analyze_request
    from alphaforge.engine import load_asset_universe

    ENGINE_AVAILABLE = True
except ImportError:
    ENGINE_AVAILABLE = False


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
ASSETS_PATH = DATA_DIR / "market" / "assets_universe.csv"
CSS_PATH = ROOT / "styles" / "style.css"

THEMES = {
    "Sombre": {
        "page-bg": "#0B1F14", "page-glow": "#1D4A30",
        "surface-bg": "#12331F", "surface-bg-2": "#0E2818",
        "text-color": "#F2F7F3", "secondary-text": "#A8BDAF",
        "border-color": "#2C4B39", "accent": "#B7F05A",
        "button-bg": "#B7F05A", "button-text": "#0B1F14",
        "input-bg": "#0F2A1B",
    },
    "Clair": {
        "page-bg": "#F4F9E8", "page-glow": "#E3F2B8",
        "surface-bg": "#FFFFFF", "surface-bg-2": "#F1F7E0",
        "text-color": "#0B1F14", "secondary-text": "#4A5F52",
        "border-color": "#C9DBB0", "accent": "#2E7D32",
        "button-bg": "#123524", "button-text": "#DFFF00",
        "input-bg": "#FFFFFF",
    },
}


def load_css(path: Path) -> str:
    css = path.read_text(encoding="utf-8")
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    return re.sub(r"\s+", " ", css).strip()


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def format_pct(value: float, signed: bool = False) -> str:
    return f"{value:+.2%}" if signed else f"{value:.2%}"


def format_points(value: float) -> str:
    return f"{value * 100:+.2f} points de pourcentage"


def asset_weights(portfolio: dict) -> dict[str, float]:
    return {
        position["symbol"]: float(position["weight_pct"])
        for position in portfolio["positions"]
    }


def request_key(persona_id: str, symbol: str, weight: float) -> dict:
    return {
        "persona_id": persona_id,
        "symbol": symbol,
        "target_weight_pct": float(weight),
    }


def render_evidence_references(
    references: list[str], request: dict, response: dict
) -> None:
    if not references:
        return
    context = create_request_context(
        request["persona_id"],
        request["symbol"],
        request["target_weight_pct"],
        root=ROOT,
    )
    context.analysis = response.get("analysis")
    context.checks = response.get("checks")
    with st.expander("Preuves consultables"):
        for reference in dict.fromkeys(references):
            resolved = resolve_evidence_reference(context, reference)
            st.markdown(f"**`{reference}`**")
            if resolved["status"] == "resolved":
                value = resolved["value"]
                if isinstance(value, (dict, list)):
                    st.json(value)
                else:
                    st.write(value)
            else:
                st.warning(resolved.get("reason", "Référence introuvable."))


def render_checks(checks: list[dict], request: dict, response: dict) -> None:
    st.markdown("**Contrôles du profil**")
    for finding in checks:
        message = f"**{finding['title']}** — {finding['message']}"
        if finding["status"] == "tension":
            st.warning(message)
        elif finding["status"] == "consistent":
            st.success(message)
        else:
            st.info(message)
        if finding.get("missing_information"):
            st.caption(
                "Informations manquantes : "
                + ", ".join(finding["missing_information"])
            )
        render_evidence_references(
            finding.get("evidence_refs", []), request, response
        )
        evidence = finding.get("evidence", {})
        assessed_sources = evidence.get("assessed_evidence", [])
        if assessed_sources:
            with st.expander(f"Preuves pour : {finding['title']}"):
                for item in assessed_sources:
                    publisher = item.get("publisher", "Source non précisée")
                    evidence_date = item.get("date") or "Date non précisée"
                    claim = item.get("claim", "Énoncé non précisé")
                    url = item.get("url")
                    line = f"- **{publisher}** ({evidence_date}) : {claim}"
                    st.markdown(
                        f"{line} [Consulter la source]({url})" if url else line
                    )
                    if item.get("limitation"):
                        st.caption(item["limitation"])
        elif evidence:
            with st.expander(f"Éléments examinés : {finding['title']}"):
                st.json(evidence)


def render_explanation(explanation: dict, request: dict, response: dict) -> None:
    st.subheader("Explication et alertes")
    st.write(explanation["summary"])
    st.caption("Explication produite par AWS Bedrock et validée par AlphaForge.")
    for change in explanation.get("changes", []):
        st.markdown(f"**Changement — {change['topic']}**")
        st.write(change["message"])
        render_evidence_references(change.get(
            "evidence_refs", []), request, response)
    if explanation.get("profile_assessment"):
        st.markdown("**Évaluation selon le profil**")
    for assessment in explanation.get("profile_assessment", []):
        st.write(
            f"**{assessment['check_id']} — {assessment['status']}** : "
            f"{assessment['message']}"
        )
        if assessment.get("missing_information"):
            st.caption(
                "Informations manquantes : "
                + ", ".join(assessment["missing_information"])
            )
        render_evidence_references(
            assessment.get("evidence_refs", []), request, response
        )
    if explanation.get("uncertainties"):
        st.markdown("**Incertitudes**")
        for uncertainty in explanation["uncertainties"]:
            st.markdown(f"- {uncertainty}")


def render_analysis(analysis: dict) -> None:
    st.caption(
        f"Période : {analysis['period']['start']} au {analysis['period']['end']} · "
        f"{analysis['period']['common_observations']:,} dates communes · "
        f"devise : {analysis['currency']}"
    )
    before, after = analysis["before"], analysis["after"]
    metric_deltas = analysis["delta_after_minus_before"]["metrics"]
    metric_labels = {
        "total_return": "Rendement total",
        "annualized_volatility": "Volatilité annualisée",
        "max_drawdown": "Recul maximal",
    }
    for column, key in zip(st.columns(3), metric_labels):
        column.metric(
            metric_labels[key],
            format_pct(after["metrics"][key]),
            delta=format_points(metric_deltas[key]),
            delta_color="inverse" if key == "annualized_volatility" else "normal",
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
    rows = []
    for symbol in sorted(
        set(before["weights_by_asset_pct"]) | set(
            after["weights_by_asset_pct"])
    ):
        old = before["weights_by_asset_pct"].get(symbol, 0.0)
        new = after["weights_by_asset_pct"].get(symbol, 0.0)
        rows.append(
            {
                "Actif": symbol,
                "Avant (%)": f"{old:.1f}",
                "Après (%)": f"{new:.1f}",
                "Écart (points)": f"{new - old:+.1f}",
            }
        )
    st.dataframe(rows, hide_index=True, width="stretch")
    st.subheader("Évolution historique (base 100)")
    series = analysis.get("series")
    if series:
        st.line_chart(
            {
                "Date": series["dates"],
                "Portefeuille initial": series["before"],
                "Après scénario": series["after"],
            },
            x="Date",
            y=["Portefeuille initial", "Après scénario"],
        )
    else:
        st.warning("Les séries temporelles sont absentes; courbe indisponible.")


def render_methodology(analysis: dict) -> None:
    with st.expander("Méthode, sources et limites"):
        for value in analysis.get("methodology", {}).values():
            st.write(value)
        st.markdown("**Sources**")
        for source in analysis.get("sources", []):
            retrieved = source.get("retrieved_on") or "date non précisée"
            label = (
                f"{source.get('file', source.get('id', 'Source'))} — "
                f"{source.get('source', 'origine non précisée')} "
                f"(extrait le {retrieved})"
            )
            url = source.get("source_url")
            st.markdown(f"- [{label}]({url})" if url and url !=
                        "n/a" else f"- {label}")
            if source.get("limitations"):
                st.caption(source["limitations"])
        st.markdown("**Limites de l’analyse**")
        for limitation in analysis.get("limitations", []):
            st.markdown(f"- {limitation}")


def render_reasoning(analysis: dict) -> None:
    """Présente les bases et limites des résultats calculés par le moteur."""
    method = analysis.get("methodology", {})
    period = analysis.get("period", {})
    scenario = analysis.get("scenario", {})
    before = analysis.get("before", {})
    after = analysis.get("after", {})
    deltas = analysis.get("delta_after_minus_before", {})
    before_metrics = before.get("metrics", {})
    after_metrics = after.get("metrics", {})
    metric_deltas = deltas.get("metrics", {})
    weights_before = before.get("weights_by_asset_pct", {})
    weights_after = after.get("weights_by_asset_pct", {})
    symbol = scenario.get("added_symbol", "l’actif sélectionné")
    target = scenario.get("target_weight_pct")

    with st.expander("Comment AlphaForge arrive à cette analyse", expanded=False):
        st.write(
            "Cette explication décrit les calculs déterministes du moteur. "
            "Elle s’appuie sur les résultats affichés et ne prétend pas révéler "
            "un raisonnement interne caché du modèle d’IA."
        )
        st.markdown("**Démarche**")
        st.markdown(
            "1. Le moteur sélectionne les prix ajustés des actifs du portefeuille "
            "initial et du scénario.\n"
            "2. Il convertit en CAD les prix libellés en USD avec le taux USD/CAD, "
            "puis retient les dates communes aux actifs.\n"
            "3. Il simule un portefeuille acheter-conserver avant et après le "
            "changement, puis compare rendement total, volatilité annualisée, "
            "recul maximal et pondérations."
        )
        st.markdown("**Données utilisées**")
        st.write(
            f"Période commune : {period.get('start', 'inconnue')} au "
            f"{period.get('end', 'inconnue')} ({period.get('common_observations', 'nombre inconnu')} observations), en {analysis.get('currency', 'devise inconnue')}."
        )
        st.write(
            "Les entrées de marché sont les prix ajustés et les taux de change "
            "décrits dans les sources de l’analyse. Les portefeuilles et personas "
            "sont des données fictives de démonstration."
        )
        sources = analysis.get("sources", [])
        if sources:
            st.caption(
                "Sources présentes dans cette analyse : "
                + "; ".join(
                    source.get("file", source.get("id", "source"))
                    for source in sources
                )
            )
        st.markdown("**Facteurs qui influencent les résultats**")
        if target is not None:
            st.write(
                f"Le scénario attribue {target:g} % à {symbol}; le financement "
                "provient d’une réduction proportionnelle des positions initiales."
            )
        old, new = weights_before.get(
            symbol, 0.0), weights_after.get(symbol, 0.0)
        st.write(
            f"La pondération de {symbol} passe de {old:.1f} % à {new:.1f} %. "
            "Les résultats dépendent aussi de la période retenue, des actifs "
            "présents et de l’alignement des dates."
        )
        metric_names = {
            "total_return": "Rendement total",
            "annualized_volatility": "Volatilité annualisée",
            "max_drawdown": "Recul maximal",
        }
        for key, label in metric_names.items():
            if key not in before_metrics or key not in after_metrics:
                continue
            delta = metric_deltas.get(key)
            if delta is None:
                continue
            direction = "augmente" if delta > 0 else "diminue" if delta < 0 else "ne change pas"
            st.write(
                f"{label} : {direction} de {format_points(delta)} "
                f"({format_pct(before_metrics[key])} avant, "
                f"{format_pct(after_metrics[key])} après)."
            )
        st.caption(
            "Ces écarts décrivent la comparaison calculée; ils n’isolent pas "
            "l’effet causal d’un seul actif et ne permettent pas d’attribuer "
            "les variations à un facteur de marché particulier."
        )
        for key in ("price_field", "fx_conversion", "calendar_alignment", "simulation", "volatility", "max_drawdown", "costs"):
            if method.get(key):
                st.caption(
                    f"{key.replace('_', ' ').capitalize()} : {method[key]}")
        st.markdown("**Limites des conclusions**")
        st.write(
            "Cette simulation historique hypothétique ne prédit pas les rendements "
            "futurs et ne constitue pas une recommandation. Les hypothèses de "
            "données, les frais exclus et les limites propres aux indicateurs "
            "peuvent changer l’interprétation."
        )
        for limitation in analysis.get("limitations", []):
            st.markdown(f"- {limitation}")


def render_tool_trace(response: dict) -> None:
    trace = response.get("tool_trace") or (
        response.get("explanation") or {}
    ).get("tool_trace", [])
    if not trace:
        return
    with st.expander("Traces factuelles des outils"):
        for entry in trace:
            st.markdown(
                f"**{entry.get('tool', 'outil')} — {entry.get('status', 'inconnu')}**")
            st.write("Arguments validés :", entry.get("arguments", {}))
            st.caption(
                "Origine d’exécution : "
                + entry.get("execution_origin", "non précisée")
            )


st.set_page_config(
    page_title="AlphaForge AI - Datathon Polyfinances", layout="wide")

theme = st.radio(
    "Thème de l’interface",
    ["Clair", "Sombre"],
    horizontal=True,
    key="app_theme",
)

try:
    css = CSS_PATH.read_text(encoding="utf-8")
except OSError as exc:
    st.error(
        f"Impossible de charger la feuille de style {CSS_PATH.name} : {exc}")
    st.stop()
variables = " ".join(f"--{k}: {v};" for k, v in THEMES[theme].items())
color_scheme = "dark" if theme == "Sombre" else "light"
st.html(
    f"<style>:root {{ {variables} color-scheme: {color_scheme}; }} {css}</style>")

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
    analyzed_request = request_key(
        persona["id"], selected_symbol, target_weight)
    try:
        with st.spinner("Analyse du changement avec AWS Bedrock…"):
            response = analyze_request(
                persona["id"], selected_symbol, target_weight
            )
    except Exception:
        response = {
            "status": "error",
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Le service d’analyse a rencontré une erreur inattendue.",
            },
        }
    st.session_state["analyzed_request"] = analyzed_request
    st.session_state["analysis_response"] = response

stored_request = st.session_state.get("analyzed_request")
response = st.session_state.get("analysis_response")
current_request = request_key(persona["id"], selected_symbol, target_weight)

if stored_request and response:
    st.markdown(
        "**Résultat conservé :** "
        f"{stored_request['persona_id']} / {stored_request['symbol']} / "
        f"{stored_request['target_weight_pct']:g} %"
    )
    if current_request != stored_request:
        st.warning(
            "Le formulaire vise maintenant un autre scénario. Les résultats "
            "ci-dessous correspondent encore à la demande conservée; cliquez "
            "sur « Analyser le changement » pour lancer une nouvelle analyse."
        )

    status = response.get("status")
    if status == "error":
        error = response.get("error", {})
        st.error(
            f"Analyse impossible ({error.get('code', 'INTERNAL_ERROR')}) : "
            f"{error.get('message', 'Erreur non précisée.')}"
        )
    else:
        analysis = response.get("analysis")
        checks = response.get("checks") or []
        if status == "success":
            st.success("Analyse AlphaForge et explication Bedrock terminées.")
        elif status == "partial":
            st.warning(
                "Analyse partielle : les calculs disponibles sont conservés, "
                "mais aucune explication IA validée n’est présentée."
            )
        for warning in response.get("warnings", []):
            st.warning(warning)
        if analysis:
            render_analysis(analysis)
            render_reasoning(analysis)
        render_checks(checks, stored_request, response)
        explanation = response.get("explanation")
        if explanation:
            render_explanation(explanation, stored_request, response)
        elif status == "partial":
            st.info("Explication Bedrock validée indisponible pour cette réponse.")
        if analysis:
            render_methodology(analysis)
        render_tool_trace(response)

st.caption(
    "Simulation académique historique, pas une prévision ni un conseil en placement. "
    "Aucune transaction n’est exécutée."
)
