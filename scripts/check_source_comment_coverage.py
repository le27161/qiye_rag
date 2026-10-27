"""检查 V1 自有源码是否具备可维护的职责与公开接口说明。

检查范围覆盖主项目、运维脚本、测试、前端 JavaScript 和章节跟敲代码。
第三方压缩库、生成站点与 V2 专属目录不属于 V1 注释维护边界。

调用顺序：发布验收脚本或命令行 -> main() -> build_report()。
"""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOTS = (
    Path("app.py"),
    Path("qa_core"),
    Path("scripts"),
    Path("tests"),
    Path("codealong/chapters"),
)
JAVASCRIPT_ROOT = Path("static/js")
POWERSHELL_ROOT = Path("scripts")
V2_PATH_PARTS = {
    "agent",
    "agent_eval",
    "agent_protocols",
    "agent_queue",
    "agent_runtime",
    "graphrag",
    "ops",
    "v2",
}


@dataclass(frozen=True)
class CommentCoverageIssue:
    """描述一个缺少注释或无法解析的源码位置。"""

    path: str
    line: int
    kind: str
    symbol: str
    message: str


def _is_v1_path(path: Path) -> bool:
    """判断路径是否属于 V1 自有代码边界。"""

    relative = path.relative_to(PROJECT_ROOT)
    if any(part.lower() in V2_PATH_PARTS for part in relative.parts):
        return False
    if relative.as_posix() == "qa_core/api/v2.py":
        return False
    if path.name.startswith("test_v2"):
        return False
    return True


def iter_python_files() -> Iterable[Path]:
    """枚举 V1 Python 文件，并排除缓存和虚拟环境。"""

    seen: set[Path] = set()
    for relative in PYTHON_ROOTS:
        target = PROJECT_ROOT / relative
        candidates = (target,) if target.is_file() else target.rglob("*.py")
        for path in candidates:
            resolved = path.resolve()
            if resolved in seen or not _is_v1_path(resolved):
                continue
            if any(part in {"__pycache__", ".venv", "venv"} for part in resolved.parts):
                continue
            seen.add(resolved)
            yield resolved


def _public_nodes(tree: ast.Module) -> Iterable[ast.AST]:
    """枚举模块公开类、函数及公开方法，不把函数内部闭包当作公共 API。"""

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not node.name.startswith("_"):
            yield node
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and not child.name.startswith("_"):
                    yield child


def check_python_file(path: Path) -> list[CommentCoverageIssue]:
    """检查 Python 模块说明和公开符号 docstring。"""

    relative = path.relative_to(PROJECT_ROOT).as_posix()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    except (OSError, SyntaxError, UnicodeError) as exc:
        return [
            CommentCoverageIssue(relative, getattr(exc, "lineno", 1) or 1, "parse_error", "", str(exc))
        ]

    issues: list[CommentCoverageIssue] = []
    if not ast.get_docstring(tree, clean=False):
        issues.append(CommentCoverageIssue(relative, 1, "module_docstring", "", "缺少文件职责说明"))
    for node in _public_nodes(tree):
        if not ast.get_docstring(node, clean=False):
            issues.append(
                CommentCoverageIssue(
                    relative,
                    node.lineno,
                    "public_docstring",
                    node.name,
                    "公开类、函数或方法缺少职责说明",
                )
            )
    return issues


def check_javascript_files() -> list[CommentCoverageIssue]:
    """检查自研 JavaScript 文件是否以职责注释开头。"""

    issues: list[CommentCoverageIssue] = []
    for path in (PROJECT_ROOT / JAVASCRIPT_ROOT).rglob("*.js"):
        if "vendor" in path.parts or not _is_v1_path(path.resolve()):
            continue
        text = path.read_text(encoding="utf-8-sig").lstrip()
        if not text.startswith(("/*", "//")):
            issues.append(
                CommentCoverageIssue(
                    path.relative_to(PROJECT_ROOT).as_posix(),
                    1,
                    "file_header",
                    "",
                    "缺少前端文件职责与交互边界说明",
                )
            )
    return issues


def check_powershell_files() -> list[CommentCoverageIssue]:
    """检查 PowerShell 脚本是否提供 comment-based help。"""

    issues: list[CommentCoverageIssue] = []
    for path in (PROJECT_ROOT / POWERSHELL_ROOT).rglob("*.ps1"):
        text = path.read_text(encoding="utf-8-sig").lstrip()
        if not text.startswith("<#"):
            issues.append(
                CommentCoverageIssue(
                    path.relative_to(PROJECT_ROOT).as_posix(),
                    1,
                    "file_header",
                    "",
                    "缺少 PowerShell 脚本职责说明",
                )
            )
    return issues


def build_report() -> dict[str, object]:
    """汇总注释覆盖结果，供本地检查和发布门禁消费。"""

    python_files = list(iter_python_files())
    issues = [issue for path in python_files for issue in check_python_file(path)]
    issues.extend(check_javascript_files())
    issues.extend(check_powershell_files())
    return {
        "report_type": "v1_source_comment_coverage",
        "ok": not issues,
        "checked_python_files": len(python_files),
        "issue_count": len(issues),
        "issues": [asdict(issue) for issue in issues],
    }


def parse_args() -> argparse.Namespace:
    """解析输出文件和失败退出码参数。"""

    parser = argparse.ArgumentParser(description="Check V1 source comment coverage.")
    parser.add_argument("--output", default=None, help="Optional JSON report path.")
    parser.add_argument("--fail-on-issues", action="store_true", help="Exit with code 1 when issues exist.")
    return parser.parse_args()


def main() -> None:
    """执行检查、打印报告并按需写入 JSON 文件。"""

    args = parse_args()
    report = build_report()
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    if args.fail_on_issues and not report["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
