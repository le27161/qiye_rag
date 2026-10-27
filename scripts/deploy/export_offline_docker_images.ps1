<#
.SYNOPSIS
    导出 KnowForge Docker 离线镜像包。

.DESCRIPTION
    生成一个可由 `docker image load` 导入的 tar 文件，包含 MySQL、Redis、
    etcd、MinIO、Milvus 和 KnowForge API 镜像。目标机器导入后，无需拉取镜像、
    构建基础镜像或安装 Python 依赖。

.EXAMPLE
    .\scripts\deploy\export_offline_docker_images.ps1
#>

param(
    [string]$OutputPath = "exports\knowforge-rag-platform-v1.0.4-docker-images.tar"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $RepoRoot

$apiImage = "localhost/knowforge-rag-platform-api:v1.0.4"
$legacyApiImage = "knowforge-rag-platform-api:latest"

# Compose 使用固定标签；若本机仍是旧标签，则只补一个本地标签，不重新构建镜像。
& docker image inspect $apiImage *> $null
if ($LASTEXITCODE -ne 0) {
    & docker image inspect $legacyApiImage *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "API image not found. Run .\scripts\deploy\deploy_docker.ps1 once before exporting the offline package."
    }
    & docker tag $legacyApiImage $apiImage
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to tag $legacyApiImage as $apiImage."
    }
}

$images = @(
    "mysql:8.4",
    "redis:7-alpine",
    "quay.io/coreos/etcd:v3.5.18",
    "minio/minio:RELEASE.2025-04-22T22-12-26Z",
    "milvusdb/milvus:v2.5.15",
    $apiImage
)

foreach ($image in $images) {
    & docker image inspect $image *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Required Docker image is missing: $image"
    }
}

if ([System.IO.Path]::IsPathRooted($OutputPath)) {
    $archivePath = $OutputPath
}
else {
    $archivePath = Join-Path $RepoRoot $OutputPath
}

$archiveDirectory = Split-Path -Parent $archivePath
New-Item -ItemType Directory -Force -Path $archiveDirectory | Out-Null

if (Test-Path -LiteralPath $archivePath) {
    Remove-Item -LiteralPath $archivePath -Force
}

Write-Host "Exporting Docker images to $archivePath ..."
& docker image save --output $archivePath @images
if ($LASTEXITCODE -ne 0) {
    throw "docker image save failed."
}

$hash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
$hashPath = "$archivePath.sha256"
"$hash  $([System.IO.Path]::GetFileName($archivePath))" | Set-Content -LiteralPath $hashPath -Encoding ascii

$sizeGiB = [math]::Round((Get-Item -LiteralPath $archivePath).Length / 1GB, 2)
Write-Host "Offline image archive created: $archivePath ($sizeGiB GiB)"
Write-Host "SHA256 file created: $hashPath"
