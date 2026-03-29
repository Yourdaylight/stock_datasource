#!/usr/bin/env python3
"""
Real-time Stock Subscription Client (WebSocket)
=================================================
通过 WebSocket 长连接接收实时股票行情数据。

架构：
  客户端启动一个本地 WebSocket 服务，后台轮询 Receiver 节点的 HTTP API，
  将最新行情通过 WebSocket 长连接实时推送给所有连接的客户端。
  用户只需连接 ws://localhost:PORT 即可持续收到数据流。

命令行使用:
  # 订阅腾讯控股和贵州茅台（启动 WebSocket 服务）
  python3 subscribe_client.py --symbols 00700.HK 600519.SH

  # 指定节点和 WebSocket 端口
  python3 subscribe_client.py --node-url http://YOUR_NODE_IP:9100 --ws-port 8765 --symbols 00700.HK

  # 安静模式（只输出 JSON，适合管道）
  python3 subscribe_client.py --symbols 00700.HK --quiet

  # 同时输出到文件
  python3 subscribe_client.py --symbols 00700.HK --output ticks.jsonl

  # 价格告警（涨跌幅超阈值时高亮）
  python3 subscribe_client.py --symbols 00700.HK --alert-pct 2.0

编程使用（作为 WebSocket 服务启动）:
  from subscribe_client import StockWSServer
  server = StockWSServer("http://your-node:9100", symbols=["00700.HK"])
  server.run(port=8765)   # 阻塞运行

连接 WebSocket（任意语言/工具）:
  # Python
  import asyncio, websockets, json
  async def listen():
      async with websockets.connect("ws://localhost:8765") as ws:
          # 可选：发送订阅指令动态增减 symbol
          await ws.send(json.dumps({"action": "subscribe", "symbols": ["00700.HK"]}))
          async for msg in ws:
              print(json.loads(msg))
  asyncio.run(listen())

  # wscat 命令行
  wscat -c ws://localhost:8765

  # 浏览器 JS
  const ws = new WebSocket("ws://localhost:8765");
  ws.onmessage = e => console.log(JSON.parse(e.data));
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set

try:
    import requests
except ImportError:
    print("ERROR: 需要 requests 库。执行: pip install requests", file=sys.stderr)
    sys.exit(1)

try:
    import websockets
    import websockets.server
except ImportError:
    print("ERROR: 需要 websockets 库。执行: pip install websockets", file=sys.stderr)
    sys.exit(1)

logger = logging.getLogger("stock-rt-subscribe")

# ── 颜色输出 ──────────────────────────────────────────────────

_COLORS_ENABLED = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    if not _COLORS_ENABLED:
        return text
    return f"\033[{code}m{text}\033[0m"


def _red(t: str) -> str:
    return _c("31", t)


def _green(t: str) -> str:
    return _c("32", t)


def _yellow(t: str) -> str:
    return _c("33", t)


def _cyan(t: str) -> str:
    return _c("36", t)


def _bold(t: str) -> str:
    return _c("1", t)


def _dim(t: str) -> str:
    return _c("2", t)


# ── 数据类 ────────────────────────────────────────────────────


def _to_optional_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    return float(value)


def _to_optional_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    return int(value)


@dataclass
class TickData:
    """一条实时行情快照"""

    ts_code: str = ""
    name: str = ""
    market: str = ""
    trade_time: Optional[str] = None
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    vol: int = 0
    amount: float = 0.0
    num: Optional[int] = None
    pre_close: float = 0.0
    pct_chg: float = 0.0
    bid: Optional[float] = None
    ask: Optional[float] = None
    bid_volume1: Optional[int] = None
    ask_volume1: Optional[int] = None
    trade_date: int = 0
    collected_at: str = ""
    version: int = 0

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TickData":
        return cls(
            ts_code=str(d.get("ts_code", "")),
            name=str(d.get("name", "")),
            market=str(d.get("market", "")),
            trade_time=None if d.get("trade_time") in (None, "") else str(d.get("trade_time")),
            open=float(d.get("open") or 0),
            high=float(d.get("high") or 0),
            low=float(d.get("low") or 0),
            close=float(d.get("close") or 0),
            vol=int(d.get("vol") or 0),
            amount=float(d.get("amount") or 0),
            num=_to_optional_int(d.get("num")),
            pre_close=float(d.get("pre_close") or 0),
            pct_chg=float(d.get("pct_chg") or 0),
            bid=_to_optional_float(d.get("bid")),
            ask=_to_optional_float(d.get("ask")),
            bid_volume1=_to_optional_int(d.get("bid_volume1")),
            ask_volume1=_to_optional_int(d.get("ask_volume1")),
            trade_date=int(d.get("trade_date") or 0),
            collected_at=str(d.get("collected_at", "")),
            version=int(d.get("version") or 0),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts_code": self.ts_code,
            "name": self.name,
            "market": self.market,
            "trade_time": self.trade_time,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "vol": self.vol,
            "amount": self.amount,
            "num": self.num,
            "pre_close": self.pre_close,
            "pct_chg": self.pct_chg,
            "bid": self.bid,
            "ask": self.ask,
            "bid_volume1": self.bid_volume1,
            "ask_volume1": self.ask_volume1,
            "trade_date": self.trade_date,
            "collected_at": self.collected_at,
            "version": self.version,
        }

    @property
    def change_str(self) -> str:
        """格式化涨跌幅字符串"""
        if self.pct_chg > 0:
            return _red(f"+{self.pct_chg:.2f}%")
        elif self.pct_chg < 0:
            return _green(f"{self.pct_chg:.2f}%")
        else:
            return f"{self.pct_chg:.2f}%"

    @property
    def price_str(self) -> str:
        """格式化价格字符串（带涨跌颜色）"""
        if self.pct_chg > 0:
            return _red(f"{self.close:.2f}")
        elif self.pct_chg < 0:
            return _green(f"{self.close:.2f}")
        else:
            return f"{self.close:.2f}"


# ── WebSocket 实时推送服务 ─────────────────────────────────────


class StockWSServer:
    """WebSocket 实时行情推送服务

    后台线程轮询 Receiver 节点 HTTP API，通过 WebSocket 长连接将行情推送给所有连接的客户端。

    订阅管理原则：
      - 如果配置了 JWT Token，数据拉取优先使用 /subscription/latest（服务端按已登记订阅过滤）
      - 客户端发送 subscribe/unsubscribe 指令时，同步到服务端订阅表，保证重启后订阅不丢失
      - 无 JWT 时降级为本地 symbols 过滤模式

    Example:
        server = StockWSServer("http://YOUR_NODE_IP:9100", symbols=["00700.HK", "600519.SH"])
        server.run(port=8765)
    """

    def __init__(
        self,
        node_url: Optional[str] = None,
        token: Optional[str] = None,
        symbols: Optional[List[str]] = None,
        poll_interval: float = 3.0,
        timeout: int = 10,
    ):
        self.node_url = (node_url or os.getenv("STOCK_RT_NODE_URL", "")).rstrip("/")
        # 支持两种 Token：JWT（订阅鉴权）和 Bearer（写入鉴权）
        self.token = token or os.getenv("STOCK_RT_JWT_TOKEN", "") or os.getenv("STOCK_RT_TOKEN", "")
        self.symbols: Set[str] = set(symbols or [])
        self.poll_interval = poll_interval
        self.timeout = timeout
        # 是否使用服务端订阅接口（有 JWT Token 时自动开启）
        self._use_subscription_api: bool = bool(self.token)

        self._session = requests.Session()
        if self.token:
            self._session.headers["Authorization"] = f"Bearer {self.token}"

        self._clients: Set[websockets.server.ServerConnection] = set()
        self._client_symbols: Dict[int, Set[str]] = {}  # ws id -> subscribed symbols
        self._last_versions: Dict[str, int] = {}
        self._latest_ticks: Dict[str, TickData] = {}
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._tick_count = 0
        self._start_time = 0.0

        # 本地回调（终端显示等）
        self._local_callbacks: List[Callable[[str, TickData], None]] = []

        if not self.node_url:
            raise ValueError(
                "需要指定节点地址。设置 STOCK_RT_NODE_URL 环境变量或传入 node_url 参数"
            )

    def add_callback(self, cb: Callable[[str, TickData], None]) -> None:
        """添加本地回调（用于终端显示等）"""
        self._local_callbacks.append(cb)

    def health_check(self) -> Dict[str, Any]:
        """检查节点健康状态"""
        resp = self._session.get(f"{self.node_url}/health", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get_stats(self) -> Dict[str, Any]:
        """获取节点服务状态"""
        resp = self._session.get(f"{self.node_url}/stats", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _sync_subscription_to_server(self, symbols: List[str], mode: str = "add") -> Dict[str, Any]:
        """
        将订阅变更同步到服务端（同步调用，在 executor 中运行）

        参数:
            symbols: 要同步的股票代码列表
            mode: "add" | "remove" | "replace"
        返回: 服务端响应 dict，失败时返回 {"status": "error", "message": ...}
        """
        if not self._use_subscription_api or not symbols:
            return {"status": "skipped"}
        try:
            resp = self._session.post(
                f"{self.node_url}/api/v1/rt-kline/subscription/sync",
                json={"symbols": symbols, "mode": mode},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            result = resp.json()
            logger.info(
                "订阅同步到服务端 mode=%s symbols=%s accepted=%s rejected=%s",
                mode, symbols,
                result.get("accepted_symbols", []),
                result.get("rejected_symbols", []),
            )
            return result
        except Exception as exc:
            logger.warning("订阅同步到服务端失败 mode=%s: %s", mode, exc)
            return {"status": "error", "message": str(exc)}

    def _fetch_latest(self, ts_code: str) -> Optional[TickData]:
        """从 HTTP API 获取单只最新行情"""
        try:
            resp = self._session.get(
                f"{self.node_url}/api/v1/rt-kline/latest",
                params={"ts_code": ts_code},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("data", [])
            return TickData.from_dict(items[0]) if items else None
        except Exception as exc:
            logger.error("获取 %s 行情失败: %s", ts_code, exc)
            return None

    def _fetch_batch(self) -> List[TickData]:
        """
        拉取最新行情。
        - 有 JWT Token：使用 /subscription/latest（服务端按已登记订阅过滤，数据有效性有保证）
        - 无 JWT Token：降级为批量接口 + 本地过滤
        """
        if self._use_subscription_api:
            try:
                resp = self._session.get(
                    f"{self.node_url}/api/v1/rt-kline/subscription/latest",
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                items = data.get("data", [])
                # 同时更新本地 symbols（以服务端登记的订阅为准）
                server_symbols = set(data.get("accepted_symbols") or data.get("registered_symbols") or [])
                if server_symbols:
                    self.symbols = server_symbols
                return [TickData.from_dict(item) for item in items]
            except Exception as exc:
                logger.warning("订阅接口拉取失败，降级为批量接口: %s", exc)
                self._use_subscription_api = False  # 降级后不再重试订阅接口

        # 降级模式：批量拉取全量 + 本地过滤
        try:
            resp = self._session.get(
                f"{self.node_url}/api/v1/rt-kline/latest",
                params={"limit": 5000},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            items = resp.json().get("data", [])
            return [TickData.from_dict(item) for item in items]
        except Exception as exc:
            logger.error("批量拉取行情失败: %s", exc)
            return []

    def _poll_once(self) -> List[TickData]:
        """
        轮询一次所有订阅的 symbol，返回有更新的 tick 列表。

        有效性保证：
          - 使用 /subscription/latest 时，服务端已按登记订阅过滤，不会推送已退订的 symbol
          - 降级模式下，本地 all_symbols 过滤确保只推送已订阅的 symbol
        """
        all_symbols = set(self.symbols)
        for syms in self._client_symbols.values():
            all_symbols |= syms

        # 拉取行情（订阅接口或批量接口）
        all_ticks = self._fetch_batch()

        updated: List[TickData] = []
        for tick in all_ticks:
            # 降级模式下需要本地过滤；订阅接口模式下服务端已过滤，但仍做一层防御
            if all_symbols and tick.ts_code not in all_symbols:
                continue

            last_ver = self._last_versions.get(tick.ts_code, 0)
            if tick.version and tick.version == last_ver:
                continue

            self._last_versions[tick.ts_code] = tick.version
            self._latest_ticks[tick.ts_code] = tick
            updated.append(tick)

        return updated

    async def _broadcast_ticks(self, ticks: List[TickData]) -> None:
        """将 tick 数据推送到所有 WebSocket 连接"""
        if not ticks:
            return

        dead_clients = set()
        for ws in self._clients:
            ws_id = id(ws)
            client_syms = self._client_symbols.get(ws_id)

            for tick in ticks:
                # 如果客户端有自定义订阅列表，只推送其关注的
                if client_syms and tick.ts_code not in client_syms:
                    continue

                msg = json.dumps(
                    {
                        "type": "tick",
                        "timestamp": datetime.now().isoformat(),
                        **tick.to_dict(),
                    },
                    ensure_ascii=False,
                )
                try:
                    await ws.send(msg)
                except Exception:
                    dead_clients.add(ws)
                    break

        # 清理断开的连接
        for ws in dead_clients:
            self._clients.discard(ws)
            self._client_symbols.pop(id(ws), None)
            logger.info("客户端断开连接，剩余 %d 个连接", len(self._clients))

    async def _handle_client(self, ws: websockets.server.ServerConnection) -> None:
        """处理一个 WebSocket 客户端连接"""
        self._clients.add(ws)
        ws_id = id(ws)
        logger.info("新客户端连接，当前 %d 个连接", len(self._clients))

        # 发送欢迎消息
        welcome = {
            "type": "welcome",
            "message": "实时行情 WebSocket 已连接",
            "server_symbols": sorted(self.symbols),
            "poll_interval": self.poll_interval,
            "node_url": self.node_url,
            "timestamp": datetime.now().isoformat(),
            "instructions": {
                "subscribe": '发送 {"action":"subscribe","symbols":["00700.HK"]} 订阅',
                "unsubscribe": '发送 {"action":"unsubscribe","symbols":["00700.HK"]} 取消订阅',
                "snapshot": '发送 {"action":"snapshot"} 获取当前所有最新行情',
                "list": '发送 {"action":"list"} 查看当前订阅列表',
            },
        }
        try:
            await ws.send(json.dumps(welcome, ensure_ascii=False))
        except Exception:
            self._clients.discard(ws)
            return

        # 如果当前没有订阅任何股票，提示用户
        if not self.symbols:
            hint = {
                "type": "notice",
                "message": "当前服务端未订阅任何股票，不会推送行情数据。请发送订阅指令添加股票。",
                "example": {"action": "subscribe", "symbols": ["00700.HK", "600519.SH"]},
                "timestamp": datetime.now().isoformat(),
            }
            try:
                await ws.send(json.dumps(hint, ensure_ascii=False))
            except Exception:
                self._clients.discard(ws)
                return

        # 发送当前最新快照
        if self._latest_ticks:
            snapshot = {
                "type": "snapshot",
                "count": len(self._latest_ticks),
                "data": [t.to_dict() for t in self._latest_ticks.values()],
                "timestamp": datetime.now().isoformat(),
            }
            try:
                await ws.send(json.dumps(snapshot, ensure_ascii=False))
            except Exception:
                self._clients.discard(ws)
                return

        # 监听客户端消息（订阅管理）
        try:
            async for raw_msg in ws:
                try:
                    msg = json.loads(raw_msg)
                    action = msg.get("action", "")

                    if action == "subscribe":
                        new_symbols = set(msg.get("symbols", []))
                        if ws_id not in self._client_symbols:
                            self._client_symbols[ws_id] = set(self.symbols)
                        self._client_symbols[ws_id] |= new_symbols
                        # 同时添加到全局轮询列表
                        self.symbols |= new_symbols

                        # 同步到服务端订阅表（保证重启后订阅不丢失）
                        sync_result: Dict[str, Any] = {}
                        if self._use_subscription_api and new_symbols:
                            sync_result = await asyncio.get_event_loop().run_in_executor(
                                None, self._sync_subscription_to_server, list(new_symbols), "add"
                            )

                        resp = {
                            "type": "subscribed",
                            "added": sorted(new_symbols),
                            "current": sorted(self._client_symbols[ws_id]),
                            "server_sync": sync_result.get("status", "skipped"),
                            "timestamp": datetime.now().isoformat(),
                        }
                        await ws.send(json.dumps(resp, ensure_ascii=False))

                    elif action == "unsubscribe":
                        rm_symbols = set(msg.get("symbols", []))
                        if ws_id in self._client_symbols:
                            self._client_symbols[ws_id] -= rm_symbols

                        # 检查是否还有其他客户端订阅了这些 symbol
                        still_needed = set()
                        for other_id, other_syms in self._client_symbols.items():
                            if other_id != ws_id:
                                still_needed |= other_syms
                        # 只有当前客户端订阅且没有其他客户端订阅时，才从全局列表移除
                        truly_removed = rm_symbols - still_needed - self.symbols
                        # 同步退订到服务端
                        sync_result = {}
                        if self._use_subscription_api and truly_removed:
                            sync_result = await asyncio.get_event_loop().run_in_executor(
                                None, self._sync_subscription_to_server, list(truly_removed), "remove"
                            )

                        resp = {
                            "type": "unsubscribed",
                            "removed": sorted(rm_symbols),
                            "current": sorted(self._client_symbols.get(ws_id, self.symbols)),
                            "server_sync": sync_result.get("status", "skipped"),
                            "timestamp": datetime.now().isoformat(),
                        }
                        await ws.send(json.dumps(resp, ensure_ascii=False))

                    elif action == "snapshot":
                        client_syms = self._client_symbols.get(ws_id)
                        if client_syms:
                            data = [t.to_dict() for s, t in self._latest_ticks.items() if s in client_syms]
                        else:
                            data = [t.to_dict() for t in self._latest_ticks.values()]
                        resp = {
                            "type": "snapshot",
                            "count": len(data),
                            "data": data,
                            "timestamp": datetime.now().isoformat(),
                        }
                        await ws.send(json.dumps(resp, ensure_ascii=False))

                    elif action == "list":
                        resp = {
                            "type": "subscription_list",
                            "symbols": sorted(self._client_symbols.get(ws_id, self.symbols)),
                            "server_symbols": sorted(self.symbols),
                            "timestamp": datetime.now().isoformat(),
                        }
                        await ws.send(json.dumps(resp, ensure_ascii=False))

                    else:
                        resp = {
                            "type": "error",
                            "message": f"未知 action: {action}，支持 subscribe/unsubscribe/snapshot/list",
                        }
                        await ws.send(json.dumps(resp, ensure_ascii=False))

                except json.JSONDecodeError:
                    await ws.send(json.dumps({
                        "type": "error",
                        "message": "无效 JSON 格式",
                    }))

        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._clients.discard(ws)
            self._client_symbols.pop(ws_id, None)
            logger.info("客户端断开，剩余 %d 个连接", len(self._clients))

    async def _poll_loop(self) -> None:
        """后台轮询循环，获取行情并广播"""
        while self._running:
            try:
                updated = await asyncio.get_event_loop().run_in_executor(
                    None, self._poll_once
                )
                if updated:
                    self._tick_count += len(updated)
                    # 推送到 WebSocket 客户端
                    await self._broadcast_ticks(updated)
                    # 触发本地回调
                    for tick in updated:
                        for cb in self._local_callbacks:
                            try:
                                cb(tick.ts_code, tick)
                            except Exception as exc:
                                logger.error("本地回调异常: %s", exc)
            except Exception as exc:
                logger.error("轮询异常: %s", exc)

            await asyncio.sleep(self.poll_interval)

    async def _serve(self, host: str = "0.0.0.0", port: int = 8765) -> None:
        """启动 WebSocket 服务"""
        self._running = True
        self._start_time = time.time()

        # 启动后台轮询
        poll_task = asyncio.create_task(self._poll_loop())

        # 启动 WebSocket 服务器
        async with websockets.serve(self._handle_client, host, port):
            logger.info("WebSocket 服务已启动: ws://%s:%d", host, port)

            # 等待停止信号
            stop_future = asyncio.get_event_loop().create_future()

            def _signal_stop():
                if not stop_future.done():
                    stop_future.set_result(True)

            loop = asyncio.get_event_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, _signal_stop)
                except NotImplementedError:
                    pass  # Windows 不支持

            await stop_future

        self._running = False
        poll_task.cancel()
        try:
            await poll_task
        except asyncio.CancelledError:
            pass

    def run(self, host: str = "0.0.0.0", port: int = 8765) -> None:
        """阻塞运行 WebSocket 服务"""
        asyncio.run(self._serve(host, port))

    def stop(self) -> None:
        """停止服务"""
        self._running = False
        logger.info("WebSocket 服务停止")


# ── 终端显示格式化 ──────────────────────────────────────────────


class TerminalDisplay:
    """终端实时行情显示器"""

    def __init__(self, alert_pct: float = 0.0):
        self.alert_pct = alert_pct
        self._tick_count = 0
        self._start_time = time.time()

    def print_header(self, symbols: List[str], node_url: str, ws_port: int, interval: float) -> None:
        """打印订阅启动头"""
        print()
        print(_bold("╔══════════════════════════════════════════════════════════════╗"))
        print(_bold("║") + _cyan("    📈 实时行情 WebSocket 推送 - Stock RT Subscribe") + _bold("        ║"))
        print(_bold("╠══════════════════════════════════════════════════════════════╣"))
        print(_bold("║") + f"  数据源: {node_url:<50s}" + _bold("║"))
        ws_url = f"ws://localhost:{ws_port}"
        print(_bold("║") + f"  WS地址: {ws_url:<50s}" + _bold("║"))
        print(_bold("║") + f"  标的  : {', '.join(symbols):<50s}" + _bold("║"))
        print(_bold("║") + f"  频率  : 每 {interval:.0f} 秒" + " " * (47 - len(f"每 {interval:.0f} 秒")) + _bold("║"))
        if self.alert_pct > 0:
            alert_str = f"涨跌幅超 ±{self.alert_pct}%"
            print(_bold("║") + f"  告警  : {alert_str:<50s}" + _bold("║"))
        print(_bold("║") + f"  时间  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S'):<50s}" + _bold("║"))
        print(_bold("╠══════════════════════════════════════════════════════════════╣"))
        print(_bold("║") + _dim("  用户连接 WebSocket 即可接收实时行情推送") + " " * 18 + _bold("║"))
        print(_bold("║") + _dim("  按 Ctrl+C 停止服务") + " " * 39 + _bold("║"))
        print(_bold("╚══════════════════════════════════════════════════════════════╝"))
        print()
        # 表头
        print(
            _bold(
                f"{'时间':<12s}  {'代码':<12s}  {'名称':<10s}  "
                f"{'最新价':>10s}  {'涨跌幅':>10s}  {'成交量':>12s}  {'成交额':>14s}"
            )
        )
        print("─" * 90)

    def on_tick(self, symbol: str, tick: TickData) -> None:
        """处理一条 tick 并显示"""
        self._tick_count += 1
        now = datetime.now().strftime("%H:%M:%S")

        # 格式化成交量（万手）
        vol_str = f"{tick.vol / 10000:.1f}万" if tick.vol >= 10000 else str(tick.vol)
        # 格式化成交额（亿）
        if tick.amount >= 1e8:
            amt_str = f"{tick.amount / 1e8:.2f}亿"
        elif tick.amount >= 1e4:
            amt_str = f"{tick.amount / 1e4:.1f}万"
        else:
            amt_str = f"{tick.amount:.0f}"

        # 告警检测
        alert = ""
        if self.alert_pct > 0 and abs(tick.pct_chg) >= self.alert_pct:
            alert = _yellow(" ⚠️ 告警!")

        line = (
            f"{now:<12s}  {tick.ts_code:<12s}  {tick.name:<10s}  "
            f"{tick.price_str:>10s}  {tick.change_str:>10s}  "
            f"{vol_str:>12s}  {amt_str:>14s}{alert}"
        )
        print(line)

    def print_footer(self) -> None:
        """打印结束统计"""
        elapsed = time.time() - self._start_time
        print()
        print("─" * 90)
        print(
            _dim(
                f"服务结束。共推送 {self._tick_count} 条 tick，"
                f"持续 {elapsed:.0f} 秒"
            )
        )


class JsonLineOutput:
    """JSON Lines 输出（文件或 stdout）"""

    def __init__(self, output_path: Optional[str] = None):
        self._file = None
        if output_path:
            self._file = open(output_path, "a", encoding="utf-8")

    def on_tick(self, symbol: str, tick: TickData) -> None:
        line = json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "symbol": symbol,
                **tick.to_dict(),
            },
            ensure_ascii=False,
        )
        if self._file:
            self._file.write(line + "\n")
            self._file.flush()
        else:
            print(line)

    def close(self) -> None:
        if self._file:
            self._file.close()


# ── CLI 入口 ─────────────────────────────────────────────────


def build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="实时股票行情 WebSocket 推送服务 — 从 Receiver 节点获取并通过 WebSocket 长连接推送",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 订阅港股腾讯控股，启动 WebSocket 服务（默认 ws://0.0.0.0:8765）
  %(prog)s --symbols 00700.HK

  # 订阅多只股票
  %(prog)s --symbols 00700.HK 09988.HK 09888.HK 600519.SH

  # 指定 WebSocket 端口和节点
  %(prog)s --ws-port 9900 --node-url http://YOUR_NODE_IP:9100 --symbols 00700.HK

  # 连接 WebSocket 接收数据
  wscat -c ws://localhost:8765
  # 或 Python:
  python3 -c "
  import asyncio, websockets, json
  async def main():
      async with websockets.connect('ws://localhost:8765') as ws:
          async for msg in ws:
              data = json.loads(msg)
              if data.get('type') == 'tick':
                  print(f'{data[\"name\"]} {data[\"close\"]} {data[\"pct_chg\"]}%%')
  asyncio.run(main())
  "

  # 一次性查询模式（不启动 WebSocket）
  %(prog)s --symbols 00700.HK --once

  # 动态订阅：连接后发送 JSON 指令
  # {"action": "subscribe", "symbols": ["00700.HK", "09988.HK"]}
  # {"action": "unsubscribe", "symbols": ["09988.HK"]}
  # {"action": "snapshot"}
  # {"action": "list"}
        """,
    )
    parser.add_argument(
        "--node-url",
        default=os.getenv("STOCK_RT_NODE_URL", ""),
        help="Receiver 节点地址（默认 $STOCK_RT_NODE_URL）",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("STOCK_RT_TOKEN", ""),
        help="鉴权 Token（默认 $STOCK_RT_TOKEN，为空则不鉴权）",
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=[],
        help="要订阅的股票代码列表（如 00700.HK 600519.SH）",
    )
    parser.add_argument(
        "--ws-port",
        type=int,
        default=int(os.getenv("STOCK_WS_PORT", "8765")),
        help="WebSocket 服务端口（默认 8765）",
    )
    parser.add_argument(
        "--ws-host",
        default="0.0.0.0",
        help="WebSocket 监听地址（默认 0.0.0.0）",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=3.0,
        help="数据轮询间隔秒数（默认 3）",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="只查询一次就退出（不启动 WebSocket 服务）",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="安静模式：不显示终端面板（WebSocket 仍正常推送）",
    )
    parser.add_argument(
        "--output", "-o",
        default="",
        help="同时输出到文件（追加 jsonl 格式）",
    )
    parser.add_argument(
        "--alert-pct",
        type=float,
        default=0.0,
        help="涨跌幅告警阈值（如 2.0 表示 ±2%%）",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="HTTP 请求超时秒数（默认 10）",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        help="日志级别（默认 WARNING）",
    )
    return parser.parse_args()


def main() -> int:
    args = build_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.WARNING),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    if not args.node_url:
        print(
            "ERROR: 需要指定节点地址。使用 --node-url 参数或设置 STOCK_RT_NODE_URL 环境变量",
            file=sys.stderr,
        )
        return 1

    if not args.symbols:
        print(
            "ERROR: 需要指定 --symbols（股票代码列表）",
            file=sys.stderr,
        )
        return 1

    # 创建服务
    try:
        server = StockWSServer(
            node_url=args.node_url,
            token=args.token if args.token else None,
            symbols=args.symbols,
            poll_interval=args.interval,
            timeout=args.timeout,
        )
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    # 健康检查
    try:
        health = server.health_check()
        if health.get("status") != "ok":
            print(f"WARNING: 节点状态异常: {health}", file=sys.stderr)
    except Exception as e:
        print(f"ERROR: 无法连接节点 {args.node_url}: {e}", file=sys.stderr)
        return 1

    # ── 一次性查询模式 ──
    if args.once:
        for symbol in args.symbols:
            tick = server._fetch_latest(symbol)
            if tick:
                if args.quiet:
                    print(json.dumps(tick.to_dict(), ensure_ascii=False))
                else:
                    amt_str = f"{tick.amount / 1e8:.2f}亿" if tick.amount >= 1e8 else f"{tick.amount / 1e4:.1f}万"
                    print(
                        f"{tick.ts_code:<12s}  {tick.name:<10s}  {tick.price_str:>10s}  "
                        f"{tick.change_str:>10s}  {amt_str:>14s}"
                    )
        return 0

    # ── WebSocket 持续推送模式 ──

    # 设置本地输出回调
    json_out = None
    display = None

    if not args.quiet:
        display = TerminalDisplay(alert_pct=args.alert_pct)
        server.add_callback(display.on_tick)

    if args.output:
        json_out = JsonLineOutput(args.output)
        server.add_callback(json_out.on_tick)

    # 打印头部
    if display:
        display.print_header(args.symbols, args.node_url, args.ws_port, args.interval)

    # 启动 WebSocket 服务（阻塞）
    try:
        server.run(host=args.ws_host, port=args.ws_port)
    except KeyboardInterrupt:
        pass
    finally:
        if display:
            display.print_footer()
        if json_out:
            json_out.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
