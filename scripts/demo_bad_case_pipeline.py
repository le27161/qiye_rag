# -*- coding: utf-8 -*-
"""Bad Case 沉淀闭环最小端到端演示（讲义第 16 章第五部分 5.4 / 5.5 / 5.6 / 5.8）。

演示不依赖 Milvus / MySQL / LLM，只调用四个核心函数：
  1. select_bad_cases()                ← 5.4 自动识别：从评测报告筛出失败样本
  2. build_feedback_bad_case()          ← 5.5 复核草稿：把用户点踩反馈导出为待补字段样本
  3. build_plan()                       ← 5.6 合并回归：把草稿合并进正式 eval_sets
  4. evaluate_report_against_gate()     ← 5.8 Gate 阻断：阈值判断决定放行/阻断发布

跑法：
  python scripts/demo_bad_case_pipeline.py
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from pathlib import Path

from scripts.extract_bad_cases_from_report import select_bad_cases
from scripts.export_feedback_bad_cases import build_feedback_bad_case
from scripts.promote_bad_cases_to_regression import build_plan
from scripts.quality.check_ingestion_quality_gate import (
    IngestionQualityThresholds,
    evaluate_report_against_gate,
)


def _print_section(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def main() -> None:
    # ───────────────────────────────────────────────────────────────
    # 步骤 1：构造一份伪造的评测报告
    # 模拟讲义 5.1 的 VPN 案例：系统答案漏了三个子项，keyword_coverage 偏低
    # 同时放一条通过样本，验证 select_bad_cases 不会误抓
    # ───────────────────────────────────────────────────────────────
    _print_section("步骤 1：构造伪造的评测报告（模拟讲义 5.1 VPN 案例）")

    fake_report = {
        "dataset": "eval_sets/multi_scenario_smoke.json",
        "rows": [
            {
                "case_id": "case_vpn_001",
                "question": "VPN 客户端版本、账号锁定、公网 IP 这些排查项分别应该怎么处理？",
                "scenario_id": "enterprise_knowledge",
                "source_filter": "it",
                "expected_source_contains": ["it_support.md", "VPN 连接排查"],
                "expected_keywords": ["客户端版本", "账号锁定", "公网 IP", "IT 工单", "截图"],
                "source_recall_hit": True,
                "hit_type_matched": True,
                "source_inference_matched": True,
                "prompt_profile_matched": True,
                "keyword_coverage": 0.4,  # 只覆盖了 2/5 关键词
            },
            {
                "case_id": "case_ok_reimburse",
                "question": "报销要准备哪些材料？",
                "expected_keywords": ["发票", "审批"],
                "source_recall_hit": True,
                "hit_type_matched": True,
                "source_inference_matched": True,
                "prompt_profile_matched": True,
                "keyword_coverage": 1.0,  # 全覆盖，应该被跳过
            },
        ],
    }
    print(f"报告中样本数: {len(fake_report['rows'])}")
    print(f"  - VPN 案例  : keyword_coverage=0.4（应被筛出）")
    print(f"  - 报销案例  : keyword_coverage=1.0（应被跳过）")

    # ───────────────────────────────────────────────────────────────
    # 步骤 2：调用 select_bad_cases 筛出失败样本（讲义 5.4 自动识别）
    # 这一步演示：脚本只挑疑似异常，不判定真值
    # ───────────────────────────────────────────────────────────────
    _print_section("步骤 2：调用 select_bad_cases 筛出失败样本（5.4 自动识别）")

    bad_cases = select_bad_cases(
        fake_report,
        min_keyword_coverage=0.8,  # 讲义默认阈值
        max_items=0,
    )
    print(f"筛出的 Bad Case 数: {len(bad_cases)}（通过样本被正确跳过）")
    print("\n筛出的 Bad Case 完整内容:")
    print(json.dumps(bad_cases, ensure_ascii=False, indent=2))

    # ───────────────────────────────────────────────────────────────
    # 步骤 3：构造一条用户点踩反馈（讲义 5.5 复核草稿上游）
    # 演示：用户点踩不是评测真值，只导出草稿，需要人工补 expected_*
    # ───────────────────────────────────────────────────────────────
    _print_section("步骤 3：把用户点踩反馈导出为复核草稿（5.5 复核草稿）")

    feedback_row = {
        "id": 42,
        "session_id": "session-demo",
        "scenario_id": "enterprise_knowledge",
        "tenant_id": "default",
        "dataset_id": "default",
        "question": "VPN 连不上应该怎么处理？",
        "answer": "请联系管理员。",
        "rating": "not_useful",
        "comment": "没有给出排障步骤",
        "sources": [
            {
                "content": "VPN 故障排查资料片段",
                "metadata": {
                    "source": "it",
                    "file_name": "vpn_troubleshooting.pdf",
                    "standard_question": "VPN 连不上怎么处理？",
                },
            }
        ],
        "created_at": "2026-08-06T21:00:00+08:00",
    }
    feedback_bad_case = build_feedback_bad_case(feedback_row)
    print("导出的复核草稿（注意 expected_* 还没填，grading_notes 提示要人工补）:")
    print(json.dumps(feedback_bad_case, ensure_ascii=False, indent=2))

    # ───────────────────────────────────────────────────────────────
    # 步骤 4：把复核后的草稿合并进正式回归集（讲义 5.6 合并回归）
    # 用 dry_run=True 演示，不实际写入文件
    # ───────────────────────────────────────────────────────────────
    _print_section("步骤 4：把复核后的 Bad Case 合并进正式回归集（5.6 dry_run 演示）")

    # 用绝对路径(基于脚本位置)避免依赖当前工作目录,
    # 因为 promote_bad_cases_to_regression.build_plan 内部 project_path() 按 PROJECT_ROOT
    # 拼接相对路径,如果当前工作目录 != PROJECT_ROOT 会找不到文件
    project_root = Path(__file__).resolve().parents[1]
    tmp_source = project_root / ".workbuddy" / "demo_local_bad_cases.json"
    tmp_target = project_root / ".workbuddy" / "demo_regression.json"
    tmp_output = project_root / ".workbuddy" / "demo_regression_merged.json"

    tmp_source.parent.mkdir(parents=True, exist_ok=True)
    tmp_source.write_text(
        json.dumps(
            [
                {
                    "case_id": "bad_case_vpn_001",
                    "source_case_id": "case_vpn_001",
                    "query": "VPN 客户端版本、账号锁定、公网 IP 这些排查项分别应该怎么处理？",
                    "scenario_id": "enterprise_knowledge",
                    "source_filter": "it",
                    "expected_hit_type": "rag",
                    "expected_effective_source": "it",
                    "expected_prompt_profile": "troubleshooting_steps",
                    "expected_source_contains": ["it_support.md", "VPN 连接排查"],
                    "expected_keywords": ["客户端版本", "账号锁定", "公网 IP", "IT 工单", "截图"],
                    "grading_notes": "答案必须分别说明三个排查项，不能只给泛泛重启建议。",
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    tmp_target.write_text(
        json.dumps(
            [
                {
                    "case_id": "case_vpn_001",
                    "query": "旧版本样本（待替换）",
                    "scenario_id": "enterprise_knowledge",
                    "expected_keywords": ["旧"],
                },
                {
                    "case_id": "case_keep",
                    "query": "保留样本",
                    "scenario_id": "enterprise_knowledge",
                    "expected_keywords": ["保留"],
                },
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    plan = build_plan(
        SimpleNamespace(
            source=str(tmp_source),
            target=str(tmp_target),
            output=str(tmp_output),
            conflict="replace",
            dry_run=False,
        )
    )
    print("合并计划（注意 stats 显示 replaced=1，trace 通过 bad_case_id 保留）:")
    plan_display = {k: v for k, v in plan.items() if k != "merged_cases"}
    print(json.dumps(plan_display, ensure_ascii=False, indent=2))
    print("\n合并后回归集前两条:")
    merged = json.loads(tmp_output.read_text(encoding="utf-8"))
    for case in merged[:2]:
        print(f"  - case_id={case.get('case_id')}, bad_case_id={case.get('bad_case_id')}, "
              f"query={case.get('query')[:30]}...")

    # 清理临时文件
    for p in [tmp_source, tmp_target, tmp_output]:
        if p.exists():
            p.unlink()

    # ───────────────────────────────────────────────────────────────
    # 步骤 5：Gate 判定演示（讲义 5.8 这条 Bad Case 如何影响 Gate）
    # 用入库质量 Gate 演示"阈值判断 → 失败则阻断发布"的核心概念
    # 构造两份对照报告：A 有问题（应阻断） / B 干净（应放行）
    # ───────────────────────────────────────────────────────────────
    _print_section("步骤 5：Gate 判定演示（5.8 阈值判断决定放行/阻断）")

    # 默认严格阈值：所有 max_* = 0，任何问题 > 0 都阻断
    strict_thresholds = IngestionQualityThresholds()

    # 报告 A：模拟"有 1 个文件解析失败 + 1 个低质量 chunk"
    # 对应真实场景：知识库候选版本里 PDF 损坏 + chunk 切分出乱码
    report_a = {
        "scenario_id": "enterprise_knowledge",
        "kb_version": "kb_demo_problem_version",
        "embedding_model_version": "bge-m3-local-v1",
        "reranker_model_version": "bge-reranker-large-local-v1",
        "chunk_schema_version": "parent_child_validity_v2",
        "failed_files_count": 1,          # 1 个解析失败 → 超 max_failed_files=0
        "unsupported_files_count": 0,
        "empty_files_count": 0,
        "ocr_risk_files_count": 0,
        "image_risk_files_count": 0,
        "image_risk_blocking_files_count": 0,
        "chunk_quality": {
            "low_quality_issue_count": 1,  # 1 个低质量 chunk → 超 max_low_quality_issues=0
            "duplicate_chunk_count": 0,
        },
        "faq_quality": {
            "exists": True,
            "empty_question_rows": [],
            "empty_answer_rows": [],
            "duplicate_questions": [],
            "invalid_sources": [],
        },
        "faq_document_conflicts": {"conflict_count": 0},
    }

    # 报告 B：模拟"全部干净"，对应 Bad Case 已修复后的状态
    report_b = {
        "scenario_id": "enterprise_knowledge",
        "kb_version": "kb_demo_clean_version",
        "embedding_model_version": "bge-m3-local-v1",
        "reranker_model_version": "bge-reranker-large-local-v1",
        "chunk_schema_version": "parent_child_validity_v2",
        "failed_files_count": 0,
        "unsupported_files_count": 0,
        "empty_files_count": 0,
        "ocr_risk_files_count": 0,
        "image_risk_files_count": 0,
        "image_risk_blocking_files_count": 0,
        "chunk_quality": {
            "low_quality_issue_count": 0,
            "duplicate_chunk_count": 0,
        },
        "faq_quality": {
            "exists": True,
            "empty_question_rows": [],
            "empty_answer_rows": [],
            "duplicate_questions": [],
            "invalid_sources": [],
        },
        "faq_document_conflicts": {"conflict_count": 0},
    }

    print("默认严格阈值：所有 max_* = 0（任何问题 > 0 都阻断）\n")

    print("【报告 A】有 1 个解析失败 + 1 个低质量 chunk（模拟未修复的 Bad Case）:")
    gate_a = evaluate_report_against_gate(report_a, strict_thresholds)
    print(f"  ok = {gate_a['ok']}                    ← 阻断发布")
    print(f"  failures 数 = {len(gate_a['failures'])}")
    for failure in gate_a["failures"]:
        threshold = failure.get("threshold", "（必填项缺失）")
        print(f"    - {failure['metric']}: actual={failure['actual']}, threshold={threshold}")
        print(f"      {failure['message']}")

    print("\n【报告 B】全部 0（模拟 Bad Case 修复后）:")
    gate_b = evaluate_report_against_gate(report_b, strict_thresholds)
    print(f"  ok = {gate_b['ok']}                     ← 放行发布")
    print(f"  failures 数 = {len(gate_b['failures'])}")
    print("  （无失败项，Gate 通过，可以激活版本）")

    print("\n教学要点：")
    print("  - 报告 A 的 failures 非空 → ok=False → rebuild_kb_version.py 不会激活版本 → 旧 active 继续")
    print("  - 报告 B 的 failures 为空 → ok=True → 激活版本 → 线上切换到新版本")
    print("  - 这就是 Bad Case 沉淀的最终价值：修复前 Gate 阻断，修复后 Gate 放行")

    _print_section("闭环演示完成")
    print("5.4 自动识别 → 5.5 复核草稿 → 5.6 合并回归 → 5.8 Gate 阻断/放行")
    print("详细命令见 docs/16-quality-evaluation.md 第 5.3 节最小可执行命令链")


if __name__ == "__main__":
    main()
