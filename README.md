# AlphaForge AI — Datathon PolyFinances 2026

> **Si je consacre X % de mon portefeuille à cet actif, qu'est-ce qui change et quels compromis dois-je comprendre compte tenu de mon profil ?**

AlphaForge AI est un assistant de simulation. Il compare un portefeuille fictif **avant** et **après** l'ajout d'un actif, sur des données historiques réelles, puis vérifie la cohérence du changement avec le profil de l'investisseur et explique les compromis.

> ⚠️ **Avertissement.** Il s'agit d'une comparaison historique hypothétique à but pédagogique. Ce n'est ni une prévision, ni une recommandation, ni un conseil en placement. Les personas et les portefeuilles sont fictifs.

### Les trois parcours

| Persona | Profil | Portefeuille fictif | Scénario testé |
|---|---|---|---|
| **Amira** | Risque élevé, 15 ans et plus, croissance à long terme | SPY 40 %, QQQ 30 %, SHOP.TO 15 %, BTC-USD 15 % | Ajouter **NVDA à 10 %** : concentration technologique |
| **Mateo** | Risque modéré, 8 à 12 ans, préférences ESG | ESGV 40 %, XBB.TO 30 %, FTS.TO 15 %, GLD 15 % | Ajouter **XOM à 10 %** : compatibilité ESG |
| **Robert** | Risque faible à modéré, 3 à 5 ans, préservation du capital | ZST.TO 40 %, XBB.TO 30 %, GLD 15 %, XIU.TO 15 % | Ajouter **TSLA à 5 %** : volatilité et préservation du capital |

L'interface permet aussi de tester n'importe quel actif du jeu de données, à n'importe quel poids.

### Architecture

```text
Interface (app.py)
   │  persona, actif, poids
   ▼
Agent IA sur AWS Bedrock ──► outil 1 : moteur de simulation   (alphaforge/engine.py)
   │                     └─► outil 2 : contrôles du profil    (alphaforge/profile_checks.py)
   ▼
Explication structurée : changements, cohérences, tensions, limites
```

Le **code calcule**, le **modèle explique**. Aucun chiffre n'est produit par le modèle de langage.

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

Le dépôt contient 49 tests automatisés. Les calculs sont vérifiés sur des exemples simples calculés à la main, indépendamment des données réelles :

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

> _À compléter par la Personne 4 : contrôles par persona, statuts `consistent` / `tension` / `insufficient_information`, preuves ESG utilisées (source, date, limites), seuils choisis par l'équipe, tests d'acceptation, lien vers le résumé d'une page._

---

## Agent IA et AWS

> _À compléter par la Personne 2 : architecture de l'agent, outils appelés, modèle Bedrock et région (sans secret ni identifiant), commandes pour lancer et tester l'agent, comportement en cas d'échec AWS (statut `partial`), exemple de `tool_trace`._

Diagnostic de l'accès AWS : voir [docs/aws_bedrock_diagnostic.md](docs/aws_bedrock_diagnostic.md).

---

## Interface

> _À compléter par la Personne 3 : lancement (`streamlit run app.py`), parcours utilisateur, captures d'écran, lien vers la vidéo de démonstration._

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
│   ├── engine.py            Moteur de simulation            (Personne 1)
│   └── profile_checks.py    Contrôles du profil et ESG      (Personne 4)
├── app.py                   Interface Streamlit             (Personne 3)
├── styles/style.css         Thèmes de l'interface           (Personne 3)
├── scripts/                 Diagnostic AWS Bedrock          (Personne 2)
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
