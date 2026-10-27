# KnowForge RAG Platform Deploy Package

This is the deployable V1 source bundle.

It excludes the real model weights. Before running Docker deployment, place these local model directories under `models/`:

- `models/bge-m3`
- `models/bge-reranker-large`
- `models/bert_intent_classifier_v1`

## One-shot deployment

```powershell
if (!(Test-Path .env.compose)) { Copy-Item .env.compose.example .env.compose }
notepad .env.compose
powershell -ExecutionPolicy Bypass -File .\scripts\deploy\deploy_docker.ps1
```

## Manual deployment

```powershell
if (!(Test-Path .env.compose)) { Copy-Item .env.compose.example .env.compose }
notepad .env.compose

docker compose --env-file .env.compose up -d mysql redis etcd minio milvus

# First deploy or base image missing
# docker build -f Dockerfile.base -t localhost/knowforge-rag-platform-base:py312 .
docker compose --env-file .env.compose build api

docker compose --env-file .env.compose run --rm api python scripts/rebuild_scenarios.py --reset-collections --description "fresh docker init all scenarios"
docker compose --env-file .env.compose up -d api
docker compose --env-file .env.compose ps
```

## Fresh-machine verification

```powershell
python .\scripts\deployerify_fresh_docker_deploy.py --keep-going
```
