"""Mini RAG 数据对象定义 — 贯穿整个 RAG 链路的所有数据结构。

核心数据流：
  用户问题 → QueryPreparation（改写 + 变体 + 检索计划）
    → RetrievalResult（FAQ/Doc 命中 + 分数 + 耗时）
    → AnswerResult（最终答案 + 来源引用 + 路由信息）

所有数据类使用 frozen=True 确保不可变，避免链路中的意外修改。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from langchain_core.documents import Document


@dataclass(frozen=True)
class RetrievalPlan:
    """检索计划 — 控制一次问答中的检索策略参数。

    这些参数由 prepare_query 函数根据问题特征设定，
    替代完整项目中的 intent_classifier + strategy 两阶段逻辑，
    保持精简版的简洁。

    Attributes:
        run_faq: 是否检索 FAQ 集合
        run_doc: 是否检索文档集合
        faq_top_k: FAQ 检索的 top_k 数量（默认 12）
        doc_top_k: 文档检索的 top_k 数量（默认 12）
        rerank: 是否启用 CrossEncoder 重排序
        use_query_variants: 是否生成多路查询变体进行检索

    调用顺序：mini-rag 流程 -> RetrievalPlan。
    """

    run_faq: bool = True
    run_doc: bool = True
    faq_top_k: int = 12
    doc_top_k: int = 12
    rerank: bool = True
    use_query_variants: bool = True


@dataclass(frozen=True)
class QueryPreparation:
    """查询准备结果 — 从原始用户问题到可供检索使用的全部信息。

    由 prepare_query() 函数完成：
      1. 追问改写 → rewritten_query
      2. 查询变体生成 → query_variants
      3. 检索计划构建 → plan

    Attributes:
        original_query:  用户原始输入（未改写）
        rewritten_query: 追问改写后的独立查询
        query_variants:  多路检索变体列表（如 ["报销流程", "费用报销流程", "报销步骤"]）
        source_filter:   按来源筛选（如 "hr"）或 None（检索全部来源）
        plan:            检索策略参数

    调用顺序：mini-rag 流程 -> QueryPreparation。
    """

    original_query: str
    rewritten_query: str
    query_variants: list[str]
    source_filter: str | None
    plan: RetrievalPlan


@dataclass
class RetrievalHit:
    """单条检索命中 — Milvus 返回的一个文档及其相似度分数。

    Attributes:
        document: LangChain Document 对象（含 page_content 和 metadata）
        score:    相似度分数（Dense 向量距离或 Reranker 重排后的分数）

    调用顺序：mini-rag 流程 -> RetrievalHit。
    """

    document: Document
    score: float


@dataclass
class RetrievalResult:
    """一次检索的完整结果 — 针对 FAQ 或文档集合的单路检索输出。

    由 MiniMilvusStore.search_many() 返回，
    包含去重合并后的命中列表、最高分、耗时等。

    Attributes:
        source_type: 来源类型（"faq" 或 "doc"）
        query:       实际用于检索的主查询（第一个变体）
        hits:        去重合并后的命中列表（已排序 + Reranker 重排）
        elapsed_ms:  检索耗时（毫秒）

    调用顺序：mini-rag 流程 -> RetrievalResult。
    """

    source_type: Literal["faq", "doc"]
    query: str
    hits: list[RetrievalHit] = field(default_factory=list)
    elapsed_ms: float = 0.0
    timings: dict[str, float] = field(default_factory=dict)

    @property
    def top_score(self) -> float:
        """返回检索命中的最高相关度分数；无命中时返回 0.0。

        该值用于 FAQ 直出判断（高于 faq_direct_threshold 时直接返回标准答案），
        以及在检索统计中展示最高匹配分。

        Returns:
            float: 最高命中分数；hits 为空时返回 0.0

        调用顺序：mini-rag 流程 -> RetrievalResult.top_score()。
        """
        return self.hits[0].score if self.hits else 0.0

    @property
    def top_document(self) -> Document | None:
        """返回检索命中中得分最高的 LangChain Document 对象；无命中时返回 None。

        该文档通常用于：
          - FAQ 直出判断时提取 answer 字段作为标准答案
          - 在检索统计中展示最佳命中的元数据信息

        Returns:
            Document | None: 得分最高的文档对象；hits 为空时返回 None

        调用顺序：mini-rag 流程 -> RetrievalResult.top_document()。
        """
        return self.hits[0].document if self.hits else None

    def source_payloads(self, limit: int = 5) -> list[dict[str, Any]]:
        """将检索命中转换为 API 友好的来源引用列表。

        每条引用包含：
          - source_type: 来源类型
          - score:       相关度分数
          - content:     文档内容前 500 字符（预览）
          - metadata:    完整元数据
          - citation:    人类可读的引用标注（如 "hr / 员工手册.md / page 3"）

        调用顺序：mini-rag 流程 -> RetrievalResult.source_payloads()。
        """
        payloads: list[dict[str, Any]] = []
        for hit in self.hits[:limit]:
            metadata = dict(hit.document.metadata or {})
            payloads.append(
                {
                    "source_type": self.source_type,
                    "score": hit.score,
                    "content": hit.document.page_content[:500],
                    "metadata": metadata,
                    "citation": format_citation(metadata),
                }
            )
        return payloads


@dataclass(frozen=True)
class AnswerResult:
    """RAG 最终答案 — 从 ask() 函数返回的完整问答结果。

    Attributes:
        answer:           LLM 生成或直接路由的最终答案文本
        sources:          引用来源列表（API 友好的格式）
        route:            命中路由类型
                           - "direct_answer": 直接回答（打招呼 / 转人工）
                           - "faq_direct":     FAQ 标准答案直出（高置信度命中）
                           - "rag":            完整 RAG 生成
        rewritten_query: 改写后的查询
        query_variants:  多路检索变体列表
        retrieval:        检索统计信息（用于调试和前端展示）

    调用顺序：mini-rag 流程 -> AnswerResult。
    """

    answer: str
    sources: list[dict[str, Any]]
    route: str
    rewritten_query: str
    query_variants: list[str]
    retrieval: dict[str, Any]


def format_citation(metadata: dict[str, Any]) -> str:
    """从文档元数据构建人类可读的引用标注。

    格式示例：
      - "hr / 员工手册.md / page 3"          (文档来源，有页码)
      - "it / faq_vpn_connection_v2"         (FAQ 来源)
      - "finance / 报销制度.pdf / page 1"    (PDF 来源)

    拼接规则：
      来源 + 文件名/路径 + (可选) page + (可选) row

    调用顺序：mini-rag 流程 -> format_citation()。
    """
    source = metadata.get("source") or "unknown"
    file_name = metadata.get("file_name") or metadata.get("path") or metadata.get("faq_id") or ""
    page = metadata.get("page")
    row = metadata.get("row_number")
    parts = [str(source)]
    if file_name:
        parts.append(str(file_name))
    if page is not None:
        parts.append(f"page {int(page) + 1}")
    if row is not None:
        parts.append(f"row {row}")
    return " / ".join(parts)

