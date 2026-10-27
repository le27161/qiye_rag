"""表格文件加载器 — CSV 和 Excel 文件处理。

将表格数据转换为可供 RAG 检索的逐行文档格式。
每行数据生成一个独立的 LangChain Document，
内容以 "字段名: 值" 的键值对形式呈现。

适用场景：
  - CSV 政策/条例文件（如 IT 安全规范表、财务科目表）
  - Excel 多工作表文档（如组织架构表、产品清单）
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from langchain_core.documents import Document

# TYPE_CHECKING 块中的 import 只用于类型标注，不产生运行时依赖
if TYPE_CHECKING:
    import pandas as pd


def _clean(value: object) -> str:
    """将 DataFrame 单元格值转换为干净的文本。

    处理：
      - NaN / None → 空字符串
      - 其他值 → 去除首尾空白的字符串

    调用顺序：mini-rag 流程 -> _clean()。
    """
    import pandas as pd

    if pd.isna(value):
        return ""
    return str(value).strip()


def dataframe_documents(path: Path, frame: "pd.DataFrame", *, sheet_name: str | None = None) -> list[Document]:
    """将 DataFrame 的每一行转换为一个 LangChain Document。

    每个 Document 的内容格式：
      文件: 文件名；工作表: Sheet1；行号: 5
      列1: 值1
      列2: 值2
      ...

    元数据包含：
      - file_type: 文件后缀（.csv / .xlsx / .xls）
      - table_id: 文件 stem（不含后缀）
      - sheet_name: 工作表名称（Excel 有，CSV 为 None）
      - row_number: 行号（从 1 开始编号）
      - table_headers: 列头列表（用于检索时匹配字段名）

    Args:
        path:       文件路径（用于元数据）
        frame:      待转换的 DataFrame
        sheet_name: 工作表名称（仅 Excel 文件），CSV 为 None

    Returns:
        LangChain Document 列表（每行一个 Document）

    调用顺序：mini-rag 流程 -> dataframe_documents()。
    """
    docs: list[Document] = []
    headers = [str(column).strip() for column in frame.columns]

    for row_index, row in frame.iterrows():
        # 构建 "列名: 值" 键值对（跳过列名为空或值为空的列）
        pairs = [
            f"{header}: {_clean(row[header])}"
            for header in headers
            if header and _clean(row[header])
        ]
        # 跳过完全空行
        if not pairs:
            continue

        # 构建内容前缀（文件、工作表、行号）
        prefix = f"文件: {path.name}"
        if sheet_name:
            prefix += f"；工作表: {sheet_name}"
        content = f"{prefix}；行号: {int(row_index) + 1}\n" + "\n".join(pairs)

        docs.append(
            Document(
                page_content=content,
                metadata={
                    "file_type": path.suffix.lower(),
                    "table_id": path.stem,
                    "sheet_name": sheet_name,
                    "row_number": int(row_index) + 1,
                    "table_headers": headers,
                },
            )
        )

    return docs


def load_table_file(path: Path) -> list[Document]:
    """表格文件加载入口 — 自动识别 CSV / XLSX / XLS 格式。

    CSV 文件：
      - 使用 pandas.read_csv() 读取
      - 单 DataFrame，sheet_name 为 None

    Excel 文件（.xlsx / .xls）：
      - 使用 pandas.read_excel(sheet_name=None) 读取所有工作表
      - 每个工作表独立处理，sheet_name 用于元数据区分

    Args:
        path: 表格文件路径

    Returns:
        LangChain Document 列表（所有行的汇总）

    Raises:
        ValueError: 不支持的文件类型

    调用顺序：mini-rag 流程 -> load_table_file()。
    """
    import pandas as pd

    suffix = path.suffix.lower()

    if suffix == ".csv":
        # CSV 文件：单 DataFrame
        frame = pd.read_csv(path)
        return dataframe_documents(path, frame)

    if suffix in {".xlsx", ".xls"}:
        # Excel 文件：遍历所有工作表
        docs: list[Document] = []
        sheets = pd.read_excel(path, sheet_name=None)
        for sheet_name, frame in sheets.items():
            docs.extend(dataframe_documents(path, frame, sheet_name=str(sheet_name)))
        return docs

    raise ValueError(f"Unsupported table file: {path}")


