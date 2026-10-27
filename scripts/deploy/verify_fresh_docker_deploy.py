# -*- coding: utf-8 -*-
"""新环境 Docker 部署后一键验收。

该脚本用于 V1 发布包落到一台新机器后的完整验收：基础设施启动、API 镜像构建、
知识库初始化、API 启动、发布门禁、接口冒烟和缓存冒烟。它只编排真实命令，不做服务桩。

用法示例：
    python scripts/deploy/verify_fresh_docker_deploy.py
    python scripts/deploy/verify_fresh_docker_deploy.py --skip-init --evaluation-limit 2 --performance-limit 2
    python scripts/deploy/verify_fresh_docker_deploy.py --base-url http://192.168.88.100:8000
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

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
    """把命令行路径解析为项目内绝对路径。

    参数：
        path: 命令行传入的路径；绝对路径原样返回，相对路径按项目根目录拼接。

    返回：
        解析后的 Path 对象。

    调用顺序：read_env_file() / run_acceptance() / main() -> project_path()。
    """
    candidate = Path(path)
    return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate


def read_env_file(path: str | Path) -> dict[str, str]:
    """读取 docker compose env 文件中的 KEY=VALUE。

    支持 # 注释行、空行和带引号的值（引号会被剥掉）。

    参数：
        path: env 文件路径（字符串或 Path 对象）。

    返回：
        键值对字典。

    异常：
        FileNotFoundError: env 文件不存在，需先从 .env.compose.example 复制填写。

    调用顺序：run_acceptance() -> project_path() -> read_env_file()。
    """
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
    """生成 docker compose 命令。

    统一追加 --env-file，保证所有 compose 子命令使用同一份环境配置。

    参数：
        env_file: docker compose env 文件路径。
        *args: 任意数量子命令及参数，例如 ("config", "--quiet")。

    返回：
        完整命令列表，可直接交给 run_command_step() 执行。

    调用顺序：run_acceptance() -> compose_command()。
    """
    return ["docker", "compose", "--env-file", env_file, *args]


def python_command(*args: str) -> list[str]:
    """生成当前 Python 解释器命令。

    参数：
        *args: 脚本路径及其参数。

    返回：
        以 sys.executable 开头的完整命令列表。

    调用顺序：run_acceptance() -> python_command()。
    """
    return [sys.executable, *args]


def default_base_url(env_values: dict[str, str]) -> str:
    """根据 API_PORT 推导本机访问地址。

    参数：
        env_values: read_env_file() 读出的环境变量字典。

    返回：
        形如 http://127.0.0.1:{API_PORT} 的本机地址；缺省端口时使用 8000。

    调用顺序：run_acceptance() -> default_base_url()。
    """
    return f"http://127.0.0.1:{env_values.get('API_PORT') or '8000'}"


def run_and_record(
    results: list[CommandStepResult],
    name: str,
    command: list[str],
    *,
    keep_going: bool,
) -> bool:
    """执行一步命令，失败时按 keep_going 决定是否继续。

    返回值表达“是否可以继续”而非“是否成功”：keep_going 开启时即使失败也返回
    True，让主流程继续收集后续步骤结果。

    参数：
        results: 步骤结果列表，执行结果会追加进去。
        name: 步骤名称。
        command: 要执行的命令列表。
        keep_going: 失败后是否继续后续步骤。

    返回：
        True 表示可以继续执行后续步骤；False 表示应立即结束验收。

    调用顺序：run_acceptance() -> run_and_record() -> run_command_step()。
    """
    result = run_command_step(name, command)
    results.append(result)
    return bool(result.ok or keep_going)


def run_acceptance(args: argparse.Namespace) -> dict:
    """执行新环境 Docker 验收并返回报告。（★★★ 核心）

    编排顺序：基础设施启动 -> 基础镜像检查/构建 -> API 镜像构建 -> 知识库初始化 ->
    API 启动 -> 发布门禁 -> 接口冒烟 -> 缓存冒烟；任何一步失败都会按 keep_going
    决定是提前结束还是继续汇总。

    参数：
        args: 解析后的命令行参数（env_file / base_url / admin_token / base_image /
            skip_base_build / skip_api_build / skip_init / active_scenario_only /
            skip_cache_smoke / keep_going / evaluation_limit / performance_limit /
            release_output）。

    返回：
        验收报告字典（结构见 build_report()），供 main() 写入 JSON 文件。

    调用顺序：main() -> run_acceptance() -> read_env_file() / run_and_record() / build_report()。
    """
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

    # 基础镜像分支策略：已存在则跳过构建；缺失时按 --skip-base-build 决定是构建还是记录失败。
    inspect = run_command_step("docker_base_image_inspect", ["docker", "image", "inspect", args.base_image])
    if inspect.ok:
        # 原因：镜像已存在，直接采纳 inspect 结果，避免重复构建浪费时间。
        results.append(inspect)
    elif not args.skip_base_build:
        # 原因：镜像缺失且未禁止构建 —— 就地构建基础镜像；失败且未开 keep_going 时提前结束。
        if not run_and_record(
            results,
            "docker_base_image_build",
            ["docker", "build", "-f", "Dockerfile.base", "-t", args.base_image, "."],
            keep_going=args.keep_going,
        ):
            return build_report(args, base_url, results)
    elif args.skip_base_build:
        # 原因：镜像缺失且用户显式 --skip-base-build —— 把失败的 inspect 记入结果以体现失败；
        # keep_going 时继续后续步骤以便汇总，否则立即结束。
        results.append(inspect)
        if args.keep_going:
            pass
        else:
            return build_report(args, base_url, results)
    # 原因：兜底检查 —— 无论走哪个分支，最近一步失败且未开 keep_going 就提前结束，
    # 防止未来新增分支时遗漏“失败即中止”的路径。
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
            python_command("scripts/quality/cache_acceptance_smoke.py", "--base-url", base_url, "--admin-token", admin_token),
            keep_going=args.keep_going,
        )
    return build_report(args, base_url, results)


def build_report(args: argparse.Namespace, base_url: str, results: list[CommandStepResult]) -> dict:
    """生成新环境验收报告。

    汇总全部步骤结果，ok 取所有步骤的与运算；步骤明细按 name / ok / returncode /
    elapsed_ms / command / 输出预览展开，方便发布门禁和人工排查。

    参数：
        args: 命令行参数（env_file / release_output / evaluation_limit / performance_limit）。
        base_url: 本次验收使用的 API 访问地址。
        results: 全部步骤结果列表。

    返回：
        可直接 JSON 序列化的验收报告字典。

    调用顺序：run_acceptance() -> build_report()；main() 只负责写入文件。
    """
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
    """构造命令行参数。

    参数：
        无。

    返回：
        配置好全部验收开关与样本数量参数的 ArgumentParser。

    调用顺序：main() -> build_parser()。
    """
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
    """命令行入口。

    参数：
        无（参数由 build_parser() 解析）。

    返回：
        0 表示验收通过；1 表示报告中存在失败步骤。

    调用顺序：命令行入口 -> main() -> build_parser() -> run_acceptance() -> write_json_file()。
    """
    configure_utf8_stdio()
    args = build_parser().parse_args()
    report = run_acceptance(args)
    output_path = project_path(args.output)
    write_json_file(output_path, report)
    print(f"新环境 Docker 验收报告已写入：{output_path}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
