# -*- coding: utf-8 -*-
# ============================================================================
# 正式讲义、章节代码和动画流程对齐检查
# ============================================================================
# 这个检查用于防止后续维护时出现三类回退：
#   - 正式讲义暴露内部课程实现标记；
#   - 章节 README 缺少统一的章节说明结构；
#   - 章节缺少可运行源码或测试文件；
#   - 已打磨章节的动画流程仍停留在旧代码口径。
#
# 检查维度：
#   1. 讲义实现标记检查（防止正式文档泄露内部实现细节）
#   2. 章节结构检查（README、源码、测试文件是否齐全）
#   3. 章节地图对齐（通过 validate_maps() 检查符号和文件）
#
# 用法示例：
#   python scripts\check_codealong_alignment.py
#   python scripts\check_codealong_alignment.py --fix  # 自动修复可修复的问题
# ============================================================================
"""检查正式讲义、章节代码和动画流程是否保持对齐。

这个检查用于防止后续维护时出现三类回退：
- 正式讲义暴露内部课程实现标记；
- 章节 README 缺少统一的章节说明结构；
- 章节缺少可运行源码或测试文件。
- 已打磨章节的动画流程仍停留在旧代码口径。
"""

from __future__ import annotations

# argparse: 命令行参数解析
import argparse

# ast: Python 抽象语法树（检查文档中的代码块）
import ast

# sys: 系统功能
import sys

# pathlib.Path: 文件路径操作
from pathlib import Path

# typing.Any: 任意类型
from typing import Any

# ── 路径设置 ──
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# ── 导入公共模块 ──
from scripts.common import configure_utf8_stdio, print_json, utc_now, write_optional_json
from scripts.check_chapter_maps import validate_maps


CHAPTERS: tuple[tuple[str, str], ...] = (
    ("05", "ch05_intent_classification"),
    ("06", "ch06_retrieval_strategy"),
    ("07", "ch07_query_rewrite_variants"),
    ("08", "ch08_milvus_hybrid_search"),
    ("09", "ch09_qaservice_orchestration"),
    ("10", "ch10_rag_pipeline"),
    ("11", "ch11_prompt_engineering"),
    ("12", "ch12_fastapi_service"),
    ("13", "ch13_preflight_checks"),
    ("14", "ch14_kb_versioning"),
    ("15", "ch15_data_isolation"),
    ("16", "ch16_ingestion_pipeline"),
    ("17", "ch17_quality_evaluation"),
    ("18", "ch18_test_system"),
    ("19", "ch19_observability_tracing"),
)

CHAPTER_ANIMATION_FILES: dict[str, str] = {
    "05": "05-intent-flow.html",
    "06": "06-retrieval-flow.html",
    "07": "07-query-flow.html",
    "08": "08-milvus-hybrid-search.html",
    "09": "09-qaservice-orchestration.html",
    "10": "10-rag-pipeline.html",
    "11": "11-prompt-engineering.html",
    "12": "12-fastapi-service.html",
    "13": "13-preflight-checks.html",
    "14": "14-kb-versioning.html",
    "15": "15-data-isolation.html",
    "16": "16-ingestion-pipeline.html",
    "17": "17-quality-evaluation.html",
    "18": "18-testing-system.html",
    "19": "19-observability-tracing.html",
}

SCHEMA_BOOTSTRAP_CHAPTERS = {"08", "09", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19"}
SCHEMA_BOOTSTRAP_REQUIRED_FILES = (
    "qa_core/storage/runtime_schema.sql",
    "qa_core/storage/bootstrap.py",
)
SCHEMA_BOOTSTRAP_EXEMPT_PY_FILES = {
    "qa_core/storage/bootstrap.py",
    "qa_core/storage/mysql_schema.py",
}
SCHEMA_BOOTSTRAP_FORBIDDEN_FRAGMENTS = {
    "CREATE TABLE": "MySQL DDL 只能写在 runtime_schema.sql，章节业务代码不要硬编码建表语句。",
    "ALTER TABLE": "MySQL DDL 只能写在 runtime_schema.sql，章节业务代码不要硬编码改表语句。",
    "CREATE INDEX": "MySQL DDL 只能写在 runtime_schema.sql，章节业务代码不要硬编码建索引语句。",
    "def ensure_table(": "Store 不再暴露 ensure_table() 建表方法，请在入口调用 bootstrap_mysql_schema()。",
    "def ensure_tables(": "Store 不再暴露 ensure_tables() 建表方法，请在入口调用 bootstrap_mysql_schema()。",
    ".ensure_table(": "测试/脚本不要调用 Store 建表兜底，请在入口调用 bootstrap_mysql_schema()。",
    ".ensure_tables(": "测试/脚本不要调用 Store 建表兜底，请在入口调用 bootstrap_mysql_schema()。",
    "ensure_summary_table": "聊天摘要表由 bootstrap 初始化，不在 ChatHistoryStore 中按需建表。",
    "create_kb_version_tables": "章节 Store 不直接导入 schema 建表函数，统一通过 SQL 文件 bootstrap。",
    "create_chunk_version_table": "章节 Store 不直接导入 schema 建表函数，统一通过 SQL 文件 bootstrap。",
    "create_index_manifest_table": "章节 Store 不直接导入 schema 建表函数，统一通过 SQL 文件 bootstrap。",
    "create_chat_summary_table": "章节 Store 不直接导入 schema 建表函数，统一通过 SQL 文件 bootstrap。",
}
CODEALONG_FORBIDDEN_COMPAT_FRAGMENTS = {
    "def answer(self) -> str | None:": "IntentResult 只保留 direct_answer；不要再提供早期 answer 兼容属性。",
    "兼容早期跟敲代码": "跟敲代码不保留早期兼容说明，避免增加学习分支。",
    "保留向后兼容": "跟敲代码不保留向后兼容分支，当前实现只保留单一清晰路径。",
}

UNIFIED_CHAPTER_ANIMATION_MARKER = "chapter-animation-template: unified-v2"

MIN_PUBLIC_DOC_LINES = 120

FORBIDDEN_PUBLIC_DOC_FRAGMENTS = (
    "跟敲",
    "codealong/chapters/",
    "codealong\\chapters\\",
    "codealong-code-flow.html",
    "跟敲代码全链路",
    "全链路图",
    "本章运行目录",
    "建议按下面顺序打开文件",
    "demo_retrieval_plan.py",
    "代码闭环地图",
    "本章代码闭环",
)

REQUIRED_ANIMATION_PAGE_FRAGMENTS = (
    UNIFIED_CHAPTER_ANIMATION_MARKER,
    "业务执行流程图",
    "代码执行流程图",
    "返回本章讲义",
    "business-flow.html",
)

GAP_DECISION_DOC = PROJECT_ROOT / "codealong" / "CODEALONG_TO_PROJECT_GAP_DECISION.md"
V2_ONLY_PROJECT_PATH_PREFIXES = (
    "qa_core/agent/",
    "qa_core/agent_eval/",
    "qa_core/agent_protocols/",
    "qa_core/agent_queue/",
    "qa_core/agent_runtime/",
    "qa_core/graphrag/",
    "qa_core/ops/",
)
V2_ONLY_PROJECT_FILES = {
    "qa_core/api/v2.py",
}

REQUIRED_README_SECTIONS = (
    "## 本章目标",
    "## 和上一章的关系",
    "## 本章代码",
    "## 运行",
    "## 测试",
    "## 对应主项目源码",
    "## 本章边界",
)

REQUIRED_QA_CORE_FILES: dict[str, tuple[str, ...]] = {
    "05": (
        "qa_core/intent/classifier.py",
        "qa_core/pipeline/steps.py",
        "qa_core/scenarios/registry.py",
        "qa_core/scenarios/boundary.py",
    ),
    "06": (
        "qa_core/intent/question_category.py",
        "qa_core/retrieval/strategy.py",
    ),
    "07": (
        "qa_core/pipeline/rewrite.py",
        "qa_core/pipeline/query_variants.py",
        "qa_core/llm/client.py",
        "qa_core/prompts/constants.py",
    ),
    "08": (
        "qa_core/retrieval/store.py",
        "qa_core/retrieval/results.py",
        "qa_core/retrieval/filters.py",
        "qa_core/retrieval/ranking.py",
        "qa_core/retrieval/factory.py",
    ),
    "09": (
        "qa_core/memory/__init__.py",
        "qa_core/memory/base.py",
        "qa_core/memory/history.py",
        "qa_core/application/service.py",
        "qa_core/application/factory.py",
    ),
    "10": (
        "qa_core/memory/__init__.py",
        "qa_core/memory/base.py",
        "qa_core/memory/history.py",
        "qa_core/pipeline/rag.py",
        "qa_core/pipeline/runtime.py",
        "qa_core/pipeline/events.py",
        "qa_core/pipeline/context.py",
        "qa_core/pipeline/retrieval_steps.py",
    ),
    "11": (
        "qa_core/memory/__init__.py",
        "qa_core/memory/base.py",
        "qa_core/memory/history.py",
        "qa_core/prompts/profiles.py",
        "qa_core/prompts/selector.py",
        "qa_core/prompts/templates.py",
    ),
    "12": (
        "app.py",
        "qa_core/memory/__init__.py",
        "qa_core/memory/base.py",
        "qa_core/memory/history.py",
        "qa_core/memory/feedback.py",
        "qa_core/api/chat.py",
        "qa_core/api/service_context.py",
        "qa_core/api/error_handlers.py",
        "qa_core/schemas.py",
    ),
    "13": (
        "qa_core/memory/__init__.py",
        "qa_core/memory/base.py",
        "qa_core/memory/history.py",
        "qa_core/memory/feedback.py",
        "qa_core/config/settings.py",
        "qa_core/config/preflight.py",
        "qa_core/config/logging_config.py",
        "qa_core/schemas.py",
    ),
    "14": (
        "qa_core/common.py",
        "qa_core/memory/__init__.py",
        "qa_core/memory/base.py",
        "qa_core/memory/history.py",
        "qa_core/memory/feedback.py",
        "qa_core/schemas.py",
        "qa_core/governance/kb_versions.py",
        "qa_core/api/kb_versions.py",
    ),
    "15": (
        "qa_core/common.py",
        "qa_core/memory/__init__.py",
        "qa_core/memory/base.py",
        "qa_core/memory/history.py",
        "qa_core/memory/feedback.py",
        "qa_core/schemas.py",
        "qa_core/governance/data_scope.py",
        "qa_core/retrieval/filters.py",
    ),
    "16": (
        "qa_core/common.py",
        "qa_core/utils.py",
        "qa_core/document_metadata.py",
        "qa_core/memory/__init__.py",
        "qa_core/memory/base.py",
        "qa_core/memory/history.py",
        "qa_core/memory/feedback.py",
        "qa_core/schemas.py",
        "qa_core/pipeline/citations.py",
        "qa_core/indexing/chunking.py",
        "qa_core/indexing/document_loaders.py",
        "qa_core/indexing/table_documents.py",
        "qa_core/indexing/document_normalizer.py",
        "qa_core/indexing/faq_ingestion.py",
        "qa_core/indexing/service.py",
    ),
    "17": (
        "qa_core/common.py",
        "qa_core/utils.py",
        "qa_core/document_metadata.py",
        "qa_core/memory/__init__.py",
        "qa_core/memory/base.py",
        "qa_core/memory/history.py",
        "qa_core/memory/feedback.py",
        "qa_core/schemas.py",
        "qa_core/pipeline/citations.py",
        "qa_core/indexing/table_documents.py",
        "qa_core/quality/ingestion.py",
        "qa_core/quality/faq.py",
        "qa_core/quality/conflicts.py",
        "qa_core/quality/chunk.py",
    ),
    "18": (
        "qa_core/common.py",
        "qa_core/utils.py",
        "qa_core/document_metadata.py",
        "qa_core/memory/__init__.py",
        "qa_core/memory/base.py",
        "qa_core/memory/history.py",
        "qa_core/memory/feedback.py",
        "qa_core/schemas.py",
        "qa_core/pipeline/citations.py",
        "qa_core/indexing/table_documents.py",
        "scripts/check_project_guardrails.py",
        "scripts/acceptance_smoke.py",
    ),
    "19": (
        "qa_core/common.py",
        "qa_core/utils.py",
        "qa_core/document_metadata.py",
        "qa_core/memory/__init__.py",
        "qa_core/memory/base.py",
        "qa_core/memory/history.py",
        "qa_core/memory/feedback.py",
        "qa_core/schemas.py",
        "qa_core/pipeline/citations.py",
        "qa_core/indexing/table_documents.py",
        "qa_core/observability/langsmith_adapter.py",
        "qa_core/pipeline/runtime.py",
    ),
}

STALE_ANIMATION_FRAGMENTS: dict[str, tuple[tuple[str, str], ...]] = {
    "05": (
        ("内存 FAQ 字典", "第 05 章动画仍使用旧口径；当前 FAQ fast path 只允许作为后续真实 FAQ 检索的前置判断。"),
    ),
    "07": (
        ("用确定性同义词规则生成少量等价表达", "第 07 章动画缺少 LLM structured-output fallback 路径。"),
        ("用本地同义词补充稳定变体", "第 07 章动画仍使用旧口径；查询变体同义词规则已迁移到 config/rules.toml。"),
    ),
}

STALE_QUERY_VARIANT_CODE_FRAGMENTS = (
    'if "流程" in query',
    'if "webhook" in normalized',
    'query.replace("失败", "报错")',
    "SHORT_STRUCTURED_MAX_CHARS",
)

FOLLOW_UP_TEST_MARKERS = (
    "FOLLOW_UP",
    "那审批呢",
    "审批",
)

FOLLOW_UP_REWRITE_MARKERS = (
    "rewritten_query",
    "rewritten",
)

FOLLOW_UP_VARIANT_MARKERS = (
    "query_variants",
    "variants",
)

SCHEMA_COMPATIBILITY_BACKFILL_FRAGMENTS = (
    "ALTER TABLE",
    "Duplicate column",
    "Duplicate key name",
    "OperationalError",
    "ProgrammingError",
    "_backfill_version_seq",
    "_reconcile_active_status",
    "backfill_legacy",
    "002_backfill",
)
SOURCE_FILTER_BOUNDARY_FILES = (
    "qa_core/retrieval/filters.py",
    "qa_core/retrieval/store.py",
    "qa_core/pipeline/steps.py",
    "qa_core/pipeline/retrieval_steps.py",
)
PIPELINE_CONTEXT_CONTRACT_FRAGMENTS = {
    "context.raw_query or query": "RAGQueryContext 创建时已经写入 raw_query，调试返回不要再回退到入参 query。",
    "(context.raw_query or query)": "RAGQueryContext 创建时已经写入 raw_query，调试返回不要再回退到入参 query。",
    "raw_query = self.raw_query or self.query": "finalize_timings() 应直接使用 self.raw_query，避免重复兜底。",
    "bool(raw_query and raw_query != self.query)": "query_normalized 直接比较 raw_query 和 query 即可。",
    "question=self.raw_query or self.query": "record_trace() 使用请求创建时写入的 raw_query，不再回退到规范化 query。",
    'source_filter=self.retrieval_info.get("source_filter") or self.source_filter': "finalize_timings() 会补齐 source_filter，record_trace() 直接读取固定字段。",
    'context.retrieval_info.get("stage_timings_ms") or {}': "finalize_timings() 已写入 stage_timings_ms，调试返回直接读取即可。",
    'context.retrieval_info.get("slowest_stage") or {}': "路由和检索阶段已记录耗时，调试返回不要重复兜底 slowest_stage。",
    'route.intent.as_dict() if route.intent else {}': "终止路由必须带 intent，调试返回不要重复判断 route.intent。",
    'context.retrieval_info.get("boundary_reason") or "source_boundary"': "source 边界分支已由 detect_and_apply_boundary_answer() 写入 boundary_reason，不再兜底。",
    "doc.metadata or {}": "LangChain Document.metadata 固定为 dict，主链路不要重复兜底。",
    "dict(doc.metadata or {})": "LangChain Document.metadata 固定为 dict，直接 dict(doc.metadata)。",
    "hit.document.metadata or {}": "RetrievalHit.document 是 LangChain Document，metadata 固定为 dict。",
    "dict(hit.document.metadata or {})": "RetrievalHit.document.metadata 固定为 dict，复制时直接 dict(hit.document.metadata)。",
    "document.metadata or {}": "document_key() 接收 LangChain Document，metadata 固定为 dict。",
    "metadata: dict[str, Any] | None": "metadata 工具函数消费内部 Document.metadata/dict，不保留 None 分支。",
    "data = metadata or {}": "metadata 工具函数消费内部 dict，直接读取 metadata 字段。",
    "dict(child_doc.metadata or {})": "LangChain Document.metadata 固定为 dict，切分后直接 dict(child_doc.metadata)。",
    "dict(chunk.metadata or {})": "LangChain Document.metadata 固定为 dict，质量检测直接 dict(chunk.metadata)。",
    "(doc.metadata or {}).get": "主链路上下文统计直接读取 doc.metadata。",
    'doc.page_content or ""': "LangChain Document.page_content 固定为 str，主链路不要重复兜底。",
    'str(doc.page_content or "")': "LangChain Document.page_content 固定为 str，不需要转字符串兜底。",
    'answer or ""': "引用后处理接收内部 answer 字符串，不保留 None 兜底。",
    'str(query or "").strip()': "normalize_queries() 接收 Iterable[str]，直接 query.strip() 即可。",
    "candidate = str(item).strip()": "QueryVariants.queries 是 Pydantic 校验后的 list[str]，直接 item.strip() 即可。",
    'compact_query = (query or "").strip()': "should_try_faq_fast_path() 只接收规范化后的 context.query，直接 query.strip() 即可。",
    'raw_query = (query or "").strip()': "create_query_context() 由 QAService 传入 query: str，直接 query.strip() 即可。",
    'clean_query = (query or "").strip()': "MilvusKnowledgeStore.search() 接收 query: str，直接 query.strip() 即可。",
    'normalized = (query or "").strip().lower()': "question_category 内部接收 query: str，直接 query.strip().lower() 即可。",
    "[score for score in [faq_result.top_score, doc_result.top_score] if score is not None]": (
        "RetrievalResult.top_score 固定返回 float，上下文 top_score 直接 max(faq, doc)。"
    ),
    "retrieval_info = retrieval or {}": "end_event() 只由 finish_success() 调用，retrieval 是固定字段，不需要空值兜底。",
    "intent: dict[str, Any] | None = None": "end_event() 是内部成功收口事件，intent 必须由 RAGQueryContext 提供。",
    "retrieval: dict[str, Any] | None = None": "end_event() 是内部成功收口事件，retrieval 必须由 RAGQueryContext 提供。",
    'retrieval_info.get("stage_timings_ms", {})': "end_event() 应直接读取 retrieval 固定字段，不重复兜底 stage_timings_ms。",
    'retrieval_info.get("first_token_ms")': "end_event() 应直接读取 retrieval 固定字段，不重复兜底 first_token_ms。",
    'retrieval_info.get("slowest_stage")': "end_event() 应直接读取 retrieval 固定字段，不重复兜底 slowest_stage。",
    'retrieval.get("slowest_stage")': "finalize_timings() 已固定写入 slowest_stage，end_event() 直接读取即可。",
    "retrieval_payload = retrieval or {}": "record_query_trace() 由 RAGQueryContext.record_trace() 单一路径调用，retrieval 是固定诊断字段。",
    "intent_payload = intent or {}": "record_query_trace() 由 RAGQueryContext.record_trace() 单一路径调用，intent 是固定诊断字段。",
    "intent: dict[str, Any] | None": "record_query_trace() 消费主链路固定 intent payload，不保留 None 分支。",
    "retrieval: dict[str, Any] | None": "record_query_trace() 消费主链路固定 retrieval payload，不保留 None 分支。",
    'getattr(scenario, "scenario_id"': "record_query_trace() 消费已解析的 ScenarioDefinition，应直接读取 scenario 字段。",
    'getattr(scenario, "display_name"': "record_query_trace() 消费已解析的 ScenarioDefinition，应直接读取 scenario 字段。",
    'return (text or "")[:max_chars]': "_safe_preview() 只由 record_query_trace() 传入字符串 answer，不保留 None 兜底。",
}
PROMPT_SELECTOR_CONTRACT_FRAGMENTS = {
    "from qa_core.config.settings import get_settings": "Prompt selector 必须消费上游已解析的 ScenarioDefinition，不读取全局 settings 做默认展示。",
    "settings = get_settings()": "Prompt selector 必须消费上游已解析的 ScenarioDefinition，不读取全局 settings 做默认展示。",
    "ScenarioDefinition | None = None": "Prompt selector 的 scenario 是主链路固定上下文，不保留 None 分支。",
    "query: str | None = None": "Prompt selector 的 query 由主链路固定传入，应是必填 str。",
    'infer_question_category(query or "")': "Prompt selector 接收必填 query: str，直接传给 infer_question_category(query)。",
    "def _scenario_prompt_context(scenario=None)": "Prompt selector 的场景上下文必须由明确 ScenarioDefinition 构造。",
    "if scenario else": "Prompt selector 不保留默认展示兜底，场景变量来自 ScenarioDefinition。",
}


def text_of(path: Path) -> str:
    """读取文本文件；不存在时返回空字符串。

    调用顺序：命令行入口 -> text_of()。
    """
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def parse_python(path: Path) -> ast.Module | None:
    """解析 Python 文件；文件不存在时返回 None。

    调用顺序：命令行入口 -> parse_python()。
    """
    if not path.exists():
        return None
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def function_arg_names(module: ast.Module, function_name: str) -> set[str]:
    """读取函数的位置参数和 keyword-only 参数名。

    调用顺序：命令行入口 -> function_arg_names()。
    """
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return {arg.arg for arg in (*node.args.args, *node.args.kwonlyargs)}
    return set()


def function_defs(module: ast.Module, function_name: str) -> list[ast.FunctionDef]:
    """返回模块中指定名称的函数或方法定义。

    调用顺序：命令行入口 -> function_defs()。
    """
    return [node for node in ast.walk(module) if isinstance(node, ast.FunctionDef) and node.name == function_name]


def arg_names(node: ast.FunctionDef) -> set[str]:
    """读取函数的位置参数和 keyword-only 参数名。

    调用顺序：命令行入口 -> arg_names()。
    """
    return {arg.arg for arg in (*node.args.args, *node.args.kwonlyargs)}


def calls_named(module: ast.Module, function_name: str) -> list[ast.Call]:
    """返回模块里对指定函数名或同名属性的调用。

    调用顺序：命令行入口 -> calls_named()。
    """
    calls: list[ast.Call] = []
    for node in ast.walk(module):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == function_name:
            calls.append(node)
        elif isinstance(func, ast.Attribute) and func.attr == function_name:
            calls.append(node)
    return calls


def find_doc(chapter_no: str) -> Path | None:
    """按章节号定位正式讲义 Markdown。

    调用顺序：命令行入口 -> find_doc()。
    """
    matches = sorted((PROJECT_ROOT / "docs").glob(f"{chapter_no}-*.md"))
    return matches[0] if matches else None


def add_failure(
    failures: list[dict[str, Any]],
    *,
    metric: str,
    chapter: str,
    path: str,
    message: str,
) -> None:
    """向失败列表中添加一条校验失败记录。

    调用顺序：命令行入口 -> add_failure()。
    """
    failures.append({"metric": metric, "chapter": chapter, "path": path, "message": message})


def check_chapter(chapter_no: str, chapter_dir_name: str) -> list[dict[str, Any]]:
    """检查单个 codealong 章节和对应讲义入口。

    调用顺序：命令行入口 -> check_chapter()。
    """
    failures: list[dict[str, Any]] = []
    marker = f"codealong/chapters/{chapter_dir_name}"
    chapter_rel = f"codealong/chapters/{chapter_dir_name}"
    chapter_dir = PROJECT_ROOT / chapter_rel

    if not chapter_dir.exists():
        add_failure(failures, metric="chapter_dir", chapter=chapter_no, path=chapter_rel, message="codealong 章节目录不存在")
        return failures

    readme = chapter_dir / "README.md"
    readme_text = text_of(readme)
    normalized_readme_text = readme_text.replace("\\", "/")
    if not readme_text:
        add_failure(failures, metric="chapter_readme", chapter=chapter_no, path=str(readme.relative_to(PROJECT_ROOT)), message="章节 README 不存在或为空")
    else:
        for section in REQUIRED_README_SECTIONS:
            if section not in readme_text:
                add_failure(
                    failures,
                    metric="chapter_readme_section",
                    chapter=chapter_no,
                    path=str(readme.relative_to(PROJECT_ROOT)),
                    message=f"章节 README 缺少固定段落：{section}",
                )
        if marker not in normalized_readme_text:
            add_failure(
                failures,
                metric="chapter_readme_path",
                chapter=chapter_no,
                path=str(readme.relative_to(PROJECT_ROOT)),
                message=f"章节 README 缺少自身目录路径：{marker}",
            )

    src_dir = chapter_dir / "src"
    if src_dir.exists():
        add_failure(
            failures,
            metric="chapter_legacy_src",
            chapter=chapter_no,
            path=str(src_dir.relative_to(PROJECT_ROOT)),
            message="最终跟敲交付禁止使用孤立 src 小样例；请迁移到 qa_core/ + scripts/ + tests/ 的增量工程结构",
        )

    qa_core_dir = chapter_dir / "qa_core"
    if not qa_core_dir.exists():
        add_failure(
            failures,
            metric="chapter_qa_core",
            chapter=chapter_no,
            path=str(qa_core_dir.relative_to(PROJECT_ROOT)),
            message="章节缺少 qa_core 业务源码目录，无法证明它是主项目同向的增量实现",
        )

    for relative in REQUIRED_QA_CORE_FILES.get(chapter_no, ()):
        required_path = chapter_dir / relative
        if not required_path.exists():
            add_failure(
                failures,
                metric="chapter_required_module",
                chapter=chapter_no,
                path=str(required_path.relative_to(PROJECT_ROOT)),
                message=f"章节缺少主项目同向模块：{relative}",
            )

    scripts_dir = chapter_dir / "scripts"
    script_files = sorted(scripts_dir.glob("*.py")) if scripts_dir.exists() else []
    if not script_files:
        add_failure(
            failures,
            metric="chapter_scripts",
            chapter=chapter_no,
            path=str(scripts_dir.relative_to(PROJECT_ROOT)),
            message="章节缺少 scripts/*.py 章节运行入口",
        )

    tests_dir = chapter_dir / "tests"
    test_files = sorted(tests_dir.glob("test_*.py")) if tests_dir.exists() else []
    if not test_files:
        add_failure(failures, metric="chapter_tests", chapter=chapter_no, path=str(tests_dir.relative_to(PROJECT_ROOT)), message="章节 tests 目录缺少 test_*.py")

    doc = find_doc(chapter_no)
    if doc is None:
        add_failure(failures, metric="doc_markdown", chapter=chapter_no, path=f"docs/{chapter_no}-*.md", message="正式讲义 Markdown 不存在")
    else:
        doc_rel = str(doc.relative_to(PROJECT_ROOT))
        doc_text = text_of(doc)
        doc_lines = doc_text.splitlines()
        first_nonempty_line = next((line.strip() for line in doc_lines if line.strip()), "")
        if not first_nonempty_line.startswith("# "):
            add_failure(
                failures,
                metric="doc_public_h1",
                chapter=chapter_no,
                path=doc_rel,
                message="正式讲义必须以一级标题开头，避免章节页面结构异常。",
            )
        if len(doc_lines) < MIN_PUBLIC_DOC_LINES:
            add_failure(
                failures,
                metric="doc_public_body_length",
                chapter=chapter_no,
                path=doc_rel,
                message=f"正式讲义正文过短，可能被同步脚本误裁剪；当前 {len(doc_lines)} 行，至少应为 {MIN_PUBLIC_DOC_LINES} 行。",
            )
        for fragment in FORBIDDEN_PUBLIC_DOC_FRAGMENTS:
            if fragment in doc_text:
                add_failure(
                    failures,
                    metric="doc_public_internal_marker",
                    chapter=chapter_no,
                    path=doc_rel,
                    message=f"正式讲义不能暴露内部课程实现信息：{fragment}",
                )
        site_doc = PROJECT_ROOT / "site" / f"{doc.stem}.html"
        site_text = text_of(site_doc)
        if not site_text:
            add_failure(failures, metric="site_doc", chapter=chapter_no, path=str(site_doc.relative_to(PROJECT_ROOT)), message="MkDocs 站点 HTML 不存在或为空，请先运行 python -m mkdocs build")
        else:
            for fragment in FORBIDDEN_PUBLIC_DOC_FRAGMENTS:
                if fragment in site_text:
                    add_failure(
                        failures,
                        metric="site_doc_public_internal_marker",
                        chapter=chapter_no,
                        path=str(site_doc.relative_to(PROJECT_ROOT)),
                        message=f"MkDocs 站点讲义不能暴露内部课程实现信息：{fragment}",
                    )

    return failures


def check_animation_alignment() -> list[dict[str, Any]]:
    """检查动画流程是否覆盖已打磨章节，并拦截已知旧口径。

    调用顺序：命令行入口 -> check_animation_alignment()。
    """
    failures: list[dict[str, Any]] = []
    animation_dir = PROJECT_ROOT / "docs" / "animation"
    business_flow = animation_dir / "business-flow.html"
    business_text = text_of(business_flow)
    if not business_text:
        add_failure(
            failures,
            metric="animation_business_flow",
            chapter="ALL",
            path=str(business_flow.relative_to(PROJECT_ROOT)),
            message="业务流程总动画不存在或为空",
        )
    else:
        for chapter_no, _ in CHAPTERS:
            if f"CH{chapter_no}" not in business_text:
                add_failure(
                    failures,
                    metric="animation_business_flow_chapter",
                    chapter=chapter_no,
                    path=str(business_flow.relative_to(PROJECT_ROOT)),
                    message=f"业务流程总动画缺少 CH{chapter_no}",
                )

    for chapter_no, chapter_dir_name in CHAPTERS:
        chapter_dir = PROJECT_ROOT / "codealong" / "chapters" / chapter_dir_name
        is_polished = (chapter_dir / "qa_core").exists() and not (chapter_dir / "src").exists()
        expected_animation_name = CHAPTER_ANIMATION_FILES[chapter_no]
        expected_animation = animation_dir / expected_animation_name
        single_chapter_animations = sorted(animation_dir.glob(f"{chapter_no}-*.html"))
        if is_polished and not expected_animation.exists():
            add_failure(
                failures,
                metric="animation_chapter_flow",
                chapter=chapter_no,
                path=str(expected_animation.relative_to(PROJECT_ROOT)),
                message=f"已打磨章节缺少固定命名的单章代码执行动画：{expected_animation_name}",
            )
        if expected_animation.exists():
            expected_animation_text = text_of(expected_animation)
            for fragment in REQUIRED_ANIMATION_PAGE_FRAGMENTS:
                if fragment not in expected_animation_text:
                    add_failure(
                        failures,
                        metric="animation_chapter_template",
                        chapter=chapter_no,
                        path=str(expected_animation.relative_to(PROJECT_ROOT)),
                        message=f"单章动画未使用统一模板或缺少必要导航：{fragment}",
                    )

        for animation_path in single_chapter_animations:
            animation_text = text_of(animation_path)
            for fragment, message in STALE_ANIMATION_FRAGMENTS.get(chapter_no, ()):
                if fragment in animation_text:
                    add_failure(
                        failures,
                        metric="animation_stale_text",
                        chapter=chapter_no,
                        path=str(animation_path.relative_to(PROJECT_ROOT)),
                        message=message,
                    )
    return failures


def check_rule_config_alignment() -> list[dict[str, Any]]:
    """检查 query variants 规则已经配置化，防止业务词表回写到代码里。

    调用顺序：命令行入口 -> check_rule_config_alignment()。
    """

    failures: list[dict[str, Any]] = []
    rules_toml = PROJECT_ROOT / "config" / "rules.toml"
    rules_text = text_of(rules_toml)
    for fragment in (
        "[query_variants]",
        "short_structured_markers",
        "[[query_variants.replacements]]",
    ):
        if fragment not in rules_text:
            add_failure(
                failures,
                metric="rules_query_variants_config",
                chapter="07",
                path=str(rules_toml.relative_to(PROJECT_ROOT)),
                message=f"config/rules.toml 缺少查询变体配置：{fragment}",
            )

    query_variant_files = [
        PROJECT_ROOT / "qa_core" / "pipeline" / "query_variants.py",
        *(
            PROJECT_ROOT / "codealong" / "chapters" / chapter_dir_name / "qa_core" / "pipeline" / "query_variants.py"
            for chapter_no, chapter_dir_name in CHAPTERS
            if chapter_no >= "07"
        ),
    ]
    for path in query_variant_files:
        text = text_of(path)
        if not text:
            continue
        if "get_rule_config().query_variants" not in text:
            add_failure(
                failures,
                metric="query_variants_config_usage",
                chapter="07",
                path=str(path.relative_to(PROJECT_ROOT)),
                message="查询变体代码未读取 get_rule_config().query_variants，可能仍在代码中写死业务词表",
            )
        for fragment in STALE_QUERY_VARIANT_CODE_FRAGMENTS:
            if fragment in text:
                add_failure(
                    failures,
                    metric="query_variants_hardcoded_rule",
                    chapter="07",
                    path=str(path.relative_to(PROJECT_ROOT)),
                    message=f"查询变体代码仍包含写死业务规则片段：{fragment}",
                )
        module = parse_python(path)
        if module is None:
            continue
        if "allow_short_structured" not in function_arg_names(module, "generate_query_variants"):
            add_failure(
                failures,
                metric="query_variants_follow_up_signature",
                chapter="07",
                path=str(path.relative_to(PROJECT_ROOT)),
                message="generate_query_variants 必须保留 allow_short_structured，避免追问改写后被短问题规则截断。",
            )
        for fragment in ("FOLLOW_UP_REWRITE_MARKERS",):
            if fragment not in text:
                add_failure(
                    failures,
                    metric="query_variants_follow_up_guard",
                    chapter="07",
                    path=str(path.relative_to(PROJECT_ROOT)),
                    message=f"查询变体缺少追问闭环回归片段：{fragment}",
                )

    runtime_call_paths = [
        PROJECT_ROOT / "qa_core" / "pipeline" / "steps.py",
        *(
            path
            for _, chapter_dir_name in CHAPTERS
            for path in (
                PROJECT_ROOT / "codealong" / "chapters" / chapter_dir_name
            ).glob("scripts/*.py")
        ),
        *(
            path
            for _, chapter_dir_name in CHAPTERS
            for path in (
                PROJECT_ROOT / "codealong" / "chapters" / chapter_dir_name
            ).rglob("qa_core/application/*.py")
        ),
        *(
            path
            for _, chapter_dir_name in CHAPTERS
            for path in (
                PROJECT_ROOT / "codealong" / "chapters" / chapter_dir_name
            ).rglob("qa_core/pipeline/*.py")
        ),
    ]
    for path in sorted({path for path in runtime_call_paths if path.exists()}):
        if path.name == "query_variants.py":
            continue
        text = text_of(path)
        if "generate_query_variants(" not in text:
            continue
        module = parse_python(path)
        if module is None:
            continue
        for call in calls_named(module, "generate_query_variants"):
            keyword_names = {keyword.arg for keyword in call.keywords if keyword.arg}
            if "allow_short_structured" not in keyword_names:
                add_failure(
                    failures,
                    metric="query_variants_follow_up_call",
                    chapter="07",
                    path=str(path.relative_to(PROJECT_ROOT)),
                    message="运行链路调用 generate_query_variants 时必须传 allow_short_structured=intent.intent == 'FOLLOW_UP'。",
                )

    return failures


def check_follow_up_variant_test_coverage() -> list[dict[str, Any]]:
    """确保第 07-19 章测试都锁住追问改写后的查询变体闭环。

    追问改写由真实 LLM 生成，不能再要求某个固定字符串。这里检查的是
    章节测试是否覆盖 FOLLOW_UP、追问输入、改写结果和变体输出这条真实闭环。

    调用顺序：命令行入口 -> check_follow_up_variant_test_coverage()。
    """

    failures: list[dict[str, Any]] = []
    for chapter_no, chapter_dir_name in CHAPTERS:
        if chapter_no < "07":
            continue
        tests_dir = PROJECT_ROOT / "codealong" / "chapters" / chapter_dir_name / "tests"
        test_text = "\n".join(text_of(path) for path in sorted(tests_dir.glob("test_*.py")))
        for fragment in FOLLOW_UP_TEST_MARKERS:
            if fragment not in test_text:
                add_failure(
                    failures,
                    metric="query_variants_follow_up_test",
                    chapter=chapter_no,
                    path=str(tests_dir.relative_to(PROJECT_ROOT)),
                    message=f"章节测试缺少真实追问闭环断言：{fragment}",
                )
        if not any(fragment in test_text for fragment in FOLLOW_UP_REWRITE_MARKERS):
            add_failure(
                failures,
                metric="query_variants_follow_up_test",
                chapter=chapter_no,
                path=str(tests_dir.relative_to(PROJECT_ROOT)),
                message="章节测试缺少追问改写结果断言：rewritten_query/rewritten",
            )
        if not any(fragment in test_text for fragment in FOLLOW_UP_VARIANT_MARKERS):
            add_failure(
                failures,
                metric="query_variants_follow_up_test",
                chapter=chapter_no,
                path=str(tests_dir.relative_to(PROJECT_ROOT)),
                message="章节测试缺少查询变体输出断言：query_variants/variants",
                )
    return failures


def check_no_schema_compatibility_backfills() -> list[dict[str, Any]]:
    """防止跟敲章节重新出现旧库兼容补丁。

    调用顺序：命令行入口 -> check_no_schema_compatibility_backfills()。
    """

    failures: list[dict[str, Any]] = []
    suffixes = {".py", ".md"}
    for chapter_no, chapter_dir_name in CHAPTERS:
        chapter_dir = PROJECT_ROOT / "codealong" / "chapters" / chapter_dir_name
        for path in sorted(chapter_dir.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in suffixes:
                continue
            text = text_of(path)
            for fragment in SCHEMA_COMPATIBILITY_BACKFILL_FRAGMENTS:
                if fragment in text:
                    add_failure(
                        failures,
                        metric="schema_compatibility_backfill",
                        chapter=chapter_no,
                        path=str(path.relative_to(PROJECT_ROOT)),
                        message=f"跟敲章节不保留旧库兼容补丁：{fragment}",
                    )
    return failures


def check_codealong_schema_bootstrap_boundary() -> list[dict[str, Any]]:
    """检查访问 MySQL 的跟敲章节不把 DDL 写回业务 Store。

    调用顺序：命令行入口 -> check_codealong_schema_bootstrap_boundary()。
    """

    failures: list[dict[str, Any]] = []
    for chapter_no, chapter_dir_name in CHAPTERS:
        chapter_dir = PROJECT_ROOT / "codealong" / "chapters" / chapter_dir_name
        if chapter_no in SCHEMA_BOOTSTRAP_CHAPTERS:
            for relative in SCHEMA_BOOTSTRAP_REQUIRED_FILES:
                path = chapter_dir / relative
                if not path.exists():
                    add_failure(
                        failures,
                        metric="codealong_schema_bootstrap",
                        chapter=chapter_no,
                        path=str(path.relative_to(PROJECT_ROOT)),
                        message="访问 MySQL 的跟敲章节必须通过 runtime_schema.sql + bootstrap_mysql_schema() 初始化表结构。",
                    )

        for path in sorted(chapter_dir.rglob("*.py")):
            relative = path.relative_to(chapter_dir).as_posix()
            if relative in SCHEMA_BOOTSTRAP_EXEMPT_PY_FILES:
                continue
            text = text_of(path)
            for fragment, message in SCHEMA_BOOTSTRAP_FORBIDDEN_FRAGMENTS.items():
                if fragment in text:
                    add_failure(
                        failures,
                        metric="codealong_schema_bootstrap",
                        chapter=chapter_no,
                        path=str(path.relative_to(PROJECT_ROOT)),
                        message=message,
                    )
    return failures


def check_codealong_no_early_compatibility_api() -> list[dict[str, Any]]:
    """检查跟敲代码不保留早期兼容 API 或兼容说明。

    调用顺序：命令行入口 -> check_codealong_no_early_compatibility_api()。
    """
    failures: list[dict[str, Any]] = []
    for chapter_no, chapter_dir_name in CHAPTERS:
        chapter_dir = PROJECT_ROOT / "codealong" / "chapters" / chapter_dir_name
        for path in sorted((chapter_dir / "qa_core").rglob("*.py")):
            text = text_of(path)
            if not text:
                continue
            for fragment, message in CODEALONG_FORBIDDEN_COMPAT_FRAGMENTS.items():
                if fragment in text:
                    add_failure(
                        failures,
                        metric="codealong_early_compatibility_api",
                        chapter=chapter_no,
                        path=str(path.relative_to(PROJECT_ROOT)),
                        message=message,
                    )
    return failures


def check_source_filter_boundary() -> list[dict[str, Any]]:
    """检查跟敲代码里 source 校验只停留在入口层，检索底层不重复透传。

    调用顺序：命令行入口 -> check_source_filter_boundary()。
    """
    failures: list[dict[str, Any]] = []

    for chapter_no, chapter_dir_name in CHAPTERS:
        chapter_dir = PROJECT_ROOT / "codealong" / "chapters" / chapter_dir_name

        filters_path = chapter_dir / "qa_core/retrieval/filters.py"
        filters_module = parse_python(filters_path)
        if filters_module is not None:
            filters_text = text_of(filters_path)
            for fragment in ("valid_sources: list[str] | None", "valid_sources is not None", "None 表示不校验"):
                if fragment in filters_text:
                    add_failure(
                        failures,
                        metric="source_filter_boundary",
                        chapter=chapter_no,
                        path=str(filters_path.relative_to(PROJECT_ROOT)),
                        message="validate_source_filter() 必须接收当前场景的明确 source 白名单，不保留 None 跳过校验分支。",
                    )
            for node in function_defs(filters_module, "build_source_expr"):
                if "valid_sources" in arg_names(node):
                    add_failure(
                        failures,
                        metric="source_filter_boundary",
                        chapter=chapter_no,
                        path=str(filters_path.relative_to(PROJECT_ROOT)),
                        message="build_source_expr() 不应接收 valid_sources；source 白名单校验放在入口层。",
                    )
                if calls_named(ast.Module(body=list(node.body), type_ignores=[]), "validate_source_filter"):
                    add_failure(
                        failures,
                        metric="source_filter_boundary",
                        chapter=chapter_no,
                        path=str(filters_path.relative_to(PROJECT_ROOT)),
                        message="build_source_expr() 内不应重复调用 validate_source_filter()。",
                    )

        store_path = chapter_dir / "qa_core/retrieval/store.py"
        store_module = parse_python(store_path)
        if store_module is not None:
            for function_name in ("search", "search_many"):
                for node in function_defs(store_module, function_name):
                    if "valid_sources" in arg_names(node):
                        add_failure(
                            failures,
                            metric="source_filter_boundary",
                            chapter=chapter_no,
                            path=str(store_path.relative_to(PROJECT_ROOT)),
                            message=f"MilvusHybridStore.{function_name}() 不应继续透传 valid_sources。",
                        )
                    for child in ast.walk(node):
                        if isinstance(child, ast.Call) and any(keyword.arg == "valid_sources" for keyword in child.keywords):
                            add_failure(
                                failures,
                                metric="source_filter_boundary",
                                chapter=chapter_no,
                                path=str(store_path.relative_to(PROJECT_ROOT)),
                                message=f"MilvusHybridStore.{function_name}() 内不应继续传递 valid_sources。",
                            )

        steps_path = chapter_dir / "qa_core/pipeline/steps.py"
        steps_module = parse_python(steps_path)
        if steps_module is not None:
            decide_route_nodes = function_defs(steps_module, "decide_route")
            if decide_route_nodes and not any(
                calls_named(ast.Module(body=list(node.body), type_ignores=[]), "validate_source_filter")
                for node in decide_route_nodes
            ):
                add_failure(
                    failures,
                    metric="source_filter_boundary",
                    chapter=chapter_no,
                    path=str(steps_path.relative_to(PROJECT_ROOT)),
                    message="decide_route() 应直接调用 validate_source_filter() 完成入口 source 校验，不再通过 QAService 回调转发。",
                )
            for node in function_defs(steps_module, "prepare_retrieval"):
                if any(isinstance(child, ast.Constant) and child.value == "validate_source" for child in ast.walk(node)):
                    add_failure(
                        failures,
                        metric="source_filter_boundary",
                        chapter=chapter_no,
                        path=str(steps_path.relative_to(PROJECT_ROOT)),
                        message="prepare_retrieval() 不应重复记录 validate_source 阶段。",
                    )
                if calls_named(ast.Module(body=list(node.body), type_ignores=[]), "validate_source"):
                    add_failure(
                        failures,
                        metric="source_filter_boundary",
                        chapter=chapter_no,
                        path=str(steps_path.relative_to(PROJECT_ROOT)),
                        message="prepare_retrieval() 不应重复调用 validate_source。",
                    )

        runtime_path = chapter_dir / "qa_core/pipeline/runtime.py"
        runtime_module = parse_python(runtime_path)
        if runtime_module is not None:
            for node in function_defs(runtime_module, "create_query_context"):
                if "validate_source" in arg_names(node):
                    add_failure(
                        failures,
                        metric="source_filter_boundary",
                        chapter=chapter_no,
                        path=str(runtime_path.relative_to(PROJECT_ROOT)),
                        message="create_query_context() 不应接收 validate_source 回调；source 校验属于 decide_route()。",
                    )
            for node in ast.walk(runtime_module):
                if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "validate_source":
                    add_failure(
                        failures,
                        metric="source_filter_boundary",
                        chapter=chapter_no,
                        path=str(runtime_path.relative_to(PROJECT_ROOT)),
                        message="RAGQueryContext 不应保存 validate_source 回调；请求上下文只保存状态。",
                    )

        rag_path = chapter_dir / "qa_core/pipeline/rag.py"
        rag_module = parse_python(rag_path)
        if rag_module is not None:
            for function_name in ("stream_query", "debug_retrieval"):
                for node in function_defs(rag_module, function_name):
                    if "validate_source" in arg_names(node):
                        add_failure(
                            failures,
                            metric="source_filter_boundary",
                            chapter=chapter_no,
                            path=str(rag_path.relative_to(PROJECT_ROOT)),
                            message=f"{function_name}() 不应接收 validate_source 回调；入口校验在 decide_route() 中完成。",
                        )

        service_path = chapter_dir / "qa_core/application/service.py"
        service_module = parse_python(service_path)
        if service_module is not None:
            for node in ast.walk(service_module):
                if isinstance(node, ast.ImportFrom) and node.module == "qa_core.config.settings":
                    if any(alias.name == "get_settings" for alias in node.names):
                        add_failure(
                            failures,
                            metric="service_dependency_boundary",
                            chapter=chapter_no,
                            path=str(service_path.relative_to(PROJECT_ROOT)),
                            message="QAService 不直接读取全局 settings；配置由下游依赖在各自边界读取。",
                        )
                if isinstance(node, (ast.Assign, ast.AnnAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for target in targets:
                        if (
                            isinstance(target, ast.Attribute)
                            and isinstance(target.value, ast.Name)
                            and target.value.id == "self"
                            and target.attr == "settings"
                        ):
                            add_failure(
                                failures,
                                metric="service_dependency_boundary",
                                chapter=chapter_no,
                                path=str(service_path.relative_to(PROJECT_ROOT)),
                                message="QAService 不保存未使用的 settings 状态；服务层只持有实际编排依赖。",
                            )
            if function_defs(service_module, "validate_source"):
                add_failure(
                    failures,
                    metric="source_filter_boundary",
                    chapter=chapter_no,
                    path=str(service_path.relative_to(PROJECT_ROOT)),
                    message="QAService 不应保留 validate_source() 薄包装；source 校验由 pipeline.steps.decide_route() 直接执行。",
                )

        for rel in SOURCE_FILTER_BOUNDARY_FILES:
            path = chapter_dir / rel
            text = text_of(path)
            if not text:
                continue
            for fragment in (
                "valid_sources=context.scenario.valid_sources",
                "valid_sources=valid_sources",
                "context.validate_source",
                "validate_source=validate_source",
                "self.validate_source",
            ):
                if fragment in text:
                    add_failure(
                        failures,
                        metric="source_filter_boundary",
                        chapter=chapter_no,
                        path=str(path.relative_to(PROJECT_ROOT)),
                        message="source 白名单不要向检索底层透传；保留入口校验即可。",
                    )

    return failures


def check_intent_retrieval_boundary() -> list[dict[str, Any]]:
    """检查跟敲代码里直答路由和检索意图分类不重新混在一起。

    调用顺序：命令行入口 -> check_intent_retrieval_boundary()。
    """
    failures: list[dict[str, Any]] = []
    forbidden_strategy_fragments = (
        "只接受检索类意图",
        "误传给检索计划",
        "intent.direct_answer",
        "直答类意图",
        "raise ValueError",
    )

    for chapter_no, chapter_dir_name in CHAPTERS:
        chapter_dir = PROJECT_ROOT / "codealong" / "chapters" / chapter_dir_name

        for path in sorted(chapter_dir.rglob("*.py")):
            text = text_of(path)
            if "direct_intent and direct_intent.direct_answer" in text:
                add_failure(
                    failures,
                    metric="intent_retrieval_boundary",
                    chapter=chapter_no,
                    path=str(path.relative_to(PROJECT_ROOT)),
                    message="classify_direct_intent() 返回 None 或带 direct_answer 的 IntentResult；调用处只需判断 direct_intent。",
                )

        classifier_path = chapter_dir / "qa_core/intent/classifier.py"
        classifier_module = parse_python(classifier_path)
        if classifier_module is not None:
            classifier_text = text_of(classifier_path)
            for fragment in (
                "from qa_core.config.settings import get_settings",
                "settings = get_settings()",
                "ScenarioDefinition | None = None",
                "if scenario is None",
                "assistant_name = scenario.assistant_name if scenario else",
                "business_domain = scenario.business_domain if scenario else",
                "support_contact = scenario.support_contact if scenario else",
            ):
                if fragment in classifier_text:
                    add_failure(
                        failures,
                        metric="intent_retrieval_boundary",
                        chapter=chapter_no,
                        path=str(classifier_path.relative_to(PROJECT_ROOT)),
                        message="意图分类必须消费上游已解析的 ScenarioDefinition，不保留默认场景或 settings 回退。",
                    )
            for node in function_defs(classifier_module, "classify_intent"):
                node_module = ast.Module(body=list(node.body), type_ignores=[])
                if calls_named(node_module, "classify_direct_intent"):
                    add_failure(
                        failures,
                        metric="intent_retrieval_boundary",
                        chapter=chapter_no,
                        path=str(classifier_path.relative_to(PROJECT_ROOT)),
                        message="classify_intent() 只处理检索类意图，不应重复调用 classify_direct_intent()。",
                    )

        strategy_path = chapter_dir / "qa_core/retrieval/strategy.py"
        strategy_module = parse_python(strategy_path)
        if strategy_module is not None:
            for node in function_defs(strategy_module, "build_retrieval_plan"):
                for child in ast.walk(node):
                    if isinstance(child, ast.Attribute) and child.attr == "direct_answer":
                        add_failure(
                            failures,
                            metric="intent_retrieval_boundary",
                            chapter=chapter_no,
                            path=str(strategy_path.relative_to(PROJECT_ROOT)),
                            message="build_retrieval_plan() 默认只接收检索类 IntentResult，不再判断 direct_answer。",
                        )
                    if isinstance(child, ast.Raise):
                        add_failure(
                            failures,
                            metric="intent_retrieval_boundary",
                            chapter=chapter_no,
                            path=str(strategy_path.relative_to(PROJECT_ROOT)),
                            message="build_retrieval_plan() 不再保留直答意图防御分支；上游 route=retrieval 才会调用它。",
                        )

        strategy_text = text_of(strategy_path)
        for fragment in forbidden_strategy_fragments:
            if fragment in strategy_text:
                add_failure(
                    failures,
                    metric="intent_retrieval_boundary",
                    chapter=chapter_no,
                    path=str(strategy_path.relative_to(PROJECT_ROOT)),
                    message=f"检索计划层不要恢复直答防御口径：{fragment}",
                )

    return failures


def check_pipeline_context_contract() -> list[dict[str, Any]]:
    """检查跟敲章节里 Pipeline 调试返回不重复兜底上下文固定字段。

    调用顺序：命令行入口 -> check_pipeline_context_contract()。
    """
    failures: list[dict[str, Any]] = []
    for chapter_no, chapter_dir_name in CHAPTERS:
        chapter_dir = PROJECT_ROOT / "codealong" / "chapters" / chapter_dir_name
        for relative in (
            "qa_core/pipeline/events.py",
            "qa_core/pipeline/runtime.py",
            "qa_core/pipeline/rag.py",
            "qa_core/pipeline/steps.py",
            "qa_core/pipeline/context.py",
            "qa_core/pipeline/citations.py",
            "qa_core/pipeline/query_variants.py",
            "qa_core/retrieval/results.py",
            "qa_core/retrieval/ranking.py",
            "qa_core/retrieval/store.py",
            "qa_core/intent/question_category.py",
            "qa_core/document_metadata.py",
            "qa_core/indexing/chunking.py",
            "qa_core/indexing/document_normalizer.py",
            "qa_core/quality/chunk.py",
            "qa_core/quality/conflicts.py",
            "qa_core/observability/langsmith_adapter.py",
        ):
            path = chapter_dir / relative
            text = text_of(path)
            if not text:
                continue
            for fragment, message in PIPELINE_CONTEXT_CONTRACT_FRAGMENTS.items():
                if fragment in text:
                    add_failure(
                        failures,
                        metric="pipeline_context_contract",
                        chapter=chapter_no,
                        path=str(path.relative_to(PROJECT_ROOT)),
                        message=message,
                    )
    return failures


def check_prompt_selector_contract() -> list[dict[str, Any]]:
    """检查跟敲章节里 Prompt selector 不保留默认场景回退。

    调用顺序：命令行入口 -> check_prompt_selector_contract()。
    """
    failures: list[dict[str, Any]] = []
    for chapter_no, chapter_dir_name in CHAPTERS:
        path = PROJECT_ROOT / "codealong" / "chapters" / chapter_dir_name / "qa_core/prompts/selector.py"
        text = text_of(path)
        if not text:
            continue
        for fragment, message in PROMPT_SELECTOR_CONTRACT_FRAGMENTS.items():
            if fragment in text:
                add_failure(
                    failures,
                    metric="prompt_selector_contract",
                    chapter=chapter_no,
                    path=str(path.relative_to(PROJECT_ROOT)),
                    message=message,
                )
    return failures


def check_ch19_project_gap_decision() -> list[dict[str, Any]]:
    """确保 CH19 与 V1 完整项目的文件差异都有明确决策登记。

    调用顺序：命令行入口 -> check_ch19_project_gap_decision()。
    """

    failures: list[dict[str, Any]] = []
    decision_text = text_of(GAP_DECISION_DOC)
    if not decision_text:
        add_failure(
            failures,
            metric="codealong_gap_decision_doc",
            chapter="19",
            path=str(GAP_DECISION_DOC.relative_to(PROJECT_ROOT)),
            message="缺少 CH19 与完整项目差异决策文档",
        )
        return failures

    required_fragments = (
        "`mainline`",
        "`appendix`",
        "`productization`",
        "## 差异清单",
        "## 主线补齐顺序",
    )
    for fragment in required_fragments:
        if fragment not in decision_text:
            add_failure(
                failures,
                metric="codealong_gap_decision_structure",
                chapter="19",
                path=str(GAP_DECISION_DOC.relative_to(PROJECT_ROOT)),
                message=f"差异决策文档缺少固定内容：{fragment}",
            )

    ch19_dir = PROJECT_ROOT / "codealong" / "chapters" / "ch19_observability_tracing"
    project_files = {path.relative_to(PROJECT_ROOT).as_posix() for path in (PROJECT_ROOT / "qa_core").rglob("*.py")}
    project_files.add("app.py")
    project_files = {
        relative
        for relative in project_files
        if relative not in V2_ONLY_PROJECT_FILES
        and not any(relative.startswith(prefix) for prefix in V2_ONLY_PROJECT_PATH_PREFIXES)
    }
    ch19_files = {path.relative_to(ch19_dir).as_posix() for path in (ch19_dir / "qa_core").rglob("*.py")}
    if (ch19_dir / "app.py").exists():
        ch19_files.add("app.py")

    missing_files = sorted(project_files - ch19_files)
    for relative in missing_files:
        if f"`{relative}`" not in decision_text:
            add_failure(
                failures,
                metric="codealong_gap_decision_missing_file",
                chapter="19",
                path=str(GAP_DECISION_DOC.relative_to(PROJECT_ROOT)),
                message=f"CH19 缺少完整项目文件但未登记决策：{relative}",
            )

    mainline_files = [
        line.split("|", maxsplit=4)[1].strip().strip("`")
        for line in decision_text.splitlines()
        if line.startswith("| `") and "| `mainline` |" in line
    ]
    if not mainline_files:
        add_failure(
            failures,
            metric="codealong_gap_decision_mainline",
            chapter="19",
            path=str(GAP_DECISION_DOC.relative_to(PROJECT_ROOT)),
            message="差异决策文档没有登记任何 mainline 文件",
        )

    return failures


def run_check() -> dict[str, Any]:
    """执行全部对齐检查并汇总报告。

    检查维度：
      1. 章节结构检查：README、源码、测试文件是否齐全
      2. 章节地图对齐：符号和文件是否与代码匹配
      3. 动画流程对齐：已打磨章节的动画流程是否与代码口径一致
      4. 规则配置对齐：查询变体规则是否已配置化
      5. 追问变体测试覆盖：各章节测试是否锁住追问改写闭环
      6. Schema 初始化口径：不引入兼容迁移和 backfill 分支
      7. 跟敲兼容 API：不保留早期兼容 property 或兼容说明
      8. source 校验边界：入口校验，检索底层不重复透传 valid_sources
      9. 意图分层边界：直答路由不回流到 classify_intent / build_retrieval_plan
      10. Pipeline 上下文契约：调试返回不重复兜底固定字段
      11. Prompt selector 契约：场景变量必须来自已解析 ScenarioDefinition
      12. CH19 项目差异决策：文件差异是否都有明确登记

    调用顺序：命令行入口 -> run_check()。
    """
    failures: list[dict[str, Any]] = []

    # 1. 逐个章节检查
    for chapter_no, chapter_dir_name in CHAPTERS:
        failures.extend(check_chapter(chapter_no, chapter_dir_name))

    # 2. 章节地图与代码对齐
    for issue in validate_maps():
        add_failure(
            failures,
            metric="chapter_map_alignment",
            chapter=issue.chapter,
            path=issue.file_path,
            message=f"{issue.title} / {issue.symbol}: {issue.message}",
        )

    # 3-6. 专项检查
    failures.extend(check_animation_alignment())
    failures.extend(check_rule_config_alignment())
    failures.extend(check_follow_up_variant_test_coverage())
    failures.extend(check_no_schema_compatibility_backfills())
    failures.extend(check_codealong_schema_bootstrap_boundary())
    failures.extend(check_codealong_no_early_compatibility_api())
    failures.extend(check_source_filter_boundary())
    failures.extend(check_intent_retrieval_boundary())
    failures.extend(check_pipeline_context_contract())
    failures.extend(check_prompt_selector_contract())
    failures.extend(check_ch19_project_gap_decision())

    return {
        "report_type": "codealong_alignment_check",
        "created_at": utc_now(),
        "ok": not failures,
        "checked_chapter_count": len(CHAPTERS),
        "failed_count": len(failures),
        "failures": failures,
    }


def main() -> int:
    """命令行入口：执行对齐检查 → 输出报告 → 返回退出码。

    Returns:
        0 = 全部检查通过，1 = 存在对齐问题。

    调用顺序：命令行入口 -> main()。
    """
    parser = argparse.ArgumentParser(description="检查正式讲义与 codealong 跟敲章节是否对齐。")
    parser.add_argument("--json-output", type=Path, default=None, help="可选：把检查报告写入 JSON 文件。")
    args = parser.parse_args()

    configure_utf8_stdio()
    report = run_check()
    write_optional_json(args.json_output, report)
    print_json(report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
