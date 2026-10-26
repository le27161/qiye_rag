---
title: Dense、BM25 和 Reranker：三层筛选，各自解决什么问题
date: 2026-10-26 09:04:00
permalink: rag/hybrid-search-reranking/
categories: [RAG 工程]
tags: [Milvus, 混合检索, BM25, Reranker]
series: RAG 工程笔记
description: 用设备报错查询解释语义召回、关键词召回、分数融合与二阶段重排的分工。
---

用户输入“ZX-410 升级后出现 E207，应该怎么处理”，里面既有自然语言，也有不容模糊的型号和错误码。只搜关键词，可能漏掉“固件更新后无法启动”的同义描述；只搜语义，又可能把其他型号的维修手册排在前面。混合检索要解决的，正是这种表达与精确约束并存的问题。

<!-- more -->

## Dense 找语义，BM25 守住词面线索

Dense 检索依赖向量表示，能够跨过部分同义表达差异。BM25 则根据词项出现情况、稀有程度和文档长度计算匹配贡献，更适合补充型号、编号和术语信号。

但 BM25 也不是数据库的字符串等值比较。`ZX-410` 如何分词、连字符是否保留，都会影响结果。需要精确限定型号时，最可靠的做法往往是提取一个规范化型号字段，在检索时加入结构化条件，而不是把全部希望交给文本排名。

Milvus 支持服务端 BM25 函数时，可以让原始文本产生 sparse 表示，而 dense 向量由本地 Embedding 生成。BGE-M3 自身也有 sparse 能力，但它与 BM25 是不同的表示方法，不应写入同一个函数输出字段并混为一谈。

## 融合不是直接把原始分数相加

余弦、L2 与 BM25 的取值范围和方向并不相同。直接算 `0.5 * dense + 0.5 * bm25`，可能让数值尺度较大的一路支配结果。

加权融合需要按所用实现的方式转换分数；RRF 则根据排名贡献组合结果，避免直接比较原始尺度。下面是可独立理解的 RRF 示例，不等同于 Milvus 内部实现的完整代码：

```python
from collections import defaultdict

def reciprocal_rank_fusion(rankings, k=60):
    scores = defaultdict(float)
    for ranking in rankings:
        for rank, document_id in enumerate(ranking, start=1):
            scores[document_id] += 1 / (k + rank)
    return sorted(scores, key=scores.get, reverse=True)
```

RRF 比较容易建立初始基线，加权方案则方便表达领域偏好。没有一种必然更优。应在相同候选预算下，比较术语问题和自然语言问题的分组效果。

## FAQ 与文档是另一层路由

同时查 FAQ 和文档，不等于完成了 Dense + Sparse 混合检索。

FAQ 集合和文档集合分别代表资料形态，每个集合内部都可以执行混合检索。业务计划先决定需要查哪些资料，再决定各集合使用怎样的检索方法。

分开存储的好处是标准问答与长文档可以使用不同字段和返回逻辑。FAQ 命中后可以读取经过审核的标准答案，而文档候选通常仍要经过证据筛选和生成。

## Reranker 只能重排已经找到的东西

Bi-Encoder 分别编码问题与文档，适合大范围召回。CrossEncoder 把问题和候选文本联合输入，能对动作、条件和细节做更细的相关性判断，但每对文本都要推理，不适合直接扫描整个知识库。

正确顺序是扩大召回、合并去重，再对有限候选重排。片段 ID 应作为去重依据，避免同一段文字因多个变体命中，挤占最终上下文。

重排输出可能是 logit，也可能经过 sigmoid 等转换，取决于模型与封装；它不是天然落在 0 到 1 之间，更不是答案正确概率。重排还可能因输入截断而漏掉文末的关键条件，所以需要一起检查候选长度和截断策略。

最后，所有召回分支都必须携带相同的权限和版本条件。不能让 dense 结果受控、sparse 结果却成为绕过隔离的后门。

延伸阅读：[动态检索计划](/rag/retrieval-plans/)、[切块与表格](/rag/chunking-and-tables/)。返回 [专栏目录](/rag/)。
