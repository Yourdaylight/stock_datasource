#!/usr/bin/env python3
"""
告警引擎 (Alert Engine)
========================

基于用户自定义策略配置（strategy_config.json）对实时 tick 数据进行条件匹配，
满足条件时触发告警通知。

设计原则：
  - 不生成买卖信号，只做条件匹配和告警
  - 策略完全由用户在 strategy_config.json 中定义
  - 支持纯实时字段条件（pct_chg / close / vol 等）
  - 支持 MCP 辅助数据（历史均量、N日高点等）作为计算依据
  - 告警冷却机制，避免重复轰炸
  - 支持控制台输出 + JSON 日志 + Webhook 推送（飞书/钉钉）
"""

import json
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, date, timedelta
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("alert-engine")

# ── 运算符映射 ──────────────────────────────────────────────────────────────
_OPS: Dict[str, Callable] = {
    ">":  lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<":  lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}

_SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_CONFIG = os.path.join(_SKILL_DIR, "strategy_config.json")


class AlertEngine:
    """
    告警引擎

    使用方式：
        engine = AlertEngine()
        engine.on_tick("00700.HK", tick_data)   # 每收到一条 tick 调用
    """

    def __init__(self, config_path: str = _DEFAULT_CONFIG):
        self._config_path = config_path
        self._config: Dict[str, Any] = {}
        self._strategies: List[Dict[str, Any]] = []
        self._global: Dict[str, Any] = {}

        # 告警冷却：{strategy_id + symbol: last_alert_timestamp}
        self._cooldown: Dict[str, float] = {}

        # MCP 辅助数据缓存：{symbol: {compute_key: value, _fetched_at: timestamp}}
        self._mcp_cache: Dict[str, Dict[str, Any]] = defaultdict(dict)
        # MCP 缓存有效期（秒），日线数据每天只需拉一次
        self._mcp_cache_ttl: int = 3600

        # 告警日志（内存）
        self._alert_log: List[Dict[str, Any]] = []

        # 外部 MCP 数据拉取回调（由 ai_agent_integration 注入）
        # 签名: fetch_fn(symbol, source, fields, lookback_days) -> Dict[str, Any]
        self._mcp_fetch_fn: Optional[Callable] = None

        self._load_config()

    # ── 配置加载 ────────────────────────────────────────────────────────────

    def _load_config(self) -> None:
        """加载策略配置文件"""
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                self._config = json.load(f)
            self._global = self._config.get("global", {})
            self._strategies = [
                s for s in self._config.get("strategies", [])
                if s.get("enabled", True)
            ]
            logger.info(f"告警引擎已加载 {len(self._strategies)} 条策略")
        except FileNotFoundError:
            logger.warning(f"策略配置文件不存在: {self._config_path}，使用空策略")
            self._strategies = []
        except json.JSONDecodeError as e:
            logger.error(f"策略配置文件解析失败: {e}")
            self._strategies = []

    def reload_config(self) -> None:
        """热重载策略配置（运行时更新策略无需重启）"""
        self._load_config()
        logger.info("策略配置已热重载")

    def set_mcp_fetch_fn(self, fn: Callable) -> None:
        """注入 MCP 数据拉取函数"""
        self._mcp_fetch_fn = fn

    # ── 核心入口 ────────────────────────────────────────────────────────────

    def on_tick(self, symbol: str, tick: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        处理一条实时 tick，返回本次触发的告警列表（空列表表示无告警）

        参数:
            symbol: 股票代码，如 "00700.HK"
            tick:   实时行情字典，包含 close/pct_chg/vol/amount 等字段
        返回:
            触发的告警列表，每条告警为 dict
        """
        triggered = []
        for strategy in self._strategies:
            # 检查该策略是否监控此 symbol
            if not self._symbol_matches(symbol, strategy):
                continue

            # 检查冷却
            cooldown_key = f"{strategy['id']}::{symbol}"
            cooldown_sec = strategy.get(
                "cooldown_seconds",
                self._global.get("alert_cooldown_seconds", 300)
            )
            last_alert = self._cooldown.get(cooldown_key, 0)
            if time.time() - last_alert < cooldown_sec:
                continue

            # 构建计算上下文（tick 字段 + MCP 辅助字段）
            ctx = self._build_context(symbol, tick, strategy)

            # 条件匹配
            if self._evaluate_conditions(strategy.get("conditions", {}), ctx):
                alert = self._fire_alert(symbol, tick, strategy, ctx)
                triggered.append(alert)
                self._cooldown[cooldown_key] = time.time()

        return triggered

    # ── 辅助方法 ────────────────────────────────────────────────────────────

    def _symbol_matches(self, symbol: str, strategy: Dict[str, Any]) -> bool:
        """判断策略是否适用于该 symbol"""
        syms = strategy.get("symbols", "*")
        if syms == "*":
            return True
        return symbol in syms

    def _build_context(
        self, symbol: str, tick: Dict[str, Any], strategy: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        构建条件评估上下文：
          - 直接来自 tick 的字段
          - 通过 MCP 辅助计算的衍生字段（如 vol_ratio / mcp_high_20d）
        """
        ctx: Dict[str, Any] = dict(tick)  # 复制 tick 字段

        mcp_assist = strategy.get("mcp_assist", {})
        if not mcp_assist.get("enabled", False):
            return ctx

        # 尝试从缓存或 MCP 获取辅助数据
        mcp_data = self._get_mcp_data(symbol, mcp_assist)
        if not mcp_data:
            return ctx

        compute = mcp_assist.get("compute", "")

        # avg_vol_5d → 计算 vol_ratio
        if compute == "avg_vol_5d":
            avg_vol = mcp_data.get("avg_vol_5d")
            if avg_vol and avg_vol > 0:
                ctx["mcp_avg_vol_5d"] = avg_vol
                cur_vol = float(tick.get("vol") or 0)
                ctx["vol_ratio"] = round(cur_vol / avg_vol, 2)

        # high_20d → 近20日最高价
        elif compute == "high_20d":
            high_20d = mcp_data.get("high_20d")
            if high_20d:
                ctx["mcp_high_20d"] = high_20d

        return ctx

    def _get_mcp_data(
        self, symbol: str, mcp_assist: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        获取 MCP 辅助数据（优先读缓存，缓存过期则重新拉取）
        """
        compute = mcp_assist.get("compute", "")
        cache_key = f"{symbol}::{compute}"
        cached = self._mcp_cache.get(cache_key, {})

        # 缓存有效
        if cached and time.time() - cached.get("_fetched_at", 0) < self._mcp_cache_ttl:
            return cached

        # 无注入函数，跳过
        if not self._mcp_fetch_fn:
            return None

        try:
            result = self._mcp_fetch_fn(
                symbol=symbol,
                source=mcp_assist.get("source", "tushare_daily"),
                fields=mcp_assist.get("fields", []),
                lookback_days=mcp_assist.get("lookback_days", 5),
                compute=compute,
            )
            if result:
                result["_fetched_at"] = time.time()
                self._mcp_cache[cache_key] = result
                return result
        except Exception as e:
            logger.warning(f"MCP 数据拉取失败 [{symbol}]: {e}")

        return None

    def _evaluate_conditions(
        self, conditions: Dict[str, Any], ctx: Dict[str, Any]
    ) -> bool:
        """
        评估条件组合

        conditions 格式:
            {
                "logic": "AND" | "OR",
                "items": [
                    {"field": "pct_chg", "op": ">=", "value": 9.5},
                    ...
                ]
            }
        """
        if not conditions:
            return False

        logic = conditions.get("logic", "AND").upper()
        items = conditions.get("items", [])

        if not items:
            return False

        results = []
        for item in items:
            field = item.get("field", "")
            op = item.get("op", ">=")
            value = item.get("value")

            # 从上下文取字段值
            field_val = ctx.get(field)
            if field_val is None:
                results.append(False)
                continue

            # value 可能是字符串（引用另一个上下文字段，如 "mcp_high_20d"）
            if isinstance(value, str):
                value = ctx.get(value)
                if value is None:
                    results.append(False)
                    continue

            try:
                op_fn = _OPS.get(op)
                if op_fn:
                    results.append(op_fn(float(field_val), float(value)))
                else:
                    logger.warning(f"未知运算符: {op}")
                    results.append(False)
            except (TypeError, ValueError):
                results.append(False)

        if logic == "OR":
            return any(results)
        else:  # AND
            return all(results)

    def _fire_alert(
        self,
        symbol: str,
        tick: Dict[str, Any],
        strategy: Dict[str, Any],
        ctx: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        触发告警：格式化消息、输出控制台、写日志、推送 Webhook
        """
        # 格式化告警消息
        try:
            msg = strategy.get("alert_message", "⚠️ {name}({ts_code}) 触发告警").format_map(
                defaultdict(lambda: "N/A", ctx)
            )
        except Exception:
            msg = f"⚠️ {symbol} 触发策略 [{strategy.get('name', '')}]"

        alert = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "strategy_id": strategy.get("id", ""),
            "strategy_name": strategy.get("name", ""),
            "symbol": symbol,
            "message": msg,
            "tick_snapshot": {
                k: tick.get(k)
                for k in ("ts_code", "name", "close", "pct_chg", "vol", "amount", "pre_close")
            },
            "ctx_extras": {
                k: v for k, v in ctx.items()
                if k not in tick and not k.startswith("_")
            },
        }

        # 控制台输出
        notify_cfg = self._global.get("notify", {})
        if notify_cfg.get("console", True):
            self._print_alert(alert)

        # 写 JSON 日志
        if notify_cfg.get("log_file", True):
            self._write_log(alert, notify_cfg.get("log_path", "alert_log.json"))

        # Webhook 推送
        webhook_cfg = notify_cfg.get("webhook", {})
        if webhook_cfg.get("enabled", False) and webhook_cfg.get("url"):
            self._send_webhook(webhook_cfg["url"], alert)

        self._alert_log.append(alert)
        return alert

    def _print_alert(self, alert: Dict[str, Any]) -> None:
        """控制台打印告警"""
        print(f"\n{'='*60}")
        print(f"🔔 告警  [{alert['time']}]  策略: {alert['strategy_name']}")
        print(f"   {alert['message']}")
        extras = alert.get("ctx_extras", {})
        if extras:
            extra_str = "  ".join(
                f"{k}={v:.2f}" if isinstance(v, float) else f"{k}={v}"
                for k, v in extras.items()
            )
            print(f"   辅助数据: {extra_str}")
        print(f"{'='*60}")

    def _write_log(self, alert: Dict[str, Any], log_path: str) -> None:
        """追加写入告警日志文件"""
        abs_path = log_path if os.path.isabs(log_path) else os.path.join(_SKILL_DIR, log_path)
        try:
            # 读取现有日志
            existing: List[Dict] = []
            if os.path.exists(abs_path):
                with open(abs_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            existing.append(alert)
            # 只保留最近 500 条
            if len(existing) > 500:
                existing = existing[-500:]
            with open(abs_path, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"写入告警日志失败: {e}")

    def _send_webhook(self, url: str, alert: Dict[str, Any]) -> None:
        """推送告警到飞书/钉钉 Webhook"""
        try:
            import requests
            payload = {
                "msg_type": "text",
                "content": {"text": alert["message"]},
            }
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            logger.warning(f"Webhook 推送失败: {e}")

    # ── 查询接口 ────────────────────────────────────────────────────────────

    def get_alert_log(self, symbol: Optional[str] = None, n: int = 20) -> List[Dict]:
        """获取最近 n 条告警记录（可按 symbol 过滤）"""
        logs = self._alert_log
        if symbol:
            logs = [a for a in logs if a["symbol"] == symbol]
        return logs[-n:]

    def get_active_strategies(self) -> List[Dict[str, Any]]:
        """返回当前已启用的策略列表（摘要）"""
        return [
            {
                "id": s.get("id"),
                "name": s.get("name"),
                "symbols": s.get("symbols"),
                "conditions_count": len(s.get("conditions", {}).get("items", [])),
                "mcp_assist": s.get("mcp_assist", {}).get("enabled", False),
                "cooldown_seconds": s.get("cooldown_seconds", 300),
            }
            for s in self._strategies
        ]

    def print_strategies_summary(self) -> None:
        """打印当前策略摘要"""
        strategies = self.get_active_strategies()
        print(f"\n{'='*55}")
        print(f"📋 当前已启用告警策略（共 {len(strategies)} 条）")
        print(f"{'='*55}")
        for s in strategies:
            mcp_tag = " [MCP辅助]" if s["mcp_assist"] else ""
            syms = s["symbols"] if isinstance(s["symbols"], str) else ", ".join(s["symbols"])
            print(f"  [{s['id']}] {s['name']}{mcp_tag}")
            print(f"       标的: {syms}")
            print(f"       条件数: {s['conditions_count']}  冷却: {s['cooldown_seconds']}s")
        print(f"{'='*55}\n")
