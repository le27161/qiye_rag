# -*- coding: utf-8 -*-
"""新环境 Docker 部署后一键验收。

该脚本用于 V1 发布包落到一台新机器后的完整验收：基础设施启动、API 镜像构建、
知识库初始化、API 启动、发布门禁、接口冒烟和缓存冒烟。它只编排真实命令，不做服务桩。

用法示例：
    python scripts/verify_fresh_docker_deploy.py
    python scripts/verify_fresh_docker_deploy.py --skip-init --evaluation-limit 2 --performance-limit 2
    python scripts/verify_fresh_docker_deploy.py --base-url http://192.168.88.100:8000
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.common import (
    CommandStepResult,
    PROJECT_ROOT,
    configure_utf8_stdio,
    run_command_step,
    utc_now,
    write_json_file,
)


DEFAULT_OUTPUT = PROJECT_ROOT / "reports" / "verification" / "v1_fresh_docker_acceptance.json"
DEFAULT_RELEASE_OUTPUT = "reports/verification/v1_fresh_docker_release.json"
DEFAULT_BASE_IMAGE = "localhost/knowforge-rag-platform-base:py312"


def project_path(path: str | Path) -> Path:
    """把命令行路径解析为项目内绝对路径。"""
    candidate = Path(path)
    return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate


def read_env_file(path: str | Path) -> dict[str, str]:
    """读取 docker compose env 文件中的 KEY=VALUE。"""
    env_path = project_path(path)
    values: dict[str, str] = {}
    if not env_path.exists():
        raise FileNotFoundError(f"{env_path} 不存在，请先从 .env.compose.example 复制并填写。")
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def compose_command(env_file: str, *args: str) -> list[str]:
    """生成 docker compose 命令。"""
    return ["docker", "compose", "--env-file", env_file, *args]


def python_command(*args: str) -> list[str]:
    """生成当前 Python 解释器命令。"""
    return [sys.executable, *args]


def default_base_url(env_values: dict[str, str]) -> str:
    """根据 API_PORT 推导本机访问地址。"""
    return f"http://127.0.0.1:{env_values.get('API_PORT') or '8000'}"


def run_and_record(
    results: list[CommandStepResult],
    name: str,
    command: list[str],
    *,
    keep_going: bool,
) -> bool:
    """执行一步命令，失败时按 keep_going 决定是否继续。"""
    result = run_command_step(name, command)
    results.append(result)
    return bool(result.ok or keep_going)


def run_acceptance(args: argparse.Namespace) -> dict:
    """执行新环境 Docker 验收并返回报告。"""
    env_path = project_path(args.env_file)
    env_values = read_env_file(env_path)
    os.environ["ENV_FILE"] = str(env_path)
    os.environ.setdefault("PYTHONUTF8", "1")

    for directory in ("logs", "reports"):
        (PROJECT_ROOT / directory).mkdir(parents=True, exist_ok=True)

    base_url = args.base_url or default_base_url(env_values)
    admin_token = args.admin_token or env_values.get("ADMIN_API_TOKEN") or ""
    results: list[CommandStepResult] = []

    step_specs: list[tuple[str, list[str]]] = [
        ("docker_compose_config", compose_command(args.env_file, "config", "--quiet")),
        ("docker_infra_up", compose_command(args.env_file, "up", "-d", "mysql", "redis", "etcd", "minio", "milvus")),
    ]
    for name, command in step_specs:
        if not run_and_record(results, name, command, keep_going=args.keep_going):
            return build_report(args, base_url, results)

    inspect = run_command_step("docker_base_image_inspect", ["docker", "image", "inspect", args.base_image])
    if inspect.ok:
        results.append(inspect)
    elif not args.skip_base_build:
        if not run_and_record(
            results,
            "docker_base_image_build",
            ["docker", "build", "-f", "Dockerfile.base", "-t", args.base_image, "."],
            keep_going=args.keep_going,
        ):
            return build_report(args, base_url, results)
    elif args.skip_base_build:
        results.append(inspect)
        if args.keep_going:
            pass
        else:
            return build_report(args, base_url, results)
    if results and not results[-1].ok and not args.keep_going:
        return build_report(args, base_url, results)

    if not args.skip_api_build:
        if not run_and_record(results, "docker_api_build", compose_command(args.env_file, "build", "api"), keep_going=args.keep_going):
            return build_report(args, base_url, results)

    if not args.skip_init:
        if args.active_scenario_only:
            scenario = env_values.get("ACTIVE_SCENARIO_ID") or "enterprise_knowledge"
            init_command = compose_command(
                args.env_file,
                "run",
                "--rm",
                "api",
                "python",
                "scripts/rebuild_kb_version.py",
                "--scenario",
                scenario,
                "--new-version",
                "--force",
                "--quality-gate",
                "--activate",
            )
            init_name = "docker_init_active_scenario"
        else:
            init_command = compose_command(
                args.env_file,
                "run",
                "--rm",
                "api",
                "python",
                "scripts/rebuild_scenarios.py",
                "--reset-collections",
                "--description",
                "fresh docker init all scenarios",
            )
            init_name = "docker_init_all_scenarios"
        if not run_and_record(results, init_name, init_command, keep_going=args.keep_going):
            return build_report(args, base_url, results)

    for name, command in [
        ("docker_api_up", compose_command(args.env_file, "up", "-d", "api")),
        ("docker_compose_ps", compose_command(args.env_file, "ps")),
        (
            "v1_release_verification",
            python_command(
                "scripts/verify_v1_release.py",
                "--include-evaluation",
                "--include-performance",
                "--include-docker",
                "--evaluation-limit",
                str(args.evaluation_limit),
                "--performance-limit",
                str(args.performance_limit),
                "--output",
                args.release_output,
            ),
        ),
        (
            "api_acceptance_smoke",
            python_command("scripts/acceptance_smoke.py", "--base-url", base_url, "--admin-token", admin_token),
        ),
        (
            "api_e2e_smoke",
            python_command("scripts/api_e2e_smoke.py", "--base-url", base_url, "--admin-token", admin_token),
        ),
    ]:
        if not run_and_record(results, name, command, keep_going=args.keep_going):
            return build_report(args, base_url, results)

    if not args.skip_cache_smoke:
        run_and_record(
            results,
            "cache_acceptance_smoke",
            python_command("scripts/cache_acceptance_smoke.py", "--base-url", base_url, "--admin-token", admin_token),
            keep_going=args.keep_going,
        )
    return build_report(args, base_url, results)


def build_report(args: argparse.Namespace, base_url: str, results: list[CommandStepResult]) -> dict:
    """生成新环境验收报告。"""
    return {
        "report_type": "v1_fresh_docker_acceptance",
        "created_at": utc_now(),
        "ok": all(step.ok for step in results),
        "env_file": str(project_path(args.env_file)),
        "base_url": base_url,
        "release_output": args.release_output,
        "evaluation_limit": int(args.evaluation_limit),
        "performance_limit": int(args.performance_limit),
        "step_count": len(results),
        "steps": [
            {
                "name": step.name,
                "ok": step.ok,
                "returncode": step.returncode,
                "elapsed_ms": step.elapsed_ms,
                "command": step.command,
                "stdout_preview": step.stdout_preview,
                "stderr_preview": step.stderr_preview,
            }
            for step in results
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数。"""
    parser = argparse.ArgumentParser(description="Run fresh Docker deployment acceptance for V1.")
    parser.add_argument("--env-file", default=".env.compose", help="docker compose env 文件。")
    parser.add_argument("--base-url", default="", help="API 访问地址；为空时按 API_PORT 推导。")
    parser.add_argument("--admin-token", default="", help="管理令牌；为空时从 env 文件读取。")
    parser.add_argument("--base-image", default=DEFAULT_BASE_IMAGE, help="API 基础镜像名称。")
    parser.add_argument("--skip-base-build", action="store_true", help="基础镜像不存在时也不构建。")
    parser.add_argument("--skip-api-build", action="store_true", help="跳过 API 镜像构建。")
    parser.add_argument("--skip-init", action="store_true", help="跳过知识库初始化。")
    parser.add_argument("--active-scenario-only", action="store_true", help="只初始化 ACTIVE_SCENARIO_ID 指定场景。")
    parser.add_argument("--skip-cache-smoke", action="store_true", help="跳过 Redis 缓存验收。")
    parser.add_argument("--keep-going", action="store_true", help="某一步失败后继续执行后续步骤并汇总报告。")
    parser.add_argument("--evaluation-limit", type=int, default=3, help="发布验收评测样本数量。")
    parser.add_argument("--performance-limit", type=int, default=3, help="发布验收性能样本数量。")
    parser.add_argument("--release-output", default=DEFAULT_RELEASE_OUTPUT, help="verify_v1_release 输出报告路径。")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="新环境验收总报告路径。")
    return parser


def main() -> int:
    """命令行入口。"""
    configure_utf8_stdio()
    args = build_parser().parse_args()
    report = run_acceptance(args)
    output_path = project_path(args.output)
    write_json_file(output_path, report)
    print(f"新环境 Docker 验收报告已写入：{output_path}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
