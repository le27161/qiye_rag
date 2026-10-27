"""Mini RAG 独立配置模块。

Mini RAG 是可单独拷贝运行的系统项目：
  - 优先读取系统环境变量，其次读取 mini-rag/.env，再兼容上一层 .env
  - 读取 mini-rag/scenarios/enterprise_knowledge/scenario.toml
  - 使用 mini-rag/config/rules.toml 管理查询变体规则
  - 包名保持 qa_core，方便和完整项目代码结构对照

配置优先级（从高到低）：
  1. 系统环境变量（os.getenv）
  2. mini-rag/.env 文件
  3. 上一层 .env 文件（仓库根目录）
  4. 代码中的默认值
"""

from __future__ import annotations

import os

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # Python 3.8-3.10
    import tomli as tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parent
ENV_FILES = (PROJECT_ROOT / ".env", REPO_ROOT / ".env")

DEFAULT_TENANT_ID = "default"
DEFAULT_DATASET_ID = "default"
DEFAULT_VISIBILITY = "public"
DEFAULT_USER_ROLE = "public"


def parse_env_file(path: Path) -> dict[str, str]:
    """解析简单的 dotenv 格式文件，返回键值对字典。

    支持的格式规则：
      - 空行和 # 开头的注释行自动跳过
      - 必须包含 = 分隔符，否则跳过
      - 值的首尾引号（单引号或双引号）自动去除
      - 不处理变量展开（不支持 ${VAR} 语法）

    Args:
        path: .env 文件的路径

    Returns:
        解析得到的键值对字典；文件不存在时返回空字典

    调用顺序：mini-rag 流程 -> parse_env_file()。
    """
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        # 去除值两端的引号（单引号或双引号）
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            values[key] = value
    return values


@lru_cache(maxsize=1)
def file_env() -> dict[str, str]:
    """读取 Mini RAG 可见的所有 dotenv 文件配置（进程级缓存）。

    加载顺序（后加载覆盖先加载）：
      1. REPO_ROOT/.env（仓库根目录）
      2. PROJECT_ROOT/.env（mini-rag 目录）

    使用 lru_cache(maxsize=1) 确保每个进程只读取一次文件，
    避免每次调用都重新解析磁盘文件。

    Returns:
        合并后的环境变量字典

    调用顺序：mini-rag 流程 -> file_env()。
    """
    values: dict[str, str] = {}
    for path in reversed(ENV_FILES):
        values.update(parse_env_file(path))
    return values


def loaded_env_files() -> list[str]:
    """返回实际存在的 dotenv 文件路径列表。

    用于健康检查端点返回，帮助用户确认哪些配置文件被加载。

    Returns:
        存在的 .env 文件路径字符串列表

    调用顺序：mini-rag 流程 -> loaded_env_files()。
    """
    return [str(path) for path in ENV_FILES if path.exists()]


def env(name: str, default: str) -> str:
    """按优先级从多层级配置源中读取字符串配置项。

    查找顺序：
      1. 系统环境变量（os.getenv）
      2. dotenv 文件（mini-rag/.env > 上一层 .env）
      3. 代码中的默认值

    Args:
        name:    环境变量名称
        default: 默认值（所有配置源都找不到时返回该值）

    Returns:
        配置值（非空字符串）

    调用顺序：mini-rag 流程 -> env()。
    """
    value = os.getenv(name)
    if value not in (None, ""):
        return value
    value = file_env().get(name)
    return value if value not in (None, "") else default


def env_any(names: tuple[str, ...], default: str = "") -> str:
    """从多个备选变量名中读取第一个非空值。

    用于兼容不同的环境变量命名约定，例如：
      - DASHSCOPE_API_KEY 和 OPENAI_API_KEY
      - DASHSCOPE_BASE_URL 和 OPENAI_BASE_URL

    Args:
        names:   备选变量名元组（按优先级排列）
        default: 全部未找到时返回的默认值

    Returns:
        第一个非空的配置值；全部为空时返回 default

    调用顺序：mini-rag 流程 -> env_any()。
    """
    for name in names:
        value = os.getenv(name)
        if value not in (None, ""):
            return value
    values = file_env()
    for name in names:
        value = values.get(name)
        if value not in (None, ""):
            return value
    return default


def project_path(value: str) -> Path:
    """将配置中的相对路径解析为绝对路径。

    解析规则：
      1. 已经是绝对路径 → 直接返回
      2. 相对路径 → 优先解析到 mini-rag 根目录
      3. 如果 mini-rag 目录下不存在 → 兼容回退到仓库根目录

    这样 Mini RAG 无论是独立运行还是作为项目一部分运行，
    都能正确找到模型文件和数据目录。

    Args:
        value: 配置中的路径字符串（相对或绝对）

    Returns:
        解析后的绝对路径

    调用顺序：mini-rag 流程 -> project_path()。
    """
    path = Path(value)
    if path.is_absolute():
        return path
    local_path = PROJECT_ROOT / path
    if local_path.exists():
        return local_path
    return REPO_ROOT / path


@dataclass(frozen=True)
class ScenarioConfig:
    """企业知识库场景场景配置。

    从 scenarios/enterprise_knowledge/scenario.toml 解析而来，
    包含场景标识、显示名称、数据来源、FAQ/文档集合名称等运行时参数。

    Attributes:
        scenario_id:     场景唯一标识（如 "enterprise_knowledge"）
        display_name:    前端展示名称（如 "企业知识库"）
        assistant_name:  助手名称（如 "企业知识库助手"）
        business_domain: 业务领域描述
        support_contact: 人工支持联系方式
        faq_collection:  Milvus FAQ 集合名称
        doc_collection:  Milvus 文档集合名称
        valid_sources:   有效数据来源列表（如 ["hr", "it", "finance"]）
        source_labels:   来源显示名称映射（如 {"hr": "人力资源", "it": "IT 支持"}）
        source_patterns: 来源文件目录命名模式（如 {"hr": "hr_data"})
        data_root:       场景数据根目录
        faq_csv_path:    FAQ CSV 文件路径

    调用顺序：mini-rag 流程 -> ScenarioConfig。
    """

    scenario_id: str
    display_name: str
    assistant_name: str
    business_domain: str
    support_contact: str
    faq_collection: str
    doc_collection: str
    valid_sources: tuple[str, ...]
    source_labels: dict[str, str]
    source_patterns: dict[str, str]
    data_root: Path
    faq_csv_path: Path


@dataclass(frozen=True)
class Settings:
    """Mini RAG 独立运行配置 — 所有可调节的运行时参数。

    配置来源：
      - 优先从系统环境变量读取，再读取 .env 文件
      - 未配置时使用代码中的默认值

    主要配置分类：
      - 数据库连接（Milvus URI、MySQL 主机/端口/账号）
      - 模型路径（Embedding、Reranker 本地模型目录）
      - LLM 配置（模型名、API Key、Base URL、超时、温度）
      - 版本标识（模型版本、切分策略版本）
      - 隔离粒度（tenant_id、dataset_id、visibility、allowed_role）
      - 检索参数（top_k、rerank 开关、阈值、上下文长度）

    Properties:
        mysql_url:         MySQL 连接 URL（由 mysql_* 属性拼接）
        chat_model:        等同 llm_model（OpenAI 兼容接口使用）
        openai_api_key:    等同 llm_api_key
        openai_base_url:   等同 llm_base_url
        llm_timeout_seconds: 等同 llm_timeout

    调用顺序：mini-rag 流程 -> Settings。
    """

    scenario_id: str = "enterprise_knowledge"
    milvus_uri: str = "http://localhost:19530"
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = "root123"
    mysql_database: str = "subjects_kg"
    embedding_model_path: Path = PROJECT_ROOT / "models" / "bge-m3"
    reranker_model_path: Path = PROJECT_ROOT / "models" / "bge-reranker-large"
    llm_model: str = "qwen-plus"
    llm_api_key: str = ""
    llm_base_url: str | None = None
    llm_timeout: float = 60.0
    llm_temperature: float = 0.1
    embedding_model_version: str = "bge-m3-local-v1"
    reranker_model_version: str = "bge-reranker-large-local-v1"
    chunk_schema_version: str = "parent_child_validity_v2"
    tenant_id: str = DEFAULT_TENANT_ID
    dataset_id: str = DEFAULT_DATASET_ID
    visibility: str = DEFAULT_VISIBILITY
    allowed_role: str = DEFAULT_USER_ROLE
    rerank_enabled: bool = True
    use_query_variants: bool = True
    retrieval_variant_max: int = 2
    faq_top_k: int = 20
    doc_top_k: int = 20
    rerank_top_n: int = 8
    final_context_top_n: int = 5
    faq_direct_threshold: float = 0.84
    min_context_score: float = 0.2
    max_context_chars: int = 5000

    @property
    def mysql_url(self) -> str:
        """返回完整的 MySQL 连接 URL（含账号、密码、数据库名）。

        调用顺序：mini-rag 流程 -> Settings.mysql_url()。
        """
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
        )

    @property
    def chat_model(self) -> str:
        """返回 LLM 模型名称，供 langchain ChatOpenAI 使用。

        调用顺序：mini-rag 流程 -> Settings.chat_model()。
        """
        return self.llm_model

    @property
    def openai_api_key(self) -> str:
        """返回 LLM API 密钥，供 langchain ChatOpenAI 使用。

        调用顺序：mini-rag 流程 -> Settings.openai_api_key()。
        """
        return self.llm_api_key

    @property
    def openai_base_url(self) -> str | None:
        """返回 LLM 服务地址，供 langchain ChatOpenAI 使用。

        调用顺序：mini-rag 流程 -> Settings.openai_base_url()。
        """
        return self.llm_base_url

    @property
    def llm_timeout_seconds(self) -> float:
        """返回 LLM 请求超时秒数。

        调用顺序：mini-rag 流程 -> Settings.llm_timeout_seconds()。
        """
        return self.llm_timeout


def load_scenario() -> ScenarioConfig:
    """从 TOML 文件加载企业知识库场景配置。

    读取路径：
      mini-rag/scenarios/enterprise_knowledge/scenario.toml

    解析字段映射到 ScenarioConfig 的各个属性，
    字符串列表转换为 tuple（保证 frozen dataclass 的不可变性）。

    Returns:
        解析后的场景配置对象

    Raises:
        FileNotFoundError: scenario.toml 不存在
        tomllib.TOMLDecodeError: TOML 格式解析失败

    调用顺序：mini-rag 流程 -> load_scenario()。
    """
    scenario_path = PROJECT_ROOT / "scenarios" / "enterprise_knowledge" / "scenario.toml"
    payload = tomllib.loads(scenario_path.read_text(encoding="utf-8"))
    scenario_root = scenario_path.parent
    return ScenarioConfig(
        scenario_id=str(payload["scenario_id"]),
        display_name=str(payload["display_name"]),
        assistant_name=str(payload["assistant_name"]),
        business_domain=str(payload["business_domain"]),
        support_contact=str(payload["support_contact"]),
        faq_collection=str(payload["faq_collection"]),
        doc_collection=str(payload["doc_collection"]),
        valid_sources=tuple(str(item) for item in payload["valid_sources"]),
        source_labels=dict(payload["source_labels"]),
        source_patterns=dict(payload["source_patterns"]),
        data_root=scenario_root / "data",
        faq_csv_path=scenario_root / "faq.csv",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """读取并缓存 Mini RAG 的完整运行时配置。

    所有配置项按以下优先级读取：
      1. 系统环境变量
      2. mini-rag/.env
      3. 仓库根目录 .env
      4. 代码默认值

    使用 lru_cache 保证每个进程只进行一次环境变量读取，
    减少重复的系统调用开销。

    Returns:
        合并所有配置源后的 Settings 对象

    调用顺序：mini-rag 流程 -> get_settings()。
    """
    return Settings(
        scenario_id=env("ACTIVE_SCENARIO_ID", "enterprise_knowledge"),
        milvus_uri=env("MILVUS_URI", "http://localhost:19530"),
        mysql_host=env("MYSQL_HOST", "127.0.0.1"),
        mysql_port=int(env("MYSQL_PORT", "3306")),
        mysql_user=env("MYSQL_USER", "root"),
        mysql_password=env("MYSQL_PASSWORD", "root123"),
        mysql_database=env("MYSQL_DATABASE", "subjects_kg"),
        embedding_model_path=project_path(env("EMBEDDING_MODEL_PATH", "models/bge-m3")),
        reranker_model_path=project_path(env("RERANKER_MODEL_PATH", "models/bge-reranker-large")),
        llm_model=env("LLM_MODEL", "qwen-plus"),
        llm_api_key=env_any(("DASHSCOPE_API_KEY", "OPENAI_API_KEY"), ""),
        llm_base_url=env_any(("DASHSCOPE_BASE_URL", "OPENAI_BASE_URL"), "") or None,
        llm_timeout=float(env("LLM_TIMEOUT", "60")),
        llm_temperature=float(env("LLM_TEMPERATURE", "0.1")),
        embedding_model_version=env("EMBEDDING_MODEL_VERSION", "bge-m3-local-v1"),
        reranker_model_version=env("RERANKER_MODEL_VERSION", "bge-reranker-large-local-v1"),
        chunk_schema_version=env("CHUNK_SCHEMA_VERSION", "parent_child_validity_v2"),
        retrieval_variant_max=int(env("RETRIEVAL_VARIANT_MAX", "2")),
        faq_top_k=int(env("FAQ_TOP_K", "20")),
        doc_top_k=int(env("DOC_TOP_K", "20")),
        rerank_top_n=int(env("RERANK_TOP_N", "8")),
        final_context_top_n=int(env("FINAL_CONTEXT_TOP_N", "5")),
        faq_direct_threshold=float(env("FAQ_DIRECT_SCORE_THRESHOLD", "0.84")),
        min_context_score=float(env("RAG_MIN_SCORE_THRESHOLD", "0.2")),
        max_context_chars=int(env("MAX_PROMPT_CONTEXT_CHARS", "5000")),
    )


# 模块级单例 — 场景配置在应用生命周期内保持不变
SCENARIO = load_scenario()
