"""Prompt 构建 — System Prompt 模板 + 上下文组装 + LLM 答案生成。

Mini RAG 的生成层，负责：
  1. 构建 System Prompt（限定角色、约束回答规则）
  2. 组装上下文（文档块编号 + 引用标注 + 长度控制）
  3. 调用 LLM 生成最终答案

System Prompt 设计理念：
  - 角色绑定：明确助手身份（如 "企业知识库助手"）
  - 规则约束：资料外不编造、回答简洁可执行、给出引用来源
  - 可模板化：assistant_name 从场景配置动态注入
"""

from __future__ import annotations

from langchain_core.documents import Document

from qa_core.config import SCENARIO
from qa_core.models import get_chat_model
from qa_core.schemas import format_citation


# System Prompt 模板 — {assistant_name} 由场景配置动态填充
SYSTEM_PROMPT = """你是{assistant_name}，只基于给定资料回答问题。
规则：
1. 资料中没有依据时，明确说当前知识库资料不足。
2. 回答要简洁、可执行，优先给步骤或清单。
3. 末尾给出"参考来源"，列出使用到的来源。
"""


def build_context(documents: list[Document], max_chars: int) -> str:
    """从选定的文档列表构建紧凑的上下文文本块。

    每条文档的格式：
      [序号] 来源：hr / 员工手册.md / page 3
      文档内容...

    长度控制：
      当累积字符数超过 max_chars 时停止添加，避免上下文过长
      导致 LLM 注意力稀释或 token 超限。

    Args:
        documents: 选定的文档列表（已按相关度排列）
        max_chars: 最大总字符数

    Returns:
        拼接后的上下文字符串（文档块之间用双换行分隔）

    调用顺序：mini-rag 流程 -> build_context()。
    """
    parts: list[str] = []
    total = 0
    for index, document in enumerate(documents, start=1):
        metadata = dict(document.metadata or {})
        # 生成人类可读的引用标注
        citation = format_citation(metadata)
        text = document.page_content.strip()
        # 格式化每条上下文块
        block = f"[{index}] 来源：{citation}\n{text}"
        # 长度控制：超出限制则截断
        if total + len(block) > max_chars:
            break
        parts.append(block)
        total += len(block)
    return "\n\n".join(parts)


def build_answer_prompt(query: str, context: str, history: list[str]) -> list[tuple[str, str]]:
    """构建发送给 LLM 的完整消息列表（System + User）。

    消息结构：
      - System: 角色定义 + 回答规则（由 SYSTEM_PROMPT 模板填充）
      - User:   历史对话 + 当前问题 + 可用资料

    Args:
        query:   用户当前问题（已改写）
        context: 组装好的上下文文本
        history: 历史对话记录（最多取 6 轮）

    Returns:
        [(role, content), ...] 格式的消息列表

    调用顺序：mini-rag 流程 -> build_answer_prompt()。
    """
    # System 消息：注入场景特定的助手名称
    system = SYSTEM_PROMPT.format(assistant_name=SCENARIO.assistant_name)
    # 历史对话截断（最多 6 轮）
    history_text = "\n".join(history[-6:]) if history else "无"
    # User 消息：历史 + 问题 + 资料
    user = f"""历史对话：
{history_text}

用户问题：
{query}

可用资料：
{context}

请基于资料回答。"""
    return [("system", system), ("user", user)]


def generate_answer(query: str, context_docs: list[Document], history: list[str], max_context_chars: int) -> str:
    """调用 LLM 生成最终答案 — Mini RAG 的生成阶段入口。

    流程：
      1. 构建上下文文本块（文档编号 + 引用 + 长度控制）
      2. 组装 System + User 消息
      3. 调用 ChatModel 生成回答
      4. 返回清理后的答案文本

    边界情况：
      - 无上下文：直接返回 "资料不足" 提示，不调用 LLM
      - LLM 调用失败：异常向上抛出，由 app.py 的异常处理层捕获

    Args:
        query:            已改写的用户问题
        context_docs:     检索和精排后的上下文文档列表
        history:          历史对话记录
        max_context_chars: 上下文最大字符数

    Returns:
        LLM 生成的答案文本

    调用顺序：mini-rag 流程 -> generate_answer()。
    """
    # 构建上下文
    context = build_context(context_docs, max_context_chars)
    # 无可用上下文时直接返回，不浪费 LLM 调用
    if not context:
        return "当前知识库资料不足，无法基于已有资料可靠回答这个问题。"
    # 组装消息
    messages = build_answer_prompt(query, context, history)
    # 调用 LLM 生成
    answer = get_chat_model().invoke(messages).content
    return str(answer).strip()


