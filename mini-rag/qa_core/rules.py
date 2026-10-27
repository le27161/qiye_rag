"""Mini RAG 规则配置模块 — 从 TOML 文件加载查询变体规则。

规则配置来源：
  mini-rag/config/rules.toml

规则的作用：
  查询变体规则用于在检索前对用户问题进行同义扩展，提高召回率。
  Mini RAG 只保留规则层替换，不调用 LLM 扩展规则未覆盖的新词。

规则结构：
  [query_variants]
    short_structured_max_chars   — 短结构化问题的最大字符数阈值
    short_structured_markers     — 短结构化问题的标记词列表
    replacements                — 一组替换规则，每条规则包含：
      - when_any / when_all       — 触发条件（查询中包含哪些词）
      - replace                  — 替换对列表 [["原词", "替换词"], ...]
      - ignore_case              — 是否忽略大小写

数据类层次：
  RuleConfig
    └── QueryVariantRules
          └── QueryVariantReplacementRule (多个)
"""

from __future__ import annotations

import re

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # Python 3.8-3.10
    import tomli as tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from qa_core.config import PROJECT_ROOT

DEFAULT_RULE_CONFIG_PATH = PROJECT_ROOT / "config" / "rules.toml"


@dataclass(frozen=True)
class QueryVariantReplacementRule:
    """一条查询变体替换规则 — 定义在什么条件下对查询进行何种替换。

    触发条件：
      - when_any：查询中包含任意一个词时触发（OR 逻辑）
      - when_all：查询中包含所有词时触发（AND 逻辑）

    替换规则：
      - replacements：一组 (原词, 替换词) 对，依次执行 str.replace
      - ignore_case：替换时是否忽略大小写

    例如：
      when_any = ["报销"]
      replace = [["报销", "费用报销"], ["报销", "报销流程"]]
      → "报销怎么走" → "费用报销怎么走"（第一条替换）
      → "报销怎么走" → "报销流程怎么走"（第二条替换）
      → 最终生成 2 个查询变体

    Args:
        when_any:     任意匹配词列表（OR 语义）
        when_all:     全部匹配词列表（AND 语义）
        replacements: 替换对列表，每对格式为 (原词, 替换词)
        ignore_case:  是否忽略大小写（默认 False）

    调用顺序：mini-rag 流程 -> QueryVariantReplacementRule。
    """

    when_any: tuple[str, ...]
    when_all: tuple[str, ...]
    replacements: tuple[tuple[str, str], ...]
    ignore_case: bool = False

    def matches(self, query: str) -> bool:
        """判断当前查询是否匹配此规则的触发条件。

        匹配逻辑：
          1. 如果没有 when_any 和 when_all → 不匹配
          2. when_any 条件：查询需包含其中至少一个词
          3. when_all 条件：查询需包含其中所有词
          4. 两个条件同时存在时需都满足

        大小写处理：
          如果 ignore_case=True，匹配前将查询和条件词都转为小写。

        Args:
            query: 用户查询文本

        Returns:
            是否匹配触发条件

        调用顺序：mini-rag 流程 -> QueryVariantReplacementRule.matches()。
        """
        source = query.lower() if self.ignore_case else query
        any_terms = tuple(item.lower() for item in self.when_any) if self.ignore_case else self.when_any
        all_terms = tuple(item.lower() for item in self.when_all) if self.ignore_case else self.when_all
        if any_terms and not any(term in source for term in any_terms):
            return False
        if all_terms and not all(term in source for term in all_terms):
            return False
        return bool(any_terms or all_terms)


@dataclass(frozen=True)
class QueryVariantRules:
    """查询变体规则集合 — 包含短结构化问题判断和替换规则列表。

    两个功能：
      1. 判断短结构化问题：根据长度和标记词确定用户问题是否
         为简短的专有名词查询（如 "VPN 连接"、"报销流程"）
      2. 生成查询变体：对匹配替换规则的查询进行同义扩展

    Attributes:
        short_structured_max_chars: 短结构化问题的最大字符数
        short_structured_markers:   短结构化问题的标记词
        replacements:               替换规则列表

    调用顺序：mini-rag 流程 -> QueryVariantRules。
    """

    short_structured_max_chars: int
    short_structured_markers: tuple[str, ...]
    replacements: tuple[QueryVariantReplacementRule, ...]

    def is_short_structured_question(self, query: str) -> bool:
        """判断是否为短结构化问题。

        短结构化问题通常是指那些长度较短、包含特定标记词的查询，
        如 "VPN 连接"、"报销流程"、"加班怎么算" 等。
        这类问题不需要追问改写，可以直接检索。

        Args:
            query: 用户查询文本

        Returns:
            True 如果是短结构化问题，False 否则

        调用顺序：mini-rag 流程 -> QueryVariantRules.is_short_structured_question()。
        """
        compact = query.strip()
        if not compact or len(compact) > self.short_structured_max_chars:
            return False
        return any(marker in compact for marker in self.short_structured_markers)


@dataclass(frozen=True)
class RuleConfig:
    """Mini RAG 规则配置的根数据类。

    当前只包含 query_variants 一个属性，
    未来可以扩展其他规则类型（如意图识别规则）。

    Attributes:
        query_variants: 查询变体规则集合

    调用顺序：mini-rag 流程 -> RuleConfig。
    """

    query_variants: QueryVariantRules


@lru_cache(maxsize=1)
def get_rule_config(path: str | Path | None = None) -> RuleConfig:
    """读取并缓存 rules.toml 规则配置文件。

    读取流程：
      1. 确定配置路径（默认 DEFAULT_RULE_CONFIG_PATH）
      2. 解析 TOML 文件
      3. 调用 _load_query_variant_rules 解析规则结构
      4. 返回 RuleConfig 对象

    使用 lru_cache 保证进程内只解析一次，
    避免每次检索都重新读取磁盘文件。

    Args:
        path: 可选的规则文件路径，未指定时使用 DEFAULT_RULE_CONFIG_PATH

    Returns:
        解析后的 RuleConfig 对象

    Raises:
        FileNotFoundError: rules.toml 文件不存在
        tomllib.TOMLDecodeError: TOML 格式解析失败
        ValueError: 配置项校验失败（如缺失必填字段）

    调用顺序：mini-rag 流程 -> get_rule_config()。
    """
    config_path = Path(path) if path else DEFAULT_RULE_CONFIG_PATH
    if not config_path.is_absolute():
        config_path = PROJECT_ROOT / config_path
    payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
    return RuleConfig(query_variants=_load_query_variant_rules(payload, config_path))


def _load_query_variant_rules(payload: dict, config_path: Path) -> QueryVariantRules:
    """从 TOML 解析结果中提取查询变体规则集合。

    严格校验以下必填字段：
      - short_structured_max_chars > 0
      - short_structured_markers 非空
      - replacements 非空

    任何校验不通过都会抛出 ValueError，明确提示出错的配置文件和字段。

    Args:
        payload:     TOML 解析后的完整配置字典
        config_path: 配置文件路径（用于错误提示）

    Returns:
        解析后的 QueryVariantRules 对象

    Raises:
        ValueError: 必填字段缺失或校验失败

    调用顺序：mini-rag 流程 -> _load_query_variant_rules()。
    """
    variant_payload = dict(payload.get("query_variants") or {})
    max_chars = int(variant_payload.get("short_structured_max_chars") or 0)
    markers = _clean_tuple(variant_payload.get("short_structured_markers", ()))
    replacements = tuple(
        _parse_replacement_rule(item, config_path)
        for item in variant_payload.get("replacements", ())
    )
    if max_chars <= 0:
        raise ValueError(f"query_variants.short_structured_max_chars 必须大于 0：{config_path}")
    if not markers:
        raise ValueError(f"query_variants.short_structured_markers 不能为空：{config_path}")
    if not replacements:
        raise ValueError(f"query_variants.replacements 不能为空：{config_path}")
    return QueryVariantRules(
        short_structured_max_chars=max_chars,
        short_structured_markers=markers,
        replacements=replacements,
    )


def _parse_replacement_rule(payload: dict, config_path: Path) -> QueryVariantReplacementRule:
    """将 TOML 中的单条替换规则解析为 QueryVariantReplacementRule。

    校验逻辑：
      - 必须配置 when_any 或 when_all（至少一个非空）
      - 必须配置 replace（至少一对有效替换）
      - 每对 replace 必须是长度为 2 的列表，且原词和替换词均非空

    Args:
        payload:     TOML 中单条替换规则的原始字典
        config_path: 配置文件路径（用于错误提示）

    Returns:
        解析后的 QueryVariantReplacementRule 对象

    Raises:
        ValueError: 规则校验失败

    调用顺序：mini-rag 流程 -> _parse_replacement_rule()。
    """
    rule_payload = dict(payload or {})
    when_any = _clean_tuple(rule_payload.get("when_any", ()))
    when_all = _clean_tuple(rule_payload.get("when_all", ()))
    replacements = tuple(
        (str(pair[0]).strip(), str(pair[1]).strip())
        for pair in rule_payload.get("replace", ())
        if isinstance(pair, (list, tuple)) and len(pair) == 2 and str(pair[0]).strip() and str(pair[1]).strip()
    )
    if not when_any and not when_all:
        raise ValueError(f"query_variants.replacements 中每条规则必须配置 when_any 或 when_all：{config_path}")
    if not replacements:
        raise ValueError(f"query_variants.replacements 中每条规则必须配置 replace：{config_path}")
    return QueryVariantReplacementRule(
        when_any=when_any,
        when_all=when_all,
        replacements=replacements,
        ignore_case=bool(rule_payload.get("ignore_case", False)),
    )


def _clean_tuple(items: object) -> tuple[str, ...]:
    """将 TOML 解析后的原始值转换为去空白、去空字符串元组。

    用于统一清洗 when_any、when_all、short_structured_markers 等
    规则配置中的字符串数组字段。

    处理逻辑：
      1. None 或空值 → 返回空元组 ()
      2. 每个元素转为字符串并去除首尾空格
      3. 自动过滤空字符串元素

    Args:
        items: TOML 解析后的原始值（通常是 list 或 tuple）

    Returns:
        清洗后的字符串元组

    调用顺序：mini-rag 流程 -> _clean_tuple()。
    """
    return tuple(str(item).strip() for item in items or () if str(item).strip())
