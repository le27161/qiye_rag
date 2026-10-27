"""FastAPI 入口 — Mini RAG 的 Web 服务启动文件。

提供三个端点：
  - GET  /       : 返回 Mini RAG 前端页面（static/index.html）
  - GET  /health : 健康检查，返回场景配置、LLM 配置、依赖检查、知识库版本等信息
  - POST /ask    : 核心问答接口，接收用户问题，返回 RAG 答案及检索溯源

启动方式：
  uvicorn app:app --reload

运行依赖：
  除 Python 标准库外需要安装 requirements.txt 中的全部包。
  启动后可通过 /health 端点检查依赖是否就绪。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# 将 mini-rag 根目录加入 Python 搜索路径，确保能 import qa_core 包
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from qa_core.config import SCENARIO, get_settings, loaded_env_files
from qa_core.kb_version import active_version
from qa_core.pipeline import ask
from qa_core.runtime import check_dependencies, dependency_error_message, friendly_runtime_error


class AskRequest(BaseModel):
    """Mini RAG 问答请求体。

    对应 POST /ask 接口的 JSON 请求体格式。
    所有字段均通过 Pydantic 进行校验。

    Attributes:
        query:         用户当前提出的问题（必填，至少 1 个字符）
        history:       历史对话记录列表，用于追问改写和上下文理解（可选）
        source_filter: 数据来源筛选，如 "hr" / "it" / "finance"（可选，不传则检索全部来源）

    调用顺序：mini-rag 流程 -> AskRequest。
    """

    query: str = Field(min_length=1)
    history: List[str] = Field(default_factory=list)
    source_filter: Optional[str] = None


# 创建 FastAPI 应用实例
app = FastAPI(title="Mini RAG", version="0.1.0")

# 静态文件目录 — 托管前端 HTML / JS / CSS
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    """返回 Mini RAG 前端页面（static/index.html）。

    这是用户通过浏览器访问 Mini RAG 的入口页面，
    包含聊天界面和配置展示面板。

    调用顺序：mini-rag 流程 -> index()。
    """
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> Dict[str, Any]:
    """健康检查端点。

    返回完整的运行时状态信息，用于：
      - 启动后自检诊断，确认所有组件就绪
      - 排查环境配置问题（如缺少依赖、API Key 未配置等）
      - 前端展示当前运行配置

    返回字段分类：
      - scenario_id / display_name : 当前场景标识
      - valid_sources / source_labels : 可用数据来源
      - active_kb_version : 当前激活的知识库版本
      - llm : LLM 模型、API Key 配置、超时、温度等
      - retrieval_config : 检索参数（rerank、top_k 等）
      - runtime : Python 依赖包检查结果

    调用顺序：mini-rag 流程 -> health()。
    """
    # 检查 Python 环境是否安装了全部必要依赖
    runtime = check_dependencies()
    settings = get_settings()

    # 尝试获取当前激活的知识库版本
    # 如果数据库连接失败、表未初始化或未执行 rebuild，给出友好提示
    try:
        kb_version = active_version()
    except Exception as exc:  # noqa: BLE001 - 健康检查必须展示所有安装状态
        kb_version = f"not_ready: {exc}"

    return {
        "ok": True,
        "scenario_id": SCENARIO.scenario_id,
        "display_name": SCENARIO.display_name,
        "valid_sources": list(SCENARIO.valid_sources),
        "source_labels": SCENARIO.source_labels,
        "active_kb_version": kb_version,
        "llm": {
            "chat_model": settings.chat_model,
            "base_url": settings.openai_base_url or "https://api.openai.com/v1",
            "api_key_configured": bool(settings.openai_api_key),
            "timeout_seconds": settings.llm_timeout_seconds,
            "temperature": settings.llm_temperature,
            "env_files": loaded_env_files(),
        },
        "retrieval_config": {
            "rerank": settings.rerank_enabled,
            "use_query_variants": settings.use_query_variants,
            "faq_top_k": settings.faq_top_k,
            "doc_top_k": settings.doc_top_k,
            "rerank_top_n": settings.rerank_top_n,
        },
        "runtime": runtime,
    }


@app.post("/ask")
def ask_api(request: AskRequest) -> Dict[str, Any]:
    """核心问答接口 — 一条问题从入口到答案的完整 RAG 链路。

    流程概览：
      1. 直接回答判断（打招呼 / 转人工）— 无检索、无 LLM
      2. 获取当前激活的知识库版本
      3. 追问改写 + 生成多路查询变体
      4. FAQ 集合混合检索（Dense + BM25 + Reranker）
      5. 高置信度 FAQ 直接返回标准答案
      6. 文档集合混合检索（Dense + BM25 + Reranker）
      7. 合并 FAQ + Doc 命中 → 构建上下文
      8. LLM 生成最终答案（带参考来源）

    返回字段：
      - answer           : 最终答案文本
      - sources          : 引用来源列表（含来源类型、分数、内容预览、引用标注）
      - route            : 命中路由（direct_answer / faq_direct / rag）
      - rewritten_query  : 改写后的查询（追问还原结果）
      - query_variants   : 多路检索变体列表
      - retrieval        : 检索细节统计（各阶段耗时、命中数、最高分等）

    异常处理：
      - ValueError （参数校验失败）→ 400
      - ModuleNotFoundError（缺少依赖）→ 500 + 安装提示
      - 其他运行时错误（LLM 认证失败、超时等）→ 500 + 中文友好提示

    调用顺序：mini-rag 流程 -> ask_api()。
    """
    try:
        result = ask(
            request.query,
            history=request.history,
            source_filter=request.source_filter,
        )
    except ValueError as exc:
        # 参数校验失败（如无效的 source_filter）→ 返回 400 Bad Request
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ModuleNotFoundError as exc:
        # 缺少 Python 依赖 → 返回 500 并给出安装命令提示
        raise HTTPException(status_code=500, detail=dependency_error_message(exc)) from exc
    except Exception as exc:
        # 其他运行时错误 → 返回 500 并替换为中文友好提示
        detail = friendly_runtime_error(exc) or str(exc)
        raise HTTPException(status_code=500, detail=detail) from exc

    return {
        "answer": result.answer,
        "sources": result.sources,
        "route": result.route,
        "rewritten_query": result.rewritten_query,
        "query_variants": result.query_variants,
        "retrieval": result.retrieval,
    }
