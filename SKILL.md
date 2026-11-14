---
name: alphaforge-project-contract
description: Appliquer les conventions communes du projet AlphaForge AI au Datathon PolyFinances 2026 lors du développement du moteur, de l’agent AWS, de l’interface et des contrôles des profils.
---

# AlphaForge AI — Contrat commun du projet

## 1. Objectif et périmètre

Construire un assistant de simulation répondant à cette question :

> Si je consacre X % de mon portefeuille à cet actif, qu’est-ce qui change et quels compromis dois-je comprendre compte tenu de mon profil ?

Prendre en charge Amira, Mateo et Robert dans un parcours commun. Utiliser les profils et portefeuilles fictifs documentés dans `data/`. Les portefeuilles et leurs pondérations sont des hypothèses de démonstration, pas des prescriptions du cas officiel.

Analyser un ajout à la fois. Ne pas ajouter de prédiction des cours, de transactions réelles ou d’optimisation automatique sans décision explicite de l’équipe. La solution reste une simulation et ne se présente pas comme un conseil financier personnalisé.

AWS doit contribuer réellement et de manière démontrable au fonctionnement de la solution. Les formats ci-dessous constituent le contrat proposé de l’équipe, pas des exigences officielles supplémentaires du concours.

## 2. Responsabilités

| Rôle | Responsabilité | Périmètre principal | Branche proposée |
|---|---|---|---|
| Personne 1 | Données et moteur de simulation | `alphaforge/engine.py`, `run_comparison.py`, tests du moteur | `feature/portfolio-engine` |
| Personne 2 | Agent et AWS | `agent/service.py`, `agent/tools.py`, `agent/prompts.py` | `feature/aws-agent` |
| Personne 3 | Interface et raccordement | `app/`, `api/` si HTTP nécessaire | `feature/interface` |
| Personne 4 | Contrôles des profils et preuves ESG | `alphaforge/profile_checks.py`, preuves ESG et tests associés | `feature/profile-checks` |

Ne pas attribuer ces rôles à des personnes nommées sans décision de l’équipe. Chaque rôle intervient sur les trois personas. Convenir du contrat avant de travailler séparément et annoncer toute modification à l’équipe.

## 3. Entrée commune

```json
{
  "persona_id": "amira",
  "symbol": "NVDA",
  "target_weight_pct": 10
}
```

- `persona_id` : `amira`, `mateo` ou `robert`.
- `symbol` : ticker exact disponible dans `assets_universe.csv`.
- `target_weight_pct` : nombre fini strictement compris entre 0 et 100. `10` signifie 10 %.
- Pour la première version, l’actif ajouté doit être absent du portefeuille initial.
- Refuser les poids non numériques, NaN, infinis, négatifs ou incohérents.
- Vérifier l’unicité des positions et un total initial de 100 % avec une tolérance numérique explicite.

## 4. Conventions financières et temporelles

| Sujet | Convention |
|---|---|
| Financement | Pour un poids cible p, multiplier les poids existants par `(1 - p / 100)` puis ajouter p % au nouvel actif |
| Devise | CAD pour toutes les comparaisons |
| Prix | `adj_close`; ne pas ajouter une seconde fois les dividendes déjà reflétés dans cette série |
| Conversion USD | Multiplier par USD/CAD, exprimé en CAD pour 1 USD |
| Change manquant | Dernier taux connu antérieur ou du jour; aucun taux futur; erreur si aucun taux antérieur disponible |
| Calendrier | Intersection stricte des dates de tous les actifs avant et après, commune aux deux simulations |
| Prix manquant | Aucun report de prix; les dates non communes sont exclues |
| Simulation | Pondérations initiales puis conservation, sans rééquilibrage périodique |
| Courbes | Base 100 au début de la période commune |
| Période | Historique commun disponible; afficher les dates réelles et le nombre d’observations |
| Volatilité | Écart-type échantillonnal des rendements simples entre observations communes, multiplié par √252 |

Le poids cible s’applique au début de la simulation historique. Les poids dérivent ensuite avec les performances. Les quantités utilisées sur prix ajustés sont des unités synthétiques permettant de représenter les distributions selon la méthode du fournisseur, pas nécessairement un nombre d’actions réel.

L’intersection retire notamment les fins de semaine crypto et certains jours fériés. Les intervalles entre observations peuvent être irréguliers : documenter que √252 est une convention approximative. La baisse maximale est mesurée sur les observations retenues et peut omettre des baisses entre ces dates.

Comparer les deux portefeuilles sur exactement les mêmes dates. Ne pas interpréter les résultats historiques comme des rendements futurs. Signaler le biais de sélection/survivance de l’univers et toute hypothèse sur les frais, taxes et coûts de transaction. Pour cette première version, les exclure explicitement de la simulation.

## 5. Unités et affichage

| Donnée | Valeur échangée | Affichage |
|---|---|---|
| Pondération | `10` | 10 % |
| Rendement total | `0.12` | 12 % |
| Volatilité annualisée | `0.20` | 20 % |
| Baisse maximale | `-0.15` | −15 % |
| Écart de volatilité | `0.03` | +3 points de pourcentage |
| Date | `2026-11-12` | Format d’affichage choisi par l’interface |
| Valeur normalisée | `100` | Base 100 |

Tous les écarts valent **après moins avant**. Une variation de baisse maximale de -0.15 à -0.10 vaut +0.05, soit une baisse historique moins profonde de 5 points; ne pas confondre le signe avec une aggravation.

Conserver la précision dans les calculs. Arrondir seulement pour l’affichage. Ne jamais remplacer un résultat manquant par zéro : utiliser `null` et une explication. Ne jamais sérialiser NaN ou Infinity.

## 6. Contrat de sortie du moteur — personne 1

Conserver les clés existantes et les compléter sans rupture silencieuse :

```text
analysis_type                    hypothetical_historical_comparison
persona                          Profil complet, horizon et informations manquantes
scenario                         Scénario, added_symbol et target_weight_pct
period                           start, end, common_observations
currency                         CAD
before                           weights_by_asset_pct, weights_by_class_pct, metrics
after                            weights_by_asset_pct, weights_by_class_pct, metrics
delta_after_minus_before         metrics, weights_by_asset_pct
series                           dates, before, after
methodology                      Méthodes et conventions
sources                          Sources identifiées
limitations                      Limites de l’analyse
```

Les objets `metrics` utilisent exactement :

```json
{
  "total_return": 0.12,
  "annualized_volatility": 0.20,
  "max_drawdown": -0.15
}
```

Ces nombres sont des exemples de format, pas des résultats calculés.

`series` contient trois tableaux de même longueur : dates ISO, valeurs avant et valeurs après. Les deux séries commencent à 100. Les indicateurs sont calculés sur les mêmes séries et dates.

Donner à chaque source un `id` stable et renseigner fichier ou URL, origine, date de consultation/extraction et limites pertinentes. Les preuves chiffrées peuvent référencer un chemin tel que `analysis.after.metrics.annualized_volatility`.

Les pondérations affichées dans `before` et `after` sont les allocations initiales des simulations, pas les allocations finales après dérive.

## 7. Contrat des contrôles — personne 4

Retourner une liste d’objets de cette forme :

```json
{
  "id": "indirect_technology_exposure",
  "status": "insufficient_information",
  "title": "Exposition technologique indirecte",
  "message": "La composition des FNB est nécessaire pour quantifier cette exposition.",
  "evidence_refs": [],
  "missing_information": ["etf_holdings"]
}
```

Statuts autorisés :

- `consistent` : les preuves soutiennent la cohérence sur le point examiné, sans certifier l’ensemble du portefeuille.
- `tension` : une tension documentée mérite d’être expliquée.
- `insufficient_information` : les éléments disponibles ne permettent pas de conclure.

Chaque référence pointe vers un champ de résultat observable ou une source identifiée. Documenter les seuils comme des règles de simulation choisies par l’équipe, jamais comme des normes officielles.

### Amira

Prendre en compte la croissance à long terme, un risque élevé et le souhait de diversification. Ne pas assimiler risque élevé à acceptation de tout investissement. Les prix seuls ne permettent pas de quantifier la technologie ou NVDA détenus indirectement par SPY/QQQ. Utiliser des compositions datées pour toute quantification sous-jacente.

### Mateo

Examiner les préférences ESG et les facteurs financiers. Les preuves sur ESGV ne suffisent pas à juger XOM ou les autres positions. Un secteur seul ne prouve pas une controverse. Distinguer faits sourcés, méthodologies d’exclusion, préférences et absence de preuves. Une absence de controverse trouvée ne garantit pas la compatibilité ESG.

### Robert

Examiner l’horizon de 3 à 5 ans et la préservation du capital. Ne pas préprogrammer le refus de TSLA : évaluer le poids, le portefeuille et les effets observés. Ne pas présenter les obligations ou l’or comme garantis ou sans risque.

### Informations inconnues

Conserver comme inconnues la capacité à absorber une perte, les besoins de liquidités et les retraits prévus. Ne rien déduire de la profession, de l’âge ou de la situation familiale. Ne pas transformer une préférence en interdiction absolue sans justification explicite.

## 8. Contrat de l’agent — personne 2

L’agent utilise les outils du moteur et des contrôles, puis retourne :

```text
summary                 Résumé court
changes                 Liste d’objets : message, evidence_refs
profile_assessment      Liste d’objets : check_id, status, message, evidence_refs
uncertainties           Liste de limites et informations manquantes
evidence_refs           Références des preuves utilisées
tool_trace              Liste d’appels : tool, arguments, status, result ou error
```

Le code calcule; le modèle contextualise et explique. Les traces doivent être capturées par l’application à partir des appels réels, jamais inventées par le modèle. Ne pas exposer de raisonnement interne détaillé.

Ne pas inventer de chiffres, sources, contrôles réussis ou preuves ESG. Ne pas présenter un résultat mis en cache ou une simulation locale comme un appel AWS réel. En cas d’échec du modèle, conserver les calculs disponibles et signaler clairement l’absence d’explication IA.

Ne pas coder en dur une recommandation ou un verdict par persona. Ne pas calculer de score global opaque de compatibilité.

## 9. Orchestration et interface

La personne 2 possède le service commun :

```python
analyze_request(persona_id, symbol, target_weight_pct)
```

La personne 3 possède l’interface et, si nécessaire, la route HTTP `POST /analyze`. Elle appelle le service sans dupliquer les calculs ou les contrôles. La personne 1 conserve les fonctions déterministes indépendantes de l’agent et de l’interface.

Réponse complète :

```json
{
  "status": "success",
  "analysis": {},
  "checks": [],
  "explanation": {},
  "warnings": []
}
```

Les objets vides illustrent la structure : remplir les champs suivant les contrats précédents. `warnings` est une liste de messages lisibles.

Si les calculs réussissent mais que l’explication AWS échoue : utiliser `status: "partial"`, conserver `analysis` et les contrôles disponibles, mettre `explanation: null` et expliquer l’échec dans `warnings`. Ne pas assimiler une réponse partielle à une intégration AWS réussie.

Échec bloquant :

```json
{
  "status": "error",
  "error": {
    "code": "UNKNOWN_SYMBOL",
    "message": "Cet actif est absent du jeu de données."
  }
}
```

Codes communs : `INVALID_PERSONA`, `UNKNOWN_SYMBOL`, `INVALID_WEIGHT`, `ASSET_ALREADY_HELD`, `INSUFFICIENT_DATA`, `AWS_UNAVAILABLE`, `INTERNAL_ERROR`.

Si HTTP utilisé : 200 pour une réponse complète ou partielle, 400 pour une entrée invalide, 422 pour des données insuffisantes, 503 si AWS est indispensable et indisponible sans résultat exploitable, 500 pour une erreur interne inattendue. Ne pas retourner de secrets, de traces système sensibles ou d’identifiants AWS.

L’interface affiche : profil, portefeuille fictif, formulaire d’ajout, pondérations avant/après, indicateurs, courbes base 100, contrôles, explication, sources et limites. Prévoir chargement, erreur et résultat partiel. Aucun framework particulier n’est imposé par ce contrat.

## 10. Collaboration et vérification

1. Partir du `main` fusionné et à jour, puis créer sa branche.
2. Créer ensemble un exemple JSON complet à partir du résultat Amira existant; les données de démonstration doivent être étiquetées.
3. Personne 1 stabilise le résultat du moteur; personne 3 peut développer sur l’exemple pendant ce temps.
4. Personne 4 raccorde ses contrôles au profil et aux résultats.
5. Personne 2 expose et appelle les outils; personne 3 raccorde le service.
6. Intégrer de petites pull requests et annoncer toute modification de schéma.
7. Réussir un parcours complet, puis vérifier les trois personas.

Contrôles minimum avant la démonstration :

- Total de 100 % avant et après; entrée invalide rejetée.
- Conversion USD/CAD et absence d’usage de taux futurs vérifiées.
- Dates identiques et courbes base 100 cohérentes.
- Calculs vérifiés sur un exemple simple indépendant.
- Aucun verdict financier ou ESG préprogrammé.
- Traçabilité des chiffres et des contrôles jusqu’aux preuves.
- Appels AWS réels vérifiables et erreurs gérées.
- Aucun secret dans le dépôt ou les réponses.

Ne pas écraser les fichiers d’une autre personne. Ne pas committer, pousser ou fusionner automatiquement sans instruction autorisant cette action. Ce fichier documente le contrat; il ne prouve pas que les fonctionnalités sont déjà implémentées.

## 11. Livrables

| Responsable | Livrable principal |
|---|---|
| Personne 1 | README, installation, reproduction et méthodes de calcul |
| Personne 2 | Documentation de l’architecture, de l’agent et d’AWS |
| Personne 3 | Vidéo de démonstration et parcours utilisateur |
| Personne 4 | Résumé d’une page, validation et coordination du pitch |

Chaque personne documente son composant. Réserver les deux dernières heures aux tests intégrés et aux livrables. Vérifier les modalités et l’heure officielle de remise. Sauvegarder code, données autorisées et notes avant l’expiration du compte AWS temporaire.
