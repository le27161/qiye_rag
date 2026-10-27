# 简历模板一：全栈 RAG 平台开发工程师

## 项目名称

**KnowForge 企业级多场景 RAG 知识问答平台**

## 项目周期

20XX.XX - 20XX.XX（按实际经历填写）

## 项目背景

KnowForge 是一个面向企业内部知识服务的多场景 RAG 平台，用于解决制度、运维、合规、跨境风控、招投标合同、保险理赔、工程资料、SaaS 客服等场景下的知识问答问题。系统采用 FAQ 高置信直出与文档 RAG 生成并行的架构，支持多场景配置、Milvus 混合检索、知识库多版本管理、数据隔离、流式问答、入库质量门禁、回归评测和 LangSmith 可观测性闭环。

## 技术栈

| 类别 | 技术选型 |
|---|---|
| Web 服务 | FastAPI、WebSocket、静态资源路由 |
| RAG 编排 | LangChain、LangChain Milvus、LangChain OpenAI 兼容接口 |
| LLM | DashScope / OpenAI 兼容模型服务 |
| 向量模型 | BGE-M3，本地 sentence-transformers 推理 |
| 重排序 | BGE-Reranker-Large，CrossEncoder 二阶段重排 |
| 检索存储 | Milvus 2.5，Dense Vector + BM25BuiltInFunction Hybrid Search |
| 元数据存储 | MySQL 8，SQLAlchemy / PyMySQL |
| 文档入库 | PyMuPDF、python-docx、python-pptx、openpyxl、CSV/Markdown Loader、PaddleOCR 离线处理 |
| 质量评测 | Recall@K、MRR、关键词覆盖率、命中路径、Prompt Profile、多场景隔离、RAGAS 补充评测 |
| 可观测性 | LangSmith Trace、Dataset、Annotation、Experiment |
| 部署 | Docker Compose，MySQL + etcd + MinIO + Milvus + API |

## 核心功能

1. **多场景配置化问答**：通过 `scenario.toml` 管理 8 个业务场景的名称、业务域、collection、source 白名单和提示词上下文。
2. **完整 RAG Pipeline**：请求上下文创建、意图识别、检索计划、查询改写、FAQ/Doc 检索、上下文构建、Prompt 选择、LLM 流式生成、历史写入。
3. **FAQ + 文档双通道检索**：FAQ 用于高置信标准答案直出，文档检索用于复杂问题和信息补充，避免把所有问题都交给 LLM 生成。
4. **Milvus 混合检索**：基于 BGE-M3 稠密向量和 Milvus BM25 内置稀疏检索，使用 weighted ranker 融合后再用 CrossEncoder 重排。
5. **检索策略动态规划**：根据 FAQ、知识查询、追问、费用、合规、排障、表格等问题类型动态调整 `top_k`、直出阈值、是否启用查询变体和上下文数量。
6. **多轮追问处理**：结合历史消息进行查询改写，支持“那审批呢”“材料呢”等追问类问题的上下文补全。
7. **Prompt Profile 选择**：按意图、问题类别和业务场景选择回答模板，控制费用、合规、排障、总结等问题的输出口径。
8. **知识库版本管理**：通过 MySQL 维护 `kb_versions` 和 `kb_active_versions`，每个版本分配单调 `version_seq`。文档检索按 `valid_from_seq <= active_seq AND valid_to_seq = 0 OR > active_seq` 有效期窗口过滤，FAQ 按 `kb_version` 精确匹配快照。支持候选版本构建、7 步事务激活和 O(1) 回滚。
9. **DataScope 数据隔离**：在入库和检索时注入 tenant、dataset、visibility、allowed_roles 等元数据，统一生成 Milvus 过滤表达式。
10. **入库质量门禁**：检查解析失败、空文件、低质量 chunk、重复 FAQ、非法 source、FAQ 与文档冲突等问题。门禁分两组：11 个数量阈值类（默认全 0，OCR 风险写死 0 不允许放宽）+ 4 个存在性必填类。未通过时 `sys.exit(1)` 阻断激活。
11. **回归评测体系**：覆盖多场景冒烟、业务深度、追问、边界、表格和性能基线等评测集，发布前执行确定性 Gate。
12. **LangSmith 可观测性闭环**：记录 Trace metadata、检索诊断和阶段耗时，把 Bad Case 标注为 Dataset 后用于 Experiment 对比。

## 个人职责

- 负责 RAG 主链路设计与实现，拆分请求上下文、路由、检索、上下文、Prompt、生成、历史写入等阶段，保证主流程可观测、可测试、可扩展。
- 设计并实现 `QAService` / Pipeline 编排层，统一管理意图识别、检索策略、查询改写、FAQ/Doc 检索、上下文构建和流式生成。
- 基于 Milvus 2.5 搭建 Dense + BM25 Hybrid Search 检索链路，封装 `MilvusHybridStore.search/search_many`，支持多变体检索、合并去重和 CrossEncoder 重排。
- 实现多场景 registry 和 `scenario.toml` 配置体系，支持场景级 collection、source 白名单、Prompt 上下文和业务信息隔离。
- 实现 WebSocket 流式输出协议，按 start/status/token/end/error 等事件返回答案、引用来源、诊断信息和耗时指标。
- 设计知识库版本控制面，将 active 版本指针迁移到 MySQL，保证线上查询通过 `kb_version` 过滤命中当前生效版本。
- 完成多格式入库链路，支持 Markdown、PDF、DOCX、PPTX、XLSX、CSV，并对表格行和 OCR 后文本接入统一入库流程。
- 接入 LangSmith Trace，记录 `scenario_id`、`kb_version`、`hit_type`、`sources_count`、`prompt_profile` 和阶段耗时，支撑 Bad Case 回归闭环。
- 编写 Docker Compose 部署配置和运行检查脚本，支持本地与容器环境快速启动和健康检查。

## 项目成果

- 交付了覆盖 8 个业务场景的 RAG 问答平台，实现 FAQ 直出、文档 RAG、多轮追问、引用溯源和流式输出的完整闭环。
- 将 FAQ 标准答案和文档知识库分开治理，高置信 FAQ 走低延迟直出，复杂问题进入 RAG 生成，降低无依据生成风险。
- 通过 Dense + BM25 混合检索和 CrossEncoder 重排提升召回覆盖与排序稳定性，具体指标可在简历中替换为实际评测结果：`Recall@K=[填写]`、`MRR=[填写]`。
- 建立 MySQL 知识库版本控制面，候选版本通过质量门禁后再切换 active 指针，避免失败入库污染线上检索。
- 建立入库质量、主链路评测、追问评测和性能基线门禁，支持版本变更前的自动化回归验证。
- 通过 LangSmith Trace 与 Dataset/Experiment 机制沉淀 Bad Case，使线上问题可以被复现、标注和回归验证。

## 简历使用建议

- 成果指标建议替换成自己实际跑出的报告数据，例如评测样本数、Recall@K、MRR、错误率、P50/P95 耗时、覆盖场景数量。
