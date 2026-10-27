"""Milvus 混合检索封装 — Dense HNSW + BM25 Sparse + CrossEncoder Reranker。

这是 Mini RAG 检索层的核心，通过 langchain_milvus 的 Milvus 类封装：
  1. Dense 向量检索  — BGE-M3 Embedding 生成的 1024 维稠密向量
  2. Sparse BM25 检索 — Milvus 服务端内置的中文 BM25 分词 + 稀疏向量
  3. CrossEncoder 重排 — BGE Reranker Large 对合并结果精排

混合检索流程：
  用户查询
    → Dense Embedding（BGE-M3）
    → Milvus Hybrid Search（Dense + BM25 Sparse 双路）
    → 多查询变体去重合并
    → CrossEncoder Reranker 精排
    → 返回 top_n 结果

集合划分：
  - FAQ 集合：企业常见问题标准答案
  - Doc 集合：业务文档切分后的文本块

去重策略：
  多个查询变体的检索结果按 chunk_id / faq_id 去重合并，
  同一个文档多次命中时保留最高分数。
"""

from __future__ import annotations

import time
from typing import Any, Literal

from langchain_core.documents import Document

from qa_core.config import SCENARIO, get_settings
from qa_core.models import get_embeddings, get_reranker
from qa_core.schemas import RetrievalHit, RetrievalResult


HNSW_M = 16
HNSW_EF_CONSTRUCTION = 200
HNSW_EF = 64
HYBRID_RANKER_KWARGS = {
    "ranker_type": "weighted",
    "ranker_params": {"weights": [0.55, 0.45]},
}


def escape_expr_value(value: str) -> str:
    """对 Milvus 布尔表达式中的字符串值进行转义处理。

    Milvus 的布尔表达式语法使用双引号包裹字符串常量，
    因此值中如果包含反斜杠或双引号，需要进行转义。

    例如：
      - 原始值 `abc"def` → 转义后 `abc\"def`
      - 原始值 `path\to\file` → 转义后 `path\\to\\file`

    Args:
        value: 待转义的原始字符串

    Returns:
        转义后的字符串（可用于 Milvus 表达式语法）

    调用顺序：mini-rag 流程 -> escape_expr_value()。
    """
    return value.replace("\\", "\\\\").replace('"', '\\"')


def bm25_function():
    """创建 Milvus 服务端 BM25 稀疏向量生成函数。

    BM25BuiltInFunction 是 langchain_milvus 提供的便捷封装，
    在 Milvus 服务端自动完成：
      - 中文分词（analyzer_params type=chinese）
      - BM25 分值计算
      - 稀疏向量存储（sparse 字段）

    enable_match=True 启用 BM25 的 match 搜索类型
    （基于词匹配的文本检索，与向量检索互补）。

    Returns:
        langchain_milvus.BM25BuiltInFunction 实例

    调用顺序：mini-rag 流程 -> bm25_function()。
    """
    from langchain_milvus import BM25BuiltInFunction

    return BM25BuiltInFunction(
        input_field_names="text",           # 输入：Milvus 中存储原始文本的字段
        output_field_names="sparse",        # 输出：Milvus 中存储稀疏向量的字段
        analyzer_params={"type": "chinese"},  # 使用 Milvus 内置中文分词器
        enable_match=True,                  # 启用基于词匹配的 BM25 检索
    )


def hybrid_index_params() -> list[dict[str, object]]:
    """返回 Dense + Sparse 混合检索的显式索引配置。

    Dense 字段使用 HNSW，Sparse 字段使用 AUTOINDEX + BM25。

    调用顺序：mini-rag 流程 -> hybrid_index_params()。
    """
    return [
        {
            "index_type": "HNSW",
            "metric_type": "L2",
            "params": {"M": HNSW_M, "efConstruction": HNSW_EF_CONSTRUCTION},
        },
        {"index_type": "AUTOINDEX", "metric_type": "BM25", "params": {}},
    ]


def hybrid_search_params() -> list[dict[str, object]]:
    """返回与混合索引对应的搜索参数。

    调用顺序：mini-rag 流程 -> hybrid_search_params()。
    """
    return [
        {"metric_type": "L2", "params": {"ef": HNSW_EF}},
        {"metric_type": "BM25", "params": {}},
    ]


def connection_args(alias: str) -> dict[str, str]:
    """构建 LangChain Milvus SDK 的连接参数字典。

    alias 用于区分同一进程内连接到不同 Milvus 集合的连接别名，
    避免连接池冲突。

    Args:
        alias: 连接别名（每个 Milvus 集合使用不同的别名）

    Returns:
        包含 uri 和 alias 的连接参数字典

    调用顺序：mini-rag 流程 -> connection_args()。
    """
    return {"uri": get_settings().milvus_uri, "alias": alias}


def drop_collection(collection_name: str) -> None:
    """删除指定的 Milvus 集合。

    仅在集合存在时执行删除操作，不会因集合不存在而报错。
    用于知识库重建时的清理步骤（rebuild --reset-collections）。

    Args:
        collection_name: 待删除的 Milvus 集合名称

    调用顺序：mini-rag 流程 -> drop_collection()。
    """
    from pymilvus import MilvusClient

    client = MilvusClient(uri=get_settings().milvus_uri)
    if client.has_collection(collection_name):
        client.drop_collection(collection_name)


def build_filter_expr(*, source_filter: str | None, kb_version: str) -> str:
    """构建 Mini RAG 的 Milvus 标量过滤表达式。

    过滤条件通过 AND 逻辑连接，包含以下维度：
      1. kb_version 版本过滤 — 只检索指定版本的知识库数据
      2. tenant_id / dataset_id 数据隔离 — 多租户隔离（精简版固定 default）
      3. visibility 可见性过滤 — public 始终可见
      4. allowed_roles 角色过滤 — Milvus array_contains 语法
      5. source 来源过滤 — 按业务来源（hr / it / finance）筛选

    Milvus 表达式语法参考：
      https://milvus.io/docs/boolean.md

    Args:
        source_filter: 来源名称（如 "hr"），None 表示检索所有 valid_sources
        kb_version:    知识库版本 ID（用于数据隔离）

    Returns:
        完整的 Milvus 标量过滤表达式字符串

    Raises:
        ValueError: source_filter 的值不在 SCENARIO.valid_sources 中

    调用顺序：mini-rag 流程 -> build_filter_expr()。
    """
    settings = get_settings()

    # 构建可见性过滤条件
    # public 始终可见；internal/private 只对匹配的角色可见
    allowed_visibility = ["public"]
    if settings.visibility in {"internal", "private"}:
        allowed_visibility.append(settings.visibility)
    visibility_expr = " or ".join(f'visibility == "{escape_expr_value(item)}"' for item in allowed_visibility)

    # 基本过滤条件：版本 + 租户 + 数据集 + 可见性 + 角色
    parts = [
        f'kb_version == "{escape_expr_value(kb_version)}"',
        f'tenant_id == "{escape_expr_value(settings.tenant_id)}"',
        f'dataset_id == "{escape_expr_value(settings.dataset_id)}"',
        f"({visibility_expr})",
        f'(array_contains(allowed_roles, "{escape_expr_value(settings.allowed_role)}"))',
    ]

    # 来源过滤：精确匹配或 IN 列表
    if source_filter:
        if source_filter not in SCENARIO.valid_sources:
            raise ValueError(f"Invalid source_filter: {source_filter}")
        parts.append(f'source == "{escape_expr_value(source_filter)}"')
    else:
        allowed = ", ".join(f'"{escape_expr_value(source)}"' for source in SCENARIO.valid_sources)
        parts.append(f"source in [{allowed}]")

    return " and ".join(parts)


def normalize_queries(queries: list[str]) -> list[str]:
    """清洗查询变体列表：去除空白项和重复项，保持原有顺序。

    每个查询变体依次处理：
      1. 转为字符串并去除首尾空格
      2. 空字符串跳过
      3. 与已存在的变体去重（保留首次出现的顺序）

    Args:
        queries: 原始查询变体列表

    Returns:
        清洗后的查询变体列表

    调用顺序：mini-rag 流程 -> normalize_queries()。
    """
    result: list[str] = []
    for query in queries:
        cleaned = str(query or "").strip()
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result


def document_key(document: Document) -> str:
    """从 LangChain Document 中提取唯一去重键。

    优先顺序：
      1. metadata 中的 chunk_id（文档切分后的文本块 ID）
      2. metadata 中的 faq_id（FAQ 文档的 ID）
      3. page_content 的前 120 个字符（备选去重标识）

    chunk_id 和 faq_id 是入库时生成的稳定哈希值，
    比文本内容更适合作为去重键。

    Args:
        document: LangChain Document 对象

    Returns:
        去重键字符串

    调用顺序：mini-rag 流程 -> document_key()。
    """
    metadata = document.metadata or {}
    return str(metadata.get("chunk_id") or metadata.get("faq_id") or document.page_content[:120])


def rerank(query: str, hits: list[RetrievalHit], top_n: int) -> list[RetrievalHit]:
    """使用 CrossEncoder Reranker 对检索结果精排。

    CrossEncoder 相比 Bi-Encoder（Dense Retrieval）的优势：
      - 将 query 和 document 拼接后同时输入模型
      - 能捕获 query-document 之间的细粒度语义交互
      - 精度更高，但计算量更大
      - 适合在粗召回（Dense/BM25）之后做精排

    执行流程：
      1. 构建 (query, document_content) 拼接对
      2. CrossEncoder 批量打分
      3. 按分数降序排列
      4. 截取前 top_n 条

    Args:
        query:  用户查询文本（用于与每个文档拼接打分）
        hits:   粗召回结果列表（通常 20-50 条）
        top_n:  精排后保留的结果数量（如 8 条）

    Returns:
        精排后的检索命中列表（已按分数降序排列）
    """
    if not hits:
        return []
    # 构建 query-document 拼接对：CrossEncoder 对每对联合编码打分
    pairs = [(query, hit.document.page_content) for hit in hits]
    # CrossEncoder 批量预测相关性分数
    scores = get_reranker().predict(pairs)
    # 按分数降序排列，取 top_n
    reranked = [
        RetrievalHit(document=hit.document, score=float(score))
        for hit, score in sorted(zip(hits, scores), key=lambda item: float(item[1]), reverse=True)
    ]
    return reranked[:top_n]


class MiniMilvusStore:
    """Mini RAG 的 Milvus 向量存储封装。

    每个实例对应一个 Milvus 集合（FAQ 集合或 Doc 集合），
    内部通过 langchain_milvus.Milvus 类连接 Milvus 服务。

    关键特性：
      - 懒加载：store 属性首次访问时才创建 Milvus 连接
      - 双向量字段：Dense（BGE-M3）+ Sparse（BM25 服务端计算）
      - Dynamic Field 启用：metadata 中的标量字段自动映射
      - Session 一致性：写入后立即可读

    使用方法：
      faq_store = MiniMilvusStore("faq_collection_name")
      result = faq_store.search_many(["查询1", "查询2"], k=10, ...)

    主要方法：
      - add_documents(): 写入文档到 Milvus 集合
      - search_many():   多查询变体混合检索 + 去重 + Reranker 精排

    调用顺序：mini-rag 流程 -> MiniMilvusStore。
    """

    def __init__(self, collection_name: str) -> None:
        """初始化 MiniMilvusStore。

        此时不会创建 Milvus 连接，真正的连接在首次访问 store 属性时建立（懒加载）。

        Args:
            collection_name: Milvus 集合名称

        调用顺序：mini-rag 流程 -> MiniMilvusStore.__init__()。
        """
        self.collection_name = collection_name
        self._store = None  # 懒加载模式：None 表示尚未创建连接

    @property
    def store(self):
        """懒加载的 LangChain Milvus 向量存储实例（首次访问时创建）。

        Milvus 实例配置说明：
          - embedding_function: BGE-M3 Dense Embedding
          - builtin_function:   服务端 BM25 稀疏向量生成
          - vector_field: ["dense", "sparse"] — 双向量字段（混合索引）
          - text_field: "text" — 存储文档原始文本的字段
          - primary_field: "pk" — 主键字段（自定义 ID）
          - auto_id=False: 使用外部传入的 ID（便于去重和追溯）
          - enable_dynamic_field=True: metadata 中的标量字段自动注册
          - consistency_level="Session": 会话级一致性
          - drop_old=False: 不自动删除已有集合

        Returns:
            langchain_milvus.Milvus 实例

        调用顺序：mini-rag 流程 -> MiniMilvusStore.store()。
        """
        from langchain_milvus import Milvus

        if self._store is None:
            self._store = Milvus(
                embedding_function=get_embeddings(),
                builtin_function=bm25_function(),
                collection_name=self.collection_name,
                connection_args=connection_args(f"mini_{self.collection_name}"),
                vector_field=["dense", "sparse"],
                index_params=hybrid_index_params(),
                search_params=hybrid_search_params(),
                text_field="text",
                primary_field="pk",
                auto_id=False,
                enable_dynamic_field=True,
                consistency_level="Session",
                drop_old=False,
            )
            self._validate_hybrid_schema()
        return self._store

    def _validate_hybrid_schema(self) -> None:
        """校验 collection 是否仍然是当前简易案例需要的 Hybrid Search 结构。"""
        collection = self.store.col
        if collection is None:
            return
        current = {
            str(index.field_name): dict(index.params or {})
            for index in list(getattr(collection, "indexes", []) or [])
            if getattr(index, "field_name", None)
        }
        expected = hybrid_index_params()
        dense = current.get("dense")
        sparse = current.get("sparse")
        problems: list[str] = []
        if not dense:
            problems.append("缺少 dense 索引")
        elif str(dense.get("index_type")) != str(expected[0]["index_type"]):
            problems.append(f"dense 索引类型应为 {expected[0]['index_type']}")
        if not sparse:
            problems.append("缺少 sparse 索引")
        elif str(sparse.get("metric_type")) != str(expected[1]["metric_type"]):
            problems.append(f"sparse 索引 metric 应为 {expected[1]['metric_type']}")
        if problems:
            raise RuntimeError(
                f"Milvus collection `{self.collection_name}` 的索引结构不是当前简易案例所需的 HNSW + BM25。"
                f"{'；'.join(problems)}。请先删除旧集合，再使用 --reset-collections 重新入库。"
            )

    def add_documents(self, documents: list[Document], ids: list[str]) -> list[str]:
        """将文档写入 Milvus 集合。

        每个文档在写入时同时生成：
          1. Dense 向量 — BGE-M3 本地模型编码
          2. Sparse 向量 — Milvus 服务端 BM25 编码
          3. 标量字段 — metadata 中的 key-value 自动映射到动态字段

        Args:
            documents: LangChain Document 列表
            ids:       对应的唯一 ID 列表（长度必须与 documents 一致）

        Returns:
            成功写入的 ID 列表（写入失败时异常向上抛出）

        调用顺序：mini-rag 流程 -> MiniMilvusStore.add_documents()。
        """
        if not documents:
            return []
        return self.store.add_documents(documents=documents, ids=ids)

    def search_many(
        self,
        queries: list[str],
        *,
        k: int,
        source_filter: str | None,
        kb_version: str,
        source_type: Literal["faq", "doc"],
        rerank_hits: bool = True,
    ) -> RetrievalResult:
        """多查询变体混合检索 — MiniMilvusStore 的核心检索入口。

        完整检索流程：
          1. 清洗查询变体（去空白、去重）
          2. 构建 Milvus 标量过滤表达式（版本 + 数据隔离 + 来源）
          3. 对每个查询变体执行 hybrid search（Dense + BM25）
          4. 多路结果合并去重（相同文档保留最高分）
          5. 按分数降序排列
          6. 可选：CrossEncoder Reranker 精排
          7. 封装为 RetrievalResult（含命中列表、最高分、耗时）

        去重策略：
          多个查询变体的结果可能包含相同文档，
          按 chunk_id / faq_id 去重，保留最高分数。

        Args:
            queries:      查询变体列表（每个变体独立检索后合并去重）
            k:            每个变体检索的 top_k 数量
            source_filter: 来源筛选（如 "hr"），None 表示检索全部来源
            kb_version:   知识库版本标识（用于标量过滤）
            source_type:  来源类型（"faq" 或 "doc"），用于结果标记
            rerank_hits:  是否启用 CrossEncoder Reranker 精排

        Returns:
            RetrievalResult 对象（含命中列表、最高分、耗时等信息）

        调用顺序：mini-rag 流程 -> MiniMilvusStore.search_many()。
        """
        started = time.perf_counter()
        timings: dict[str, float] = {}
        # 第一步：清洗查询变体
        searched_queries = normalize_queries(queries)
        # 第二步：根据业务分类和知识库版本号构建 Milvus 检索过滤条件
        expr = build_filter_expr(source_filter=source_filter, kb_version=kb_version)
        merged: dict[str, RetrievalHit] = {}

        # 第三步：逐个查询变体执行混合检索 + 合并去重
        hybrid_started = time.perf_counter()
        for query in searched_queries:
            # 对每个查询变体执行 Milvus 混合检索（Dense + BM25 双路）
            # 例如变体列表：["报销流程是什么", "报销 SOP", "报销处理步骤"]
            docs_with_scores = self.store.similarity_search_with_score(
                query=query,
                k=k,
                expr=expr,
                **HYBRID_RANKER_KWARGS,
            )
            for document, score in docs_with_scores:
                hit = RetrievalHit(document=document, score=float(score))
                key = document_key(document)
                # 去重：同一文档被多个变体命中时，保留最高分数
                previous = merged.get(key)
                if previous is None or hit.score > previous.score:
                    merged[key] = hit
        timings["hybrid_search_ms"] = round((time.perf_counter() - hybrid_started) * 1000, 2)

        # 第四步：按分数降序排列所有命中结果
        hits = sorted(merged.values(), key=lambda item: item.score, reverse=True)

        # 第五步：CrossEncoder Reranker 精排（可选）
        if rerank_hits and hits:
            rerank_started = time.perf_counter()
            hits = rerank(searched_queries[0], hits, get_settings().rerank_top_n)
            timings["rerank_ms"] = round((time.perf_counter() - rerank_started) * 1000, 2)
        else:
            timings["rerank_ms"] = 0.0

        # 计算总耗时（毫秒）
        elapsed_ms = (time.perf_counter() - started) * 1000
        timings["total_ms"] = round(elapsed_ms, 2)
        return RetrievalResult(
            source_type=source_type,
            query=searched_queries[0] if searched_queries else "",
            hits=hits,
            elapsed_ms=elapsed_ms,
            timings=timings,
        )


def faq_store() -> MiniMilvusStore:
    """获取 FAQ 集合的 Milvus 存储实例。

    FAQ 集合存储企业常见问题及其标准答案，
    检索命中高置信度时可直接返回标准答案（faq_direct_answer），
    无需走后续的文档检索和 LLM 生成路径。

    Returns:
        指向 FAQ 集合的 MiniMilvusStore 实例

    调用顺序：mini-rag 流程 -> faq_store()。
    """
    return MiniMilvusStore(SCENARIO.faq_collection)


def doc_store() -> MiniMilvusStore:
    """获取文档集合的 Milvus 存储实例。

    文档集合存储业务文档切分后的文本块（chunk），
    检索结果作为 LLM 生成答案时的参考上下文。

    Returns:
        指向 Doc 集合的 MiniMilvusStore 实例

    调用顺序：mini-rag 流程 -> doc_store()。
    """
    return MiniMilvusStore(SCENARIO.doc_collection)
