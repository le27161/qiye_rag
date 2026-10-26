# RAG 系列编辑说明

## 输出和边界

本次输出为当前 Hexo 博客中的 21 篇中文 Markdown 文章，以及 `/rag/` 专栏目录。没有生成另一套独立课件网站，没有复制课件的 HTML、图片、动画或原项目大段源码。

只读取 `D:\Users\86181\Desktop\xuexi\01_课件\site`；所有新增和修改均在本博客仓库。已有 Hello World、原独立参考 HTML、站点名称与主题均保留。导航新增“RAG 工程”，前置知识页优先链接到新博客，旧参考页仍可访问。

文章来源为用户提供的本地 KnowForge RAG Platform 资料。技术讲解采用新问题、新例子和重新组织的论证，不以“学习目标—章节—练习—重点掌握”的课件结构输出。源资料的授权状态未独立核实；对外使用任何源资料原图、原代码仍需另行核对权利。

## 选题与参考主题对应

文件均位于 `source/_posts/`，以 `rag-` 开头。

| 博客主题 / 文件后缀 | 主要参考页 |
| --- | --- |
| system-boundaries | 01-project-overview、index、course-outline |
| embedding-models | 02-rag-fundamentals、appendix-f |
| langchain-boundaries | 03-langchain-ecosystem |
| milvus-indexes | 04-milvus-index-and-operations、appendix-c |
| hybrid-search-reranking | 02-rag-fundamentals、08-milvus-hybrid-search、appendix-d |
| intent-routing | 05-intent-classification |
| retrieval-plans | 06-retrieval-strategy |
| query-rewriting | 07-query-rewrite-variants |
| pipeline-and-confidence | 09-qaservice-orchestration、10-rag-pipeline |
| prompt-profiles | 10-rag-pipeline、11-prompt-engineering |
| fastapi-streaming | 11/12-fastapi-async、10-rag-pipeline |
| startup-readiness | 12/13-app-entry-preflight、appendix-a |
| chunking-and-tables | 13-knowledge-governance、15/16-ingestion-pipeline、appendix-e/g |
| ingestion-and-versioning | 13-knowledge-governance、13/14-kb-versioning、offline-ingestion-teaching-notes |
| data-scope-and-cache | 14/15-data-isolation、10-rag-pipeline |
| evaluation-and-bad-cases | 14-rag-quality、16/17-quality-evaluation |
| testing-strategy | 15/17/18-testing-system |
| observability-capacity | 16-observability-capacity、18/19-observability-tracing |
| docker-delivery | 17-docker-delivery、19/20-docker-containerization |
| fingerprints-and-foundations | appendix-a/b/h、13-knowledge-governance |
| ai-assisted-development | 两份 04.5-vibe-coding-rag-practice 页面 |

同主题不同编号页面合并处理，不根据文件编号重复发布。动画和独立时序图作为理解主链路的辅助资料，不作为单独博客选题。404、资源文件与搜索索引不属于正文内容。

## 对容易误解的描述所作处理

- 不给未经复现实验的耗时、容量或准确率背书，不引用无完整实验条件的提升数字。
- 区分向量距离、混合融合分、重排 logit 与答案诊断分，不把它们统一写成概率。
- 不将所有模型的句向量提取方式都描述为 Mean Pooling。
- 区分元数据快速指纹与文件内容 SHA256，避免“用了 SHA256 就一定检测了内容”的误解。
- 对源资料不同版本的切块参数不强行选一个通用标准，改为解释长度单位、父子块取舍和评测方法。
- 明确本地 Embedding 不等于整条链路不向外发送原文。
- 强调权限来自可信身份，不能由前端自报角色；Prompt 与 CORS 都不能替代后端授权或 WebSocket Origin 校验。
- 补充线性有效期版本模型的分叉、并发构建与回滚后再发布边界。
- 明确线程桥接不会自动强制取消正在执行的同步模型调用，也不保证线程亲和性。
- 明确流式生成后若修订答案，前端必须接收最终全文或替换事件。
- 区分 Compose 配置解析、依赖就绪、首次入库与真实业务验收；不把删除卷或重建集合当作默认排错步骤。

## 验证范围

`npm run build` 验证博客生成；`npm run check:rag` 检查文章元数据、目录覆盖、摘要、Markdown 站内链接和生成 HTML。

这不代表原 RAG 项目的模型、数据库、API 或 Docker 流程已经在本博客环境中集成运行。文章里的部分代码明确属于结构示意或需要外部依赖的例子。
