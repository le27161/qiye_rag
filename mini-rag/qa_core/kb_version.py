"""MySQL 知识库版本管理 — 与完整项目对齐的建表和版本控制。

Mini RAG 直接使用完整项目的表结构和版本生成逻辑，确保：
  - 版本 ID 格式一致（kb_{scenario_id}_{timestamp}_{config_hash}）
  - 表结构兼容（完整项目可以读取 Mini RAG 创建的版本记录）
  - 版本状态流转一致（STAGED → ACTIVE → 归档）

两张核心表：
  kb_versions        — 版本详情的 append-only 记录表
  kb_active_versions — 每个场景当前激活版本的指针表

版本状态机：
  STAGED（创建时）→ ACTIVE（激活后）→ 上一条 ACTIVE 降为 STAGED

使用方式：
  1. rebuild 时调用 create_version() 创建版本（STAGED）
  2. 数据写入完成后调用 activate_version() 激活
  3. 在线问答通过 active_version() 获取当前版本 ID
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from qa_core.config import SCENARIO, get_settings


# === 数据库表常量 ===

KB_VERSIONS_TABLE = "kb_versions"       # 版本详情表（记录每个版本的元数据）
KB_ACTIVE_TABLE = "kb_active_versions"   # 当前激活版本的指针表（每个场景一行）
STATUS_STAGED = "STAGED"                 # 已创建但未激活（初始状态）
STATUS_ACTIVE = "ACTIVE"                 # 已激活（当前在线问答使用的版本）


# === 时间戳工具 ===


def utc_now() -> str:
    """返回 ISO 格式的当前 UTC 时间戳。

    用于写入 kb_versions.created_at / activated_at 字段，
    ISO 格式保证跨时区可解析性。

    示例输出：
      2025-06-18T14:30:52.123456+00:00

    调用顺序：mini-rag 流程 -> utc_now()。
    """
    return datetime.now(timezone.utc).isoformat()


def utc_file_stamp() -> str:
    """返回版本 ID 中使用的时间戳格式（YYYYMMDD_HHMMSS）。

    用于生成可读的版本标识，便于运维人员理解版本创建时间。

    示例输出：
      20250618_143052

    调用顺序：mini-rag 流程 -> utc_file_stamp()。
    """
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


# === 序列化工具 ===


def json_dumps(value: Any) -> str:
    """将元数据序列化为 JSON 字符串，格式与完整项目一致。

    使用 ensure_ascii=False 保留中文字符（可读性更好），
    sort_keys=True 保证相同输入产生相同输出（确定性序列化）。

    Args:
        value: 待序列化的 Python 对象（通常是 dict）

    Returns:
        JSON 字符串

    调用顺序：mini-rag 流程 -> json_dumps()。
    """
    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True)


def stable_hash(*parts: object) -> str:
    """从版本定义参数生成稳定的 SHA256 哈希值。

    用于版本 ID 中嵌入配置指纹，确保不同的配置参数
    自动产生不同的版本标识。

    输入参数的顺序影响哈希结果，因此调用方需保证参数顺序一致。
    输出为完整的 64 位十六进制字符串。

    Args:
        parts: 参与哈希计算的参数（场景 ID、模型版本、集合名称等）

    Returns:
        64 位 SHA256 十六进制哈希字符串

    调用顺序：mini-rag 流程 -> stable_hash()。
    """
    raw = "|".join(str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# === 数据类 ===


@dataclass(frozen=True)
class KBVersion:
    """知识库版本记录 — 使用与完整项目相同的表字段结构。

    虽然 Mini RAG 不直接使用这个数据类进行查询（而是直接使用 SQL），
    但它明确了版本记录包含的全部字段，方便理解和调试。

    Attributes:
        scenario_id:             场景标识
        kb_version:              版本 ID
        description:             版本描述（如 "mini rag rebuild"）
        status:                  状态（STAGED / ACTIVE / ARCHIVED）
        created_at:              创建时间（ISO 格式 UTC）
        activated_at:            激活时间（ISO 格式 UTC，未激活时为 None）
        doc_collection:          Milvus 文档集合名称
        faq_collection:          Milvus FAQ 集合名称
        embedding_model_version: Embedding 模型版本标识
        reranker_model_version:  Reranker 模型版本标识
        chunk_schema_version:    切分策略版本标识

    调用顺序：mini-rag 流程 -> KBVersion。
    """

    scenario_id: str
    kb_version: str
    description: str
    status: str
    created_at: str
    activated_at: str | None
    doc_collection: str
    faq_collection: str
    embedding_model_version: str
    reranker_model_version: str
    chunk_schema_version: str


# === 版本 ID 生成 ===


def new_kb_version() -> str:
    """生成与完整项目完全兼容的知识库版本 ID。

    版本 ID 格式：
      kb_{scenario_id}_{timestamp}_{config_hash_8chars}

    其中 config_hash 由以下参数计算得出：
      - scenario_id
      - embedding_model_version
      - reranker_model_version
      - chunk_schema_version
      - doc_collection / faq_collection

    这样当任何配置参数变化时，会自动产生不同的版本 ID。
    取 hash 前 8 位作为后缀，兼顾唯一性和可读性。

    示例输出：
      kb_enterprise_knowledge_20250618_143052_a1b2c3d4

    Returns:
        新生成的版本 ID 字符串

    调用顺序：mini-rag 流程 -> new_kb_version()。
    """
    settings = get_settings()
    config_hash = stable_hash(
        SCENARIO.scenario_id,
        settings.embedding_model_version,
        settings.reranker_model_version,
        settings.chunk_schema_version,
        SCENARIO.doc_collection,
        SCENARIO.faq_collection,
    )[:8]
    return f"kb_{SCENARIO.scenario_id}_{utc_file_stamp()}_{config_hash}"


# === 数据库连接 ===


def get_engine() -> Engine:
    """创建 MySQL SQLAlchemy 数据库引擎。

    使用 pool_pre_ping=True 启用连接池健康检查：
      每次从连接池取出连接时先发送测试查询（ping），
      确保连接仍然有效。这样可以有效防止因 MySQL 服务端
      超时断开导致的 "MySQL server has gone away" 错误。

    Returns:
        SQLAlchemy Engine 实例（惰性连接，首次执行 SQL 时建立实际连接）

    调用顺序：mini-rag 流程 -> get_engine()。
    """
    return create_engine(get_settings().mysql_url, pool_pre_ping=True)


# === 建表 ===


def init_tables(engine: Engine | None = None) -> None:
    """创建知识库版本管理所需的两张 MySQL 表。

    使用 CREATE TABLE IF NOT EXISTS 保证幂等性，
    多次调用不会重复创建或报错。

    kb_versions 表：
      - 组合主键 (scenario_id, kb_version)
      - 索引：scenario_id + status（用于按场景查询活跃版本）
      - 索引：scenario_id + created_at（用于按时间排序）
      - 包含与完整项目兼容的全部字段（created_by、sources_json、stats_json 等）

    kb_active_versions 表：
      - 主键 scenario_id（每个场景只有一行激活指针）
      - active_kb_version: 当前激活的版本 ID
      - previous_kb_version: 上一激活版本 ID（保留用于回滚）

    Args:
        engine: 可选的 SQLAlchemy 引擎（未指定时自动创建）

    调用顺序：mini-rag 流程 -> init_tables()。
    """
    engine = engine or get_engine()
    with engine.begin() as conn:
        # 创建版本详情表
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS kb_versions (
                    scenario_id VARCHAR(128) NOT NULL,
                    kb_version VARCHAR(191) NOT NULL,
                    status VARCHAR(32) NOT NULL,
                    description TEXT NULL,
                    created_at VARCHAR(40) NOT NULL,
                    activated_at VARCHAR(40) NULL,
                    archived_at VARCHAR(40) NULL,
                    doc_collection VARCHAR(191) NOT NULL,
                    faq_collection VARCHAR(191) NOT NULL,
                    embedding_model_version VARCHAR(191) NOT NULL,
                    reranker_model_version VARCHAR(191) NOT NULL,
                    chunk_schema_version VARCHAR(191) NOT NULL,
                    created_by VARCHAR(128) NOT NULL,
                    sources_json LONGTEXT NULL,
                    stats_json LONGTEXT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (scenario_id, kb_version),
                    INDEX idx_kb_versions_status (scenario_id, status),
                    INDEX idx_kb_versions_created_at (scenario_id, created_at)
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
                """
            )
        )
        # 创建激活版本指针表
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS kb_active_versions (
                    scenario_id VARCHAR(128) PRIMARY KEY,
                    active_kb_version VARCHAR(191) NOT NULL DEFAULT '',
                    previous_kb_version VARCHAR(191) NOT NULL DEFAULT '',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
                """
            )
        )


# === 版本管理操作 ===


def create_version(description: str = "mini rag rebuild", *, engine: Engine | None = None) -> str:
    """在 MySQL 中创建一个知识库版本记录（状态：STAGED）。

    完整操作流程：
      1. 确保 kb_versions 和 kb_active_versions 表已创建（init_tables 幂等）
      2. 生成新的版本 ID（kb_scenario_timestamp_hash）
      3. 向 kb_versions 插入一条 STAGED 状态的版本记录
      4. 将场景的 valid_sources 和创建原因记录到 sources_json / stats_json

    Args:
        description: 版本描述（默认为 "mini rag rebuild"）
        engine:      可选的 SQLAlchemy 引擎（未指定时自动创建）

    Returns:
        新创建的版本 ID

    调用顺序：mini-rag 流程 -> create_version()。
    """
    engine = engine or get_engine()
    init_tables(engine)
    settings = get_settings()
    version = new_kb_version()

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO kb_versions
                    (
                        scenario_id, kb_version, status, description, created_at,
                        activated_at, archived_at, doc_collection, faq_collection,
                        embedding_model_version, reranker_model_version, chunk_schema_version,
                        created_by, sources_json, stats_json
                    )
                VALUES
                    (
                        :scenario_id, :kb_version, :status, :description, :created_at,
                        NULL, NULL, :doc_collection, :faq_collection,
                        :embedding_model_version, :reranker_model_version, :chunk_schema_version,
                        :created_by, :sources_json, :stats_json
                    )
                """
            ),
            {
                "scenario_id": SCENARIO.scenario_id,
                "kb_version": version,
                "status": STATUS_STAGED,
                "description": description,
                "created_at": utc_now(),
                "doc_collection": SCENARIO.doc_collection,
                "faq_collection": SCENARIO.faq_collection,
                "embedding_model_version": settings.embedding_model_version,
                "reranker_model_version": settings.reranker_model_version,
                "chunk_schema_version": settings.chunk_schema_version,
                "created_by": "qa_core",
                "sources_json": json_dumps(list(SCENARIO.valid_sources)),
                "stats_json": json_dumps({"created_reason": "qa_core_rebuild"}),
            },
        )

    return version


def activate_version(kb_version: str, *, engine: Engine | None = None) -> None:
    """将指定版本标记为当前激活版本。

    完整的激活流程在一个数据库事务中执行，保证原子性：
      1. 获取当前激活版本指针（SELECT ... FOR UPDATE 加行锁，防并发）
      2. 记录上一版本 ID（用于回滚场景）
      3. 将所有 ACTIVE 状态版本降级为 STAGED
      4. 将目标版本升级为 ACTIVE（记录激活时间）
      5. Upsert kb_active_versions 指针表

    设计要点：
      - SELECT ... FOR UPDATE 行锁防止并发激活冲突
      - 同一事务中执行所有操作，中间失败自动回滚
      - 保留 previous_kb_version 用于版本回滚

    Args:
        kb_version: 要激活的版本 ID
        engine:     可选的 SQLAlchemy 引擎（未指定时自动创建）

    调用顺序：mini-rag 流程 -> activate_version()。
    """
    engine = engine or get_engine()
    init_tables(engine)
    now = utc_now()

    with engine.begin() as conn:
        # 加行锁读取当前激活版本指针，防止并发冲突
        pointer = conn.execute(
            text(
                """
                SELECT active_kb_version, previous_kb_version
                FROM kb_active_versions
                WHERE scenario_id = :scenario_id
                FOR UPDATE
                """
            ),
            {"scenario_id": SCENARIO.scenario_id},
        ).mappings().first()

        # 记录上一激活版本 ID（用于回滚）
        previous = str(pointer["active_kb_version"] or "") if pointer else ""
        # 如果目标版本已经是激活版本（重复激活），保留原始的 previous 值
        if previous == kb_version and pointer:
            previous = str(pointer["previous_kb_version"] or "")

        # 将当前所有 ACTIVE 状态的版本降级为 STAGED
        conn.execute(
            text(
                """
                UPDATE kb_versions
                SET status = :staged_status
                WHERE scenario_id = :scenario_id AND status = :active_status
                """
            ),
            {
                "scenario_id": SCENARIO.scenario_id,
                "staged_status": STATUS_STAGED,
                "active_status": STATUS_ACTIVE,
            },
        )

        # 将目标版本升级为 ACTIVE
        conn.execute(
            text(
                """
                UPDATE kb_versions
                SET status = :active_status, activated_at = :activated_at
                WHERE scenario_id = :scenario_id AND kb_version = :kb_version
                """
            ),
            {
                "scenario_id": SCENARIO.scenario_id,
                "kb_version": kb_version,
                "active_status": STATUS_ACTIVE,
                "activated_at": now,
            },
        )

        # 更新激活版本指针表（INSERT OR UPDATE）
        conn.execute(
            text(
                """
                INSERT INTO kb_active_versions
                    (scenario_id, active_kb_version, previous_kb_version)
                VALUES
                    (:scenario_id, :active_kb_version, :previous_kb_version)
                ON DUPLICATE KEY UPDATE
                    active_kb_version = VALUES(active_kb_version),
                    previous_kb_version = VALUES(previous_kb_version),
                    updated_at = CURRENT_TIMESTAMP
                """
            ),
            {
                "scenario_id": SCENARIO.scenario_id,
                "active_kb_version": kb_version,
                "previous_kb_version": previous,
            },
        )


def active_version(*, engine: Engine | None = None) -> str:
    """查询当前场景正在使用的激活版本 ID。

    如果尚不存在激活版本（首次启动、尚未执行 rebuild），
    抛出 RuntimeError 并提示用户运行重建脚本。

    查询逻辑：
      1. 确保表已创建（幂等）
      2. 从 kb_active_versions 指针表查询 active_kb_version
      3. 未找到有效记录时触发错误提示

    Args:
        engine: 可选的 SQLAlchemy 引擎（用于依赖注入 / 测试）

    Returns:
        当前激活的版本 ID

    Raises:
        RuntimeError: 尚未有激活版本（需要先执行 rebuild 入库）

    调用顺序：mini-rag 流程 -> active_version()。
    """
    engine = engine or get_engine()
    init_tables(engine)

    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT active_kb_version
                FROM kb_active_versions
                WHERE scenario_id = :scenario_id
                """
            ),
            {"scenario_id": SCENARIO.scenario_id},
        ).mappings().first()

    if not row or not str(row["active_kb_version"] or "").strip():
        raise RuntimeError("Mini RAG has no active KB version. Run: python mini-rag/scripts/rebuild.py")

    return str(row["active_kb_version"])
