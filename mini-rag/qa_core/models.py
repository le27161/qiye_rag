"""模型加载器 — BGE Embedding、CrossEncoder Reranker、ChatModel 三大模型。

所有模型使用 lru_cache 进程级缓存，避免重复加载消耗显存和内存。

模型职责：
  - Embedding (BGE-M3)     : 将文本转为 1024 维 Dense 向量，用于 Milvus Dense 检索
  - Reranker (BGE-Reranker): CrossEncoder 架构，对检索召回结果精排
  - ChatModel (LLM)        : 追问改写 + 最终答案生成

设备选择：
  - GPU 可用时自动使用 CUDA
  - 无 GPU 时回退到 CPU（本地课程环境友好）
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

# 禁止 HuggingFace tokenizers 的多进程并行，避免与 FastAPI 的多线程冲突
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from qa_core.config import get_settings


def device() -> str:
    """选择合适的推理设备：优先 CUDA，无 GPU 时用 CPU。

    注意：本地课程环境中 CPU 完全可以运行 BGE 模型（仅推理），
    只是速度较慢。CUDA 不是必须的。

    调用顺序：mini-rag 流程 -> device()。
    """
    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


def require_path(path: Path, label: str) -> Path:
    """验证模型路径存在，不存在时给出清晰的错误提示。

    这比 FileNotFoundError 更友好，会明确告诉用户是哪个模型目录不存在。

    调用顺序：mini-rag 流程 -> require_path()。
    """
    if not path.exists():
        raise RuntimeError(f"{label} path does not exist: {path}")
    return path


@lru_cache(maxsize=1)
def get_embeddings():
    """加载并缓存本地 BGE-M3 Embedding 模型。

    模型参数：
      - device: GPU/CPU 自动选择
      - local_files_only=True: 只使用本地文件，不尝试从 HuggingFace Hub 下载
      - normalize_embeddings=True: 输出 L2 归一化向量（Milvus 余弦相似度依赖归一化）

    返回：langchain_huggingface.HuggingFaceEmbeddings 实例

    调用顺序：mini-rag 流程 -> get_embeddings()。
    """
    from langchain_huggingface import HuggingFaceEmbeddings

    settings = get_settings()
    model_path = require_path(settings.embedding_model_path, "Embedding model")
    return HuggingFaceEmbeddings(
        model_name=str(model_path),
        model_kwargs={"device": device(), "local_files_only": True},
        encode_kwargs={"normalize_embeddings": True},
    )


@lru_cache(maxsize=1)
def get_reranker():
    """加载并缓存本地 BGE CrossEncoder Reranker 模型。

    CrossEncoder 重排序原理：
      - 将 (query, document) 拼接后同时输入模型
      - 输出一个相关性分数（而非向量距离）
      - 相比 Dense/BM25 检索，CrossEncoder 能更好地理解语义匹配

    参数：
      - local_files_only=True: 只使用本地模型文件
      - vocab_file: 指定 sentencepiece 词表文件路径（BGE Reranker 依赖此文件）
      - use_fast=False: 使用慢速 tokenizer（兼容性更好）

    返回：sentence_transformers.CrossEncoder 实例

    调用顺序：mini-rag 流程 -> get_reranker()。
    """
    from sentence_transformers import CrossEncoder

    settings = get_settings()
    model_path = require_path(settings.reranker_model_path, "Reranker model")
    # BGE Reranker Large 需要 sentencepiece 词表文件
    vocab_file = require_path(model_path / "sentencepiece.bpe.model", "Reranker tokenizer")
    return CrossEncoder(
        str(model_path),
        device=device(),
        local_files_only=True,
        # 使用慢速 tokenizer 并指定 vocab_file，确保与 HuggingFace 格式兼容
        tokenizer_kwargs={"use_fast": False, "vocab_file": str(vocab_file)},
    )


@lru_cache(maxsize=1)
def get_chat_model():
    """创建 LLM 对话模型实例 — 用于追问改写和答案生成。

    使用 OpenAI 兼容接口，支持：
      - OpenAI 官方 API
      - DashScope（阿里云百炼）
      - 本地 vLLM / Ollama 等 OpenAI 兼容服务

    配置从 Settings 中读取（API Key、Base URL、模型名、超时、温度）。

    异常情况：
      - 如果未配置 DASHSCOPE_API_KEY，抛出 RuntimeError 并提示配置方法

    返回：langchain_openai.ChatOpenAI 实例

    调用顺序：mini-rag 流程 -> get_chat_model()。
    """
    from langchain_openai import ChatOpenAI

    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("DASHSCOPE_API_KEY is required for Mini RAG answer generation.")
    return ChatOpenAI(
        model=settings.chat_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout_seconds,
    )



