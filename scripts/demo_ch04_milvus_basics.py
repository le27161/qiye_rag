"""第 04 章可运行演示：PyMilvus 向量搜索基础生命周期。

本演示创建一个临时 Collection，构建 HNSW 索引，插入三条小型向量，
执行向量搜索，默认在演示结束后删除该 Collection。

前置条件：Milvus 服务可用（通过 qa_core.config.settings 中的 MILVUS_URI 配置）。

使用方式：
    python scripts/demo_ch04_milvus_basics.py

    保留 Collection（供后续调试）：
    python scripts/demo_ch04_milvus_basics.py --keep-collection

    或通过 Docker Compose：
    docker compose --env-file .env.compose run --rm api python scripts/demo_ch04_milvus_basics.py
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility

# 将项目根目录加入 Python 搜索路径，确保能导入 qa_core 包
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from qa_core.config.settings import get_settings


def parse_args() -> argparse.Namespace:
    """解析命令行参数。

    返回:
        包含 collection、keep_collection、uri 三个字段的参数命名空间

    调用顺序：命令行入口 -> parse_args()。
    """
    parser = argparse.ArgumentParser(description="运行一个临时的 PyMilvus 向量搜索演示。")
    parser.add_argument("--collection", default="demo_ch04_vector_search", help="临时 Collection 名称。")
    parser.add_argument("--keep-collection", action="store_true", help="演示结束后保留 Collection（默认删除）。")
    parser.add_argument("--uri", default="", help="覆盖 Milvus URI，默认使用 settings 中的 MILVUS_URI。")
    return parser.parse_args()


def connect(alias: str, uri: str) -> None:
    """连接到 Milvus 服务。

    从项目配置中读取 Milvus 连接参数，支持数据库名称（milvus_database）。
    连接别名使用时间戳后缀避免冲突。

    参数:
        alias: 连接别名（每个连接实例唯一）
        uri: Milvus 服务地址（为空时使用 settings 中的默认值）

    执行流程:
        1. 通过 get_settings() 获取全局配置
        2. 如果配置了 milvus_database，加入连接参数
        3. 调用 connections.connect() 建立连接
    """
    settings = get_settings()
    kwargs = {"alias": alias, "uri": uri or settings.milvus_uri}
    if settings.milvus_database:
        kwargs["db_name"] = settings.milvus_database
    connections.connect(**kwargs)


def reset_collection(collection_name: str, alias: str) -> None:
    """如果 Collection 已存在则删除，确保演示以干净状态开始。

    参数:
        collection_name: 要删除的 Collection 名称
        alias: 连接别名

    调用顺序：命令行入口 -> reset_collection()。
    """
    if utility.has_collection(collection_name, using=alias):
        utility.drop_collection(collection_name, using=alias)


def create_demo_collection(collection_name: str, alias: str) -> Collection:
    """创建演示用的 Collection，包含主键、文本、来源和向量四个字段。

    字段设计：
        - pk (VARCHAR): 文档唯一标识（主键）
        - text (VARCHAR): 文档文本内容
        - source (VARCHAR): 文档来源分类（hr / finance / it）
        - dense (FLOAT_VECTOR): 4 维稠密向量

    索引配置：
        - 索引类型：HNSW（分层可导航小世界图）
        - 距离度量：IP（内积）
        - 参数：M=8, efConstruction=64（适合小型演示数据集）

    参数:
        collection_name: Collection 名称
        alias: 连接别名

    返回:
        创建好的 Collection 实例（已建索引，但尚未插入数据）

    调用顺序：命令行入口 -> create_demo_collection()。
    """
    fields = [
        FieldSchema(name="pk", dtype=DataType.VARCHAR, is_primary=True, max_length=64),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="dense", dtype=DataType.FLOAT_VECTOR, dim=4),
    ]
    schema = CollectionSchema(fields=fields, description="第 04 章 PyMilvus 演示 Collection")
    collection = Collection(
        name=collection_name,
        schema=schema,
        using=alias,
        consistency_level="Session",
    )
    # 在插入前建索引，避免后续搜索报错
    collection.create_index(
        field_name="dense",
        index_params={
            "index_type": "HNSW",
            "metric_type": "IP",
            "params": {"M": 8, "efConstruction": 64},
        },
    )
    return collection


def insert_demo_rows(collection: Collection) -> None:
    """向 Collection 中插入三条演示数据并立即落盘。

    三条数据分别模拟 HR（人力资源）、Finance（财务）和 IT（信息技术）
    三个业务领域的文档，每个文档的向量在不同维度上有高响应值。

    参数:
        collection: 已创建好的 Collection 实例

    执行流程:
        1. 构造包含三条文档的 rows 列表
        2. 调用 collection.insert() 批量插入
        3. 调用 collection.flush() 确保数据落盘可查
    """
    rows = [
        {
            "pk": "doc_hr_onboarding",
            "text": "新人入职需要提交材料、签署合同并完成账号开通。",
            "source": "hr",
            "dense": [0.92, 0.08, 0.02, 0.01],  # 第一维响应最高 → HR 主题
        },
        {
            "pk": "doc_finance_expense",
            "text": "报销需要发票、审批单和部门负责人签字。",
            "source": "finance",
            "dense": [0.05, 0.91, 0.03, 0.02],  # 第二维响应最高 → Finance 主题
        },
        {
            "pk": "doc_it_vpn",
            "text": "VPN 无法连接时先检查账号状态、客户端版本和网络环境。",
            "source": "it",
            "dense": [0.05, 0.05, 0.95, 0.01],  # 第三维响应最高 → IT 主题
        },
    ]
    collection.insert(rows)
    collection.flush()


def search_demo(collection: Collection) -> None:
    """在 Collection 上执行向量搜索演示。

    查询向量 [0.9, 0.1, 0.02, 0.01] 模拟 HR 主题的查询，
    期望召回 doc_hr_onboarding 作为第一条结果。

    参数:
        collection: 已包含数据的 Collection 实例

    执行流程:
        1. 将 Collection 加载到内存（collection.load()）
        2. 构造与 HR 文档接近的查询向量
        3. 执行搜索（limit=3, output_fields 包含 text 和 source）
        4. 打印排序后的搜索结果
    """
    collection.load()
    # 查询向量与 doc_hr_onboarding 的向量接近，预期第一维响应最高
    query_vector = [[0.9, 0.1, 0.02, 0.01]]
    results = collection.search(
        data=query_vector,
        anns_field="dense",
        param={"metric_type": "IP", "params": {"ef": 32}},
        limit=3,
        output_fields=["text", "source"],
    )
    print("\n查询向量（接近 HR 入职文档）的搜索结果：")
    for rank, hit in enumerate(results[0], start=1):
        print(
            f"{rank}. pk={hit.id}, score={hit.score:.4f}, "
            f"source={hit.entity.get('source')}, text={hit.entity.get('text')}"
        )


def main() -> None:
    """演示主入口：完整的 Milvus 向量搜索生命周期。

    执行流程:
        1. 解析命令行参数
        2. 生成带时间戳的唯一连接别名
        3. 连接到 Milvus 服务
        4. 清理可能残留的同名 Collection
        5. 创建演示 Collection 和 HNSW 索引
        6. 插入三条演示数据
        7. 执行向量搜索并打印结果
        8. 根据 --keep-collection 决定是否删除临时 Collection
        9. 断开 Milvus 连接
    """
    args = parse_args()
    # 使用时间戳确保连接别名唯一，避免并发冲突
    alias = f"{args.collection}_{int(time.time())}_alias"
    connect(alias, args.uri)
    try:
        reset_collection(args.collection, alias)
        collection = create_demo_collection(args.collection, alias)
        print(f"已创建 Collection：{args.collection}")
        insert_demo_rows(collection)
        print("已插入 3 条演示数据并落盘。")
        search_demo(collection)
    finally:
        if not args.keep_collection:
            reset_collection(args.collection, alias)
            print(f"\n已删除临时 Collection：{args.collection}")
        connections.disconnect(alias)


if __name__ == "__main__":
    main()
