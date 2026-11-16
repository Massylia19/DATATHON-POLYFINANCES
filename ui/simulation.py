"""Interface Streamlit de simulation des portefeuilles AlphaForge."""

from __future__ import annotations

import re
import streamlit as st

from ui.shared import (
    ASSETS_PATH,
    DATA_DIR,
    ROOT,
    apply_intent_request,
    asset_weights,
    read_json,
    request_key,
    select_persona,
)

try:
    from agent.context import create_request_context
    from agent.evidence import resolve_evidence_reference
    from agent.service import (
        answer_follow_up,
        analyze_comparison,
        analyze_request,
        interpret_scenario_request,
    )
    from alphaforge.engine import load_asset_universe
    from alphaforge.presentation import (
        ASSET_CLASS_LABELS,
        CHECK_TITLE_LABELS,
        METRIC_PRESENTATION,
        SOURCE_PRESENTATION,
        STATUS_LABELS,
        build_main_summary,
        describe_metric_change,
        format_date_fr,
        format_preferences,
        format_rate,
        format_weight,
        format_weight_delta,
        has_unsafe_main_narrative,
        join_french_list,
        missing_information_phrases,
        persona_possessive,
        readable_label,
        RISK_LEVEL_LABELS,
    )

    ENGINE_AVAILABLE = True
except ImportError:
    ENGINE_AVAILABLE = False


from ui.renderers import (
    bedrock_availability_hint,
    render_analysis,
    render_chart,
    render_methodology,
    render_priorities,
    render_remaining,
    render_simulation,
    render_sources,
    render_summary,
    render_technical_details,
    render_variant_comparison,
    render_weight_details,
)

if not ENGINE_AVAILABLE:
    st.error(
        "Les composants AlphaForge ne sont pas disponibles. "
        "Installez les dépendances du projet, puis relancez l’application."
    )
    st.stop()

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
except (OSError, KeyError, ValueError) as exc:
    st.error(f"Impossible de charger les données du projet : {exc}")
    st.stop()

persona_by_id = {persona["id"]: persona for persona in personas}
st.caption("Simulation fictive · aucune transaction réelle.")
st.title("Testez une idée. Comprenez ses effets.")

selected_persona_id = st.session_state.get("selected_persona_id", personas[0]["id"])
if selected_persona_id not in persona_by_id:
    selected_persona_id = personas[0]["id"]
st.session_state["selected_persona_id"] = selected_persona_id
st.session_state.setdefault("_persona_selector", selected_persona_id)


def on_persona_change() -> None:
    select_persona(st.session_state["_persona_selector"], scenarios_by_id)


def on_symbol_change() -> None:
    st.session_state["selected_symbol"] = st.session_state["_symbol_input"]


def on_weight_change() -> None:
    st.session_state["target_weight"] = float(st.session_state["_weight_input"])


def interpret_natural_request() -> None:
    interpreted = interpret_scenario_request(
        st.session_state.get("natural_request_text", ""), root=ROOT
    )
    if interpreted.get("status") == "ready":
        apply_intent_request(interpreted["request"])
        st.session_state["intent_message"] = ("success", "Demande comprise. Vérifiez les paramètres puis lancez l’analyse.")
    else:
        st.session_state["pending_intent"] = None
        message = interpreted.get("message") or interpreted.get(
            "error", {}
        ).get("message", "La demande n’a pas pu être comprise.")
        st.session_state["intent_message"] = (
            "error" if interpreted.get("status") == "error" else "info",
            message,
        )


st.radio(
    "Profil d’investisseur",
    options=list(persona_by_id),
    format_func=lambda persona_id: persona_by_id[persona_id]["name"],
    horizontal=True,
    key="_persona_selector",
    on_change=on_persona_change,
)
selected_persona_id = st.session_state["selected_persona_id"]
persona = persona_by_id[selected_persona_id]
scenario = scenarios_by_id[persona["id"]]
st.session_state.setdefault("selected_symbol", scenario["symbol"])
st.session_state.setdefault(
    "target_weight", float(scenario["target_weight_pct"])
)
if st.session_state["selected_symbol"] in {
    position["symbol"]
    for position in portfolios_by_id[persona["id"]]["positions"]
} or st.session_state["selected_symbol"] not in assets:
    st.session_state["selected_symbol"] = scenario["symbol"]
    st.session_state["target_weight"] = float(scenario["target_weight_pct"])

portfolio = portfolios_by_id[persona["id"]]
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
    st.caption(readable_label(persona.get("risk_level", ""), RISK_LEVEL_LABELS))
    with st.expander("Détails du profil"):
        st.write(f"**Préférences :** {format_preferences(persona.get('preferences', []))}")
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
if not available_symbols:
    st.error("Aucun actif disponible à ajouter au portefeuille.")
    st.stop()

default_symbol = scenario["symbol"]
if st.session_state["selected_symbol"] not in available_symbols:
    st.session_state["selected_symbol"] = default_symbol
st.session_state.setdefault("_symbol_input", st.session_state["selected_symbol"])
st.session_state.setdefault("_weight_input", float(st.session_state["target_weight"]))
if st.session_state["_symbol_input"] not in available_symbols:
    st.session_state["_symbol_input"] = default_symbol

asset_col, weight_col, action_col = st.columns(
    [1.5, 1.1, 1], vertical_alignment="bottom"
)
with asset_col:
    selected_symbol = st.selectbox(
        "Actif à ajouter",
        available_symbols,
        key="_symbol_input",
        on_change=on_symbol_change,
        format_func=lambda symbol: (
            f"{assets.get(symbol, {}).get('name', symbol)} — {symbol}"
        ),
    )
with weight_col:
    target_weight = st.slider(
        "Part du portefeuille (%)",
        min_value=1.0,
        max_value=50.0,
        step=0.5,
        key="_weight_input",
        on_change=on_weight_change,
    )
with action_col:
    submitted = st.button("Analyser le scénario", type="primary", width='stretch')

st.session_state["selected_symbol"] = selected_symbol
st.session_state["target_weight"] = float(target_weight)

selected_asset = assets[selected_symbol]
selected_asset_name = selected_asset.get("name", selected_symbol)
selected_asset_type = readable_label(
    selected_asset.get("asset_class", ""), ASSET_CLASS_LABELS
)
st.caption(f"{selected_asset_type} · L’ajout réduit proportionnellement les autres positions.")
pending_intent = st.session_state.get("pending_intent")
if pending_intent == request_key(
    persona["id"], selected_symbol, target_weight
):
    st.success(
        "Paramètres compris : "
        f"{persona['name']} · {selected_asset_name} ({selected_symbol}) · "
        f"{format_weight(target_weight)}. Vérifiez-les puis lancez l’analyse."
    )
with st.expander("Décrire ma demande avec mes mots"):
    st.text_input(
        "Par exemple : Pour Amira, tester 15 % de NVIDIA.",
        max_chars=500,
        key="natural_request_text",
    )
    st.button(
        "Comprendre la demande",
        key="interpret_scenario_request",
        on_click=interpret_natural_request,
    )
    intent_message = st.session_state.get("intent_message")
    if intent_message:
        getattr(st, intent_message[0])(intent_message[1])

if submitted:
    analyzed_request = request_key(persona["id"], selected_symbol, target_weight)
    st.session_state["pending_intent"] = None
    with st.spinner(
        "Nous comparons les portefeuilles et préparons votre explication…"
    ):
        response = analyze_request(
            persona["id"], selected_symbol, target_weight
        )
    st.session_state["analyzed_request"] = analyzed_request
    st.session_state["analysis_response"] = response

stored_request = st.session_state.get("analyzed_request")
response = st.session_state.get("analysis_response")
current_request = request_key(persona["id"], selected_symbol, target_weight)

synthesis_tab, variants_tab, sources_tab = st.tabs(
    ["Synthèse", "Variantes", "Sources et méthode"]
)

with synthesis_tab:
    if not stored_request or not response:
        st.info("Choisissez un profil et un actif, puis lancez l’analyse.")
        st.caption("Les questions seront disponibles après la première simulation.")
    if stored_request and response:
        stored_analysis = response.get("analysis") or {}
        stored_persona = stored_analysis.get("persona", {})
        stored_name = stored_persona.get("name", stored_request["persona_id"].title())
        stored_asset_name = assets.get(stored_request["symbol"], {}).get(
            "name", "cet actif"
        )
        if current_request != stored_request:
            st.warning(
                f"Le rapport précédent concernait {stored_name}, "
                f"{stored_asset_name} à "
                f"{format_weight(stored_request['target_weight_pct'])}. "
                "Il est masqué, car le scénario sélectionné a changé. "
                "Lancez l’analyse pour obtenir le nouveau résultat."
            )
        else:
            st.caption("Étape 3")
            st.subheader("Comprendre et comparer")
            status = response.get("status")
            technical_mode = st.toggle(
                "Mode technique",
                value=False,
                help="Affiche les métriques brutes, les contrôles et les preuves détaillés.",
            )
            if status == "success":
                st.success("Simulation calculée et explication Bedrock validée.")
            elif status == "partial":
                st.warning(
                    "Les calculs sont disponibles, mais l’agent n’a pas fourni "
                    "d’explication validée. Le résumé ci-dessous s’appuie sur les "
                    "résultats calculés."
                )
                availability_hint = bedrock_availability_hint(response)
                if availability_hint:
                    st.caption(availability_hint)
            elif status == "error":
                st.error(
                    "Nous n’avons pas pu calculer ce scénario. Vérifiez les choix "
                    "et les données disponibles, puis réessayez."
                )
            else:
                st.error("Le service a retourné un état de simulation inconnu.")

            analysis = response.get("analysis")
            checks = response.get("checks") or []
            if status == "error":
                if technical_mode:
                    render_technical_details(response, None, [], stored_request)
            elif analysis:
                explanation = response.get("explanation")
                stored_asset = assets.get(stored_request["symbol"], {})
                stored_asset_name = stored_asset.get("name", "cet actif")
                render_simulation(analysis, stored_asset)
                report_left, report_right = st.columns([1.8, 1.0], gap="medium")
                with report_left:
                    with st.container(border=True):
                        render_analysis(analysis)
                        render_summary(analysis, stored_asset_name, explanation)
                    with st.container(border=True):
                        st.subheader("Cohérence avec le profil")
                        render_priorities(
                            stored_persona or persona,
                            checks,
                            explanation,
                            stored_asset_name,
                        )
                        render_remaining(stored_persona or persona, checks)
                    with st.expander("Évolution historique"):
                        render_chart(analysis, stored_asset_name)
                    render_weight_details(analysis, assets)
                with report_right:
                    with st.container(border=True):
                        st.subheader("Comprendre avec AlphaForge")
                        st.caption("Posez une question sur les résultats affichés.")
                if technical_mode:
                    render_technical_details(
                        response, analysis, checks, stored_request
                    )
                previous_follow_up = st.session_state.get("follow_up_result")
                with report_right.container(border=True):
                    st.markdown("**Vos questions**")
                    st.caption(
                        "Exemples : Pourquoi le risque change-t-il ? "
                        "Est-ce que cela diversifie vraiment le portefeuille ? "
                        "Quelles preuves soutiennent l’analyse ESG ?"
                    )
                    follow_up_question = st.text_input(
                        "Votre question",
                        max_chars=500,
                        key="follow_up_question",
                    )
                    if st.button("Répondre à ma question", key="answer_follow_up"):
                        if re.search(
                            r"\d+(?:[.,]\d+)?\s*(?:%|pour\s*cent|pourcent)",
                            follow_up_question,
                            re.IGNORECASE,
                        ):
                            follow_up_result = interpret_scenario_request(
                                follow_up_question,
                                root=ROOT,
                                current_request=stored_request,
                            )
                            follow_up_kind = "scenario"
                        else:
                            follow_up_result = answer_follow_up(
                                follow_up_question,
                                response,
                                stored_request,
                                root=ROOT,
                            )
                            follow_up_kind = "answer"
                        st.session_state["follow_up_result"] = {
                            "request": stored_request,
                            "question": follow_up_question,
                            "kind": follow_up_kind,
                            "result": follow_up_result,
                        }

                    follow_up_state = st.session_state.get("follow_up_result")
                    if (
                        follow_up_state
                        and follow_up_state.get("request") == stored_request
                        and follow_up_state.get("question") == follow_up_question
                    ):
                        follow_up_result = follow_up_state["result"]
                        if follow_up_state["kind"] == "scenario":
                            if follow_up_result.get("status") == "ready":
                                requested = follow_up_result["request"]
                                requested_persona = persona_by_id[
                                    requested["persona_id"]
                                ]
                                requested_asset = assets[requested["symbol"]]
                                st.info(
                                    "Nouvelle variante comprise : "
                                    f"{requested_persona['name']} · "
                                    f"{requested_asset['name']} — "
                                    f"{requested['symbol']} · "
                                    f"{format_weight(requested['target_weight_pct'])}. "
                                    "Utilisez-la pour mettre à jour le scénario, puis "
                                    "lancez le calcul."
                                )
                                st.button(
                                    "Utiliser cette variante",
                                    key="apply_follow_up_variant",
                                    on_click=apply_intent_request,
                                    args=(requested,),
                                )
                            else:
                                message = follow_up_result.get("message") or (
                                    follow_up_result.get("error", {}).get("message")
                                )
                                st.info(
                                    message
                                    or "La nouvelle variante doit être précisée."
                                )
                        elif follow_up_result.get("status") == "success":
                            st.markdown(follow_up_result["answer"])
                            st.caption(
                                "Réponse fondée sur les données et contrôles "
                                "de cette simulation."
                            )
                            if technical_mode:
                                st.json(
                                    {
                                        "evidence_refs": follow_up_result[
                                            "evidence_refs"
                                        ],
                                        "origin": follow_up_result["origin"],
                                    }
                                )
                        else:
                            st.info(
                                follow_up_result.get("message")
                                or "La réponse de suivi n’est pas disponible."
                            )
            elif status in {"success", "partial"}:
                st.error("Les calculs ne sont pas présents dans cette réponse.")
                if technical_mode:
                    render_technical_details(response, None, checks, stored_request)


with variants_tab:
    st.write(
        "Comparez deux proportions du même actif, à partir du même portefeuille "
        "fictif et sur une période historique commune."
    )
    st.session_state.setdefault("comparison_weight_a", 5.0)
    st.session_state.setdefault("comparison_weight_b", 20.0)
    comparison_columns = st.columns(2)
    with comparison_columns[0]:
        comparison_weight_a = st.slider(
            "Variante A — part du portefeuille (%)",
            min_value=1.0,
            max_value=50.0,
            step=0.5,
            key="comparison_weight_a",
        )
    with comparison_columns[1]:
        comparison_weight_b = st.slider(
            "Variante B — part du portefeuille (%)",
            min_value=1.0,
            max_value=50.0,
            step=0.5,
            key="comparison_weight_b",
        )

    comparison_request = {
        "persona_id": persona["id"],
        "symbol": selected_symbol,
        "weight_a_pct": float(comparison_weight_a),
        "weight_b_pct": float(comparison_weight_b),
    }
    if st.button("Comparer les variantes", key="compare_variants"):
        with st.spinner("Nous comparons les deux variantes…"):
            comparison_response = analyze_comparison(
                persona["id"],
                selected_symbol,
                comparison_weight_a,
                comparison_weight_b,
            )
        st.session_state["comparison_request"] = comparison_request
        st.session_state["comparison_response"] = comparison_response

    stored_comparison_request = st.session_state.get("comparison_request")
    stored_comparison = st.session_state.get("comparison_response")
    if stored_comparison_request and stored_comparison:
        if comparison_request != stored_comparison_request:
            st.info(
                "Les paramètres de comparaison ont changé. Relancez la "
                "comparaison pour afficher le résultat correspondant."
            )
        elif stored_comparison.get("status") == "error":
            st.error(
                "Cette comparaison n’a pas pu être réalisée sur une période "
                "commune."
            )
            if st.toggle(
                "Mode technique — comparaison",
                value=False,
                key="comparison_technical_mode",
            ):
                st.json(stored_comparison)
        else:
            render_variant_comparison(stored_comparison, assets, persona)
            if st.toggle(
                "Mode technique — comparaison",
                value=False,
                key="comparison_technical_mode",
            ):
                st.json(stored_comparison)


with sources_tab:
    if stored_request == current_request and response and response.get("analysis"):
        render_methodology()
        render_sources(response["analysis"], response.get("checks") or [])
    else:
        st.info("Lancez une analyse pour consulter les sources et la méthode.")

st.caption(
    "Les résultats historiques ne préjugent pas des résultats futurs. "
    "Aucune transaction n’est exécutée."
)




