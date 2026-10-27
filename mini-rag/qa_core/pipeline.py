"""Mini RAG 在线问答 Pipeline — ask 函数主流程编排。

这是 Mini RAG 的核心入口，串联起一次完整问答的所有阶段：

  路由决策树：
    用户问题
      ├── direct_answer     → 直接返回（打招呼 / 转人工）
      ├── faq_direct        → 高置信度 FAQ 标准答案直出
      └── rag               → 完整 RAG 管线（FAQ检索 + Doc检索 + LLM生成）

  完整 RAG 阶段：
    1. 直接回答判断（无检索、无 LLM）
    2. 获取 MySQL 中当前激活的知识库版本
    3. 查询预处理（追问改写 + 变体生成 + 检索计划）
    4. FAQ 混合检索（Dense + BM25 + Reranker）
    5. FAQ 直出判断（最高分 > 阈值 → 直接返回标准答案）
    6. 文档混合检索（Dense + BM25 + Reranker）
    7. 选择上下文（FAQ + Doc 命中合并，按 min_score 过滤）
    8. LLM 生成最终答案（带来源引用）

  每个阶段都记录耗时，用于性能分析和运行展示。
"""

from __future__ import annotations

import time

from langchain_core.documents import Document

from qa_core.config import get_settings
from qa_core.kb_version import active_version
from qa_core.prompts import generate_answer
from qa_core.query import prepare_query
from qa_core.retrieval import doc_store, faq_store
from qa_core.schemas import AnswerResult, RetrievalHit, RetrievalResult


def direct_answer(query: str) -> str | None:
    """处理无需检索的直接回答场景。

    适用场景：
      - 打招呼："你好" / "hi" → 返回欢迎语
      - 转人工："转人工" → 返回人工支持指引

    这些场景不走检索和 LLM，直接返回预设文本，响应速度最快。

    Returns:
        预设答案文本；不匹配时返回 None，由上层进入完整 RAG 流程。

    调用顺序：mini-rag 流程 -> direct_answer()。
    """
    normalized = query.strip().lower()
    if normalized in {"hi", "hello", "你好", "您好"}:
        return "您好，我可以基于企业知识库回答 HR、IT 支持和财务报销相关问题。"
    if "转人工" in query or "人工" == query.strip():
        return "可以联系内部服务台处理人工支持请求。"
    return None


def faq_direct_answer(result: RetrievalResult, threshold: float) -> str | None:
    """FAQ 标准答案直出判断 — 当 FAQ 检索最高分超过阈值时直接返回标准答案。

    设计理由：
      FAQ 集合中的问答经过人工审核，答案质量有保证。
      当检索到的 FAQ 置信度足够高时，无需再查文档和调用 LLM 生成，
      可以节省 LLM 调用成本和延迟。

    Args:
        result:    FAQ 检索结果
        threshold: 直出分数阈值（默认 0.84）

    Returns:
        FAQ 标准答案文本；不满足阈值时返回 None。

    调用顺序：mini-rag 流程 -> faq_direct_answer()。
    """
    top = result.top_document
    if top is None or result.top_score < threshold:
        return None
    # FAQ 文档的 metadata 中包含原始的 answer 字段
    answer = (top.metadata or {}).get("answer")
    return str(answer).strip() if answer else None


def select_context_docs(
    faq_result: RetrievalResult,
    doc_result: RetrievalResult,
    *,
    top_n: int,
    min_score: float,
) -> list[Document]:
    """从 FAQ 和文档检索结果中选择最终送入 LLM 的上下文文档。

    选择策略：
      1. 合并 FAQ 和 Doc 的所有命中
      2. 过滤掉分数低于 min_score 的命中（去除不相关内容）
      3. 按分数降序排列
      4. 取前 top_n 条

    为什么合并 FAQ 和 Doc？
      - FAQ 命中提供标准化答案片段（高准确度但覆盖面窄）
      - Doc 命中提供详细文档内容（覆盖面宽但可能不够精炼）
      - 两者互补，组合后的上下文更完整

    Args:
        faq_result: FAQ 检索结果
        doc_result: 文档检索结果
        top_n:      最终上下文文档数量上限
        min_score:  最低相关度阈值

    Returns:
        按相关度排序的 LangChain Document 列表

    调用顺序：mini-rag 流程 -> select_context_docs()。
    """
    # 合并 FAQ 和 Doc 的命中，过滤低分
    candidates: list[RetrievalHit] = [
        *[hit for hit in faq_result.hits if hit.score >= min_score],
        *[hit for hit in doc_result.hits if hit.score >= min_score],
    ]
    # 按分数降序排列
    candidates.sort(key=lambda item: item.score, reverse=True)
    # 取 top_n
    return [hit.document for hit in candidates[:top_n]]


def ask(query: str, *, history: list[str] | None = None, source_filter: str | None = None) -> AnswerResult:
    """Mini RAG 核心问答入口 — 从用户问题到最终答案的完整管线。

    阶段详解（带计时）：
      ┌─────────────────────────────────────────────────┐
      │ 阶段1: direct_route_ms                          │
      │   直接回答判断（打招呼/转人工）                    │
      ├─────────────────────────────────────────────────┤
      │ 阶段2: active_version_ms                        │
      │   从 MySQL 获取当前激活的知识库版本                │
      ├─────────────────────────────────────────────────┤
      │ 阶段3: prepare_query_ms                         │
      │   追问改写 + 查询变体生成 + 检索计划构建           │
      ├─────────────────────────────────────────────────┤
      │ 阶段4: faq_search_total_ms                      │
      │   FAQ 混合检索（Dense + BM25 + Reranker）        │
      ├─────────────────────────────────────────────────┤
      │ 阶段5: faq_direct_check_ms                      │
      │   FAQ 直出判断（高分直接返回）                     │
      ├─────────────────────────────────────────────────┤
      │ 阶段6: doc_search_total_ms                      │
      │   文档混合检索（Dense + BM25 + Reranker）         │
      ├─────────────────────────────────────────────────┤
      │ 阶段7: select_context_ms                        │
      │   FAQ + Doc 命中合并、过滤、截断                  │
      ├─────────────────────────────────────────────────┤
      │ 阶段8: llm_generate_ms                          │
      │   LLM 生成最终答案（带引用）                      │
      └─────────────────────────────────────────────────┘

    Args:
        query:         用户当前问题
        history:       历史对话记录（用于追问改写）
        source_filter: 按来源筛选（如 "hr"/"it"/"finance"）

    Returns:
        AnswerResult（答案文本、来源引用、路由类型、检索统计、各阶段耗时）

    调用顺序：mini-rag 流程 -> ask()。
    """
    settings = get_settings()

    # 对话历史
    history = history or []

    # === 全局计时 （该功能不是必选项，是为了将来优化各个阶段参考各自阶段耗时） ===
    total_started = time.perf_counter()
    timings: dict[str, float] = {}

    def mark(name: str, started: float) -> float:
        """记录一个阶段的耗时（毫秒），并返回新的计时起点。

        在 ask() 主流程中各阶段之间调用，用于精确测量每个环节的耗时，
        最终汇总到 AnswerResult.retrieval.timings 中供分析和展示。

        Args:
            name:    阶段名称（如 "direct_route_ms"、"faq_search_total_ms"）
            started: 该阶段开始的时间戳（time.perf_counter() 的返回值）

        Returns:
            float: 当前时间戳（作为下一个阶段的计时起点）

        调用顺序：mini-rag 流程 -> mark()。
        """
        timings[name] = round((time.perf_counter() - started) * 1000, 2)
        return time.perf_counter()

    # === 阶段1: 直接回答判断 ===
    stage_started = time.perf_counter()
    direct = direct_answer(query)
    mark("direct_route_ms", stage_started)
    if direct:
        timings["total_ms"] = round((time.perf_counter() - total_started) * 1000, 2)
        return AnswerResult(
            answer=direct,
            sources=[],
            route="direct_answer",
            rewritten_query=query,
            query_variants=[query],
            retrieval={"timings": timings},
        )

    # === 阶段2: 获取知识库版本 ===
    stage_started = time.perf_counter()
    kb_version = active_version()
    print("kb_version", kb_version)
    stage_started = mark("active_version_ms", stage_started)

    # === 阶段3: 查询预处理 ===
    prepared = prepare_query(query, history=history, source_filter=source_filter)
    stage_started = mark("prepare_query_ms", stage_started)

    # === 阶段4: FAQ 检索 ===
    faq_result = faq_store().search_many(
        prepared.query_variants, # 查询变体的集合
        k=prepared.plan.faq_top_k, # 召回的数量（检索计划生成的参数）
        source_filter=prepared.source_filter, # 设定检索数据时指定的过滤条件
        kb_version=kb_version, # 当前可用的版本号
        source_type="faq",
        rerank_hits=prepared.plan.rerank, # 开启二次精排
    )
    stage_started = mark("faq_search_total_ms", stage_started)

    # === 阶段5: FAQ 直出判断 ===
    faq_answer = faq_direct_answer(faq_result, settings.faq_direct_threshold)
    stage_started = mark("faq_direct_check_ms", stage_started)
    if faq_answer:
        # 高置信度 FAQ 命中 → 直接返回，跳过文档检索和 LLM 生成
        timings["total_ms"] = round((time.perf_counter() - total_started) * 1000, 2)
        return AnswerResult(
            answer=faq_answer,
            sources=faq_result.source_payloads(limit=3),
            route="faq_direct",
            rewritten_query=prepared.rewritten_query,
            query_variants=prepared.query_variants,
            retrieval={
                "kb_version": kb_version,
                "faq_top_score": faq_result.top_score,
                "doc_top_score": 0.0,
                "faq_hits": len(faq_result.hits),
                "doc_hits": 0,
                "query_variant_count": len(prepared.query_variants),
                "rerank": prepared.plan.rerank,
                "faq_elapsed_ms": round(faq_result.elapsed_ms, 2),
                "faq_retrieval_timings": faq_result.timings,
                "faq_rerank_ms": faq_result.timings.get("rerank_ms", 0.0),
                "timings": timings,
            },
        )

    # === 阶段6: 文档检索 ===
    doc_result = doc_store().search_many(
        prepared.query_variants,
        k=prepared.plan.doc_top_k,
        source_filter=prepared.source_filter,
        kb_version=kb_version,
        source_type="doc",
        rerank_hits=prepared.plan.rerank,
    )
    stage_started = mark("doc_search_total_ms", stage_started)

    # === 阶段7: 选择上下文 ===
    context_docs = select_context_docs(
        faq_result,
        doc_result,
        top_n=settings.final_context_top_n,
        min_score=settings.min_context_score,
    )
    stage_started = mark("select_context_ms", stage_started)

    # === 阶段8: LLM 生成答案 ===
    answer = generate_answer(
        prepared.rewritten_query,
        context_docs,
        history,
        settings.max_context_chars,
    )
    mark("llm_generate_ms", stage_started)

    # === 汇总 ===
    timings["total_ms"] = round((time.perf_counter() - total_started) * 1000, 2)

    # FAQ 和 Doc 的来源引用（FAQ 最多 2 条 + Doc 最多 5 条，总共最多 5 条）
    sources = faq_result.source_payloads(limit=2) + doc_result.source_payloads(limit=5)

    return AnswerResult(
        answer=answer,
        sources=sources[:5],
        route="rag",
        rewritten_query=prepared.rewritten_query,
        query_variants=prepared.query_variants,
        retrieval={
            "kb_version": kb_version,
            "faq_hits": len(faq_result.hits),
            "doc_hits": len(doc_result.hits),
            "faq_top_score": faq_result.top_score,
            "doc_top_score": doc_result.top_score,
            "context_docs": len(context_docs),
            "query_variant_count": len(prepared.query_variants),
            "rerank": prepared.plan.rerank,
            "faq_elapsed_ms": round(faq_result.elapsed_ms, 2),
            "doc_elapsed_ms": round(doc_result.elapsed_ms, 2),
            "faq_retrieval_timings": faq_result.timings,
            "doc_retrieval_timings": doc_result.timings,
            "faq_rerank_ms": faq_result.timings.get("rerank_ms", 0.0),
            "doc_rerank_ms": doc_result.timings.get("rerank_ms", 0.0),
            "timings": timings,
        },
    )


