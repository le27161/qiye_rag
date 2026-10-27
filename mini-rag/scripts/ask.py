"""命令行问答脚本 — 不启动 Web 服务，直接在终端向 Mini RAG 提问。

适用于快速测试和调试场景，无需启动 Web 服务即可验证问答链路。
支持历史对话（模拟多轮交互）和来源筛选（限定检索范围）。

使用方式：
  # 单轮问答
  python mini-rag/scripts/ask.py "VPN 怎么连接" --source-filter it

  # 多轮对话（--history 可多次指定）
  python mini-rag/scripts/ask.py "那审批呢" --history "报销流程是什么"

输出：JSON 格式的完整答案（含来源引用、路由信息、检索统计）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Windows PowerShell 下旧版 Python 可能默认使用本地代码页，强制 CLI JSON 使用 UTF-8。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# 将 mini-rag 根目录加入 Python 搜索路径，确保能够 import qa_core 包
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qa_core.pipeline import ask
from qa_core.runtime import dependency_error_message, friendly_runtime_error


def main() -> None:
    """CLI 入口 — 解析参数、执行问答、输出 JSON 结果。

    执行流程:
        1. 解析命令行参数（query 为必填位置参数）
        2. 调用 ask() 执行问答核心逻辑
        3. 异常处理：
           - ModuleNotFoundError：缺少 Python 依赖，输出安装提示到 stderr 后退出
           - 其他运行时异常：尝试转换为友好中文提示，无法转换则向上抛出
        4. 以 JSON 格式输出问答结果（ensure_ascii=False 保留中文）

    参数（通过命令行）:
        query: 用户问题（位置参数，必填）
        --history: 历史对话记录（可多次指定，如 --history "问题1" --history "回答1"）
        --source-filter: 来源筛选（hr / it / finance，不指定则检索全部）
    """
    parser = argparse.ArgumentParser(description="向 Mini RAG 提问。")
    parser.add_argument("query", help="要问的问题")
    parser.add_argument("--history", action="append", default=[], help="历史对话记录（可多次指定，按时间顺序）")
    parser.add_argument("--source-filter", default=None, help="按来源筛选（hr / it / finance，不指定则检索全部）")
    args = parser.parse_args()

    try:
        result = ask(args.query, history=args.history, source_filter=args.source_filter)
    except ModuleNotFoundError as exc:
        # 缺少 Python 依赖 → 输出安装提示到 stderr 并退出
        print(dependency_error_message(exc), file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        # 运行时错误 → 尝试转换为友好中文提示
        friendly = friendly_runtime_error(exc)
        if friendly:
            print(friendly, file=sys.stderr)
            sys.exit(1)
        raise

    # 输出 JSON 结果（ensure_ascii=False 保留中文）
    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

