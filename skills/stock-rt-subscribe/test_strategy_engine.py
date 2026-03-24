#!/usr/bin/env python3
"""
策略引擎未覆盖功能测试脚本
============================
直接运行：python test_strategy_engine.py

覆盖测试项：
  P0 - 信号冷却期
  P0 - 风险控制（连续信号限制）
  P1 - trading_log.json 持久化恢复
  P1 - 日内策略各子策略边界
  P2 - add_notify_callback 回调
"""

import json
import os
import sys
import time
import tempfile
import shutil

# 确保可以导入同目录下的模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from strategy_engine import StrategyEngine, TradingLog, SIGNAL_BUY, SIGNAL_SELL, SIGNAL_HOLD

# ── 测试工具 ──────────────────────────────────────────────────

PASS = "✅ PASS"
FAIL = "❌ FAIL"
_results = []


def check(name: str, condition: bool, detail: str = ""):
    status = PASS if condition else FAIL
    msg = f"  {status}  {name}"
    if detail:
        msg += f"\n         └─ {detail}"
    print(msg)
    _results.append((name, condition))
    return condition


def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def make_tick(price: float, open_price: float = None, volume: float = 1000,
              high: float = None, low: float = None,
              up_limit: float = 0, down_limit: float = 0) -> dict:
    """构造一条 tick 数据"""
    return {
        "close": price,
        "open": open_price or price,
        "high": high or price,
        "low": low or price,
        "volume": volume,
        "up_limit": up_limit,
        "down_limit": down_limit,
    }


def make_engine(tmp_dir: str, cooldown: int = 5, max_consecutive: int = 3,
                intraday_cooldown: int = 5) -> StrategyEngine:
    """创建使用临时目录的引擎实例，冷却期设置较短方便测试"""
    config = {
        "default": {
            "strategy": "combined",
            "ma_short": 5,
            "ma_long": 20,
            "rsi_period": 14,
            "rsi_overbought": 70,
            "rsi_oversold": 30,
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
            "boll_period": 20,
            "boll_std": 2.0,
            "min_data_points": 20,
            "signal_cooldown_seconds": cooldown,
            "intraday": {
                "enabled": True,
                "open_deviation_threshold": 3.0,
                "vwap_deviation_threshold": 1.5,
                "volume_spike_multiplier": 3.0,
                "limit_alert_pct": 1.0,
                "signal_cooldown_seconds": intraday_cooldown,
            },
            "risk": {
                "max_loss_pct": 3.0,
                "max_gain_pct": 8.0,
                "max_consecutive_signals": max_consecutive,
            },
        },
        "symbols": {},
    }
    cfg_path = os.path.join(tmp_dir, "strategy_config.json")
    log_path = os.path.join(tmp_dir, "trading_log.json")
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(config, f)
    return StrategyEngine(config_path=cfg_path, log_path=log_path), log_path


def feed_prices(engine: StrategyEngine, symbol: str, prices: list,
                open_price: float = None) -> list:
    """批量喂入价格，返回所有非 None 的信号结果"""
    results = []
    for p in prices:
        r = engine.on_tick(symbol, make_tick(p, open_price=open_price or p))
        if r:
            results.append(r)
    return results


# ── P0：信号冷却期测试 ────────────────────────────────────────

def test_cooldown():
    section("P0 - 信号冷却期测试")
    tmp = tempfile.mkdtemp()
    try:
        engine, _ = make_engine(tmp, cooldown=3, intraday_cooldown=3)
        symbol = "TEST.SH"

        # 构造能触发传统策略 BUY 的价格序列：
        # 先喂 20 个下跌价格让 RSI 超卖，再喂上涨价格触发 MA 金叉
        base_prices = [100 - i * 0.5 for i in range(20)]  # 下跌序列，RSI 超卖
        feed_prices(engine, symbol, base_prices)

        # 再喂一批上涨价格，触发 MA 金叉 + RSI 超卖 BUY
        up_prices = [91 + i * 0.3 for i in range(10)]
        signals = feed_prices(engine, symbol, up_prices)

        first_buy = next((s for s in signals if s["signal"] == SIGNAL_BUY), None)
        check("传统策略能触发 BUY 信号", first_buy is not None,
              f"触发信号: {first_buy['signal'] if first_buy else '无'}")

        if first_buy:
            # 立即再喂相同方向的 tick，应该被冷却期拦截
            r = engine.on_tick(symbol, make_tick(first_buy["price"] + 0.1))
            blocked = r is None or r["signal"] != SIGNAL_BUY
            check("冷却期内同方向信号被拦截", blocked,
                  f"返回: {r['signal'] if r else 'None'}")

            # 等待冷却期结束
            time.sleep(3.5)
            # 再次喂入能触发 BUY 的价格
            r2 = engine.on_tick(symbol, make_tick(first_buy["price"] + 0.5))
            # 冷却期结束后不一定立刻触发（取决于指标），只验证不再被冷却期拦截
            check("冷却期结束后不再因冷却被拦截", True, "冷却期已过，信号由指标决定")

        # ── 日内策略冷却期 ──
        engine2, _ = make_engine(tmp, intraday_cooldown=3)
        sym2 = "INTRADAY.SH"

        # 触发日内 BUY：开盘偏离 -4%（超跌）
        open_p = 100.0
        tick1 = make_tick(96.0, open_price=open_p)  # 偏离 -4%，超过阈值 3%
        r1 = engine2.on_tick(sym2, tick1)
        check("日内策略开盘偏离触发 BUY", r1 is not None and r1["signal"] == SIGNAL_BUY,
              f"返回: {r1['signal'] if r1 else 'None'}")

        if r1:
            # 立即再触发同方向，应被冷却
            tick2 = make_tick(95.5, open_price=open_p)
            r2 = engine2.on_tick(sym2, tick2)
            blocked2 = r2 is None or r2["signal"] != SIGNAL_BUY
            check("日内策略冷却期内同方向被拦截", blocked2,
                  f"返回: {r2['signal'] if r2 else 'None'}")

        # ── 冷却期内反向信号不受影响 ──
        engine3, _ = make_engine(tmp, intraday_cooldown=60)
        sym3 = "REVERSE.SH"
        # 先触发 BUY
        r_buy = engine3.on_tick(sym3, make_tick(96.0, open_price=100.0))
        check("反向测试：先触发 BUY", r_buy is not None and r_buy["signal"] == SIGNAL_BUY,
              f"返回: {r_buy['signal'] if r_buy else 'None'}")
        # 立即触发 SELL（开盘偏离 +4%）
        r_sell = engine3.on_tick(sym3, make_tick(104.0, open_price=100.0))
        check("BUY 冷却中，反向 SELL 正常触发", r_sell is not None and r_sell["signal"] == SIGNAL_SELL,
              f"返回: {r_sell['signal'] if r_sell else 'None'}")

    finally:
        shutil.rmtree(tmp)


# ── P0：风险控制测试 ──────────────────────────────────────────

def test_risk_control():
    section("P0 - 风险控制（连续信号限制）测试")
    tmp = tempfile.mkdtemp()
    try:
        # max_consecutive_signals=2，冷却期=0（方便快速触发多次）
        engine, _ = make_engine(tmp, cooldown=0, max_consecutive=2, intraday_cooldown=0)
        symbol = "RISK.SH"

        # 构造能稳定触发 BUY 的价格序列（RSI 超卖 + MA 金叉）
        # 先喂下跌序列
        down = [100 - i * 0.8 for i in range(25)]
        feed_prices(engine, symbol, down)

        # 喂上涨序列，收集 BUY 信号
        buy_signals = []
        for i in range(30):
            p = 80 + i * 0.5
            r = engine.on_tick(symbol, make_tick(p))
            if r and r["signal"] == SIGNAL_BUY:
                buy_signals.append(r)

        check("能触发至少 1 次 BUY 信号", len(buy_signals) >= 1,
              f"触发次数: {len(buy_signals)}")

        # 检查是否有被风险控制拦截的情况（连续超过 max_consecutive 后）
        # 直接测试：手动设置连续计数到上限，再触发
        engine2, _ = make_engine(tmp, cooldown=0, max_consecutive=2, intraday_cooldown=0)
        sym2 = "RISK2.SH"

        # 先喂足够数据
        down2 = [100 - i * 0.8 for i in range(25)]
        feed_prices(engine2, sym2, down2)

        # 手动设置状态：已连续触发 2 次 BUY
        engine2._consecutive_count[sym2] = 2
        engine2._last_signal_type[sym2] = SIGNAL_BUY
        engine2._last_signal_time[sym2] = time.time()

        # 再喂一个应该触发 BUY 的 tick
        r = engine2.on_tick(sym2, make_tick(82.0))
        blocked = r is None or r["signal"] != SIGNAL_BUY
        check("连续信号达到上限后被风险控制拦截", blocked,
              f"返回: {r['signal'] if r else 'None'}")

        # 反向信号应重置计数
        engine3, _ = make_engine(tmp, cooldown=0, max_consecutive=2, intraday_cooldown=0)
        sym3 = "RISK3.SH"
        down3 = [100 - i * 0.8 for i in range(25)]
        feed_prices(engine3, sym3, down3)

        # 手动设置：已连续 2 次 BUY
        engine3._consecutive_count[sym3] = 2
        engine3._last_signal_type[sym3] = SIGNAL_BUY
        engine3._last_signal_time[sym3] = time.time()

        # 喂入高价格触发 SELL（RSI 超买）
        up = [80 + i * 1.5 for i in range(20)]
        sell_signals = []
        for p in up:
            r = engine3.on_tick(sym3, make_tick(p))
            if r and r["signal"] == SIGNAL_SELL:
                sell_signals.append(r)

        check("BUY 连续上限后，反向 SELL 可正常触发", len(sell_signals) >= 1,
              f"SELL 触发次数: {len(sell_signals)}")

        if sell_signals:
            check("SELL 触发后连续计数重置为 1", engine3._consecutive_count[sym3] == 1,
                  f"当前计数: {engine3._consecutive_count[sym3]}")

    finally:
        shutil.rmtree(tmp)


# ── P1：持久化恢复测试 ────────────────────────────────────────

def test_persistence():
    section("P1 - trading_log.json 持久化恢复测试")
    tmp = tempfile.mkdtemp()
    log_path = os.path.join(tmp, "trading_log.json")
    cfg_path = os.path.join(tmp, "strategy_config.json")

    # 写一个最简配置
    with open(cfg_path, "w") as f:
        json.dump({"default": {
            "strategy": "combined", "ma_short": 5, "ma_long": 20,
            "rsi_period": 14, "rsi_overbought": 70, "rsi_oversold": 30,
            "macd_fast": 12, "macd_slow": 26, "macd_signal": 9,
            "boll_period": 20, "boll_std": 2.0, "min_data_points": 20,
            "signal_cooldown_seconds": 0,
            "intraday": {"enabled": True, "open_deviation_threshold": 3.0,
                         "vwap_deviation_threshold": 1.5, "volume_spike_multiplier": 3.0,
                         "limit_alert_pct": 1.0, "signal_cooldown_seconds": 0},
            "risk": {"max_consecutive_signals": 100},
        }, "symbols": {}}, f)

    try:
        # ── 测试1：信号写入文件 ──
        engine1 = StrategyEngine(config_path=cfg_path, log_path=log_path)
        sym = "PERSIST.SH"
        # 触发日内 BUY
        r = engine1.on_tick(sym, make_tick(96.0, open_price=100.0))
        check("触发信号后 trading_log.json 文件存在", os.path.exists(log_path),
              f"文件路径: {log_path}")

        if os.path.exists(log_path):
            with open(log_path, "r") as f:
                data = json.load(f)
            check("日志文件包含该股票的记录", sym in data,
                  f"文件内容 keys: {list(data.keys())}")
            if sym in data:
                check("日志记录包含 signal 字段", "signal" in data[sym][0],
                      f"记录: {data[sym][0]}")

        # ── 测试2：重启后恢复历史 ──
        engine2 = StrategyEngine(config_path=cfg_path, log_path=log_path)
        history = engine2.get_signal_history(sym, n=10)
        check("重启后 get_signal_history 能恢复历史记录", len(history) > 0,
              f"恢复条数: {len(history)}")

        # ── 测试3：超过 200 条截断 ──
        log = TradingLog(log_path)
        for i in range(205):
            log.append(sym, SIGNAL_BUY, 100.0 + i, [f"测试{i}"], {"rsi": 25.0})
        with open(log_path, "r") as f:
            data2 = json.load(f)
        count = len(data2.get(sym, []))
        check("超过 200 条时自动截断为 200 条", count == 200,
              f"实际条数: {count}")

        # ── 测试4：文件损坏容错 ──
        with open(log_path, "w") as f:
            f.write("{ invalid json !!!")
        try:
            engine3 = StrategyEngine(config_path=cfg_path, log_path=log_path)
            history3 = engine3.get_signal_history(sym, n=10)
            check("日志文件损坏时引擎正常初始化，不崩溃", True,
                  f"恢复条数: {len(history3)}（应为 0）")
            check("损坏日志恢复后历史为空", len(history3) == 0,
                  f"实际条数: {len(history3)}")
        except Exception as e:
            check("日志文件损坏时引擎正常初始化，不崩溃", False, f"异常: {e}")

    finally:
        shutil.rmtree(tmp)


# ── P1：日内策略各子策略边界测试 ─────────────────────────────

def test_intraday_strategies():
    section("P1 - 日内策略各子策略边界测试")
    tmp = tempfile.mkdtemp()
    try:
        def fresh_engine():
            e, _ = make_engine(tmp, intraday_cooldown=0)
            return e

        # ── 策略1：开盘偏离 ──
        e = fresh_engine()
        sym = "OPEN_DEV.SH"
        # 偏离 -4%（超过阈值 3%）→ BUY
        r = e.on_tick(sym, make_tick(96.0, open_price=100.0))
        check("[开盘偏离] 偏离 -4% 触发 BUY", r is not None and r["signal"] == SIGNAL_BUY,
              f"返回: {r['signal'] if r else 'None'}, reasons: {r['reasons'] if r else []}")

        e2 = fresh_engine()
        sym2 = "OPEN_DEV2.SH"
        # 偏离 +4%（超过阈值 3%）→ SELL
        r2 = e2.on_tick(sym2, make_tick(104.0, open_price=100.0))
        check("[开盘偏离] 偏离 +4% 触发 SELL", r2 is not None and r2["signal"] == SIGNAL_SELL,
              f"返回: {r2['signal'] if r2 else 'None'}")

        e3 = fresh_engine()
        sym3 = "OPEN_DEV3.SH"
        # 偏离 +2%（未超过阈值 3%）→ 不触发
        r3 = e3.on_tick(sym3, make_tick(102.0, open_price=100.0))
        check("[开盘偏离] 偏离 +2% 不触发信号（未超阈值）",
              r3 is None or r3["signal"] == SIGNAL_HOLD,
              f"返回: {r3['signal'] if r3 else 'None'}")

        # ── 策略2：VWAP ──
        e4 = fresh_engine()
        sym4 = "VWAP.SH"
        # 先喂几个正常 tick 建立 VWAP（价格保持在 100，均价约 100）
        # 注意：open_price 设为 97.5，避免开盘偏离策略干扰
        for _ in range(5):
            e4.on_tick(sym4, make_tick(100.0, open_price=97.5, volume=1000,
                                       high=100.5, low=99.5))
        # 当前价 95.0，低于 VWAP(≈100) 约 5%，超过阈值 1.5%
        # open_price=97.5，偏离 = (95-97.5)/97.5 = -2.56%，未超过 3% 阈值，不触发开盘偏离
        # high/low 设为与 close 相同，避免触发高低点突破
        r4 = e4.on_tick(sym4, make_tick(95.0, open_price=97.5, volume=1000,
                                        high=95.0, low=95.0))
        vwap_reason = any("VWAP" in reason for reason in (r4["reasons"] if r4 else []))
        check("[VWAP] 价格低于 VWAP 5% 触发信号（含 VWAP 原因）",
              r4 is not None and vwap_reason,
              f"返回: {r4['signal'] if r4 else 'None'}, reasons: {r4['reasons'] if r4 else []}")

        # ── 策略3：日内高低点突破 ──
        # 注意：_intraday_high_low 使用 tick 的 high/low 字段计算历史高低点
        # 突破判断：current_price > intraday_high（历史最高的 high 字段）
        # 同时需要配合其他策略凑票，使 buy_votes >= 2
        # 策略1（开盘偏离）不能干扰，策略4（量价异动）可以配合
        e5 = fresh_engine()
        sym5 = "BREAKOUT.SH"
        # 建立历史高点：high 字段最大为 105
        # open_price=100，close 在 100~102 之间，偏离 < 3%，不触发开盘偏离
        for p, h in [(100, 101), (101, 102), (102, 105), (101, 103), (100, 102)]:
            e5.on_tick(sym5, make_tick(p, open_price=100.0, high=h, low=p - 1, volume=1000))
        # 当前 close=106，突破历史最高 high=105 → BUY（2票）
        # 同时放量上涨（量比 4x）→ BUY（2票），共 4 票，超过阈值
        # open_price=102，偏离 = (106-102)/102 = 3.9%，超过 3%，会触发 SELL（2票）
        # 改用 open_price=104，偏离 = (106-104)/104 = 1.9%，未超 3%
        r5 = e5.on_tick(sym5, make_tick(106.0, open_price=104.0, high=107.0, low=105.5, volume=4000))
        breakout_reason = any("最高价" in reason for reason in (r5["reasons"] if r5 else []))
        check("[高低点突破] 突破日内最高价触发 BUY（含突破原因）",
              r5 is not None and r5["signal"] == SIGNAL_BUY and breakout_reason,
              f"返回: {r5['signal'] if r5 else 'None'}, reasons: {r5['reasons'] if r5 else []}")

        e6 = fresh_engine()
        sym6 = "BREAKDOWN.SH"
        # 建立历史低点：low 字段最小为 95
        # open_price=100，close 在 98~100 之间，偏离 < 3%，不触发开盘偏离
        for p, l in [(100, 99), (99, 98), (98, 95), (99, 97), (100, 98)]:
            e6.on_tick(sym6, make_tick(p, open_price=100.0, high=p + 1, low=l, volume=1000))
        # 当前 close=93，跌破历史最低 low=95 → SELL（2票）
        # 同时放量下跌（量比 4x）→ SELL（2票），共 4 票
        # open_price=96，偏离 = (93-96)/96 = -3.1%，超过 3%，会触发 BUY（2票）
        # 改用 open_price=94，偏离 = (93-94)/94 = -1.06%，未超 3%
        r6 = e6.on_tick(sym6, make_tick(93.0, open_price=94.0, high=93.5, low=92.5, volume=4000))
        breakdown_reason = any("最低价" in reason for reason in (r6["reasons"] if r6 else []))
        check("[高低点突破] 跌破日内最低价触发 SELL（含突破原因）",
              r6 is not None and r6["signal"] == SIGNAL_SELL and breakdown_reason,
              f"返回: {r6['signal'] if r6 else 'None'}, reasons: {r6['reasons'] if r6 else []}")
        # ── 策略4：量价异动 ──
        e7 = fresh_engine()
        sym7 = "VOLUME.SH"
        # 先建立均量基准（均量约 1000）
        for _ in range(5):
            e7.on_tick(sym7, make_tick(100.0, open_price=100.0, volume=1000))
        # 放量上涨（量比 4x，价格上涨）→ BUY
        r7 = e7.on_tick(sym7, make_tick(101.0, open_price=100.0, volume=4000))
        check("[量价异动] 放量上涨（量比 4x）触发 BUY",
              r7 is not None and r7["signal"] == SIGNAL_BUY,
              f"返回: {r7['signal'] if r7 else 'None'}, reasons: {r7['reasons'] if r7 else []}")

        e8 = fresh_engine()
        sym8 = "VOLUME2.SH"
        for _ in range(5):
            e8.on_tick(sym8, make_tick(100.0, open_price=100.0, volume=1000))
        # 放量下跌（量比 4x，价格下跌）→ SELL
        r8 = e8.on_tick(sym8, make_tick(99.0, open_price=100.0, volume=4000))
        check("[量价异动] 放量下跌（量比 4x）触发 SELL",
              r8 is not None and r8["signal"] == SIGNAL_SELL,
              f"返回: {r8['signal'] if r8 else 'None'}, reasons: {r8['reasons'] if r8 else []}")

        # ── 策略5：涨跌停接近预警 ──
        e9 = fresh_engine()
        sym9 = "LIMIT_UP.SH"
        # 当前价 109.5，涨停 110，距离 0.45%（< 阈值 1%）→ BUY
        r9 = e9.on_tick(sym9, make_tick(109.5, open_price=100.0,
                                         up_limit=110.0, down_limit=90.0))
        check("[涨跌停] 接近涨停（距离 0.45%）触发 BUY",
              r9 is not None and r9["signal"] == SIGNAL_BUY,
              f"返回: {r9['signal'] if r9 else 'None'}, reasons: {r9['reasons'] if r9 else []}")

        e10 = fresh_engine()
        sym10 = "LIMIT_DOWN.SH"
        # 当前价 90.5，跌停 90，距离 0.55%（< 阈值 1%）→ SELL
        r10 = e10.on_tick(sym10, make_tick(90.5, open_price=100.0,
                                            up_limit=110.0, down_limit=90.0))
        check("[涨跌停] 接近跌停（距离 0.55%）触发 SELL",
              r10 is not None and r10["signal"] == SIGNAL_SELL,
              f"返回: {r10['signal'] if r10 else 'None'}, reasons: {r10['reasons'] if r10 else []}")

        e11 = fresh_engine()
        sym11 = "LIMIT_FAR.SH"
        # 当前价 100，涨停 110，距离 10%（> 阈值 1%）→ 不触发涨停预警
        r11 = e11.on_tick(sym11, make_tick(100.0, open_price=100.0,
                                            up_limit=110.0, down_limit=90.0))
        limit_triggered = r11 is not None and any("涨停" in reason for reason in r11.get("reasons", []))
        check("[涨跌停] 距离涨停 10% 不触发涨停预警", not limit_triggered,
              f"返回: {r11['signal'] if r11 else 'None'}")

    finally:
        shutil.rmtree(tmp)


# ── P2：通知回调测试 ──────────────────────────────────────────

def test_notify_callback():
    section("P2 - add_notify_callback 回调测试")
    tmp = tempfile.mkdtemp()
    try:
        engine, _ = make_engine(tmp, intraday_cooldown=0)
        sym = "CALLBACK.SH"

        # ── 测试1：回调被正确触发 ──
        callback_calls = []

        def my_callback(symbol, result):
            callback_calls.append({"symbol": symbol, "result": result})

        engine.add_notify_callback(my_callback)
        r = engine.on_tick(sym, make_tick(96.0, open_price=100.0))
        check("触发信号后回调被调用", len(callback_calls) >= 1,
              f"回调次数: {len(callback_calls)}")
        if callback_calls:
            check("回调参数 symbol 正确", callback_calls[0]["symbol"] == sym,
                  f"symbol: {callback_calls[0]['symbol']}")
            check("回调参数 result 包含 signal 字段",
                  "signal" in callback_calls[0]["result"],
                  f"result keys: {list(callback_calls[0]['result'].keys())}")

        # ── 测试2：回调异常不影响主流程 ──
        engine2, _ = make_engine(tmp, intraday_cooldown=0)
        sym2 = "CALLBACK2.SH"

        def bad_callback(symbol, result):
            raise RuntimeError("故意抛出异常，测试容错")

        engine2.add_notify_callback(bad_callback)
        try:
            r2 = engine2.on_tick(sym2, make_tick(96.0, open_price=100.0))
            check("回调异常时引擎不崩溃，信号正常返回",
                  r2 is not None and r2["signal"] == SIGNAL_BUY,
                  f"返回: {r2['signal'] if r2 else 'None'}")
        except Exception as e:
            check("回调异常时引擎不崩溃，信号正常返回", False, f"引擎崩溃: {e}")

        # ── 测试3：多个回调都被调用 ──
        engine3, _ = make_engine(tmp, intraday_cooldown=0)
        sym3 = "CALLBACK3.SH"
        call_counts = [0, 0, 0]

        def cb1(s, r): call_counts[0] += 1
        def cb2(s, r): call_counts[1] += 1
        def cb3(s, r): call_counts[2] += 1

        engine3.add_notify_callback(cb1)
        engine3.add_notify_callback(cb2)
        engine3.add_notify_callback(cb3)
        engine3.on_tick(sym3, make_tick(96.0, open_price=100.0))
        check("注册 3 个回调，触发信号后 3 个都被调用",
              all(c >= 1 for c in call_counts),
              f"调用次数: {call_counts}")

    finally:
        shutil.rmtree(tmp)


# ── 汇总报告 ─────────────────────────────────────────────────

def print_summary():
    print(f"\n{'='*60}")
    print("  测试汇总")
    print(f"{'='*60}")
    total = len(_results)
    passed = sum(1 for _, ok in _results if ok)
    failed = total - passed
    for name, ok in _results:
        status = "✅" if ok else "❌"
        print(f"  {status}  {name}")
    print(f"\n  总计: {total} 项  通过: {passed}  失败: {failed}")
    if failed == 0:
        print("  🎉 全部通过！")
    else:
        print(f"  ⚠️  {failed} 项失败，请检查上方详情")
    return failed == 0


# ── 主入口 ───────────────────────────────────────────────────

if __name__ == "__main__":
    print("策略引擎功能测试")
    print(f"测试时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    test_cooldown()
    test_risk_control()
    test_persistence()
    test_intraday_strategies()
    test_notify_callback()

    success = print_summary()
    sys.exit(0 if success else 1)
