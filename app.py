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
    from alphaforge.presentation import (
        ASSET_CLASS_LABELS,
        CHECK_TITLE_LABELS,
        METRIC_PRESENTATION,
        MISSING_INFORMATION_LABELS,
        STATUS_LABELS,
        TOPIC_LABELS,
        describe_metric_change,
        evidence_value_for_display,
        format_points,
        format_rate,
        format_weight,
        format_weight_delta,
        readable_label,
    )

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
    references: list[str], request: dict, response: dict, *, inside_expander: bool = False
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
    container = st.container() if inside_expander else st.expander("Preuves consultables")
    with container:
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


def translated_missing(items: list[str]) -> list[str]:
    return [readable_label(item, MISSING_INFORMATION_LABELS) for item in items]


def structured_metric_label(reference: str) -> str:
    metric_key = reference.rsplit(".", 1)[-1]
    metric = METRIC_PRESENTATION.get(metric_key, {})
    title = metric.get("title", readable_label(metric_key, {}))
    if ".before." in reference:
        return f"Avant — {title}"
    if ".after." in reference:
        return f"Après — {title}"
    if ".delta_after_minus_before." in reference:
        return f"Écart — {title}"
    return title


def render_structured_metrics(metrics: list[dict]) -> None:
    for metric in metrics:
        st.caption(
            f"{structured_metric_label(metric['evidence_ref'])} : "
            f"{evidence_value_for_display(metric['evidence_ref'], metric['value'], metric['unit'])}"
        )


def render_simulation(analysis: dict, asset: dict) -> None:
    persona = analysis["persona"]
    scenario = analysis["scenario"]
    st.subheader("Votre simulation")
    st.write(
        f"Vous consacrez **{format_weight(scenario['target_weight_pct'])}** du "
        f"portefeuille de **{persona.get('name', persona['id'].title())}** à "
        f"**{asset.get('name', scenario['added_symbol'])}** "
        f"({scenario['added_symbol']})."
    )
    st.write(
        "Les autres positions diminuent proportionnellement pour financer cet ajout."
    )
    st.caption(
        f"Comparaison historique du {analysis['period']['start']} au "
        f"{analysis['period']['end']} · {analysis['period']['common_observations']:,} "
        f"dates communes · valeurs exprimées en {analysis['currency']}"
    )


def render_summary(explanation: dict | None) -> None:
    st.subheader("Ce qu’il faut retenir")
    if explanation:
        st.write(explanation["summary"])
        st.caption(
            "Cette explication a été produite par Bedrock. L’application contrôle "
            "sa structure, ses valeurs chiffrées et ses références; elle ne certifie "
            "pas chaque nuance du texte."
        )
    else:
        st.info(
            "Les calculs sont disponibles, mais l’explication automatique n’a pas "
            "pu être produite."
        )


def render_analysis(analysis: dict, explanation: dict | None) -> None:
    st.subheader("Ce qui change")
    before, after = analysis["before"], analysis["after"]
    metric_deltas = analysis["delta_after_minus_before"]["metrics"]
    for column, key in zip(st.columns(3), METRIC_PRESENTATION):
        presentation = METRIC_PRESENTATION[key]
        column.metric(
            presentation["title"],
            format_rate(after["metrics"][key]),
            delta=format_points(metric_deltas[key]),
            delta_color="inverse" if key == "annualized_volatility" else "normal",
            help=f"{presentation['technical']} — {presentation['definition']}",
        )
        column.caption(describe_metric_change(key, metric_deltas[key]))
    if explanation:
        for change in explanation.get("changes", []):
            st.markdown(
                f"**{readable_label(change['topic'], TOPIC_LABELS)}** — "
                f"{change['message']}"
            )
            render_structured_metrics(change.get("metrics", []))
    st.dataframe(
        [
            {
                "Indicateur": presentation["title"],
                "Avant": format_rate(before["metrics"][key]),
                "Après": format_rate(after["metrics"][key]),
                "Écart": format_points(metric_deltas[key]),
            }
            for key, presentation in METRIC_PRESENTATION.items()
        ],
        hide_index=True,
        width="stretch",
    )
    st.subheader("Pondérations avant et après")
    rows = []
    for symbol in sorted(
        set(before["weights_by_asset_pct"]) | set(after["weights_by_asset_pct"])
    ):
        old = before["weights_by_asset_pct"].get(symbol, 0.0)
        new = after["weights_by_asset_pct"].get(symbol, 0.0)
        rows.append(
            {
                "Actif": symbol,
                "Avant": format_weight(old),
                "Après": format_weight(new),
                "Écart": format_weight_delta(new - old),
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


def render_priorities(
    persona_name: str, checks: list[dict], explanation: dict | None
) -> None:
    st.subheader(f"Par rapport aux priorités de {persona_name}")
    assessments = {
        item["check_id"]: item
        for item in (explanation or {}).get("profile_assessment", [])
    }
    if any("ESG" in check.get("title", "") for check in checks):
        st.caption("ESG signifie critères environnementaux, sociaux et de gouvernance.")
    if any("FNB" in (check.get("message", "") + check.get("title", "")) for check in checks):
        st.caption(
            "Un FNB est un fonds négocié en Bourse, qui regroupe plusieurs placements."
        )
    for check in checks:
        status = readable_label(check["status"], STATUS_LABELS)
        title = readable_label(check["id"], CHECK_TITLE_LABELS)
        assessment = assessments.get(check["id"])
        message = assessment["message"] if assessment else check["message"]
        content = f"**{status} — {title}**  \n{message}"
        if check["status"] == "tension":
            st.warning(content)
        elif check["status"] == "consistent":
            st.success(content)
        else:
            st.info(content)
        if assessment:
            render_structured_metrics(assessment.get("metrics", []))


def render_remaining(
    analysis: dict, checks: list[dict], explanation: dict | None
) -> None:
    st.subheader("Ce qu’il reste à savoir")
    missing = list(
        dict.fromkeys(
            item
            for check in checks
            for item in check.get("missing_information", [])
        )
    )
    for item in translated_missing(missing):
        st.markdown(f"- {item}")
    for uncertainty in (explanation or {}).get("uncertainties", []):
        st.markdown(f"- {uncertainty}")
    if not missing and not (explanation or {}).get("uncertainties"):
        st.write("Aucune information manquante supplémentaire n’est signalée.")


def render_metric_details(analysis: dict) -> None:
    with st.expander("Comprendre les chiffres"):
        for presentation in METRIC_PRESENTATION.values():
            st.markdown(f"**{presentation['title']}**")
            st.caption(f"Terme technique : {presentation['technical']}")
            st.write(presentation["definition"])
        st.markdown("**Répartition par grandes catégories**")
        for key, value in analysis["after"].get("weights_by_class_pct", {}).items():
            st.write(
                f"{readable_label(key, ASSET_CLASS_LABELS)} : {format_weight(value)}"
            )


def render_sources(
    analysis: dict,
    checks: list[dict],
    explanation: dict | None,
    request: dict,
    response: dict,
) -> None:
    with st.expander("Vérifier les sources"):
        for source in analysis.get("sources", []):
            retrieved = source.get("retrieved_on") or "date non précisée"
            label = (
                f"{source.get('file', source.get('id', 'Source'))} — "
                f"{source.get('source', 'origine non précisée')} "
                f"(extrait le {retrieved})"
            )
            url = source.get("source_url")
            st.markdown(f"- [{label}]({url})" if url and url != "n/a" else f"- {label}")
            if source.get("limitations"):
                st.caption(source["limitations"])
        for check in checks:
            for item in check.get("evidence", {}).get("assessed_evidence", []):
                publisher = item.get("publisher", "Source non précisée")
                date = item.get("date") or "date non précisée"
                url = item.get("url")
                line = f"**{publisher}** ({date}) — {item.get('claim', '')}"
                st.markdown(
                    f"- {line} [Consulter la source]({url})" if url else f"- {line}"
                )
                if item.get("company_published_source"):
                    st.caption("Source publiée par l’entreprise concernée.")
                if item.get("limitation"):
                    st.caption(item["limitation"])
        references = []
        for change in (explanation or {}).get("changes", []):
            references.extend(change.get("evidence_refs", []))
        for assessment in (explanation or {}).get("profile_assessment", []):
            references.extend(assessment.get("evidence_refs", []))
        if references:
            render_evidence_references(
                references, request, response, inside_expander=True
            )


def render_methodology(analysis: dict) -> None:
    with st.expander("Comment la comparaison est calculée"):
        for value in analysis.get("methodology", {}).values():
            st.write(value)
        st.markdown("**Limites de la comparaison**")
        for limitation in analysis.get("limitations", []):
            st.markdown(f"- {limitation}")


def render_technical_details(response: dict) -> None:
    trace = response.get("tool_trace") or (
        response.get("explanation") or {}
    ).get("tool_trace", [])
    with st.expander("Détails techniques"):
        for warning in response.get("warnings", []):
            st.warning(warning)
        if not trace:
            st.write("Aucune trace d’outil disponible.")
        for entry in trace:
            st.markdown(f"**{entry.get('tool', 'outil')} — {entry.get('status', 'inconnu')}**")
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
preferences = [
    "ESG (critères environnementaux, sociaux et de gouvernance)"
    if preference == "ESG"
    else preference
    for preference in persona["preferences"]
]
st.write("**Préférences :** " + ", ".join(preferences))
st.write(
    "**Informations inconnues :** "
    + (
        ", ".join(translated_missing(persona.get("missing_information", [])))
        or "Aucune indiquée."
    )
)
st.markdown("**Portefeuille fictif initial**")
st.dataframe(
    [{"Actif": symbol, "Pondération": format_weight(weight)}
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
    analyzed_request = request_key(persona["id"], selected_symbol, target_weight)
    try:
        with st.spinner(
            "Nous comparons les portefeuilles et préparons votre explication…"
        ):
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
    stored_analysis = response.get("analysis") or {}
    stored_persona = stored_analysis.get("persona", {})
    stored_name = stored_persona.get("name", stored_request["persona_id"].title())
    st.markdown(
        "**Résultat conservé :** "
        f"{stored_name} · {stored_request['symbol']} · "
        f"{format_weight(stored_request['target_weight_pct'])}"
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
            "Nous n’avons pas pu produire le rapport. Vérifiez les choix du "
            "formulaire, puis relancez l’analyse."
        )
        with st.expander("Détails techniques"):
            st.write(
                f"{error.get('code', 'INTERNAL_ERROR')} — "
                f"{error.get('message', 'Erreur non précisée.')}"
            )
    else:
        analysis = response.get("analysis")
        checks = response.get("checks") or []
        if status == "success":
            st.success("Votre rapport est prêt.")
        elif status == "partial":
            st.warning(
                "Les calculs sont disponibles, mais l’explication automatique "
                "n’a pas pu être produite."
            )
        if analysis:
            explanation = response.get("explanation")
            render_simulation(
                analysis, assets.get(stored_request["symbol"], {})
            )
            render_summary(explanation)
            render_analysis(analysis, explanation)
            render_priorities(stored_name, checks, explanation)
            render_remaining(analysis, checks, explanation)
            render_metric_details(analysis)
            render_sources(
                analysis, checks, explanation, stored_request, response
            )
            render_methodology(analysis)
            render_technical_details(response)

st.caption(
    "Simulation académique historique, pas une prévision ni un conseil en placement. "
    "Aucune transaction n’est exécutée."
)
