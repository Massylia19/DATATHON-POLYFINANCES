# AlphaForge AI — Datathon PolyFinances 2026

> **Si je consacre X % de mon portefeuille à cet actif, qu'est-ce qui change et quels compromis dois-je comprendre compte tenu de mon profil ?**

AlphaForge AI est une application pédagogique de simulation. Elle compare un portefeuille fictif **avant** et **après** l'ajout d'un actif, sur des données historiques réelles, puis examine la cohérence du changement avec le profil et explique les compromis.

> **Avertissement.** Il s'agit d'une comparaison historique hypothétique à but pédagogique. Ce n'est ni une prévision, ni une recommandation, ni un conseil en placement. Les personas et les portefeuilles sont fictifs.

### Les trois parcours

| Persona | Profil | Portefeuille fictif | Scénario testé |
|---|---|---|---|
| **Amira** | Risque élevé, 15 ans et plus, croissance à long terme | SPY 40 %, QQQ 30 %, SHOP.TO 15 %, BTC-USD 15 % | Ajouter **NVDA à 10 %** : concentration technologique |
| **Mateo** | Risque modéré, 8 à 12 ans, préférences ESG | ESGV 40 %, XBB.TO 30 %, FTS.TO 15 %, GLD 15 % | Ajouter **XOM à 10 %** : compatibilité ESG |
| **Robert** | Risque faible à modéré, 3 à 5 ans, préservation du capital | ZST.TO 40 %, XBB.TO 30 %, GLD 15 %, XIU.TO 15 % | Ajouter **TSLA à 5 %** : volatilité et préservation du capital |

L'interface permet aussi de tester n'importe quel actif du jeu de données, à n'importe quel poids.

### Architecture

AlphaForge utilise une architecture multi-couches avec séparation claire entre calcul déterministe (Python) et explication narrative (AWS Bedrock / Claude). Le **code calcule**, le **modèle explique**. Aucun chiffre n'est produit par le modèle de langage.

#### Vue d'ensemble simplifiée

```text
┌──────────────────────────────────────────────────────────────────────────┐
│  FRONTEND (React + TypeScript)                                           │
│  • Interface utilisateur (profil, actifs, poids)                         │
│  • Visualisations (graphiques, métriques)                                │
│  • Port 5173 (Vite dev server)                                           │
└──────────────────────────────────────────────────────────────────────────┘
                              ↓ HTTP POST
┌──────────────────────────────────────────────────────────────────────────┐
│  API (FastAPI)                                                           │
│  • Validation des entrées (Pydantic)                                     │
│  • Endpoints REST (/api/custom-portfolio, /api/interpret)                │
│  • Port 8000                                                             │
└──────────────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────────────┐
│  BACKEND LOGIC (agent/service.py)                                        │
│  • Orchestration de l'analyse                                            │
│  • Appels au moteur de simulation                                        │
│  • Appels à AWS Bedrock (optionnel)                                      │
└──────────────────────────────────────────────────────────────────────────┘
                    ↓                              ↓
    ┌───────────────────────────┐    ┌───────────────────────────┐
    │  MOTEUR DE SIMULATION     │    │  AWS BEDROCK CONVERSE API │
    │  (alphaforge/engine.py)   │    │  • Claude Opus 5.5        │
    │  • Calculs déterministes  │    │  • Région us-east-1       │
    │  • Métriques financières  │    │  • Explication narrative  │
    │  • Données historiques    │    │  • Tools : 4 outils       │
    └───────────────────────────┘    └───────────────────────────┘
                    ↓
    ┌───────────────────────────────────────────────────────────┐
    │  DONNÉES LOCALES                                          │
    │  • data/personas.json (profils investisseurs)             │
    │  • data/portfolios.json (allocations)                     │
    │  • data/market/prices_daily.csv (Yahoo Finance)           │
    │  • data/market/fx_usdcad_daily.csv (Banque du Canada)     │
    │  • data/market/assets_universe.csv (métadonnées)          │
    └───────────────────────────────────────────────────────────┘
```

#### Architecture détaillée : Flux de données end-to-end

**Cas d'usage 1 : Modification de portefeuille (sans explication IA)**

```text
┌─────────────────────────────────────────────────────────────────────────────────────┐
│ 1. FRONTEND (React) : PortfolioEditor.tsx                                           │
│    Utilisateur modifie poids, ajoute/retire actifs                                  │
│    → Normalisation automatique à 100%                                               │
│    → Clic "Analyser ce portefeuille"                                                │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                    ↓ POST /api/custom-portfolio
┌─────────────────────────────────────────────────────────────────────────────────────┐
│ 2. API (FastAPI) : api/main.py::create_custom_portfolio_analysis()                 │
│    Validation : CustomPortfolioRequest (Pydantic)                                   │
│    • persona_id : "amira" | "mateo" | "robert"                                      │
│    • weights : dict[symbol → weight_pct]  (total = 100%)                            │
│    → Appelle api/services.py::run_custom_portfolio()                                │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────────────┐
│ 3. BACKEND : agent/service.py::analyze_custom_portfolio()                          │
│    a) Chargement contexte :                                                         │
│       • Lit data/personas.json → charge profil utilisateur                          │
│       • Lit data/portfolios.json → charge portefeuille initial                      │
│       • Lit data/market/prices_daily.csv → prix historiques (Yahoo Finance)         │
│       • Lit data/market/fx_usdcad_daily.csv → taux USD/CAD (Banque du Canada)      │
│       • Lit data/market/assets_universe.csv → métadonnées (classes, secteurs)      │
│    b) Simulation AVANT (alphaforge/engine.py) :                                     │
│       • Normalise portefeuille initial                                              │
│       • Convertit prix en CAD (FX forward fill)                                     │
│       • Aligne sur dates communes (intersection stricte)                            │
│       • Simule buy-and-hold (quantités fixes)                                       │
│       • Calcule métriques : rendement, volatilité, max drawdown                     │
│    c) Simulation APRÈS :                                                            │
│       • Applique custom_weights (portefeuille personnalisé)                         │
│       • Même processus que AVANT                                                    │
│    d) Calcul des deltas :                                                           │
│       • delta = after - before (différences)                                        │
│    e) Génération séries temporelles :                                               │
│       • Base 100 au départ, évolution relative                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                    ↓ JSON Response
┌─────────────────────────────────────────────────────────────────────────────────────┐
│ 4. API → FRONTEND : Réponse structurée                                              │
│    {                                                                                 │
│      "status": "success",                                                            │
│      "before": { "weights_by_asset_pct": {...}, "metrics": {...} },                │
│      "after": { ... },                                                               │
│      "delta_after_minus_before": { ... },                                           │
│      "series": { "dates": [...], "before": [...], "after": [...] },                │
│      "period": { "start": "...", "end": "...", "common_observations": 756 }        │
│    }                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────────────┐
│ 5. FRONTEND (React) : CustomPortfolioResults.tsx                                    │
│    Affichage des résultats :                                                        │
│    • 3 cartes métriques (Rendement, Volatilité, Baisse max) avec deltas            │
│    • Graphique ligne SVG (AVANT vs APRÈS, base 100)                                 │
│    • Tableaux de composition détaillée (poids par actif)                            │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

**Cas d'usage 2 : Ajout d'actif avec explication IA (AWS Bedrock)**

```text
┌─────────────────────────────────────────────────────────────────────────────────────┐
│ 1. FRONTEND (React) : SimulationForm.tsx                                            │
│    Utilisateur sélectionne : persona + actif à ajouter + poids                      │
│    → Clic "Analyser"                                                                │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                    ↓ POST /api/interpret
┌─────────────────────────────────────────────────────────────────────────────────────┐
│ 2. API (FastAPI) : api/main.py::interpret_request()                                │
│    Validation : InterpretRequest (Pydantic)                                         │
│    → Appelle api/services.py::run_interpret()                                       │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────────────┐
│ 3. BACKEND : agent/service.py::analyze_request()                                   │
│    a) Chargement contexte (même que cas 1)                                          │
│    b) Simulation AVANT + APRÈS (même que cas 1)                                     │
│    c) ⭐ NOUVEAU : Génération explication IA via AWS Bedrock                        │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────────────┐
│ 4. AWS BEDROCK CONVERSE API (agent/service.py::_converse_loop)                     │
│    ┌─────────────────────────────────────────────────────────────────────────────┐ │
│    │ a) Création client boto3 :                                                   │ │
│    │    • boto3.client('bedrock-runtime', region_name='us-east-1')               │ │
│    │    • Credentials AWS depuis environnement ou ~/.aws/credentials             │ │
│    │    • Timeout : 30s connect, 90s read                                        │ │
│    │    • Retry : 3 tentatives avec backoff exponentiel                          │ │
│    └─────────────────────────────────────────────────────────────────────────────┘ │
│                                 ↓                                                    │
│    ┌─────────────────────────────────────────────────────────────────────────────┐ │
│    │ b) Construction du prompt :                                                  │ │
│    │    • System Instructions (SYSTEM_INSTRUCTIONS) : prompt de rôle             │ │
│    │    • Evidence Catalog : métriques injectées (avant/après, deltas)           │ │
│    │    • User Message : "Explique les compromis pour [persona] si ajoute        │ │
│    │                      [actif] à [poids]%"                                     │ │
│    │    • Tools : 4 outils disponibles au modèle :                               │ │
│    │      * compare_asset_metrics (compare 2 actifs)                             │ │
│    │      * analyze_diversification (évalue classes, secteurs)                   │ │
│    │      * compute_correlation (calcule corrélations)                           │ │
│    │      * search_evidence (cherche dans catalog)                               │ │
│    └─────────────────────────────────────────────────────────────────────────────┘ │
│                                 ↓                                                    │
│    ┌─────────────────────────────────────────────────────────────────────────────┐ │
│    │ c) Boucle Converse (max 8 appels) :                                         │ │
│    │    1. Appel bedrock.converse() :                                            │ │
│    │       • model_id = "us.anthropic.claude-opus-5-5" (ou BEDROCK_MODEL_ID)    │ │
│    │       • system = [{"text": SYSTEM_INSTRUCTIONS}]                            │ │
│    │       • messages = [{"role": "user", "content": [{"text": "..."}]}]        │ │
│    │       • toolConfig = {"tools": TOOL_SPECS}                                  │ │
│    │       • inferenceConfig = {"maxTokens": 2048, "temperature": 0}            │ │
│    │                                                                              │ │
│    │    2. Traitement réponse Bedrock :                                          │ │
│    │       • Si stopReason = "end_turn" : Fini, extraire texte                  │ │
│    │       • Si stopReason = "tool_use" :                                        │ │
│    │         → Exécuter tool via dispatch_tool() (Python local)                 │ │
│    │         → Injecter résultat tool dans next message                         │ │
│    │         → Re-appeler bedrock.converse() (boucle)                           │ │
│    │                                                                              │ │
│    │    3. Extraction narrative :                                                │ │
│    │       • Cherche dernier message avec role="assistant"                       │ │
│    │       • Extrait texte narratif (main_narrative)                             │ │
│    │       • Validation : has_unsafe_main_narrative() (NSFW, legal advice)      │ │
│    └─────────────────────────────────────────────────────────────────────────────┘ │
│                                 ↓                                                    │
│    ┌─────────────────────────────────────────────────────────────────────────────┐ │
│    │ d) Gestion d'erreurs AWS :                                                   │ │
│    │    • ThrottlingException : Quota dépassé → Mode dégradé                     │ │
│    │    • ModelTimeoutException : Timeout → Mode dégradé                         │ │
│    │    • ValidationException : Prompt invalide → Mode dégradé                   │ │
│    │    • ServiceUnavailableException : AWS down → Mode dégradé                  │ │
│    │    → Retour {"status": "partial", "warnings": ["Erreur AWS: ..."]}         │ │
│    └─────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                    ↓ JSON Response
┌─────────────────────────────────────────────────────────────────────────────────────┐
│ 5. API → FRONTEND : Réponse avec explication                                        │
│    {                                                                                 │
│      "status": "success",                                                            │
│      "analysis": { ... },  // Métriques (comme cas 1)                               │
│      "explanation": {                                                                │
│        "main_narrative": "... (texte généré par Claude Opus 5.5) ...",             │
│        "references": [                                                               │
│          {"id": "ev_001", "category": "metric", "label": "Rendement total", ...}   │
│        ]                                                                             │
│      },                                                                              │
│      "warnings": []  // Vide si succès                                              │
│    }                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────────────┐
│ 6. FRONTEND (React) : SimulationResults.tsx                                         │
│    Affichage des résultats :                                                        │
│    • Explication narrative (texte généré par IA)                                    │
│    • Métriques comparatives (avant/après)                                           │
│    • Graphiques                                                                     │
│    • Références aux sources de données                                              │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

#### Interface alternative : Streamlit

Streamlit (`ui/`) reste disponible comme interface historique pour tests rapides :

```bash
streamlit run app.py  # Port 8501
```

**Fonctionnalités Streamlit :**
- `ui/simulation.py` : Ajout d'un seul actif (équivalent React + Bedrock)
- `ui/portfolio_editor.py` : Modifications multiples (équivalent React sans Bedrock)

#### Dépendances externes critiques

| Service/Librairie | Rôle | Disponibilité requise |
|---|---|---|
| **AWS Bedrock** | Explication narrative IA | Optionnelle (mode dégradé si indisponible) |
| **Yahoo Finance** | Données historiques prix | Pré-téléchargées (data/market/prices_daily.csv) |
| **Banque du Canada** | Taux de change USD/CAD | Pré-téléchargées (data/market/fx_usdcad_daily.csv) |
| **boto3 + botocore** | Client AWS Python | Requise si Bedrock activé |
| **FastAPI** | Serveur API REST | Requise pour frontend React |
| **React + Vite** | Frontend moderne | Requise pour interface web |
| **Streamlit** | Interface alternative | Optionnelle (historique) |

**Mode dégradé (sans AWS) :**
```bash
export BEDROCK_MODEL_ID=""  # Désactive Bedrock explicitement
# OU : Ne pas configurer credentials AWS
# → API retourne "status": "partial" avec métriques mais sans explication
```

Le parcours principal est l'application React (`frontend/`), qui communique avec FastAPI (`api/`) pour accéder aux calculs Python et optionnellement à AWS Bedrock pour les explications narratives.

---

## Installation

Prérequis : **Python 3.12 ou plus récent**.

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

**Windows (PowerShell)**

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

`pip install -e .` installe les dépendances déclarées dans `pyproject.toml` (`streamlit`, `boto3`). Le moteur de simulation lui-même n'utilise que la bibliothèque standard Python.

---

## Reproduire les résultats

Les commandes ci-dessous supposent l'environnement virtuel activé. Sous Windows, remplacer `python` par `py -3` si nécessaire.

**Lancer tous les tests**

```bash
python -m unittest discover -s tests -v
```

**Régénérer les trois résultats de référence** (`results/amira_comparison.json`, `mateo_…`, `robert_…`)

```bash
python run_comparison.py --all
```

**Simuler un ajout personnalisé**

```bash
python run_comparison.py --persona robert --symbol TSLA --weight 5
python run_comparison.py --persona amira --symbol nvda --weight 7.5 --output results/test.json
python run_comparison.py --persona mateo --json
```

| Option | Rôle |
|---|---|
| `--persona` | `amira`, `mateo` ou `robert` (défaut : `amira`) |
| `--symbol`, `--weight` | Actif à ajouter et poids cible en %, à donner ensemble. Sans eux, le scénario de `data/scenarios.json` est utilisé. |
| `--output` | Enregistre le résultat complet en JSON |
| `--json` | Affiche le JSON complet au lieu du résumé |
| `--all` | Exécute les trois scénarios de référence et écrit les fichiers dans `results/` |

Exemple de résumé affiché :

```text
robert + TSLA 5% | 2021-11-12 → 2026-11-12 | 1228 dates | CAD
                        before     after       delta
Total return             41.5%     40.9%     -0.5 pp
Volatility                6.1%      6.7%     +0.6 pp
Max drop                 -7.3%     -8.3%     -1.0 pp
[tension] Préservation du capital
```

**Lancer l'interface** : voir la section [Interface](#interface).

---

## Utiliser le moteur depuis le code

```python
from alphaforge import run_analysis, EngineError

try:
    result = run_analysis("amira", "NVDA", 10)
except EngineError as error:
    print(error.code, error.message)
```

- `persona_id` : `"amira"`, `"mateo"` ou `"robert"`.
- `symbol` : un ticker de `data/market/assets_universe.csv`. Les espaces sont retirés et la casse est ignorée (`" nvda "` devient `"NVDA"`).
- `target_weight_pct` : un nombre strictement compris entre 0 et 100. `10` signifie 10 %.

### Codes d'erreur

| Code | Cause | Exemple |
|---|---|---|
| `INVALID_PERSONA` | Persona inconnu | `run_analysis("bob", "NVDA", 10)` |
| `UNKNOWN_SYMBOL` | Actif absent du jeu de données | `"APPLE"`, `""` |
| `INVALID_WEIGHT` | Poids non numérique, infini, NaN, ≤ 0 ou ≥ 100 | `0`, `100`, `"10"`, `True` |
| `ASSET_ALREADY_HELD` | Actif déjà présent dans le portefeuille | Amira + `SPY` |
| `INSUFFICIENT_DATA` | Moins de deux dates communes entre les actifs | — |

`EngineError` hérite de `ValueError`. Une incohérence dans les fichiers de données (doublon, prix négatif) lève une `ValueError` ordinaire.

### Format du résultat

| Clé | Contenu |
|---|---|
| `persona` | Profil complet : objectif, horizon, préférences, informations manquantes |
| `scenario` | Actif ajouté, poids cible, règle de financement |
| `period` | Première et dernière date communes, nombre d'observations |
| `currency` | `CAD` |
| `before`, `after` | Pondérations par actif et par classe, indicateurs |
| `delta_after_minus_before` | Écarts **après moins avant** |
| `series` | `dates`, `before`, `after` : courbes en base 100 |
| `methodology`, `sources`, `limitations` | Conventions, sources identifiées (`id` stable), limites |

**Unités** : pondérations en points de pourcentage (`10` = 10 %), indicateurs en décimales (`0.12` = 12 %). Une baisse maximale qui passe de `-0.15` à `-0.10` donne un écart de `+0.05` : la baisse historique est **moins** profonde de 5 points.

---

## Méthodes de calcul

### Données

Jeu de départ AlphaForge (`data/market/`, extrait le 2026-11-13), du **2021-11-12 au 2026-11-12** :

- prix quotidiens de Yahoo Finance (via `yfinance`) ; on utilise **`adj_close`**, ajusté pour les dividendes et les fractionnements ;
- taux USD/CAD quotidien de la Banque du Canada (série `FXUSDCAD`).

### 1. Financement de l'ajout

Pour un poids cible *p*, chaque position existante est multipliée par **(1 − p/100)**, puis *p* % est attribué au nouvel actif. Le total reste 100 %.

> Amira + NVDA 10 % : SPY 40 → 36, QQQ 30 → 27, SHOP.TO 15 → 13,5, BTC-USD 15 → 13,5, NVDA 10.

### 2. Conversion en CAD

Tous les résultats sont en CAD. Un prix en USD est multiplié par le taux USD/CAD (CAD pour 1 USD) **du jour même ou du dernier jour antérieur disponible**, par exemple lors d'un jour férié canadien. **Aucun taux futur n'est utilisé.** Les prix des actifs eux-mêmes ne sont jamais reportés d'un jour à l'autre.

### 3. Alignement des calendriers

Les actions et FNB comptent 1 255 jours de cotation, les cryptomonnaies 1 827 (7 jours sur 7), et les jours fériés diffèrent entre la TSX et les marchés américains. On garde **uniquement les dates où tous les actifs, avant et après, ont un prix** : 1 228 dates communes pour chacun des trois scénarios. Les deux portefeuilles sont comparés sur exactement les mêmes dates.

### 4. Simulation acheter-et-conserver

On investit 1 à la première date commune selon les pondérations initiales, puis on conserve des **quantités fixes**, sans rééquilibrage. Les pondérations dérivent ensuite avec les performances. Les courbes `series` sont exprimées en **base 100** à la première date.

### 5. Indicateurs

Avec *V₀ … Vₙ* les valeurs du portefeuille et *rₜ = Vₜ / Vₜ₋₁ − 1* :

| Indicateur | Formule |
|---|---|
| Rendement total | *Vₙ / V₀ − 1* |
| Volatilité annualisée | écart-type échantillonnal des *rₜ* × √252 |
| Baisse maximale | min sur *t* de (*Vₜ / max(V₀ … Vₜ) − 1*) |

### 6. Vérifications

Les tests automatisés vérifient les calculs, les contrats de l'agent et les parcours AppTest. Ils incluent des exemples simples calculés à la main, indépendamment des données réelles :

- conversion : un prix de 10 USD un jour sans taux, entre un taux de 1,25 la veille et de 1,30 le lendemain, donne **12,50 CAD** et non 13,00 ;
- indicateurs : la série [100, 110, 99] donne un rendement de **−1 %**, une baisse maximale de **−10 %** et une volatilité de √0,02 × √252 ;
- alignement : seules les dates présentes pour tous les actifs sont conservées ;
- pour chaque scénario : totaux de 100 %, courbes qui commencent à 100, dernier point cohérent avec le rendement total, aucune valeur NaN dans le JSON.

---

## Résultats des trois scénarios

Période du 2021-11-12 au 2026-11-12, 1 228 dates communes, en CAD. Écarts en points de pourcentage (après − avant).

| Scénario | Rendement total | Volatilité annualisée | Baisse maximale |
|---|---|---|---|
| **Amira + NVDA 10 %** | 73,7 % → 118,6 % (**+44,9**) | 21,8 % → 25,6 % (**+3,8**) | −38,6 % → −40,0 % (**−1,4**) |
| **Mateo + XOM 10 %** | 66,2 % → 85,1 % (**+18,9**) | 9,6 % → 9,3 % (**−0,4**) | −16,2 % → −8,8 % (**+7,4**) |
| **Robert + TSLA 5 %** | 41,5 % → 40,9 % (**−0,5**) | 6,1 % → 6,7 % (**+0,6**) | −7,3 % → −8,3 % (**−1,0**) |

Ce que les chiffres montrent, sans constituer un verdict :

- **Amira** : sur cette période, l'ajout de NVDA augmente fortement le rendement historique, mais aussi la volatilité et la baisse maximale. La part de NVDA déjà détenue indirectement par SPY et QQQ n'est pas mesurable avec les seuls prix.
- **Mateo** : XOM améliore le rendement et réduit la baisse maximale, car l'énergie a progressé en 2022 quand les actions et les obligations reculaient. Ce gain financier doit être mis en regard de ses préférences ESG.
- **Robert** : même à 5 %, TSLA réduit légèrement le rendement historique et augmente la volatilité et la baisse maximale, ce qui crée une tension avec l'objectif de préservation du capital.

---

## Contrôles du profil et preuves ESG

Les contrôles sont exécutés par `alphaforge/profile_checks.py`. Ils conservent les statuts `consistent`, `tension` et `insufficient_information` ainsi que les preuves et les informations manquantes propres à chaque contrôle. Une information absente n'est pas transformée en conclusion positive ou négative. Les limites et références ESG datées sont conservées dans le rapport détaillé.

---

## Agent IA et AWS

`agent.service.analyze_request` orchestre deux outils locaux déterministes : `simulate_portfolio_change`, puis `check_profile`. Bedrock Converse produit ensuite une explication structurée, validée par rapport aux preuves et métriques du moteur. Une demande en langage naturel peut être interprétée séparément; le code vérifie le profil, l'actif et le pourcentage explicite avant d'afficher les paramètres à confirmer. Les questions de suivi utilisent le scénario et les preuves actuellement affichés.

Par défaut, le service utilise le profil d'inférence `us.anthropic.claude-opus-5-5`; `BEDROCK_MODEL_ID` permet de le remplacer. Si Bedrock ou l'authentification AWS est indisponible, le service conserve les calculs et les contrôles avec le statut `partial`, et indique la cause détectée lorsqu'elle est connue. Il ne présente pas un texte de remplacement comme une réponse du modèle. La comparaison A/B exécute deux analyses indépendantes du même actif et bloque l'affichage si leurs dates ne correspondent pas.

Diagnostic de l'accès AWS : voir [docs/aws_bedrock_diagnostic.md](docs/aws_bedrock_diagnostic.md).

---

## Application web React et API FastAPI

L'entrée principale documentée est désormais une application React + TypeScript
dans `frontend/`, reliée à l'API FastAPI de `api/`. Le navigateur ne lit jamais
les fichiers de marché et ne reçoit aucune clé AWS : tous les calculs, contrôles
et appels Bedrock restent côté Python.

### Lancement de l'application

**Prérequis** : Python 3.12+, Node.js 20+ et npm.

#### Windows (PowerShell)

```powershell
# Terminal 1 — Lancer l'API backend
py -3.12 -m pip install -e .
$env:BEDROCK_MODEL_ID = "us.anthropic.claude-opus-5-5"
py -3.12 -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2 — Lancer le frontend
cd frontend
npm install
npm run dev
```

#### macOS / Linux

```bash
# Terminal 1 — Lancer l'API backend
python3 -m pip install -e .
export BEDROCK_MODEL_ID="us.anthropic.claude-opus-5-5"
python3 -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2 — Lancer le frontend
cd frontend
npm install
npm run dev
```

**Ouvrir l'application** : <http://localhost:5173>

Vite relaie automatiquement `/api` vers `http://127.0.0.1:8000`. Pour une API différente, définir `VITE_API_URL` avant de démarrer Vite.

**Mode sans AWS** : Pour utiliser l'application sans Bedrock, définir `$env:BEDROCK_MODEL_ID = ""` (Windows) ou `export BEDROCK_MODEL_ID=""` (macOS/Linux) avant de lancer l'API. Les calculs et contrôles déterministes restent disponibles avec le statut `partial`; l'interface indique alors que l'explication IA est indisponible.

### Parcours utilisateur dans l'application React

L'application offre plusieurs parcours pour explorer les simulations de portefeuille :

#### 1. Parcours découverte (démarrage rapide)

1. **Page d'accueil** : Vue d'ensemble de l'application avec trois profils fictifs
2. **Choisir un profil** : Cliquer sur Amira, Mateo ou Robert dans le "Démarrage rapide"
3. **Simuler un ajout** : Sélectionner un actif et définir un poids (1-50%)
4. **Lancer l'analyse** : Le système calcule les métriques et génère une explication IA
5. **Explorer les résultats** : Comparer avant/après, consulter les graphiques et les compromis

#### 2. Parcours personnalisation (éditeur de portefeuille)

1. **Accéder à l'éditeur** : Menu "Éditeur de portefeuille"
2. **Sélectionner un profil** : Amira, Mateo ou Robert
3. **Ajuster les poids existants** : Utiliser les curseurs pour modifier les pondérations
4. **Ajouter de nouveaux actifs** : Sélectionner parmi les actifs disponibles
5. **Définir les nouvelles pondérations** : Ajuster les poids des actifs ajoutés
6. **Normaliser** : Option automatique pour ajuster à 100%
7. **Analyser** : Lancer une analyse complète du portefeuille personnalisé
8. **Consulter les résultats** : Comparer les performances avant/après

#### 3. Parcours exploration approfondie

1. **Consulter les profils** : Page "Profils fictifs" pour voir tous les détails (objectifs, horizons, préférences)
2. **Vérifier la cohérence** : Page "Cohérence du scénario" pour identifier les tensions avec le profil
3. **Poser des questions** : Assistant IA flottant accessible via l'icône de chat
   - Questions liées à l'analyse en cours
   - Explications des compromis
   - Clarifications sur les métriques
4. **Consulter les sources** : Page "Sources et méthode" pour la transparence méthodologique

#### 4. Parcours gestion des scénarios

1. **Enregistrer un scénario** : Après une analyse, cliquer sur "Enregistrer"
2. **Consulter les scénarios** : Page "Scénarios" pour voir tous les scénarios enregistrés
3. **Rouvrir un scénario** : Charger les paramètres d'un scénario précédent
4. **Comparer** : Analyser plusieurs variantes du même profil

#### Navigation et fonctionnalités transversales

- **Menu latéral** : Navigation entre toutes les pages
- **Thème clair/sombre** : Bouton en haut à droite
- **Indicateur de scénario actif** : Affiche le profil et l'actif en cours dans le menu latéral
- **Assistant flottant** : Accessible depuis toutes les pages pour poser des questions

### Architecture technique

Les réponses nécessaires aux questions de suivi sont conservées dans la mémoire
du processus API pendant une heure, avec un maximum de 100 entrées. Elles sont
perdues au redémarrage. Ce stockage convient à la démonstration locale avec un
seul processus, pas à un déploiement multi-instance.

Les questions de l'assistant sont indépendantes et liées à une analyse précise; 
aucun historique de chat n'est transmis. Les scénarios enregistrés sont conservés 
dans le `localStorage` du navigateur et contiennent les paramètres et la date 
d'enregistrement, pas un instantané des résultats historiques. La résolution des 
preuves de l'analyse utilise le cache mémoire API et devient indisponible après 
son expiration.

Les requêtes longues affichent un état de chargement et une réponse devenue 
obsolète est ignorée si le scénario change entre-temps.

### Vérifications frontend

```powershell
cd frontend
npm test
npm run typecheck
npm run lint
npm run build
```

### Interface Streamlit historique

L'interface Streamlit (`app.py`, styles dans `styles/style.css`) guide l'utilisateur à travers trois étapes : choisir un personnage fictif, décrire un ajout d'actif, puis comprendre les résultats calculés. Les cartes des profils reprennent uniquement les objectifs, horizons et préférences documentés. Les autres paramètres sont modifiables depuis l'interface.

Les profils et portefeuilles fournis dans le dépôt sont des données de démonstration; les prix historiques proviennent des fichiers de marché du projet. L'application n'exécute aucune transaction. À la demande explicite de l'utilisateur, elle appelle le service AlphaForge; celui-ci utilise Bedrock Converse avec le profil par défaut documenté ou l'identifiant défini par `BEDROCK_MODEL_ID`. Des identifiants AWS valides et actifs restent nécessaires. Les réponses simulées sont réservées aux tests; elles ne sont pas utilisées par l'application.

### Lancement

Depuis la racine du dépôt, avec l'environnement virtuel activé (voir [Installation](#installation)) :

```bash
streamlit run app.py
```

Si la commande `streamlit` n'est pas reconnue, utiliser :

```bash
python -m streamlit run app.py
```

Sous Windows, remplacer `python` par `py -3`.

Le terminal doit contenir les identifiants temporaires AWS Workshop Studio.
Le profil d'inférence est déjà configuré par défaut. Pour en choisir un autre :

```powershell
$env:BEDROCK_MODEL_ID = "us.anthropic.claude-opus-5-5"
python -m streamlit run app.py
```

La région utilisée par le service est `us-east-1`. L'interface ne demande et
n'enregistre aucune clé AWS. Si l'accès AWS n'est pas authentifié, l'application
indique que les identifiants doivent être renouvelés ou configurés.

Streamlit affiche l'adresse de l'application dans le terminal, par défaut <http://localhost:8501>, et ouvre normalement le navigateur automatiquement. Pour arrêter l'application, appuyer sur `Ctrl+C` dans le terminal. Après une modification de `app.py` ou de `styles/style.css`, il suffit de recharger la page; une modification de `.streamlit/config.toml` demande de relancer l'application.

### Parcours utilisateur

1. **Choisir le thème (facultatif).** Le sélecteur dans la barre latérale permet de passer de l'affichage Clair à l'affichage Sombre.

2. **Choisir une situation fictive.** Choisir la carte d'Amira, Mateo ou Robert. La carte résume son objectif, son horizon et ses préférences documentés; la barre latérale donne accès au portefeuille fictif initial. La saisie en langage naturel est facultative.

3. **Décrire le changement.**
   - « Actif » : choisir un actif de `data/market/assets_universe.csv` que le persona ne détient pas déjà. Un actif est proposé par défaut, selon le scénario de référence de `data/scenarios.json`;
   - « Part du portefeuille (%) » : régler le poids de l'actif ajouté, de 1 % à 50 % par pas de 0,5 %. Ce poids est financé par une réduction proportionnelle des positions existantes;
   - l'aperçu du scénario affiche le nom complet et le symbole avant calcul. Pour une demande en langage naturel, les paramètres compris doivent être vérifiés avant de cliquer sur « Analyser le scénario ».

4. **Lancer l'analyse.** Cliquer sur « Analyser le scénario ». Un seul appel au service orchestre la simulation historique, les contrôles et l'explication Bedrock.

5. **Lire le rapport** :
   - **Scénario analysé** : nom complet de l'actif, poids ajouté, réduction proportionnelle des autres placements, dates en français et résultats en dollars canadiens;
   - les trois **comparaisons avant/après** et la **courbe historique** dans la zone principale;
   - **L'éclairage de l'agent** : compromis relié au profil, constats et informations manquantes;
   - **Ce qui change** : accès aux pondérations détaillées;
   - **Comprendre le calcul** et **Consulter les sources** : sections repliées;
   - **Mode technique** (désactivé par défaut) : preuves, valeurs brutes, contrôles individuels, données et traces destinés à l'équipe et au jury.

6. **Comparer ou approfondir.** Comparer deux poids du même actif sur les mêmes dates, ou poser une question liée au rapport. Une question qui propose un autre pourcentage doit passer par l'interprétation, puis un nouveau calcul explicite; le modèle n'est pas autorisé à estimer le résultat.

7. **Explorer d'autres scénarios.** Modifier l'actif, le poids ou le personnage, puis relancer explicitement l'analyse. Le dernier résultat reste en session lors d'un changement de thème ou d'un rerun; aucun nouvel appel AWS n'est effectué sans action explicite. Si les paramètres changent, l'ancien rapport est masqué jusqu'au nouveau calcul.

### Ce que l'interface affiche et ne fait pas

- En état `success`, la synthèse qualitative de Bedrock n'est affichée que si elle ne contient ni décimales brutes ni identifiants internes; les comparaisons chiffrées proviennent des métriques validées du moteur.
- En état `partial`, les calculs et contrôles disponibles restent affichés avec un résumé qualitatif dérivé des résultats structurés; aucune réponse locale n'est présentée comme une réponse de Claude.
- En état `error`, le rapport affiche une explication accessible; le code et les détails ne sont accessibles qu'en mode technique.
- Les chiffres proviennent du moteur de simulation. L'interface ne fait que les mettre en forme.
- Les résultats décrivent une période historique simulée; ils ne préjugent pas des résultats futurs. Aucune transaction n'est exécutée.

### Thèmes

Les thèmes Clair et Sombre sont définis dans `app.py` (dictionnaire `THEMES`, qui fournit les couleurs) et dans `styles/style.css` (mise en forme des cartes, boutons, tableaux et alertes). Pour modifier une couleur, changer sa valeur dans `THEMES`; pour modifier la forme d'un élément, éditer `styles/style.css`.

### Captures d'écran et démonstration

#### Parcours oral de 3 à 5 minutes

1. **Le problème (30 s)** — Les chiffres d'un portefeuille ne suffisent pas à expliquer les compromis et les inconnues.
2. **Amira (45 s)** — Choisir sa carte et saisir « Pour Amira, tester 15 % de NVIDIA ». Montrer les paramètres compris avant de lancer l'analyse.
3. **Résultat calculé (60 s)** — Montrer les trois comparaisons historiques, la courbe, le lien avec l'objectif de croissance et l'exposition indirecte aux FNB qui reste inconnue.
4. **Variante A/B (45 s)** — Comparer deux poids du même actif; vérifier que la période commune est affichée et que les résultats changent.
5. **Question de suivi (45 s)** — Demander « Et avec 5 % ? », vérifier la variante comprise, l'appliquer et relancer explicitement le moteur.
6. **Autre profil et limites (45 s)** — Choisir Robert avec TSLA, puis rappeler qu'il s'agit d'une simulation historique, sans frais, sans prévision et sans transaction réelle. Montrer les sources et, brièvement, le mode technique.

#### Mode de secours sans AWS

Depuis un terminal PowerShell, sans identifiants AWS, désactivez explicitement
Bedrock pour ce lancement :

```powershell
$env:BEDROCK_MODEL_ID = ""
python -m streamlit run app.py
```

Le moteur local conserve les résultats et les contrôles avec le statut `partial`. La compréhension du langage naturel et les réponses Bedrock de suivi sont signalées indisponibles; sélectionner le personnage, l'actif et le poids manuellement. Ne pas présenter cette démonstration hors ligne comme une réponse du modèle. La comparaison A/B fonctionne localement et affiche ses calculs sur une période identique.

Les captures d'écran et la vidéo officielle de démonstration restent à produire.

---

## Limites

- **Historique, pas prévision** : les rendements passés ne préjugent pas des rendements futurs.
- **Biais du survivant** : l'univers de 31 actifs a été choisi en 2026 parmi des titres importants aujourd'hui.
- **Frais, taxes et coûts de transaction** ne sont pas modélisés.
- **√252 est une convention approximative** : l'alignement des calendriers rend les intervalles entre observations irréguliers.
- **La baisse maximale** est mesurée sur les dates retenues et peut omettre une baisse survenue entre deux observations.
- **Composition des FNB inconnue** : l'exposition indirecte (par exemple à NVDA via QQQ) n'est pas mesurée.
- **Aucune cote ESG** dans le jeu de départ : les constats ESG reposent sur des preuves datées et documentées.
- **Informations inconnues** : la capacité à absorber une perte, les besoins de liquidités et les retraits prévus restent inconnus pour les trois personas. Rien n'est déduit de la profession, de l'âge ou de la situation familiale.

---

## Structure du projet

```text
DATATHON-POLYFINANCES/
├── alphaforge/
│   ├── engine.py            Moteur de simulation            
│   └── profile_checks.py    Contrôles du profil et ESG      
├── app.py                   Interface Streamlit             
├── styles/style.css         Thèmes de l'interface           
├── scripts/                 Diagnostic AWS Bedrock          
├── run_comparison.py        Commande de simulation
├── data/
│   ├── market/              Jeu de départ AlphaForge (prix, change, univers, sources)
│   ├── personas.json        Profils fictifs
│   ├── portfolios.json      Portefeuilles fictifs
│   ├── scenarios.json       Scénarios de référence
│   ├── esg_evidence.json    Preuves ESG datées
│   └── validation_report.json
├── results/                 Résultats de référence des trois scénarios
├── tests/                   Tests automatisés
├── docs/                    Documentation complémentaire
└── pyproject.toml
```

---

## Sources

| id | Source | Date | Utilisation |
|---|---|---|---|
| `src_prices_daily` | Yahoo Finance via `yfinance` | extrait le 2026-11-13 | Prix quotidiens `adj_close` |
| `src_fx_usdcad` | Banque du Canada, API Valet, série `FXUSDCAD` | extrait le 2026-11-13 | Conversion USD → CAD |
| `src_assets_universe` | Organisateurs du datathon | 2026-11-13 | Univers de 31 actifs, devises, classes |
| `src_personas` | Équipe AlphaForge | — | Profils fictifs inspirés du cas officiel |
| `src_portfolios` | Équipe AlphaForge | — | Portefeuilles fictifs de démonstration |

Le détail de la provenance et des conditions d'utilisation figure dans [data/market/README.md](data/market/README.md) et `data/market/sources_metadata.csv`.
