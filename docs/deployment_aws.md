# Déploiement AWS sans clé statique

Le frontend ne doit recevoir aucune clé AWS. Le backend FastAPI s'exécute sur
AWS App Runner avec un rôle IAM d'instance. Boto3 obtient et renouvelle
automatiquement les identifiants temporaires de ce rôle.

## 1. Construire et publier l'image API

Créer une fois un dépôt ECR, puis se connecter à ECR avec AWS CLI. Remplacer les
valeurs entre chevrons :

```powershell
aws ecr create-repository --repository-name alphaforge-api --region us-east-1
$account = aws sts get-caller-identity --query Account --output text
$repository = "$account.dkr.ecr.us-east-1.amazonaws.com/alphaforge-api"
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin "$account.dkr.ecr.us-east-1.amazonaws.com"
docker build -f Dockerfile.api -t alphaforge-api .
docker tag alphaforge-api:latest "${repository}:latest"
docker push "${repository}:latest"
```

## 2. Créer App Runner et le rôle IAM

Le template crée deux rôles distincts : un rôle de lecture ECR pour App Runner et
un rôle d'exécution autorisé à appeler Bedrock. Il n'enregistre aucune clé.

```powershell
aws cloudformation deploy `
  --template-file infra/apprunner.yaml `
  --stack-name alphaforge-api `
  --capabilities CAPABILITY_IAM `
  --region us-east-1 `
  --parameter-overrides `
    ImageRepositoryUri=$repository `
    ImageTag=latest `
    FrontendOrigin=https://<frontend.example> `
    BedrockModelId=<modele-ou-profil-bedrock> `
    BedrockResourceArn="*"
```

Après validation, remplacer `BedrockResourceArn="*"` par l'ARN exact du modèle
ou du profil d'inférence afin d'appliquer le moindre privilège.

Récupérer l'URL :

```powershell
aws cloudformation describe-stacks --stack-name alphaforge-api --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text
```

## 3. Construire le frontend

Configurer l'URL retournée avant la construction :

```powershell
$env:VITE_API_URL="https://<url-app-runner>"
cd frontend
npm ci
npm run build
```

Publier ensuite `frontend/dist` sur l'hébergeur statique choisi. La valeur exacte
de son origine HTTPS doit correspondre au paramètre `FrontendOrigin`.

## Local contre production

- Local : `%USERPROFILE%\.aws\credentials` et `start-api.ps1`.
- Production : rôle IAM App Runner, rotation automatique, aucune clé statique.
- Jamais : clé dans React, dans Git, dans le Dockerfile ou dans CloudFormation.
