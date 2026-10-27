# -*- coding: utf-8 -*-
# ============================================================================
# 章节地图元数据校验 — 验证 codealong 章节地图与代码文件对齐
# ============================================================================
# 该脚本读取 sync_chapter_animations.py 中定义的 CHAPTERS 节点数据，
# 验证每个节点声明的文件路径和符号是否在实际代码中存在。
#
# 校验内容：
#   1. 文件路径校验 — 节点中声明的文件在章节目录中是否存在
#   2. 符号校验     — 节点中声明的函数/类/方法是否在对应文件中存在
#
# 特殊处理：
#   - SKIP_SYMBOLS: 不检查的符号（占位符、命令字符串、配置常量等）
#   - SYMBOL_ALIASES: 符号别名的映射（如 "QAService.stream_query()" →
#     ["class QAService", "def stream_query"]）
#
# 退出码：0 = 校验通过，1 = 存在问题
# ============================================================================

"""校验章节流程地图引用的源码文件和符号是否真实存在。

调用顺序：课程示例、测试或命令行入口 -> 本模块公开接口。
"""

from __future__ import annotations

# fnmatch: Unix 文件名模式匹配（支持 * ? [] 通配符）
import fnmatch

# re: 正则表达式（用于分割 + 连接的路径和符号字符串）
import re

# dataclasses: 数据类定义（MapIssue）
from dataclasses import dataclass

# pathlib.Path: 文件路径操作
from pathlib import Path

# CHAPTERS: 从同步脚本中导入的章节节点数据
from sync_chapter_animations import CHAPTERS


# ── 常量定义 ──

# PROJECT_ROOT: 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# SKIP_SYMBOLS: 不需要校验的符号白名单
# 这些是占位符、命令字符串或配置常量，不需要在代码中查找
SKIP_SYMBOLS = {
    "DEFAULT_*",
    "archive payload",
    "retrieval_info['prompt_profile']",
    "list/rollback/archive payload",
    "rollback",
    "python -m unittest / acceptance_smoke",
    "python -m unittest",
    "store.delete_ids() / add_documents()",
    "store.delete_ids()",
    "add_documents()",
    "search_many(..., data_scope=...)",
    "search_many(...",
    "data_scope=...)",
    "active_kb_version",
    "run_guardrails()",
    "unittest",
    "router",
    "BM25BuiltInFunction",
    "MilvusHybridStore",
    "Collection.hybrid_search()",
    "os.walk()",
}

# SYMBOL_ALIASES: 符号别名映射
# 键是地图中使用的自然语言名称，值是对应的代码中搜索标记
SYMBOL_ALIASES = {
    "QueryServiceContext.from_ws_payload()": ("class QueryServiceContext", "def from_ws_payload"),
    "from_debug_request()": "def from_debug_request",
    "FeedbackStore.add_feedback()": ("class FeedbackStore", "def add_feedback"),
    "QAService.stream_query()": ("class QAService", "def stream_query"),
    "resolve_scenario()": "def resolve_scenario",
    "Settings": "class Settings",
    "RetrievalPlan": "class RetrievalPlan",
    "IntentResult": "class IntentResult",
    "RouteDecision": "class RouteDecision",
    "DataScope": "class DataScope",
    "KnowledgeBaseVersion": "class KnowledgeBaseVersion",
    "KnowledgeBaseVersionStore": "class KnowledgeBaseVersionStore",
    "IndexManifest": "class IndexManifest",
    "RAGQueryContext": "class RAGQueryContext",
    "PromptProfile": "class PromptProfile",
    "QueryVariants": "class QueryVariants",
    "TestSystemChapter18Test": "class TestSystemChapter18Test",
    "QualityReportChapter17Test": "class QualityReportChapter17Test",
    "_MySqlStore": "class _MySqlStore",
}


@dataclass(frozen=True)
class MapIssue:
    """一个地图校验发现的问题。

    Attributes:
        chapter: 章节号（如 "05"）
        title: 节点标题
        file_path: 声明的文件路径
        symbol: 声明的符号
        message: 问题描述（"文件不存在" / "符号未在对应文件中找到"）

    调用顺序：命令行入口 -> MapIssue。
    """
    chapter: str
    title: str
    file_path: str
    symbol: str
    message: str

    def format(self) -> str:
        """格式化为一行可读的错误信息。

        调用顺序：命令行入口 -> MapIssue.format()。
        """
        return f"第 {self.chapter} 章 {self.title}: {self.file_path} / {self.symbol} - {self.message}"


def _chapter_root(chapter: dict[str, object]) -> Path:
    """返回章节目录路径。

    调用顺序：命令行入口 -> _chapter_root()。
    """
    return PROJECT_ROOT / str(chapter["path"])


def _split_file_items(value: str) -> list[str]:
    """拆分地图节点中的文件路径。

    调用顺序：命令行入口 -> _split_file_items()。
    """
    if not value:
        return []
    parts = re.split(r"\s*(?:,|，|\+|\band\b)\s*", value)
    return [part.strip() for part in parts if part.strip()]


def _split_symbol_items(value: str) -> list[str]:
    """拆分地图节点中用斜杠或逗号连接的符号。

    调用顺序：命令行入口 -> _split_symbol_items()。
    """
    if not value:
        return []
    parts = re.split(r"\s*(?:/|,|，|\+|\band\b)\s*", value)
    return [part.strip() for part in parts if part.strip()]


def _skip_symbol(symbol: str) -> bool:
    """判断符号是否属于无需落代码检查的展示型节点。

    调用顺序：命令行入口 -> _skip_symbol()。
    """
    return symbol in SKIP_SYMBOLS or any(fnmatch.fnmatch(symbol, pattern) for pattern in SKIP_SYMBOLS)


def _symbol_needles(symbol: str) -> tuple[str, ...]:
    """把地图符号转成源文件中的搜索标记。

    调用顺序：命令行入口 -> _symbol_needles()。
    """
    alias = SYMBOL_ALIASES.get(symbol)
    if isinstance(alias, tuple):
        return alias
    if isinstance(alias, str):
        return (alias,)
    if symbol.endswith("()"):
        return (f"def {symbol[:-2]}",)
    return (symbol,)


def _symbol_exists(source_text: str, symbol: str) -> bool:
    """判断符号是否存在于文件内容。

    调用顺序：命令行入口 -> _symbol_exists()。
    """
    if _skip_symbol(symbol):
        return True
    return all(needle in source_text for needle in _symbol_needles(symbol))


def _read_source_target(target: Path) -> str:
    """读取文件或目录中的 Python/文本源码。

    调用顺序：命令行入口 -> _read_source_target()。
    """
    if target.is_dir():
        parts: list[str] = []
        for path in sorted(target.rglob("*.py")):
            parts.append(path.read_text(encoding="utf-8", errors="ignore"))
        return "\n".join(parts)
    return target.read_text(encoding="utf-8", errors="ignore")


def validate_maps() -> list[MapIssue]:
    """校验章节地图中的文件和符号是否能对齐到章节代码。

    调用顺序：命令行入口 -> validate_maps()。
    """
    issues: list[MapIssue] = []
    for chapter in CHAPTERS:
        chapter_no = str(chapter["no"])
        chapter_root = _chapter_root(chapter)
        for node in chapter["nodes"]:  # type: ignore[index]
            _, title, file_value, symbol_value, _ = node
            file_paths = _split_file_items(str(file_value))
            symbols = _split_symbol_items(str(symbol_value))
            if not file_paths:
                continue
            source_texts: dict[str, str] = {}
            for relative_file in file_paths:
                target = chapter_root / relative_file
                if not target.exists():
                    issues.append(
                        MapIssue(chapter_no, str(title), relative_file, str(symbol_value), "文件不存在")
                    )
                    continue
                source_texts[relative_file] = _read_source_target(target)
            if not source_texts or not symbols:
                continue
            for symbol in symbols:
                if any(_symbol_exists(source_text, symbol) for source_text in source_texts.values()):
                    continue
                issues.append(
                    MapIssue(chapter_no, str(title), " / ".join(source_texts.keys()), symbol, "符号未在对应文件中找到")
                )
    return issues


def main() -> int:
    """命令行入口。

    调用顺序：命令行入口 -> main()。
    """
    issues = validate_maps()
    if not issues:
        print("章节地图校验通过：05-19 地图节点均能对齐到对应章节代码。")
        return 0
    for issue in issues:
        print(issue.format())
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
