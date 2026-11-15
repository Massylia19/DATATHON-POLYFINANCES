"""Fonctions d’affichage réutilisables de l’interface AlphaForge."""

from __future__ import annotations

import streamlit as st

from agent.context import create_request_context
from agent.evidence import resolve_evidence_reference
from alphaforge.presentation import (
    ASSET_CLASS_LABELS,
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
from ui.shared import ROOT

def bedrock_availability_hint(response: dict) -> str | None:
    warning_text = " ".join(str(item) for item in response.get("warnings", []))
    if "Identifiants AWS absents ou incomplets" in warning_text:
        return (
            "La session n’a pas d’identifiants AWS actifs. Lancez l’application "
            "depuis le terminal authentifié, puis relancez l’analyse."
        )
    if "Les identifiants AWS temporaires ont expiré" in warning_text:
        return "Les identifiants AWS ont expiré. Renouvelez-les puis relancez l’analyse."
    if "Accès refusé par IAM" in warning_text:
        return (
            "Le compte AWS n’a pas accès à ce modèle Bedrock. Vérifiez les "
            "autorisations du compte."
        )
    if "Modèle ou profil introuvable" in warning_text:
        return "Le modèle configuré est introuvable dans la région AWS utilisée."
    if "Point de terminaison AWS indisponible" in warning_text:
        return "Bedrock est inaccessible depuis le réseau actuel."
    if "désactivé explicitement" in warning_text:
        return (
            "L’accès à Bedrock est désactivé pour ce lancement. Réactivez-le "
            "pour obtenir une explication de l’agent."
        )
    if "Validation de l'explication" in warning_text:
        return (
            "La réponse reçue n’a pas passé les contrôles de fiabilité. "
            "Les calculs restent disponibles; vous pouvez relancer l’analyse."
        )
    return None


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
    symbol = scenario["added_symbol"]
    asset_type = readable_label(
        asset.get("asset_class", ""),
        ASSET_CLASS_LABELS,
    )
    st.subheader("Scénario analysé")
    st.write(
        f"Dans cette simulation, {persona['name']} consacre "
        f"**{format_weight(scenario['target_weight_pct'])}** de son portefeuille "
        f"à **{asset_name} — {symbol}**. Les autres positions diminuent "
        "proportionnellement."
    )
    if asset_type != "Autre information à vérifier":
        st.caption(f"{asset_type} · Portefeuille fictif")
    currency = (
        "dollars canadiens"
        if analysis.get("currency") == "CAD"
        else readable_label(analysis.get("currency", ""), {})
    )
    st.caption(
        f"Du {format_date_fr(analysis['period']['start'])} au "
        f"{format_date_fr(analysis['period']['end'])} · "
        f"Résultats exprimés en {currency}."
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
        with column:
            st.markdown(f"**{presentation['title']}**")
            st.caption("Avant")
            st.markdown(f"### {format_rate(before['metrics'][key])}")
            st.caption("Après")
            st.markdown(f"### {format_rate(after['metrics'][key])}")
            st.caption(describe_metric_change(key, metric_deltas[key]))
            with st.popover("Définition"):
                st.write(presentation["definition"])


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


def render_variant_comparison(
    response: dict, assets: dict[str, dict], persona: dict
) -> None:
    if response.get("status") == "partial":
        st.warning(
            "Les calculs sont disponibles, mais au moins une explication "
            "Bedrock est indisponible."
        )
    variants = response.get("variants", [])
    if len(variants) != 2:
        st.error("Les deux variantes ne sont pas disponibles.")
        return
    analyses = [variant.get("analysis") for variant in variants]
    if any(not isinstance(analysis, dict) for analysis in analyses):
        st.error("Les résultats calculés des deux variantes sont requis.")
        return

    weight_labels = [
        format_weight(analysis["scenario"]["target_weight_pct"])
        for analysis in analyses
    ]
    symbol = analyses[0]["scenario"]["added_symbol"]
    asset_name = assets.get(symbol, {}).get("name", symbol)
    asset_label = f"{asset_name} — {symbol}"
    st.caption(
        f"{format_date_fr(response['period']['start'])} au "
        f"{format_date_fr(response['period']['end'])} · "
        f"mêmes dates pour les deux variantes"
    )
    rows = []
    for metric_key, presentation in METRIC_PRESENTATION.items():
        rows.append(
            {
                "Indicateur": presentation["title"],
                f"Variante {weight_labels[0]}": format_rate(
                    analyses[0]["after"]["metrics"][metric_key]
                ),
                f"Variante {weight_labels[1]}": format_rate(
                    analyses[1]["after"]["metrics"][metric_key]
                ),
            }
        )
    st.dataframe(rows, hide_index=True, width="stretch")
    st.line_chart(
        {
            "Date": analyses[0]["series"]["dates"],
            "Portefeuille initial": analyses[0]["series"]["before"],
            f"{asset_label} à {weight_labels[0]}": analyses[0]["series"]["after"],
            f"{asset_label} à {weight_labels[1]}": analyses[1]["series"]["after"],
        },
        x="Date",
        y=[
            "Portefeuille initial",
            f"{asset_label} à {weight_labels[0]}",
            f"{asset_label} à {weight_labels[1]}",
        ],
    )
    variant_columns = st.columns(2)
    for column, label, weight_label, variant, analysis in zip(
        variant_columns,
        ("A", "B"),
        weight_labels,
        variants,
        analyses,
    ):
        with column.container(border=True):
            st.subheader(f"Variante {label} · {weight_label}")
            st.write(
                build_main_summary(
                    analysis,
                    persona,
                    asset_name,
                    variant.get("explanation"),
                )
            )
            render_priorities(
                persona,
                variant.get("checks") or [],
                variant.get("explanation"),
                asset_name,
            )


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



