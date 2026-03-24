#!/usr/bin/env python3
"""
AI Agent 实时股票数据订阅集成接口
====================================

为AI agent提供统一的接口来使用stock-rt-subscribe skill，
包含鉴权引导、订阅管理、数据接收和统计分析功能。

订阅管理设计原则：
  - 所有订阅变更（新增/退订/替换）必须先同步到服务端，再更新本地 WebSocket 推送列表
  - 服务端 /subscription/sync 是订阅状态的唯一权威来源
  - 本地 WebSocket 推送列表始终从服务端拉取，保证重启后订阅不丢失
  - 数据拉取优先使用 /subscription/latest（按服务端登记的订阅），保证数据有效性

使用示例:
    from ai_agent_integration import StockDataAgent
    
    # 创建AI agent实例
    agent = StockDataAgent()
    
    # 引导用户设置鉴权
    agent.guide_authentication()
    
    # 启动订阅服务（同时同步到服务端）
    agent.start_subscription(['00700.HK', '600519.SH'])
    
    # 动态新增订阅
    agent.add_symbols(['600519.SH'])
    
    # 动态退订
    agent.remove_symbols(['00700.HK'])
    
    # 接收并分析数据
    agent.analyze_realtime_data(duration=60)
"""

import os
import asyncio
import json
import logging
import subprocess
import time
import websockets
import requests
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from collections import defaultdict

# 导入交易策略引擎
try:
    from strategy_engine import StrategyEngine, SIGNAL_BUY, SIGNAL_SELL, SIGNAL_HOLD
    _STRATEGY_AVAILABLE = True
except ImportError:
    _STRATEGY_AVAILABLE = False
    logger_placeholder = logging.getLogger("stock-rt-agent")
    logger_placeholder.warning("strategy_engine.py 未找到，策略分析功能不可用")

# subscribe_client.py 与本文件同目录
_SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_SKILL_DIR, "..", ".."))
_SUBSCRIBE_CLIENT = os.path.join(_SKILL_DIR, "subscribe_client.py")

logger = logging.getLogger("stock-rt-agent")


def logger_print(msg: str) -> None:
    """同时输出到 logger 和 stdout（方便 AI agent 直接看到日志）"""
    logger.info(msg)
    print(msg)


class StockDataAgent:
    """AI Agent 股票数据集成类"""
    
    def __init__(self, ws_port: int = 8765, poll_interval: float = 3.0):
        self.ws_port = ws_port
        self.poll_interval = poll_interval
        self.subscription_process = None
        self.is_running = False
        self.data_callback = None
        self.stock_history = defaultdict(list)
        self._session = requests.Session()
        # 当前已同步到服务端的订阅列表（本地缓存，以服务端为准）
        self._server_symbols: List[str] = []
        # 交易策略引擎（实时信号生成）
        self.strategy_engine: Optional["StrategyEngine"] = (
            StrategyEngine() if _STRATEGY_AVAILABLE else None
        )
        if self.strategy_engine:
            # 注册控制台通知回调
            self.strategy_engine.add_notify_callback(self._on_strategy_signal)
        
    def guide_authentication(self) -> bool:
        """
        引导用户完成鉴权设置
        返回: True 如果节点可达（鉴权通过或无需鉴权）
        """
        print("🔐 股票数据订阅鉴权引导")
        print("=" * 50)
        
        # 检查节点地址
        node_url = os.getenv("STOCK_RT_NODE_URL", "").rstrip("/")
        if not node_url:
            print("❌ 未设置 STOCK_RT_NODE_URL 环境变量")
            print("💡 请执行以下命令设置节点地址:")
            print("   export STOCK_RT_NODE_URL=\"http://139.155.0.115:9100\"")
            return False
        
        print(f"✅ 节点地址: {node_url}")
        
        # 检查 Token（可选，用于写入鉴权，普通查询可不填）
        token = os.getenv("STOCK_RT_TOKEN", "")
        if token:
            # 设置到 session，后续 HTTP 请求自动携带
            self._session.headers["Authorization"] = f"Bearer {token}"
            print(f"✅ 鉴权Token已设置: {token[:10]}...")
        else:
            print("ℹ️  未设置 STOCK_RT_TOKEN（只读查询无需 Token）")
        
        # 测试节点连通性
        try:
            response = self._session.get(f"{node_url}/health", timeout=10)
            
            if response.status_code == 200:
                health_data = response.json()
                status = health_data.get("status", "unknown")
                print(f"✅ 节点连接正常 - 状态: {status}")
                # 打印节点统计信息（如有）
                if "total_symbols" in health_data:
                    print(f"   可用标的数: {health_data['total_symbols']}")
                return True
            elif response.status_code == 401:
                print("❌ 鉴权失败，请检查 STOCK_RT_TOKEN 是否正确")
                print("💡 请联系管理员获取有效 Token，并执行:")
                print("   export STOCK_RT_TOKEN=\"your_token_here\"")
                return False
            else:
                print(f"❌ 节点连接失败: HTTP {response.status_code}")
                return False
                
        except requests.exceptions.ConnectionError:
            print(f"❌ 无法连接到节点 {node_url}，请检查网络或节点地址")
            return False
        except Exception as e:
            print(f"❌ 连接异常: {e}")
            return False
    
    def _get_node_url(self) -> str:
        return os.getenv("STOCK_RT_NODE_URL", "").rstrip("/")

    def _get_jwt_token(self) -> str:
        """获取 JWT Token（用于订阅鉴权）"""
        return os.getenv("STOCK_RT_JWT_TOKEN", os.getenv("STOCK_RT_TOKEN", ""))

    def _auth_headers(self) -> Dict[str, str]:
        """返回带 JWT 鉴权的请求头"""
        token = self._get_jwt_token()
        if token:
            return {"Authorization": f"Bearer {token}"}
        return {}

    def sync_subscription(self, symbols: List[str], mode: str = "replace") -> Dict[str, Any]:
        """
        将订阅列表同步到服务端（唯一权威来源）
        
        参数:
            symbols: 股票代码列表
            mode: 同步模式
                  - "replace": 替换全部订阅（默认）
                  - "add":     在现有基础上新增
                  - "remove":  从现有订阅中退订
        返回: 服务端返回的同步结果
        """
        node_url = self._get_node_url()
        if not node_url:
            return {"error": "未设置 STOCK_RT_NODE_URL"}

        try:
            resp = self._session.post(
                f"{node_url}/api/v1/rt-kline/subscription/sync",
                json={"symbols": symbols, "mode": mode},
                headers=self._auth_headers(),
                timeout=10,
            )
            resp.raise_for_status()
            result = resp.json()
            # 更新本地缓存
            self._server_symbols = result.get("accepted_symbols", [])
            return result
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            msg = ""
            try:
                msg = e.response.json().get("message", "") if e.response is not None else ""
            except Exception:
                pass
            return {"error": f"HTTP {status}: {msg or str(e)}"}
        except Exception as e:
            return {"error": str(e)}

    def list_subscription(self) -> Dict[str, Any]:
        """
        从服务端查询当前已登记的订阅列表
        返回: {subscribed_symbols, current_subscriptions, max_subs, ...}
        """
        node_url = self._get_node_url()
        if not node_url:
            return {"error": "未设置 STOCK_RT_NODE_URL"}
        try:
            resp = self._session.get(
                f"{node_url}/api/v1/rt-kline/subscription/list",
                headers=self._auth_headers(),
                timeout=10,
            )
            resp.raise_for_status()
            result = resp.json()
            self._server_symbols = result.get("subscribed_symbols", [])
            return result
        except Exception as e:
            return {"error": str(e)}

    def add_symbols(self, symbols: List[str]) -> Dict[str, Any]:
        """
        动态新增订阅（先同步服务端，再通知本地 WebSocket 服务）
        
        参数:
            symbols: 要新增的股票代码列表
        返回: 同步结果
        """
        print(f"➕ 新增订阅: {', '.join(symbols)}")
        result = self.sync_subscription(symbols, mode="add")
        if "error" in result:
            print(f"❌ 服务端同步失败: {result['error']}")
            return result

        accepted = result.get("accepted_symbols", [])
        rejected = result.get("rejected_symbols", [])
        print(f"✅ 服务端已接受: {accepted}")
        if rejected:
            print(f"⚠️  被拒绝的 symbol: {rejected}")

        # 通知本地 WebSocket 服务动态增加推送
        if self.is_running and accepted:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._ws_subscribe(accepted))
            except RuntimeError:
                asyncio.run(self._ws_subscribe(accepted))

        return result

    def remove_symbols(self, symbols: List[str]) -> Dict[str, Any]:
        """
        动态退订（先同步服务端，再通知本地 WebSocket 服务停止推送）
        
        参数:
            symbols: 要退订的股票代码列表
        返回: 同步结果
        """
        print(f"➖ 退订: {', '.join(symbols)}")
        result = self.sync_subscription(symbols, mode="remove")
        if "error" in result:
            print(f"❌ 服务端同步失败: {result['error']}")
            return result

        removed = symbols
        print(f"✅ 服务端已退订: {removed}")
        print(f"📋 当前订阅: {result.get('accepted_symbols', [])}")

        # 通知本地 WebSocket 服务停止推送
        if self.is_running and removed:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._ws_unsubscribe(removed))
            except RuntimeError:
                asyncio.run(self._ws_unsubscribe(removed))

        return result

    async def _ws_subscribe(self, symbols: List[str]) -> None:
        """向本地 WebSocket 服务发送 subscribe 指令"""
        try:
            async with websockets.connect(
                f"ws://localhost:{self.ws_port}", open_timeout=3
            ) as ws:
                await ws.send(json.dumps({"action": "subscribe", "symbols": symbols}))
                resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
                logger_print(f"WS subscribe 响应: {resp.get('type')} current={resp.get('current', [])}")
        except Exception as e:
            logger_print(f"⚠️  WS subscribe 通知失败（服务端已同步，不影响数据）: {e}")

    async def _ws_unsubscribe(self, symbols: List[str]) -> None:
        """向本地 WebSocket 服务发送 unsubscribe 指令"""
        try:
            async with websockets.connect(
                f"ws://localhost:{self.ws_port}", open_timeout=3
            ) as ws:
                await ws.send(json.dumps({"action": "unsubscribe", "symbols": symbols}))
                resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
                logger_print(f"WS unsubscribe 响应: {resp.get('type')} current={resp.get('current', [])}")
        except Exception as e:
            logger_print(f"⚠️  WS unsubscribe 通知失败（服务端已同步，不影响数据）: {e}")

    def _fetch_batch_latest(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """
        批量拉取多个 symbol 的最新行情（一次 HTTP 请求）
        优先使用 /subscription/latest（按服务端登记的订阅），保证数据有效性
        返回: tick 数据列表
        """
        node_url = self._get_node_url()
        if not node_url:
            return []
        try:
            # 优先使用订阅接口（服务端按已登记的订阅过滤，数据更准确）
            jwt_token = self._get_jwt_token()
            if jwt_token:
                resp = self._session.get(
                    f"{node_url}/api/v1/rt-kline/subscription/latest",
                    headers=self._auth_headers(),
                    timeout=10,
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("data", [])

            # 无 JWT 时降级为批量接口 + 本地过滤
            resp = self._session.get(
                f"{node_url}/api/v1/rt-kline/latest",
                params={"limit": 2000},
                timeout=10,
            )
            resp.raise_for_status()
            items = resp.json().get("data", [])
            symbol_set = set(symbols)
            return [item for item in items if item.get("ts_code") in symbol_set]
        except Exception:
            return []

    def start_subscription(self, symbols: List[str], alert_threshold: float = 0.0) -> bool:
        """
        启动WebSocket订阅服务（后台子进程）
        流程：先将订阅列表同步到服务端，再启动本地 WebSocket 推送服务
        返回: True 如果服务启动成功
        """
        if not self.guide_authentication():
            return False
        
        print(f"🚀 启动股票订阅服务")
        print(f"📈 订阅标的: {', '.join(symbols)}")

        # ── Step 1: 先将订阅同步到服务端 ──
        jwt_token = self._get_jwt_token()
        if jwt_token:
            print("🔄 同步订阅列表到服务端...")
            result = self.sync_subscription(symbols, mode="replace")
            if "error" in result:
                print(f"⚠️  服务端订阅同步失败（将使用本地模式）: {result['error']}")
            else:
                accepted = result.get("accepted_symbols", [])
                rejected = result.get("rejected_symbols", [])
                print(f"✅ 服务端已接受订阅: {accepted}")
                if rejected:
                    print(f"⚠️  被拒绝的 symbol: {rejected}")
                # 以服务端接受的为准
                symbols = accepted if accepted else symbols
        else:
            print("ℹ️  未设置 JWT Token，跳过服务端订阅同步（使用本地模式）")
        
        # 检查 subscribe_client.py 是否存在
        if not os.path.isfile(_SUBSCRIBE_CLIENT):
            print(f"❌ 找不到 subscribe_client.py: {_SUBSCRIBE_CLIENT}")
            return False
        
        try:
            # 构建启动命令（使用绝对路径，避免 cwd 依赖）
            cmd = [
                "python3", _SUBSCRIBE_CLIENT,
                "--node-url", os.getenv("STOCK_RT_NODE_URL", "").rstrip("/"),
                "--symbols", *symbols,
                "--ws-port", str(self.ws_port),
                "--interval", str(self.poll_interval),
                "--quiet",  # 不显示终端面板，WebSocket 仍正常推送
            ]
            
            # 添加 Token（如果设置）
            token = os.getenv("STOCK_RT_TOKEN", "")
            if token:
                cmd.extend(["--token", token])
            
            # 添加告警阈值
            if alert_threshold > 0:
                cmd.extend(["--alert-pct", str(alert_threshold)])
            
            # 启动后台进程（不依赖 cwd）
            self.subscription_process = subprocess.Popen(
                cmd,
                cwd=_PROJECT_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            
            # 等待服务启动
            time.sleep(3)
            
            # 检查服务是否正常启动
            if self.subscription_process.poll() is not None:
                stderr_output = self.subscription_process.stderr.read().decode("utf-8", errors="replace")
                print(f"❌ 订阅服务启动失败")
                if stderr_output:
                    print(f"   错误信息: {stderr_output[:200]}")
                return False
            
            self.is_running = True
            print(f"✅ 订阅服务已启动 (PID: {self.subscription_process.pid})")
            print(f"🌐 WebSocket地址: ws://localhost:{self.ws_port}")
            return True
            
        except Exception as e:
            print(f"❌ 启动订阅服务失败: {e}")
            return False
    
    def stop_subscription(self):
        """停止订阅服务"""
        if self.subscription_process:
            print("🛑 停止订阅服务...")
            self.subscription_process.terminate()
            try:
                self.subscription_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.subscription_process.kill()
            self.is_running = False
            print("✅ 订阅服务已停止")
    
    def set_data_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """设置数据接收回调函数"""
        self.data_callback = callback
    
    async def receive_realtime_data(self, duration: int = 30, 
                                   on_tick: Optional[Callable] = None) -> Dict[str, List]:
        """
        接收实时数据并返回分析结果
        参数:
            duration: 接收数据时长（秒）
            on_tick: 每收到一条数据的回调函数
        返回: 股票历史数据字典
        """
        if not self.is_running:
            print("⚠️  订阅服务未启动，请先调用 start_subscription()")
            return {}
        
        print(f"📡 开始接收实时数据 ({duration}秒)...")
        
        try:
            async with websockets.connect(f"ws://localhost:{self.ws_port}") as ws:
                # 发送订阅指令（接收服务端默认订阅的所有 symbol）
                await ws.send(json.dumps({
                    "action": "subscribe",
                    "symbols": []
                }))
                
                start_time = time.time()
                message_count = 0
                
                while time.time() - start_time < duration:
                    try:
                        message = await asyncio.wait_for(ws.recv(), timeout=5)
                        data = json.loads(message)
                        
                        if data.get("type") == "tick":
                            symbol = data.get("ts_code", "")
                            if symbol:
                                self.stock_history[symbol].append(data)
                                message_count += 1
                                
                                # 调用回调函数
                                if on_tick:
                                    on_tick(data)
                                if self.data_callback:
                                    self.data_callback(data)
                                
                                # 显示进度
                                if message_count % 10 == 0:
                                    print(f"📊 已接收 {message_count} 条行情数据...")
                                    
                    except asyncio.TimeoutError:
                        continue
                    except Exception as e:
                        print(f"⚠️  数据处理异常: {e}")
                        continue
                
                print(f"✅ 数据接收完成，共接收 {message_count} 条数据")
                return dict(self.stock_history)
                
        except Exception as e:
            print(f"❌ 数据接收失败: {e}")
            return {}
    
    def _on_strategy_signal(self, symbol: str, result: Dict[str, Any]) -> None:
        """
        策略引擎信号回调 — 信号生成时自动触发
        负责控制台打印 + 可扩展飞书/钉钉推送
        """
        signal = result.get("signal", SIGNAL_HOLD)
        price = result.get("price", 0)
        reasons = result.get("reasons", [])
        t = result.get("time", "")
        emoji = {SIGNAL_BUY: "🟢 买入", SIGNAL_SELL: "🔴 卖出"}.get(signal, "⚪ 持仓")

        print(f"\n{'='*55}")
        print(f"📊 交易信号  [{t}]")
        print(f"   标的: {symbol}   信号: {emoji}   价格: {price}")
        for r in reasons:
            print(f"   └─ {r}")
        print(f"{'='*55}")

        # ── 可扩展：飞书/钉钉 Webhook 推送 ──
        # webhook_url = os.getenv("NOTIFY_WEBHOOK_URL", "")
        # if webhook_url:
        #     self._send_webhook(webhook_url, symbol, signal, price, reasons)

    def analyze_stock_changes(self, stock_data: Dict[str, List]) -> Dict[str, Any]:
        """
        分析股票数据变化，并通过策略引擎生成交易信号

        流程：
          1. 基础统计分析（价格变化、波动率等）
          2. 将历史 tick 逐条喂给策略引擎，生成技术指标和交易信号
          3. 将策略信号合并到分析结果中返回
        """
        if not stock_data:
            return {"error": "无数据可分析"}

        analysis_result = {}

        for symbol, data_list in stock_data.items():
            if len(data_list) < 2:
                analysis_result[symbol] = {"status": "数据不足，无法分析"}
                continue

            # 防御性字段访问，避免 KeyError
            prices = [float(d.get("close") or 0) for d in data_list]
            changes = [float(d.get("pct_chg") or 0) for d in data_list]

            # 过滤掉价格为 0 的无效数据
            valid_pairs = [(p, c) for p, c in zip(prices, changes) if p > 0]
            if len(valid_pairs) < 2:
                analysis_result[symbol] = {"status": "有效数据不足，无法分析"}
                continue

            prices = [p for p, _ in valid_pairs]
            changes = [c for _, c in valid_pairs]

            # ── 基础统计 ──
            initial_price = prices[0]
            latest_price = prices[-1]
            total_change = latest_price - initial_price
            total_change_pct = (total_change / initial_price) * 100 if initial_price else 0
            max_change = max(changes)
            min_change = min(changes)
            avg_change = sum(changes) / len(changes)
            volatility = sum((c - avg_change) ** 2 for c in changes) / len(changes)

            result = {
                "name": data_list[0].get("name", "Unknown"),
                "initial_price": round(initial_price, 2),
                "latest_price": round(latest_price, 2),
                "total_change": round(total_change, 2),
                "total_change_pct": round(total_change_pct, 2),
                "max_change": round(max_change, 2),
                "min_change": round(min_change, 2),
                "avg_change": round(avg_change, 2),
                "volatility": round(volatility, 4),
                "data_points": len(data_list),
                "trend": "上涨" if total_change > 0 else "下跌" if total_change < 0 else "持平",
            }

            # ── 策略引擎分析 ──
            if self.strategy_engine:
                last_signal = None
                for tick in data_list:
                    sig = self.strategy_engine.on_tick(symbol, tick)
                    if sig:
                        last_signal = sig

                # 获取最终信号
                final_signal = (
                    last_signal or self.strategy_engine.get_latest_signal(symbol)
                )
                indicators = self.strategy_engine.get_indicators(symbol)
                history = self.strategy_engine.get_signal_history(symbol, n=3)

                result["strategy"] = {
                    "signal": final_signal["signal"] if final_signal else SIGNAL_HOLD,
                    "price": final_signal["price"] if final_signal else latest_price,
                    "reasons": final_signal["reasons"] if final_signal else [],
                    "indicators": indicators,
                    "recent_signals": history,
                }
            else:
                result["strategy"] = {"signal": SIGNAL_HOLD, "reasons": ["策略引擎未加载"]}

            analysis_result[symbol] = result

        return analysis_result
    
    def print_analysis_report(self, analysis_result: Dict[str, Any]):
        """打印分析报告（含策略信号）"""
        print("\n" + "=" * 60)
        print("📊 AI Agent 股票数据分析报告")
        print("=" * 60)

        for symbol, analysis in analysis_result.items():
            if "error" in analysis or "status" in analysis:
                print(f"\n{symbol}: {analysis.get('error', analysis.get('status'))}")
                continue

            print(f"\n📈 {symbol} ({analysis['name']}):")
            print(f"   趋势: {analysis['trend']}")
            print(f"   初始价格: {analysis['initial_price']}")
            print(f"   最新价格: {analysis['latest_price']}")
            print(f"   总变化: {analysis['total_change']:+.2f} ({analysis['total_change_pct']:+.2f}%)")
            print(f"   数据点数: {analysis['data_points']}")
            print(f"   最大涨跌: {analysis['max_change']:+.2f}%")
            print(f"   最小涨跌: {analysis['min_change']:+.2f}%")
            print(f"   平均涨跌: {analysis['avg_change']:+.2f}%")
            print(f"   波动率: {analysis['volatility']:.4f}")

            # 打印策略信号
            strategy = analysis.get("strategy", {})
            if strategy:
                sig = strategy.get("signal", SIGNAL_HOLD)
                sig_emoji = {SIGNAL_BUY: "🟢 买入", SIGNAL_SELL: "🔴 卖出", SIGNAL_HOLD: "⚪ 持仓"}.get(sig, "⚪")
                print(f"   策略信号: {sig_emoji}")
                for r in strategy.get("reasons", []):
                    print(f"      └─ {r}")
                # 打印技术指标
                ind = strategy.get("indicators", {})
                if ind:
                    ind_str = "  ".join(
                        f"{k}={v:.2f}" for k, v in ind.items()
                        if v is not None and isinstance(v, (int, float)) and k != "data_points"
                    )
                    if ind_str:
                        print(f"   指标: {ind_str}")
                # 打印近期历史信号
                recent = strategy.get("recent_signals", [])
                if recent:
                    print(f"   近期信号:")
                    for rec in recent[-3:]:
                        r_emoji = {SIGNAL_BUY: "🟢", SIGNAL_SELL: "🔴"}.get(rec.get("signal", ""), "⚪")
                        print(f"      {r_emoji} {rec.get('time','')}  {rec.get('signal','')}  @{rec.get('price','')}")

        print("\n" + "=" * 60)

        # 打印全局信号日志摘要
        if self.strategy_engine:
            summary = self.strategy_engine.get_log_summary()
            if summary:
                print("\n📋 交易信号日志摘要（trading_log.json）")
                print("-" * 60)
                for sym, s in summary.items():
                    sig_emoji = {SIGNAL_BUY: "🟢", SIGNAL_SELL: "🔴"}.get(s.get("last_signal", ""), "⚪")
                    print(f"   {sym}: 最新={sig_emoji}{s['last_signal']}@{s['last_price']}  "
                          f"时间={s['last_time']}  "
                          f"总计={s['total_signals']}次(买{s['buy_count']}/卖{s['sell_count']})")
                print("-" * 60)
    
    async def complete_workflow(self, symbols: List[str], duration: int = 60):
        """
        完整的AI agent工作流程
        1. 鉴权引导
        2. 启动订阅
        3. 接收数据
        4. 分析数据
        5. 生成报告
        """
        print("🤖 AI Agent 股票数据订阅工作流启动")
        print("=" * 50)
        
        # 步骤1: 鉴权引导（已在 start_subscription 内调用，此处单独展示）
        if not self.guide_authentication():
            return
        
        # 步骤2: 启动订阅
        if not self.start_subscription(symbols):
            return
        
        # 步骤3: 接收数据
        def on_tick_callback(data):
            """实时数据回调 — 同时喂给策略引擎做实时信号判断"""
            symbol = data.get("ts_code", "")
            price = float(data.get("close") or 0)
            change = float(data.get("pct_chg") or 0)

            # 大幅波动告警
            if abs(change) > 2.0:
                print(f"⚠️  {symbol} 大幅波动: {change:+.2f}%")

            # 实时策略信号（信号触发时会自动调用 _on_strategy_signal 打印通知）
            if self.strategy_engine and symbol:
                self.strategy_engine.on_tick(symbol, data)
        
        stock_data = await self.receive_realtime_data(duration, on_tick_callback)
        
        # 步骤4: 分析数据
        analysis_result = self.analyze_stock_changes(stock_data)
        
        # 步骤5: 生成报告
        self.print_analysis_report(analysis_result)
        
        # 步骤6: 停止服务
        self.stop_subscription()
        
        print("✅ AI Agent 工作流完成")


# 使用示例
async def demo():
    """演示如何使用AI agent接口"""
    agent = StockDataAgent()
    
    # 订阅港股和A股
    symbols = ["00700.HK", "09988.HK", "600519.SH", "000001.SZ"]
    
    # 运行完整工作流
    await agent.complete_workflow(symbols, duration=30)


if __name__ == "__main__":
    # 运行演示
    asyncio.run(demo())