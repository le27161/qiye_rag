# 企业多场景 RAG 知识问答平台

基于 **FastAPI、LangChain 和 Milvus Hybrid Search** 的知识问答项目，覆盖文档入库、FAQ 与文档检索、重排序、流式回答、知识库版本管理和质量回归。

## 主要功能

- **混合检索**：本地 BGE-M3 稠密向量与 Milvus 内置 BM25 组合召回，通过 BGE Reranker 重排序。
- **FAQ 与文档分层**：高置信 FAQ 返回标准答案，其余问题进入文档检索与生成链路。
- **多格式入库**：Markdown、TXT、PDF、DOCX、PPTX、CSV 和 Excel；表格保留工作表、行号与字段信息。扫描件提供独立 OCR 处理流程。
- **多场景配置**：使用场景配置、FAQ 和资料目录管理业务数据，并提供意图判断、source 推断及 Prompt Profile 路由。
- **知识库版本**：支持构建、质量门禁、激活、归档，以及基于文件指纹和 chunk 有效期的增量更新。
- **数据范围过滤**：围绕 tenant、dataset、visibility 和角色元数据组织检索过滤；生产环境仍需接入可信身份与授权体系。
- **问答与治理页面**：原生静态前端、WebSocket 流式回答、会话历史、反馈和基础管理页面。
- **质量回归**：提供检索评测、接口冒烟、Bad Case 提取、质量门禁与可选 LangSmith 观测脚本。

## 系统结构

在线问答与离线入库分别组织：

```text
在线：问题 → 场景与数据范围 → 意图 / 查询处理
          → FAQ / 文档混合检索 → 重排序 → 上下文与提示词
          → LLM 流式回答 → 来源引用 / 会话历史 / 反馈

离线：FAQ / 文档 → 解析与标准化 → 切块与向量化
                → Milvus 写入 → 质量报告 → 知识库版本激活
```

FastAPI 提供页面和接口；Milvus 存储检索数据；MySQL 保存会话、反馈、版本及入库元数据；Redis 用于缓存；模型调用默认使用 DashScope 的 OpenAI 兼容接口。

## 内置场景

| 场景 ID | 资料主题 |
| --- | --- |
| `enterprise_knowledge` | HR、IT、财务制度 |
| `saas_support` | 账号、计费、开放集成 |
| `equipment_ops` | 巡检、告警、安全规范 |
| `compliance_qa` | 合同、审计、隐私保护 |
| `cross_border_risk` | 海关、制裁、信用证、物流、单证 |
| `tender_contract_risk` | 招投标、合同、交付、验收 |
| `insurance_claims` | 保单、理赔材料、责任与赔付 |
| `engineering_project_qa` | 图纸、规范、进度、质量与安全 |

场景资料用于功能演示与回归验证，不应直接作为真实业务的合规、理赔或安全决策依据。

## 快速开始

完整步骤见 [部署指南](INSTALL.md)。以下为 Docker Compose 首次部署的主要流程，命令在仓库根目录执行。

### 1. 获取源码

```sh
git clone https://github.com/le27161/qiye_rag.git
cd qiye_rag
```

### 2. 准备配置和模型

PowerShell：

```powershell
if (!(Test-Path .env.compose)) { Copy-Item .env.compose.example .env.compose }
notepad .env.compose
New-Item -ItemType Directory -Force -Path models,logs,reports,site | Out-Null
```

填写 `DASHSCOPE_API_KEY`、`ADMIN_API_TOKEN`，核对端口及模型路径。准备以下模型目录：

```text
models/
  bge-m3/
  bge-reranker-large/
  bert_intent_classifier_v1/
```

模型权重不随仓库分发。意图分类目录需要包含与项目匹配的已训练模型，不能仅用基础 BERT 权重代替。模型尚未准备好时，服务不能完整启动。

### 3. 构建并初始化

```sh
docker build -f Dockerfile.base -t localhost/knowforge-rag-platform-base:py312 .
docker compose --env-file .env.compose build api
docker compose --env-file .env.compose up -d mysql redis etcd minio milvus
```

等待基础服务健康就绪后，为默认场景构建并激活知识库：

```sh
docker compose --env-file .env.compose run --rm api python scripts/rebuild_kb_version.py --scenario enterprise_knowledge --new-version --quality-gate --activate --description "initial knowledge base"
docker compose --env-file .env.compose up -d api
docker compose --env-file .env.compose ps
```

启动前请先按部署指南创建挂载目录。其他场景需要分别初始化，不能只切换配置后直接使用空知识库。初始化命令会调用本地模型和外部依赖，首次执行可能较慢。

### 4. 访问服务

默认 API 端口为 `8000`：

- 问答页面：<http://localhost:8000/>
- 管理页面：<http://localhost:8000/admin>
- 健康状态：<http://localhost:8000/health>
- API 文档：<http://localhost:8000/api/docs>

`/docs` 是额外文档站点入口，不是 Swagger。当前仓库未包含构建该站点所需的完整文档源码，不将它作为启动或使用入口。

## 目录说明

```text
app.py             FastAPI 服务入口
qa_core/           API、编排、检索、入库、版本与存储模块
config/            规则配置
scenarios/         业务场景、FAQ 与文档资料
eval_sets/         回归评测样本
data_packs/        企业仿真与资料治理样本
static/            问答和管理页面
scripts/           入库、评测、部署与诊断脚本
tests/             自动化测试
mini-rag/          精简 RAG 子项目
resume_templates/  项目介绍材料
```

`models/`、`.env`、`.env.compose`、`logs/`、`reports/`、生成站点及本地压缩包均不提交到 Git。

## 配置模式

| 模式 | 配置模板 | 实际配置 | 依赖地址 |
| --- | --- | --- | --- |
| Docker Compose | `.env.compose.example` | `.env.compose` | Compose 服务名，如 `mysql`、`milvus` |
| 本机 Python | `.env.local.example` | `.env` | 本机地址和宿主机映射端口 |

本机调试使用 Python 3.12，在独立虚拟环境中安装 [requirements.txt](requirements.txt)。不要将两种模式的数据库地址、端口和模型路径混用。

## 测试与评测

安装依赖后，可在配置好的测试环境中运行：

```sh
python scripts/check_project_guardrails.py
python -m pytest
```

部分检查和测试依赖模型、数据库或其他项目资料，不保证仅克隆源码即可全部通过。

在模型、数据库与知识库版本就绪后执行检索回归：

```sh
python scripts/evaluate_core_chain.py --dataset eval_sets/multi_scenario_smoke.json --limit 20 --output reports/evaluation/core_chain_latest.json
python scripts/quality/check_evaluation_gate.py --report reports/evaluation/core_chain_latest.json
```

评测会访问真实依赖，可能产生模型服务费用。结果应连同数据集、模型版本、知识库版本和运行环境一起复核；本仓库不以未附完整实验条件的历史分数作为效果承诺。

## 安全与使用边界

- 当前 Compose 含有演示数据库与对象存储凭据，并映射基础服务端口。不要直接暴露到公网；生产部署前应修改服务端与客户端凭据、限制网络访问并配置 HTTPS、认证和审计。
- `.env` 中的管理令牌与模型密钥不能提交。LangSmith 等外部服务可能接收问题、上下文和 Trace，启用前应评估数据处理范围。
- Prompt 和元数据过滤不替代服务端授权；涉及个人或企业资料时，应先完成授权、脱敏和访问控制。
- `--reset-collections` 会删除并重建向量集合，不作为日常更新或排错的默认选项；已有数据环境先备份。
- 项目保留 KnowForge 名称与现有第三方代码标识。公开仓库不等于获得任意再分发授权；依赖、模型和资料应分别核对许可。本仓库暂未提供统一的开源许可证声明。

更多操作说明见 [部署指南](INSTALL.md)、[版本维护说明](VERSIONING.md) 和 [企业仿真数据包](data_packs/enterprise_realistic_pack/README.md)。
