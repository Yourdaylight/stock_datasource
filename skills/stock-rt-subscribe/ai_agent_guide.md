# AI Agent 实时股票数据订阅使用指南

## 概述

`stock-rt-subscribe` skill 为 AI agent 提供实时股票数据订阅能力，通过 WebSocket 长连接接收 A 股、港股、ETF 的实时行情数据。

## 鉴权流程

### 1. 环境变量设置

AI agent 需要引导用户设置以下环境变量：

```bash
# 设置 Receiver 节点地址（必填）
export STOCK_RT_NODE_URL="http://139.155.0.115:9100"

# 设置鉴权 Token（如果需要）
export STOCK_RT_TOKEN="your-access-token-here"

# 设置 WebSocket 端口（可选，默认8765）
export STOCK_WS_PORT="8765"
```

### 2. 鉴权验证

AI agent 可以通过以下方式验证鉴权状态：

```python
import os
import requests

# 检查环境变量
node_url = os.getenv("STOCK_RT_NODE_URL")
token = os.getenv("STOCK_RT_TOKEN")

if not node_url:
    # 引导用户设置节点地址
    print("请设置 STOCK_RT_NODE_URL 环境变量指向 Receiver 节点")
    
# 健康检查
headers = {"Authorization": f"Bearer {token}"} if token else {}
response = requests.get(f"{node_url}/health", headers=headers, timeout=10)

if response.status_code == 200:
    print("✅ 节点连接正常")
elif response.status_code == 401:
    print("❌ 鉴权失败，请检查 STOCK_RT_TOKEN")
else:
    print(f"❌ 节点连接失败: {response.status_code}")
```

## AI Agent 集成方式

### 方式一：启动 WebSocket 服务作为数据源

AI agent 可以启动订阅服务作为后台数据源：

```python
import subprocess
import asyncio
import websockets
import json

# 启动 WebSocket 服务
process = subprocess.Popen([
    "python3", "subscribe_client.py",
    "--node-url", os.getenv("STOCK_RT_NODE_URL"),
    "--symbols", "00700.HK", "600519.SH", "09988.HK",
    "--ws-port", "8765",
    "--interval", "3"
])

# 等待服务启动
import time
time.sleep(2)

# 连接 WebSocket 接收数据
async def receive_stock_data():
    async with websockets.connect("ws://localhost:8765") as ws:
        # 发送订阅指令
        await ws.send(json.dumps({
            "action": "subscribe",
            "symbols": ["00700.HK", "600519.SH"]
        }))
        
        # 持续接收数据
        async for message in ws:
            data = json.loads(message)
            if data.get("type") == "tick":
                # 处理实时数据
                print(f"📈 {data['name']}: {data['close']} 元 ({data['pct_chg']}%)")
                
                # AI agent 可以在这里进行数据分析、决策等
                if data['pct_chg'] > 2.0:
                    print(f"⚠️  {data['name']} 涨幅超过 2%")

# 运行数据接收
asyncio.run(receive_stock_data())
```

### 方式二：直接调用 API 获取数据

对于不需要实时推送的场景，AI agent 可以直接调用 API：

```python
import requests
import os

def get_stock_snapshot(symbols):
    """获取股票最新快照数据"""
    node_url = os.getenv("STOCK_RT_NODE_URL")
    token = os.getenv("STOCK_RT_TOKEN")
    
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    
    results = []
    for symbol in symbols:
        response = requests.get(
            f"{node_url}/api/v1/rt-kline/latest",
            params={"ts_code": symbol},
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("data"):
                results.append(data["data"][0])
    
    return results

# 使用示例
snapshot = get_stock_snapshot(["00700.HK", "600519.SH"])
for stock in snapshot:
    print(f"{stock['name']}: {stock['close']} 元 ({stock['pct_chg']}%)")
```

## 动态订阅管理

AI agent 可以动态管理订阅列表：

```python
async def manage_subscriptions(ws):
    """动态订阅管理"""
    
    # 添加订阅
    await ws.send(json.dumps({
        "action": "subscribe",
        "symbols": ["09888.HK", "09618.HK"]  # 百度、京东
    }))
    
    # 取消订阅
    await ws.send(json.dumps({
        "action": "unsubscribe", 
        "symbols": ["09988.HK"]  # 取消阿里
    }))
    
    # 获取当前订阅列表
    await ws.send(json.dumps({"action": "list"}))
    
    # 获取最新快照
    await ws.send(json.dumps({"action": "snapshot"}))
```

## 数据分析和告警

AI agent 可以基于实时数据进行智能分析：

```python
class StockAnalyzer:
    def __init__(self, alert_threshold=2.0):
        self.alert_threshold = alert_threshold
        self.price_history = {}
        
    def analyze_tick(self, tick_data):
        """分析单条tick数据"""
        symbol = tick_data["ts_code"]
        current_price = tick_data["close"]
        pct_change = tick_data["pct_chg"]
        
        # 记录价格历史
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        self.price_history[symbol].append(current_price)
        
        # 涨跌幅告警
        if abs(pct_change) >= self.alert_threshold:
            direction = "大涨" if pct_change > 0 else "大跌"
            return f"⚠️ {tick_data['name']} {direction}: {pct_change:.2f}%"
        
        # 趋势分析（简单移动平均）
        if len(self.price_history[symbol]) >= 5:
            recent_prices = self.price_history[symbol][-5:]
            avg_price = sum(recent_prices) / len(recent_prices)
            trend = "上升" if current_price > avg_price else "下降"
            return f"📊 {tick_data['name']} 短期趋势: {trend}"
        
        return None

# 使用示例
analyzer = StockAnalyzer(alert_threshold=1.5)

async def process_data_with_ai(ws):
    async for message in ws:
        data = json.loads(message)
        if data.get("type") == "tick":
            analysis = analyzer.analyze_tick(data)
            if analysis:
                print(f"🤖 AI分析: {analysis}")
```

## 错误处理和重连机制

```python
async def robust_websocket_client():
    """带错误处理和重连的WebSocket客户端"""
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            async with websockets.connect("ws://localhost:8765") as ws:
                retry_count = 0  # 重置重试计数
                
                # 连接成功后的处理
                await ws.send(json.dumps({"action": "subscribe", "symbols": ["00700.HK"]}))
                
                async for message in ws:
                    # 处理数据...
                    pass
                    
        except Exception as e:
            retry_count += 1
            print(f"连接失败，第{retry_count}次重试: {e}")
            await asyncio.sleep(5)  # 等待5秒后重试
    
    print("❌ 连接失败，达到最大重试次数")
```

## 最佳实践

1. **鉴权安全**: 引导用户通过环境变量设置敏感信息，避免硬编码
2. **错误处理**: 实现重连机制，处理网络异常
3. **资源管理**: 及时关闭连接，避免资源泄漏
4. **数据过滤**: 根据AI agent的需求动态调整订阅列表
5. **性能优化**: 合理设置轮询间隔，避免过度请求

## 故障排除

- **连接失败**: 检查STOCK_RT_NODE_URL和网络连接
- **鉴权错误**: 验证STOCK_RT_TOKEN是否正确
- **无数据**: 确认当前是否为交易时间
- **服务未启动**: 确保subscribe_client.py已正确启动

通过这个skill，AI agent可以轻松获取实时股票数据，为投资决策、市场分析等场景提供数据支持。