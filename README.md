# KnowForge RAG Platform

这是一个基于 `LangChain + Milvus Hybrid Search + FastAPI` 的多场景 RAG 系统项目。项目目标不是做一个简单聊天页面，而是把企业级 RAG 的主链路、知识库治理、RAG 回归验收、版本管理、数据隔离和流式问答做成可以演示、可以验收、可以写进简历的完整工程。

工程名统一为 `knowforge-rag-platform`，产品展示名为 **KnowForge RAG Platform**，中文定位是 **企业级多场景 RAG 知识平台**。

当前业务场景已经冻结为 8 个，不再继续新增场景包；后续重点放在资料质量、评测回归和版本治理。

如果是第一次学习或准备演示，建议先看 [系统讲义首页](docs/index.md) 和 [课程大纲](docs/course-outline.md)。前者帮助先抓主线，后者按 01-19 讲串起当前文档和主链路。

如果需要从第 05 章开始按章节跟敲项目代码，进入 [codealong/](codealong/README.md)。该目录和主项目源码分开，按章节提供可运行、可测试的小闭环。

## 学习路径减法

第一次学习不要从所有脚本、所有业务场景和所有状态页卡片开始。建议按三层看：

| 层级 | 范围 | 目标 |
| --- | --- | --- |
| 必须掌握 | `app.py`、`qa_core/api`、`qa_core/application`、`qa_core/pipeline`、`qa_core/retrieval`、`qa_core/prompts`、`qa_core/indexing` | 跑通并讲清楚 RAG 主链路 |
| 验收掌握 | `scripts/rebuild_kb_version.py`、`scripts/check_project_guardrails.py`、`scripts/evaluate_core_chain.py`、`scripts/quality/check_evaluation_gate.py`、`scripts/api_e2e_smoke.py`、`scripts/acceptance_smoke.py` | 证明系统可交付 |
| 了解即可 | 企业资料治理、本地 Bad Case 沉淀、LangSmith 可选观测、overlay 激活、OCR 提升、性能检查等专题 | 汇报追问或二次扩展时再讲 |

状态页也按这个原则做了减法：聚焦 V1 基础治理工作台，只展示并操作知识库版本、入库质量报告、回归报告、治理摘要和低质量反馈入口；Trace 详情可以接入 LangSmith，本地质量闭环以评测报告、`eval_sets/` 和 Gate 脚本为主。

## 1. 项目定位

本项目适合用来讲清楚以下能力：

- 如何用 LangChain 组织文档加载、切分、向量化、LLM 调用和聊天历史；
- 如何用 Milvus 2.5.x 内置 BM25 做 dense + sparse 混合检索；
- 如何把 FAQ 标准问答和文档 RAG 组合在一条主链路里；
- 如何做知识库版本、embedding 版本、chunk schema 版本和 active 版本切换；
- 如何做多场景、多 source、多租户数据隔离；
- 如何用 Prompt Profile 控制费用、合规、安全、排障等高风险问题的回答边界；
- 如何用 Recall@K、MRR、关键词覆盖、Prompt 命中率和场景隔离率做回归评测；
- 如何通过本地评测报告或 LangSmith Trace 定位 RAG bad case。

一句话介绍：

> 基于 LangChain 和 Milvus Hybrid Search 构建的 KnowForge RAG Platform，支持 FAQ 直出、文档问答、知识库多版本、数据隔离、流式输出、入库质量检查和 RAG 回归验收。

## 2. 业务场景

| 场景 ID | 业务背景 | source 数 | FAQ | 文档 | 简历包装 |
| --- | --- | ---: | ---: | ---: | --- |
| `enterprise_knowledge` | HR、IT、财务制度 | 3 | 8 | 11 | 企业内部知识库智能问答平台 |
| `saas_support` | 账号、计费、开放集成 | 3 | 6 | 11 | SaaS 客服知识库智能助手 |
| `equipment_ops` | 巡检、告警、安全规范 | 3 | 6 | 11 | 制造业设备运维知识助手 |
| `compliance_qa` | 合同、审计、隐私保护 | 3 | 6 | 11 | 企业合规制度智能问答系统 |
| `cross_border_risk` | 海关、制裁、信用证、物流、单证 | 5 | 11 | 15 | 跨境贸易风控 RAG 知识问答平台 |
| `tender_contract_risk` | 招投标、合同、交付、验收、履约风险 | 5 | 11 | 15 | 招投标合规与合同履约 RAG 风控平台 |
| `insurance_claims` | 保单、理赔材料、责任、除外、赔付 | 5 | 10 | 15 | 保险理赔材料审核与 RAG 知识问答助手 |
| `engineering_project_qa` | 图纸、规范、进度、质量、安全资料 | 5 | 11 | 15 | 工程项目资料与施工规范 RAG 问答助手 |

更推荐在简历和汇报中主推后四个差异化场景：

- 跨境贸易风控：适合讲海关申报、制裁筛查、信用证和单证一致性；
- 招投标合同履约：适合讲合同风险、交付验收和付款边界；
- 保险理赔审核：适合讲材料审核、责任认定和赔付口径控制；
- 工程项目资料问答：适合讲多文档、多版本、图纸/规范冲突和标准规范检索。

## 3. 核心功能

| 能力 | 当前实现 |
| --- | --- |
| 多场景切换 | `scenarios/<scenario_id>/scenario.toml + faq.csv + data/` 配置化切换 |
| 混合检索 | Milvus dense vector + Milvus 内置 BM25 sparse |
| FAQ 直出 | 高置信 FAQ 直接返回标准答案，低置信进入文档 RAG |
| 文档 RAG | LangChain loader/splitter + parent-child chunk + rerank |
| 表格资料 | CSV/Excel 按表头、工作表、行号和单元格键值转换为行级 Document；表格类问题会优先保留表格行上下文 |
| 多格式样例 | 8 个冻结场景都包含 Markdown、CSV、XLSX、DOCX、PPTX、PDF，便于直接验证多格式入库 |
| 离线 OCR | PaddleOCR + PyMuPDF 生成待复核 Markdown 和 OCR 报告；已复核 Markdown 通过提升脚本进入资料目录，再走版本重建 |
| 意图识别 | FAQ、知识咨询、追问、越界、客服等意图识别 |
| source 推断 | 不手选分类时，根据问题自动推断 source |
| 场景边界 | 问题明显属于其他场景时阻断检索，只提示切换场景 |
| source 边界 | 用户选错分类时阻断错误分类检索，避免低分上下文污染答案 |
| 查询扩展 | 针对知识咨询和追问生成 query variants |
| Prompt 路由 | 费用、合规、排障、总结等问题使用不同 Prompt Profile |
| 多版本知识库 | active 版本检索，支持新版本入库、评测、激活和回滚 |
| 版本对比 | 支持单场景和全场景 base/candidate 召回对比，激活前发现召回退化 |
| 数据隔离 | tenant、dataset、visibility、allowed_roles 写入 metadata 并参与检索过滤 |
| 聊天历史 | MySQL + LangChain `SQLChatMessageHistory` |
| 流式输出 | WebSocket 返回 `start/status/token/end` 事件 |
| LangSmith 观测 | Trace、阶段耗时、首 token、检索诊断、来源引用，RAG 答案缺引用时自动补参考来源 |
| 入库质量检查 | 入库质量报告、FAQ/正文冲突检测、低质量 chunk 检测、表格/OCR 风险统计 |
| 评测回归 | Recall@K、MRR、关键词覆盖、模板命中率、场景隔离率、表格行召回专项回归、负样本边界回归 |
| 性能基线 | 固定 `phase1_performance_baseline.json`，覆盖 8 个场景的 FAQ、文档 RAG 和表格 RAG |
| 就绪总报告 | 汇总表格、负样本、版本对比、性能和接口冒烟，生成一期交付视图 |
| Bad Case 闭环 | 本地评测报告 + `extract_bad_cases_from_report.py` + `eval_sets/`，人工确认后进入回归评测；LangSmith 可选承接 Trace 和协作标注 |
| 企业仿真数据包 | `data_packs/enterprise_realistic_pack/` 提供 clean overlay 和 dirty samples，用于拉近样例数据与真实企业资料现场的距离 |

## 4. 技术架构

| 层级 | 方案 |
| --- | --- |
| Web/API | FastAPI + WebSocket |
| RAG 编排 | `qa_core.application.QAService` |
| LangChain | loader、splitter、ChatOpenAI、SQLChatMessageHistory、Milvus 集成 |
| LLM | DashScope OpenAI-compatible API |
| Embedding | 本地 BGE-M3 |
| Rerank | 本地 BGE reranker |
| 向量库 | Milvus 2.5.x，支持内置 BM25 Function / Hybrid Search |
| 稀疏检索 | Milvus `BM25BuiltInFunction` |
| 历史/反馈 | MySQL |
| 前端 | 原生静态页面 + 状态页 |
| RAG 回归验收 | 项目内置脚本 + JSON 报告 |
| 扩展边界 | 当前主链路聚焦企业知识库 RAG，不包含任务调度、工具调用或跨系统协作实现 |

主链路：

```text
浏览器页面
  -> FastAPI / WebSocket
  -> QAService
  -> 场景解析 / 数据域解析
  -> 查询路由 direct_answer / faq_exact / retrieval
  -> 意图识别 / source 推断 / 追问改写
  -> 检索计划生成
  -> FAQ Hybrid 检索
  -> 文档 Hybrid 检索
  -> rerank / 上下文构建
  -> Prompt Profile 路由
  -> LLM 流式生成
  -> MySQL 历史 / LangSmith Trace / feedback
```

## 5. 为什么这样设计

### 为什么不用自研 BM25

当前项目使用 Milvus 2.5.x 的内置 BM25 能力。dense、sparse、版本过滤和数据隔离统一放在 Milvus 中完成，避免维护本地 BM25、RedisSearch 或第二套索引。

### 为什么不把 LlamaIndex 放进主链路

LlamaIndex 很适合快速搭建 RAG 数据接入和 QueryEngine 原型，但本项目的一期主线是多场景企业级 RAG：查询路由、FAQ/Doc 分层检索、知识库 active 版本、DataScope、质量门禁、Prompt Profile 和回归验收都需要显式可见。

当前选择是：

```text
主链路：LangChain + Milvus Hybrid Search + qa_core 显式 Pipeline
可选扩展：LlamaIndex 文档加载、transformations、缓存机制
不放入一期主代码：LlamaIndex QueryEngine / Index 作为在线问答主框架
```

这样可以避免同时解释 LangChain 的 `Document/VectorStore` 和 LlamaIndex 的 `Document/Node/Index/QueryEngine`，降低首轮学习复杂度。代码层面也保持一致：`requirements.txt` 不引入 `llama-index`，主项目不导入 `llama_index`。

### 本轮收敛了哪些复杂度

项目保留企业核心能力，不追求把代码压到最少。本轮收敛重点是去掉不会进入一期主链路的依赖和方案：

| 项目 | 当前状态 | 说明 |
|---|---|---|
| Redis | 直接依赖 | 用于 query embedding 缓存、FAQ/Doc 检索候选缓存；不替代 Milvus Hybrid Search，不缓存普通 LLM 自由生成答案 |
| Python 本地 BM25 | 不作为主链路依赖 | `rank_bm25` 只在讲义中作为原理示例，线上 sparse 检索由 Milvus BM25BuiltInFunction 完成 |
| LlamaIndex | 不引入主代码 | 仅作为入库基础设施可选优化方向，不进入一期主链路 |
| Docling | 主依赖，按配置启用 | `requirements.txt` 已包含；默认 `DOCUMENT_PARSER_BACKEND=native`，复杂 PDF/DOCX/PPTX/HTML 可切到 `docling` |
| RAGAS | 保留补充评测 | 语义质量补充分析，不替代工程回归门禁 |

这样做可以降低学习复杂度，同时不牺牲 `scenario`、`kb_version`、`DataScope`、质量门禁、Prompt Profile 等企业级能力。

### 文档解析为什么是 native 默认 + Docling 配置增强

当前默认文档解析后端是：

```env
DOCUMENT_PARSER_BACKEND=native
```

默认路径覆盖 Markdown、TXT、带文本层 PDF、DOCX、PPTX、CSV、XLSX、XLS。CSV/Excel 始终使用项目内行级表格 loader，保留 sheet、行号、表头和单元格键值，便于检索和引用。

Docling 已纳入完整项目依赖，安装主依赖即可。复杂版面资料可以启用 Docling：

```powershell
pip install -r requirements.txt
$env:DOCUMENT_PARSER_BACKEND="docling"
python scripts/tools/docling_parser_smoke.py
```

Docker Compose 环境使用同一套项目依赖。普通 Python 依赖变更后，重建 API 镜像即可补齐依赖；如果是新机器首次部署、基础镜像不存在，或新增了系统级依赖，再先构建 `Dockerfile.base`：

```powershell
docker compose --env-file .env.compose build api
```

```powershell
docker build -f Dockerfile.base -t localhost/knowforge-rag-platform-base:py312 .
docker compose --env-file .env.compose build api
```

Linux 服务器如果无法访问默认 Debian 源，可在构建时覆盖源地址；项目默认使用 HTTPS，避免受限网络阻断 HTTP 80 端口：

```bash
docker build -f Dockerfile.base \
  --build-arg DEBIAN_MIRROR=https://deb.debian.org/debian \
  --build-arg DEBIAN_SECURITY_MIRROR=https://deb.debian.org/debian-security \
  --build-arg PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple \
  --build-arg PYTORCH_INDEX_URL=https://download.pytorch.org/whl/cpu \
  -t localhost/knowforge-rag-platform-base:py312 .
docker compose --env-file .env.compose \
  build --build-arg PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple api
```

内网部署时，将两个参数替换为企业可访问的 Debian 镜像源即可。

然后在 `.env.compose` 中设置 `DOCUMENT_PARSER_BACKEND=docling`。这个开关只接管 PDF/DOCX/PPTX/HTML，表格资料仍走项目行级 loader，扫描件仍应走 OCR 复核治理流程。可先运行 `python scripts/tools/docling_parser_smoke.py` 验证增强解析环境，再重建知识库版本。

如果 API 容器仍报 `ModuleNotFoundError: No module named 'pptx'`，先确认镜像中的 `/app/requirements.txt` 确实已经包含 `python-pptx`，避免在旧镜像上反复排错：

```powershell
docker run --rm knowforge-rag-platform-api:latest sh -lc "grep -n 'python-pptx' /app/requirements.txt"
```

如果镜像里没有这行，说明运行机器上的项目代码还没同步到最新；先同步代码，再执行：

```powershell
docker compose --env-file .env.compose build --no-cache api
docker compose --env-file .env.compose up -d --force-recreate api
```

### 为什么保留 Milvus 适配层

在线业务检索统一通过 `langchain-milvus` 的 VectorStore 接入 Milvus，`QAService`
和 pipeline 不直接调用 PyMilvus。项目仍保留 `qa_core/retrieval/milvus_compat.py`
作为底层适配层，用来处理 Milvus database 检查、BM25 内置函数和 PyMilvus ORM
连接别名注册。当前稳定组合只保留显式、可读的连接初始化，不在业务链路里加入额外运行时改写。

推荐解释口径：

```text
LangChain / langchain-milvus 负责 RAG VectorStore 抽象；
PyMilvus 负责底层连接现实；
适配层只把 BM25 Function、database 和连接别名接好，不进入业务编排。
```

### 为什么 MySQL 仍然保留

MySQL 不再承担知识检索职责，只保存聊天历史、摘要、反馈和后续可能的管理元数据。知识召回由 Milvus 负责，会话状态由 MySQL 负责，职责更清楚。

### 为什么暂不引入 Alembic

项目已经把 MySQL 表结构初始化收敛到 `qa_core/storage/runtime_schema.sql`。版本表、active 指针表、Manifest 表、反馈表和摘要表的 DDL 都在这个 SQL 文件里，`qa_core/storage/mysql_schema.py` 只负责读取并执行它，业务 Store 只负责读写。

| 选择 | 当前处理 |
|---|---|
| 当前阶段 | 用 `runtime_schema.sql` 集中展示表结构，无需额外学习迁移框架 |
| 企业核心 | 保留 MySQL 控制面、Milvus 数据面、active 指针和质量门禁 |
| 生产升级 | 后续可以把 `runtime_schema.sql` 提升为 Alembic revision |

这样既降低首轮学习复杂度，也为后续生产化迁移留下清晰入口。

### 为什么 FAQ 和文档分开

FAQ 是标准口径，适合高置信直出；文档是解释依据，适合复杂问题补充上下文。二者混在一个检索策略里容易导致标准答案被长文档稀释，或者复杂问题被单条 FAQ 误答。

### 为什么要 Prompt Profile

不同问题风险不同。退款、预算、信用证、保证金、赔付等问题需要 `pricing_guard`；合同、隐私、制裁、安全交底、检验批等问题需要 `compliance_guard`；API 限流、设备告警等问题需要 `troubleshooting_steps`。这类路由必须稳定可测，不能完全交给模型自由发挥。

## 6. 快速启动

先选择运行模式，再准备环境变量。两种模式不要混用。

| 文件 | 是否提交 | 用途 |
|---|---:|---|
| `.env.compose.example` | 是 | Docker Compose 模板，地址使用 `mysql`、`milvus`、`/app/models/...` |
| `.env.compose` | 否 | Docker Compose 实际运行配置，由 `.env.compose.example` 复制后填写 |
| `.env.local.example` | 是 | 本机 API 调试模板，地址使用 `localhost` 和 `models/...` |
| `.env` | 否 | 本机 API 实际运行配置，由 `.env.local.example` 复制后填写 |

项目不再保留 `.env.example`。这个名字无法表达运行模式，容易把容器地址和本机地址混用。

### 6.1 全 Docker 测试

当前如果只是为了验收项目，推荐让 MySQL、Milvus 和 API 都由 Docker Compose 管理。这样
API 容器访问依赖时统一使用 `mysql`、`milvus` 这些 Compose 服务名，不会和宿主机
`localhost` 视角混在一起。

```powershell
if (!(Test-Path .env.compose)) { Copy-Item .env.compose.example .env.compose }
notepad .env.compose
```

必须配置真实可用值：

```text
DASHSCOPE_API_KEY=真实可用的模型服务 Key
ADMIN_API_TOKEN=随机长令牌
```

一键部署并初始化 8 个冻结业务场景：

```powershell
.\scripts\deploy\deploy_docker.ps1
```

如果只是临时调试当前 active 场景：

```powershell
.\scripts\deploy\deploy_docker.ps1 -ActiveScenarioOnly
```

脚本执行顺序是：启动 MySQL/Redis/Milvus → 确认基础依赖镜像存在并构建 API 镜像 → 在 API 容器里重建并激活 8 个业务场景 →
启动 API。这个顺序不能反过来，因为 API 启动前会检查 active KB 版本；空库直接启动 API
会被 preflight 拒绝。

脚本也会提前创建 `logs/`、`reports/` 两个运行时目录。手动执行
`docker compose` 时也要保证这些目录存在，否则 Windows Docker 可能把缺失的宿主机目录挂成不可用路径。

手动执行等价命令：

```powershell
docker compose --env-file .env.compose up -d mysql redis etcd minio milvus
# 新机器首次部署且本地没有基础镜像时先执行：
# docker build -f Dockerfile.base -t localhost/knowforge-rag-platform-base:py312 .
docker compose --env-file .env.compose build api
docker compose --env-file .env.compose run --rm api python scripts/rebuild_scenarios.py --reset-collections --description "docker init all scenarios"
docker compose --env-file .env.compose up -d api
docker compose --env-file .env.compose ps
```

访问：

- 问答页：http://127.0.0.1:8000/
- 状态页：http://127.0.0.1:8000/admin
- 讲义页：http://127.0.0.1:8000/docs/

讲义和流程动画由宿主机 `./site` 挂载到容器 `/app/site`。修改 `docs/` 或
`docs/animation/` 后，先执行 `python -m mkdocs build`，刷新 `/docs/...` 即可看到更新；
不需要为了讲义内容重建 API 镜像。

### 6.2 本机 API 调试

本机启动 API，Docker 只跑 MySQL/Milvus：

```powershell
if (!(Test-Path .env)) { Copy-Item .env.local.example .env }
notepad .env
```

本机模式同样必须配置真实可用值：

```text
DASHSCOPE_API_KEY=真实可用的模型服务 Key
ADMIN_API_TOKEN=随机长令牌
```

`DASHSCOPE_API_KEY` 不是形式校验。服务启动前会实际调用一次 OpenAI-compatible
LLM 接口，Key 欠费、无权限、模型名错误或服务地址不可用都会直接启动失败。正式学习和演示前
请先运行 `python scripts/tools/check_langchain_stack.py`，确认模型服务可用。

LangSmith 是企业观测和协作诊断入口，但本地 smoke 不强制开启。未配置
`LANGSMITH_TRACING=true` 和 `LANGSMITH_API_KEY` 时，状态页会显示未启用，接口验收仍会通过；
正式企业化演示时再打开 LangSmith tracing。

本地模型默认放在项目目录的 `models/` 下，Windows 和 Linux 都能使用同一套相对路径：

```text
./models/bge-m3
./models/bge-reranker-large
```

容器内模型路径保持不变：

```text
EMBEDDING_MODEL_PATH=/app/models/bge-m3
RERANKER_MODEL_PATH=/app/models/bge-reranker-large
```

Docker Compose 固定把项目 `./models` 挂载到容器 `/app/models`，因此 `.env.compose`
不需要再配置宿主机模型路径。外置模型目录可以通过系统软链接或手动调整 compose 挂载实现，课程默认只保留这一种最稳路径。

启动基础设施：

```powershell
docker compose --env-file .env.compose up -d mysql etcd minio milvus
```

Linux 宿主机如果提示 `python: command not found`，直接改用 `python3`。如果继续提示
`No module named pip`、`No module named pandas` 之类错误，说明宿主机 Python 依赖未安装；
这时推荐优先用 Docker API 容器执行脚本，或者先补齐：

```powershell
sudo apt update
sudo apt install -y python3-pip python3-venv
python3 -m pip install -r requirements.txt
```

在宿主机启动 API：

```powershell
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

检查 LangChain、Milvus、MySQL、模型和 LLM 配置：

```powershell
python scripts/tools/check_langchain_stack.py
```

访问：

- 问答页：http://127.0.0.1:8000/
- 状态页：http://127.0.0.1:8000/admin

## 7. 初始化知识库

Docker Compose 模式下，推荐在 API 容器内执行入库脚本。所有
`docker compose --env-file .env.compose ...` 命令都要求项目根目录已经存在
`.env.compose`，仓库只提交 `.env.compose.example`，首次使用前先生成本地配置文件：

```powershell
if (!(Test-Path .env.compose)) { Copy-Item .env.compose.example .env.compose }
notepad .env.compose
```

新环境首次部署，或者 Milvus collection schema 变更后需要重建全部 8 个冻结场景，使用：

```powershell
docker compose --env-file .env.compose up -d mysql redis etcd minio milvus
# 新机器首次部署且本地没有基础镜像时先执行：
# docker build -f Dockerfile.base -t localhost/knowforge-rag-platform-base:py312 .
docker compose --env-file .env.compose build api
docker compose --env-file .env.compose run --rm api python scripts/rebuild_scenarios.py --reset-collections
```

如果之前已经存在知识库，只是资料内容变化，重建全部 8 个场景时不要删除 collection：

```powershell
docker compose --env-file .env.compose run --rm api python scripts/rebuild_scenarios.py
```

如果只重建某一个已有场景，例如企业知识场景：

```powershell
docker compose --env-file .env.compose run --rm api python scripts/rebuild_kb_version.py --scenario enterprise_knowledge --new-version --force --quality-gate --activate
```

只有在旧 collection schema 不兼容、切换了 hybrid 字段结构，或者明确要清空重建单场景 collection 时，才给单场景命令追加 `--reset-collections`：

```powershell
docker compose --env-file .env.compose run --rm api python scripts/rebuild_kb_version.py --scenario enterprise_knowledge --new-version --force --reset-collections --quality-gate --activate
```

本机 API 调试模式下，首次运行或资料变更后，重建并激活 8 个场景：

```powershell
$scenarios = 'enterprise_knowledge','saas_support','equipment_ops','compliance_qa','cross_border_risk','tender_contract_risk','insurance_claims','engineering_project_qa'
foreach ($s in $scenarios) {
    python scripts/rebuild_kb_version.py --scenario $s --new-version --force --quality-gate --activate
}
```

单独重建某个场景：

```powershell
python scripts/rebuild_kb_version.py --scenario engineering_project_qa --new-version --force --quality-gate --activate
```

如果宿主机直接运行重建脚本时在 `reports/ingestion/...json` 报 `PermissionError: [Errno 13] Permission denied`，
通常是之前 Docker 容器以 `root` 写入了 `reports/` 或 `logs/`。先把目录 ownership 改回当前用户再重跑：

```powershell
sudo chown -R $env:USERNAME:$env:USERNAME reports logs
```

Linux shell 对应写法：

```bash
sudo chown -R $(whoami):$(whoami) reports logs
```

## 8. 验收命令

封版前推荐先按一条固定主路径验收。默认模式不依赖已启动 API 服务，也不要求宿主机安装完整
Milvus 运行依赖，适合快速确认讲义、跟敲结构、Docker Compose 配置和工程守护规则：

```powershell
python scripts/check_project_guardrails.py
python scripts/course/check_codealong_alignment.py
python scripts/course/check_docs_consistency.py
python -m mkdocs build --strict
python scripts/verify_v1_release.py
```

如果本机或容器已经具备 `requirements.txt` 中的完整 Python 依赖，再跑全量单测：

```powershell
python -m pytest tests -q
```

当前环境只适合快速回归时，可以先跑不依赖外部服务的核心测试子集：

```powershell
python -m pytest tests\test_intent_and_scenarios.py tests\test_api_protection.py tests\test_mysql_metadata_stores.py tests\test_preflight.py tests\test_ocr_script_paths.py tests\test_v1_maintenance_bindings.py -q
```

需要把 Docker 中的第 08 章分集合契约一起纳入封版验收时：

```powershell
python scripts/verify_v1_release.py --include-docker
```

API 已启动后，可以把真实接口和 WebSocket 验收也纳入报告：

```powershell
python scripts/verify_v1_release.py --include-api --base-url http://127.0.0.1:8000
```

验收报告默认写入 `reports/verification/v1_release_latest.json`。

如果确认当前环境已经安装完整运行时依赖，也可以让 V1 验收入口追加运行时单测：

```powershell
python scripts/verify_v1_release.py --include-runtime-tests
```

最小闭环命令还需要掌握这几条：

```powershell
python scripts/rebuild_kb_version.py --scenario enterprise_knowledge --new-version --force --quality-gate --activate
python scripts/evaluate_core_chain.py --dataset eval_sets/multi_scenario_smoke.json --limit 20 --output reports/evaluation/multi_scenario_smoke_live.json
python scripts/quality/check_evaluation_gate.py --report reports/evaluation/multi_scenario_smoke_live.json
python scripts/api_e2e_smoke.py --base-url http://127.0.0.1:8001
python scripts/acceptance_smoke.py --base-url http://127.0.0.1:8001
```

多场景核心评测：

```powershell
python scripts/evaluate_core_chain.py --dataset eval_sets/multi_scenario_smoke.json --limit 40 --output reports/evaluation/multi_scenario_smoke_live_40.json
python scripts/quality/check_evaluation_gate.py --report reports/evaluation/multi_scenario_smoke_live_40.json
```

RAGAS 语义质量补充评测：

```powershell
python scripts/quality/evaluate_ragas_quality.py --report reports/evaluation/multi_scenario_smoke_live_40.json --limit 10 --output reports/evaluation/multi_scenario_smoke_live_40_ragas.json
```

RAGAS 只作为离线语义质量分析，主要观察 `faithfulness`、`answer_relevancy` 等 LLM-as-judge 指标；
它不替代 `check_evaluation_gate.py`。企业级主门禁仍然以 Recall@K、MRR、hit_type、source 推断、
Prompt Profile、场景隔离、错误率和耗时为准。

汇报增强评测：

```powershell
python scripts/evaluate_core_chain.py --dataset eval_sets/multi_scenario_interview_regression.json --limit 16 --output reports/evaluation/multi_scenario_interview_regression_live_16_final.json
python scripts/quality/check_evaluation_gate.py --report reports/evaluation/multi_scenario_interview_regression_live_16_final.json --min-source-inference-accuracy 1.0 --min-prompt-profile-accuracy 1.0
```

业务深度评测：

```powershell
python scripts/evaluate_core_chain.py --dataset eval_sets/business_depth_regression.json --limit 32 --output reports/evaluation/business_depth_regression_live_32.json
python scripts/quality/check_evaluation_gate.py --report reports/evaluation/business_depth_regression_live_32.json --min-source-inference-accuracy 1.0 --min-prompt-profile-accuracy 0.85
```

多轮追问评测：

```powershell
python scripts/quality/evaluate_followup_chain.py --dataset eval_sets/multi_turn_followup_regression.json --output reports/evaluation/multi_turn_followup_smoke.json
python scripts/quality/check_followup_gate.py --report reports/evaluation/multi_turn_followup_smoke.json
```

真实链路验收：

如果 API 在 Docker Compose 中运行，推荐在 API 容器内执行验收脚本，脚本会读取
`.env.compose` 注入的 `ADMIN_API_TOKEN`，不需要把管理令牌写在命令行里。

真实 API 合同验收：

```powershell
docker compose --env-file .env.compose exec api python scripts/api_e2e_smoke.py --base-url http://127.0.0.1:8000
```

该脚本只检查 LangSmith 状态接口是否可用，不要求本地环境必须开启 LangSmith。是否开启会写入
`details.langsmith_enabled`，方便正式演示前确认。

页面和 WebSocket 验收：

```powershell
docker compose --env-file .env.compose exec api python scripts/acceptance_smoke.py --base-url http://127.0.0.1:8000
```

OCR 复核资料提升：

```powershell
python scripts/ocr/run_offline_ocr.py --input-dir incoming_scans --output-dir reports/ocr/batch_001
python scripts/ocr/promote_ocr_candidates.py --input-dir reports/ocr/batch_001 --scenario engineering_project_qa --source quality
python scripts/ocr/promote_ocr_candidates.py --input-dir reports/ocr/batch_001 --scenario engineering_project_qa --source quality --apply
python scripts/rebuild_kb_version.py --scenario engineering_project_qa --new-version --force --quality-gate --activate
```

固定性能基线：

```powershell
python scripts/quality/check_performance_gate.py --dataset eval_sets/phase1_performance_baseline.json --limit 8 --no-warmup --output reports/verification/phase1_performance_latest.json --gate-output reports/verification/phase1_performance_gate_latest.json
```

全场景版本召回对比：

```powershell
python scripts/kb/compare_all_kb_versions.py --dataset eval_sets/business_depth_regression.json --per-scenario-limit 2 --output reports/verification/kb_version_compare_all_latest.json
```

缺失文档清理预览：

```powershell
python scripts/kb/cleanup_missing_docs.py --all-scenarios
```

如果报告确认无误，再显式执行：

```powershell
python scripts/kb/cleanup_missing_docs.py --all-scenarios --apply
```

Bad Case 反馈闭环默认走本地文件：

```powershell
python scripts/evaluate_core_chain.py --dataset eval_sets/multi_scenario_smoke.json --limit 20 --output reports/evaluation/core_chain_latest.json
python scripts/extract_bad_cases_from_report.py --report reports/evaluation/core_chain_latest.json --output eval_sets/local_bad_cases.json
python scripts/evaluate_core_chain.py --dataset eval_sets/local_bad_cases.json --output reports/evaluation/local_bad_cases_latest.json
python scripts/quality/check_evaluation_gate.py --report reports/evaluation/local_bad_cases_latest.json
```

这条链路对应：本地评测报告发现问题，`extract_bad_cases_from_report.py` 筛出失败样本，人工复核 `expected_*` 字段后沉淀到 `eval_sets/`，最后由 Evaluation 和 Gate 重新验证。LangSmith 可以作为企业扩展承接 Trace 可视化、多人标注和实验对比，但不是本地验收的前置条件。

本地通电诊断：

```powershell
python scripts/tools/check_local_runtime.py --require-api --output reports/verification/local_runtime_latest.json
```

这份诊断报告现在不只会告诉你“端口不通”，还会额外说明三件事：

- 当前 `.env` 是否符合“本机 API + localhost 端口”模式；
- `docker-compose.yml` 暴露了哪些宿主机端口；
- `docker ps` 里是否已经有相关容器存在，但没有把 MySQL / Milvus / API 端口映射到宿主机。

如果 `.env` 使用 `mysql`、`milvus` 和 `/app/models/...`，通常说明把 Compose 配置复制到了本机
API 调试配置里。宿主机直接跑诊断时，脚本会把这些容器内视角的端口和路径降级为提示项，避免把
“运行模式不同”误判成项目不可用。全 Docker 模式请检查 `.env.compose`，并优先在 API 容器内执行验收命令。

例如标准 `docker-compose.yml` 默认把 MySQL 暴露到 `3306`。如果本机 `.env` 写了其他端口，
诊断报告会明确指出本机配置与容器端口不一致，而不是只给出一个抽象的“连接失败”。

企业资料真实度分析：

```powershell
python scripts/enterprise_overlay/analyze_enterprise_data_realism.py --output reports/verification/enterprise_data_realism_latest.json
```

当前 `scenarios/` 是可控样例资料。企业仿真数据包位于 `data_packs/enterprise_realistic_pack/`，
其中 `clean_overlay/` 可用于后续入库增强，`dirty_samples/` 只用于资料治理演示，不默认进入
active 知识库版本。详细说明见 [enterprise_data_realism.md](docs/enterprise_data_realism.md)。

clean overlay 预检：

```powershell
python scripts/enterprise_overlay/build_enterprise_overlay_dataset.py --all-scenarios --output reports/verification/enterprise_overlay_build_latest.json
```

这会在 `reports/enterprise_overlay_build/` 下生成临时增强数据集，并复用入库质量报告和入库质量检查。它只验证“增强资料是否具备进入知识库版本重建的资格”，不会修改当前 active 知识库。

dirty samples 治理分析：

```powershell
python scripts/enterprise_overlay/analyze_dirty_enterprise_samples.py --output reports/verification/dirty_enterprise_samples_latest.json
```

它会识别过期口径、FAQ/正文冲突风险、OCR 噪声和表格专用切分需求，并明确这些样本默认不允许 active 入库。

企业 overlay 就绪检查：

```powershell
python scripts/enterprise_overlay/check_enterprise_overlay_readiness.py --output reports/verification/enterprise_overlay_readiness_latest.json
```

它会确认 clean overlay 预检、dirty samples 阻断、资料真实度提升和 overlay 回归评测集覆盖都满足要求。

生成 overlay 上线计划：

```powershell
python scripts/enterprise_overlay/plan_enterprise_overlay_activation.py --output reports/verification/enterprise_overlay_activation_plan_latest.json
```

计划文件只生成 `rebuild_kb_version.py` 命令。需要正式执行计划时，运行：

```powershell
python scripts/enterprise_overlay/run_enterprise_overlay_activation.py --plan reports/verification/enterprise_overlay_activation_plan_latest.json --output reports/verification/enterprise_overlay_activation_run_latest.json
```

增强资料真正激活后，再跑：

```powershell
python scripts/quality/check_evaluation_gate.py --dataset eval_sets/enterprise_overlay_regression.json --limit 24 --output reports/verification/enterprise_overlay_evaluation_latest.json --gate-output reports/verification/enterprise_overlay_evaluation_gate_latest.json --min-source-inference-accuracy 1.0 --min-prompt-profile-accuracy 0.85
```

这条 overlay 回归作为独立质量检查保留，适合临时排查或资料增强后快速复测。

该报告现在会优先读取最新 live 验收产物，而不是旧的静态报告快照，重点汇总：

- 最新业务深度评测；
- 最新多轮追问评测；
- 最新性能回归结果；
- 最新企业资料真实度、clean overlay 预检和 dirty samples 治理摘要；
- 当前 bad case 复核分层；
- 当前本地通电状态。

这轮又补了两类状态页筛选能力：

- 时间窗口：最近 `30m / 6h / 24h / 7d / 全部时间`
- 定位维度：按 `closure_bucket / session_id / trace_id` 聚焦 bad case 和 trace

现在状态页不只是“看报表”，而是可以直接回答：

- 这次新增问题是最近 24 小时出现的，还是旧历史遗留；
- 某次验收会话里到底是哪条 trace 开始回答变差；
- 这是边界拦截本来就对，还是知识覆盖真的缺了。

V1 当前 `/admin` 的定位是“基础治理工作台”：

- 直接查看并操作 `ACTIVE / STAGED / ARCHIVED` 版本；
- 查看入库质量报告详情；
- 查看 gate / performance / governance 报告详情；
- 查看最近低质量反馈（Bad Case 入口）；
- LangSmith 可选承担 Trace 详情、协作标注和实验对比，本地 Evaluation/Gate 仍是确定性验收入口。

如果前端改动后页面看起来没有更新，先确认运行机器上的 `static/index.html` 和
`static/js/render.js` 是否已经同步到最新，再重启 API 服务。静态资源版本号可以帮助浏览器失效缓存，
但前提仍然是运行目录里的文件已经更新。

## 9. 当前验证结果

最近一次业务深度回归：

```text
reports/evaluation/business_depth_regression_live_32.json
```

关键指标：

```text
total = 32
errors = 0
recall_at_k = 1.0
mrr = 1.0
hit_type_accuracy = 1.0
source_inference_accuracy = 1.0
prompt_profile_accuracy = 1.0
faq_direct_accuracy = 1.0
scenario_isolation_accuracy = 1.0
avg_keyword_coverage = 0.9922
```

项目守护检查已覆盖：

- 禁止恢复旧版 `mysql_qa` / `rag_qa` 主链路；
- 禁止新增第 9 个场景包；
- 禁止 fallback 导入和技术降级路径；
- 检查依赖版本固定、导入位置和密钥卫生。

## 10. 推荐演示问题

| 场景 | 问题 |
| --- | --- |
| 企业知识库 | 没有预算审批可以先采购再报销吗？ |
| SaaS 客服 | 客户要求退款或赠送额度时能直接答应吗？ |
| 设备运维 | 同一设备反复温度告警要怎么处理？ |
| 合规风控 | 批量导出客户数据需要哪些审批？ |
| 跨境贸易 | HS 编码归类存在争议时能先按客户说法申报吗？ |
| 招投标合同 | 客户只口头确认验收可以申请回款吗？ |
| 保险理赔 | 收款账户和被保险人不一致可以打款吗？ |
| 工程项目 | 安全技术交底只有口头说明可以吗？ |

演示时建议打开 `/admin`，观察命中的 `scenario_id`、`source_filter`、`kb_version`、`prompt_profile`、来源引用和阶段耗时。

## 11. 文档导航

| 文档 | 用途 |
| --- | --- |
| `docs/index.md` | 20 讲系统课程首页、学习优先级和二期规划 |
| `docs/course-outline.md` | 课程大纲、学习路线和 P3 扩展方向 |
| `docs/01-project-overview.md` | 项目概述、环境搭建和生产部署说明 |
| `docs/16-ingestion-pipeline.md` | 文档入库、FAQ 入库和 IndexManifest 增量机制 |
| `docs/17-quality-evaluation.md` | RAG 回归验收、入库质量检查和 Bad Case 沉淀 |
| `docs/19-observability-tracing.md` | LangSmith Trace、阶段耗时诊断和观测闭环 |
| `docs/20-docker-containerization.md` | Docker 容器化部署、交付验收和排障闭环 |
| `docs/appendix/` | 8 个技术附录 |

## 12. 二期方向

一期只做 RAG，并且已经闭环：

- 知识库构建；
- 多场景检索；
- FAQ + 文档混合；
- 多版本；
- 数据隔离；
- 流式问答；
- 入库质量检查；
- 评测回归。

后续增强层不抢当前主线：

- 多模态入库：复杂 PDF、扫描件、图纸、票据、验收照片，先解析、复核、质检，再版本化入库；
- GraphRAG：只用于合同、理赔、工程规范这类关系链明显的问题，不替代当前 Milvus Hybrid RAG；
- 模型升级实验：在 `bge-m3` 基线稳定后，再评估 Qwen3-Embedding 等新模型。

## 13. 安全说明

- `.env`、`.env.compose` 不提交真实 Key；
- `.env.local.example`、`.env.compose.example` 只保留占位符；
- `logs/`、`reports/` 默认不作为线上公开材料；
- 当前项目不提供技术降级方案，Milvus、MySQL、本地模型、LLM Key 和 active 知识库版本都是启动前置条件。
