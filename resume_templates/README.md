# KnowForge 项目简历模板索引

本目录提供 5 个岗位方向的 KnowForge 项目简历模板。模板已经按当前项目真实实现做过校准：突出多场景 RAG、Milvus Hybrid Search、知识库版本治理、DataScope、质量门禁和 LangSmith 闭环，同时避免写入无法被项目证明的夸大指标。

## 模板列表

| 编号 | 岗位方向 | 适用方向 | 重点能力 |
|---|---|---|---|
| [01](./01-全栈RAG平台开发工程师.md) | 全栈 RAG 平台开发工程师 | 后端 / 全栈 / RAG 应用开发 | FastAPI、WebSocket、RAG Pipeline、Milvus、知识库版本、前端问答页 |
| [02](./02-AI检索算法工程师.md) | AI 检索 / RAG 算法工程师 | 检索 / 推荐 / RAG 算法 | Dense + BM25 Hybrid Search、BGE-M3、Reranker、RetrievalPlan、Recall@K、MRR |
| [03](./03-后端开发与数据治理工程师.md) | 后端开发与知识库数据治理工程师 | 后端 / 数据平台 / 知识库治理 | 文档解析、IndexManifest、MySQL 版本控制面、DataScope、入库质量门禁 |
| [04](./04-质量评测与可观测性工程师.md) | RAG 质量评测与可观测性工程师 | 测试开发 / 质量工程 / 可观测性 | 评测门禁、入库质量、追问评测、性能基线、LangSmith、RAGAS 补充评测 |
| [05](./05-技术架构师与项目负责人.md) | 技术架构师 / 项目负责人 | 架构设计 / Tech Lead / 项目交付 | 架构分层、多场景平台化、版本治理、质量体系、交付边界 |

## 使用原则

1. **按真实经历裁剪**：没有参与的模块不要写进“个人职责”，可以保留在“项目功能”中作为团队或项目能力。
2. **指标不要虚构**：模板中的 `[填写]` 位置应替换为实际评测报告数据，例如 Recall@K、MRR、评测样本数、P95 耗时、chunk 数。
3. **区分主门禁和补充评测**：本项目主评测是工程回归指标，RAGAS 是语义质量补充分析，不要写反。
4. **知识库版本表述要准确**：当前项目使用 MySQL active 指针 + Milvus `kb_version` 过滤，不是 Milvus Alias 原子切换。
5. **检索实现要准确**：当前项目使用 Milvus `BM25BuiltInFunction` 和 weighted ranker，不是本地自研 BM25，也不是 RRF。
6. **成果口径要稳**：没有真实生产数据时，使用“建立评测体系”“支持版本门禁”“完成闭环”比直接写“准确率 XX%”“延迟毫秒级”更可信。

## 项目通用一句话

> KnowForge 是基于 FastAPI + LangChain + Milvus Hybrid Search + MySQL 的企业级多场景 RAG 知识问答平台，支持 FAQ 直出、文档 RAG、多轮追问、知识库多版本治理、DataScope 数据隔离、质量门禁、LangSmith 可观测性和 Docker Compose 部署。

## 推荐简历表达方式

可以把项目成果写成下面这种可证明口径：

```text
负责 KnowForge 多场景 RAG 平台核心链路建设，基于 Milvus 2.5 Dense + BM25 Hybrid Search 和 BGE-Reranker 实现 FAQ/文档双通道检索；通过 MySQL 管理知识库 active 版本指针，配合 kb_version 过滤实现候选版本构建、质量门禁和线上版本切换；建立 Recall@K、MRR、关键词覆盖率、Prompt Profile、场景隔离和性能基线等回归指标，并接入 LangSmith Trace/Dataset/Experiment 支撑 Bad Case 闭环。
```
