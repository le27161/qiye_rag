"""
评估或调用第 05 章的 BERT 检索意图模型服务。

该脚本提供两个功能：
    1. 评估模式：在默认评测样本上运行 BERT 意图分类器，输出准确率等指标
    2. 预测模式：对单个查询进行分类，输出预测标签和置信度

使用方式：
    # 仅评估模型准确率
    python scripts/demo_intent_model.py --eval-only

    # 对单个查询进行分类
    python scripts/demo_intent_model.py "IT 设备采购流程怎么走"

    # 对追问类查询进行分类
    python scripts/demo_intent_model.py "那第二种方案呢" --has-history

    # 输出治理报告
    python scripts/demo_intent_model.py --output latest
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from qa_core.intent.governance import INTENT_MODEL_LATEST_REPORT, build_intent_model_report  # noqa: E402
from qa_core.intent.model_classifier import (  # noqa: E402
    DEFAULT_EVAL_EXAMPLES,
    BertIntentModelService,
)
from scripts.common import write_json_file  # noqa: E402


def main() -> None:
    """CLI 入口：加载 BERT 意图模型，执行评估和/或预测。

    执行流程：
        1. 从配置加载 BertIntentModelService（含本地微调模型权重）
        2. 在 DEFAULT_EVAL_EXAMPLES 上运行评估
        3. 如果提供了 query 参数且非 eval-only 模式，执行单条预测
        4. 根据 --output 参数可选输出治理报告
        5. 以 JSON 格式打印结果
    """
    parser = argparse.ArgumentParser(description="Evaluate or call the BERT retrieval-intent model service.")
    parser.add_argument("query", nargs="?", default=None, help="Optional query to classify.")
    parser.add_argument("--has-history", action="store_true", help="Mark the query as a history-dependent follow-up.")
    parser.add_argument("--eval-only", action="store_true", help="Only print validation metrics.")
    parser.add_argument(
        "--output",
        default="",
        help=f"Optional governance report output path. Use --output latest to write {INTENT_MODEL_LATEST_REPORT}.",
    )
    args = parser.parse_args()

    # 从配置加载 BERT 意图模型服务（含本地微调权重）
    service = BertIntentModelService.from_settings()
    # 在默认评测集上运行评估
    evaluation = service.evaluate(DEFAULT_EVAL_EXAMPLES)
    payload: dict[str, object] = {
        "model": service.model_version,
        "model_path": str(service.model_path),
        "labels": list(service.labels),
        "evaluation": evaluation.as_dict(),
        "usage_note": "the V1 online pipeline calls this BERT intent model service inside the intent-decision gateway",
    }

    # 如果用户提供了具体查询，执行单条分类预测
    if args.query and not args.eval_only:
        prediction = service.predict(args.query, has_history=args.has_history)
        payload["prediction"] = {
            "query": args.query,
            "has_history": args.has_history,
            **prediction.as_dict(),
        }

    # 可选：输出治理报告到指定路径
    if args.output:
        output_path = INTENT_MODEL_LATEST_REPORT if args.output == "latest" else Path(args.output)
        report = build_intent_model_report(evaluate=True)
        payload["governance_report"] = write_json_file(output_path, report)

    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
