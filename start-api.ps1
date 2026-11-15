$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$credentialsPath = Join-Path $env:USERPROFILE ".aws\credentials"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    Write-Error "L'environnement .venv est introuvable. Créez-le avant de lancer l'API."
}

if (-not (Test-Path -LiteralPath $credentialsPath)) {
    $credentialsDirectory = Split-Path -Parent $credentialsPath
    New-Item -ItemType Directory -Path $credentialsDirectory -Force | Out-Null
    @"
[default]
aws_access_key_id=REMPLACE_MOI
aws_secret_access_key=REMPLACE_MOI
aws_session_token=REMPLACE_MOI
"@ | Set-Content -LiteralPath $credentialsPath -Encoding ASCII

    Write-Host "Le fichier AWS vient d'être créé." -ForegroundColor Yellow
    Write-Host "Remplace les trois valeurs REMPLACE_MOI dans le Bloc-notes, puis enregistre et ferme-le." -ForegroundColor Yellow
    Start-Process -FilePath "notepad.exe" -ArgumentList $credentialsPath -Wait
}

$env:AWS_PROFILE = "default"
$env:AWS_DEFAULT_REGION = "us-east-1"

Write-Host "Vérification du profil AWS enregistré..." -ForegroundColor Cyan
& $pythonPath (Join-Path $projectRoot "scripts\check_aws_auth.py")
if ($LASTEXITCODE -ne 0) {
    Write-Error "Le profil AWS est absent, invalide ou expiré. Mettez à jour $credentialsPath."
}

Write-Host "Démarrage de l'API AlphaForge sur http://127.0.0.1:8000" -ForegroundColor Green
Set-Location -LiteralPath $projectRoot
& $pythonPath -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
