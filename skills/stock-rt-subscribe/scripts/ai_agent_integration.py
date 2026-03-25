#!/usr/bin/env python3
"""
AI Agent 实时股票数据订阅集成接口
====================================

为AI agent提供统一的接口来使用stock-rt-subscribe skill，
包含鉴权引导、订阅管理、数据接收和告警统计功能。

订阅管理设计原则：
  - 所有订阅变更（新增/退订/替换）必须先同步到服务端，再更新本地 WebSocket 推送列表
  - 服务端 /subscription/sync 是订阅状态的唯一权威来源
  - 本地 WebSocket 推送列表始终从服务端拉取，保证重启后订阅不丢失
  - 数据拉取优先使用 /subscription/latest（按服务端登记的订阅），保证数据有效性

数据流：
  实时 tick → AlertEngine.on_tick()
                  ├── 匹配用户策略条件（strategy_config.json）
                  ├── 需要MCP辅助时 → _mcp_fetch_for_alert() → 节点 HTTP API
                  └── 条件满足 → 触发告警（控制台/日志/Webhook）

使用示例:
    from ai_agent_integration import StockDataAgent

    agent = StockDataAgent()
    agent.guide_authentication()
    agent.start_subscription(['00700.HK', '600519.SH'])
    agent.add_symbols(['600519.SH'])
    agent.remove_symbols(['00700.HK'])
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
from datetime import datetime, date, timedelta
from collections import defaultdict

# 导入告警引擎
try:
    from alert_engine import AlertEngine
    _ALERT_ENGINE_AVAILABLE = True
except ImportError:
    _ALERT_ENGINE_AVAILABLE = False
    logging.getLogger("stock-rt-agent").warning("alert_engine.py 未找到，告警功能不可用")

# subscribe_client.py 与本文件同目录
_SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_SKILL_DIR, "..", ".."))
_SUBSCRIBE_CLIENT = os.path.join(_SKILL_DIR, "subscribe_client.py")
_ENV_FILE = os.path.join(_SKILL_DIR, ".env")

# 默认 MCP 服务地址
_DEFAULT_MCP_URL = "http://s1.jqcloudnet.cn:8001/mcp"

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
        self.stock_history: Dict[str, List] = defaultdict(list)
        self._session = requests.Session()
        # 当前已同步到服务端的订阅列表（本地缓存，以服务端为准）
        self._server_symbols: List[str] = []

        # 启动时自动加载 .env
        self._load_env()

        # 告警引擎
        self.alert_engine: Optional["AlertEngine"] = (
            AlertEngine() if _ALERT_ENGINE_AVAILABLE else None
        )
        if self.alert_engine:
            # 注入 MCP 数据拉取函数
            self.alert_engine.set_mcp_fetch_fn(self._mcp_fetch_for_alert)

    # ── .env 配置管理 ──────────────────────────────────────────────────────

    def _load_env(self) -> None:
        """从 .env 文件加载环境变量（不覆盖已有的系统环境变量）"""
        if not os.path.exists(_ENV_FILE):
            return
        try:
            with open(_ENV_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, val = line.partition("=")
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    # 不覆盖已有的系统环境变量
                    if key and key not in os.environ:
                        os.environ[key] = val
            logger.debug(f".env 已加载: {_ENV_FILE}")
        except Exception as e:
            logger.warning(f"加载 .env 失败: {e}")

    def _save_env(self, kvs: Dict[str, str]) -> None:
        """将键值对写入 .env 文件（追加或更新已有 key）"""
        existing: Dict[str, str] = {}
        lines: List[str] = []
        if os.path.exists(_ENV_FILE):
            with open(_ENV_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#") and "=" in stripped:
                        k, _, _ = stripped.partition("=")
                        existing[k.strip()] = line
                    lines.append(line)

        # 更新已有 key 或追加新 key
        for key, val in kvs.items():
            entry = f'{key}="{val}"\n'
            if key in existing:
                lines = [entry if l == existing[key] else l for l in lines]
            else:
                lines.append(entry)

        with open(_ENV_FILE, "w", encoding="utf-8") as f:
            f.writelines(lines)

    def _prompt_config(self) -> bool:
        """
        交互式引导用户配置 .env 文件
        询问：节点地址、Token、MCP 地址
        返回: True 表示配置完成
        """
        print("\n⚙️  股票数据订阅 — 初始化配置")
        print("=" * 50)
        print(f"配置将保存到: {_ENV_FILE}")
        print("直接回车使用括号内的默认值\n")

        kvs: Dict[str, str] = {}

        # 节点地址
        cur_node = os.getenv("STOCK_RT_NODE_URL", "")
        prompt_node = f"节点地址 [{cur_node or 'http://139.155.0.115:9100'}]: "
        val = input(prompt_node).strip()
        if not val:
            val = cur_node or "http://139.155.0.115:9100"
        kvs["STOCK_RT_NODE_URL"] = val.rstrip("/")
        os.environ["STOCK_RT_NODE_URL"] = kvs["STOCK_RT_NODE_URL"]

        # JWT Token（可选）
        cur_token = os.getenv("STOCK_RT_TOKEN", "")
        prompt_token = f"JWT Token（可选，只读查询留空）[{cur_token[:10] + '...' if cur_token else '留空'}]: "
        val = input(prompt_token).strip()
        if val:
            kvs["STOCK_RT_TOKEN"] = val
            os.environ["STOCK_RT_TOKEN"] = val
        elif cur_token:
            kvs["STOCK_RT_TOKEN"] = cur_token

        # MCP 服务地址
        cur_mcp = os.getenv("STOCK_MCP_URL", _DEFAULT_MCP_URL)
        prompt_mcp = f"MCP 服务地址 [{cur_mcp}]: "
        val = input(prompt_mcp).strip()
        if not val:
            val = cur_mcp
        kvs["STOCK_MCP_URL"] = val.rstrip("/")
        os.environ["STOCK_MCP_URL"] = kvs["STOCK_MCP_URL"]

        self._save_env(kvs)
        print(f"\n✅ 配置已保存到 {_ENV_FILE}")
        return True

    def reconfigure(self) -> bool:
        """强制重新配置（覆盖现有 .env），适合更新 MCP 地址等场景"""
        return self._prompt_config()

    def install(self) -> bool:
        """
        安装 stock-rt-subscribe skill

        执行步骤：
          1. 检查 Python 依赖（requirements）是否已安装
          2. 若 .env 不存在则引导用户完成初始化配置
          3. 验证节点连通性
          4. 验证 MCP 服务可达性（可选）
          5. 打印安装成功摘要

        返回: True 表示安装成功，False 表示安装失败
        """
        print("\n📦 stock-rt-subscribe skill 安装向导")
        print("=" * 55)

        # ── Step 1: 检查 Python 依赖 ──────────────────────────────
        print("\n[1/4] 检查 Python 依赖...")
        skill_json_path = os.path.join(_SKILL_DIR, "skill.json")
        requirements: List[str] = []
        try:
            with open(skill_json_path, "r", encoding="utf-8") as f:
                skill_meta = json.load(f)
            requirements = skill_meta.get("requirements", [])
        except Exception:
            requirements = ["requests", "websockets"]

        missing: List[str] = []
        for pkg in requirements:
            pkg_name = pkg.split(">=")[0].split("==")[0].strip()
            try:
                __import__(pkg_name.replace("-", "_"))
            except ImportError:
                missing.append(pkg)

        if missing:
            print(f"   ⚠️  缺少依赖: {', '.join(missing)}")
            print(f"   正在安装...")
            try:
                result = subprocess.run(
                    ["pip3", "install", *missing],
                    capture_output=True, text=True, timeout=120,
                )
                if result.returncode == 0:
                    print(f"   ✅ 依赖安装成功: {', '.join(missing)}")
                else:
                    print(f"   ❌ 依赖安装失败:\n{result.stderr[:300]}")
                    print(f"   💡 请手动执行: pip3 install {' '.join(missing)}")
                    return False
            except Exception as e:
                print(f"   ❌ 安装异常: {e}")
                print(f"   💡 请手动执行: pip3 install {' '.join(missing)}")
                return False
        else:
            print(f"   ✅ 依赖已满足: {', '.join(requirements)}")

        # ── Step 2: 初始化配置 ─────────────────────────────────────
        print("\n[2/4] 检查配置文件...")
        if not os.path.exists(_ENV_FILE):
            print(f"   ⚠️  未找到配置文件 {_ENV_FILE}")
            print("   启动初始化配置向导...\n")
            if not self._prompt_config():
                print("   ❌ 配置初始化失败")
                return False
        else:
            self._load_env()
            print(f"   ✅ 已加载配置文件: {_ENV_FILE}")
            node_url = os.getenv("STOCK_RT_NODE_URL", "")
            mcp_url = os.getenv("STOCK_MCP_URL", _DEFAULT_MCP_URL)
            print(f"      节点地址: {node_url or '(未设置)'}")
            print(f"      MCP 地址: {mcp_url}")

        # ── Step 3: 验证节点连通性 ─────────────────────────────────
        print("\n[3/4] 验证节点连通性...")
        node_url = os.getenv("STOCK_RT_NODE_URL", "").rstrip("/")
        if not node_url:
            print("   ❌ STOCK_RT_NODE_URL 未设置，跳过连通性验证")
            print("   💡 请在 .env 中设置节点地址后重新运行 install()")
            return False

        try:
            token = os.getenv("STOCK_RT_TOKEN", "")
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            resp = self._session.get(f"{node_url}/health", headers=headers, timeout=10)
            if resp.status_code == 200:
                health = resp.json()
                print(f"   ✅ 节点连接正常 — 状态: {health.get('status', 'ok')}")
                if "total_symbols" in health:
                    print(f"      可用标的数: {health['total_symbols']}")
            elif resp.status_code == 401:
                print("   ⚠️  节点需要鉴权，请确认 STOCK_RT_TOKEN 已正确设置")
            else:
                print(f"   ⚠️  节点响应异常: HTTP {resp.status_code}（安装继续）")
        except Exception as e:
            print(f"   ⚠️  节点连接失败: {e}（安装继续，运行时需确保节点可达）")

        # ── Step 4: 验证 MCP 服务可达性 ───────────────────────────
        print("\n[4/4] 验证 MCP 服务可达性...")
        mcp_url = self._get_mcp_url()
        try:
            # 发送 initialize 探测请求
            resp = self._session.post(
                mcp_url,
                json={"jsonrpc": "2.0", "id": 0, "method": "initialize",
                      "params": {"protocolVersion": "2024-11-05",
                                 "capabilities": {},
                                 "clientInfo": {"name": "stock-rt-install", "version": "1.0"}}},
                headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
                timeout=8,
            )
            if resp.status_code in (200, 201):
                print(f"   ✅ MCP 服务可达: {mcp_url}")
            else:
                print(f"   ⚠️  MCP 服务响应: HTTP {resp.status_code}（安装继续）")
        except Exception as e:
            print(f"   ⚠️  MCP 服务暂不可达: {e}（安装继续，MCP辅助功能运行时按需连接）")

        # ── 安装成功摘要 ───────────────────────────────────────────
        print("\n" + "=" * 55)
        print("🎉 stock-rt-subscribe skill 安装完成！")
        print("=" * 55)
        print(f"   配置文件 : {_ENV_FILE}")
        print(f"   节点地址 : {os.getenv('STOCK_RT_NODE_URL', '(未设置)')}")
        print(f"   MCP 地址 : {self._get_mcp_url()}")
        print(f"   告警引擎 : {'✅ 已加载' if self.alert_engine else '⚠️  未加载（alert_engine.py 缺失）'}")
        print()
        print("📖 快速开始:")
        print("   from ai_agent_integration import StockDataAgent")
        print("   agent = StockDataAgent()")
        print("   import asyncio")
        print("   asyncio.run(agent.complete_workflow(['00700.HK', '600519.SH'], duration=60))")
        print("=" * 55 + "\n")
        return True

    # ── 鉴权 ────────────────────────────────────────────────────────────────

    def guide_authentication(self) -> bool:
        """
        引导用户完成鉴权设置
        若 .env 不存在则自动触发配置引导
        返回: True 如果节点可达（鉴权通过或无需鉴权）
        """
        print("🔐 股票数据订阅鉴权引导")
        print("=" * 50)

        node_url = os.getenv("STOCK_RT_NODE_URL", "").rstrip("/")
        if not node_url:
            print("⚠️  未检测到节点配置，启动初始化向导...")
            if not self._prompt_config():
                return False
            node_url = os.getenv("STOCK_RT_NODE_URL", "").rstrip("/")
        if not node_url:
            print("❌ 节点地址仍未设置，请手动在 .env 中添加 STOCK_RT_NODE_URL")
            return False

        print(f"✅ 节点地址: {node_url}")

        token = os.getenv("STOCK_RT_TOKEN", "")
        if token:
            self._session.headers["Authorization"] = f"Bearer {token}"
            print(f"✅ 鉴权Token已设置: {token[:10]}...")
        else:
            print("ℹ️  未设置 STOCK_RT_TOKEN（只读查询无需 Token）")

        try:
            response = self._session.get(f"{node_url}/health", timeout=10)
            if response.status_code == 200:
                health_data = response.json()
                print(f"✅ 节点连接正常 - 状态: {health_data.get('status', 'unknown')}")
                if "total_symbols" in health_data:
                    print(f"   可用标的数: {health_data['total_symbols']}")
                return True
            elif response.status_code == 401:
                print("❌ 鉴权失败，请检查 STOCK_RT_TOKEN 是否正确")
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

    # ── 内部工具 ─────────────────────────────────────────────────────────────

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

    # ── MCP JSON-RPC 调用 ────────────────────────────────────────────────────

    def _get_mcp_url(self) -> str:
        """获取 MCP 服务地址（优先环境变量，其次默认值）"""
        return os.getenv("STOCK_MCP_URL", _DEFAULT_MCP_URL).rstrip("/")

    def _mcp_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        timeout: int = 15,
    ) -> Optional[Any]:
        """
        通过 Streamable HTTP JSON-RPC 调用 MCP 工具

        协议：POST {mcp_url}  Content-Type: application/json
        请求体：标准 JSON-RPC 2.0 tools/call 格式
        返回：工具返回的 content[0].text 解析后的对象，失败返回 None
        """
        mcp_url = self._get_mcp_url()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }
        try:
            resp = self._session.post(
                mcp_url,
                json=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
                timeout=timeout,
            )
            resp.raise_for_status()

            # 兼容 SSE（text/event-stream）和普通 JSON 两种响应格式
            content_type = resp.headers.get("Content-Type", "")
            if "text/event-stream" in content_type:
                # 从 SSE 流中提取第一个 data: 行
                raw = ""
                for line in resp.text.splitlines():
                    if line.startswith("data:"):
                        raw = line[5:].strip()
                        break
                if not raw:
                    return None
                body = json.loads(raw)
            else:
                body = resp.json()

            # 解析 JSON-RPC 响应
            if "error" in body:
                logger.warning(f"MCP 工具调用错误 [{tool_name}]: {body['error']}")
                return None

            result = body.get("result", {})
            content = result.get("content", [])
            if content and isinstance(content, list):
                text = content[0].get("text", "")
                try:
                    return json.loads(text)
                except (json.JSONDecodeError, TypeError):
                    return text
            return result

        except Exception as e:
            logger.warning(f"MCP 调用失败 [{tool_name}]: {e}")
            return None

    # ── MCP 辅助数据拉取（注入给 AlertEngine）────────────────────────────────

    def _mcp_fetch_for_alert(
        self,
        symbol: str,
        source: str,
        fields: List[str],
        lookback_days: int,
        compute: str,
    ) -> Optional[Dict[str, Any]]:
        """
        为 AlertEngine 拉取 MCP 辅助数据（历史均量、N日高点等）

        通过 MCP JSON-RPC 调用 tushare_daily_get_daily_data 获取历史日线，
        并按 compute 类型计算结果：
          - avg_vol_5d : 近 lookback_days 日平均成交量
          - high_20d   : 近 lookback_days 日最高价

        返回: {compute_key: value} 或 None（拉取失败时）
        """
        # 计算日期范围（向前推 lookback_days 个自然日，留足余量）
        end_dt = date.today()
        start_dt = end_dt - timedelta(days=lookback_days * 2 + 10)  # 多取一些，过滤非交易日
        end_date = end_dt.strftime("%Y%m%d")
        start_date = start_dt.strftime("%Y%m%d")

        # 根据 source 选择 MCP 工具
        if source == "tushare_daily":
            tool = "tushare_daily_get_daily_data"
            args = {"code": symbol, "start_date": start_date, "end_date": end_date}
        else:
            # 默认也走 tushare_daily
            tool = "tushare_daily_get_daily_data"
            args = {"code": symbol, "start_date": start_date, "end_date": end_date}

        result = self._mcp_call(tool, args)
        if not result:
            return None

        # result 可能是 list（行列表）或 dict（含 data 字段）
        rows: List[Dict[str, Any]] = []
        if isinstance(result, list):
            rows = result
        elif isinstance(result, dict):
            rows = result.get("data", result.get("rows", []))

        if not rows:
            return None

        # 只取最近 lookback_days 条（按 trade_date 降序取前 N）
        rows_sorted = sorted(
            rows,
            key=lambda r: str(r.get("trade_date") or r.get("date") or ""),
            reverse=True,
        )[:lookback_days]

        if compute == "avg_vol_5d":
            vols = [float(r.get("vol") or 0) for r in rows_sorted if r.get("vol")]
            if not vols:
                return None
            return {"avg_vol_5d": sum(vols) / len(vols)}

        elif compute == "high_20d":
            highs = [float(r.get("high") or 0) for r in rows_sorted if r.get("high")]
            if not highs:
                return None
            return {"high_20d": max(highs)}

        return None

    # ── 订阅管理 ─────────────────────────────────────────────────────────────

    def sync_subscription(self, symbols: List[str], mode: str = "replace") -> Dict[str, Any]:
        """
        将订阅列表同步到服务端（唯一权威来源）

        参数:
            symbols: 股票代码列表
            mode: "replace" | "add" | "remove"
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
        """从服务端查询当前已登记的订阅列表"""
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
        """动态新增订阅（先同步服务端，再通知本地 WebSocket 服务）"""
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

        if self.is_running and accepted:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._ws_subscribe(accepted))
            except RuntimeError:
                asyncio.run(self._ws_subscribe(accepted))

        return result

    def remove_symbols(self, symbols: List[str]) -> Dict[str, Any]:
        """动态退订（先同步服务端，再通知本地 WebSocket 服务停止推送）"""
        print(f"➖ 退订: {', '.join(symbols)}")
        result = self.sync_subscription(symbols, mode="remove")
        if "error" in result:
            print(f"❌ 服务端同步失败: {result['error']}")
            return result

        print(f"✅ 服务端已退订: {symbols}")
        print(f"📋 当前订阅: {result.get('accepted_symbols', [])}")

        if self.is_running and symbols:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._ws_unsubscribe(symbols))
            except RuntimeError:
                asyncio.run(self._ws_unsubscribe(symbols))

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
        """
        node_url = self._get_node_url()
        if not node_url:
            return []
        try:
            jwt_token = self._get_jwt_token()
            if jwt_token:
                resp = self._session.get(
                    f"{node_url}/api/v1/rt-kline/subscription/latest",
                    headers=self._auth_headers(),
                    timeout=10,
                )
                resp.raise_for_status()
                return resp.json().get("data", [])

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

    # ── 订阅服务启停 ──────────────────────────────────────────────────────────

    def start_subscription(self, symbols: List[str], alert_threshold: float = 0.0) -> bool:
        """
        启动WebSocket订阅服务（后台子进程）
        流程：先将订阅列表同步到服务端，再启动本地 WebSocket 推送服务
        """
        if not self.guide_authentication():
            return False

        print(f"🚀 启动股票订阅服务")
        print(f"📈 订阅标的: {', '.join(symbols)}")

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
                symbols = accepted if accepted else symbols
        else:
            print("ℹ️  未设置 JWT Token，跳过服务端订阅同步（使用本地模式）")

        if not os.path.isfile(_SUBSCRIBE_CLIENT):
            print(f"❌ 找不到 subscribe_client.py: {_SUBSCRIBE_CLIENT}")
            return False

        try:
            cmd = [
                "python3", _SUBSCRIBE_CLIENT,
                "--node-url", os.getenv("STOCK_RT_NODE_URL", "").rstrip("/"),
                "--symbols", *symbols,
                "--ws-port", str(self.ws_port),
                "--interval", str(self.poll_interval),
                "--quiet",
            ]

            token = os.getenv("STOCK_RT_TOKEN", "")
            if token:
                cmd.extend(["--token", token])

            if alert_threshold > 0:
                cmd.extend(["--alert-pct", str(alert_threshold)])

            self.subscription_process = subprocess.Popen(
                cmd,
                cwd=_PROJECT_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            time.sleep(3)

            if self.subscription_process.poll() is not None:
                stderr_output = self.subscription_process.stderr.read().decode("utf-8", errors="replace")
                print(f"❌ 订阅服务启动失败")
                if stderr_output:
                    print(f"   错误信息: {stderr_output[:200]}")
                return False

            self.is_running = True
            print(f"✅ 订阅服务已启动 (PID: {self.subscription_process.pid})")
            print(f"🌐 WebSocket地址: ws://localhost:{self.ws_port}")

            # 打印当前告警策略摘要
            if self.alert_engine:
                self.alert_engine.print_strategies_summary()

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

    # ── 数据接收 ─────────────────────────────────────────────────────────────

    async def receive_realtime_data(
        self, duration: int = 30, on_tick: Optional[Callable] = None
    ) -> Dict[str, List]:
        """
        接收实时数据并返回历史数据字典
        参数:
            duration: 接收数据时长（秒）
            on_tick:  每收到一条数据的回调函数
        """
        if not self.is_running:
            print("⚠️  订阅服务未启动，请先调用 start_subscription()")
            return {}

        print(f"📡 开始接收实时数据 ({duration}秒)...")

        try:
            async with websockets.connect(f"ws://localhost:{self.ws_port}") as ws:
                await ws.send(json.dumps({"action": "subscribe", "symbols": []}))

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

                                if on_tick:
                                    on_tick(data)
                                if self.data_callback:
                                    self.data_callback(data)

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

    # ── 告警统计报告 ──────────────────────────────────────────────────────────

    def print_alert_report(self) -> None:
        """打印告警统计报告（触发次数 + 近期告警）"""
        print("\n" + "=" * 60)
        print("� 告警统计报告")
        print("=" * 60)

        if not self.alert_engine:
            print("⚠️  告警引擎未加载")
            return

        all_alerts = self.alert_engine.get_alert_log(n=500)
        if not all_alerts:
            print("ℹ️  本次运行未触发任何告警")
            print("=" * 60)
            return

        # 按策略统计触发次数
        strategy_counter: Dict[str, int] = defaultdict(int)
        symbol_counter: Dict[str, int] = defaultdict(int)
        for a in all_alerts:
            strategy_counter[a.get("strategy_name", "未知")] += 1
            symbol_counter[a.get("symbol", "未知")] += 1

        print(f"\n📊 共触发告警 {len(all_alerts)} 次")

        print("\n  按策略统计:")
        for name, cnt in sorted(strategy_counter.items(), key=lambda x: -x[1]):
            print(f"    {name}: {cnt} 次")

        print("\n  按标的统计:")
        for sym, cnt in sorted(symbol_counter.items(), key=lambda x: -x[1]):
            print(f"    {sym}: {cnt} 次")

        # 近期 5 条告警
        recent = all_alerts[-5:]
        print(f"\n  近期 {len(recent)} 条告警:")
        for a in recent:
            print(f"    [{a['time']}] {a['strategy_name']} — {a['message']}")

        print("\n" + "=" * 60)

    # ── 完整工作流 ────────────────────────────────────────────────────────────

    async def complete_workflow(self, symbols: List[str], duration: int = 60):
        """
        完整的AI agent工作流程
        1. 鉴权引导
        2. 启动订阅（同步服务端 + 打印策略摘要）
        3. 接收数据（每条 tick 喂给 AlertEngine）
        4. 打印告警统计报告
        5. 停止服务
        """
        print("🤖 AI Agent 股票数据订阅工作流启动")
        print("=" * 50)

        if not self.guide_authentication():
            return

        if not self.start_subscription(symbols):
            return

        def on_tick_callback(data: Dict[str, Any]) -> None:
            """实时数据回调 — 每条 tick 喂给 AlertEngine 做条件匹配"""
            symbol = data.get("ts_code", "")
            if not symbol:
                return

            # 喂给告警引擎（内部自动匹配策略、冷却、输出告警）
            if self.alert_engine:
                self.alert_engine.on_tick(symbol, data)

        stock_data = await self.receive_realtime_data(duration, on_tick_callback)

        # 打印告警统计报告
        self.print_alert_report()

        self.stop_subscription()
        print("✅ AI Agent 工作流完成")


# 使用示例
async def demo():
    """演示如何使用AI agent接口"""
    agent = StockDataAgent()
    symbols = ["00700.HK", "09988.HK", "600519.SH", "000001.SZ"]
    await agent.complete_workflow(symbols, duration=30)


if __name__ == "__main__":
    asyncio.run(demo())