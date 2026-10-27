# -*- coding: utf-8 -*-
# ============================================================================
# 本地服务真实链路验收脚本
# ============================================================================
# 该脚本假设 FastAPI 服务已经启动，例如：
#   python -m uvicorn app:app --host 127.0.0.1 --port 8000
#
# 它不再使用服务桩、假 QAService 或内存替身，而是通过 HTTP/WebSocket 访问真实服务。
# 因此它会验证当前项目是否真正通电：
#   1. 健康检查（/health）          — 服务是否存活 + active 场景
#   2. 场景列表（/api/scenarios）   — 是否能返回场景配置
#   3. 首页（/）                    — 页面是否包含 KnowForge RAG Platform 标识
#   4. 管理页（/admin）             — 状态页是否可访问
#   5. LangSmith 状态（/api/admin/langsmith） — 可观测性状态
#   6. WebSocket 流式问答（/api/stream）      — 核心功能闭环验证
#      - 检查 start / token / end 事件
#
# 每个检查项返回布尔值，最终 ok=all(checks) 为总通过条件。
# 返回非零退出码表示验收失败（CI/CD 可据此判断构建状态）。
#
# 用法示例：
#   python scripts\acceptance_smoke.py
#   python scripts\acceptance_smoke.py --base-url http://192.168.1.100:8000 --admin-token my-token
#
# 输出格式：缩进美化的 JSON，包含 report_type、ok、checks、
# active_scenario_id、websocket_event_types
# ============================================================================

"""执行 V1 部署后的 HTTP、WebSocket 与治理接口冒烟验收。

调用顺序：课程示例、测试或命令行入口 -> 本模块公开接口。
"""

from __future__ import annotations

# argparse: 命令行参数解析（--base-url, --admin-token, --query 等）
import argparse

# json: 标准 JSON 序列化
import json

# sys: 系统功能（sys.path 修改 + sys.exit 退出码）
import sys

# time: 时间相关功能（time.monotonic 用于 WebSocket 超时控制）
import time

# pathlib.Path: 文件路径操作
from pathlib import Path

# urllib: HTTP 请求（用于访问 REST API 接口）
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

# websocket: WebSocket 客户端（用于测试流式问答）
import websocket

# ── 路径设置 ──
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# ── 导入核心模块 ──
from qa_core.config.settings import get_settings  # 读取运行配置（含 ADMIN_API_TOKEN）
from scripts.common import configure_utf8_stdio, write_optional_json  # UTF-8 输出 + 可选 JSON 写入


def http_json(base_url: str, path: str, token: str = "") -> dict:
    """读取 JSON 接口，失败时抛出带路径的异常。

    用于访问 /health、/api/scenarios、/api/admin/langsmith 等 JSON 接口。
    超时 10 秒，避免长时间等待。

    Args:
        base_url: 服务根 URL（如 http://127.0.0.1:8000）
        path: API 路径（如 /health）
        token: 管理令牌（用于需要认证的管理接口）

    Returns:
        解析后的 JSON dict

    Raises:
        RuntimeError: HTTP 错误、URL 错误或超时

    调用顺序：命令行入口 -> http_json()。
    """
    req = urlrequest.Request(base_url.rstrip("/") + path, headers=_headers(token))
    try:
        with urlrequest.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"HTTP check failed: {path}: {exc}") from exc


def http_text(base_url: str, path: str) -> str:
    """读取文本页面，确认页面可访问。

    用于验证首页和管理页是否能正常返回 HTML。

    Args:
        base_url: 服务根 URL
        path: 页面路径（如 / 或 /admin）

    Returns:
        页面文本内容

    调用顺序：命令行入口 -> http_text()。
    """
    req = urlrequest.Request(base_url.rstrip("/") + path)
    try:
        with urlrequest.urlopen(req, timeout=10) as response:
            return response.read().decode("utf-8", errors="ignore")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"Page check failed: {path}: {exc}") from exc


def websocket_events(
    base_url: str,
    token: str = "",
    query: str = "新人入职流程怎么走",
    scenario_id: str = "enterprise_knowledge",
    max_events: int = 1000,
    max_seconds: float = 180.0,
) -> list[dict]:
    """连接真实 WebSocket 服务并收集一次问答事件。

    这里要求 `websocket-client` 依赖已经安装。它不会 monkey patch 应用对象，
    也不会绕过 MySQL、Milvus、LLM 或本地模型，因此可以作为"核心功能是否闭环"的验收入口。

    流程：
      1. 根据 base_url 的 scheme 确定 ws:// 或 wss://
      2. 建立 WebSocket 连接到 /api/stream
      3. 发送 JSON payload（query、session_id、scenario_id）
      4. 循环接收事件直到收到 "end" 或 "error" 或超时
      5. 返回收集到的事件列表

    Args:
        base_url: HTTP 服务根 URL（自动转为 ws/wss）
        token: 管理令牌
        query: 测试问题
        scenario_id: 场景 ID
        max_events: 最多接收的事件数（防无限循环）
        max_seconds: 最多等待秒数（超时保护）

    Returns:
        SSE 事件列表（每个事件是一个 dict）

    Raises:
        RuntimeError: WebSocket 返回 error 事件或超时未收到 end

    调用顺序：命令行入口 -> websocket_events()。
    """
    parsed = urlparse(base_url.rstrip("/"))
    scheme = "wss" if parsed.scheme == "https" else "ws"
    ws_url = f"{scheme}://{parsed.netloc}/api/stream"
    headers = [f"X-Admin-Token: {token}"] if token else []
    ws = websocket.create_connection(ws_url, timeout=90, header=headers)
    try:
        ws.send(
            json.dumps(
                {
                    "query": query,
                    "session_id": "acceptance-smoke-session",
                    "scenario_id": scenario_id,
                },
                ensure_ascii=False,
            )
        )
        events: list[dict] = []
        deadline = time.monotonic() + max_seconds
        while len(events) < max_events and time.monotonic() < deadline:
            event = json.loads(ws.recv())
            events.append(event)
            if event.get("type") == "error":
                raise RuntimeError(f"WebSocket returned error: {event.get('error')}")
            if event.get("type") == "end":
                return events
        raise RuntimeError(f"WebSocket did not finish, received {len(events)} events")
    finally:
        ws.close()


def _headers(token: str) -> dict[str, str]:
    """构造管理令牌 header。

    X-Admin-Token 是所有管理接口的统一认证头。
    为空时跳过，因为部分接口（如 /health）不需要认证。

    调用顺序：命令行入口 -> _headers()。
    """
    return {"X-Admin-Token": token} if token else {}


def resolve_admin_token(raw_token: str | None) -> str:
    """解析本次验收使用的管理令牌。

    管理接口已经要求强令牌保护，但验收脚本不应该要求每次手动复制令牌：
    - 命令行显式传入时优先使用，方便临时验收远端环境；
    - 未传入时读取当前运行配置的 `ADMIN_API_TOKEN`，保持本地和容器内一键验收体验；
    - 返回报告只展示验收结果，不展示令牌本身，避免敏感信息进入日志。

    调用顺序：命令行入口 -> resolve_admin_token()。
    """
    return (raw_token or get_settings().admin_api_token or "").strip()


def main() -> None:
    """执行真实服务验收并打印 JSON 摘要。

    执行流程：
      1. 设置 UTF-8 输出
      2. 解析命令行参数
      3. 解析管理令牌
      4. 依次执行 6 项检查（health / scenarios / page / admin / langsmith / websocket）
      5. 汇总检查结果，输出 JSON
      6. 如有失败项，返回非零退出码
    """
    configure_utf8_stdio()

    # ── 构建参数解析器 ──
    parser = argparse.ArgumentParser(description="Run real acceptance smoke checks against the FastAPI service.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--admin-token", default="", help="为空时自动读取当前运行配置中的 ADMIN_API_TOKEN。")
    parser.add_argument("--query", default="新人入职流程怎么走")
    parser.add_argument("--scenario", default="enterprise_knowledge", help="Scenario id used by the WebSocket smoke query.")
    parser.add_argument("--max-events", type=int, default=1000, help="最多接收的 WebSocket 事件数量。")
    parser.add_argument("--max-seconds", type=float, default=180.0, help="最多等待 WebSocket end 事件的秒数。")
    parser.add_argument("--output", default="", help="可选 JSON 报告输出路径。")
    args = parser.parse_args()
    admin_token = resolve_admin_token(args.admin_token)

    # ── 执行 6 项检查 ──
    checks: dict[str, object] = {}

    # 1. 健康检查
    health = http_json(args.base_url, "/health")
    # 2. 场景列表
    scenarios = http_json(args.base_url, "/api/scenarios")
    # 3. 首页
    page = http_text(args.base_url, "/")
    # 4. 管理页
    admin = http_text(args.base_url, "/admin")
    # 5. LangSmith 状态
    langsmith = http_json(args.base_url, "/api/admin/langsmith", admin_token)
    # 6. WebSocket 流式问答
    events = websocket_events(args.base_url, admin_token, args.query, args.scenario, args.max_events, args.max_seconds)
    event_types = [event.get("type") for event in events]

    # ── 汇总检查结果 ──
    checks["health"] = health.get("status") == "healthy"
    checks["scenarios"] = bool(scenarios.get("scenarios"))
    checks["page"] = "KnowForge RAG Platform" in page
    checks["admin_page"] = "KnowForge 状态页" in admin
    checks["admin_langsmith"] = "enabled" in langsmith and "project" in langsmith
    checks["websocket_events"] = "start" in event_types and "token" in event_types and "end" in event_types

    ok = all(bool(value) for value in checks.values())
    payload = {
        "report_type": "acceptance_smoke",
        "ok": ok,
        "base_url": args.base_url,
        "checks": checks,
        "active_scenario_id": health.get("active_scenario_id"),
        "smoke_scenario_id": args.scenario,
        "websocket_event_types": event_types,
    }
    write_optional_json(args.output, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    # 当脚本直接运行时（python acceptance_smoke.py），__name__ == "__main__"
    # 当作为模块导入时（import acceptance_smoke），__name__ == "acceptance_smoke"
    main()
