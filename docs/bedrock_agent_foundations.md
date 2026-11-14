# Agent Bedrock : fondations et service Converse

Le module `agent` relie une demande validée au moteur local, aux contrôles de
profil et à Bedrock Converse. Il ne contient aucune clé AWS. La région est
`us-east-1` et le modèle est lu dans `BEDROCK_MODEL_ID`. Aucun paramètre
`temperature` n'est envoyé.

## Créer un contexte isolé et appeler les outils

```python
from agent import create_request_context, dispatch_tool

context = create_request_context("amira", "NVDA", 10)
arguments = {
    "persona_id": "amira",
    "symbol": "NVDA",
    "target_weight_pct": 10,
}
simulation = dispatch_tool(context, "simulate_portfolio_change", arguments)
checks = dispatch_tool(context, "check_profile", arguments)
```

Le contexte valide et fige la demande initiale. Il contient le profil chargé
par l'application, puis conserve l'analyse, les contrôles et les traces réelles
de cette demande seulement. Il ne repose sur aucun état global mutable.

`simulate_portfolio_change` appelle `run_analysis`. `check_profile` utilise
uniquement le profil et l'analyse conservés dans le contexte : le modèle ne
peut pas lui fournir ses propres métriques. Les schémas Converse sont exposés
dans `agent.TOOL_SPECS`.

## Appeler le service

```python
from agent import analyze_request

response = analyze_request("amira", "NVDA", 10)
```

Les trois arguments usuels restent positionnels. Pour les tests, le service
accepte aussi des paramètres nommés : `client` pour injecter un client Converse,
`root` pour choisir le répertoire du projet et des données, et `model_id` pour
injecter une configuration non secrète.

Le service valide la demande avant tout accès AWS, puis limite le parcours à
8 appels Converse et 12 exécutions d'outils. Il conserve les messages
assistant, associe chaque `toolResult` à son `toolUseId`, traite plusieurs
appels d'outils et transmet au modèle un payload condensé sans les longues
séries. Une seule tentative de réparation JSON est autorisée.

Le retour respecte le contrat commun : `status`, `analysis`, `checks`,
`explanation` et `warnings`. Une réussite contient l'explication validée et la
trace factuelle ajoutée par l'application. Une panne AWS ou une explication
invalide produit un résultat `partial` si les calculs locaux restent
exploitables. Une erreur du moteur produit un état bloquant.

## Preuves et validation

`build_interface_payload(context)` conserve le résultat complet, y compris les
séries. `build_evidence_bundle(context)` prépare les métriques, contrôles,
sources et références nécessaires au modèle, en remplaçant les longues séries
par un résumé et une référence au contexte.

Une référence inconnue reste marquée `missing`; aucune source n'est fabriquée.
Les preuves ESG intégrées au dépôt sont reprises sans prétendre qu'elles ont été
revérifiées sur Internet.

Le service vérifie la structure JSON, les identifiants et statuts des contrôles,
ainsi que l'existence des références. Il rejette une `tool_trace` rédigée par le
modèle et ajoute celle du code. Cette validation ne prouve toutefois pas chaque
formulation de la prose ni chaque chiffre qu'elle pourrait citer. Les nombres
structurés du moteur restent la source de vérité pour l'interface.

## Démonstration réelle

Dans un PowerShell qui contient déjà les trois variables AWS temporaires :

```powershell
Set-Location "C:\Users\Selmah\Documents\uni\DATATHON\.worktrees\feature-bedrock-agent"
$env:BEDROCK_MODEL_ID = "us.anthropic.claude-opus-5-5"
.\.venv-agent\Scripts\python.exe -m agent.demo --persona amira --symbol NVDA --weight 10
```

Sur cette machine, le lanceur du venv créé par la distribution Microsoft Store
peut encore afficher `Unable to create process`. Le contournement vérifié garde
les paquets de `.venv-agent` et utilise directement le même Python 3.12.10 :

```powershell
$python312 = "C:\Program Files\WindowsApps\PythonSoftwareFoundation.Python.3.12_3.12.2800.0_x64__qbz5n2kfra8p0\python3.12.exe"
& $python312 -c "import runpy,site,sys; site.addsitedir(r'.venv-agent\Lib\site-packages'); sys.argv=['agent.demo','--persona','amira','--symbol','NVDA','--weight','10']; runpy.run_module('agent.demo',run_name='__main__')"
```

Le code de sortie est `0` pour une réussite complète, `2` pour un résultat
partiel et `1` pour une erreur bloquante. La commande affiche les métriques, la
période, les contrôles, l'explication ou les avertissements, et les traces
factuelles.

Le raccordement Streamlit, une route HTTP et la validation sémantique avancée
de la prose restent hors de cette étape.
