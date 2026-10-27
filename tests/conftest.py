"""Pytest 运行时隔离配置。"""

from __future__ import annotations

import os

from qa_core.config.settings import get_settings


os.environ["CACHE_ENABLED"] = "false"
get_settings.cache_clear()
