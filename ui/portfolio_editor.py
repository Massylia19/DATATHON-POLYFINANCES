"""Interface de modification avancée du portefeuille AlphaForge.

╔══════════════════════════════════════════════════════════════════════════════╗
║                    ÉDITEUR DE PORTEFEUILLE - STREAMLIT                       ║
║                  Interface utilisateur pour modifications                     ║
║                        multiples et analyse comparative                       ║
╚══════════════════════════════════════════════════════════════════════════════╝

OVERVIEW :
----------
Cette interface Streamlit permet à l'utilisateur de :
1. Sélectionner un profil d'investisseur (persona)
2. Modifier les poids de TOUS les actifs existants avec des sliders interactifs
3. Ajouter de NOUVEAUX actifs depuis l'univers disponible (multi-sélection)
4. Retirer des actifs (bouton "Retirer" ou mettre le poids à 0%)
5. Normaliser automatiquement les poids pour atteindre 100%
6. Lancer une simulation comparative (AVANT vs APRÈS) via analyze_custom_portfolio()
7. Visualiser les résultats : métriques, graphiques, composition

C'est l'interface complète pour tester différents scénarios de portefeuille de manière
pédagogique et fictive (aucune transaction réelle).

ARCHITECTURE (Interface Streamlit) :
------------------------------------
┌────────────────────────────────────────────────────────────────────────────┐
│ 1. Sélection Persona (radio buttons)                                       │
│    → Charge portefeuille initial depuis portfolios.json                    │
│    → Réinitialise les poids personnalisés                                  │
└────────────────────────────────────────────────────────────────────────────┘
                                  ↓
┌────────────────────────────────────────────────────────────────────────────┐
│ 2. Modification Poids Existants (sliders 0-100%)                           │
│    → Session state : st.session_state["custom_weights"]                    │
│    → Boutons "Retirer" pour mettre poids à 0                               │
└────────────────────────────────────────────────────────────────────────────┘
                                  ↓
┌────────────────────────────────────────────────────────────────────────────┐
│ 3. Ajout Nouveaux Actifs (multiselect + sliders)                           │
│    → Liste actifs disponibles = univers - actifs_actuels (weight > 0)      │
│    → Session state : st.session_state["new_assets"]                        │
│    → Sliders 0.5-50% pour chaque nouvel actif                              │
└────────────────────────────────────────────────────────────────────────────┘
                                  ↓
┌────────────────────────────────────────────────────────────────────────────┐
│ 4. Résumé & Normalisation                                                  │
│    → Calcul total = sum(custom_weights) + sum(new_assets)                  │
│    → Checkbox "Normaliser automatiquement" (défaut: activé)                │
│    → Si normalisé : factor = 100 / total, apply à tous les poids           │
└────────────────────────────────────────────────────────────────────────────┘
                                  ↓
┌────────────────────────────────────────────────────────────────────────────┐
│ 5. Analyse (bouton "Analyser ce portefeuille")                             │
│    → Appel analyze_custom_portfolio(persona_id, final_portfolio)           │
│    → Résultat stocké dans st.session_state["custom_analysis_result"]       │
│    → Rerun pour afficher résultats                                         │
└────────────────────────────────────────────────────────────────────────────┘
                                  ↓
┌────────────────────────────────────────────────────────────────────────────┐
│ 6. Affichage Résultats (métriques + graphiques)                            │
│    → Métriques : rendement, volatilité, drawdown (AVANT vs APRÈS)          │
│    → Graphique ligne : évolution temporelle (base 100)                     │
│    → Expander : détails pondérations (tableaux)                            │
└────────────────────────────────────────────────────────────────────────────┘

SOURCES DE DONNÉES :
--------------------
- Personas : data/personas.json (profils investisseurs)
- Portefeuilles initiaux : data/portfolios.json (allocations par persona)
- Univers d'actifs : data/market/assets_universe.csv (symboles, noms, classes)
- Simulation : agent/service.py::analyze_custom_portfolio() (backend)

HYPOTHÈSES CRITIQUES :
----------------------
⚠️ INTERFACE :
- L'utilisateur comprend que c'est une simulation pédagogique (disclaimer en bas)
- Les modifications ne sont PAS sauvegardées (session state volatile)
- Un seul portefeuille personnalisé à la fois (pas d'historique)
- Les calculs sont déclenchés manuellement (bouton "Analyser")

⚠️ BACKEND (délégué à analyze_custom_portfolio) :
- Buy-and-hold strict (pas de rééquilibrage)
- Historique ≠ futur
- Coûts de transaction exclus
- Voir docstring de analyze_custom_portfolio() pour détails

⚠️ STREAMLIT :
- Session state persiste entre reruns dans la même session navigateur
- Un changement de persona réinitialise les poids (comportement voulu)
- Les reruns sont déclenchés par : changement de valeur widget, boutons

LIMITES :
---------
- **UX** : Pas de historique des analyses précédentes (une seule à la fois)
- **UX** : Pas de sauvegarde des portefeuilles personnalisés (session volatile)
- **UX** : Pas de comparaison multi-scénarios (A vs B vs C)
- **Performance** : Analyse peut prendre 2-5 secondes (calcul backend)
- **Validation** : Pas de check avancé (diversification min, exposition max par classe)
- **Ergonomie** : Sur mobile, sliders nombreux = scroll long
- **Méthodologiques** : Toutes les limites de analyze_custom_portfolio()

VALIDATION DES ENTRÉES :
------------------------
✅ Total des poids = 100% (avec tolérance 0.01% ou normalisation auto)
✅ Tous les symboles sélectionnés existent dans l'univers
✅ Persona sélectionné existe
✅ Poids >= 0 (sliders limités)
❌ Backend valide davantage (symboles dans market data, etc.)

COMPORTEMENT :
--------------
1. **Changement de persona** :
   → Réinitialise custom_weights et new_assets
   → Efface les résultats d'analyse précédents

2. **Bouton "Retirer"** :
   → Met le poids de l'actif à 0 (l'actif reste dans custom_weights)
   → L'actif avec poids 0 n'apparaît pas dans le portefeuille final
   → Peut être ré-ajouté via "Ajouter de nouveaux actifs"

3. **Normalisation** :
   → Si cochée ET total ≠ 100% : applique factor = 100/total à tous les poids
   → Si décochée : utilisateur doit ajuster manuellement à 100%
   → Bouton "Analyser" désactivé si total ≠ 100% et normalisation décochée

4. **Affichage résultats** :
   → Résultats persistent jusqu'à : changement persona, "Nouvelle analyse", rerun
   → Résultats liés au persona (si change persona, résultats effacés)

5. **Bouton "Réinitialiser"** :
   → Recharge les poids du portefeuille initial du persona
   → Efface new_assets
   → Efface résultats d'analyse

ACCESSIBILITÉ :
---------------
- Labels clairs pour tous les sliders (nom actif + symbole + type)
- Boutons avec libellés explicites ("Retirer", "Analyser", "Réinitialiser")
- Métriques avec help tooltips (expliquent chaque indicateur)
- Disclaimer visible en bas de page
- Statut visuel : st.success() / st.warning() / st.error()

SÉCURITÉ :
----------
- Aucune transaction réelle (simulation pure)
- Pas de sauvegarde serveur (tout en session locale)
- Pas d'entrée libre de texte (seulement sélections/sliders)
- Backend valide les inputs (protect contre injections/valeurs aberrantes)

PERFORMANCE :
-------------
- Interface réactive : reruns Streamlit ~50-200ms
- Calcul analyse : 2-5 secondes (backend Python)
- Pas de cache actuellement (chaque analyse recalcule tout)
- Optimisation possible : @st.cache_data sur les chargements JSON/CSV

MAINTENANCE :
-------------
- Dépendances : streamlit, agent.service, alphaforge.engine
- Fichiers couplés : data/personas.json, data/portfolios.json, assets_universe.csv
- Tests : Voir tests/test_custom_portfolio.py pour validation backend
- UI tests : Manuels (Streamlit n'a pas de test framework robuste)

EXEMPLES D'USAGE :
------------------
1. **Scénario : Tester ajout de Bitcoin** :
   - Sélectionner persona "Amira"
   - Aller dans "Ajouter de nouveaux actifs"
   - Sélectionner "BTC-USD"
   - Mettre slider à 10%
   - Cocher "Normaliser automatiquement"
   - Cliquer "Analyser ce portefeuille"
   → Voir impact sur volatilité et rendement

2. **Scénario : Retirer une action** :
   - Sélectionner persona "Mateo"
   - Trouver "Apple Inc. (AAPL)" dans la liste
   - Cliquer bouton "Retirer" à côté
   → Le poids passe à 0%, actif retiré du portefeuille final

3. **Scénario : Rééquilibrer manuellement** :
   - Décocher "Normaliser automatiquement"
   - Ajuster tous les sliders pour atteindre exactement 100%
   - Observer la métrique "Total des pondérations"
   → Quand "Équilibré" apparaît en vert, peut analyser

VOIR AUSSI :
------------
- agent/service.py::analyze_custom_portfolio() : Backend de simulation
- ui/simulation.py : Interface Streamlit originale (ajout d'un seul actif)
- frontend/src/features/PortfolioEditor.tsx : Version React (même fonctionnalité)
- tests/test_custom_portfolio.py : Tests backend (40+ cas)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  AVERTISSEMENT LÉGAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Cette interface produit des SIMULATIONS PÉDAGOGIQUES basées sur des données
historiques. Ce n'est PAS un conseil en placement, NI une recommandation d'achat
ou de vente. Les performances passées ne garantissent pas les résultats futurs.

L'utilisateur doit consulter un conseiller financier qualifié avant toute décision
d'investissement réelle. Aucune vérification de l'adéquation au profil de risque,
à la situation financière, aux objectifs, ou aux contraintes légales/fiscales de
l'utilisateur n'est effectuée par cet outil.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import streamlit as st

from ui.shared import (
    ASSETS_PATH,
    DATA_DIR,
    ROOT,
    asset_weights,
    read_json,
)

try:
    from agent.service import analyze_custom_portfolio
    from alphaforge.engine import load_asset_universe
    from alphaforge.presentation import (
        ASSET_CLASS_LABELS,
        format_rate,
        format_weight,
        readable_label,
        RISK_LEVEL_LABELS,
    )
    ENGINE_AVAILABLE = True
except ImportError:
    ENGINE_AVAILABLE = False

if not ENGINE_AVAILABLE:
    st.error(
        "Les composants AlphaForge ne sont pas disponibles. "
        "Installez les dépendances du projet, puis relancez l'application."
    )
    st.stop()

try:
    personas = read_json(DATA_DIR / "personas.json")["personas"]
    portfolios_by_id = {
        portfolio["persona_id"]: portfolio
        for portfolio in read_json(DATA_DIR / "portfolios.json")["portfolios"]
    }
    assets = load_asset_universe(ASSETS_PATH)
except (OSError, KeyError, ValueError) as exc:
    st.error(f"Impossible de charger les données du projet : {exc}")
    st.stop()

persona_by_id = {persona["id"]: persona for persona in personas}

st.caption("Modification avancée · aucune transaction réelle.")
st.title("Modifier plusieurs actifs et ajuster les poids")

# Sélection du profil
selected_persona_id = st.session_state.get("editor_persona_id", personas[0]["id"])
if selected_persona_id not in persona_by_id:
    selected_persona_id = personas[0]["id"]

st.session_state["editor_persona_id"] = selected_persona_id

def on_persona_change() -> None:
    st.session_state["editor_persona_id"] = st.session_state["_editor_persona_selector"]
    # Réinitialiser les poids personnalisés
    if "custom_weights" in st.session_state:
        del st.session_state["custom_weights"]
    if "new_assets" in st.session_state:
        del st.session_state["new_assets"]

st.radio(
    "Profil d'investisseur",
    options=list(persona_by_id),
    format_func=lambda persona_id: persona_by_id[persona_id]["name"],
    horizontal=True,
    key="_editor_persona_selector",
    on_change=on_persona_change,
)

persona = persona_by_id[selected_persona_id]
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

# Initialiser les poids personnalisés si nécessaire
if "custom_weights" not in st.session_state or st.session_state.get("_reset_weights"):
    st.session_state["custom_weights"] = starting_weights.copy()
    st.session_state["_reset_weights"] = False

# Initialiser les nouveaux actifs
if "new_assets" not in st.session_state:
    st.session_state["new_assets"] = {}

st.subheader("1. Ajuster les poids des actifs existants")
st.caption("Modifiez les pondérations de votre portefeuille actuel")

# Afficher et permettre l'ajustement des poids existants
custom_weights = st.session_state["custom_weights"]

for symbol in sorted(custom_weights.keys()):
    asset_info = assets.get(symbol, {})
    asset_name = asset_info.get("name", symbol)
    asset_type = readable_label(asset_info.get("asset_class", ""), ASSET_CLASS_LABELS)

    col1, col2 = st.columns([3, 1])
    with col1:
        weight = st.slider(
            f"{asset_name} ({symbol})",
            min_value=0.0,
            max_value=100.0,
            value=float(custom_weights[symbol]),
            step=0.5,
            key=f"weight_{symbol}",
            help=f"Type: {asset_type}"
        )
        custom_weights[symbol] = weight
    with col2:
        if st.button("Retirer", key=f"remove_{symbol}"):
            custom_weights[symbol] = 0.0

st.divider()

st.subheader("2. Ajouter de nouveaux actifs")
st.caption("Sélectionnez un ou plusieurs actifs à ajouter au portefeuille")

# Liste des actifs disponibles (pas déjà dans le portefeuille)
available_symbols = sorted(
    set(assets.keys()) - set(symbol for symbol, weight in custom_weights.items() if weight > 0)
)

if available_symbols:
    selected_new_assets = st.multiselect(
        "Actifs à ajouter",
        options=available_symbols,
        format_func=lambda symbol: f"{assets[symbol].get('name', symbol)} — {symbol}",
        key="new_assets_selector"
    )

    # Afficher les sliders pour les nouveaux actifs sélectionnés
    if selected_new_assets:
        st.caption("Définissez les pondérations pour les nouveaux actifs")
        new_assets = st.session_state["new_assets"]

        for symbol in selected_new_assets:
            if symbol not in new_assets:
                new_assets[symbol] = 5.0  # Valeur par défaut

            asset_info = assets[symbol]
            asset_name = asset_info.get("name", symbol)
            asset_type = readable_label(asset_info.get("asset_class", ""), ASSET_CLASS_LABELS)

            weight = st.slider(
                f"{asset_name} ({symbol})",
                min_value=0.5,
                max_value=50.0,
                value=float(new_assets[symbol]),
                step=0.5,
                key=f"new_weight_{symbol}",
                help=f"Type: {asset_type}"
            )
            new_assets[symbol] = weight

        # Nettoyer les actifs désélectionnés
        for symbol in list(new_assets.keys()):
            if symbol not in selected_new_assets:
                del new_assets[symbol]
else:
    st.info("Tous les actifs disponibles sont déjà dans le portefeuille.")

st.divider()

# Calculer le total
total_weight = sum(weight for weight in custom_weights.values() if weight > 0)
total_weight += sum(st.session_state["new_assets"].values())

st.subheader("3. Résumé du nouveau portefeuille")

# Afficher le total et le statut
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total des pondérations", f"{total_weight:.1f}%")
with col2:
    if abs(total_weight - 100.0) < 0.01:
        st.success("Équilibré")
    else:
        st.warning(f"Écart: {total_weight - 100:.1f}%")
with col3:
    if st.button("Réinitialiser", key="reset_weights"):
        st.session_state["_reset_weights"] = True
        st.session_state["new_assets"] = {}
        st.rerun()

# Normalisation automatique
if total_weight > 0:
    normalize = st.checkbox(
        "Normaliser automatiquement à 100%",
        value=True,
        help="Ajuste proportionnellement tous les poids pour atteindre exactement 100%"
    )
else:
    normalize = False
    st.error("Le total doit être supérieur à 0%")

# Afficher le portefeuille final
if total_weight > 0:
    st.caption("Composition du nouveau portefeuille:")

    # Combiner actifs existants et nouveaux
    final_portfolio = {}
    for symbol, weight in custom_weights.items():
        if weight > 0:
            final_portfolio[symbol] = weight
    final_portfolio.update(st.session_state["new_assets"])

    # Normaliser si demandé
    if normalize and abs(total_weight - 100.0) > 0.01:
        factor = 100.0 / total_weight
        final_portfolio = {symbol: weight * factor for symbol, weight in final_portfolio.items()}

    # Afficher le tableau
    rows = []
    for symbol in sorted(final_portfolio.keys()):
        asset_info = assets.get(symbol, {})
        is_new = symbol in st.session_state["new_assets"]
        rows.append({
            "Placement": f"{'Nouveau ' if is_new else ''}{asset_info.get('name', symbol)}",
            "Symbole": symbol,
            "Pondération": f"{final_portfolio[symbol]:.2f}%",
        })

    st.dataframe(rows, hide_index=True, width='stretch')

    # Bouton d'analyse (pour l'instant, juste afficher un message)
    st.divider()

    can_analyze = normalize or abs(total_weight - 100.0) < 0.01

    if can_analyze:
        if st.button("Analyser ce portefeuille", type="primary", width='stretch'):
            with st.spinner("Analyse en cours du portefeuille personnalisé..."):
                result = analyze_custom_portfolio(selected_persona_id, final_portfolio)
            st.session_state["custom_analysis_result"] = result
            st.session_state["custom_analysis_persona"] = selected_persona_id
            st.rerun()
    else:
        st.warning("Veuillez équilibrer le portefeuille à 100% ou activer la normalisation automatique.")

# Afficher les résultats de l'analyse si disponibles
if st.session_state.get("custom_analysis_result") and st.session_state.get("custom_analysis_persona") == selected_persona_id:
    result = st.session_state["custom_analysis_result"]

    st.divider()
    st.header("Résultats de l'analyse")

    if result.get("status") == "success":
        st.success("Analyse terminée avec succès")

        analysis = result
        before = analysis["before"]
        after = analysis["after"]
        deltas = analysis["delta_after_minus_before"]

        # Afficher les métriques principales
        st.subheader("Comparaison des performances")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**Rendement total**")
            st.metric(
                "Avant",
                format_rate(before["metrics"]["total_return"]),
                help="Rendement historique du portefeuille original"
            )
            st.metric(
                "Après",
                format_rate(after["metrics"]["total_return"]),
                delta=format_rate(deltas["metrics"]["total_return"]),
                help="Rendement historique du portefeuille personnalisé"
            )

        with col2:
            st.markdown("**Volatilité annualisée**")
            st.metric(
                "Avant",
                format_rate(before["metrics"]["annualized_volatility"]),
                help="Risque mesuré par la volatilité"
            )
            st.metric(
                "Après",
                format_rate(after["metrics"]["annualized_volatility"]),
                delta=format_rate(deltas["metrics"]["annualized_volatility"]),
                delta_color="inverse",
                help="Risque mesuré par la volatilité (moins c'est mieux)"
            )

        with col3:
            st.markdown("**Baisse maximale**")
            st.metric(
                "Avant",
                format_rate(before["metrics"]["max_drawdown"]),
                help="Plus forte baisse depuis un sommet"
            )
            st.metric(
                "Après",
                format_rate(after["metrics"]["max_drawdown"]),
                delta=format_rate(deltas["metrics"]["max_drawdown"]),
                delta_color="inverse",
                help="Plus forte baisse depuis un sommet (moins c'est pire)"
            )

        # Graphique d'évolution
        st.subheader("Évolution historique")
        series = analysis.get("series", {})
        if series and "dates" in series:
            st.line_chart(
                {
                    "Date": series["dates"],
                    "Portefeuille initial": series["before"],
                    "Portefeuille personnalisé": series["after"],
                },
                x="Date",
                y=["Portefeuille initial", "Portefeuille personnalisé"],
            )
            st.caption(
                f"Période d'analyse: {analysis['period']['start']} au {analysis['period']['end']} "
                f"({analysis['period']['common_observations']} observations)"
            )

        # Détails des pondérations
        with st.expander("Détails des pondérations"):
            st.markdown("**Avant (portefeuille initial)**")
            before_rows = []
            for symbol, weight in sorted(before["weights_by_asset_pct"].items()):
                asset_name = assets.get(symbol, {}).get("name", symbol)
                before_rows.append({
                    "Actif": asset_name,
                    "Symbole": symbol,
                    "Poids": f"{weight:.2f}%"
                })
            st.dataframe(before_rows, hide_index=True, width='stretch')

            st.markdown("**Après (portefeuille personnalisé)**")
            after_rows = []
            for symbol, weight in sorted(after["weights_by_asset_pct"].items()):
                asset_name = assets.get(symbol, {}).get("name", symbol)
                delta = deltas["weights_by_asset_pct"].get(symbol, 0.0)
                delta_str = f"+{delta:.2f}%" if delta > 0 else f"{delta:.2f}%" if delta < 0 else "—"
                after_rows.append({
                    "Actif": asset_name,
                    "Symbole": symbol,
                    "Poids": f"{weight:.2f}%",
                    "Variation": delta_str
                })
            st.dataframe(after_rows, hide_index=True, width='stretch')

        # Bouton pour recommencer
        if st.button("Nouvelle analyse", key="new_analysis"):
            del st.session_state["custom_analysis_result"]
            if "custom_analysis_persona" in st.session_state:
                del st.session_state["custom_analysis_persona"]
            st.rerun()

    elif result.get("status") == "error":
        error = result.get("error", {})
        st.error(f"Erreur lors de l'analyse: {error.get('message', 'Erreur inconnue')}")
        st.caption(f"Code d'erreur: {error.get('code', 'UNKNOWN')}")

        if st.button("Réessayer", key="retry_analysis"):
            del st.session_state["custom_analysis_result"]
            if "custom_analysis_persona" in st.session_state:
                del st.session_state["custom_analysis_persona"]
            st.rerun()

st.caption(
    "Les modifications ne sont pas sauvegardées. "
    "Cette interface permet de tester différents scénarios de manière fictive."
)
