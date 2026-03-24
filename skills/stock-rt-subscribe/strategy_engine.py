#!/usr/bin/env python3
"""
交易策略引擎
============
基于实时 tick 数据，计算技术指标并生成交易信号。

设计原则：
  - 每只股票独立维护价格历史和信号状态
  - 支持多种策略模式：trend（趋势跟踪）、mean_reversion（均值回归）、combined（综合）
  - 信号冷却期：避免在同一价位重复发出相同信号
  - trading_log.json：持久化历史信号，Agent 重启后可恢复上下文
  - 风险控制：最大亏损/盈利阈值，连续信号次数限制

使用示例:
    from strategy_engine import StrategyEngine

    engine = StrategyEngine()
    engine.on_tick("600519.SH", tick_dict)   # 每收到一条 tick 调用
    result = engine.get_latest_signal("600519.SH")
    print(result)  # {"signal": "BUY", "price": 1680.0, "reasons": [...]}
"""

import json
import logging
import math
import os
import time
from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional, Tuple

logger = logging.getLogger("strategy-engine")

_SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
_CONFIG_PATH = os.path.join(_SKILL_DIR, "strategy_config.json")
_LOG_PATH = os.path.join(_SKILL_DIR, "trading_log.json")

# 信号常量
SIGNAL_BUY = "BUY"
SIGNAL_SELL = "SELL"
SIGNAL_HOLD = "HOLD"


# ── 技术指标计算 ──────────────────────────────────────────────

def _sma(prices: List[float], period: int) -> Optional[float]:
    """简单移动平均"""
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period


def _ema(prices: List[float], period: int) -> Optional[float]:
    """指数移动平均（递推公式）"""
    if len(prices) < period:
        return None
    k = 2.0 / (period + 1)
    ema = sum(prices[:period]) / period
    for p in prices[period:]:
        ema = p * k + ema * (1 - k)
    return ema


def _rsi(prices: List[float], period: int = 14) -> Optional[float]:
    """相对强弱指数 RSI"""
    if len(prices) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(prices)):
        delta = prices[i] - prices[i - 1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))
    # 取最近 period 个
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9
          ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    MACD 指标（递推 EMA，O(n) 复杂度）
    返回: (macd_line, signal_line, histogram)
    """
    if len(prices) < slow + signal:
        return None, None, None

    k_fast = 2.0 / (fast + 1)
    k_slow = 2.0 / (slow + 1)
    k_sig = 2.0 / (signal + 1)

    # 用前 slow 个价格初始化 EMA
    ema_f = sum(prices[:fast]) / fast
    ema_s = sum(prices[:slow]) / slow

    # 从第 slow 个价格开始递推，同时构建 MACD 序列
    macd_series: List[float] = []
    for i, p in enumerate(prices):
        if i < slow:
            if i >= fast:
                ema_f = p * k_fast + ema_f * (1 - k_fast)
            continue
        ema_f = p * k_fast + ema_f * (1 - k_fast)
        ema_s = p * k_slow + ema_s * (1 - k_slow)
        macd_series.append(ema_f - ema_s)

    if len(macd_series) < signal:
        return None, None, None

    macd_line = macd_series[-1]

    # 用 MACD 序列的前 signal 个初始化 signal EMA
    sig_ema = sum(macd_series[:signal]) / signal
    for m in macd_series[signal:]:
        sig_ema = m * k_sig + sig_ema * (1 - k_sig)

    signal_line = sig_ema
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _bollinger(prices: List[float], period: int = 20, std_mult: float = 2.0
               ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    布林带
    返回: (upper, middle, lower)
    """
    if len(prices) < period:
        return None, None, None
    window = prices[-period:]
    middle = sum(window) / period
    variance = sum((p - middle) ** 2 for p in window) / period
    std = math.sqrt(variance)
    return middle + std_mult * std, middle, middle - std_mult * std


# ── 日内策略指标计算 ──────────────────────────────────────────

def _open_deviation(current_price: float, open_price: float) -> Optional[float]:
    """
    开盘价偏离率
    返回: 当前价相对开盘价的涨跌幅（百分比），第一个 tick 即可使用
    """
    if open_price <= 0:
        return None
    return (current_price - open_price) / open_price * 100


def _vwap(ticks: List[Dict[str, Any]]) -> Optional[float]:
    """
    日内 VWAP（成交量加权平均价）
    返回: VWAP 价格，至少需要 1 条 tick
    """
    total_value = 0.0
    total_volume = 0.0
    for t in ticks:
        price = float(t.get("close") or 0)
        volume = float(t.get("volume") or 0)
        if price > 0 and volume > 0:
            total_value += price * volume
            total_volume += volume
    if total_volume <= 0:
        return None
    return total_value / total_volume


def _intraday_high_low(ticks: List[Dict[str, Any]]) -> Tuple[Optional[float], Optional[float]]:
    """
    日内最高价和最低价
    返回: (intraday_high, intraday_low)
    """
    if not ticks:
        return None, None
    highs = [float(t.get("high") or t.get("close") or 0) for t in ticks if float(t.get("high") or t.get("close") or 0) > 0]
    lows = [float(t.get("low") or t.get("close") or 0) for t in ticks if float(t.get("low") or t.get("close") or 0) > 0]
    if not highs or not lows:
        return None, None
    return max(highs), min(lows)


def _volume_spike(ticks: List[Dict[str, Any]], spike_mult: float = 3.0) -> Tuple[Optional[float], Optional[float]]:
    """
    量价异动检测
    返回: (当前成交量, 日内均量)，调用方判断是否异动
    """
    if len(ticks) < 2:
        return None, None
    volumes = [float(t.get("volume") or 0) for t in ticks]
    current_vol = volumes[-1]
    avg_vol = sum(volumes[:-1]) / len(volumes[:-1]) if len(volumes) > 1 else 0
    if avg_vol <= 0:
        return current_vol, None
    return current_vol, avg_vol


def _limit_proximity(current_price: float, up_limit: float, down_limit: float
                     ) -> Tuple[Optional[float], Optional[float]]:
    """
    涨跌停接近度
    返回: (距涨停百分比, 距跌停百分比)，正值表示还有空间，负值表示已超过
    """
    if up_limit <= 0 or down_limit <= 0 or current_price <= 0:
        return None, None
    up_dist = (up_limit - current_price) / current_price * 100
    down_dist = (current_price - down_limit) / current_price * 100
    return up_dist, down_dist


# ── 策略配置加载 ──────────────────────────────────────────────

def _load_config() -> Dict[str, Any]:
    """加载策略配置文件"""
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("加载策略配置失败，使用默认配置: %s", e)
        return {}


def _get_symbol_config(config: Dict[str, Any], symbol: str) -> Dict[str, Any]:
    """获取某只股票的完整配置（合并 default + symbol 级别）"""
    default = config.get("default", {})
    symbol_cfg = config.get("symbols", {}).get(symbol, {})
    # 深度合并：symbol 级别覆盖 default
    merged = {**default}
    for k, v in symbol_cfg.items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k] = {**merged[k], **v}
        else:
            merged[k] = v
    return merged


# ── 交易日志（Agent 记忆） ─────────────────────────────────────

class TradingLog:
    """
    持久化交易信号日志（trading_log.json）
    Agent 重启后可读取历史信号，避免重复发出相同信号
    """

    def __init__(self, log_path: str = _LOG_PATH):
        self._path = log_path
        self._data: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._load()

    def _load(self) -> None:
        """从文件加载历史日志"""
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for symbol, records in raw.items():
                self._data[symbol] = records
            logger.info("加载交易日志: %d 只股票的历史信号", len(self._data))
        except Exception as e:
            logger.warning("加载交易日志失败: %s", e)

    def _save(self) -> None:
        """保存日志到文件"""
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(dict(self._data), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("保存交易日志失败: %s", e)

    def append(self, symbol: str, signal: str, price: float,
               reasons: List[str], indicators: Dict[str, Any]) -> None:
        """记录一条信号"""
        record = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "signal": signal,
            "price": round(price, 3),
            "reasons": reasons,
            "indicators": {k: round(v, 4) if isinstance(v, float) else v
                           for k, v in indicators.items() if v is not None},
        }
        self._data[symbol].append(record)
        # 每只股票最多保留 200 条
        if len(self._data[symbol]) > 200:
            self._data[symbol] = self._data[symbol][-200:]
        self._save()

    def get_last(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取某只股票最近一条信号记录"""
        records = self._data.get(symbol, [])
        return records[-1] if records else None

    def get_history(self, symbol: str, n: int = 10) -> List[Dict[str, Any]]:
        """获取某只股票最近 n 条信号记录"""
        return self._data.get(symbol, [])[-n:]

    def get_all_summary(self) -> Dict[str, Any]:
        """获取所有股票的信号摘要"""
        summary = {}
        for symbol, records in self._data.items():
            if not records:
                continue
            last = records[-1]
            buy_count = sum(1 for r in records if r["signal"] == SIGNAL_BUY)
            sell_count = sum(1 for r in records if r["signal"] == SIGNAL_SELL)
            summary[symbol] = {
                "last_signal": last["signal"],
                "last_price": last["price"],
                "last_time": last["time"],
                "total_signals": len(records),
                "buy_count": buy_count,
                "sell_count": sell_count,
            }
        return summary


# ── 策略引擎核心 ──────────────────────────────────────────────

class StrategyEngine:
    """
    交易策略引擎

    每只股票独立维护：
      - 价格历史队列（最多保留 max_history 条）
      - 最近信号状态（用于冷却期判断）
      - 连续信号计数（风险控制）

    信号生成流程：
      1. 计算技术指标（MA/RSI/MACD/BOLL）
      2. 根据策略模式生成候选信号
      3. 冷却期检查（避免频繁重复信号）
      4. 风险控制检查（最大亏损/盈利/连续信号）
      5. 写入 trading_log.json（Agent 记忆）
      6. 触发通知回调
    """

    def __init__(self, config_path: str = _CONFIG_PATH, log_path: str = _LOG_PATH,
                 max_history: int = 200):
        self._config = _load_config()
        self._log = TradingLog(log_path)
        self._max_history = max_history

        # 每只股票的价格历史 {symbol: deque([price, ...])}
        self._price_history: Dict[str, Deque[float]] = defaultdict(
            lambda: deque(maxlen=max_history)
        )
        # 每只股票的完整 tick 历史 {symbol: deque([tick_dict, ...])}
        self._tick_history: Dict[str, Deque[Dict[str, Any]]] = defaultdict(
            lambda: deque(maxlen=max_history)
        )
        # 最近一次信号时间戳 {symbol: timestamp}
        self._last_signal_time: Dict[str, float] = {}
        # 最近一次信号类型 {symbol: signal}
        self._last_signal_type: Dict[str, str] = {}
        # 连续相同信号计数 {symbol: count}
        self._consecutive_count: Dict[str, int] = defaultdict(int)
        # 最新信号结果缓存 {symbol: result_dict}
        self._latest_signals: Dict[str, Dict[str, Any]] = {}

        # 通知回调列表
        self._notify_callbacks: List[Any] = []

        logger.info("策略引擎初始化完成，配置文件: %s", config_path)

    def add_notify_callback(self, callback) -> None:
        """注册通知回调，callback(symbol, result) 在信号生成时触发"""
        self._notify_callbacks.append(callback)

    def on_tick(self, symbol: str, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        处理一条 tick 数据，返回信号结果（无信号时返回 None）

        参数:
            symbol: 股票代码
            tick: tick 数据字典，需包含 close 字段
        返回:
            {signal, price, reasons, indicators, symbol, time} 或 None
        """
        price = float(tick.get("close") or 0)
        if price <= 0:
            return None

        self._price_history[symbol].append(price)
        self._tick_history[symbol].append(tick)

        cfg = _get_symbol_config(self._config, symbol)
        min_points = cfg.get("min_data_points", 20)
        ticks = list(self._tick_history[symbol])
        prices = list(self._price_history[symbol])

        # 日内策略：从第 1 个 tick 就可以运行，不受 min_data_points 限制
        intraday_result = self._generate_intraday_signal(symbol, ticks, price, cfg)
        if intraday_result and intraday_result["signal"] != SIGNAL_HOLD:
            self._latest_signals[symbol] = intraday_result
            self._log.append(
                symbol, intraday_result["signal"], intraday_result["price"],
                intraday_result["reasons"], intraday_result["indicators"]
            )
            for cb in self._notify_callbacks:
                try:
                    cb(symbol, intraday_result)
                except Exception as e:
                    logger.error("通知回调异常: %s", e)
            return intraday_result

        # 传统技术指标策略：需要足够的历史数据
        if len(prices) < min_points:
            return None

        result = self._generate_signal(symbol, prices, price, cfg)

        if result and result["signal"] != SIGNAL_HOLD:
            self._latest_signals[symbol] = result
            # 写入记忆日志
            self._log.append(
                symbol, result["signal"], result["price"],
                result["reasons"], result["indicators"]
            )
            # 触发通知
            for cb in self._notify_callbacks:
                try:
                    cb(symbol, result)
                except Exception as e:
                    logger.error("通知回调异常: %s", e)

        return result if result and result["signal"] != SIGNAL_HOLD else None

    def _generate_intraday_signal(self, symbol: str, ticks: List[Dict[str, Any]],
                                   current_price: float, cfg: Dict[str, Any]
                                   ) -> Optional[Dict[str, Any]]:
        """
        日内策略信号生成（从第 1 个 tick 即可运行）

        包含5种日内策略：
          1. 开盘价偏离策略：价格偏离开盘价超过阈值
          2. VWAP 策略：价格相对 VWAP 的位置
          3. 日内高低点突破：突破当日最高/最低价
          4. 量价异动：成交量突然放大
          5. 涨跌停接近预警：价格接近涨停/跌停
        """
        if not ticks:
            return None

        intraday_cfg = cfg.get("intraday", {})
        if not intraday_cfg.get("enabled", True):
            return None

        first_tick = ticks[0]
        open_price = float(first_tick.get("open") or current_price)
        up_limit = float(ticks[-1].get("up_limit") or 0)
        down_limit = float(ticks[-1].get("down_limit") or 0)

        buy_votes, sell_votes = 0, 0
        reasons: List[str] = []
        indicators: Dict[str, Any] = {}

        # ── 策略1：开盘价偏离 ──
        open_dev_threshold = intraday_cfg.get("open_deviation_threshold", 3.0)
        deviation = _open_deviation(current_price, open_price)
        if deviation is not None:
            indicators["open_deviation_pct"] = round(deviation, 3)
            indicators["open_price"] = open_price
            if deviation >= open_dev_threshold:
                sell_votes += 2
                reasons.append(f"开盘偏离+{deviation:.2f}%（>{open_dev_threshold}%），强势后回调风险")
            elif deviation <= -open_dev_threshold:
                buy_votes += 2
                reasons.append(f"开盘偏离{deviation:.2f}%（<-{open_dev_threshold}%），超跌反弹机会")

        # ── 策略2：VWAP ──
        vwap_val = _vwap(ticks)
        if vwap_val is not None:
            indicators["vwap"] = round(vwap_val, 3)
            vwap_dev = (current_price - vwap_val) / vwap_val * 100
            indicators["vwap_deviation_pct"] = round(vwap_dev, 3)
            vwap_threshold = intraday_cfg.get("vwap_deviation_threshold", 1.5)
            if current_price > vwap_val * (1 + vwap_threshold / 100):
                sell_votes += 1
                reasons.append(f"价格({current_price:.2f})高于VWAP({vwap_val:.2f}) +{vwap_dev:.2f}%，超买")
            elif current_price < vwap_val * (1 - vwap_threshold / 100):
                buy_votes += 1
                reasons.append(f"价格({current_price:.2f})低于VWAP({vwap_val:.2f}) {vwap_dev:.2f}%，超卖")

        # ── 策略3：日内高低点突破 ──
        if len(ticks) >= 2:
            # 用除最后一条 tick 之外的历史来确定高低点，避免自我参照
            intraday_high, intraday_low = _intraday_high_low(ticks[:-1])
            if intraday_high is not None and intraday_low is not None:
                indicators["intraday_high"] = round(intraday_high, 3)
                indicators["intraday_low"] = round(intraday_low, 3)
                if current_price > intraday_high:
                    buy_votes += 2
                    reasons.append(f"突破日内最高价({intraday_high:.2f})，上行动能强")
                elif current_price < intraday_low:
                    sell_votes += 2
                    reasons.append(f"跌破日内最低价({intraday_low:.2f})，下行动能强")

        # ── 策略4：量价异动 ──
        if len(ticks) >= 3:
            current_vol, avg_vol = _volume_spike(ticks)
            if current_vol is not None and avg_vol is not None and avg_vol > 0:
                indicators["current_volume"] = current_vol
                indicators["avg_volume"] = round(avg_vol, 1)
                spike_mult = intraday_cfg.get("volume_spike_multiplier", 3.0)
                vol_ratio = current_vol / avg_vol
                indicators["volume_ratio"] = round(vol_ratio, 2)
                if vol_ratio >= spike_mult:
                    # 量价配合：放量上涨买入，放量下跌卖出
                    if current_price >= (ticks[-2].get("close") or current_price):
                        buy_votes += 2
                        reasons.append(f"放量上涨（量比{vol_ratio:.1f}x），主力买入信号")
                    else:
                        sell_votes += 2
                        reasons.append(f"放量下跌（量比{vol_ratio:.1f}x），主力出货信号")

        # ── 策略5：涨跌停接近预警 ──
        if up_limit > 0 and down_limit > 0:
            up_dist, down_dist = _limit_proximity(current_price, up_limit, down_limit)
            if up_dist is not None and down_dist is not None:
                indicators["up_limit"] = up_limit
                indicators["down_limit"] = down_limit
                indicators["up_limit_dist_pct"] = round(up_dist, 3)
                indicators["down_limit_dist_pct"] = round(down_dist, 3)
                limit_alert_pct = intraday_cfg.get("limit_alert_pct", 1.0)
                if 0 <= up_dist <= limit_alert_pct:
                    buy_votes += 3
                    reasons.append(f"接近涨停({up_limit:.2f})，距离{up_dist:.2f}%，强势信号")
                elif 0 <= down_dist <= limit_alert_pct:
                    sell_votes += 3
                    reasons.append(f"接近跌停({down_limit:.2f})，距离{down_dist:.2f}%，弱势信号")

        # ── 确定候选信号 ──
        if buy_votes > sell_votes and buy_votes >= 2:
            candidate = SIGNAL_BUY
        elif sell_votes > buy_votes and sell_votes >= 2:
            candidate = SIGNAL_SELL
        else:
            candidate = SIGNAL_HOLD

        # ── 冷却期检查（日内策略使用独立冷却键） ──
        intraday_symbol = f"{symbol}__intraday"
        cooldown = intraday_cfg.get("signal_cooldown_seconds", 120)
        last_time = self._last_signal_time.get(intraday_symbol, 0)
        last_type = self._last_signal_type.get(intraday_symbol, "")
        now = time.time()

        if candidate != SIGNAL_HOLD:
            if candidate == last_type and (now - last_time) < cooldown:
                remaining = int(cooldown - (now - last_time))
                logger.debug("%s 日内信号冷却中，还需 %ds", symbol, remaining)
                candidate = SIGNAL_HOLD
                reasons = [f"日内信号冷却期（{remaining}s 后可再次触发）"]

        if candidate != SIGNAL_HOLD:
            self._last_signal_time[intraday_symbol] = now
            self._last_signal_type[intraday_symbol] = candidate

        if candidate == SIGNAL_HOLD:
            return None

        return {
            "symbol": symbol,
            "signal": candidate,
            "price": round(current_price, 3),
            "reasons": reasons,
            "indicators": indicators,
            "strategy_type": "intraday",
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data_points": len(ticks),
        }

    def _generate_signal(self, symbol: str, prices: List[float],
                         current_price: float, cfg: Dict[str, Any]) -> Dict[str, Any]:
        """核心信号生成逻辑（传统技术指标策略）"""
        strategy = cfg.get("strategy", "combined")

        # ── 计算技术指标 ──
        ma_short = cfg.get("ma_short", 5)
        ma_long = cfg.get("ma_long", 20)
        rsi_period = cfg.get("rsi_period", 14)
        rsi_ob = cfg.get("rsi_overbought", 70)
        rsi_os = cfg.get("rsi_oversold", 30)
        macd_fast = cfg.get("macd_fast", 12)
        macd_slow = cfg.get("macd_slow", 26)
        macd_sig = cfg.get("macd_signal", 9)
        boll_period = cfg.get("boll_period", 20)
        boll_std = cfg.get("boll_std", 2.0)

        sma5 = _sma(prices, ma_short)
        sma20 = _sma(prices, ma_long)
        rsi_val = _rsi(prices, rsi_period)
        macd_line, signal_line, histogram = _macd(prices, macd_fast, macd_slow, macd_sig)
        boll_upper, boll_mid, boll_lower = _bollinger(prices, boll_period, boll_std)

        indicators = {
            f"ma{ma_short}": sma5,
            f"ma{ma_long}": sma20,
            "rsi": rsi_val,
            "macd": macd_line,
            "macd_signal": signal_line,
            "macd_hist": histogram,
            "boll_upper": boll_upper,
            "boll_mid": boll_mid,
            "boll_lower": boll_lower,
        }

        # ── 信号投票 ──
        buy_votes, sell_votes = 0, 0
        reasons: List[str] = []

        # MA 金叉/死叉
        if sma5 is not None and sma20 is not None:
            if strategy in ("trend", "combined"):
                if sma5 > sma20:
                    buy_votes += 2
                    reasons.append(f"MA{ma_short}({sma5:.2f})>MA{ma_long}({sma20:.2f}) 金叉")
                elif sma5 < sma20:
                    sell_votes += 2
                    reasons.append(f"MA{ma_short}({sma5:.2f})<MA{ma_long}({sma20:.2f}) 死叉")

        # RSI 超买超卖
        if rsi_val is not None:
            if rsi_val > rsi_ob:
                sell_votes += 2
                reasons.append(f"RSI={rsi_val:.1f} 超买(>{rsi_ob})")
            elif rsi_val < rsi_os:
                buy_votes += 2
                reasons.append(f"RSI={rsi_val:.1f} 超卖(<{rsi_os})")

        # MACD 金叉/死叉
        if macd_line is not None and signal_line is not None:
            if macd_line > signal_line and histogram and histogram > 0:
                buy_votes += 1
                reasons.append(f"MACD({macd_line:.4f})>Signal({signal_line:.4f}) 金叉")
            elif macd_line < signal_line and histogram and histogram < 0:
                sell_votes += 1
                reasons.append(f"MACD({macd_line:.4f})<Signal({signal_line:.4f}) 死叉")

        # 布林带突破
        if boll_upper is not None and boll_lower is not None:
            if strategy in ("mean_reversion", "combined"):
                if current_price > boll_upper:
                    sell_votes += 1
                    reasons.append(f"价格({current_price:.2f})突破布林上轨({boll_upper:.2f})")
                elif current_price < boll_lower:
                    buy_votes += 1
                    reasons.append(f"价格({current_price:.2f})跌破布林下轨({boll_lower:.2f})")

        # ── 确定候选信号 ──
        if buy_votes > sell_votes and buy_votes >= 2:
            candidate = SIGNAL_BUY
        elif sell_votes > buy_votes and sell_votes >= 2:
            candidate = SIGNAL_SELL
        else:
            candidate = SIGNAL_HOLD

        # ── 冷却期检查 ──
        cooldown = cfg.get("signal_cooldown_seconds", 300)
        last_time = self._last_signal_time.get(symbol, 0)
        last_type = self._last_signal_type.get(symbol, "")
        now = time.time()

        if candidate != SIGNAL_HOLD:
            if candidate == last_type and (now - last_time) < cooldown:
                remaining = int(cooldown - (now - last_time))
                logger.debug("%s 信号冷却中，还需 %ds", symbol, remaining)
                candidate = SIGNAL_HOLD
                reasons = [f"信号冷却期（{remaining}s 后可再次触发）"]

        # ── 风险控制 ──
        if candidate != SIGNAL_HOLD:
            risk_cfg = cfg.get("risk", {})
            max_consecutive = risk_cfg.get("max_consecutive_signals", 3)
            if (candidate == last_type and
                    self._consecutive_count[symbol] >= max_consecutive):
                logger.warning("%s 连续 %d 次 %s 信号，风险控制暂停",
                               symbol, max_consecutive, candidate)
                candidate = SIGNAL_HOLD
                reasons = [f"风险控制：连续 {max_consecutive} 次相同信号，暂停发出"]

        # ── 更新状态 ──
        if candidate != SIGNAL_HOLD:
            if candidate == last_type:
                self._consecutive_count[symbol] += 1
            else:
                self._consecutive_count[symbol] = 1
            self._last_signal_time[symbol] = now
            self._last_signal_type[symbol] = candidate

        return {
            "symbol": symbol,
            "signal": candidate,
            "price": round(current_price, 3),
            "reasons": reasons,
            "indicators": indicators,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data_points": len(prices),
        }

    def get_latest_signal(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取某只股票最新的非 HOLD 信号"""
        return self._latest_signals.get(symbol)

    def get_all_latest_signals(self) -> Dict[str, Dict[str, Any]]:
        """获取所有股票的最新信号"""
        return dict(self._latest_signals)

    def get_signal_history(self, symbol: str, n: int = 10) -> List[Dict[str, Any]]:
        """从记忆日志获取历史信号"""
        return self._log.get_history(symbol, n)

    def get_log_summary(self) -> Dict[str, Any]:
        """获取所有股票的信号日志摘要"""
        return self._log.get_all_summary()

    def get_indicators(self, symbol: str) -> Dict[str, Any]:
        """获取某只股票当前技术指标快照"""
        prices = list(self._price_history.get(symbol, []))
        if not prices:
            return {}
        cfg = _get_symbol_config(self._config, symbol)
        ma_short = cfg.get("ma_short", 5)
        ma_long = cfg.get("ma_long", 20)
        return {
            f"ma{ma_short}": _sma(prices, ma_short),
            f"ma{ma_long}": _sma(prices, ma_long),
            "rsi": _rsi(prices, cfg.get("rsi_period", 14)),
            "current_price": prices[-1],
            "data_points": len(prices),
        }

    def print_signal_report(self, result: Dict[str, Any]) -> None:
        """打印信号报告到控制台"""
        signal = result.get("signal", SIGNAL_HOLD)
        symbol = result.get("symbol", "")
        price = result.get("price", 0)
        reasons = result.get("reasons", [])
        t = result.get("time", "")

        emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}.get(signal, "⚪")
        print(f"\n{emoji} [{t}] {symbol} 信号: {signal}  价格: {price}")
        for r in reasons:
            print(f"   └─ {r}")
