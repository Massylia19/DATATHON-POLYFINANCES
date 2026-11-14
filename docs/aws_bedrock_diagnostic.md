# Diagnostic AWS Bedrock

Ces scripts utilisent uniquement la région `us-east-1`. Ils ne lisent jamais
les valeurs des identifiants temporaires pour les afficher ou les écrire.

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
