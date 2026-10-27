# 安装与部署

本文面向当前 `qiye_rag` 仓库，代码内项目名仍为 KnowForge RAG Platform。以下步骤用于本地或受控测试环境，不代表生产部署已完成安全加固。

## 前置条件

- Git、Docker Engine 或 Docker Desktop，以及 Docker Compose v2。
- 可访问容器镜像源、Python 包源与配置的模型服务。
- 足够的内存和磁盘空间以加载本地模型并运行 MySQL、Redis、Milvus、etcd 和 MinIO；实际资源需求需按模型、资料规模与并发压测确定。
- 本机 Python 调试建议使用 Python 3.12 和独立虚拟环境。

所有命令均从仓库根目录执行。不要在已有业务环境中直接运行集合重置或卷删除命令。

## 1. 获取源码

```sh
git clone https://github.com/le27161/qiye_rag.git
cd qiye_rag
```

## 2. 准备模型

自行获取有权使用的模型，并放入：

```text
models/bge-m3/
models/bge-reranker-large/
models/bert_intent_classifier_v1/
```

前两项分别用于 Embedding 与 Rerank；第三项需要匹配项目标签及配置的意图分类模型。仓库不分发权重，也不承诺自动下载或自动训练。只有基础 BERT 权重不能替代已经训练好的意图分类器。

## 3. 配置环境

PowerShell：

```powershell
if (!(Test-Path .env.compose)) { Copy-Item .env.compose.example .env.compose }
notepad .env.compose
New-Item -ItemType Directory -Force -Path models,logs,reports,site | Out-Null
```

Linux / macOS：

```sh
test -f .env.compose || cp .env.compose.example .env.compose
mkdir -p models logs reports site
```

编辑 `.env.compose`，至少确认：

- `DASHSCOPE_API_KEY`：真实可用的模型服务密钥。
- `ADMIN_API_TOKEN`：自行生成的随机长令牌。
- `ACTIVE_SCENARIO_ID`：默认 `enterprise_knowledge`。
- 数据库、Redis、Milvus 地址使用 Compose 服务名；模型路径使用容器内的 `/app/models/...`。
- 宿主机映射端口无冲突。模板中的 MySQL 映射端口与本机模式默认端口不同，本机调试时尤其需要核对。

当前 `docker-compose.yml` 中存在演示用的硬编码 MySQL 和 MinIO 凭据。仅修改 `.env.compose` 不会同步改变全部服务端凭据；如需调整，应同时修改 Compose 服务配置、健康检查及连接配置。Redis 默认未启用认证。生产环境应额外限制基础服务端口和网络访问。

`site/` 在这里仅作为 Compose 挂载目录创建；它不会自动获得文档内容，也不影响主要问答页面的使用。

## 4. 构建镜像并启动基础服务

```sh
docker build -f Dockerfile.base -t localhost/knowforge-rag-platform-base:py312 .
docker compose --env-file .env.compose build api
docker compose --env-file .env.compose up -d mysql redis etcd minio milvus
docker compose --env-file .env.compose ps
```

等待依赖服务健康后再继续。若启动失败，先检查端口、可用资源和服务日志：

```sh
docker compose --env-file .env.compose logs --tail 100 mysql redis milvus
```

不要将包含密钥、原始业务资料或个人信息的日志直接公开。

## 5. 初始化知识库

首次为默认场景构建版本，并在入库质量门禁通过后激活：

```sh
docker compose --env-file .env.compose run --rm api python scripts/rebuild_kb_version.py --scenario enterprise_knowledge --new-version --quality-gate --activate --description "initial knowledge base"
```

此步骤依赖本地模型和数据库。出现解析、连接或质量检查错误时，先修复原因；不要为绕过错误直接删除集合或关闭门禁。

如需其他场景，将 `--scenario` 替换成 `scenarios/` 下的场景 ID，分别构建并激活。API 启动会检查默认场景的 active 知识库版本，所以初始化必须先于 API 启动。

## 6. 启动与检查

```sh
docker compose --env-file .env.compose up -d api
docker compose --env-file .env.compose ps
docker compose --env-file .env.compose logs --tail 100 api
```

默认访问：

- 问答：<http://localhost:8000/>
- 管理：<http://localhost:8000/admin>
- 健康检查：<http://localhost:8000/health>
- Swagger：<http://localhost:8000/api/docs>

如果修改了 `API_PORT`，需相应替换 URL 端口。健康状态应结合返回的模型和检索预热信息判断，不能仅凭容器进程存在认定问答链路可用。

## 日常更新

资料更新可创建新的增量版本，质量检查通过后再激活：

```sh
docker compose --env-file .env.compose run --rm api python scripts/rebuild_kb_version.py --scenario enterprise_knowledge --new-version --incremental-from active --quality-gate --activate --description "knowledge update"
```

此命令会更新知识库及 active 指针，应先备份并在测试环境验证。模型或切块策略变更前，单独评估全量重建与迁移方案。不要将 `--reset-collections` 作为普通更新参数。

仅更新应用代码时：

```sh
docker compose --env-file .env.compose build api
docker compose --env-file .env.compose up -d api
```

停止容器而保留命名卷：

```sh
docker compose --env-file .env.compose down
```

不要随意添加 `-v`，该选项会删除相关命名卷中的持久化数据。

## 本机 Python 调试

PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
if (!(Test-Path .env)) { Copy-Item .env.local.example .env }
```

修改 `.env` 中的密钥、本地模型路径与宿主机映射端口，确认基础服务可达。先使用本机 Python 执行知识库构建，再启动：

```sh
python scripts/rebuild_kb_version.py --scenario enterprise_knowledge --new-version --quality-gate --activate
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

完整业务回归需另外运行评测与接口检查，具体入口见 [README](README.md)。上述命令已按源码入口核对，但不代表本次文档更新中已实际启动模型和数据库完成验收。
