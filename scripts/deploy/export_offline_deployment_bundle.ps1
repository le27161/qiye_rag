<#
.SYNOPSIS
    生成 KnowForge 可离线部署的交付目录。

.DESCRIPTION
    交付目录包含项目源码、讲义、场景数据、部署脚本和全部 Docker 运行镜像。
    默认不复制 models/ 下的模型权重，避免每次导出额外增加约 4.6 GiB；需要真正
    完全离线的交付时，传入 -IncludeModels 将三套运行模型一并复制。

.EXAMPLE
    .\scripts\deploy\export_offline_deployment_bundle.ps1

.EXAMPLE
    .\scripts\deploy\export_offline_deployment_bundle.ps1 -IncludeModels
#>

param(
    [string]$BundlePath = "exports\knowforge-rag-platform-v1.0.4-offline",
    [switch]$IncludeModels
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $RepoRoot

if ([System.IO.Path]::IsPathRooted($BundlePath)) {
    $bundleRoot = $BundlePath
}
else {
    $bundleRoot = Join-Path $RepoRoot $BundlePath
}

if (Test-Path -LiteralPath $bundleRoot) {
    throw "Bundle path already exists: $bundleRoot. Use a new output path to avoid overwriting an existing delivery."
}

New-Item -ItemType Directory -Force -Path $bundleRoot | Out-Null

$files = @(
    "app.py",
    "docker-compose.yml",
    "Dockerfile",
    "Dockerfile.base",
    "requirements.txt",
    ".env.compose.example",
    ".env.local.example",
    ".dockerignore",
    ".gitignore",
    "README.md",
    "VERSIONING.md",
    "mkdocs.yml",
    "pytest.ini"
)

$directories = @(
    "qa_core",
    "static",
    "scripts",
    "scenarios",
    "docs",
    "site",
    "eval_sets",
    "data_packs",
    "resume_templates",
    "tests"
)

foreach ($file in $files) {
    Copy-Item -LiteralPath (Join-Path $RepoRoot $file) -Destination (Join-Path $bundleRoot $file) -Force
}
foreach ($directory in $directories) {
    Copy-Item -LiteralPath (Join-Path $RepoRoot $directory) -Destination (Join-Path $bundleRoot $directory) -Recurse -Force
}

$modelsTarget = Join-Path $bundleRoot "models"
New-Item -ItemType Directory -Force -Path $modelsTarget | Out-Null
if ($IncludeModels) {
    foreach ($modelDirectory in @("bge-m3", "bge-reranker-large", "bert_intent_classifier_v1")) {
        $source = Join-Path $RepoRoot "models\$modelDirectory"
        if (-not (Test-Path -LiteralPath $source -PathType Container)) {
            throw "Required model directory is missing: $source"
        }
        Copy-Item -LiteralPath $source -Destination (Join-Path $modelsTarget $modelDirectory) -Recurse -Force
    }
}
else {
    @(
        "部署前请将以下运行模型目录放入此处：",
        "- bge-m3",
        "- bge-reranker-large",
        "- bert_intent_classifier_v1",
        "",
        "如需在导出时一并包含模型，请使用 -IncludeModels 参数重新导出。"
    ) | Set-Content -LiteralPath (Join-Path $modelsTarget "README.md") -Encoding utf8
}

$offlineDirectory = Join-Path $bundleRoot "offline"
New-Item -ItemType Directory -Force -Path $offlineDirectory | Out-Null
$imagesArchive = Join-Path $offlineDirectory "knowforge-rag-platform-v1.0.4-docker-images.tar"

& (Join-Path $PSScriptRoot "export_offline_docker_images.ps1") -OutputPath $imagesArchive
if ($LASTEXITCODE -ne 0) {
    throw "Docker image export failed."
}

$installGuide = @'
# KnowForge RAG Platform 离线部署

本目录已包含 KnowForge 运行所需的全部 Docker 镜像。目标机器导入镜像后，不需要
执行 `docker pull`、构建 API 镜像，也不需要下载 Python 依赖包。

## 前置条件

- 已安装 Docker Desktop，或 Docker Engine + Docker Compose V2。
- 导入镜像并创建服务数据卷后，磁盘至少保留 16 GiB 可用空间。
- 确认 `models/bge-m3`、`models/bge-reranker-large`、
  `models/bert_intent_classifier_v1` 三个目录存在。只有使用 `-IncludeModels`
  导出的包才会自动包含它们。

## 首次离线部署

```powershell
if (!(Test-Path .env.compose)) { Copy-Item .env.compose.example .env.compose }
notepad .env.compose
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\deploy\deploy_offline_docker.ps1
```

首次部署会为全部 8 个业务场景初始化 active 知识库版本。只初始化配置中的 active
场景时，执行：

```powershell
.\scripts\deploy\deploy_offline_docker.ps1 -ActiveScenarioOnly
```

首次部署完成后的重启不需要重新导入、构建或入库：

```powershell
.\scripts\deploy\deploy_offline_docker.ps1 -SkipInit
```

部署完成后访问 `http://127.0.0.1:8000/`。

说明：本包解决 Docker 镜像和 Python 依赖的离线交付。在线问答默认调用 DashScope，
因此问答阶段仍需要可访问配置的 LLM 服务；如使用本地 LLM，则由本地 LLM 服务负责该能力。
'@
$installGuide | Set-Content -LiteralPath (Join-Path $bundleRoot "INSTALL-OFFLINE.md") -Encoding utf8

$sizeGiB = [math]::Round((Get-ChildItem -LiteralPath $bundleRoot -File -Recurse | Measure-Object -Property Length -Sum).Sum / 1GB, 2)
Write-Host "Offline deployment bundle created: $bundleRoot ($sizeGiB GiB)"
