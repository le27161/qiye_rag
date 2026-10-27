"""Mini RAG 单元测试 — 无需启动 Milvus 或 MySQL 即可运行的快速验证。

测试覆盖：
  1. 场景配置完整性 — 验证 enterprise_knowledge 场景数据真实存在
  2. 业务文件验证 — 确认三个来源各自有数据文件
  3. FAQ 加载完整性 — 验证 FAQ 文档的元数据字段齐全、数据隔离正确
  4. 版本 ID 格式 — 确认版本 ID 与企业级项目约定一致
  5. 检索过滤表达式 — 验证 Milvus 过滤条件包含全部数据边界
  6. 查询变体和追问检测 — 验证改写逻辑的规则匹配

运行方式：
  cd mini-rag
  python -m pytest tests/test_qa_core.py -v

注意：这些测试只验证纯函数逻辑，不依赖 Milvus / MySQL 的运行时连接。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from langchain_core.documents import Document


# 将 mini-rag 根目录加入 Python 搜索路径
MINI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MINI_ROOT))

from qa_core.config import SCENARIO
from qa_core.ingest import load_faq_documents
from qa_core.kb_version import new_kb_version
from qa_core.loaders import iter_source_files
from qa_core.prompts import generate_answer
from qa_core.query import generate_variants, needs_rewrite
from qa_core.retrieval import MiniMilvusStore, build_filter_expr, hybrid_index_params, hybrid_search_params, rerank
from qa_core.schemas import RetrievalHit


def test_scenario_uses_real_enterprise_data() -> None:
    """验证场景配置指向真实的 enterprise_knowledge 数据。

    检查要点：
      - scenario_id 为 "enterprise_knowledge"
      - FAQ CSV 文件存在
      - 数据根目录存在
      - valid_sources 包含 hr / it / finance 三个来源

    调用顺序：mini-rag 流程 -> test_scenario_uses_real_enterprise_data()。
    """
    assert SCENARIO.scenario_id == "enterprise_knowledge"
    assert SCENARIO.faq_csv_path.exists()
    assert SCENARIO.data_root.exists()
    assert set(SCENARIO.valid_sources) == {"hr", "it", "finance"}


def test_source_files_are_real_business_files() -> None:
    """验证每个数据来源目录下都有实际的业务文件。

    三个来源（hr / it / finance）各自至少有一个文档文件。
    如果此项失败，请检查 scenarios/enterprise_knowledge/data/{source}_data/ 目录。

    调用顺序：mini-rag 流程 -> test_source_files_are_real_business_files()。
    """
    counts = {source: len(iter_source_files(SCENARIO.data_root, source)) for source in SCENARIO.valid_sources}
    assert counts["hr"] > 0, f"HR 来源目录无文件"
    assert counts["it"] > 0, f"IT 来源目录无文件"
    assert counts["finance"] > 0, f"Finance 来源目录无文件"


def test_faq_documents_include_answers_and_versions() -> None:
    """验证 FAQ 加载函数生成的文档包含所有必要元数据。

    检查要点：
      - 文档列表非空
      - 文档数和 ID 数一致
      - kb_version 被正确写入
      - answer 字段存在（用于 FAQ 直出）
      - 数据隔离字段正确（tenant_id / dataset_id / visibility / allowed_roles）
      - 模型版本字段存在（embedding_model_version / chunk_schema_version）

    调用顺序：mini-rag 流程 -> test_faq_documents_include_answers_and_versions()。
    """
    docs, ids = load_faq_documents("test_version")
    assert docs, "FAQ CSV 无有效数据行"
    assert len(docs) == len(ids), "文档数和 ID 数不一致"
    assert docs[0].metadata["kb_version"] == "test_version"
    assert docs[0].metadata["answer"], "FAQ 文档缺少 answer 字段"
    assert docs[0].metadata["tenant_id"] == "default"
    assert docs[0].metadata["dataset_id"] == "default"
    assert docs[0].metadata["visibility"] == "public"
    assert docs[0].metadata["allowed_roles"] == ["public"]
    assert docs[0].metadata["embedding_model_version"]
    assert docs[0].metadata["chunk_schema_version"]


def test_kb_version_id_matches_full_project_shape() -> None:
    """验证版本 ID 格式与企业级项目约定一致。

    版本 ID 应符合：kb_{scenario_id}_{timestamp}_{hash} 格式。
    例如：kb_enterprise_knowledge_20250618_143052_a1b2c3d4

    注意：ID 不能以 "mini_" 开头（这会导致与企业级版本命名不兼容）。

    调用顺序：mini-rag 流程 -> test_kb_version_id_matches_full_project_shape()。
    """
    version = new_kb_version()
    assert version.startswith("kb_enterprise_knowledge_")
    assert not version.startswith("mini_"), "版本 ID 不应包含 mini_ 前缀"


def test_retrieval_filter_keeps_data_scope_boundary() -> None:
    """验证 Milvus 检索过滤表达式包含完整的数据隔离边界。

    检查过滤条件中包含：
      - kb_version: 版本过滤
      - tenant_id: 租户隔离
      - dataset_id: 数据集隔离
      - visibility: 可见性过滤（public 始终可查）
      - allowed_roles: 角色数组过滤（Milvus array_contains 语法）
      - source: 来源过滤（默认查全部三个来源）

    调用顺序：mini-rag 流程 -> test_retrieval_filter_keeps_data_scope_boundary()。
    """
    expr = build_filter_expr(source_filter=None, kb_version="kb_test")
    assert 'kb_version == "kb_test"' in expr
    assert 'tenant_id == "default"' in expr
    assert 'dataset_id == "default"' in expr
    assert '(visibility == "public")' in expr
    assert 'array_contains(allowed_roles, "public")' in expr
    assert 'source in ["hr", "it", "finance"]' in expr


def test_query_variants_and_followup_detection() -> None:
    """验证查询变体生成和追问检测的逻辑正确性。

    测试场景：
      1. 有历史 + 短追问 + 包含追问问关键词 → needs_rewrite 返回 True
      2. 包含 "流程" 的查询 → 生成包含 "步骤" 的变体
      3. 变体数量受 Mini RAG RETRIEVAL_VARIANT_MAX 约束

    调用顺序：mini-rag 流程 -> test_query_variants_and_followup_detection()。
    """
    # 追问检测：短追问 + 有关键词 → 需要改写
    assert needs_rewrite("那审批呢", ["报销流程是什么"])

    # 变体生成读取 mini-rag/config/rules.toml：流程 → SOP / 处理步骤 / 办理流程
    variants = generate_variants("报销流程是什么")
    assert variants[0] == "报销流程是什么"  # 原始查询始终保留
    assert "报销SOP是什么" in variants
    assert len(variants) <= 3  # Mini RAG 默认 RETRIEVAL_VARIANT_MAX=2，即原问题 + 2 个额外变体


def test_hybrid_index_params_use_hnsw_and_bm25() -> None:
    """验证 Mini RAG 的 Milvus 混合检索显式使用 HNSW + BM25。"""
    dense_index, sparse_index = hybrid_index_params()
    dense_search, sparse_search = hybrid_search_params()

    assert dense_index["index_type"] == "HNSW"
    assert dense_index["metric_type"] == "L2"
    assert dense_index["params"]["M"] == 16
    assert dense_index["params"]["efConstruction"] == 200

    assert sparse_index["index_type"] == "AUTOINDEX"
    assert sparse_index["metric_type"] == "BM25"

    assert dense_search["metric_type"] == "L2"
    assert dense_search["params"]["ef"] == 64
    assert sparse_search["metric_type"] == "BM25"


def test_rerank_skips_model_when_no_candidates(monkeypatch) -> None:
    """候选为空时不应加载或调用 Reranker 模型。"""
    called = False

    def fail_if_called():
        nonlocal called
        called = True
        raise AssertionError("empty rerank should not load model")

    monkeypatch.setattr("qa_core.retrieval.get_reranker", fail_if_called)

    assert rerank("报销流程", [], top_n=3) == []
    assert called is False


def test_rerank_sorts_by_cross_encoder_score(monkeypatch) -> None:
    """验证 Reranker 按 CrossEncoder 分数降序排序并执行 top_n 截断。"""

    class FakeReranker:
        def predict(self, pairs):
            assert [pair[0] for pair in pairs] == ["VPN 连不上怎么办"] * 3
            return [0.12, 0.93, 0.41]

    monkeypatch.setattr("qa_core.retrieval.get_reranker", lambda: FakeReranker())

    hits = [
        RetrievalHit(Document(page_content="检查报销发票", metadata={"chunk_id": "finance"}), 0.8),
        RetrievalHit(Document(page_content="重启 VPN 客户端", metadata={"chunk_id": "vpn"}), 0.7),
        RetrievalHit(Document(page_content="联系服务台重置密码", metadata={"chunk_id": "support"}), 0.6),
    ]

    result = rerank("VPN 连不上怎么办", hits, top_n=2)

    assert [hit.document.metadata["chunk_id"] for hit in result] == ["vpn", "support"]
    assert [hit.score for hit in result] == [0.93, 0.41]


def test_generate_answer_returns_insufficient_context_without_llm(monkeypatch) -> None:
    """没有上下文时直接返回资料不足，不应浪费 LLM 调用。"""

    def fail_if_called():
        raise AssertionError("generate_answer should not call LLM without context")

    monkeypatch.setattr("qa_core.prompts.get_chat_model", fail_if_called)

    answer = generate_answer("未知制度是什么", [], [], max_context_chars=500)

    assert "资料不足" in answer


def test_ask_endpoint_direct_answer_shape() -> None:
    """验证 /ask 直接回答路径的 API 响应结构，不依赖 Milvus、MySQL 或 LLM。"""
    from fastapi.testclient import TestClient
    from app import app

    response = TestClient(app).post("/ask", json={"query": "你好", "history": [], "source_filter": None})

    assert response.status_code == 200
    payload = response.json()
    assert payload["route"] == "direct_answer"
    assert payload["sources"] == []
    assert payload["query_variants"] == ["你好"]
    assert "timings" in payload["retrieval"]


def test_search_many_reports_hybrid_and_rerank_timings(monkeypatch) -> None:
    """验证混合检索结果会保留召回和 Reranker 的分阶段耗时。"""

    class FakeMilvus:
        def similarity_search_with_score(self, *, query, k, expr, **kwargs):
            assert k == 5
            assert 'kb_version == "kb_test"' in expr
            assert kwargs["ranker_type"] == "weighted"
            if "费用" in query:
                return [
                    (Document(page_content="报销需要发票和审批单", metadata={"chunk_id": "expense"}), 0.91),
                ]
            return [
                (Document(page_content="报销需要发票和审批单", metadata={"chunk_id": "expense"}), 0.42),
                (Document(page_content="VPN 故障请重启客户端", metadata={"chunk_id": "vpn"}), 0.33),
            ]

    def fake_rerank(query, hits, top_n):
        assert query == "报销流程"
        assert top_n >= 2
        return [RetrievalHit(hit.document, hit.score + 1.0) for hit in hits]

    monkeypatch.setattr("qa_core.retrieval.rerank", fake_rerank)

    store = MiniMilvusStore("fake_collection")
    store._store = FakeMilvus()

    result = store.search_many(
        ["报销流程", "费用报销流程"],
        k=5,
        source_filter=None,
        kb_version="kb_test",
        source_type="doc",
        rerank_hits=True,
    )

    assert [hit.document.metadata["chunk_id"] for hit in result.hits] == ["expense", "vpn"]
    assert result.hits[0].score == pytest.approx(1.91)
    assert result.timings["hybrid_search_ms"] >= 0
    assert result.timings["rerank_ms"] >= 0
    assert result.timings["total_ms"] >= 0
