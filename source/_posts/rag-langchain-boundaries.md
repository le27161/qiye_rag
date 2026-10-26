---
title: LangChain 在工程里最有用的角色，是适配器而不是总导演
date: 2026-10-26 09:02:00
permalink: rag/langchain-boundaries/
categories: [RAG 工程]
tags: [LangChain, Python, 架构设计]
series: RAG 工程笔记
description: 保留模型、消息和文档适配能力，把权限、版本及业务流程留在可测试的应用层。
---

刚接触 LangChain，容易把重点放在“用哪条 Chain”。但当系统开始处理 FAQ 直出、知识版本、租户权限和流式错误时，一条通用问答链往往不够用了。此时没有必要在彻底自研与全盘依赖框架之间二选一，真正需要明确的是框架负责到哪里。

<!-- more -->

## 统一外部差异，价值已经很大

模型供应商、文档格式和向量库的接口各不相同。LangChain 的实际价值，是让这些差异尽量停留在系统边缘。

`ChatOpenAI` 及兼容接口的适配器负责模型调用；`SystemMessage`、`HumanMessage` 和 `AIMessage` 保留消息角色；`Document` 将正文与 metadata 放在同一对象里；Loader、Splitter 和 VectorStore 则为离线解析及在线召回提供统一入口。

业务层依赖这些较稳定的对象，就不必在每个分支重新处理供应商的响应格式。但兼容 OpenAI 风格接口，不代表所有供应商都支持相同的结构化输出、工具调用和流式行为，接入前仍应做能力测试。

## 结构化输出解决格式问题，不解决事实问题

下面是一段独立的结构示例，需要安装支持相应接口的 LangChain 集成，并自行提供模型配置：

```python
from pydantic import BaseModel, Field

class QueryVariants(BaseModel):
    queries: list[str] = Field(min_length=1, max_length=3)

def generate_variants(chat_model, question: str) -> QueryVariants:
    structured = chat_model.with_structured_output(QueryVariants)
    return structured.invoke(
        "只生成同义检索问句，不增加时间、金额或适用对象：" + question
    )
```

相比让模型输出一段自由文本再手工分割，这种方式让字段和数量约束更明确。但 Pydantic 通过，只能说明结构合法，不能证明三个问句真的等价。系统仍需去重、保留原问题，并对新增实体或约束做检查。

## 不要让框架替你定义业务边界

“是否允许跨租户检索”“低置信意图是否禁用 FAQ 模糊直出”“候选版本何时上线”，不是模型适配层的职责。

这些判断如果隐藏在复杂 Chain 或回调里，排查时很难看清执行顺序。显式的普通 Python 流程通常更直接：先校验范围，再确定路由，随后准备检索、筛证据，最后生成和收尾。

LCEL 的管道组合适合输入输出清晰的局部流程，例如模板、模型和解析器的串联。但遇到权限判断、复用候选、提前返回和事务更新时，优先选择容易测试与观测的表达方式，没必要为了使用某种语法而重写整条业务链。

## 历史记录也不是模型自带的记忆

消息历史组件保存了会话，并不意味着模型每次都能看到所有消息。实际发送哪些历史、怎样压缩、何时清理，仍由应用决定。

同样，VectorStore 封装也没有消除 Milvus 的 schema、索引和加载状态。接口让调用更方便，却不能替代对底层行为的理解。比如 wrapper 自动完成向量编码，并不等于缓存、指标和过滤条件可以不再检查。

我的取舍是：通用兼容问题交给生态，业务决策保留在应用层。判断这个边界是否合理，可以看一件事——不用连接真实模型，能不能独立测试路由、权限和发布规则。

延伸阅读：[Pipeline 与请求状态](/rag/pipeline-and-confidence/)、[分层测试](/rag/testing-strategy/)。返回 [专栏目录](/rag/)。
