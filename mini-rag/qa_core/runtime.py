"""Mini RAG 运行时依赖检查 — 帮助排查环境问题。

检测 Ask 流程所需的所有 Python 包是否已安装，
对常见运行时报错给出友好中文提示。
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeDependency:
    """Mini RAG 运行时依赖的 Python 包描述。

    Attributes:
        module:  import 时使用的模块标识（如 "langchain_milvus"）
        package: pip install 的包名（如 "langchain-milvus"）
        used_by: 中文用途说明（如 "Milvus 混合检索"），用于报错提示

    调用顺序：mini-rag 流程 -> RuntimeDependency。
    """

    module: str
    package: str
    used_by: str


# Mini RAG 在线问答流程所必需的全部 Python 依赖清单
ASK_DEPENDENCIES: tuple[RuntimeDependency, ...] = (
    RuntimeDependency("langchain_milvus", "langchain-milvus", "Milvus 混合检索"),
    RuntimeDependency("pymilvus", "pymilvus", "Milvus 连接"),
    RuntimeDependency("langchain_huggingface", "langchain-huggingface", "BGE embedding"),
    RuntimeDependency("sentence_transformers", "sentence-transformers", "CrossEncoder rerank"),
    RuntimeDependency("langchain_openai", "langchain-openai", "LLM 改写与生成"),
    RuntimeDependency("torch", "torch", "本地模型推理"),
    RuntimeDependency("sqlalchemy", "SQLAlchemy", "MySQL active 版本"),
    RuntimeDependency("pymysql", "PyMySQL", "MySQL 连接驱动"),
)


def check_dependencies() -> dict[str, object]:
    """检查当前 Python 环境是否可以运行 Mini RAG 的 Ask 流程。

    使用 importlib.util.find_spec 检测模块是否可导入（不实际加载模块），
    比 try/except ImportError 更轻量。

    返回字典包含：
      - ok: bool — 所有依赖是否就绪
      - missing: list[dict] — 缺失的依赖列表（模块名、包名、用途）
      - install_command: str — 安装命令提示
      - hint: str — 中文环境提示（conda 用户注意事项）

    调用顺序：mini-rag 流程 -> check_dependencies()。
    """
    missing = [
        {"module": dep.module, "package": dep.package, "used_by": dep.used_by}
        for dep in ASK_DEPENDENCIES
        if importlib.util.find_spec(dep.module) is None
    ]
    return {
        "ok": not missing,
        "missing": missing,
        "install_command": "pip install -r requirements.txt",
        "hint": (
            "请确认启动 Mini RAG 的 Python 环境就是已安装项目依赖的环境。"
            "如果使用 conda，请先 conda activate knowforge-rag。"
        ),
    }


def dependency_error_message(exc: ModuleNotFoundError) -> str:
    """将 ModuleNotFoundError 转换为友好的中文安装提示。

    根据缺失的模块名匹配 ASK_DEPENDENCIES 清单：
      - 匹配成功 → 给出包名和用途说明
      - 匹配失败 → 使用模块名本身作为包名提示

    调用顺序：mini-rag 流程 -> dependency_error_message()。
    """
    missing_name = exc.name or str(exc)
    matched = next((dep for dep in ASK_DEPENDENCIES if dep.module == missing_name), None)
    if matched:
        package = matched.package
        used_by = matched.used_by
    else:
        package = missing_name
        used_by = "Mini RAG 运行链路"
    return (
        f"当前 Python 环境缺少模块 {missing_name}，它用于{used_by}。"
        f"请在启动 Mini RAG 的同一个环境中执行：pip install -r requirements.txt。"
        f"如果项目依赖已经装在 conda 环境里，请先 conda activate knowforge-rag，再启动 API。"
        f"对应包名：{package}。"
    )


def friendly_runtime_error(exc: Exception) -> str | None:
    """将常见运行时异常转换为中文友好提示。

    当前识别的异常类型：
      - AuthenticationError / invalid_api_key : OpenAI/LLM 鉴权失败
      - RateLimitError / rate limit            : LLM 调用触发限流
      - TimeoutError / request timed out       : LLM 请求超时
      - DASHSCOPE_API_KEY is required          : 缺少 API Key

    如果异常不在已知范围内，返回 None，由上层使用原始错误信息。

    调用顺序：mini-rag 流程 -> friendly_runtime_error()。
    """
    class_name = exc.__class__.__name__
    text = str(exc)

    if class_name == "AuthenticationError" or "invalid_api_key" in text or "Incorrect API key" in text:
        return (
            "LLM 鉴权失败：当前环境中的 DASHSCOPE_API_KEY 无效、过期，或不属于当前配置的 "
            "DASHSCOPE_BASE_URL。请更换有效 Key 后重新启动 Mini RAG。"
        )
    if class_name in {"RateLimitError", "APIRateLimitError"} or "rate limit" in text.lower():
        return "LLM 调用触发限流，请稍后重试，或更换可用额度的模型/API Key。"
    if "request timed out" in text.lower() or class_name in {"APITimeoutError", "TimeoutException"}:
        return (
            "LLM 请求超时：Mini RAG 已进入追问改写或答案生成阶段，但当前 DASHSCOPE_BASE_URL/模型服务响应过慢。"
            "请检查模型网关是否可访问，或把 LLM_TIMEOUT 调大后重启 Mini RAG。"
        )
    if "DASHSCOPE_API_KEY is required" in text or "OPENAI_API_KEY is required" in text:
        return "缺少 DASHSCOPE_API_KEY。请在 mini-rag/.env 或启动 Mini RAG 的同一个终端中设置 DASHSCOPE_API_KEY。"

    return None





