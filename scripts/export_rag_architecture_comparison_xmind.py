"""Export a source-evidence-based KnowForge vs EduRAG comparison XMind.

The mind map is designed for presentation:
    conclusion -> reason -> source evidence -> engineering impact -> judgement

Usage:
    python scripts/export_rag_architecture_comparison_xmind.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.export_xmind import write_xmind


PALETTE = {
    "root": "#1d4ed8",
    "conclusion": "#7c3aed",
    "edurag": "#d97706",
    "knowforge": "#059669",
    "evidence": "#2563eb",
    "risk": "#dc2626",
    "impact": "#be123c",
    "recommend": "#0f766e",
}


def node(
    node_id: str,
    title: str,
    note: str = "",
    color: str = "evidence",
    children: list[dict] | None = None,
) -> dict:
    """构造 XMind 思维导图节点字典。

    调用顺序：命令行入口 -> node()。
    """
    item = {
        "id": node_id,
        "title": title,
        "color": PALETTE[color],
    }
    if note:
        item["note"] = note
    if children:
        item["children"] = children
    return item


TREE = node(
    "root",
    "KnowForge vs EduRAG：有证据的企业级 RAG 架构评价",
    (
        "这张图不是功能清单，而是评价链路：\n"
        "1. 先给结论。\n"
        "2. 再说明为什么。\n"
        "3. 再落到源码证据。\n"
        "4. 最后说明工程影响和课程取舍。\n\n"
        "总判断：EduRAG 适合入门演示；KnowForge 更适合作为企业级 RAG 主项目。"
    ),
    "root",
    [
        node(
            "final_conclusion",
            "0. 总结论：不是功能多少，而是架构边界是否正确",
            (
                "EduRAG 能把 RAG 基础链路跑起来，但 FAQ、缓存、BM25、版本治理之间的边界不够清晰。\n"
                "KnowForge 更重，但把 FAQ/Doc 检索、知识库版本、数据隔离、质量门禁和评测闭环放进同一套体系。"
            ),
            "conclusion",
            [
                node(
                    "edurag_short_judgement",
                    "EduRAG：演示价值高，企业架构成熟度不足",
                    "适合第一阶段用于理解 RAG 由哪些组件组成；不适合直接作为企业级 RAG 架构范本。",
                    "edurag",
                ),
                node(
                    "knowforge_short_judgement",
                    "KnowForge：复杂度更高，但企业工程闭环更完整",
                    "适合讲多场景、版本治理、数据隔离、质量门禁、评测、反馈和生产诊断。",
                    "knowforge",
                ),
                node(
                    "course_strategy",
                    "课程建议：mini-rag 入门，KnowForge 进阶",
                    "mini-rag 先解决上手门槛；KnowForge 承接企业级架构和工程治理。",
                    "recommend",
                ),
            ],
        ),
        node(
            "faq_chain",
            "1. FAQ 检索架构：EduRAG 最大问题在这里",
            (
                "判断依据：EduRAG 把 FAQ 做成 MySQL + Redis + Python 进程内 BM25；KnowForge 把 FAQ 也纳入 Milvus Hybrid Search。\n"
                "这不是实现细节差异，而是系统边界差异。"
            ),
            "risk",
            [
                node(
                    "faq_edurag_conclusion",
                    "结论：EduRAG 的 FAQ 与文档 RAG 是两套检索系统",
                    "FAQ 先走 BM25，命中则直接返回；未命中才进入 RAG。文档走 Milvus。两套链路天然割裂。",
                    "risk",
                    [
                        node(
                            "faq_edurag_reason",
                            "原因：FAQ 没有进入统一向量库治理",
                            "FAQ 存 MySQL，Redis 缓存问题和答案，BM25 索引在 Python 进程内构建。",
                            "edurag",
                        ),
                        node(
                            "faq_edurag_evidence",
                            "源码证据：BM25Search + MySQLClient + RedisClient",
                            (
                                "D:/BaiduNetdiskDownload/南京1期-RAG应用开发-Rdurag/南京1/学习者端/04-代码/0001.项目代码/"
                                "integrated_qa_system/mysql_qa/retrieval/bm25_search.py\n"
                                "- 使用 rank_bm25.BM25Okapi。\n"
                                "- Redis key: qa_original_questions / qa_tokenized_questions。\n"
                                "- MySQL fetch_questions() 拉全部问题。\n"
                                "- search(query, threshold=0.85) 决定是否 FAQ 直出。\n\n"
                                "integrated_qa_system/new_main.py\n"
                                "- query() 中先 bm25_search.search()。\n"
                                "- need_rag=True 时才调用 rag_system.generate_answer()。"
                            ),
                            "evidence",
                        ),
                        node(
                            "faq_edurag_impact",
                            "工程影响：版本、权限、诊断和评测都难统一",
                            (
                                "当 FAQ 和 Doc 不在同一检索体系内，后续要做 kb_version、tenant、source、visibility、role、trace、"
                                "quality gate、evaluation gate 时，需要两套实现和两套解释。"
                            ),
                            "impact",
                        ),
                    ],
                ),
                node(
                    "faq_knowforge_conclusion",
                    "结论：KnowForge 的 FAQ 和 Doc 在同一检索治理体系内",
                    "FAQ 和 Doc 使用不同 collection，但都通过 MilvusHybridStore 执行 dense + sparse hybrid search。",
                    "knowforge",
                    [
                        node(
                            "faq_knowforge_evidence",
                            "源码证据：search_faq / search_doc 使用同一类过滤参数",
                            (
                                "D:/workspace/knowforge-rag-platform/qa_core/pipeline/retrieval_steps.py\n"
                                "- search_faq() 调用 get_faq_store().search_many(...)\n"
                                "- search_doc() 调用 get_doc_store().search_many(...)\n"
                                "- 两者都传 kb_version、valid_sources、data_scope、source_type。\n\n"
                                "D:/workspace/knowforge-rag-platform/qa_core/retrieval/store.py\n"
                                "- MilvusHybridStore 封装 dense + sparse hybrid search。\n"
                                "- build_source_expr() 合并 source/kb_version/DataScope。"
                            ),
                            "evidence",
                        ),
                        node(
                            "faq_knowforge_impact",
                            "工程影响：统一检索、统一过滤、统一诊断",
                            "FAQ、文档、版本、权限、重排、引用来源和诊断信息都能走同一套解释框架。",
                            "recommend",
                        ),
                    ],
                ),
            ],
        ),
        node(
            "bm25_chain",
            "2. BM25 方案：不是能用就等于适合企业级",
            (
                "注意：EduRAG 不是从零手写 BM25 公式，而是使用 rank_bm25 库。\n"
                "但它的 BM25 索引由应用进程自己维护，这才是架构问题。"
            ),
            "risk",
            [
                node(
                    "bm25_edurag_problem",
                    "EduRAG：进程内 BM25 索引",
                    (
                        "服务启动或初始化时从 MySQL/Redis 得到问题列表，在 Python 进程中构建 BM25Okapi。\n"
                        "多个 API 副本意味着多个 BM25 索引副本。"
                    ),
                    "edurag",
                    [
                        node(
                            "bm25_edurag_evidence",
                            "源码证据：BM25Okapi(tokenized_questions)",
                            (
                                "bm25_search.py\n"
                                "- from rank_bm25 import BM25Okapi\n"
                                "- self.bm25 = BM25Okapi(tokenized_questions)\n"
                                "- scores = self.bm25.get_scores(query_tokens)"
                            ),
                            "evidence",
                        ),
                        node(
                            "bm25_edurag_impact",
                            "工程影响：扩容、更新和一致性成本高",
                            (
                                "FAQ 数据变更后，需要考虑 Redis 缓存、MySQL 数据、进程内 BM25 索引三者一致。\n"
                                "如果多个服务副本同时运行，索引刷新和缓存失效会更复杂。"
                            ),
                            "impact",
                        ),
                    ],
                ),
                node(
                    "bm25_threshold_problem",
                    "EduRAG：softmax 阈值不稳定",
                    (
                        "BM25 原始分数被 softmax 成概率分布后，再用 0.85 判断是否直出。\n"
                        "这个值受候选问题数量和分数分布影响，不能稳定表达“是否高度匹配”。"
                    ),
                    "risk",
                    [
                        node(
                            "bm25_threshold_evidence",
                            "源码证据：_softmax(scores) + threshold=0.85",
                            (
                                "bm25_search.py\n"
                                "- softmax_scores = self._softmax(scores)\n"
                                "- best_score = softmax_scores[best_idx]\n"
                                "- if best_score >= threshold: 返回 FAQ 答案"
                            ),
                            "evidence",
                        ),
                        node(
                            "bm25_threshold_impact",
                            "工程影响：FAQ 直出标准不可解释",
                            (
                                "当 FAQ 数量变化时，同一个问题的 softmax top1 可能发生明显变化。\n"
                                "这会导致直出阈值难以调优，也难以向业务方解释。"
                            ),
                            "impact",
                        ),
                    ],
                ),
                node(
                    "bm25_knowforge",
                    "KnowForge：Milvus 内置 BM25 sparse function",
                    "BM25 sparse 召回由 Milvus collection schema 和服务端函数承担，并与 dense 向量统一融合。",
                    "knowforge",
                    [
                        node(
                            "bm25_knowforge_evidence",
                            "源码证据：BM25BuiltInFunction + dense/sparse 双字段",
                            (
                                "qa_core/retrieval/milvus_compat.py\n"
                                "- BM25BuiltInFunction\n\n"
                                "qa_core/retrieval/store.py\n"
                                "- builtin_function=bm25_function()\n"
                                "- vector_field=[\"dense\", \"sparse\"]\n"
                                "- similarity_search_with_score 使用 weighted ranker 融合"
                            ),
                            "evidence",
                        ),
                    ],
                ),
            ],
        ),
        node(
            "mysql_redis_chain",
            "3. MySQL / Redis 边界：EduRAG 把缓存和查询混进主链路",
            "企业级系统中，MySQL 更适合做治理元数据和事务记录，不适合承担语义检索或 FAQ 相似匹配。",
            "risk",
            [
                node(
                    "mysql_edurag",
                    "EduRAG：MySQL 直接参与 FAQ 查询",
                    "jpkb 表保存 subject_name、question、answer；BM25 命中后按 question 精确查 answer。",
                    "edurag",
                    [
                        node(
                            "mysql_edurag_evidence",
                            "源码证据：jpkb 简单表结构",
                            (
                                "mysql_qa/db/mysql_client.py\n"
                                "- CREATE TABLE IF NOT EXISTS jpkb\n"
                                "- question VARCHAR(1000)\n"
                                "- answer VARCHAR(1000)\n"
                                "- fetch_questions(): SELECT question FROM jpkb\n"
                                "- fetch_answer(query): SELECT answer FROM jpkb WHERE question = %s"
                            ),
                            "evidence",
                        ),
                        node(
                            "mysql_edurag_impact",
                            "工程影响：缺少企业知识库治理字段",
                            "没有 scenario_id、source、kb_version、tenant_id、dataset_id、visibility、status、updated_at 等关键字段。",
                            "impact",
                        ),
                    ],
                ),
                node(
                    "redis_edurag",
                    "EduRAG：Redis 增加复杂度，但没有承担搜索能力",
                    "Redis 缓存问题列表和答案，但 BM25 召回仍在 Python 进程内完成。",
                    "edurag",
                    [
                        node(
                            "redis_evidence",
                            "源码证据：answer:{query} 与问题列表缓存",
                            (
                                "mysql_qa/cache/redis_client.py\n"
                                "- set_data/get_data JSON 缓存。\n"
                                "- get_answer(query) 使用 answer:{query}。\n\n"
                                "bm25_search.py\n"
                                "- qa_original_questions\n"
                                "- qa_tokenized_questions"
                            ),
                            "evidence",
                        ),
                        node(
                            "redis_impact",
                            "工程影响：缓存失效缺少版本维度",
                            "缓存 key 没有 kb_version、scenario、source、tenant 等命名空间，FAQ 更新后容易出现旧答案污染。",
                            "impact",
                        ),
                    ],
                ),
                node(
                    "mysql_knowforge",
                    "KnowForge：MySQL 回到治理层",
                    "MySQL 管理 kb_versions、kb_active_versions、history、feedback；语义检索交给 Milvus。",
                    "knowforge",
                    [
                        node(
                            "mysql_knowforge_evidence",
                            "源码证据：kb_versions / kb_active_versions",
                            (
                                "qa_core/governance/kb_versions.py\n"
                                "- KB_VERSIONS_TABLE = kb_versions\n"
                                "- KB_ACTIVE_TABLE = kb_active_versions\n"
                                "- activate_version()\n"
                                "- resolve_active_version()"
                            ),
                            "evidence",
                        ),
                    ],
                ),
            ],
        ),
        node(
            "version_governance_chain",
            "4. 知识库版本治理：企业级 RAG 的分水岭",
            "真实企业项目不能直接覆盖线上知识库，而是候选版本入库、检查、通过后切换 active 指针。",
            "knowforge",
            [
                node(
                    "edurag_version_gap",
                    "EduRAG：缺少完整 active version 闭环",
                    "资料更新、FAQ 更新和线上检索之间缺少候选版本、质量门禁、激活指针、回滚指针。",
                    "risk",
                ),
                node(
                    "knowforge_version_flow",
                    "KnowForge：STAGED -> ACTIVE -> ARCHIVED",
                    "新版本先 STAGED，质量通过后 activate；线上检索只过滤当前 active kb_version。",
                    "knowforge",
                    [
                        node(
                            "version_evidence",
                            "源码证据：版本状态机和 active 指针",
                            (
                                "qa_core/governance/kb_versions.py\n"
                                "- KB_VERSION_STATUS_STAGED\n"
                                "- KB_VERSION_STATUS_ACTIVE\n"
                                "- KB_VERSION_STATUS_ARCHIVED\n"
                                "- activate_version()\n"
                                "- previous_kb_version\n\n"
                                "qa_core/pipeline/runtime.py\n"
                                "- resolve_active_kb_version()\n"
                                "- sync_retrieval_cache_for_active_version()"
                            ),
                            "evidence",
                        ),
                        node(
                            "version_impact",
                            "工程影响：失败版本不污染线上",
                            "门禁失败时新版本不激活；旧 active 继续服务；检索表达式里带 kb_version == 当前 active。",
                            "recommend",
                        ),
                    ],
                ),
            ],
        ),
        node(
            "quality_chain",
            "5. 质量门禁与评测：KnowForge 的企业闭环更完整",
            "企业 RAG 不能只看“能回答”，还要回答是否稳定、资料是否合格、更新是否安全。",
            "knowforge",
            [
                node(
                    "edurag_quality_gap",
                    "EduRAG：有评测探索，但不构成完整上线门禁",
                    "RAGAS 脚本有学习价值，但没有和知识库版本激活、入库报告、接口回归形成强约束闭环。",
                    "edurag",
                ),
                node(
                    "knowforge_quality",
                    "KnowForge：入库质量 + 回归评测 + 性能基线",
                    "把质量检查放到脚本、报告和 gate 中，适合作为企业上线前置条件。",
                    "knowforge",
                    [
                        node(
                            "quality_evidence",
                            "源码证据：quality gate / evaluation gate / performance gate",
                            (
                                "scripts/check_ingestion_quality_gate.py\n"
                                "- failed_files、duplicate_chunks、duplicate_faq_questions 等阈值。\n\n"
                                "scripts/check_evaluation_gate.py\n"
                                "- 读取评测报告，判断是否达标。\n\n"
                                "scripts/check_performance_gate.py\n"
                                "- 性能基线门禁。"
                            ),
                            "evidence",
                        ),
                        node(
                            "quality_impact",
                            "工程影响：能解释为什么可以上线",
                            "不是“入库成功就上线”，而是资料质量、问答效果、接口和性能都达标后再激活。",
                            "recommend",
                        ),
                    ],
                ),
            ],
        ),
        node(
            "presentation_chain",
            "6. 课程设计判断：怎么讲才合理",
            "最终不是否定 EduRAG，而是明确它和 KnowForge 在课程中的位置。",
            "recommend",
            [
                node(
                    "teach_edurag",
                    "EduRAG 适合讲：RAG 组件初识",
                    "用于展示 MySQL FAQ、Redis 缓存、BM25、Milvus、LLM 如何串起来，但要明确它不是企业级最佳实践。",
                    "edurag",
                ),
                node(
                    "teach_mini_rag",
                    "mini-rag 适合讲：真实但精简的最小闭环",
                    "连接真实 Milvus + MySQL + BGE + LLM，但裁剪复杂治理能力，降低入门难度。",
                    "recommend",
                ),
                node(
                    "teach_knowforge",
                    "KnowForge 适合讲：企业级架构主项目",
                    "讲多场景、版本治理、DataScope、质量门禁、评测、反馈、可观测性。",
                    "knowforge",
                ),
                node(
                    "teach_warning",
                    "讲解重点：不要只说功能多，要说为什么这么设计",
                    "每个结论都要回到：源码实现 -> 工程问题 -> 企业场景影响 -> 最终设计判断。",
                    "conclusion",
                ),
            ],
        ),
    ],
)


CUSTOMER_REPORT_TREE = node(
    "customer_report_root",
    "KnowForge 多场景企业级 RAG vs EduRAG：客户汇报版",
    (
        "汇报目标：明确说明 KnowForge 多场景企业级 RAG 项目是什么架构，EduRAG 项目是什么架构，"
        "两者在企业级落地能力上差在哪里。\n"
        "表达策略：正面对比，不回避 EduRAG 的架构短板；同时突出 KnowForge 的架构优势、功能优势和企业级特点。\n\n"
        "核心结论：EduRAG 更适合演示串联；KnowForge 多场景企业级 RAG 更适合企业级知识库问答平台建设。"
    ),
    "root",
    [
        node(
            "report_opening",
            "0. 汇报主结论：KnowForge 是多场景企业级 RAG，EduRAG 是演示型 RAG",
            (
                "KnowForge 多场景企业级 RAG 解决的是企业真实落地中的知识库治理问题：\n"
                "资料如何入库、版本如何发布、权限如何隔离、检索如何统一、回答如何追溯、效果如何评测、反馈如何闭环。\n\n"
                "EduRAG 项目更偏演示，适合理解 MySQL、Redis、BM25、Milvus、LLM 如何串联；"
                "KnowForge 项目更偏企业级平台，适合长期运营和持续迭代。"
            ),
            "conclusion",
            [
                node(
                    "opening_demo_vs_platform",
                    "EduRAG：演示型 RAG",
                    "重点是把 MySQL FAQ、Redis 缓存、BM25、Milvus 文档检索和 LLM 生成串起来，帮助学习者理解 RAG 基础组件。",
                    "edurag",
                ),
                node(
                    "opening_enterprise_platform",
                    "KnowForge：多场景企业级 RAG",
                    "覆盖入库、质量、版本、权限、检索、生成、引用、评测、反馈、诊断。",
                    "knowforge",
                ),
                node(
                    "opening_customer_sentence",
                    "客户表达：KnowForge 交付的是可治理、可追溯、可评测的 RAG 工程体系",
                    "这句话适合作为汇报开场或结尾，帮助客户把项目定位从“问答页面”提升为“企业知识平台”。",
                    "recommend",
                ),
            ],
        ),
        node(
            "architecture_advantages",
            "1. 架构对比：KnowForge 边界清晰，EduRAG 链路割裂",
            (
                "架构优势是汇报重点。KnowForge 把检索、治理、权限和质量放在同一套主链路里；"
                "EduRAG 把 FAQ、缓存、文档 RAG 做成几条割裂链路。"
            ),
            "knowforge",
            [
                node(
                    "adv_unified_retrieval",
                    "KnowForge：FAQ 和文档统一进入 Milvus Hybrid Search",
                    (
                        "FAQ 有独立 collection，文档有独立 collection，但执行层统一使用 MilvusHybridStore。\n"
                        "两者都支持 dense + sparse、kb_version、source、DataScope、rerank、诊断和引用。\n\n"
                        "客户价值：后期扩展多业务、多权限、多版本时，不需要维护两套检索体系。"
                    ),
                    "knowforge",
                ),
                node(
                    "adv_clear_boundary",
                    "KnowForge：MySQL 回归治理层，Milvus 承担检索层",
                    (
                        "KnowForge 中 MySQL 负责 kb_versions、kb_active_versions、history、feedback 等治理数据；"
                        "语义检索和关键词召回交给 Milvus。\n\n"
                        "客户价值：职责边界清晰，避免 MySQL/Redis/Python BM25 混在检索主链路中导致扩展困难。"
                    ),
                    "knowforge",
                ),
                node(
                    "adv_version_release",
                    "KnowForge：知识库发布是候选版本 + active 指针切换",
                    (
                        "新资料先进入 STAGED 版本，质量门禁通过后才切换 ACTIVE；失败版本不会污染线上。\n\n"
                        "客户价值：适合企业资料频繁更新场景，支持上线保护和回滚思路。"
                    ),
                    "knowforge",
                ),
                node(
                    "adv_data_scope",
                    "KnowForge：数据隔离前置到检索表达式",
                    (
                        "通过 DataScope 将 tenant_id、dataset_id、visibility、allowed_roles 等约束合并到 Milvus expr。\n\n"
                        "客户价值：为多部门、多租户、多角色访问控制打基础。"
                    ),
                    "knowforge",
                ),
                node(
                    "adv_observability",
                    "KnowForge：检索和生成过程可诊断、可解释",
                    (
                        "查询过程能看到 intent、route、retrieval_plan、FAQ 分数、Doc 分数、kb_version、耗时阶段和引用来源。\n\n"
                        "客户价值：系统出问题时能定位，而不是只看到一句“大模型答错了”。"
                    ),
                    "knowforge",
                ),
            ],
        ),
        node(
            "function_advantages",
            "2. 功能对比：KnowForge 覆盖企业知识库闭环，EduRAG 更偏基础链路",
            "这一部分用来告诉客户：KnowForge 不只是检索增强生成，而是围绕企业知识库运营做完整能力；EduRAG 更偏基础链路演示。",
            "knowforge",
            [
                node(
                    "func_multiscenario",
                    "多业务场景",
                    "支持企业知识库、合规问答、工程项目、设备运维、保险理赔、SaaS 支持、跨境风控、招投标合同风险等场景。",
                    "knowforge",
                ),
                node(
                    "func_hybrid_search",
                    "FAQ + 文档统一混合检索",
                    "同时支持语义召回和关键词精确匹配；FAQ 高置信直出，信息不足时进入 RAG 生成。",
                    "knowforge",
                ),
                node(
                    "func_multiformat",
                    "多格式资料入库",
                    "支持 Markdown、CSV、XLSX、DOCX、PPTX、PDF、OCR 后复核等资料类型，适合企业资料形态复杂的现实场景。",
                    "knowforge",
                ),
                node(
                    "func_query_understanding",
                    "追问改写与查询变体",
                    "能处理多轮追问、指代消解、查询变体和动态检索计划，提升复杂问题召回率。",
                    "knowforge",
                ),
                node(
                    "func_quality_gate",
                    "入库质量门禁",
                    "检查失败文件、空文件、重复 chunk、重复 FAQ、非法 source、FAQ 与文档冲突等问题。",
                    "knowforge",
                ),
                node(
                    "func_eval_gate",
                    "评测与回归验证",
                    "支持评测集、效果门禁、接口验证、性能基线，能发现系统升级后的效果退化。",
                    "knowforge",
                ),
                node(
                    "func_feedback",
                    "用户反馈闭环",
                    "用户点赞/点踩可以沉淀为后续知识库优化、FAQ 补充、Prompt 调整和评测集扩充依据。",
                    "knowforge",
                ),
                node(
                    "func_citation",
                    "引用来源与答案追溯",
                    "回答不只是生成文本，还能给出参考来源、分数和上下文依据，降低企业使用风险。",
                    "knowforge",
                ),
            ],
        ),
        node(
            "enterprise_traits",
            "3. 企业级特点：KnowForge 具备安全发布、权限隔离、质量可控、效果可量化",
            "这一部分适合给客户管理层讲，语言要从技术功能提升到业务价值。",
            "recommend",
            [
                node(
                    "enterprise_lifecycle",
                    "KnowForge：知识库生命周期管理",
                    "从资料入库、质量检查、版本激活、线上检索、用户反馈到效果评测形成闭环。",
                    "recommend",
                ),
                node(
                    "enterprise_safe_release",
                    "KnowForge：安全发布机制",
                    "候选版本先入库，质量通过后才切换 active；失败版本不影响线上。",
                    "recommend",
                ),
                node(
                    "enterprise_security",
                    "KnowForge：数据域隔离",
                    "支持租户、数据集、可见级别、角色等维度，为企业权限治理打基础。",
                    "recommend",
                ),
                node(
                    "enterprise_measurable",
                    "KnowForge：可评测、可回归",
                    "通过评测集、质量门禁和性能基线判断系统是否稳定达标。",
                    "recommend",
                ),
                node(
                    "enterprise_explainable",
                    "KnowForge：可诊断、可追溯",
                    "每次回答可以追踪命中路径、召回来源、分数、版本和耗时阶段。",
                    "recommend",
                ),
            ],
        ),
        node(
            "comparison_risks",
            "4. EduRAG 企业化风险：适合演示，不适合直接生产化",
            (
                "这里不回避 EduRAG 的问题：它更偏演示，企业化落地时会遇到以下风险。"
            ),
            "risk",
            [
                node(
                    "risk_split_chain",
                    "风险一：FAQ 和文档检索链路割裂",
                    (
                        "EduRAG 中 FAQ 走 MySQL + Redis + Python BM25；文档走 Milvus RAG。\n"
                        "企业化后版本、权限、诊断、评测都要做两套。"
                    ),
                    "risk",
                ),
                node(
                    "risk_bm25_process",
                    "风险二：Python 进程内 BM25 扩展性有限",
                    (
                        "使用 rank_bm25.BM25Okapi 没问题，但索引由应用进程自己维护。\n"
                        "多实例部署、FAQ 更新、缓存刷新都会带来一致性问题。"
                    ),
                    "risk",
                ),
                node(
                    "risk_redis",
                    "风险三：Redis 只是缓存，不是真正检索服务",
                    "Redis 缓存问题列表和答案，但不承担召回排序；增加了组件复杂度，却没有统一检索治理。",
                    "risk",
                ),
                node(
                    "risk_mysql_schema",
                    "风险四：MySQL FAQ 表结构偏 Demo",
                    "缺少 scenario_id、source、kb_version、tenant_id、dataset_id、visibility、status 等企业治理字段。",
                    "risk",
                ),
                node(
                    "risk_no_version",
                    "风险五：缺少完整知识库版本发布机制",
                    "没有 STAGED/ACTIVE/ARCHIVED、质量门禁、active 指针、previous version 等安全发布闭环。",
                    "risk",
                ),
                node(
                    "risk_no_scope",
                    "风险六：缺少统一数据隔离能力",
                    "多部门、多租户、多角色场景下，单纯 source_filter 难以支撑企业权限治理。",
                    "risk",
                ),
                node(
                    "risk_no_gate",
                    "风险七：缺少完整质量和评测门禁",
                    "资料质量、问答效果、性能基线和接口回归没有形成强约束闭环。",
                    "risk",
                ),
            ],
        ),
        node(
            "evidence_support",
            "5. 技术证据支撑：关键判断不是主观评价",
            "这一部分放源码证据，客户如果追问“为什么这么说”，可以展开这里。",
            "evidence",
            [
                node(
                    "evidence_edurag_faq",
                    "EduRAG 证据：FAQ 走 MySQL + Redis + BM25",
                    (
                        "integrated_qa_system/mysql_qa/retrieval/bm25_search.py\n"
                        "- from rank_bm25 import BM25Okapi\n"
                        "- qa_original_questions / qa_tokenized_questions\n"
                        "- fetch_questions() 拉 MySQL 问题\n"
                        "- BM25Okapi(tokenized_questions)\n"
                        "- search(query, threshold=0.85)\n\n"
                        "integrated_qa_system/new_main.py\n"
                        "- query() 中先 bm25_search.search()\n"
                        "- need_rag=True 时才 rag_system.generate_answer()"
                    ),
                    "edurag",
                ),
                node(
                    "evidence_edurag_mysql",
                    "EduRAG 证据：jpkb 表结构偏简单",
                    (
                        "integrated_qa_system/mysql_qa/db/mysql_client.py\n"
                        "- CREATE TABLE IF NOT EXISTS jpkb\n"
                        "- subject_name, question, answer\n"
                        "- fetch_questions(): SELECT question FROM jpkb\n"
                        "- fetch_answer(): SELECT answer FROM jpkb WHERE question = %s"
                    ),
                    "edurag",
                ),
                node(
                    "evidence_knowforge_retrieval",
                    "KnowForge 证据：FAQ / Doc 统一 MilvusHybridStore",
                    (
                        "qa_core/pipeline/retrieval_steps.py\n"
                        "- search_faq() 调用 get_faq_store().search_many(...)\n"
                        "- search_doc() 调用 get_doc_store().search_many(...)\n"
                        "- 两者都传 kb_version、valid_sources、data_scope、source_type。\n\n"
                        "qa_core/retrieval/store.py\n"
                        "- MilvusHybridStore\n"
                        "- vector_field=[\"dense\", \"sparse\"]\n"
                        "- build_source_expr(source, kb_version, data_scope)"
                    ),
                    "knowforge",
                ),
                node(
                    "evidence_knowforge_governance",
                    "KnowForge 证据：版本、质量、隔离都有主链路实现",
                    (
                        "qa_core/governance/kb_versions.py\n"
                        "- STAGED / ACTIVE / ARCHIVED\n"
                        "- activate_version()\n"
                        "- resolve_active_version()\n\n"
                        "qa_core/retrieval/filters.py\n"
                        "- source + kb_version + DataScope 合并为 Milvus expr。\n\n"
                        "scripts/check_ingestion_quality_gate.py\n"
                        "- 入库质量门禁。"
                    ),
                    "knowforge",
                ),
            ],
        ),
        node(
            "customer_value",
            "6. KnowForge 客户价值总结：降低风险、提升可维护性、支撑长期运营",
            "这一部分适合作为汇报最后一页或 XMind 最后一段展开。",
            "recommend",
            [
                node(
                    "value_risk_control",
                    "降低上线风险",
                    "新知识库版本先检查再激活，失败版本不影响线上问答。",
                    "recommend",
                ),
                node(
                    "value_scalability",
                    "提升扩展能力",
                    "FAQ 和文档统一检索治理，多场景、多权限、多版本扩展成本更低。",
                    "recommend",
                ),
                node(
                    "value_governance",
                    "增强知识治理能力",
                    "知识从哪里来、当前哪个版本生效、谁能访问、质量是否合格，都有系统化记录。",
                    "recommend",
                ),
                node(
                    "value_traceability",
                    "增强可解释和可追溯能力",
                    "回答依据、引用来源、召回分数、耗时阶段都可诊断。",
                    "recommend",
                ),
                node(
                    "value_iteration",
                    "支持持续优化",
                    "评测集、用户反馈、质量报告和性能基线可以驱动长期迭代。",
                    "recommend",
                ),
            ],
        ),
        node(
            "closing_lines",
            "7. 汇报金句：一页讲清 KnowForge 与 EduRAG 的差异",
            "这些句子适合放在汇报总结页，也适合你口头收束。",
            "conclusion",
            [
                node(
                    "line_one",
                    "EduRAG 解决“RAG 基础组件如何串起来”，KnowForge 解决“企业知识如何可信运营”",
                    "用来拉开定位差距。",
                    "conclusion",
                ),
                node(
                    "line_two",
                    "KnowForge 的核心优势不是页面问答，而是统一检索、多版本发布、数据隔离、质量门禁和评测反馈闭环",
                    "用来总结功能亮点。",
                    "conclusion",
                ),
                node(
                    "line_three",
                    "KnowForge 将 FAQ 和文档统一纳入 Milvus Hybrid Search；EduRAG 的 FAQ 和文档检索链路是割裂的",
                    "用来强调架构优势。",
                    "conclusion",
                ),
                node(
                    "line_four",
                    "KnowForge 的知识库更新是候选版本入库、质量检查、active 指针切换；EduRAG 缺少完整版本发布闭环",
                    "用来强调企业级发布机制。",
                    "conclusion",
                ),
            ],
        ),
    ],
)


def main() -> None:
    """命令行入口：解析参数并导出架构对比 XMind 报表。

    调用顺序：命令行入口 -> main()。
    """
    parser = argparse.ArgumentParser(description="Export KnowForge vs EduRAG architecture comparison as XMind.")
    parser.add_argument(
        "-o",
        "--output",
        default="reports/xmind/KnowForge_vs_EduRAG_customer_report.xmind",
        help="Output .xmind file path.",
    )
    args = parser.parse_args()

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_xmind(CUSTOMER_REPORT_TREE, str(output_path))


if __name__ == "__main__":
    main()
