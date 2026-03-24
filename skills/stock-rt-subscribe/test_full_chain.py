#!/usr/bin/env python3
"""
完整链路测试脚本 — test_full_chain.py
======================================
测试 ai_agent_integration.py 的完整链路，包括：
  1. 鉴权引导（guide_authentication）
  2. 服务端订阅同步（sync_subscription / list_subscription）
  3. 启动订阅服务（start_subscription）
  4. 动态新增/退订（add_symbols / remove_symbols）
  5. 实时数据接收（receive_realtime_data）
  6. 数据分析 + 策略信号（analyze_stock_changes）
  7. 报告打印（print_analysis_report）
  8. 完整工作流（complete_workflow）

运行方式:
  # 先设置环境变量
  export STOCK_RT_NODE_URL="http://139.155.0.115:9100"
  export STOCK_RT_JWT_TOKEN="your_jwt_token"   # 可选，有则走订阅接口

  # 运行测试（开盘前可跑 T1~T4，开盘后跑全部）
  python3 test_full_chain.py

  # 只跑指定测试
  python3 test_full_chain.py --test T1 T2 T3
  python3 test_full_chain.py --test all        # 全部（含实时数据，需开盘）
  python3 test_full_chain.py --test workflow   # 只跑完整工作流
"""

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime

# ── 颜色输出 ──────────────────────────────────────────────────

def _ok(msg):  print(f"  ✅ {msg}")
def _fail(msg): print(f"  ❌ {msg}")
def _info(msg): print(f"  ℹ️  {msg}")
def _warn(msg): print(f"  ⚠️  {msg}")
def _title(msg): print(f"\n{'='*60}\n🧪 {msg}\n{'='*60}")
def _sep():  print("-" * 60)

# ── 测试标的 ──────────────────────────────────────────────────

TEST_SYMBOLS = ["00700.HK", "09988.HK", "600519.SH", "000001.SZ"]
ADD_SYMBOLS   = ["09888.HK"]   # 动态新增
REMOVE_SYMBOLS = ["09988.HK"]  # 动态退订

# ── 导入被测模块 ──────────────────────────────────────────────

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from ai_agent_integration import StockDataAgent
    from strategy_engine import SIGNAL_BUY, SIGNAL_SELL, SIGNAL_HOLD
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════
# T1 — 鉴权引导
# ═══════════════════════════════════════════════════════════════

def test_t1_authentication():
    _title("T1 — 鉴权引导 (guide_authentication)")
    agent = StockDataAgent()

    node_url = os.getenv("STOCK_RT_NODE_URL", "")
    if not node_url:
        _warn("未设置 STOCK_RT_NODE_URL，跳过连通性测试")
        _info("请执行: export STOCK_RT_NODE_URL=\"http://139.155.0.115:9100\"")
        return False

    result = agent.guide_authentication()
    if result:
        _ok(f"节点连通性正常: {node_url}")
    else:
        _fail("节点连通性失败，请检查网络或节点地址")
    return result


# ═══════════════════════════════════════════════════════════════
# T2 — 服务端订阅同步
# ═══════════════════════════════════════════════════════════════

def test_t2_subscription_sync():
    _title("T2 — 服务端订阅同步 (sync_subscription / list_subscription)")
    agent = StockDataAgent()

    jwt = os.getenv("STOCK_RT_JWT_TOKEN", os.getenv("STOCK_RT_TOKEN", ""))
    if not jwt:
        _warn("未设置 JWT Token，跳过服务端订阅同步测试（需要 Token 才能写入订阅）")
        _info("请执行: export STOCK_RT_JWT_TOKEN=\"your_token\"")
        return True  # 非阻塞，继续后续测试

    # 2-1: replace 模式
    _sep()
    print("  [2-1] replace 模式同步订阅...")
    result = agent.sync_subscription(TEST_SYMBOLS, mode="replace")
    if "error" in result:
        _fail(f"replace 同步失败: {result['error']}")
    else:
        accepted = result.get("accepted_symbols", [])
        rejected = result.get("rejected_symbols", [])
        _ok(f"replace 同步成功，接受: {accepted}")
        if rejected:
            _warn(f"被拒绝: {rejected}")

    # 2-2: 查询订阅列表
    _sep()
    print("  [2-2] 查询服务端订阅列表...")
    list_result = agent.list_subscription()
    if "error" in list_result:
        _fail(f"查询失败: {list_result['error']}")
    else:
        subs = list_result.get("subscribed_symbols", [])
        _ok(f"当前服务端订阅: {subs}")

    # 2-3: add 模式
    _sep()
    print(f"  [2-3] add 模式新增 {ADD_SYMBOLS}...")
    result = agent.sync_subscription(ADD_SYMBOLS, mode="add")
    if "error" in result:
        _fail(f"add 同步失败: {result['error']}")
    else:
        _ok(f"add 同步成功，当前: {result.get('accepted_symbols', [])}")

    # 2-4: remove 模式
    _sep()
    print(f"  [2-4] remove 模式退订 {REMOVE_SYMBOLS}...")
    result = agent.sync_subscription(REMOVE_SYMBOLS, mode="remove")
    if "error" in result:
        _fail(f"remove 同步失败: {result['error']}")
    else:
        _ok(f"remove 同步成功，当前: {result.get('accepted_symbols', [])}")

    # 2-5: 恢复原始订阅
    agent.sync_subscription(TEST_SYMBOLS, mode="replace")
    _ok("已恢复原始订阅列表")
    return True


# ═══════════════════════════════════════════════════════════════
# T3 — 启动订阅服务
# ═══════════════════════════════════════════════════════════════

def test_t3_start_subscription():
    _title("T3 — 启动订阅服务 (start_subscription)")
    agent = StockDataAgent()

    node_url = os.getenv("STOCK_RT_NODE_URL", "")
    if not node_url:
        _warn("未设置 STOCK_RT_NODE_URL，跳过")
        return None

    print(f"  启动订阅服务，标的: {TEST_SYMBOLS}")
    ok = agent.start_subscription(TEST_SYMBOLS)
    if ok:
        _ok(f"订阅服务启动成功 (PID: {agent.subscription_process.pid})")
        _ok(f"WebSocket 地址: ws://localhost:{agent.ws_port}")
    else:
        _fail("订阅服务启动失败")
        return None

    # 等待服务稳定
    print("  等待 5 秒让服务稳定...")
    time.sleep(5)

    # 检查进程是否还活着
    if agent.subscription_process.poll() is None:
        _ok("订阅服务进程运行正常")
    else:
        _fail("订阅服务进程已意外退出")
        return None

    return agent  # 返回 agent 供后续测试复用


# ═══════════════════════════════════════════════════════════════
# T4 — 动态新增/退订
# ═══════════════════════════════════════════════════════════════

def test_t4_dynamic_subscription(agent: StockDataAgent):
    _title("T4 — 动态新增/退订 (add_symbols / remove_symbols)")

    if not agent or not agent.is_running:
        _warn("订阅服务未运行，跳过动态订阅测试")
        return

    # 4-1: 新增订阅
    _sep()
    print(f"  [4-1] 动态新增 {ADD_SYMBOLS}...")
    result = agent.add_symbols(ADD_SYMBOLS)
    if "error" in result:
        _fail(f"新增失败: {result['error']}")
    else:
        _ok(f"新增成功: {result.get('accepted_symbols', ADD_SYMBOLS)}")

    time.sleep(2)

    # 4-2: 退订
    _sep()
    print(f"  [4-2] 动态退订 {REMOVE_SYMBOLS}...")
    result = agent.remove_symbols(REMOVE_SYMBOLS)
    if "error" in result:
        _fail(f"退订失败: {result['error']}")
    else:
        _ok(f"退订成功")

    time.sleep(2)


# ═══════════════════════════════════════════════════════════════
# T5 — 实时数据接收
# ═══════════════════════════════════════════════════════════════

async def test_t5_receive_data(agent: StockDataAgent, duration: int = 30):
    _title(f"T5 — 实时数据接收 (receive_realtime_data, {duration}秒)")

    if not agent or not agent.is_running:
        _warn("订阅服务未运行，跳过实时数据接收测试")
        return {}

    tick_log = []

    def on_tick(data):
        tick_log.append(data)
        symbol = data.get("ts_code", "")
        price  = data.get("close", 0)
        chg    = data.get("pct_chg", 0)
        name   = data.get("name", "")
        t      = data.get("collected_at", "")[:19]
        print(f"    📌 [{t}] {symbol} {name}  价格={price}  涨跌={chg:+.2f}%")

    stock_data = await agent.receive_realtime_data(duration=duration, on_tick=on_tick)

    _sep()
    if stock_data:
        _ok(f"共接收 {sum(len(v) for v in stock_data.values())} 条 tick")
        for sym, ticks in stock_data.items():
            _ok(f"  {sym}: {len(ticks)} 条")
    else:
        _warn("未收到任何 tick 数据（可能非交易时间）")

    return stock_data


# ═══════════════════════════════════════════════════════════════
# T6 — 数据分析 + 策略信号
# ═══════════════════════════════════════════════════════════════

def test_t6_analyze(agent: StockDataAgent, stock_data: dict):
    _title("T6 — 数据分析 + 策略信号 (analyze_stock_changes)")

    if not stock_data:
        # 构造模拟数据用于测试分析逻辑
        _warn("无实时数据，使用模拟 tick 数据测试分析逻辑")
        stock_data = _make_mock_data()

    result = agent.analyze_stock_changes(stock_data)

    if "error" in result:
        _fail(f"分析失败: {result['error']}")
        return result

    for symbol, analysis in result.items():
        if "status" in analysis:
            _warn(f"{symbol}: {analysis['status']}")
            continue
        _ok(f"{symbol} ({analysis.get('name', '')}):")
        print(f"      趋势={analysis['trend']}  "
              f"初始={analysis['initial_price']}  "
              f"最新={analysis['latest_price']}  "
              f"变化={analysis['total_change_pct']:+.2f}%")
        strategy = analysis.get("strategy", {})
        sig = strategy.get("signal", SIGNAL_HOLD)
        sig_emoji = {SIGNAL_BUY: "🟢买入", SIGNAL_SELL: "🔴卖出", SIGNAL_HOLD: "⚪持仓"}.get(sig, "⚪")
        print(f"      策略信号: {sig_emoji}")
        for r in strategy.get("reasons", []):
            print(f"        └─ {r}")

    return result


# ═══════════════════════════════════════════════════════════════
# T7 — 报告打印
# ═══════════════════════════════════════════════════════════════

def test_t7_print_report(agent: StockDataAgent, analysis_result: dict):
    _title("T7 — 报告打印 (print_analysis_report)")
    if not analysis_result:
        _warn("无分析结果，跳过报告打印")
        return
    agent.print_analysis_report(analysis_result)
    _ok("报告打印完成")


# ═══════════════════════════════════════════════════════════════
# T8 — 完整工作流（complete_workflow）
# ═══════════════════════════════════════════════════════════════

async def test_t8_complete_workflow(duration: int = 60):
    _title(f"T8 — 完整工作流 (complete_workflow, {duration}秒)")

    node_url = os.getenv("STOCK_RT_NODE_URL", "")
    if not node_url:
        _warn("未设置 STOCK_RT_NODE_URL，跳过完整工作流测试")
        return

    agent = StockDataAgent()
    await agent.complete_workflow(TEST_SYMBOLS, duration=duration)
    _ok("完整工作流执行完毕")


# ═══════════════════════════════════════════════════════════════
# 辅助：构造模拟 tick 数据（非交易时间用）
# ═══════════════════════════════════════════════════════════════

def _make_mock_data() -> dict:
    """构造足够触发策略信号的模拟 tick 序列"""
    import random
    random.seed(42)
    mock = {}
    for sym, name, base in [
        ("00700.HK", "腾讯控股", 380.0),
        ("600519.SH", "贵州茅台", 1700.0),
    ]:
        ticks = []
        price = base
        pre_close = base * 0.99
        for i in range(40):
            chg = random.uniform(-1.5, 2.0)
            price = round(price * (1 + chg / 100), 2)
            pct_chg = round((price - pre_close) / pre_close * 100, 2)
            ticks.append({
                "ts_code": sym,
                "name": name,
                "close": price,
                "open": round(price * 0.998, 2),
                "high": round(price * 1.005, 2),
                "low":  round(price * 0.995, 2),
                "vol":  random.randint(10000, 500000),
                "amount": round(price * random.randint(10000, 500000), 2),
                "pre_close": pre_close,
                "pct_chg": pct_chg,
                "trade_date": int(datetime.now().strftime("%Y%m%d")),
                "collected_at": datetime.now().isoformat(),
                "version": i + 1,
            })
            pre_close = price
        mock[sym] = ticks
    return mock


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════

async def run_tests(tests: list, duration: int):
    print(f"\n{'='*60}")
    print(f"🚀 完整链路测试开始  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   节点: {os.getenv('STOCK_RT_NODE_URL', '(未设置)')}")
    print(f"   JWT:  {'已设置' if os.getenv('STOCK_RT_JWT_TOKEN') else '(未设置，只读模式)'}")
    print(f"   标的: {TEST_SYMBOLS}")
    print(f"{'='*60}")

    run_all = "all" in tests or "workflow" in tests

    # T1 — 鉴权
    if run_all or "T1" in tests:
        auth_ok = test_t1_authentication()
        if not auth_ok and run_all:
            _fail("鉴权失败，终止后续测试")
            return

    # T2 — 订阅同步
    if run_all or "T2" in tests:
        test_t2_subscription_sync()

    # T8 — 完整工作流（独立运行）
    if "workflow" in tests:
        await test_t8_complete_workflow(duration=duration)
        return

    # T3 — 启动服务
    agent = None
    if run_all or any(t in tests for t in ["T3", "T4", "T5", "T6", "T7"]):
        agent = test_t3_start_subscription()

    # T4 — 动态订阅
    if agent and (run_all or "T4" in tests):
        test_t4_dynamic_subscription(agent)

    # T5 — 实时数据接收
    stock_data = {}
    if agent and (run_all or "T5" in tests):
        stock_data = await test_t5_receive_data(agent, duration=duration)

    # T6 — 数据分析
    analysis_result = {}
    if run_all or "T6" in tests:
        analysis_result = test_t6_analyze(
            agent or StockDataAgent(),
            stock_data
        )

    # T7 — 报告打印
    if run_all or "T7" in tests:
        test_t7_print_report(
            agent or StockDataAgent(),
            analysis_result
        )

    # T8 — 完整工作流
    if run_all or "T8" in tests:
        await test_t8_complete_workflow(duration=duration)

    # 停止服务
    if agent and agent.is_running:
        agent.stop_subscription()

    print(f"\n{'='*60}")
    print(f"✅ 测试完成  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="完整链路测试脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
测试项说明:
  T1  鉴权引导（guide_authentication）
  T2  服务端订阅同步（sync_subscription / list_subscription）
  T3  启动订阅服务（start_subscription）
  T4  动态新增/退订（add_symbols / remove_symbols）
  T5  实时数据接收（receive_realtime_data）—— 需开盘
  T6  数据分析 + 策略信号（analyze_stock_changes）
  T7  报告打印（print_analysis_report）
  T8  完整工作流（complete_workflow）—— 需开盘
  all      运行 T1~T8 全部
  workflow 只运行 T8 完整工作流

示例:
  # 开盘前：只测鉴权和订阅同步
  python3 test_full_chain.py --test T1 T2

  # 开盘后：跑完整链路
  python3 test_full_chain.py --test all --duration 60

  # 只跑完整工作流
  python3 test_full_chain.py --test workflow --duration 120
        """
    )
    parser.add_argument(
        "--test", nargs="+",
        default=["T1", "T2", "T6", "T7"],
        help="要运行的测试项（默认: T1 T2 T6 T7）"
    )
    parser.add_argument(
        "--duration", type=int, default=30,
        help="实时数据接收时长（秒，默认 30）"
    )
    args = parser.parse_args()

    asyncio.run(run_tests(args.test, args.duration))


if __name__ == "__main__":
    main()
