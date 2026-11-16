# AlphaForge AI — Datathon PolyFinances 2026

> **Si je consacre X % de mon portefeuille à cet actif, qu'est-ce qui change et quels compromis dois-je comprendre compte tenu de mon profil ?**

> 🌐 **Application en ligne : <https://dnljlar20i0ps.cloudfront.net>**

AlphaForge AI est une application pédagogique de simulation. Elle compare un portefeuille fictif **avant** et **après** l'ajout d'un actif, sur des données historiques réelles, puis examine la cohérence du changement avec le profil et explique les compromis.

> ⚠️ **Avertissement.** Il s'agit d'une comparaison historique hypothétique à but pédagogique. Ce n'est ni une prévision, ni une recommandation, ni un conseil en placement. Les personas et les portefeuilles sont fictifs.

### Les parcours

| Persona | Profil | Portefeuille fictif | Scénario testé |
|---|---|---|---|
| **Amira** | Risque élevé, 15 ans et plus, croissance à long terme | SPY 40 %, QQQ 30 %, SHOP.TO 15 %, BTC-USD 15 % | Ajouter **NVDA à 10 %** : concentration technologique |
| **Mateo** | Risque modéré, 8 à 12 ans, préférences ESG | ESGV 40 %, XBB.TO 30 %, FTS.TO 15 %, GLD 15 % | Ajouter **XOM à 10 %** : compatibilité ESG |
| **Robert** | Risque faible à modéré, 3 à 5 ans, préservation du capital | ZST.TO 40 %, XBB.TO 30 %, GLD 15 %, XIU.TO 15 % | Ajouter **TSLA à 5 %** : volatilité et préservation du capital |
| **Alex** 🚩 *(démo)* | Risque élevé, 15 ans et plus, mais objectif de préservation du capital | SPY 40 %, QQQ 30 %, BTC-USD 20 %, GLD 10 % | Ajouter **NVDA à 10 %** : profil contradictoire, signalé par un drapeau rouge |

L'interface permet aussi de tester n'importe quel actif du jeu de données, à n'importe quel poids.

### Architecture

AlphaForge utilise une architecture multi-couches avec séparation claire entre calcul déterministe (Python) et explication narrative (AWS Bedrock / Claude). Le **code calcule**, le **modèle explique et confronte les conclusions aux preuves**. Aucun chiffre n'est produit par le modèle de langage.

```text
Interface React / TypeScript (frontend/)
   │  profil, actif, poids
   ▼
API FastAPI (api/)
   │                     ├─► moteur de simulation            (alphaforge/engine.py)
   │                     ├─► contrôles du profil              (alphaforge/profile_checks.py)
   │                     ├─► vérification des contradictions  (alphaforge/contradiction_checks.py)
   │                     └─► explication et contre-analyse IA (Bedrock)
   ▼
Résultat structuré : métriques, contrôles, preuves et limites
```

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

`pip install -e .` installe les dépendances Python déclarées dans `pyproject.toml`. Le moteur de simulation lui-même n'utilise que la bibliothèque standard Python. L'interface React demande en plus Node.js 20+ (voir [Interface web](#interface-web-react)).

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
| `--persona` | `amira`, `mateo`, `robert` ou `alex` (défaut : `amira`) |
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

**Lancer l'interface** : voir la section [Interface web](#interface-web-react).

---

## Utiliser le moteur depuis le code

```python
from alphaforge import run_analysis, EngineError

try:
    result = run_analysis("amira", "NVDA", 10)
except EngineError as error:
    print(error.code, error.message)
```

- `persona_id` : `"amira"`, `"mateo"`, `"robert"` ou `"alex"`.
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

**En bref :** on prend le portefeuille du persona, on y ajoute l'actif choisi, puis on rejoue les deux versions (avant / après) sur les mêmes jours passés et on compare trois chiffres : le rendement, la volatilité et la pire baisse.

### Données utilisées

Jeu de départ AlphaForge (`data/market/`, extrait le 2026-11-13), du **2021-11-12 au 2026-11-12** :

- **Prix** : prix quotidiens de Yahoo Finance (via `yfinance`). On utilise `adj_close`, c'est-à-dire le prix corrigé des dividendes et des fractionnements d'actions.
- **Taux de change** : USD/CAD quotidien de la Banque du Canada (série `FXUSDCAD`).

### Les étapes, une par une

**1. Faire de la place pour le nouvel actif.**

Pour ajouter un actif à *p* %, on réduit toutes les positions existantes dans la même proportion (× **(1 − p/100)**). Le total reste 100 %.

> Exemple — Amira + NVDA 10 % : SPY 40 → 36, QQQ 30 → 27, SHOP.TO 15 → 13,5, BTC-USD 15 → 13,5, NVDA 10.

**2. Tout mettre en dollars canadiens.**

Un prix en USD est multiplié par le taux USD/CAD **du jour même**, ou, s'il manque (jour férié au Canada), **de la veille la plus proche**. On n'utilise jamais un taux du futur. Les prix des actifs, eux, ne sont jamais recopiés d'un jour à l'autre.

**3. Garder seulement les jours communs.**

Les actions cotent 5 jours sur 7, les cryptos 7 jours sur 7, et les jours fériés diffèrent entre la Bourse de Toronto et les marchés américains. On garde **uniquement les dates où tous les actifs ont un prix** : 1 228 dates pour chacun des trois scénarios. Avant et après sont donc comparés sur exactement les mêmes jours.

**4. Acheter et conserver.**

On investit 1 $ le premier jour selon les pondérations, puis on ne touche plus à rien : les **quantités restent fixes**, sans rééquilibrage. Les courbes du graphique partent de **100**.

**5. Calculer les trois indicateurs.**

Avec *Vₜ* la valeur du portefeuille au jour *t* et *rₜ = Vₜ / Vₜ₋₁ − 1* le rendement d'un jour :

| Indicateur | Ce que ça veut dire | Formule |
|---|---|---|
| **Rendement total** | Combien le portefeuille a gagné ou perdu sur toute la période | *Vₙ / V₀ − 1* |
| **Volatilité annualisée** | À quel point la valeur bouge d'un jour à l'autre (plus c'est haut, plus c'est agité) | écart-type des *rₜ* × √252 |
| **Baisse maximale** | La pire chute depuis un sommet précédent | min de (*Vₜ / plus haut atteint jusqu'à t* − 1) |

**Comment lire les écarts :** l'écart est toujours **après − avant**, en points de pourcentage. Pour la baisse maximale, un écart **positif** est une bonne nouvelle : passer de −15 % à −10 % donne +5 points, la chute est moins profonde.

### Comment on a vérifié les calculs

Des tests automatisés comparent le moteur à des exemples simples calculés à la main :

- **Change** : 10 USD un jour sans taux, avec 1,25 la veille et 1,30 le lendemain, donne **12,50 CAD** (taux de la veille), pas 13,00.
- **Indicateurs** : la série [100, 110, 99] donne un rendement de **−1 %**, une baisse maximale de **−10 %** et une volatilité de √0,02 × √252.
- **Dates** : seules les dates présentes pour tous les actifs sont gardées.
- **Pour chaque scénario** : les pondérations font 100 %, les courbes partent de 100, le dernier point correspond au rendement total, et aucune valeur n'est vide (NaN).

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

### Drapeau rouge : profils contradictoires

Certains profils se contredisent eux-mêmes, avant même d'ajouter un actif. `alphaforge/contradiction_checks.py` repère ces contradictions directement dans les déclarations du profil et les ajoute aux contrôles (statut `tension`) :

| Identifiant | Contradiction détectée | En langage simple |
|---|---|---|
| `speculation_preference_conflict` | Préférence pour les cryptos ou la spéculation **et** volonté de limiter la spéculation | « Aime les cryptos, mais veut éviter la spéculation. » |
| `risk_objective_conflict` | Tolérance au risque élevée **et** objectif de préservation du capital | « Accepte beaucoup de risque, mais veut protéger son argent. » |

Le persona de démonstration **Alex** déclenche les deux. Les autres personas n'en déclenchent aucune.

- **API** : `/api/bootstrap` renvoie pour chaque persona une liste `contradictions` (`id`, `title`, `message`), vide si le profil est cohérent.
- **Interface** : un badge rouge « Profil contradictoire » apparaît sur la carte du profil et dans le démarrage rapide, un drapeau dans le sélecteur de profil, et un encadré « Drapeau rouge : Alex se contredit » sur la page Simuler. Sur la page Cohérence, les contradictions sont comptées à part, surlignées en rouge et ouvertes par défaut.
- **En ligne de commande** : `python run_comparison.py --persona alex` affiche les deux contradictions sous les résultats.

Une contradiction n'empêche pas la simulation : elle signale qu'il faut clarifier les objectifs du profil avant d'interpréter les résultats.

---

## Agent IA et AWS

`agent.service.analyze_request` orchestre deux outils locaux déterministes : `simulate_portfolio_change`, puis `check_profile`. Bedrock Converse produit ensuite une explication structurée, validée par rapport aux preuves et métriques du moteur.

Une demande en langage naturel peut être interprétée séparément; le code vérifie le profil, l'actif et le pourcentage explicite avant d'afficher les paramètres à confirmer.

### Chat IA contextuel

Un assistant conversationnel permet de poser des questions de suivi en langage naturel sur l'analyse affichée. Il utilise le scénario courant, les métriques calculées et les preuves disponibles pour fournir des explications contextualisées.

Les questions peuvent notamment porter sur :

- Les changements entre le portefeuille avant et après.
- Les compromis associés à l'ajout d'un actif.
- Les indicateurs de rendement, de volatilité et de baisse maximale.
- La cohérence du scénario avec les objectifs et les préférences du persona.
- Les preuves et les limites qui soutiennent les conclusions.

Les questions de suivi utilisent le scénario et les preuves actuellement affichés.

### Contre-analyse et détection des contradictions

Une fonctionnalité de contre-analyse permet de confronter les conclusions de l'analyse aux données, aux métriques et aux preuves présentes dans le dossier.

Elle vise à :

- Repérer les contradictions entre les conclusions et les données historiques.
- Vérifier si les explications sont cohérentes avec les indicateurs calculés.
- Faire ressortir les compromis ou les éléments qui pourraient nuancer une conclusion.
- Identifier les informations manquantes qui empêchent de tirer une conclusion solide.
- Mettre en évidence les limites des preuves disponibles, notamment pour les préférences ESG.

Cette fonctionnalité permet de ne pas simplement accepter une conclusion générée par l'IA, mais de la questionner et de la confronter aux éléments concrets du dossier.

### AWS Bedrock

Par défaut, le service utilise le profil d'inférence `us.anthropic.claude-opus-5-5`; `BEDROCK_MODEL_ID` permet de le remplacer.

Si Bedrock ou l'authentification AWS est indisponible, le service conserve les calculs et les contrôles avec le statut `partial`, et indique la cause détectée lorsqu'elle est connue. Il ne présente pas un texte de remplacement comme une réponse du modèle.

La comparaison A/B exécute deux analyses indépendantes du même actif et bloque l'affichage si leurs dates ne correspondent pas.

Diagnostic de l'accès AWS : voir [docs/aws_bedrock_diagnostic.md](docs/aws_bedrock_diagnostic.md).

---

## Interface web (React)

L'interface est une application **React + TypeScript** (dossier `frontend/`), construite avec Vite, Tailwind CSS et Recharts pour les graphiques. Elle parle à l'API Python FastAPI (dossier `api/`).

**Le navigateur ne fait aucun calcul.** Il envoie le profil, l'actif et le poids à l'API, puis affiche les résultats. Les calculs, les contrôles et les appels à Bedrock restent côté Python, et aucune clé AWS n'arrive dans le navigateur.

### Lancer l'application

**Prérequis** : Python 3.12+, Node.js 20+ et npm. Il faut **deux terminaux**.

#### Terminal 1 — l'API

**macOS / Linux**
```bash
pip install -e .
export BEDROCK_MODEL_ID="us.anthropic.claude-opus-5-5"  # Optionnel
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

**Windows (PowerShell)**
```powershell
pip install -e .
$env:BEDROCK_MODEL_ID = "us.anthropic.claude-opus-5-5"  # Optionnel
py -3.12 -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

#### Terminal 2 — l'interface

```bash
cd frontend
npm install
npm run dev
```

**Ouvrir l'application** : <http://localhost:5173>

**Notes :**
- Vite relaie automatiquement `/api` vers `http://127.0.0.1:8000`. Pour une API différente, définir `VITE_API_URL` avant `npm run dev`.
- **Mode sans AWS** : lancer l'API avec `BEDROCK_MODEL_ID=""` (PowerShell : `$env:BEDROCK_MODEL_ID = ""`). Les chiffres et les contrôles restent disponibles. L'interface indique que l'explication IA est indisponible.

### Version en ligne (déploiement AWS)

L'application est publique ici : **<https://dnljlar20i0ps.cloudfront.net>**

```text
Navigateur ──HTTPS──▶ CloudFront (dnljlar20i0ps.cloudfront.net)
                        ├── /*      → S3 alphaforge-frontend-014498642951 (build React, accès privé via OAC)
                        └── /api/*  → ECS Express « alphaforge-api » (FastAPI + Bedrock, rôle IAM alphaforge-ecs-task-role)
```

- Le frontend et l'API partagent le même domaine. Le frontend est donc construit **sans** `VITE_API_URL` et appelle `/api` en relatif. Il n'y a pas de CORS à configurer.
- L'API utilise le rôle IAM de la tâche ECS. Aucune clé AWS ne se trouve dans le navigateur, le dépôt ou l'image.
- Limite : CloudFront coupe les requêtes au bout de **60 s**. Une comparaison complète de trois scénarios peut dépasser ce délai. Une analyse simple prend environ 35 s.

Republier le frontend après une modification :

```bash
cd frontend
npm ci && npm run build
aws s3 sync dist s3://alphaforge-frontend-014498642951 --delete
aws cloudfront create-invalidation --distribution-id E1GDMWAK8WJOMS --paths "/*"
```

Republier l'API : pousser une nouvelle image dans ECR (`alphaforge-api`), puis mettre à jour le service ECS Express `alphaforge-api` (cluster `default`, `us-east-1`). Pour les étapes détaillées, voir [docs/deployment_aws.md](docs/deployment_aws.md).

### Ce qu'on trouve dans l'application

| Page | À quoi elle sert |
|---|---|
| **Vue d'ensemble** | Présente le projet et la question posée |
| **Profils fictifs** | Les cartes d'Amira, Mateo, Robert et Alex : objectif, horizon, préférences et portefeuille de départ, avec un drapeau rouge si le profil se contredit |
| **Simuler un ajout** | Choisir l'actif et le poids, lancer l'analyse, voir les cartes avant/après, le graphique et les pondérations |
| **Cohérence** | Les contrôles du profil (cohérent, tension ou information manquante) et leurs preuves, avec les contradictions du profil mises en évidence en rouge. Disponible après une analyse. |
| **Mes scénarios** | Les scénarios enregistrés sur cet appareil |
| **Sources et méthode** | D'où viennent les données et comment les chiffres sont calculés |

**Fonctionnalités IA :**

- **Chat IA contextuel** : permet de poser des questions en langage naturel sur l'analyse affichée et d'obtenir des explications adaptées au scénario en cours.
- **Contre-analyse** : permet de confronter les conclusions de l'analyse aux données, aux preuves et aux informations du dossier afin de faire ressortir les contradictions, les limites et les éventuelles incohérences.

**Bon à savoir :**

- Rien ne se calcule tout seul : une analyse démarre seulement quand on clique.
- Si on change le scénario pendant un calcul, l'ancienne réponse est ignorée.
- Les scénarios enregistrés restent dans le navigateur (`localStorage`). On garde les paramètres, pas les résultats.
- L'API garde les réponses en mémoire pendant une heure (100 au maximum) pour les questions de suivi. Tout est perdu au redémarrage : c'est fait pour une démo locale.
- Les questions de l'assistant sont indépendantes et liées à une analyse précise ; aucun historique de chat n'est transmis.

### Vérifier l'interface

```bash
cd frontend
npm test            # tests
npm run typecheck   # vérification des types
npm run lint        # style du code
npm run build       # version de production
```

---

## Limites

- **Historique, pas prévision** : les rendements passés ne préjugent pas des rendements futurs.
- **Biais du survivant** : l'univers de 31 actifs a été choisi en 2026 parmi des titres importants aujourd'hui.
- **Frais, taxes et coûts de transaction** ne sont pas modélisés.
- **√252 est une convention approximative** : l'alignement des calendriers rend les intervalles entre observations irréguliers.
- **La baisse maximale** est mesurée sur les dates retenues et peut omettre une baisse survenue entre deux observations.
- **Composition des FNB inconnue** : l'exposition indirecte (par exemple à NVDA via QQQ) n'est pas mesurée.
- **Aucune cote ESG** dans le jeu de départ : les constats ESG reposent sur des preuves datées et documentées.
- **Informations inconnues** : la capacité à absorber une perte, les besoins de liquidités et les retraits prévus restent inconnus pour tous les personas. Rien n'est déduit de la profession, de l'âge ou de la situation familiale.
- **Limites de l'IA** : les explications et contre-analyses dépendent des données et des preuves disponibles. Une contradiction détectée ou une conclusion nuancée ne constitue pas une validation financière indépendante.

---

## Structure du projet

```text
DATATHON-POLYFINANCES/
├── alphaforge/
│   ├── engine.py            Moteur de simulation
│   ├── profile_checks.py    Contrôles du profil et ESG
│   └── contradiction_checks.py  Drapeau rouge : contradictions du profil
├── api/                     API FastAPI
├── frontend/                Interface React / TypeScript
├── agent/                   Service d'orchestration et AWS Bedrock
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
