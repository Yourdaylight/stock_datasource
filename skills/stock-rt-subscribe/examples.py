#!/usr/bin/env python3
"""
实时行情 WebSocket 订阅使用示例
================================

展示三种用法：
1. 启动 WebSocket 服务，终端显示 + WebSocket 推送
2. 作为 WebSocket 客户端连接已运行的服务
3. 带告警策略的 WebSocket 客户端
"""

import asyncio
import json
import os
import sys
import time

# ── 配置 ──────────────────────────────────────────────────────
# 设置环境变量 STOCK_RT_NODE_URL 指向你的 receiver 节点
# 例如: export STOCK_RT_NODE_URL=http://your-node-ip:9100
NODE_URL = os.getenv("STOCK_RT_NODE_URL", "")
WS_PORT = int(os.getenv("STOCK_WS_PORT", "8765"))

# 要订阅的港股
SYMBOLS = [
    "00700.HK",  # 腾讯控股
    "09988.HK",  # 阿里巴巴
    "09888.HK",  # 百度集团
    "09618.HK",  # 京东集团
]


def example_1_ws_server():
    """示例 1：启动 WebSocket 推送服务（服务端）

    启动后，用户可以通过以下方式连接：
      wscat -c ws://localhost:8765
      或运行示例 2 的客户端代码
    """
    if not NODE_URL:
        print("ERROR: 需要设置 STOCK_RT_NODE_URL 环境变量，指向 receiver 节点地址")
        print("  例如: export STOCK_RT_NODE_URL=http://your-node-ip:9100")
        return

    print("\n" + "=" * 60)
    print("示例 1：启动 WebSocket 实时推送服务")
    print("=" * 60)
    print(f"节点: {NODE_URL}")
    print(f"标的: {', '.join(SYMBOLS)}")
    print(f"WebSocket: ws://0.0.0.0:{WS_PORT}")
    print(f"\n用户连接 ws://localhost:{WS_PORT} 即可接收推送")
    print("按 Ctrl+C 停止\n")

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from subscribe_client import StockWSServer

    server = StockWSServer(
        node_url=NODE_URL,
        symbols=SYMBOLS,
        poll_interval=3.0,
    )
    server.run(port=WS_PORT)


def example_2_ws_client():
    """示例 2：WebSocket 客户端 — 连接服务并持续接收行情"""
    print("\n" + "=" * 60)
    print("示例 2：WebSocket 客户端（连接已运行的服务）")
    print("=" * 60)
    print(f"连接: ws://localhost:{WS_PORT}")
    print("按 Ctrl+C 停止\n")

    try:
        import websockets
    except ImportError:
        print("ERROR: 需要 websockets 库。执行: pip install websockets")
        return

    async def listen():
        uri = f"ws://localhost:{WS_PORT}"
        async with websockets.connect(uri) as ws:
            print(f"✅ 已连接 {uri}\n")

            # 发送订阅指令（可选，服务端已有默认订阅）
            await ws.send(json.dumps({
                "action": "subscribe",
                "symbols": SYMBOLS,
            }))

            tick_count = 0
            async for raw_msg in ws:
                data = json.loads(raw_msg)
                msg_type = data.get("type", "")

                if msg_type == "welcome":
                    print(f"🤝 {data['message']}")
                    print(f"   服务端订阅: {data.get('server_symbols', [])}")
                    print()

                elif msg_type == "subscribed":
                    print(f"📋 订阅确认: {data.get('current', [])}")
                    print()

                elif msg_type == "snapshot":
                    print(f"📸 快照: {data['count']} 条数据")
                    for item in data.get("data", []):
                        pct = item.get("pct_chg", 0)
                        icon = "📈" if pct > 0 else "📉" if pct < 0 else "➖"
                        print(f"   {icon} {item.get('name', '')}({item.get('ts_code', '')}): "
                              f"{item.get('close', 0):.2f}  {pct:+.2f}%")
                    print()

                elif msg_type == "tick":
                    tick_count += 1
                    pct = data.get("pct_chg", 0)
                    icon = "📈" if pct > 0 else "📉" if pct < 0 else "➖"
                    print(
                        f"  {icon} [{tick_count}] "
                        f"{data.get('name', '')}({data.get('ts_code', '')}): "
                        f"{data.get('close', 0):.2f} 元  {pct:+.2f}%  "
                        f"成交额: {data.get('amount', 0) / 1e8:.2f}亿"
                    )

    try:
        asyncio.run(listen())
    except KeyboardInterrupt:
        print("\n\n客户端已断开")


def example_3_alert_client():
    """示例 3：带告警的 WebSocket 客户端"""
    print("\n" + "=" * 60)
    print("示例 3：价格告警 WebSocket 客户端（涨跌幅超 1% 时触发）")
    print("=" * 60)

    ALERT_THRESHOLD = 1.0

    try:
        import websockets
    except ImportError:
        print("ERROR: 需要 websockets 库。执行: pip install websockets")
        return

    async def listen_with_alert():
        uri = f"ws://localhost:{WS_PORT}"
        alert_count = 0

        async with websockets.connect(uri) as ws:
            print(f"✅ 已连接 {uri}")
            print(f"告警阈值: ±{ALERT_THRESHOLD}%\n")

            async for raw_msg in ws:
                data = json.loads(raw_msg)

                if data.get("type") != "tick":
                    continue

                pct = data.get("pct_chg", 0)
                name = data.get("name", "")
                ts_code = data.get("ts_code", "")
                close = data.get("close", 0)

                if abs(pct) >= ALERT_THRESHOLD:
                    alert_count += 1
                    direction = "🔴 大涨" if pct > 0 else "🟢 大跌"
                    print(
                        f"  ⚠️  [{alert_count}] {direction}! "
                        f"{name}({ts_code}): "
                        f"{close:.2f} 元  {pct:+.2f}%"
                    )
                else:
                    print(f"  ✓ {name}: {close:.2f} 元  {pct:+.2f}% (正常)")

    try:
        asyncio.run(listen_with_alert())
    except KeyboardInterrupt:
        print("\n\n告警客户端已断开")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        example_num = sys.argv[1]
        if example_num == "1":
            example_1_ws_server()
        elif example_num == "2":
            example_2_ws_client()
        elif example_num == "3":
            example_3_alert_client()
        else:
            print(f"未知示例: {example_num}，可选 1/2/3")
    else:
        print("用法: python3 examples.py [1|2|3]")
        print("  1 - 启动 WebSocket 推送服务（服务端）")
        print("  2 - WebSocket 客户端（连接服务接收行情）")
        print("  3 - 带告警的 WebSocket 客户端")
        print()
        print("典型流程:")
        print("  终端 A: python3 examples.py 1     # 启动服务")
        print("  终端 B: python3 examples.py 2     # 连接接收行情")
        print()
        print("默认运行示例 1（启动 WebSocket 服务）:")
        example_1_ws_server()
