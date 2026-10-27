"""查询准备模块 — 追问改写 + 查询变体生成 + 检索计划构建。

这是 Mini RAG 的查询预处理层，对应完整项目中的：
  - intent_classifier.py   (意图识别)
  - query_rewrite.py       (追问改写 + 变体生成)
  - retrieval_plan.py      (检索策略)

精简版做了简化：
  - 意图识别：仅通过关键词 + 追问判断，不去调用 LLM 分类
  - 查询变体：读取 mini-rag/config/rules.toml 中的确定性规则，不调用 LLM 生成
  - 检索计划：读取 Mini RAG 独立 Settings 中的 top_k、阈值和重排参数

设计思路：
  先通过小模型/规则做查询理解和多路改写，
  再用这多路查询变体去 Milvus 做多路检索，
  合并去重后送 Reranker 精排 → 最终用 top_k 个 context 送 LLM。
"""

from __future__ import annotations

from qa_core.rules import get_rule_config

from qa_core.config import get_settings
from qa_core.models import get_chat_model
from qa_core.schemas import QueryPreparation, RetrievalPlan


# 常见追问关键词 — 用于判断当前问题是否为省略/指代式的追问
FOLLOW_UP_HINTS = ("那", "这个", "它", "审批", "材料", "费用", "怎么处理", "怎么走")


def needs_rewrite(query: str, history: list[str]) -> bool:
    """判断当前查询是否需要追问改写。

    判断规则：
      1. 没有历史对话 → 不是追问
      2. 查询很短（≤12 字） → 很可能是省略了上下文的追问
      3. 包含追问关键词 → 很可能是追问

    例如：
      - "那审批呢"（有 "那" + 很短）→ 需要改写
      - "VPN 连接"（无历史）→ 不需要改写
      - "怎么处理"（有 "怎么处理"）→ 需要改写

    调用顺序：mini-rag 流程 -> needs_rewrite()。
    """
    if not history:
        return False
    normalized = query.strip()
    return len(normalized) <= 12 or any(hint in normalized for hint in FOLLOW_UP_HINTS)


def rewrite_query(query: str, history: list[str]) -> str:
    """使用 LLM 将追问改写为独立可检索的完整问题。

    为什么要改写？
      多轮对话中，用户常用省略/指代："那审批呢？"、"它的流程是什么？"
      这些追问丢失了上下文，直接检索效果极差。
      改写后："企业差旅费用审批流程是什么？"

    改写策略：
      - 非追问（needs_rewrite 返回 False）直接返回原始查询
      - 追问场景调用 LLM，给最近 6 轮历史 + 当前追问，要求输出独立问题

    降级处理：
      如果 LLM 返回空字符串，回退到原始查询。

    调用顺序：mini-rag 流程 -> rewrite_query()。
    """
    if not needs_rewrite(query, history):
        return query
    # 只取最近 6 轮历史，避免 prompt 过长影响 LLM 质量
    history_text = "\n".join(history[-6:])
    prompt = (
        "你是企业知识库问答系统的查询改写器。请把用户追问改写成一个可独立检索的问题。"
        "只输出改写后的问题，不要解释。\n\n"
        f"历史对话：\n{history_text}\n\n"
        f"当前追问：{query}"
    )
    rewritten = get_chat_model().invoke(prompt).content
    return str(rewritten).strip() or query


def generate_variants(query: str, max_variants: int | None = None) -> list[str]:
    """生成多路查询变体 — 用于提高召回的多样性。

    为什么要多路检索？
      同一个问题可以有多种表达方式：
        - "报销流程是什么" ≈ "费用报销流程" ≈ "报销步骤" ≈ "报销 SOP"
      数据库中可能只有其中一种表达方式的文档。
      用多个变体同时检索，取合并去重结果，可以大幅提高召回率。

    当前读取 mini-rag/config/rules.toml 中的 query_variants.replacements。
    Mini RAG 只保留规则层，不调用 LLM 扩展规则未覆盖的新词。

    调用顺序：mini-rag 流程 -> generate_variants()。
    """
    if max_variants is None:
        max_variants = get_settings().retrieval_variant_max + 1
    variants = [query.strip()]  # 原始查询始终排在第一位

    def add(candidate: str) -> None:
        """向变体列表添加一个候选查询，自动去重并受数量上限约束。

        添加逻辑：
          1. 去除首尾空白后检查是否为空
          2. 检查是否已存在于 variants 列表中（避免重复）
          3. 检查当前列表长度是否已达到 max_variants 上限

        Args:
            candidate: 待添加的候选变体文本

        调用顺序：mini-rag 流程 -> add()。
        """
        candidate = candidate.strip()
        if candidate and candidate not in variants and len(variants) < max_variants:
            variants.append(candidate)

    rules = get_rule_config().query_variants
    for rule in rules.replacements:
        if not rule.matches(query):
            continue
        for old, new in rule.replacements:
            add(query.replace(old, new) if not rule.ignore_case else _replace_ignore_case(query, old, new))
    return variants


def prepare_query(query: str, *, history: list[str] | None = None, source_filter: str | None = None) -> QueryPreparation:
    """查询预处理主入口 — 将用户原始输入转换为可检索的结构化数据。

    处理流程：
      1. 追问改写：将省略/指代追问还原为独立问题
      2. 构建检索计划：设置 FAQ/Doc 的 top_k、是否启用 Reranker、是否启用多路变体等
      3. 生成查询变体：对改写后的问题生成多路同义表达（如果启用了 use_query_variants）

    Args:
        query:         用户当前问题
        history:       历史对话记录（用于追问改写），默认为空列表
        source_filter: 按数据来源筛选（如 "hr"），默认检索全部来源

    Returns:
        QueryPreparation（含改写后查询、变体列表、检索计划）

    调用顺序：mini-rag 流程 -> prepare_query()。
    """
    settings = get_settings()
    history = history or []

    # 第一步：追问改写
    rewritten = rewrite_query(query, history)

    # 第二步：构建检索计划（参数来自 Mini RAG 独立 Settings）
    plan = RetrievalPlan(
        faq_top_k=settings.faq_top_k,
        doc_top_k=settings.doc_top_k,
        rerank=settings.rerank_enabled,
        use_query_variants=settings.use_query_variants,
    )

    # 第三步：生成查询变体（仅在启用时）
    variants = generate_variants(rewritten, settings.retrieval_variant_max + 1) if plan.use_query_variants else [rewritten]

    return QueryPreparation(
        original_query=query,
        rewritten_query=rewritten,
        query_variants=variants,
        source_filter=source_filter,
        plan=plan,
    )




def _replace_ignore_case(query: str, old: str, new: str) -> str:
    """执行规则配置要求的忽略大小写替换。

    与 str.replace 不同，此函数使用正则替换，支持：
      - 忽略大小写匹配（如 "webhook" 可匹配 "Webhook" / "WEBHOOK"）
      - 正则转义（old 中的特殊字符不会被视为正则语法）

    使用 re.escape(old) 确保替换词中的特殊字符（如 . * + 等）
    不会意外导致正则行为异常。

    Args:
        query: 待处理的原始查询文本
        old:   要被替换的文本（大小写不敏感）
        new:   替换后的文本

    Returns:
        替换后的查询文本

    示例：
        >>> _replace_ignore_case("Webhook 配置", "webhook", "回调")
        "回调 配置"

    调用顺序：mini-rag 流程 -> _replace_ignore_case()。
    """
    import re

    return re.sub(re.escape(old), new, query, flags=re.IGNORECASE)



