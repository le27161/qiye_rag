# Codex 提示词：Vibe Coding 实践版简易混合检索 RAG

本文件是第二阶段实践单元配套的唯一提示词文件。实践目标是使用 Codex 完成一个简易但真实可运行的 RAG，核心链路为：

```text
文档入库
→ Dense + BM25 混合检索
→ BGE Reranker 精排
→ LLM 生成答案
```

本实训不展开意图识别、Redis、质量门禁、多租户和 Trace。每一轮只完成一个阶段，并在进入下一轮前查看 diff、运行测试和记录结果。

## 使用规则

每次执行提示词前：

1. 确认当前工作目录；
2. 查看 `git diff`；
3. 确认上一阶段测试结果；
4. 只让 Codex 完成当前阶段；
5. 修改后重新查看 diff 和测试结果；
6. 记录修改文件、运行命令和验收结果。

## 1. 项目分析：只规划，不改文件

```text
请先阅读当前项目，不要修改任何文件。

我要完成一个简易但真实可运行的 RAG：
- 使用 FastAPI 提供 GET /、GET /health、POST /ask；
- 使用 Milvus 2.5+ 保存 text、dense、sparse；
- Dense 使用本地 BGE-M3；
- Sparse 使用 Milvus 服务端 BM25BuiltInFunction；
- Dense 索引使用 HNSW；
- Sparse 索引使用 AUTOINDEX + BM25；
- 使用 Weighted Hybrid Search 融合两路召回；
- 使用本地 BGE Reranker 对候选结果精排；
- 使用 OpenAI 兼容接口调用 LLM；
- 返回 answer、sources、route、retrieval 和 timings；
- 使用 Docker Compose 启动 MySQL、etcd、MinIO、Milvus 和 API。

请输出：
1. 当前项目已有的相关文件；
2. 每个文件的职责；
3. 离线入库顺序；
4. 在线问答顺序；
5. 需要修改的文件；
6. 分阶段实施计划；
7. 每阶段的测试计划。

暂时不要生成大段代码，也不要修改文件。
```

## 2. 项目骨架和配置

```text
请根据已经确认的方案，只完成项目骨架和配置。

要求：
- 保留清晰的 app.py、qa_core、scripts、static、tests 目录；
- 配置从 .env 读取，不把 API Key 写死；
- 先提供 GET /health；
- 为配置解析和健康检查添加纯逻辑测试；
- 不实现混合检索、Reranker 和 LLM；
- 不修改与本阶段无关的文件。

完成后只报告：修改文件、运行命令、测试结果和未完成内容。
```

## 3. 文档加载、切分和入库

```text
请只实现离线入库流程。

要求：
- 读取 FAQ CSV 和业务文档；
- 支持 Markdown、TXT、PDF、DOCX、PPTX、CSV、XLSX；
- FAQ 转换为包含 question、answer、source 的 Document；
- 文档使用 RecursiveCharacterTextSplitter 切分；
- 写入 FAQ Collection 和 Document Collection；
- Milvus 记录必须包含 text、dense、sparse；
- Dense 使用本地 BGE-M3；
- Sparse 使用 Milvus 2.5+ BM25BuiltInFunction；
- Dense 索引使用 HNSW；
- Sparse 索引使用 AUTOINDEX + BM25；
- 为记录增加 source 和 kb_version 元数据；
- 创建并激活本次知识库版本；
- 添加不依赖真实服务的入库元数据和索引参数测试。

先阅读相关代码并列出修改文件，再开始修改。
```

## 4. Dense + BM25 混合检索

```text
请在现有入库代码基础上，只实现在线混合检索。

要求：
- 接收 query 和 top_k；
- 同时执行 Dense 检索和 BM25 检索；
- 使用 Weighted Hybrid Search 融合结果；
- 保留原文、source 和分数；
- 对重复 chunk 去重；
- 返回文档、分数和耗时；
- 不加入 Reranker，不加入 LLM，不修改 API 页面；
- 添加不依赖真实 Milvus 的参数和纯函数测试。

请说明：
1. Dense 和 Sparse 分别解决什么问题；
2. Weighted 融合发生在哪里；
3. 为什么不能直接比较两路未经处理的原始分数；
4. 如何验证检索结果确实来自知识库。
```

## 5. BGE Reranker 精排

```text
请在混合检索之后加入 BGE Reranker，不要修改 Milvus 的索引和召回逻辑。

执行顺序必须是：
混合检索召回候选
→ 构造 (query, document) 对
→ CrossEncoder 批量打分
→ 按 Reranker 分数降序排列
→ 截取 top_n

要求：
- 使用本地 BGE Reranker 模型；
- 模型只在在线检索阶段加载，不参与入库；
- 保留原文和 source；
- 候选为空时直接返回空结果，不调用模型；
- 添加纯函数测试，验证排序和 top_n 截断；
- 记录 Reranker 阶段耗时。

完成后解释：
- Embedding 和 Reranker 的输入有什么区别；
- 为什么 Reranker 不能替代 Milvus 召回；
- 为什么不能把所有文档都交给 Reranker。
```

## 6. LLM 和问答接口

```text
请把已经完成的混合检索和 Reranker 接到 POST /ask。

要求：
- 接收 query、history 和 source_filter；
- 执行混合检索，再执行 Reranker；
- 只把最终排序后的上下文交给 LLM；
- Prompt 要求答案只能依据上下文；
- 没有相关资料时明确说明资料不足；
- 返回 answer、sources、route、retrieval、timings；
- API Key 只从环境变量读取；
- 不缓存最终 LLM 答案。

请检查调用顺序是否为：
app.py → pipeline.ask() → retrieval.search_many()
→ rerank() → select_context_docs() → generate_answer()
```

## 7. 页面、测试和 Docker

```text
请补齐页面、测试和 Docker 运行说明。

要求：
- 页面展示问题、答案、来源、检索诊断和耗时；
- 测试覆盖健康检查、空问题、检索结果、Reranker 排序和响应结构；
- Docker Compose 启动 MySQL、etcd、MinIO、Milvus 和 API；
- API 通过服务名访问依赖；
- 本地模型通过 volume 挂载到 /app/models；
- API Key 不写进 Dockerfile 或 compose 文件；
- 运行 docker compose config；
- README 写清启动、入库、提问、测试和常见报错。

不要增加意图识别、Redis、Agent、GraphRAG、WebSocket 或管理后台。
```

## 8. 调试提示词

```text
请先阅读当前项目中与报错相关的代码，再定位根因，不要重写整个项目。

当前目录：
...

执行命令：
...

期望行为：
...

完整报错：
...

请按以下顺序回答：
1. 根因；
2. 涉及文件和函数；
3. 最小修改方案；
4. 修改后执行的验证命令；
5. 仍可能存在的风险。

只修改解决当前问题所必需的文件。
```
