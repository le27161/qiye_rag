"""真实数据入库 Pipeline — FAQ + 文档加载 → 切分 → Milvus 写入 → MySQL 版本激活。

Mini RAG 的离线入库流程，对应完整项目中的 indexing/ 模块。

入库流程概览：
  1. 扫描场景数据目录中的 FAQ CSV 和业务文档
  2. FAQ CSV → 每条 FAQ 转为 LangChain Document（含 source / question / answer 元数据）
  3. 业务文档 → 多格式加载 → RecursiveCharacterTextSplitter 切分 → 附版本和隔离元数据
  4. 写入 Milvus：FAQ 集合 + Doc 集合（每个文档同时生成 Dense + Sparse 向量）
  5. 在 MySQL 中创建知识库版本记录并激活

重建策略：
  - 默认不 drop 集合（增量覆盖：同一 ID 的写入会更新已有数据）
  - --reset-collections 选项会先 drop 再重建（完全清空）
"""

from __future__ import annotations

import csv
from pathlib import Path

from langchain_core.documents import Document

from qa_core.config import SCENARIO, get_settings
from qa_core.kb_version import activate_version, create_version
from qa_core.loaders import chunk_documents, iter_source_files, load_file, stable_id
from qa_core.retrieval import doc_store, drop_collection, faq_store


def scope_metadata() -> dict[str, object]:
    """返回写入 Milvus 每条文档的默认数据隔离和 Schema 版本元数据。

    这些字段用于 Milvus 标量过滤，确保：
      - 数据隔离（tenant / dataset / visibility / roles）
      - 版本追溯（模型版本、切分策略版本）

    调用顺序：mini-rag 流程 -> scope_metadata()。
    """
    settings = get_settings()
    return {
        "tenant_id": settings.tenant_id,
        "dataset_id": settings.dataset_id,
        "visibility": settings.visibility,
        "allowed_roles": [settings.allowed_role],
        "embedding_model_version": settings.embedding_model_version,
        "reranker_model_version": settings.reranker_model_version,
        "chunk_schema_version": settings.chunk_schema_version,
    }


def load_faq_documents(kb_version: str) -> tuple[list[Document], list[str]]:
    """从真实 FAQ CSV 文件中加载 FAQ 文档。

    读取 scenarios/enterprise_knowledge/faq.csv，
    每行包含：question（问题）、answer（标准答案）、source（来源）。

    处理逻辑：
      1. 验证 source 是否在 valid_sources 中（hr / it / finance）
      2. 跳过空问题或空答案的行
      3. 每条 FAQ 生成一个 Document，内容格式为 "问题：xxx\n答案：yyy"
      4. 生成唯一标识 faq_id = stable_hash(kb_version, "faq", source, question)

    Args:
        kb_version: 当前知识库版本标识

    Returns:
        (documents, ids) — 文档列表和对应的唯一 ID 列表

    调用顺序：mini-rag 流程 -> load_faq_documents()。
    """
    documents: list[Document] = []
    ids: list[str] = []
    base_metadata = scope_metadata()

    # 使用 utf-8-sig 编码处理 BOM（某些 CSV 编辑器会在文件头插入 BOM 标记）
    with SCENARIO.faq_csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for index, row in enumerate(reader):
            question = (row.get("question") or "").strip()
            answer = (row.get("answer") or "").strip()
            source = (row.get("source") or "").strip()

            # 跳过无效行
            if not question or not answer:
                continue

            # 验证 source 合法性
            if source not in SCENARIO.valid_sources:
                raise ValueError(f"Invalid FAQ source `{source}` at row {index + 2}")

            # 生成唯一标识（用于 Milvus 主键和去重）
            faq_id = stable_id(kb_version, "faq", source, question)
            # FAQ 文档内容格式：问题 + 答案拼接
            content = f"问题：{question}\n答案：{answer}"

            documents.append(
                Document(
                    page_content=content,
                    metadata={
                        "faq_id": faq_id,
                        "chunk_id": faq_id,
                        "source": source,
                        "source_type": "faq",
                        "kb_version": kb_version,
                        "question": question,
                        "answer": answer,
                        **base_metadata,  # 合并隔离和版本元数据
                    },
                )
            )
            ids.append(faq_id)

    return documents, ids


def load_document_chunks(kb_version: str) -> tuple[list[Document], list[str]]:
    """加载并切分所有业务文档。

    流程：
      1. 遍历所有 valid_sources（hr / it / finance）
      2. 在每个来源的 data 目录下递归查找支持的文档格式
      3. 加载原始文档
      4. RecursiveCharacterTextSplitter 切分
      5. 每个 chunk 附加来源、版本、文件路径等元数据

    支持的文件格式（由 loaders.py 处理）：
      .md, .txt, .pdf, .docx, .pptx, .csv, .xlsx, .xls

    Args:
        kb_version: 当前知识库版本标识

    Returns:
        (all_chunks, ids) — 切分后的文档列表和对应的 ID 列表

    调用顺序：mini-rag 流程 -> load_document_chunks()。
    """
    all_chunks: list[Document] = []
    ids: list[str] = []

    # 获取所有的业务分类（"hr", "it", "finance"）
    for source in SCENARIO.valid_sources:
        for path in iter_source_files(SCENARIO.data_root, source):
            # 加载原始文档（多格式支持）
            raw_documents = load_file(path)
            # 切分文档 + 附加元数据
            chunks = chunk_documents(
                raw_documents,
                source=source,
                path=Path(path),
                kb_version=kb_version,
                base_metadata=scope_metadata(),
            )
            all_chunks.extend(chunks)
            ids.extend(str(chunk.metadata["chunk_id"]) for chunk in chunks)

    return all_chunks, ids


def rebuild(*, reset_collections: bool = False, description: str = "mini rag rebuild") -> dict[str, object]:
    """重建 Mini RAG 知识库 — FAQ + 文档全部重新入库。

    完整流程：
      1. (可选) 删除已有 Milvus 集合 — 完全重建
      2. 在 MySQL 中创建新的知识库版本记录（status=STAGED）
      3. 加载并写入 FAQ 文档到 Milvus
      4. 加载、切分并写入业务文档到 Milvus
      5. 在 MySQL 中激活新版本（MARK ACTIVE）

    Args:
        reset_collections: 是否先删除已有集合（默认 False，增量覆盖）
        description: 版本描述（写入 kb_versions 表的 description 字段）

    Returns:
        入库结果摘要（scenario_id、kb_version、FAQ 条数、Doc chunk 数）

    调用顺序：mini-rag 流程 -> rebuild()。
    """
    # 可选：删除已有集合
    if reset_collections:
        drop_collection(SCENARIO.faq_collection)
        drop_collection(SCENARIO.doc_collection)

    # 在 MySQL 中创建版本
    kb_version = create_version(description)
    print("kb_version:", kb_version)

    # 加载 FAQ
    faq_documents, faq_ids = load_faq_documents(kb_version)
    # 加载文档 chunks
    doc_documents, doc_ids = load_document_chunks(kb_version)

    # 写入 Milvus（FAQ 集合 + Doc 集合分别写入）
    faq_store().add_documents(faq_documents, faq_ids)
    doc_store().add_documents(doc_documents, doc_ids)

    # 激活版本
    activate_version(kb_version)

    return {
        "scenario_id": SCENARIO.scenario_id,
        "kb_version": kb_version,
        "faq_records": len(faq_documents),
        "doc_chunks": len(doc_documents),
        "activated": True,
    }


