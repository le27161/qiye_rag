# -*- coding: utf-8 -*-
# ============================================================================
# 文档一致性检查 — 防止 README、架构文档和验收命令滞后
# ============================================================================
# 这不是语法检查，而是防止 README、架构文档和验收命令在多轮优化后滞后。
# 当前项目已经冻结为 8 个业务场景，一期只做 RAG；
# 这些边界如果文档里说错，会让学习路径和交付口径同时跑偏。
#
# 检查内容：
#   1. 必需文件是否存在（REQUIRED_PATHS）
#      - README.md、docs/ 关键文档、scripts/ 关键脚本、eval_sets/ 评测集
#   2. README 关键片段是否保留（README_REQUIRED_SNIPPETS）
#      - "当前业务场景已经冻结为 8 个"
#      - "LangChain + Milvus Hybrid Search + FastAPI"
#      - "Bad Case 闭环"
#      - "一期源码不提前放 Agent 预留实现"
#      - "GraphRAG"
#   3. README 场景表行数是否正确（FROZEN_SCENARIO_COUNT = 8）
#   4. 课程大纲关键片段是否保留（COURSE_REQUIRED_SNIPPETS）
#      - "20 讲系统化课程"、"P3 扩展方向"、"GraphRAG Agent" 等
#
# 用法示例：
#   python scripts\check_docs_consistency.py
#   python scripts\check_docs_consistency.py --output reports/verification/docs_consistency_latest.json
#
# 退出码：0 = 一致，1 = 存在不一致
# ============================================================================

"""校验冻结场景、讲义导航和发布文档是否保持一致。

调用顺序：课程示例、测试或命令行入口 -> 本模块公开接口。
"""

from __future__ import annotations

# argparse: 命令行参数解析
import argparse

# json: 标准 JSON 序列化
import json

# sys: 系统功能（sys.path + sys.exit）
import sys

# pathlib.Path: 文件路径操作
from pathlib import Path

# typing.Any: 任意类型（failures 列表的元素类型）
from typing import Any

# ── 路径设置 ──
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# ── 导入公共工具 ──
from scripts.common import configure_utf8_stdio, utc_now, write_optional_json


FROZEN_SCENARIO_COUNT = 8
REQUIRED_PATHS = (
    "README.md",
    "docs/index.md",
    "docs/course-outline.md",
    "docs/01-project-overview.md",
    "docs/19-observability-tracing.md",
    "docs/appendix/appendix-h-tool-foundations.md",
    "scripts/enterprise_overlay/run_enterprise_overlay_activation.py",
    "eval_sets/business_depth_regression.json",
    "eval_sets/enterprise_overlay_regression.json",
    "eval_sets/phase1_performance_baseline.json",
)
README_REQUIRED_SNIPPETS = (
    "当前业务场景已经冻结为 8 个",
    "LangChain + Milvus Hybrid Search + FastAPI",
    "Bad Case 闭环",
    "一期源码不提前放 Agent 预留实现",
    "GraphRAG",
)
COURSE_REQUIRED_SNIPPETS = (
    "20 讲系统化课程",
    "P3 扩展方向",
    "GraphRAG Agent",
    "Router/Planner",
    "01 → 19",
)
PUBLIC_CHAPTER_DOC_GLOBS = (
    "docs/[0-9][0-9]-*.md",
)
FORBIDDEN_INTERNAL_VOICE = (
    "\u5b66\u4e60\u8005\u4f1a",
    "\u9879\u76ee\u8868\u8fbe",
    "\u8bc4\u5ba1\u65b9",
    "\u8bfe\u7a0b\u4e0a\u53ef\u4ee5\u5f3a\u8c03",
    "\u8bfe\u7a0b\u6f14\u793a",
    "\u8bb2\u89e3\u8005",
    "\u8bb2\u89e3",
    "\u6c47\u62a5",
    "\u9996\u8f6e\u6559\u5b66",
    "\u53cd\u9762\u6559\u6750",
)


def text_of(path: Path) -> str:
    """读取文本文件；不存在时返回空字符串。

    调用顺序：命令行入口 -> text_of()。
    """
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def check_required_paths() -> list[dict[str, Any]]:
    """检查文档和关键脚本是否存在。

    调用顺序：命令行入口 -> check_required_paths()。
    """
    failures: list[dict[str, Any]] = []
    for rel_path in REQUIRED_PATHS:
        path = PROJECT_ROOT / rel_path
        if not path.exists():
            failures.append({"metric": "required_path", "path": rel_path, "message": "必需文件不存在"})
    return failures


def check_readme() -> list[dict[str, Any]]:
    """检查 README 是否仍反映当前一期边界。

    调用顺序：命令行入口 -> check_readme()。
    """
    failures: list[dict[str, Any]] = []
    readme = text_of(PROJECT_ROOT / "README.md")
    for snippet in README_REQUIRED_SNIPPETS:
        if snippet not in readme:
            failures.append({"metric": "readme_snippet", "path": "README.md", "message": f"README 缺少关键说明：{snippet}"})
    scenario_section = readme.split("## 2. 业务场景", 1)[-1].split("\n## ", 1)[0]
    scenario_rows = [line for line in scenario_section.splitlines() if line.startswith("| `") and "` |" in line]
    if len(scenario_rows) != FROZEN_SCENARIO_COUNT:
        failures.append(
            {
                "metric": "readme_scenario_count",
                "path": "README.md",
                "message": f"README 场景表应为 {FROZEN_SCENARIO_COUNT} 行，当前 {len(scenario_rows)} 行",
            }
        )
    return failures


def check_course_outline() -> list[dict[str, Any]]:
    """检查课程大纲是否保留当前 19 讲和二期边界表达。

    调用顺序：命令行入口 -> check_course_outline()。
    """
    failures: list[dict[str, Any]] = []
    outline = text_of(PROJECT_ROOT / "docs" / "course-outline.md")
    for snippet in COURSE_REQUIRED_SNIPPETS:
        if snippet not in outline:
            failures.append(
                {
                    "metric": "course_outline_snippet",
                    "path": "docs/course-outline.md",
                    "message": f"课程大纲缺少关键说明：{snippet}",
                }
            )
    return failures


def check_public_chapter_tone() -> list[dict[str, Any]]:
    """检查正式章节讲义避免出现内部备课口吻。

    调用顺序：命令行入口 -> check_public_chapter_tone()。
    """
    failures: list[dict[str, Any]] = []
    for pattern in PUBLIC_CHAPTER_DOC_GLOBS:
        for path in sorted(PROJECT_ROOT.glob(pattern)):
            text = text_of(path)
            for line_no, line in enumerate(text.splitlines(), start=1):
                for phrase in FORBIDDEN_INTERNAL_VOICE:
                    if phrase in line:
                        failures.append(
                            {
                                "metric": "public_chapter_tone",
                                "path": str(path.relative_to(PROJECT_ROOT)),
                                "line": line_no,
                                "message": f"正式讲义不应出现内部视角表达：{phrase}",
                            }
                        )
    return failures


def build_report() -> dict[str, Any]:
    """生成文档一致性检查报告。

    调用顺序：命令行入口 -> build_report()。
    """
    failures = [*check_required_paths(), *check_readme(), *check_course_outline(), *check_public_chapter_tone()]
    return {
        "report_type": "docs_consistency_check",
        "created_at": utc_now(),
        "ok": not failures,
        "frozen_scenario_count": FROZEN_SCENARIO_COUNT,
        "checked_path_count": len(REQUIRED_PATHS),
        "failed_count": len(failures),
        "failures": failures,
    }


def build_parser() -> argparse.ArgumentParser:
    """构造命令行解析器。

    调用顺序：命令行入口 -> build_parser()。
    """
    parser = argparse.ArgumentParser(description="Check documentation consistency for phase-1 RAG project.")
    parser.add_argument("--output", default=str(PROJECT_ROOT / "reports" / "verification" / "docs_consistency_latest.json"))
    return parser


def main() -> None:
    """执行文档一致性检查。

    调用顺序：命令行入口 -> main()。
    """
    configure_utf8_stdio()
    args = build_parser().parse_args()
    payload = build_report()
    write_optional_json(args.output, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if not payload["ok"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
