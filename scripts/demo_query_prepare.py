# -*- coding: utf-8 -*-
# ============================================================================
# 第 06 章兼容入口：查询准备演示（路由 + 意图 + 检索计划）
# ============================================================================
# 这是一个命令行交互脚本，使用真实项目模块演示第 06 章核心功能，
# 但有意在 Milvus 检索之前停止——不执行查询改写、查询变体和实际检索。
#
# 演示内容：
#   1. decide_low_cost_route() — 低成本路由决策（直答/检索 + source_boundary）
#   2. classify_intent()       — 检索意图分类（FOLLOW_UP / FAQ / KNOWLEDGE + source 推断）
#   3. build_retrieval_plan()  — 检索计划生成（15 个检索参数）
#
# 用法示例：
#   python scripts\demo_query_prepare.py "报销流程是什么"
#   python scripts\demo_query_prepare.py "那审批呢" --history "报销流程是什么"
#   python scripts\demo_query_prepare.py "报销流程" --source finance
#   python scripts\demo_query_prepare.py "VPN 怎么连" --scenario equipment_ops
# ============================================================================

"""演示追问改写、历史压缩和检索问题准备过程。

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

# typing.Literal: 字面量类型（RouteName = "direct_answer" | "retrieval"）
from typing import Literal

# HumanMessage: LangChain 标准人类消息类型
from langchain_core.messages import HumanMessage

# ── 路径设置 ──
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ── 导入核心 API ──
from qa_core.intent.classifier import IntentResult, classify_direct_intent, classify_intent
from qa_core.retrieval.strategy import build_retrieval_plan
from qa_core.scenarios.boundary import detect_source_boundary  # source 边界检测
from qa_core.scenarios.registry import ScenarioDefinition, resolve_scenario

RouteName = Literal["direct_answer", "retrieval"]


@dataclass(frozen=True)
class RoutePreview:
    """轻量路由预览 —— 与学习者查看的公共字段一致。

    Attributes:
        route: "direct_answer" | "retrieval"
        answer: 直答答案（retrieval 时为 None）
        intent: 意图分类结果（direct_answer 时由 classify_direct_intent 产出）
        reason: 路由原因码（如 "greeting"、"source_boundary"、"no_deterministic_route"）

    调用顺序：命令行入口 -> RoutePreview。
    """
    route: RouteName
    answer: str | None = None
    intent: IntentResult | None = None
    reason: str = ""


def parse_args() -> argparse.Namespace:
    """解析命令行参数。

    Returns:
        argparse.Namespace: 含 query、history、source_filter、scenario_id、plan_only

    调用顺序：命令行入口 -> parse_args()。
    """
    parser = argparse.ArgumentParser(description="Inspect route, intent and RetrievalPlan without executing retrieval.")
    parser.add_argument("query", help="User question")
    parser.add_argument("--history", action="append", default=[], help="Previous user/assistant message. Can be repeated.")
    parser.add_argument("--source", "--source-filter", dest="source_filter", help="Frontend-selected source filter.")
    parser.add_argument("--scenario", dest="scenario_id", help="Scenario id. Defaults to ACTIVE_SCENARIO_ID.")
    parser.add_argument("--plan-only", action="store_true", help="Kept for chapter 06 clarity; this script always stops at RetrievalPlan.")
    return parser.parse_args()


def message_history(items: list[str]) -> list[HumanMessage]:
    """将命令行历史字符串转为 LangChain HumanMessage 列表。

    过滤空字符串和纯空白字符串。

    调用顺序：命令行入口 -> message_history()。
    """
    return [HumanMessage(content=item.strip()) for item in items if item and item.strip()]


def validate_source_filter(source_filter: str | None, scenario: ScenarioDefinition) -> None:
    """当用户选择的 source 不在当前场景白名单中时快速失败。

    Args:
        source_filter: 用户选择的 source 过滤
        scenario: 当前场景定义

    Raises:
        ValueError: source_filter 不在 valid_sources 中

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
    """匹配 qa_core.pipeline.context.effective_source_filter 的逻辑。

    优先级：命令行 source_filter > intent 推断的 suggested_source > None
    只在 suggested_source 在白名单中时才使用。

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
    """返回与主 pipeline 相同的确定性 source-boundary 提示。

    当检测到用户问题更像其他 source 分类时，返回中文提示引导用户切换分类。

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
    """镜像主 pipeline 的确定性路由检查，但不执行 FAQ 快路径检索。

    路由决策顺序：
      1. 校验 source_filter 合法性
      2. classify_direct_intent() — 检查是否匹配直答规则（问候/转人工/越界）
      3. detect_source_boundary() — 检查 source 边界是否匹配
      4. 都不命中 → retrieval 路由

    调用顺序：命令行入口 -> decide_low_cost_route()。
    """
    validate_source_filter(source_filter, scenario)

    # 步骤 1：直答意图检查
    direct_intent = classify_direct_intent(query, scenario)
    if direct_intent:
        return (
            RoutePreview(
                route="direct_answer",
                answer=direct_intent.direct_answer,
                intent=direct_intent,
                reason=direct_intent.reason,
            ),
            {"reason": "not_checked_after_direct_answer"},
        )

    # 步骤 2：source 边界检查
    answer, boundary_payload = boundary_answer(query, scenario, source_filter)
    if answer:
        intent = IntentResult(
            intent="OUT_OF_SCOPE",
            direct_answer=answer,
            confidence=0.98,
            reason="source_boundary",
            requires_rewrite=False,
            suggested_source=None,
        )
        return RoutePreview(route="direct_answer", answer=answer, intent=intent, reason="source_boundary"), boundary_payload

    # 步骤 3：进入检索路由
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
    """解析命令行参数 → 路由决策 → 意图分类 → 检索计划 → 输出 JSON。

    执行流程：
      1. 解析参数 + 获取场景配置
      2. decide_low_cost_route() — 低成本路由判断
      3. 如果 route=retrieval：
         a. classify_intent() — 检索意图分类
         b. resolve_effective_source_filter() — 确定有效 source
         c. build_retrieval_plan() — 生成检索计划
      4. 如果 route=direct_answer → 跳过检索相关步骤
      5. 序列化为 JSON 并打印
    """
    args = parse_args()
    scenario = resolve_scenario(args.scenario_id)
    history = message_history(args.history)

    # 步骤 1：路由决策
    route, source_boundary = decide_low_cost_route(args.query, scenario, args.source_filter)

    intent = route.intent
    plan = None
    source_filter = None

    # 步骤 2：仅 retrieval 时执行后续分类和计划
    if route.route == "retrieval":
        intent = classify_intent(args.query, history, scenario)
        source_filter = resolve_effective_source_filter(args.source_filter, intent.suggested_source, scenario)
        plan = build_retrieval_plan(args.query, intent)

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
        # 以下字段为与第 07 章 demo_query_rewrite_variants.py 输出格式保持一致
        "rewritten_query": args.query if plan else None,
        "query_variants": None,
        "plan_only": True,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
