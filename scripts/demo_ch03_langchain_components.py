"""第 03 章可运行演示：KnowForge 使用的 LangChain 基础组件。

本演示刻意保持离线状态：
- 不需要 LLM API key
- 不需要 Milvus 连接
- 不需要项目数据库

它展示了项目后续在实际管道代码中使用的小型 LangChain 构建块：
Message 对象、Runnable、结构化 Pydantic 输出、Document 和
RecursiveCharacterTextSplitter。

使用方式：
    python scripts/demo_ch03_langchain_components.py
"""

from __future__ import annotations

from pprint import pprint

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableLambda
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field


class QueryPlan(BaseModel):
    """演示用的结构化输出模型。

    模拟了后续项目中 query_variants.py 里的路由输出结构。

    Attributes:
        intent: 路由意图（如 KNOWLEDGE_QUERY / FAQ_QUERY）
        variants: 确定性查询变体列表
        needs_retrieval: 是否需要执行检索

    调用顺序：命令行入口 -> QueryPlan。
    """

    intent: str = Field(description="路由意图")
    variants: list[str] = Field(description="确定性查询变体")
    needs_retrieval: bool = Field(description="是否需要执行检索")


def build_messages(question: str) -> list[SystemMessage | HumanMessage | AIMessage]:
    """构建多轮消息序列，模拟 ChatOpenAI 的输入格式。

    与项目中 qa_core/memory/history.py 的消息结构一致：
    SystemMessage → HumanMessage → AIMessage → HumanMessage（当前问题）。

    参数:
        question: 用户当前提问

    返回:
        按对话顺序排列的消息列表

    调用顺序：命令行入口 -> build_messages()。
    """
    return [
        SystemMessage(content="你是企业内部知识助手，只回答制度、流程和资料范围内的问题。"),
        HumanMessage(content="新人入职流程有哪些步骤？"),
        AIMessage(content="新人入职通常包括材料提交、合同签署、账号开通和部门报到。"),
        HumanMessage(content=question),
    ]


def deterministic_query_planner(payload: dict) -> QueryPlan:
    """纯函数版本的路由规划器，模拟结构化路由输出。

    与项目中 qa_core/pipeline/query_variants.py 的逻辑对应，
    但此处不调用 LLM，而是基于关键词做规则判断。

    参数:
        payload: 包含 "question" 字段的字典

    返回:
        QueryPlan 实例，包含路由意图和查询变体

    调用顺序：命令行入口 -> deterministic_query_planner()。
    """
    question = str(payload["question"]).strip()
    # 生成原始问题作为基础变体
    variants = [question]
    # 如果问题包含"流程"，自动生成同义变体
    if "流程" in question:
        variants.extend([
            question.replace("流程", "SOP"),
            question.replace("流程", "办理步骤"),
        ])
    return QueryPlan(
        # 包含"流程"或"制度"关键词认定为 KNOWLEDGE_QUERY，否则为 FAQ_QUERY
        intent="KNOWLEDGE_QUERY" if "流程" in question or "制度" in question else "FAQ_QUERY",
        # dict.fromkeys 去重，保持原始顺序
        variants=list(dict.fromkeys(variants)),
        needs_retrieval=True,
    )


def build_documents() -> list[Document]:
    """构建 LangChain Document 对象，模拟入库层的数据格式。

    与项目中 qa_core/indexing/document_loaders.py 生成的 Document 结构相同，
    包含 page_content 和 metadata（scenario_id、source、file_name、kb_version）。

    返回:
        包含一条测试文档的 Document 列表

    调用顺序：命令行入口 -> build_documents()。
    """
    return [
        Document(
            page_content=(
                "新人入职流程包括提交身份证明、签署劳动合同、开通邮箱和 VPN、"
                "完成部门报到。试用期转正需要直属负责人审批。"
            ),
            metadata={
                "scenario_id": "enterprise_knowledge",
                "source": "hr",
                "file_name": "onboarding.md",
                "kb_version": "kb_demo",
            },
        )
    ]


def split_documents(documents: list[Document]) -> list[Document]:
    """使用与项目相同的 Splitter 对文档进行切分。

    与项目中 qa_core/indexing/chunking.py 使用的
    RecursiveCharacterTextSplitter 同族，但 chunk 参数更小以适合演示。

    参数:
        documents: 待切分的 Document 列表

    返回:
        切分后的 Document chunk 列表

    调用顺序：命令行入口 -> split_documents()。
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=42,
        chunk_overlap=8,
        # 按中文标点优先切分，保持语义完整性
        separators=["。", "，", "\n", " ", ""],
    )
    return splitter.split_documents(documents)


def main() -> None:
    """演示主入口：依次展示 LangChain 五大核心组件的用法。

    执行流程:
        1. Message 对象：展示多轮对话的消息结构
        2. Runnable + 结构化输出：模拟路由规划器的调用链
        3. Document + metadata：展示文档和元数据如何组织
        4. RecursiveCharacterTextSplitter：展示中文文本切分效果
        5. 映射到项目代码位置：帮助读者找到实际生产代码
    """
    question = "入职流程需要哪些审批？"

    print("\n[1] Message 对象")
    for message in build_messages(question):
        print(f"- {message.__class__.__name__}: {message.content}")

    print("\n[2] Runnable + 结构化对象")
    planner = RunnableLambda(deterministic_query_planner)
    plan = planner.invoke({"question": question})
    pprint(plan.model_dump())

    print("\n[3] Document + metadata")
    documents = build_documents()
    for doc in documents:
        pprint({"page_content": doc.page_content, "metadata": doc.metadata})

    print("\n[4] RecursiveCharacterTextSplitter")
    chunks = split_documents(documents)
    for index, chunk in enumerate(chunks, start=1):
        pprint({
            "chunk": index,
            "page_content": chunk.page_content,
            "metadata": chunk.metadata,
        })

    print("\n[5] 项目代码位置映射")
    pprint({
        "ChatOpenAI": "qa_core/llm/client.py::get_chat_model",
        "messages": "qa_core/memory/history.py",
        "structured_output": "qa_core/pipeline/query_variants.py",
        "Document_loader": "qa_core/indexing/document_loaders.py",
        "splitter": "qa_core/indexing/chunking.py",
        "VectorStore": "qa_core/retrieval/store.py::MilvusHybridStore",
    })


if __name__ == "__main__":
    main()
