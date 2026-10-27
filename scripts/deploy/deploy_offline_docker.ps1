<#
.SYNOPSIS
    从离线镜像包部署 KnowForge。

.DESCRIPTION
    先校验并导入 Docker 镜像，再复用 deploy_docker.ps1 的健康检查和知识库初始化
    流程。由于以 -NoBuild 运行，不会拉取镜像、构建镜像或安装 Python 依赖。

.EXAMPLE
    .\scripts\deploy\deploy_offline_docker.ps1
#>

param(
    [string]$EnvFile = ".env.compose",
    [string]$ImagesArchive = "offline\knowforge-rag-platform-v1.0.4-docker-images.tar",
    [switch]$ActiveScenarioOnly,
    [switch]$SkipInit,
    [int]$HealthTimeoutSeconds = 420
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $RepoRoot

if ([System.IO.Path]::IsPathRooted($ImagesArchive)) {
    $archivePath = $ImagesArchive
}
else {
    $archivePath = Join-Path $RepoRoot $ImagesArchive
}

if (-not (Test-Path -LiteralPath $archivePath -PathType Leaf)) {
    throw "Offline image archive was not found: $archivePath"
}

$hashPath = "$archivePath.sha256"
if (Test-Path -LiteralPath $hashPath -PathType Leaf) {
    $expectedHash = ((Get-Content -LiteralPath $hashPath -Raw).Trim() -split '\s+')[0].ToLowerInvariant()
    $actualHash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($expectedHash -ne $actualHash) {
        throw "Offline image archive checksum mismatch: $archivePath"
    }
}

Write-Host "Loading offline Docker images..."
& docker image load --input $archivePath
if ($LASTEXITCODE -ne 0) {
    throw "docker image load failed."
}

$deployScript = Join-Path $PSScriptRoot "deploy_docker.ps1"
$arguments = @{
    EnvFile = $EnvFile
    NoBuild = $true
    SkipInit = $SkipInit
    HealthTimeoutSeconds = $HealthTimeoutSeconds
}
if ($ActiveScenarioOnly) {
    $arguments.ActiveScenarioOnly = $true
}

& $deployScript @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Offline Docker deployment failed."
}
