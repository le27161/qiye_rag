# -*- coding: utf-8 -*-
# ============================================================================
# 第 07 章兼容入口：查询改写与变体生成
# ============================================================================
# 这是一个命令行交互脚本，使用真实项目模块演示第 07 章核心功能，
# 可能调用已配置的 LLM（当改写或变体生成需要时）。
#
# 与 demo_query_prepare.py 的区别：
#   - demo_query_prepare.py: 停在检索计划（第 06 章范围），不执行改写和变体
#   - demo_query_rewrite_variants.py（本脚本）: 执行完改写 + 变体生成
#     （第 07 章范围），在 Milvus 检索之前停止
#
# 用法示例：
#   python scripts\demo_query_rewrite_variants.py "那审批呢" --history "报销流程是什么"
#   python scripts\demo_query_rewrite_variants.py "入职流程文档在哪里查看"
#   python scripts\demo_query_rewrite_variants.py "报销流程" --source finance
# ============================================================================

"""演示查询变体的规则生成与模型生成路径。

调用顺序：课程示例、测试或命令行入口 -> 本模块公开接口。
"""

from __future__ import annotations

# argparse: 命令行参数解析
import argparse

# json: 标准 JSON 序列化
import json

# sys: 系统功能（sys.path 修改）
import sys

# dataclasses: 数据类定义（RoutePreview）
from dataclasses import dataclass

# pathlib.Path: 文件路径操作
from pathlib import Path

# typing.Literal: 字面量类型
from typing import Literal

# HumanMessage: LangChain 标准人类消息类型
from langchain_core.messages import HumanMessage

# ── 路径设置 ──
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ── 导入核心 API ──
from qa_core.intent.classifier import IntentResult, classify_direct_intent, classify_intent
from qa_core.pipeline.query_variants import generate_query_variants  # 第 07 章：查询变体生成
from qa_core.pipeline.rewrite import rewrite_query_if_needed        # 第 07 章：追问改写
from qa_core.retrieval.strategy import build_retrieval_plan
from qa_core.scenarios.boundary import detect_source_boundary
from qa_core.scenarios.registry import ScenarioDefinition, resolve_scenario

RouteName = Literal["direct_answer", "retrieval"]


@dataclass(frozen=True)
class RoutePreview:
    """轻量路由预览 —— 命令行演示用。

    Attributes:
        route: "direct_answer" | "retrieval"
        answer: 直答答案
        intent: 意图分类结果
        reason: 路由原因码

    调用顺序：命令行入口 -> RoutePreview。
    """
    route: RouteName
    answer: str | None = None
    intent: IntentResult | None = None
    reason: str = ""


def parse_args() -> argparse.Namespace:
    """解析命令行参数。

    调用顺序：命令行入口 -> parse_args()。
    """
    parser = argparse.ArgumentParser(description="Inspect query rewrite and query variants before Milvus retrieval.")
    parser.add_argument("query", help="User question")
    parser.add_argument("--history", action="append", default=[], help="Previous user/assistant message. Can be repeated.")
    parser.add_argument("--source", "--source-filter", dest="source_filter", help="Frontend-selected source filter.")
    parser.add_argument("--scenario", dest="scenario_id", help="Scenario id. Defaults to ACTIVE_SCENARIO_ID.")
    return parser.parse_args()


def message_history(items: list[str]) -> list[HumanMessage]:
    """将命令行历史字符串转为 LangChain HumanMessage 列表。

    调用顺序：命令行入口 -> message_history()。
    """
    return [HumanMessage(content=item.strip()) for item in items if item and item.strip()]


def validate_source_filter(source_filter: str | None, scenario: ScenarioDefinition) -> None:
    """当 source_filter 不在场景白名单中时快速失败。

    调用顺序：命令行入口 -> validate_source_filter()。
    """
    if source_filter and source_filter not in scenario.valid_sources:
        allowed = ", ".join(scenario.valid_sources)
        raise ValueError(f"source_filter={source_filter!r} is not valid for scenario {scenario.scenario_id}. Allowed: {allowed}")


def resolve_effective_source_filter(
    source_filter: str | None,
    suggested_source: str | None,
    scenario: ScenarioDefinition,
) -> str | None:
    """确定有效 source：命令行 > intent 推断 > None。

    调用顺序：命令行入口 -> resolve_effective_source_filter()。
    """
    if source_filter:
        return source_filter
    if suggested_source and suggested_source in scenario.valid_sources:
        return suggested_source
    return None


def boundary_answer(
    query: str,
    scenario: ScenarioDefinition,
    source_filter: str | None,
) -> tuple[str | None, dict]:
    """返回 source-boundary 提示（与主 pipeline 一致的确定性逻辑）。

    调用顺序：命令行入口 -> boundary_answer()。
    """
    boundary = detect_source_boundary(query, scenario, source_filter)
    payload = boundary.as_dict()
    if not boundary.mismatched:
        return None, payload
    answer = (
        f"当前选择的是「{boundary.selected_source_label}」，但问题更像当前场景下的"
        f"「{boundary.matched_source_label}」分类。为避免按错误资料回答，请切换分类后再查询。"
    )
    return answer, payload


def decide_low_cost_route(
    query: str,
    scenario: ScenarioDefinition,
    source_filter: str | None,
) -> tuple[RoutePreview, dict]:
    """镜像主 pipeline 的确定性路由检查（不含 FAQ 快路径检索）。

    调用顺序：命令行入口 -> decide_low_cost_route()。
    """
    validate_source_filter(source_filter, scenario)

    # 直答意图检查
    direct_intent = classify_direct_intent(query, scenario)
    if direct_intent:
        return (
            RoutePreview(route="direct_answer", answer=direct_intent.direct_answer,
                         intent=direct_intent, reason=direct_intent.reason),
            {"reason": "not_checked_after_direct_answer"},
        )

    # source 边界检查
    answer, boundary_payload = boundary_answer(query, scenario, source_filter)
    if answer:
        intent = IntentResult(intent="OUT_OF_SCOPE", direct_answer=answer, confidence=0.98,
                              reason="source_boundary", requires_rewrite=False, suggested_source=None)
        return RoutePreview(route="direct_answer", answer=answer, intent=intent, reason="source_boundary"), boundary_payload

    return RoutePreview(route="retrieval", reason="no_deterministic_route"), boundary_payload


def route_payload(route: RoutePreview) -> dict:
    """将 RoutePreview 序列化为 JSON 友好的 dict。

    调用顺序：命令行入口 -> route_payload()。
    """
    return {
        "route": route.route,
        "reason": route.reason,
        "answer": route.answer,
        "intent": route.intent.as_dict() if route.intent else None,
    }


def main() -> None:
    """解析参数 → 路由 → 意图 → 改写 → 计划 → 变体 → 输出 JSON。

    执行流程（串联第 05/06/07 章）：
      1. 解析参数 + 获取场景配置
      2. decide_low_cost_route() — 低成本路由判断
      3. 如果 route=retrieval：
         a. classify_intent() — 检索意图分类（第 05 章）
         b. rewrite_query_if_needed() — 追问改写（第 07 章新增）
         c. build_retrieval_plan() — 检索计划（第 06 章）
         d. generate_query_variants() — 查询变体（第 07 章新增）
      4. 序列化为 JSON 并打印
    """
    args = parse_args()
    scenario = resolve_scenario(args.scenario_id)
    history = message_history(args.history)

    # 步骤 1：路由决策
    route, source_boundary = decide_low_cost_route(args.query, scenario, args.source_filter)

    intent = route.intent
    plan = None
    rewritten_query = None
    query_variants = None
    source_filter = None

    # 步骤 2：仅 retrieval 时执行后续链路
    if route.route == "retrieval":
        # 2a. 意图分类
        intent = classify_intent(args.query, history, scenario)
        # 2b. 确定有效 source
        source_filter = resolve_effective_source_filter(args.source_filter, intent.suggested_source, scenario)
        # 2c. 追问改写（消费 IntentResult.requires_rewrite）
        rewritten_query = rewrite_query_if_needed(args.query, history, intent.requires_rewrite)
        # 2d. 检索计划（基于改写后的问题）
        plan = build_retrieval_plan(rewritten_query, intent)
        # 2e. 查询变体（消费 RetrievalPlan.use_query_variants）
        query_variants = generate_query_variants(
            rewritten_query,
            enabled=plan.use_query_variants,
            allow_short_structured=intent.intent == "FOLLOW_UP",
        )

    # 步骤 3：构造输出
    output = {
        "query": args.query,
        "history": args.history,
        "scenario": {
            "scenario_id": scenario.scenario_id,
            "display_name": scenario.display_name,
        },
        "route": route_payload(route),
        "source_boundary": source_boundary,
        "intent": intent.as_dict() if intent else None,
        "effective_source_filter": source_filter,
        "retrieval_plan": plan.as_dict() if plan else None,
        "rewritten_query": rewritten_query,       # 第 07 章产出
        "query_variants": query_variants,           # 第 07 章产出
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
