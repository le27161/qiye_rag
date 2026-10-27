"""命令行知识库重建脚本 — 将 FAQ 和业务文档加载入库并激活新版本。

通过 qa_core.ingest.rebuild() 将 mini-rag/data/ 下的 FAQ 和业务文档
处理后写入 Milvus 向量库，并创建新的知识库版本记录。

两种重建模式：
  - 增量模式（默认）：相同 ID 的文档会更新，不删除已有数据
  - 完全重建（--reset-collections）：先删除 Milvus 集合再重新创建

使用方式：
  # 增量重建（默认）
  python mini-rag/scripts/rebuild.py

  # 完全重建
  python mini-rag/scripts/rebuild.py --reset-collections

  # 自定义版本描述
  python mini-rag/scripts/rebuild.py --description "更新了HR部门的报销政策文档"

输出：JSON 格式的入库结果（scenario_id、版本号、FAQ 条数、Doc chunk 数）。
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

from qa_core.ingest import rebuild


def main() -> None:
    """CLI 入口 — 解析参数、执行重建、输出 JSON 结果。

    执行流程:
        1. 解析命令行参数（--reset-collections、--description）
        2. 调用 rebuild() 执行知识库重建：
           - 读取 data/ 目录下的 FAQ 和业务文档
           - 对文档进行分块处理（chunking）
           - 生成向量并写入 Milvus 集合
           - 创建新版本记录到 kb_versions 表
        3. 以 JSON 格式输出重建结果

    参数（通过命令行）:
        --reset-collections: 是否先删除已有 Milvus 集合（完全清空重来）
        --description: 版本描述（记录在 kb_versions 表中，用于版本追溯）
    """
    parser = argparse.ArgumentParser(description="重建 Mini RAG 知识库。")
    parser.add_argument(
        "--reset-collections",
        action="store_true",
        help="先删除已有 Milvus 集合再重建（完全清空重来）",
    )
    parser.add_argument(
        "--description",
        default="mini rag rebuild",
        help="版本描述（记录在 kb_versions 表中，用于版本追溯）",
    )
    args = parser.parse_args()

    result = rebuild(reset_collections=args.reset_collections, description=args.description)
    # 输出 JSON 结果（ensure_ascii=False 保留中文）
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

