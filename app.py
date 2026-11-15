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
        CHECK_TITLE_LABELS,
        METRIC_PRESENTATION,
        SOURCE_PRESENTATION,
        STATUS_LABELS,
        build_main_summary,
        describe_metric_change,
        format_date_fr,
        format_rate,
        format_weight,
        format_weight_delta,
        has_unsafe_main_narrative,
        join_french_list,
        missing_information_phrases,
        persona_possessive,
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


def render_simulation(analysis: dict, asset: dict) -> None:
    persona = analysis["persona"]
    scenario = analysis["scenario"]
    asset_name = asset.get("name", "cet actif")
    st.subheader("Votre simulation")
    st.write(
        f"Vous ajoutez **{asset_name}** à hauteur de "
        f"**{format_weight(scenario['target_weight_pct'])}** du portefeuille "
        f"{persona_possessive(persona.get('name', ''))}."
    )
    st.write("Les autres placements diminuent proportionnellement.")
    currency = (
        "dollars canadiens"
        if analysis.get("currency") == "CAD"
        else readable_label(analysis.get("currency", ""), {})
    )
    st.caption(
        f"Du {format_date_fr(analysis['period']['start'])} au "
        f"{format_date_fr(analysis['period']['end'])} · Montants en {currency}."
    )


def render_summary(
    analysis: dict, asset_name: str, explanation: dict | None
) -> None:
    st.subheader("En quelques mots")
    st.write(
        build_main_summary(
            analysis,
            analysis["persona"],
            asset_name,
            explanation,
        )
    )


def render_analysis(analysis: dict) -> None:
    st.subheader("Comparaisons avant/après")
    before, after = analysis["before"], analysis["after"]
    metric_deltas = analysis["delta_after_minus_before"]["metrics"]
    for column, key in zip(st.columns(3), METRIC_PRESENTATION):
        presentation = METRIC_PRESENTATION[key]
        column.metric(
            presentation["title"],
            f"{format_rate(before['metrics'][key])} avant / "
            f"{format_rate(after['metrics'][key])} après",
            help=presentation["definition"],
        )
        column.caption(describe_metric_change(key, metric_deltas[key]))


def render_weight_details(
    analysis: dict, assets: dict[str, dict]
) -> None:
    with st.expander("Pondérations détaillées"):
        before, after = analysis["before"], analysis["after"]
        rows = []
        for symbol in sorted(
            set(before["weights_by_asset_pct"])
            | set(after["weights_by_asset_pct"])
        ):
            asset_name = assets.get(symbol, {}).get("name", "Autre placement")
            old = before["weights_by_asset_pct"].get(symbol, 0.0)
            new = after["weights_by_asset_pct"].get(symbol, 0.0)
            rows.append(
                {
                    "Placement": asset_name,
                    "Avant": format_weight(old),
                    "Après": format_weight(new),
                    "Écart": format_weight_delta(new - old),
                }
            )
        st.dataframe(rows, hide_index=True, width="stretch")


def render_chart(analysis: dict, asset_name: str) -> None:
    st.subheader("Évolution historique")
    series = analysis.get("series")
    if series:
        st.line_chart(
            {
                "Date": series["dates"],
                "Portefeuille initial": series["before"],
                f"Portefeuille avec {asset_name}": series["after"],
            },
            x="Date",
            y=["Portefeuille initial", f"Portefeuille avec {asset_name}"],
        )
        st.caption(
            "Les deux courbes partent de la même base et illustrent leur "
            "évolution relative."
        )
    else:
        st.warning("La courbe n’est pas disponible pour ce scénario.")


def fund_composition_is_unknown(checks: list[dict]) -> bool:
    check_by_id = {check["id"]: check for check in checks}
    grouped_ids = {"concentration", "diversification", "etf_overlap"}
    grouped_checks = [check_by_id[key] for key in grouped_ids if key in check_by_id]
    return (
        len(grouped_checks) == len(grouped_ids)
        and all(
            item["status"] == "insufficient_information"
            and {"etf_holdings", "sector_exposures"}
            .intersection(item.get("missing_information", []))
            for item in grouped_checks
        )
    )


def render_priorities(
    persona: dict,
    checks: list[dict],
    explanation: dict | None,
    asset_name: str,
) -> None:
    st.subheader("Ce que cela signifie pour le profil")
    assessment_by_id = {
        item["check_id"]: item
        for item in (explanation or {}).get("profile_assessment", [])
    }

    grouped_ids = {"concentration", "diversification", "etf_overlap"}
    findings_shown = 0
    displayed_findings: set[str] = set()

    def show_finding(message: str) -> None:
        nonlocal findings_shown
        if findings_shown < 3 and message not in displayed_findings:
            st.markdown(message)
            displayed_findings.add(message)
            findings_shown += 1

    if fund_composition_is_unknown(checks):
        show_finding(
            f"Nous ne savons pas quelle part de {asset_name} est déjà détenue "
            "à travers les fonds du portefeuille."
        )
        handled_ids = grouped_ids
    else:
        handled_ids = set()

    for check in checks:
        if check["id"] in handled_ids:
            continue
        status = check["status"]
        if status == "insufficient_information":
            continue

        model_message = assessment_by_id.get(check["id"], {}).get("message")
        if not has_unsafe_main_narrative(model_message):
            show_finding(model_message)
        elif status == "tension":
            objective = persona.get("objective", "ce profil")
            objective = objective[:1].lower() + objective[1:]
            show_finding(
                f"Le contrôle signale un point à examiner au regard de "
                f"l’objectif de {objective} "
                f"{persona_possessive(persona['name'])}."
            )


def render_remaining(persona: dict, checks: list[dict]) -> None:
    st.subheader("Les informations qui manquent")
    missing = list(persona.get("missing_information", []))
    for check in checks:
        missing.extend(check.get("missing_information", []))
    if fund_composition_is_unknown(checks):
        missing = [
            item
            for item in missing
            if item not in {"etf_holdings", "sector_exposures"}
        ]
    phrases = missing_information_phrases(missing, persona["name"])
    if phrases:
        st.write(f"Nous ne connaissons pas encore : {join_french_list(phrases)}.")
    else:
        st.write("Aucune information manquante supplémentaire n’est signalée.")


def render_methodology() -> None:
    with st.expander("Comprendre le calcul"):
        st.markdown(
            "- Les deux portefeuilles sont comparés sur les mêmes dates, "
            "lorsque les données de tous les placements sont disponibles."
        )
        st.markdown(
            "- Les valeurs sont exprimées en dollars canadiens; les prix en "
            "dollars américains sont convertis avec le taux de change."
        )
        st.markdown(
            "- Les placements sont conservés sans rééquilibrage; leurs "
            "pondérations évoluent avec les prix."
        )
        st.markdown("- Les frais et les taxes ne sont pas inclus.")


def render_sources(analysis: dict, checks: list[dict]) -> None:
    with st.expander("Consulter les sources"):
        for source in analysis.get("sources", []):
            source_id = source.get("id", "")
            organization, role = SOURCE_PRESENTATION.get(
                source_id, ("Organisme non précisé", "document de référence")
            )
            retrieved = source.get("retrieved_on")
            date_label = (
                f" · consulté le {format_date_fr(retrieved)}"
                if retrieved
                else " · date non précisée"
            )
            source_name = f"{organization} — {role}"
            title = source.get("title") or source.get("file") or "Document source"
            url = source.get("source_url")
            st.markdown(f"**{source_name}**{date_label}")
            st.markdown(
                f"- [{title}]({url})" if url and url != "n/a" else f"- {title}"
            )

        for check in checks:
            for item in check.get("evidence", {}).get("assessed_evidence", []):
                publisher = item.get("publisher", "Organisme non précisé")
                title = item.get("title", "Document source")
                date_value = item.get("date")
                date_type = (
                    "publié le"
                    if item.get("date_type") == "publication"
                    else "consulté le"
                )
                date_label = (
                    f" · {date_type} {format_date_fr(date_value)}"
                    if date_value
                    else ""
                )
                url = item.get("url")
                st.markdown(
                    f"**{publisher} — document associé au contrôle ESG**"
                    f"{date_label}"
                )
                st.markdown(
                    f"- [{title}]({url})" if url else f"- {title}"
                )


def render_technical_details(
    response: dict,
    analysis: dict | None,
    checks: list[dict],
    request: dict,
) -> None:
    with st.expander("Détails techniques"):
        for warning in response.get("warnings", []):
            st.warning(warning)
        if response.get("error"):
            st.json(response["error"])
        if analysis:
            st.markdown("**Métriques, formules et données de comparaison**")
            st.json(
                {
                    key: value
                    for key, value in analysis.items()
                    if key != "series"
                }
            )
        st.markdown("**Contrôles individuels et preuves**")
        for check in checks:
            status = readable_label(check.get("status", ""), STATUS_LABELS)
            title = readable_label(check.get("id", ""), CHECK_TITLE_LABELS)
            st.markdown(f"**{title} — {status}**")
            st.json(check)
        explanation = response.get("explanation") or {}
        if explanation:
            st.markdown("**Réponse complète du modèle**")
            st.json(explanation)
        references = []
        for check in checks:
            references.extend(check.get("evidence_refs", []))
        for change in explanation.get("changes", []):
            references.extend(change.get("evidence_refs", []))
        for assessment in explanation.get("profile_assessment", []):
            references.extend(assessment.get("evidence_refs", []))
        if references:
            render_evidence_references(
                references, request, response, inside_expander=True
            )
        trace = response.get("tool_trace") or explanation.get("tool_trace", [])
        st.markdown("**Traces des outils**")
        if trace:
            st.json(trace)
        else:
            st.write("Aucune trace d’outil disponible.")


st.set_page_config(
    page_title="AlphaForge AI - Datathon Polyfinances", layout="wide")

with st.sidebar:
    st.markdown("## AlphaForge")
    st.caption("Comprendre avant de décider.")
    st.markdown(
        """
        <nav class="af-nav" aria-label="Navigation principale">
            <a href="#overview">Vue d’ensemble</a>
            <a class="active" href="#scenario-form">Simuler un ajout</a>
            <a href="#results">Résultats</a>
            <a href="#sources-method">Sources &amp; méthode</a>
        </nav>
        """,
        unsafe_allow_html=True,
    )
    theme = st.radio(
        "Thème de l’interface",
        ["Clair", "Sombre"],
        index=1,
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

st.html('<div id="overview"></div>')
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
topbar = st.columns([2.2, 1.1, 1.0])
with topbar[0]:
    st.caption("Comprendre avant de décider.")
with topbar[1]:
    st.markdown(
        '<span class="af-badge">AlphaForge AI · Agent Bedrock</span>',
        unsafe_allow_html=True,
    )
with topbar[2]:
    selected_persona_name = st.selectbox(
        "Profil", list(persona_by_name), label_visibility="collapsed"
    )
persona = persona_by_name[selected_persona_name]
portfolio = portfolios_by_id[persona["id"]]
scenario = scenarios_by_id[persona["id"]]
starting_weights = asset_weights(portfolio)

horizon_end = persona["horizon_years_max"]
horizon = (
    f"{persona['horizon_years_min']}–{horizon_end} ans"
    if horizon_end is not None
    else f"{persona['horizon_years_min']} ans et plus"
)
with st.sidebar:
    st.divider()
    st.markdown(f"### {persona['name']}")
    st.caption(f"{persona['objective']} · {horizon}")
    with st.expander("Portefeuille fictif initial"):
        st.dataframe(
            [
                {
                    "Placement": assets.get(symbol, {}).get("name", "Autre placement"),
                    "Pondération": format_weight(weight),
                }
                for symbol, weight in starting_weights.items()
            ],
            hide_index=True,
            width="stretch",
        )
        st.caption(portfolio.get("construction_note", "Hypothèse pédagogique."))
        if portfolio.get("esg_evidence_limitations"):
            st.caption(portfolio["esg_evidence_limitations"])

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

title_symbol = st.session_state.get("selected_symbol", default_symbol)
if title_symbol not in available_symbols:
    title_symbol = default_symbol
st.title(f"Et si vous ajoutiez {title_symbol} ?")
st.write("Mesurez l’impact sur votre portefeuille et comprenez les compromis.")

st.html('<div id="scenario-form"></div>')
with st.form("custom_scenario_form"):
    col_profile, col_symbol, col_weight, col_action = st.columns(
        [0.85, 1.15, 1.45, 1.3]
    )
    with col_profile:
        st.markdown("**Profil**")
        st.markdown(persona["name"])
    with col_symbol:
        selected_symbol = st.selectbox(
            "Actif",
            available_symbols,
            index=default_index,
            key="selected_symbol",
            format_func=lambda symbol: (
                f"{symbol} · {assets.get(symbol, {}).get('name', symbol)}"
            ),
        )
    with col_weight:
        target_weight = st.slider(
            "Poids cible (%)", min_value=1.0, max_value=50.0,
            value=float(scenario["target_weight_pct"]), step=0.5,
            key="target_weight",
        )
    with col_action:
        st.markdown("**Analyse**")
        submitted = st.form_submit_button(
            "Analyser le scénario", type="primary"
        )
st.caption(
    "Financement : réduction proportionnelle des positions existantes."
)
st.html('<div id="results"></div>')

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
    stored_asset_name = assets.get(stored_request["symbol"], {}).get(
        "name", "cet actif"
    )
    st.markdown(
        "**Résultat conservé :** "
        f"{stored_name} · {stored_asset_name} · "
        f"{format_weight(stored_request['target_weight_pct'])}"
    )
    if current_request != stored_request:
        st.warning(
            "Le formulaire vise maintenant un autre scénario. Les résultats "
            "ci-dessous correspondent encore à la demande conservée; cliquez "
            "sur « Analyser le changement » pour lancer une nouvelle analyse."
        )

    status = response.get("status")
    technical_mode = st.toggle(
        "Mode technique",
        value=False,
        help="Affiche les métriques brutes, les contrôles et les preuves détaillés.",
    )
    if status == "error":
        st.error(
            "Nous n’avons pas pu produire le rapport. Vérifiez les choix du "
            "formulaire, puis relancez l’analyse."
        )
        if technical_mode:
            render_technical_details(response, None, [], stored_request)
    else:
        analysis = response.get("analysis")
        checks = response.get("checks") or []
        if status == "success":
            st.success("Votre rapport est prêt.")
        elif status == "partial":
            st.warning(
                "Les calculs sont disponibles; l’explication automatique "
                "n’a pas pu être produite."
            )
        if analysis:
            explanation = response.get("explanation")
            stored_asset = assets.get(stored_request["symbol"], {})
            stored_asset_name = stored_asset.get("name", "cet actif")
            report_persona = stored_persona or persona
            report_horizon_end = report_persona.get("horizon_years_max")
            report_horizon = (
                f"{report_persona['horizon_years_min']}–{report_horizon_end} ans"
                if report_horizon_end is not None
                else f"{report_persona['horizon_years_min']} ans et plus"
            )
            render_simulation(analysis, stored_asset)
            report_left, report_right = st.columns([1.8, 1.0], gap="medium")
            with report_left:
                with st.container(border=True):
                    render_analysis(analysis)
                with st.container(border=True):
                    render_chart(analysis, stored_asset_name)
                with st.container(border=True):
                    st.subheader("Ce qui change")
                    render_weight_details(analysis, assets)
            with report_right:
                with st.container(border=True):
                    st.subheader("L’éclairage de l’agent")
                    render_summary(analysis, stored_asset_name, explanation)
                    render_priorities(
                        stored_persona or persona,
                        checks,
                        explanation,
                        stored_asset_name,
                    )
                    render_remaining(stored_persona or persona, checks)
                with st.container(border=True):
                    st.subheader("Analyse traçable")
                    st.write(
                        f"Profil consulté : {stored_name} · "
                        f"{report_persona['objective']} · {report_horizon}."
                    )
                    st.write(
                        f"Simulation calculée : ajout de {stored_asset_name} "
                        f"à {format_weight(stored_request['target_weight_pct'])}."
                    )
                    st.write(f"Contrôles exécutés : {len(checks)}.")
                with st.container(border=True):
                    st.html('<div id="sources-method"></div>')
                    render_methodology()
                    render_sources(analysis, checks)
            if technical_mode:
                render_technical_details(
                    response, analysis, checks, stored_request
                )

st.caption(
    "Les résultats historiques ne préjugent pas des résultats futurs. "
    "Aucune transaction n’est exécutée."
)
