<#
.SYNOPSIS
    KnowForge RAG Platform Docker 一键部署脚本。

.DESCRIPTION
    该脚本通过 docker compose 完成 KnowForge 的完整部署：
      1. 校验 .env.compose 环境变量（API Key、管理令牌）
      2. 启动基础设施（MySQL、Redis、etcd、MinIO、Milvus）
      3. 等待基础设施健康就绪
      4. 构建 API 镜像（首次部署或 --NoBuild:$false 时）
      5. 初始化知识库版本（全场景或仅 active 场景）
      6. 启动 API 服务

.PARAMETER EnvFile
    docker compose 环境变量文件路径，默认为 .env.compose。

.PARAMETER AllScenarios
    初始化所有 8 个冻结业务场景的知识库版本（默认行为）。

.PARAMETER ActiveScenarioOnly
    仅初始化 ACTIVE_SCENARIO_ID 指定的场景。与 -AllScenarios 互斥。

.PARAMETER SkipInit
    跳过知识库初始化步骤（适用于已初始化过的环境重启）。

.PARAMETER NoBuild
    跳过 API 镜像构建步骤（适用于镜像已存在的情况）。

.PARAMETER HealthTimeoutSeconds
    等待基础设施服务健康就绪的最大秒数，默认 420 秒（7 分钟）。

.EXAMPLE
    .\scripts\deploy_docker.ps1
    完整部署：构建镜像 → 初始化全部 8 个场景 → 启动 API。

.EXAMPLE
    .\scripts\deploy_docker.ps1 -ActiveScenarioOnly
    仅初始化和激活一个业务场景（快速验证）。

.EXAMPLE
    .\scripts\deploy_docker.ps1 -SkipInit -NoBuild
    重启已有的 KnowForge 容器（不重新构建或初始化）。
#>

param(
    [string]$EnvFile = ".env.compose",
    [switch]$AllScenarios,
    [switch]$ActiveScenarioOnly,
    [switch]$SkipInit,
    [switch]$NoBuild,
    [int]$HealthTimeoutSeconds = 420
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

<#
.SYNOPSIS
    \u5c06\u76f8\u5bf9\u8def\u5f84\u89e3\u6790\u4e3a\u57fa\u4e8e\u9879\u76ee\u6839\u76ee\u5f55\u7684\u7edd\u5bf9\u8def\u5f84\u3002
    \u5982\u679c\u8def\u5f84\u5df2\u7ecf\u662f\u7edd\u5bf9\u8def\u5f84\u5219\u76f4\u63a5\u8fd4\u56de\u3002
#>
function Resolve-RepoPath {
    param([string]$Path)
    if ([System.IO.Path]::IsPathRooted($Path)) {
        return $Path
    }
    return Join-Path $RepoRoot $Path
}

<#
.SYNOPSIS
    \u786e\u4fdd\u6307\u5b9a\u76ee\u5f55\u5b58\u5728\uff0c\u4e0d\u5b58\u5728\u5219\u521b\u5efa\u3002
    \u5982\u679c\u8def\u5f84\u5df2\u5b58\u5728\u4f46\u4e0d\u662f\u76ee\u5f55\uff08\u662f\u6587\u4ef6\uff09\uff0c\u5219\u629b\u51fa\u5f02\u5e38\u3002
#>
function Ensure-Directory {
    param([string]$Path)
    $resolvedPath = Resolve-RepoPath $Path
    if (Test-Path -LiteralPath $resolvedPath) {
        $item = Get-Item -LiteralPath $resolvedPath
        if (-not $item.PSIsContainer) {
            throw "$Path must be a directory, but a file already exists at $resolvedPath."
        }
        return
    }
    New-Item -ItemType Directory -Path $resolvedPath -Force | Out-Null
}

<#
.SYNOPSIS
    \u4ece docker compose .env \u6587\u4ef6\u4e2d\u8bfb\u53d6\u6307\u5b9a\u73af\u5883\u53d8\u91cf\u7684\u503c\u3002

.DESCRIPTION
    \u89e3\u6790 KEY=value \u683c\u5f0f\u7684\u73af\u5883\u53d8\u91cf\u6587\u4ef6\uff0c\u652f\u6301\u5f15\u53f7\u5305\u88f9\u7684\u503c\u3002
    \u5982\u679c\u540c\u4e00\u53d8\u91cf\u51fa\u73b0\u591a\u6b21\uff0c\u53d6\u6700\u540e\u4e00\u6b21\u51fa\u73b0\u7684\u503c\uff08docker compose \u884c\u4e3a\uff09\u3002

.PARAMETER Path
    .env \u6587\u4ef6\u8def\u5f84\u3002

.PARAMETER Name
    \u73af\u5883\u53d8\u91cf\u540d\u79f0\uff08\u5982 DASHSCOPE_API_KEY\uff09\u3002
#>
function Get-EnvValue {
    param(
        [string]$Path,
        [string]$Name
    )
    $escapedName = [regex]::Escape($Name)
    $line = Get-Content -LiteralPath $Path |
        Where-Object { $_ -match "^\s*$escapedName\s*=" } |
        Select-Object -Last 1
    if (-not $line) {
        return ""
    }
    return (($line -replace "^\s*$escapedName\s*=", "").Trim().Trim('"').Trim("'"))
}

<#
.SYNOPSIS
    \u6821\u9a8c .env \u6587\u4ef6\u4e2d\u7684\u5173\u952e\u914d\u7f6e\u503c\u662f\u5426\u5df2\u6b63\u786e\u586b\u5199\u3002

.DESCRIPTION
    \u68c0\u67e5\u9879\uff1a
      - \u503c\u4e0d\u80fd\u4e3a\u7a7a
      - \u957f\u5ea6\u4e0d\u80fd\u4f4e\u4e8e MinLength\uff08\u9ed8\u8ba4 8\uff09
      - \u4e0d\u80fd\u5305\u542b\u4e2d\u6587\u5b57\u7b26\uff08\u53ef\u80fd\u662f\u6a21\u677f\u5360\u4f4d\uff09
      - \u4e0d\u80fd\u5305\u542b replace/changeme/placeholder \u7b49\u5360\u4f4d\u5173\u952e\u8bcd
#>
function Assert-ConfiguredValue {
    param(
        [string]$Path,
        [string]$Name,
        [int]$MinLength = 8
    )
    $value = Get-EnvValue -Path $Path -Name $Name
    if ([string]::IsNullOrWhiteSpace($value) -or
        $value.Length -lt $MinLength -or
        $value -match '[\u4e00-\u9fff]' -or
        $value -match '(?i)replace|changeme|change-me|your-|placeholder') {
        throw "$Name is not configured in $Path. Please edit the env file before deployment."
    }
}

<#
.SYNOPSIS
    \u6267\u884c docker compose \u547d\u4ee4\u5e76\u68c0\u67e5\u9000\u51fa\u7801\u3002
    \u4efb\u4f55\u975e\u96f6\u9000\u51fa\u7801\u90fd\u4f1a\u5bfc\u81f4\u811a\u672c\u7ec8\u6b62\u3002
#>
function Invoke-Compose {
    param([string[]]$Arguments)
    & docker compose --env-file $EnvFile @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose command failed: $($Arguments -join ' ')"
    }
}

<#
.SYNOPSIS
    \u5faa\u73af\u7b49\u5f85 Docker Compose \u670d\u52a1\u5065\u5eb7\u5c31\u7eea\u3002

.DESCRIPTION
    \u6bcf 5 \u79d2\u68c0\u67e5\u4e00\u6b21\u5bb9\u5668\u7684\u5065\u5eb7\u72b6\u6001\uff0c\u76f4\u5230\u72b6\u6001\u4e3a healthy/running
    \u6216\u8d85\u8fc7 TimeoutSeconds \u79d2\u3002\u7528\u4e8e\u786e\u4fdd MySQL\u3001Redis\u3001Milvus \u7b49
    \u57fa\u7840\u8bbe\u65bd\u5728\u540e\u7eed\u6b65\u9aa4\u6267\u884c\u524d\u5df2\u53ef\u7528\u3002
#>
function Wait-ComposeHealth {
    param(
        [string]$Service,
        [int]$TimeoutSeconds
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $containerId = (& docker compose --env-file $EnvFile ps -q $Service).Trim()
        if ($LASTEXITCODE -ne 0) {
            throw "Unable to inspect service: $Service"
        }
        if ($containerId) {
            $status = (& docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' $containerId 2>$null).Trim()
            if ($status -eq "healthy" -or $status -eq "running") {
                Write-Host "$Service is $status."
                return
            }
            Write-Host "$Service status: $status. Waiting..."
        }
        Start-Sleep -Seconds 5
    }
    throw "$Service did not become healthy within $TimeoutSeconds seconds."
}

# ---------- 阶段 1：环境校验 ----------

$EnvFilePath = Resolve-RepoPath $EnvFile
# .env 文件不存在时，从模板 .env.compose.example 复制一份并提示用户填写
if (-not (Test-Path -LiteralPath $EnvFilePath)) {
    Copy-Item -LiteralPath (Join-Path $RepoRoot ".env.compose.example") -Destination $EnvFilePath
    throw "Created $EnvFile. Please fill DASHSCOPE_API_KEY and ADMIN_API_TOKEN, then rerun this script."
}

# 校验关键环境变量已正确填写（非模板占位符）
Assert-ConfiguredValue -Path $EnvFilePath -Name "DASHSCOPE_API_KEY" -MinLength 12
Assert-ConfiguredValue -Path $EnvFilePath -Name "ADMIN_API_TOKEN" -MinLength 12

$env:ENV_FILE = $EnvFile

if ($AllScenarios -and $ActiveScenarioOnly) {
    throw "-AllScenarios and -ActiveScenarioOnly cannot be used together."
}

# 确保 logs 和 reports 目录存在，避免 docker compose 因挂载失败
foreach ($directory in @("logs", "reports")) {
    Ensure-Directory -Path $directory
}

if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot "site\index.html"))) {
    Write-Warning "site/index.html was not found. Run 'python -m mkdocs build' before opening /docs in Docker."
}

# ---------- 阶段 2：启动基础设施（MySQL、Redis、etcd、MinIO、Milvus） ----------

Write-Host "Validating docker compose config..."
Invoke-Compose -Arguments @("config", "--quiet")

Write-Host "Starting MySQL, Redis, etcd, MinIO and Milvus..."
Invoke-Compose -Arguments @("up", "-d", "mysql", "redis", "etcd", "minio", "milvus")
Wait-ComposeHealth -Service "mysql" -TimeoutSeconds $HealthTimeoutSeconds
Wait-ComposeHealth -Service "redis" -TimeoutSeconds $HealthTimeoutSeconds
Wait-ComposeHealth -Service "milvus" -TimeoutSeconds $HealthTimeoutSeconds

# ---------- 阶段 3：构建 API 镜像 ----------

if (-not $NoBuild) {
    # 基础镜像包含 Python 3.12 + 系统依赖（poppler、tesseract 等），构建耗时较长
    & docker image inspect localhost/knowforge-rag-platform-base:py312 *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Base dependency image was not found. Building it first..."
        & docker build -f Dockerfile.base -t localhost/knowforge-rag-platform-base:py312 .
        if ($LASTEXITCODE -ne 0) {
            throw "docker build Dockerfile.base failed."
        }
    }
    Write-Host "Building API image..."
    Invoke-Compose -Arguments @("build", "api")
}

# ---------- 阶段 4：初始化知识库版本 ----------

if (-not $SkipInit) {
    if ($ActiveScenarioOnly) {
        # 仅初始化当前 active 场景，适合快速验证
        $scenario = Get-EnvValue -Path $EnvFilePath -Name "ACTIVE_SCENARIO_ID"
        if ([string]::IsNullOrWhiteSpace($scenario)) {
            $scenario = "enterprise_knowledge"
        }
        Write-Host "Initializing active scenario only: $scenario"
        Invoke-Compose -Arguments @(
            "run", "--rm", "api", "python", "scripts/rebuild_kb_version.py",
            "--scenario", $scenario,
            "--new-version", "--force", "--quality-gate", "--activate"
        )
    }
    else {
        # 初始化全部 8 个冻结业务场景
        Write-Host "Initializing all 8 frozen business scenarios (Docker default)..."
        Invoke-Compose -Arguments @(
            "run", "--rm", "api", "python", "scripts/rebuild_scenarios.py",
            "--reset-collections",
            "--description", "docker init all scenarios"
        )
    }
}

# ---------- 阶段 5：启动 API 并输出访问地址 ----------

Write-Host "Starting API..."
Invoke-Compose -Arguments @("up", "-d", "api")
Invoke-Compose -Arguments @("ps")

$apiPort = Get-EnvValue -Path $EnvFilePath -Name "API_PORT"
if ([string]::IsNullOrWhiteSpace($apiPort)) {
    $apiPort = "8000"
}
Write-Host "KnowForge is ready at http://127.0.0.1:$apiPort/"
