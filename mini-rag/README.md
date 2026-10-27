# Mini RAG

Mini RAG 是第二阶段实践单元的独立项目：在第 04 讲学习 Milvus 索引机制之后，使用 Codex 完成一条简易但真实可运行的 RAG 闭环。

它不是 mock demo。它保留真实的 Milvus、BGE-M3、BGE Reranker、MySQL 和 LLM 组件，但暂不引入完整企业级治理能力。

## 保留的主链路

```text
用户问题
  -> FAQ / 文档混合检索
  -> BGE Reranker 精排
  -> 选择上下文
  -> LLM 生成
  -> answer + sources
```

## 技术边界

| 能力 | Mini RAG 实现 |
| --- | --- |
| API | FastAPI `GET /`、`GET /health`、`POST /ask` |
| 资料存放 | `scenarios/enterprise_knowledge/` 中的 FAQ 和业务文档 |
| Dense 检索 | 本地 BGE-M3 + Milvus HNSW |
| Sparse 检索 | Milvus 2.5+ 服务端 BM25 |
| 混合检索 | Weighted Hybrid Search |
| 精排 | 本地 BGE Reranker Large CrossEncoder |
| 生成 | OpenAI 兼容接口，默认 DashScope |

## 不放进 Mini RAG 的内容

- 8 个业务场景切换
- 完整意图识别模型和网关仲裁
- Redis 检索缓存
- 多租户管理页面
- 入库质量门禁和评测体系
- WebSocket 流式输出
- LangSmith Trace
- GraphRAG、复杂任务编排、LlamaIndex

这些能力放在完整企业级项目中讲。本目录保留一套边界清晰的真实实现，适合跟随第二阶段实践单元逐阶段阅读、运行和修改。

## 目录结构

```text
mini-rag/
  app.py
  qa_core/
    config.py
    ingest.py
    kb_version.py
    loaders.py
    models.py
    pipeline.py
    prompts.py
    query.py
    retrieval.py
    schemas.py
    table_loader.py
  scripts/
    rebuild.py
    ask.py
  scenarios/enterprise_knowledge/
  static/
  tests/
  prompts/vibe-coding-lab.md
  Dockerfile
  docker-compose.yml
  requirements.txt
  .env.example
```

## 本机运行

当前 `mini-rag/` 目录就是第二阶段实践单元的参考实现。请在 Codex 中打开项目工作区，使用 `prompts/vibe-coding-lab.md`，先让 Codex 分析目录，再按阶段阅读和修改，不要一次性重写整个项目。

先启动基础设施。如果你在完整仓库里使用 Mini RAG，可以复用上层 Compose：

```powershell
cd D:\workspace\knowforge-rag-platform
docker compose --env-file .env.compose up -d mysql etcd minio milvus
```

再准备 Mini RAG 配置：

```powershell
cd D:\workspace\knowforge-rag-platform\mini-rag
copy .env.example .env
```

编辑 `mini-rag/.env`，至少确认：

```env
DASHSCOPE_API_KEY=你的Key
EMBEDDING_MODEL_PATH=../models/bge-m3
RERANKER_MODEL_PATH=../models/bge-reranker-large
MILVUS_URI=http://127.0.0.1:19530
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
```

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

重建知识库：

```powershell
python scripts\rebuild.py --reset-collections --description "mini rag init"
```

启动 API：

```powershell
python -m uvicorn app:app --host 127.0.0.1 --port 8010
```

打开：

```text
http://127.0.0.1:8010/
```

## Docker 独立运行

如果只想启动 Mini RAG 自己的一套容器：

```powershell
cd D:\workspace\knowforge-rag-platform\mini-rag
copy .env.example .env
```

编辑 `.env`：

```env
DASHSCOPE_API_KEY=你的Key
MINI_RAG_MODELS_DIR=../models
```

启动：

```powershell
docker compose up -d --build
```

入库：

```powershell
docker compose exec api python scripts/rebuild.py --reset-collections --description "mini rag init"
```

访问：

```text
http://127.0.0.1:8010/
```

## 命令行提问

```powershell
python scripts\ask.py "新人入职需要完成哪些流程？"
python scripts\ask.py "VPN 连不上怎么处理？" --source-filter it
python scripts\ask.py "那审批呢" --history "报销流程是什么"
```

## 测试

这些测试不连接真实 Milvus/MySQL，只检查纯逻辑和配置口径：

```powershell
python -m pytest tests -q
```

重点保护：

- 场景资料存在
- FAQ 入库元数据完整
- active 版本 ID 格式正确
- Milvus 过滤表达式包含版本、权限和 source 边界
- 查询变体生成正确
- HNSW + BM25 索引参数正确
- Reranker 空候选跳过、排序和 top_n 截断正确
- `/ask` 直接回答路径返回稳定响应结构

## 诊断字段

`POST /ask` 会在 `retrieval` 中返回关键诊断字段：

- `faq_hits` / `doc_hits`：FAQ 和文档命中数量
- `faq_top_score` / `doc_top_score`：两路最高分
- `faq_elapsed_ms` / `doc_elapsed_ms`：FAQ 和文档检索总耗时
- `faq_rerank_ms` / `doc_rerank_ms`：Reranker 精排耗时
- `retrieval.timings.total_ms`：整条问答链路总耗时

## 提示词模板与实训材料

本实践单元只保留一份 Codex 提示词：

```text
mini-rag/prompts/vibe-coding-lab.md
```

- `vibe-coding-lab.md`：Codex 专用的分阶段提示词，包含方案分析、入库、混合检索、Reranker、生成、测试和调试。

先使用这份提示词完成小步闭环，再阅读项目代码，理解如何把一份复杂需求拆成可验证的实现阶段。
