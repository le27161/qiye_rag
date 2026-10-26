---
title: RAG 工程笔记
date: 2026-10-26 09:30:00
description: 从检索原理到知识发布，围绕实际问题梳理 RAG 系统的设计取舍、实现边界与排障方法。
---

RAG 最有意思的部分，不是把文档接到模型上，而是让系统在资料更新、权限变化和请求并发时，依然给出有依据、可追溯的回答。

这组文章围绕这些工程问题展开。可以按下面的主题连续阅读，也可以从遇到的问题直接进入，每篇都保留了必要背景。

## 先看清系统在做什么

[做 RAG 系统，先分清问答链路和知识发布链路](/rag/system-boundaries/) 从整体职责入手，解释为什么检索数据面和发布控制面要分开。

[Embedding 不是理解全文，而是为检索构造坐标](/rag/embedding-models/) 讨论向量度量、归一化和换模型时需要迁移什么。

[LangChain 在工程里最有用的角色，是适配器而不是总导演](/rag/langchain-boundaries/) 梳理框架与业务逻辑的边界。

## 让检索真的找到答案

- [Milvus 索引怎么选：别从 HNSW 参数开始调](/rag/milvus-indexes/)
- [Dense、BM25 和 Reranker：三层筛选，各自解决什么问题](/rag/hybrid-search-reranking/)
- [意图识别的终点不是标签，而是一次安全的路由决策](/rag/intent-routing/)
- [同一套 Top-K 不够用：把检索策略写成可解释的计划](/rag/retrieval-plans/)
- [“那外包人员呢？”：让追问变成可独立检索的问题](/rag/query-rewriting/)

## 从候选证据到流式回答

- [RAG Pipeline 的核心不是串组件，而是管理证据和请求状态](/rag/pipeline-and-confidence/)
- [Prompt 不该只有一份：用回答策略约束高风险问题](/rag/prompt-profiles/)
- [async 不会自动消除阻塞：把 RAG 流式输出接进 FastAPI](/rag/fastapi-streaming/)
- [端口打开不代表服务可用：为 RAG 设计启动与就绪检查](/rag/startup-readiness/)

## 把资料变成可以治理的知识

- [切块不是按字数剪文本：正文、表格与父子块的不同处理](/rag/chunking-and-tables/)
- [入库成功不等于上线成功：把知识更新做成可回滚的发布](/rag/ingestion-and-versioning/)
- [权限过滤不能只写在 Prompt 里，缓存也必须认识用户边界](/rag/data-scope-and-cache/)
- [指纹、稳定 ID 和配置摘要：RAG 增量更新容易忽略的基础设施](/rag/fingerprints-and-foundations/)

## 验证效果，然后交付

- [别只问“回答像不像”：用评测把 RAG 错误拆到具体层](/rag/evaluation-and-bad-cases/)
- [RAG 测试别全押在端到端：把确定性逻辑先测扎实](/rag/testing-strategy/)
- [RAG 为什么慢、为什么错：用 Trace 拆开质量和容量问题](/rag/observability-capacity/)
- [让 RAG 真正在另一台机器跑起来：Docker 交付与排障思路](/rag/docker-delivery/)
- [AI 辅助开发 RAG，关键不是一次生成多少代码](/rag/ai-assisted-development/)

## 相关主题

想了解工具调用与工作流，可以阅读 [Agent 工程手记](/agent/)；模型、上下文和框架的概括性介绍见 [大模型知识](/llm/)。
