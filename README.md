# DATATHON-POLYFINANCES

## Comparaison historique des portefeuilles

Le moteur Python applique un scénario, convertit les prix ajustés en CAD et
compare un portefeuille acheter-et-conserver avant et après la modification.
Il utilise uniquement la bibliothèque standard Python.

Sous Windows, lancer les tests avec :

```powershell
py -3 -m unittest discover -s tests -v
```

Produire la comparaison d'Amira :

```powershell
py -3 run_comparison.py --persona amira --output results/amira_comparison.json
```

Conventions principales :

- `adj_close` est utilisé pour refléter les distributions et fractionnements;
- les prix USD sont multipliés par USD/CAD, exprimé en CAD pour 1 USD;
- un taux de change manquant est remplacé par le dernier taux antérieur connu;
- les prix des actifs ne sont jamais reportés;
- seules les dates communes à tous les actifs avant et après sont conservées;
- les quantités sont fixes après l'investissement initial, sans rééquilibrage;
- la volatilité utilise les rendements entre observations communes et un
  facteur d'annualisation de 252.

Le résultat est une comparaison historique hypothétique, pas une prévision ni
une recommandation. Les données de prix seules ne permettent pas de mesurer
l'exposition technologique détenue indirectement par SPY ou QQQ.

## Structure du projet

```text
DATATHON/
├── alphaforge/
│   ├── __init__.py
│   └── engine.py
├── data/
│   ├── market/
│   │   ├── assets_universe.csv
│   │   ├── prices_daily.csv
│   │   ├── fx_usdcad_daily.csv
│   │   └── sources_metadata.csv
│   ├── personas.json
│   ├── portfolios.json
│   ├── scenarios.json
│   └── validation_report.json
├── results/
│   └── amira_comparison.json
├── tests/
│   └── test_portfolio_engine.py
├── pyproject.toml
└── run_comparison.py
```

Le dossier `data/market/` conserve aussi les autres fichiers du jeu de départ
(`corporate_actions.csv`, `macro_rates.csv`, son README et son script de
construction) afin que la provenance du jeu demeure reproductible.
