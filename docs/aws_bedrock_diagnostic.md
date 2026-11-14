# Diagnostic AWS Bedrock

Ces scripts utilisent uniquement la région `us-east-1`. Ils ne lisent jamais
les valeurs des identifiants temporaires pour les afficher ou les écrire.

- Région : `us-east-1`
- Profil testé avec succès : `us.anthropic.claude-opus-5-5`
- Ne pas envoyer le paramètre `temperature` pour ce modèle.

Pour le futur agent, définir l'identifiant du modèle comme configuration non
secrète dans le PowerShell courant :

```powershell
$env:BEDROCK_MODEL_ID = "us.anthropic.claude-opus-5-5"
```

Le script de diagnostic conserve volontairement l'identifiant comme argument.

Depuis un PowerShell où les trois variables Workshop Studio sont déjà définies,
à la racine du projet :

```powershell
.\.venv\Scripts\python.exe .\scripts\check_aws_auth.py
.\.venv\Scripts\python.exe .\scripts\list_bedrock_profiles.py
```

Copier ensuite uniquement l'identifiant exact affiché pour le profil voulu :

```powershell
.\.venv\Scripts\python.exe .\scripts\test_bedrock_converse.py "IDENTIFIANT_EXACT_DU_PROFIL"
```

Ne pas placer les commandes Workshop Studio contenant les secrets dans un
script, un fichier `.env`, l'historique Git ou une capture d'écran. Les
identifiants temporaires doivent être renouvelés dans Workshop Studio après
leur expiration.
