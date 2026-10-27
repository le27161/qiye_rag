# -*- coding: utf-8 -*-
# ============================================================================
# 清理讲义 Markdown 文件中的章节地图块
# ============================================================================
# 该脚本从 CHAPTERS 数据结构中读取每个章节的节点信息，
# 清理历史版本中插入到 docs/*.md 的 <!-- chapter-map:start --> ... <!-- chapter-map:end --> 标记块。
#
# 与 sync_chapter_animations.py 共享 CHAPTERS 数据源。
# 两个脚本的区别：
#   - sync_chapter_animations.py: 生成 docs/animation/ 下的独立 HTML 动画页面
#   - sync_chapter_maps.py:       从正式讲义中移除实现地图标记块
# ============================================================================
"""Remove per-chapter implementation maps from lecture Markdown files."""

from __future__ import annotations

# re: 正则表达式（查找和替换 chapter-map 标记块）
import re

# pathlib.Path: 文件路径操作
from pathlib import Path

# CHAPTERS: 章节节点数据（与 sync_chapter_animations.py 共享）
from sync_chapter_animations import CHAPTERS


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = PROJECT_ROOT / "docs"

START = "<!-- chapter-map:start -->"
END = "<!-- chapter-map:end -->"
MIN_CHAPTER_DOC_LINES = 120

Edge = tuple[str, str] | tuple[str, str, str]


MANUAL_CHAPTERS: list[dict[str, object]] = [
    {
        "no": "01",
        "title": "项目概述与环境搭建",
        "doc": "01-project-overview.md",
        "intro": "本图把第 1 讲的环境准备和项目入口串起来，后续章节都会沿着这套运行环境继续增量开发。",
        "nodes": [
            ("ENV", "运行配置", ".env / .env.compose", "Settings / get_settings()", "准备本机运行和 Docker Compose 运行所需配置。"),
            ("DOCKER", "基础服务", "docker-compose.yml", "milvus / mysql / minio / etcd / api", "启动知识库、历史、对象存储和 API 运行依赖。"),
            ("APP", "应用入口", "app.py", "app = FastAPI", "创建 FastAPI 应用并注册页面、API 和治理路由。"),
            ("STATIC", "讲义站点", "mkdocs.yml + docs/", "mkdocs build", "生成课程讲义站点并作为后续学习入口。"),
            ("VERIFY", "环境验证", "qa_core/config/preflight.py", "validate_runtime_environment()", "检查关键配置、模型路径和场景配置是否可用。"),
        ],
    },
    {
        "no": "02",
        "title": "RAG 核心概念深入",
        "doc": "02-rag-fundamentals.md",
        "intro": "本图把 Embedding、Hybrid Search、Rerank 和上下文生成放到项目代码落点上，后续实现会逐章补齐这些节点。",
        "nodes": [
            ("EMBED", "文本向量化", "qa_core/retrieval/models.py", "get_embedding_model()", "把用户问题和文档 chunk 转成 Dense 向量。"),
            ("SPARSE", "关键词稀疏召回", "qa_core/retrieval/store.py", "BM25BuiltInFunction", "用 BM25 Sparse Function 补足关键词匹配能力。"),
            ("HYBRID", "混合检索", "qa_core/retrieval/store.py", "MilvusHybridStore.search_many()", "融合 Dense 与 Sparse 召回结果。"),
            ("RERANK", "精排重排", "qa_core/retrieval/ranking.py", "rerank_hits()", "用 CrossEncoder 对候选证据重新排序。"),
            ("CONTEXT", "上下文构建", "qa_core/pipeline/context.py", "build_context()", "把高质量证据整理为可引用上下文。"),
            ("ANSWER", "答案生成", "qa_core/pipeline/rag.py", "stream_query()", "让 LLM 基于上下文生成可溯源答案。"),
        ],
    },
    {
        "no": "03",
        "title": "LangChain 生态系统",
        "doc": "03-langchain-ecosystem.md",
        "intro": "本图只展示本项目真正使用的 LangChain 能力：它们是工程适配器，不替代业务编排。",
        "nodes": [
            ("CHAT", "模型适配", "qa_core/llm/client.py", "get_chat_model()", "用 ChatOpenAI 兼容接口接入 DashScope 等模型服务。"),
            ("MSG", "对话消息", "qa_core/memory/history.py", "format_messages()", "用消息对象组织多轮历史和追问上下文。"),
            ("STRUCT", "结构化输出", "qa_core/pipeline/query_variants.py", "with_structured_output(QueryVariants)", "让模型输出稳定的查询变体结构。"),
            ("DOC", "文档对象", "qa_core/indexing/document_loaders.py", "load_file()", "把多格式资料加载成 LangChain Document。"),
            ("SPLIT", "文本切分", "qa_core/indexing/chunking.py", "split_documents()", "把长文档切成可检索 chunk。"),
            ("VECTOR", "向量库封装", "qa_core/retrieval/store.py", "MilvusHybridStore", "封装 langchain-milvus 与 PyMilvus 的检索边界。"),
        ],
    },
    {
        "no": "04",
        "title": "Milvus 索引机制与基本操作",
        "doc": "04-milvus-index-and-operations.md",
        "intro": "本图把第 4 讲的 Milvus 基础操作对应到项目后续真实检索代码，完整入库链路在第 16 讲展开。",
        "nodes": [
            ("DB", "连接与数据库", "qa_core/retrieval/milvus_compat.py", "ensure_milvus_database()", "确认 Milvus 连接和 database 可用。"),
            ("CONN", "连接参数", "qa_core/retrieval/milvus_compat.py", "langchain_connection_args()", "统一生成 Milvus URI / database 参数，目标集合由 collection_name 决定。"),
            ("FACTORY", "Store 创建", "qa_core/retrieval/factory.py", "get_faq_store() / get_doc_store()", "按场景 collection 创建 FAQ 与文档检索 store。"),
            ("INDEX", "写入与索引", "qa_core/retrieval/store.py", "add_documents()", "把 Document 写入 Milvus 并依赖 collection schema/index。"),
            ("SEARCH", "检索执行", "qa_core/retrieval/store.py", "search_many()", "执行带过滤条件的 Dense + Sparse 混合检索。"),
            ("RESULT", "结果对象", "qa_core/retrieval/results.py", "RetrievalResult", "把 hits、top_score 和来源快照交给后续章节。"),
        ],
    },
]


MAP_EDGES: dict[str, list[Edge]] = {
    "02": [
        ("EMBED", "HYBRID"),
        ("SPARSE", "HYBRID"),
        ("HYBRID", "RERANK"),
        ("RERANK", "CONTEXT"),
        ("CONTEXT", "ANSWER"),
    ],
    "04": [
        ("DB", "CONN"),
        ("CONN", "FACTORY"),
        ("FACTORY", "INDEX"),
        ("INDEX", "SEARCH"),
        ("SEARCH", "RESULT"),
    ],
    "05": [
        ("DEMO", "SCENARIO"),
        ("DEMO", "ROUTE"),
        ("SCENARIO", "SOURCE"),
        ("SCENARIO", "DIRECT"),
        ("SOURCE", "ROUTE"),
        ("ROUTE", "DIRECT"),
        ("ROUTE", "CLASSIFY"),
        ("DIRECT", "OUT", "直答分支"),
        ("CLASSIFY", "OUT", "检索分支"),
    ],
    "06": [
        ("INPUT", "INTENT"),
        ("INTENT", "CATEGORY"),
        ("INTENT", "TABLE"),
        ("INTENT", "BASE"),
        ("CATEGORY", "PLAN"),
        ("TABLE", "PLAN"),
        ("BASE", "PLAN"),
        ("PLAN", "OUT"),
    ],
    "07": [
        ("PREP", "HISTORY"),
        ("HISTORY", "REWRITE"),
        ("REWRITE", "MODEL"),
        ("MODEL", "STRUCT"),
        ("STRUCT", "DEDUP"),
        ("PREP", "HEURISTIC"),
        ("HEURISTIC", "DEDUP"),
        ("DEDUP", "OUT"),
    ],
    "09": [
        ("FACTORY", "SERVICE"),
        ("HISTORY", "SERVICE"),
        ("SERVICE", "VALIDATE"),
        ("SERVICE", "STREAM"),
        ("SERVICE", "DEBUG"),
        ("STREAM", "OUT"),
        ("DEBUG", "OUT"),
    ],
    "10": [
        ("STREAM", "CTX"),
        ("CTX", "EVENT_START"),
        ("EVENT_START", "ROUTE"),
        ("ROUTE", "PREP", "retrieval"),
        ("PREP", "FAQ"),
        ("FAQ", "ANSWER", "高置信直出"),
        ("FAQ", "DOC", "继续检索"),
        ("DOC", "CONTEXT"),
        ("CONTEXT", "ANSWER"),
    ],
    "11": [
        ("PROFILE", "SELECT"),
        ("TEMPLATES", "SELECT"),
        ("SCENARIO", "SELECT"),
        ("SELECT", "PROMPT"),
        ("PROMPT", "ANSWER"),
        ("ANSWER", "DIAG"),
    ],
    "12": [
        ("APP", "ROUTER"),
        ("ROUTER", "CONTEXT"),
        ("SCHEMA", "CONTEXT"),
        ("CONTEXT", "COLLECT"),
        ("COLLECT", "WS"),
        ("CONTEXT", "DEBUG"),
        ("ROUTER", "FEEDBACK"),
        ("ROUTER", "ERROR"),
    ],
    "13": [
        ("SETTINGS", "CHECK_VALUE"),
        ("SETTINGS", "CHECK_PATH"),
        ("SETTINGS", "CHECK_SCENARIO"),
        ("CHECK_VALUE", "PREFLIGHT"),
        ("CHECK_PATH", "PREFLIGHT"),
        ("CHECK_SCENARIO", "PREFLIGHT"),
        ("PREFLIGHT", "VALIDATE"),
        ("VALIDATE", "APP"),
        ("SETTINGS", "LOG"),
    ],
    "14": [
        ("COMMON", "GEN"),
        ("GEN", "MODEL"),
        ("MYSQL", "STORE"),
        ("MODEL", "STORE"),
        ("STORE", "ENSURE"),
        ("ENSURE", "RESULT"),
        ("RESULT", "ACTIVE"),
        ("ACTIVE", "QUERY"),
        ("STORE", "API"),
        ("API", "ACTIVE"),
    ],
    "15": [
        ("CLEAN", "SCOPE"),
        ("CLEAN", "RESOLVE"),
        ("SCOPE", "RESOLVE"),
        ("RESOLVE", "CONTEXT"),
        ("ESCAPE", "SOURCE"),
        ("CONTEXT", "SOURCE"),
        ("SOURCE", "STORE"),
        ("STORE", "TEST"),
    ],
    "16": [
        ("INGEST", "FILES"),
        ("INGEST", "MANIFEST"),
        ("FILES", "FINGER"),
        ("FINGER", "MANIFEST"),
        ("MANIFEST", "REUSE", "基线未变化"),
        ("REUSE", "WRITE", "引用旧 chunk 有效期"),
        ("FILES", "LOAD", "变化文件"),
        ("LOAD", "TABLE", "表格文件"),
        ("LOAD", "NORMALIZE", "普通文档"),
        ("TABLE", "NORMALIZE"),
        ("META", "NORMALIZE"),
        ("UTILS", "CHUNK"),
        ("NORMALIZE", "CHUNK"),
        ("CHUNK", "WRITE"),
        ("WRITE", "MANIFEST", "记录 chunk_id"),
        ("WRITE", "VERSION"),
        ("FAQ", "VERSION"),
        ("META", "CITE", "在线引用"),
    ],
    "17": [
        ("REPORT", "FAQ_READ"),
        ("FAQ_READ", "FAQ_ANALYZE"),
        ("FAQ_ANALYZE", "CONFLICT"),
        ("META", "CONFLICT"),
        ("REPORT", "CHUNK"),
        ("CONFLICT", "DEMO"),
        ("CHUNK", "DEMO"),
        ("DEMO", "TEST"),
    ],
    "18": [
        ("UNIT", "GUARD"),
        ("INTENT", "GUARD"),
        ("RETRIEVAL", "GUARD"),
        ("GUARD", "SMOKE"),
        ("SMOKE", "REPORT"),
        ("REPORT", "OUT"),
    ],
    "19": [
        ("CONFIG", "STATUS"),
        ("STATUS", "TRACE"),
        ("CTX", "STAGE"),
        ("STAGE", "TOKEN"),
        ("TOKEN", "CITE"),
        ("CITE", "FINALIZE"),
        ("FINALIZE", "TRACE"),
        ("TRACE", "FINISH"),
        ("FINISH", "DEMO"),
    ],
}


def _escape_mermaid(value: str) -> str:
    """转义 Mermaid 流程图中的特殊字符，防止渲染异常。

    调用顺序：命令行入口 -> _escape_mermaid()。
    """
    return (
        value.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _node_id(index: int) -> str:
    """根据节点序号生成 Mermaid 节点 ID（M1, M2, ...）。

    调用顺序：命令行入口 -> _node_id()。
    """
    return f"M{index + 1}"


def _build_mermaid(
    no: str,
    nodes: list[tuple[str, str, str, str, str]],
    edges: list[Edge],
) -> str:
    """生成章节功能闭环的 Mermaid 流程图。

    流程图的视觉约定：
      - 首节点用灰色背景（入口），尾节点用绿色背景（产出）
      - 中间节点按序号交替使用蓝、紫、黄色背景
      - 每条边上可选加上中文标签（如 "直答分支" / "检索分支"）

    调用顺序：命令行入口 -> _build_mermaid()。
    """
    # 构造节点 ID：C{章节号}_{节点ID}，如 C05_DEMO
    node_ids = {raw_id: f"C{no}_{re.sub(r'[^0-9A-Za-z_]', '_', raw_id)}" for raw_id, *_ in nodes}
    lines = ["```mermaid", "flowchart TD"]
    # 定义节点
    for index, node in enumerate(nodes):
        raw_id, title, _, symbol, _ = node
        label = f"{_escape_mermaid(title)}<br/>{_escape_mermaid(symbol)}"
        # 尾节点使用六边形（产出节点），其他节点使用方框
        shape_open = "{{" if index == len(nodes) - 1 else "["
        shape_close = "}}" if index == len(nodes) - 1 else "]"
        lines.append(f'    {node_ids[raw_id]}{shape_open}"{label}"{shape_close}')
    # 定义边
    for edge in edges:
        if len(edge) == 2:
            left, right = edge
            lines.append(f"    {node_ids[left]} --> {node_ids[right]}")
        else:
            left, right, label = edge
            lines.append(f'    {node_ids[left]} -->|"{_escape_mermaid(label)}"| {node_ids[right]}')
    # 定义节点样式（颜色约定）
    for index in range(len(nodes)):
        raw_id = nodes[index][0]
        node_id = node_ids[raw_id]
        if index == 0:
            fill, stroke = "#F8FAFC", "#64748B"   # 入口：灰色
        elif index == len(nodes) - 1:
            fill, stroke = "#DCFCE7", "#16A34A"  # 产出：绿色
        elif index % 3 == 1:
            fill, stroke = "#DBEAFE", "#2563EB"  # 蓝色
        elif index % 3 == 2:
            fill, stroke = "#F5F3FF", "#7C3AED"  # 紫色
        else:
            fill, stroke = "#FEF3C7", "#D97706"  # 黄色
        lines.append(f"    style {node_id} fill:{fill},stroke:{stroke},stroke-width:2px")
    lines.append("```")
    return "\n".join(lines)


def _build_table(nodes: list[tuple[str, str, str, str, str]]) -> str:
    """生成章节节点与代码对齐的 Markdown 表格。

    表格列：节点 | 对齐文件 | 函数/对象 | 本章职责
    学员可以通过此表格快速定位每个功能对应的源码位置。

    调用顺序：命令行入口 -> _build_table()。
    """
    lines = [
        "| 节点 | 对齐文件 | 函数/对象 | 本章职责 |",
        "| --- | --- | --- | --- |",
    ]
    for _, title, file_path, symbol, body in nodes:
        lines.append(f"| {title} | `{file_path}` | `{symbol}` | {body} |")
    return "\n".join(lines)


def _normalize_nodes(chapter: dict[str, object]) -> list[tuple[str, str, str, str, str]]:
    """将章节字典中的节点数据规范化为五元组。

    返回格式：(node_id, title, file_path, symbol, body)
    每个字段都转为纯字符串，避免后续渲染时出现 None 或非字符串值。

    调用顺序：命令行入口 -> _normalize_nodes()。
    """
    return [
        (str(node_id), str(title), str(file_path), str(symbol), str(body))
        for node_id, title, file_path, symbol, body in chapter["nodes"]  # type: ignore[index]
    ]


def _build_section(chapter: dict[str, object]) -> str:
    """构建一个章节的完整地图 Markdown 块。

    包含：章节介绍 → Mermaid 流程图 → 节点与代码对齐表格
    如果 MAP_EDGES 中没有该章节的边定义，则自动生成顺序边（A→B→C→...）。
    输出以 chapter-map:start / chapter-map:end 标记包裹。

    调用顺序：命令行入口 -> _build_section()。
    """
    no = str(chapter["no"])
    intro = str(
        chapter.get(
            "intro",
            "本图对应本讲功能闭环，展示从输入到本讲交付物的主干路径。节点与主项目代码文件和函数保持一致，后续章节消费的能力只作为交付边界出现。",
        )
    )
    nodes = _normalize_nodes(chapter)
    # 获取边定义：优先使用显式定义的边，否则生成顺序边
    edges = MAP_EDGES.get(no) or [(left[0], right[0]) for left, right in zip(nodes, nodes[1:])]
    # 安全校验：边中引用的节点 ID 必须在节点列表中
    known_ids = {node[0] for node in nodes}
    missing_ids = sorted({node_id for edge in edges for node_id in edge[:2]} - known_ids)
    if missing_ids:
        raise ValueError(f"Chapter {no} map edges reference unknown node ids: {missing_ids}")
    return (
        f"{START}\n"
        "## 本讲地图\n\n"
        f"{intro}\n\n"
        f"### 图 1：第 {no} 讲功能闭环地图\n\n"
        f"{_build_mermaid(no, nodes, edges)}\n\n"
        "### 节点与代码对齐\n\n"
        f"{_build_table(nodes)}\n"
        f"{END}\n"
    )


def _section_end(text: str, start: int) -> int:
    """找到从 start 位置开始的当前 section 结束位置。

    识别规则：下一个 ## 标题 或 --- 分隔线即为 section 边界。
    如果没有找到边界，返回文本末尾。

    调用顺序：命令行入口 -> _section_end()。
    """
    candidates: list[int] = []
    for pattern in (r"\n## ", r"\n---\s*\n"):
        match = re.search(pattern, text[start + 1 :])
        if match:
            candidates.append(start + 1 + match.start())
    return min(candidates) if candidates else len(text)


def _insert_index(text: str) -> int:
    """找到章节地图 Markdown 块的插入位置。

    优先级：
      1. "本讲目标" section 之后（最常见）
      2. "本章动画" section 之后（独立演示页）
      3. 第一个 ## 标题之前（兜底）

    调用顺序：命令行入口 -> _insert_index()。
    """
    goal_match = re.search(r"\n## 本讲目标\b", text)
    if goal_match:
        return _section_end(text, goal_match.start())

    animation_match = re.search(r"\n## 本章动画\b", text)
    if animation_match:
        return _section_end(text, animation_match.start())

    h1_match = re.search(r"\n## ", text)
    return h1_match.start() if h1_match else len(text)


def sync_doc(chapter: dict[str, object]) -> bool:
    """清理单个章节讲义文件中的 chapter-map 标记块。

    Returns:
        True 表示文件被修改，False 表示无变化。

    调用顺序：命令行入口 -> sync_doc()。
    """
    doc_path = DOCS_DIR / str(chapter["doc"])
    text = doc_path.read_text(encoding="utf-8")
    new_text = re.sub(
        rf"\n?{re.escape(START)}.*?{re.escape(END)}\n?",
        "\n",
        text,
        count=1,
        flags=re.S,
    )

    if new_text == text:
        return False
    # 安全阀：防止意外截断导致文件过短
    if str(chapter["no"]) >= "05" and len(new_text.splitlines()) < MIN_CHAPTER_DOC_LINES:
        raise ValueError(
            f"Refusing to write suspiciously short chapter doc {doc_path.relative_to(PROJECT_ROOT)}: "
            f"{len(new_text.splitlines())} lines"
        )
    doc_path.write_text(new_text, encoding="utf-8")
    return True


def main() -> None:
    """命令行入口：同步所有章节的文档映射关系。

    调用顺序：命令行入口 -> main()。
    """
    chapters = MANUAL_CHAPTERS + CHAPTERS
    changed = sum(1 for chapter in chapters if sync_doc(chapter))
    print(f"Removed chapter map blocks for {len(chapters)} chapters; changed {changed} files.")


if __name__ == "__main__":
    main()
