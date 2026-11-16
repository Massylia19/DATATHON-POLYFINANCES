# AlphaForge AI — Datathon PolyFinances 2026

> **Si je consacre X % de mon portefeuille à cet actif, qu'est-ce qui change et quels compromis dois-je comprendre compte tenu de mon profil ?**

AlphaForge AI est une application pédagogique de simulation. Elle compare un portefeuille fictif **avant** et **après** l'ajout d'un actif, sur des données historiques réelles, puis examine la cohérence du changement avec le profil et explique les compromis.

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
Interface React / TypeScript (frontend/)
   │  profil, actif, poids
   ▼
API FastAPI (api/)
   │                     ├─► moteur de simulation            (alphaforge/engine.py)
   │                     ├─► contrôles du profil              (alphaforge/profile_checks.py)
   │                     └─► explication et contre-analyse IA (Bedrock)
   ▼
Résultat structuré : métriques, contrôles, preuves et limites
```

Le **code calcule**, le **modèle explique et confronte les conclusions aux preuves**. Aucun chiffre n'est produit par le modèle de langage.

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
| `--persona` | `amira`, `mateo` ou `robert` (défaut : `amira`) |
| `--symbol`, `--weight` | Actif à ajouter et poids cible en
