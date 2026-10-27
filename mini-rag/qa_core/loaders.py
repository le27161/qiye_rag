"""文档加载器与文本切分 — 支持 8 种格式的文档加载和 RecursiveCharacterTextSplitter 切分。

支持的文档格式：
  - 纯文本    : .md, .txt   → 直接读取 UTF-8 文本
  - PDF       : .pdf        → PyMuPDF (fitz) 提取文本层
  - Word      : .docx       → python-docx 提取段落和表格
  - PowerPoint: .pptx       → python-pptx 提取幻灯片文本和表格
  - 表格      : .csv/.xlsx/.xls → pandas 读取，每行转为独立 document

切分策略：
  RecursiveCharacterTextSplitter，chunk_size=650, chunk_overlap=120，
  使用中文友好的分隔符优先级：## → ### → 换行 → 句号 → 分号 → 空格 → 字符
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from langchain_core.documents import Document

from qa_core.table_loader import load_table_file


# 支持的文档后缀列表
SUPPORTED_SUFFIXES = {".md", ".txt", ".pdf", ".docx", ".pptx", ".csv", ".xlsx", ".xls"}


def load_text_file(path: Path) -> list[Document]:
    """加载 Markdown 或纯文本文件。

    直接读取文件内容作为单个 Document。
    空文件返回空列表（不生成无意义 document）。

    调用顺序：mini-rag 流程 -> load_text_file()。
    """
    text = path.read_text(encoding="utf-8").strip()
    return [Document(page_content=text, metadata={"file_type": path.suffix.lower()})] if text else []


def load_pdf(path: Path) -> list[Document]:
    """使用 PyMuPDF (fitz) 加载 PDF，每页提取为一个 Document。

    注意：
      - 只提取文本层（不支持 OCR 扫描件识别）
      - 每页非空文本作为独立 Document（含页码元数据）
      - 扫描件 PDF（无文本层）会产生空页

    调用顺序：mini-rag 流程 -> load_pdf()。
    """
    import fitz

    docs: list[Document] = []
    with fitz.open(str(path)) as pdf:
        for page_index, page in enumerate(pdf):
            text = page.get_text("text").strip()
            if text:
                docs.append(Document(page_content=text, metadata={"page": page_index, "file_type": ".pdf"}))
    return docs


def load_docx(path: Path) -> list[Document]:
    """使用 python-docx 加载 DOCX 文件。

    提取内容包括：
      - 文档段落文本
      - 表格内容（每行用 " | " 连接单元格）

    整个文件合并为一个 Document（不按段落切分），
    后续由 RecursiveCharacterTextSplitter 统一切分。

    调用顺序：mini-rag 流程 -> load_docx()。
    """
    from docx import Document as DocxDocument

    docx = DocxDocument(str(path))
    lines = [paragraph.text.strip() for paragraph in docx.paragraphs if paragraph.text.strip()]

    # 提取表格内容
    for table in docx.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                lines.append(" | ".join(cells))

    content = "\n".join(lines).strip()
    return [Document(page_content=content, metadata={"file_type": ".docx"})] if content else []


def load_pptx(path: Path) -> list[Document]:
    """使用 python-pptx 加载 PPTX 文件，每张幻灯片提取为一个 Document。

    提取内容包括：
      - 形状中的文本
      - 表格内容（每行用 " | " 连接单元格）

    使用 dict.fromkeys() 去重保持顺序，去除幻灯片内重复文本。
    每张有内容的幻灯片作为一个独立 Document。

    调用顺序：mini-rag 流程 -> load_pptx()。
    """
    from pptx import Presentation

    presentation = Presentation(str(path))
    docs: list[Document] = []

    for slide_index, slide in enumerate(presentation.slides):
        lines: list[str] = []

        for shape in slide.shapes:
            # 提取表格
            if getattr(shape, "has_table", False):
                for row in shape.table.rows:
                    cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if cells:
                        lines.append(" | ".join(cells))
            # 提取文本
            text = getattr(shape, "text", "").strip()
            if text:
                lines.append(text)

        # 去重保持顺序（幻灯片内可能有重复占位符）
        content = "\n".join(dict.fromkeys(lines)).strip()
        if content:
            docs.append(Document(page_content=content, metadata={"page": slide_index, "file_type": ".pptx"}))

    return docs


def load_file(path: Path) -> list[Document]:
    """统一文件加载入口 — 根据后缀名分派到对应的加载器。

    支持 8 种格式：
      - .md / .txt  → load_text_file()
      - .pdf        → load_pdf()
      - .docx       → load_docx()
      - .pptx       → load_pptx()
      - .csv / .xlsx / .xls → load_table_file()

    Args:
        path: 文件路径

    Returns:
        LangChain Document 列表

    Raises:
        ValueError: 不支持的文件类型

    调用顺序：mini-rag 流程 -> load_file()。
    """
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt"}:
        return load_text_file(path)
    if suffix == ".pdf":
        return load_pdf(path)
    if suffix == ".docx":
        return load_docx(path)
    if suffix == ".pptx":
        return load_pptx(path)
    if suffix in {".csv", ".xlsx", ".xls"}:
        return load_table_file(path)
    raise ValueError(f"Unsupported file type: {path}")


def stable_id(*parts: object) -> str:
    """从任意数量的参数生成稳定的短 ID。

    使用 SHA256 哈希保证：
      - 相同输入始终产生相同 ID（幂等）
      - 不同输入几乎不可能碰撞
      - 可用于 FAQ ID 和 chunk ID 生成

    取前 24 位十六进制字符作为短 ID，
    在保证唯一性的前提下缩短 ID 长度。

    调用顺序：mini-rag 流程 -> stable_id()。
    """
    raw = "|".join(str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def iter_source_files(data_root: Path, source: str) -> list[Path]:
    """遍历指定来源目录下的所有支持的文档文件。

    目录结构约定：
      scenarios/enterprise_knowledge/data/
        ├── hr_data/      → source = "hr"
        ├── it_data/      → source = "it"
        └── finance_data/ → source = "finance"

    递归查找所有后缀在 SUPPORTED_SUFFIXES 中的文件。

    Args:
        data_root: 场景数据根目录
        source:    数据来源标识（如 "hr"/"it"/"finance"）

    Returns:
        排序后的文件路径列表

    调用顺序：mini-rag 流程 -> iter_source_files()。
    """
    source_dir = data_root / f"{source}_data"
    if not source_dir.exists():
        return []
    return sorted(
        path
        for path in source_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )


def chunk_documents(
    documents: list[Document],
    *,
    source: str,
    path: Path,
    kb_version: str,
    base_metadata: dict[str, object] | None = None,
) -> list[Document]:
    """使用 RecursiveCharacterTextSplitter 切分文档并附加检索元数据。

    切分参数：
      - chunk_size=650: 每个块的目标字符数（中文约 300-400 字）
      - chunk_overlap=120: 相邻块的重叠字符数（防止语义被切断）

    分隔符优先级（从高到低）：
      ## (Markdown H2) → ### (Markdown H3) → 换行 → 中文句号 → 中文分号 → 英文分号 → 空格 → 字符

    切分后每个 chunk 追加元数据：
      - chunk_id: 唯一标识（hash 生成）
      - source: 来源标识（hr/it/finance）
      - source_type: "doc"（区别于 "faq"）
      - kb_version: 知识库版本
      - file_name: 原始文件名
      - path: 文件相对路径
      - 隔离元数据（tenant_id / dataset_id / visibility / allowed_roles）
      - 模型版本元数据（embedding_model_version / chunk_schema_version 等）

    Args:
        documents:     待切分的原始文档列表
        source:        来源标识
        path:          文件路径
        kb_version:    知识库版本
        base_metadata: 基础元数据（来自 scope_metadata()）

    Returns:
        切分后的 Document 列表（每个 chunk 携带完整元数据）

    调用顺序：mini-rag 流程 -> chunk_documents()。
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    # 创建切分器
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=650,
        chunk_overlap=120,
        separators=["\n## ", "\n### ", "\n", "。", "；", ";", " ", ""],
    )
    # 执行切分
    chunks = splitter.split_documents(documents)

    # 为每个 chunk 追加元数据
    result: list[Document] = []
    for index, chunk in enumerate(chunks):
        metadata = dict(chunk.metadata or {})
        # 生成唯一 chunk_id（版本 + 来源 + 文件路径 + 序号 + 内容前缀）
        chunk_id = stable_id(kb_version, source, path.as_posix(), index, chunk.page_content[:80])
        metadata.update(
            {
                "chunk_id": chunk_id,
                "source": source,
                "source_type": "doc",
                "kb_version": kb_version,
                "file_name": path.name,
                "path": path.as_posix(),
            }
        )
        # 合并隔离和版本元数据
        metadata.update(base_metadata or {})
        result.append(Document(page_content=chunk.page_content, metadata=metadata))

    return result


