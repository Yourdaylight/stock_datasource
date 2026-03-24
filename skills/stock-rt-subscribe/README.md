# Stock Real-time Subscribe Skill

## 📈 实时股票数据订阅技能

为AI agent提供实时A股、港股、ETF行情数据订阅能力，通过WebSocket长连接实现秒级数据推送。

### 🎯 核心功能

- **实时行情订阅**: 支持A股、港股、ETF的秒级行情数据
- **WebSocket推送**: 长连接持续推送，支持多客户端连接
- **动态订阅管理**: 连接后可动态添加/删除订阅标的
- **智能告警**: 涨跌幅阈值告警，实时风险监控
- **统计分析**: 内置数据分析和投资建议生成
- **AI agent集成**: 专为AI agent设计的统一接口

### 🏗️ 架构设计

```
  Receiver Node (HTTP API)         subscribe_client.py             AI Agent
  ┌─────────────────────┐     ┌──────────────────────────┐     ┌────────────────┐
  │ /api/v1/rt-kline/   │────▶│  后台轮询 HTTP → 解析    │────▶│ WebSocket 客户端│
  │  latest?ts_code=... │     │  WebSocket 推送给所有连接 │     │ (AI Agent)    │
  └─────────────────────┘     └──────────────────────────┘     └────────────────┘
                                ws://localhost:8765
```

## 🚀 快速开始

### 环境准备

1. **安装依赖**
```bash
pip install requests websockets
```

2. **设置环境变量**
```bash
# 必填: Receiver节点地址
export STOCK_RT_NODE_URL="http://139.155.0.115:9100"

# 可选: 鉴权Token
export STOCK_RT_TOKEN="your-token-here"

# 可选: WebSocket端口
export STOCK_WS_PORT="8765"
```

### 基础使用

#### 1. 启动WebSocket服务
```bash
cd skills/stock-rt-subscribe
python3 subscribe_client.py --symbols 00700.HK 600519.SH
```

#### 2. 连接WebSocket接收数据
```bash
# 使用wscat命令行工具
wscat -c ws://localhost:8765

# 或运行示例客户端
python3 examples.py 2
```

## 🤖 AI Agent 集成

### 统一接口使用

```python
from ai_agent_integration import StockDataAgent

# 创建AI agent实例
agent = StockDataAgent()

# 引导用户鉴权
if agent.guide_authentication():
    # 启动订阅服务
    symbols = ["00700.HK", "600519.SH", "09988.HK"]
    agent.start_subscription(symbols)
    
    # 接收实时数据
    async def on_tick(data):
        print(f"📈 {data['name']}: {data['close']}元 ({data['pct_chg']}%)")
    
    stock_data = await agent.receive_realtime_data(
        duration=60, 
        on_tick=on_tick
    )
    
    # 分析数据
    analysis = agent.analyze_stock_changes(stock_data)
    agent.print_analysis_report(analysis)
    
    # 停止服务
    agent.stop_subscription()
```

### 完整工作流演示

运行AI agent演示脚本:
```bash
python3 ai_agent_demo.py
```

演示流程包括:
1. ✅ 鉴权引导和系统设置
2. ✅ 股票选择和建议
3. ✅ 实时数据订阅启动
4. ✅ 智能数据分析和告警
5. ✅ 投资建议生成
6. ✅ 资源清理和报告输出

## 📊 数据格式

### WebSocket消息格式

#### 欢迎消息
```json
{
    "type": "welcome",
    "message": "实时行情WebSocket已连接",
    "server_symbols": ["00700.HK", "600519.SH"],
    "poll_interval": 3.0,
    "instructions": {
        "subscribe": "发送{'action':'subscribe','symbols':[...]}订阅",
        "unsubscribe": "发送{'action':'unsubscribe','symbols':[...]}取消订阅",
        "snapshot": "发送{'action':'snapshot'}获取当前所有最新行情",
        "list": "发送{'action':'list'}查看当前订阅列表"
    }
}
```

#### 实时行情数据
```json
{
    "type": "tick",
    "timestamp": "2026-03-20T15:30:00.123456",
    "ts_code": "00700.HK",
    "name": "腾讯控股",
    "market": "hk",
    "open": 445.0,
    "high": 452.0,
    "low": 443.0,
    "close": 450.0,
    "vol": 12345678,
    "amount": 5678901234.0,
    "pre_close": 448.0,
    "pct_chg": 0.45,
    "trade_date": 20260320,
    "collected_at": "2026-03-20T15:30:00",
    "version": 42
}
```

## 🔧 高级功能

### 动态订阅管理

连接后发送JSON指令动态管理订阅:

```json
// 添加订阅
{"action": "subscribe", "symbols": ["09888.HK", "09618.HK"]}

// 取消订阅
{"action": "unsubscribe", "symbols": ["09988.HK"]}

// 获取快照
{"action": "snapshot"}

// 查看订阅列表
{"action": "list"}
```

### 告警配置

```bash
# 设置涨跌幅告警阈值
python3 subscribe_client.py --symbols 00700.HK --alert-pct 2.0

# AI agent中设置
agent.start_subscription(symbols, alert_threshold=2.0)
```

### 数据输出选项

```bash
# 安静模式（适合管道处理）
python3 subscribe_client.py --symbols 00700.HK --quiet

# 输出到JSONL文件
python3 subscribe_client.py --symbols 00700.HK --output ticks.jsonl

# 一次性查询（不启动WebSocket）
python3 subscribe_client.py --symbols 00700.HK --once
```

## 📁 文件结构

```
skills/stock-rt-subscribe/
├── SKILL.md                 # 技能详细文档
├── skill.json               # AI agent技能配置
├── subscribe_client.py      # 核心订阅服务
├── examples.py              # 使用示例
├── ai_agent_integration.py  # AI agent统一接口
├── ai_agent_demo.py         # AI agent演示脚本
├── ai_agent_guide.md        # AI agent使用指南
└── README.md               # 本文件
```

## 🛠️ 故障排除

### 常见问题

**Q: 连接失败，提示"无法连接到节点"**
A: 检查STOCK_RT_NODE_URL是否正确，网络连接是否正常

**Q: 鉴权失败，HTTP 401错误**
A: 验证STOCK_RT_TOKEN是否正确设置

**Q: 无数据推送**
A: 确认当前是否为交易时间（A股9:30-15:00，港股9:30-16:00）

**Q: WebSocket连接被拒绝**
A: 确保subscribe_client.py已正确启动，端口未被占用

**Q: 股票代码无效**
A: 使用完整代码格式：上交所`600519.SH`，深交所`000001.SZ`，港股`00700.HK`

### 调试模式

```bash
# 启用详细日志
export LOG_LEVEL=DEBUG
python3 subscribe_client.py --symbols 00700.HK

# 或使用--log-level参数
python3 subscribe_client.py --symbols 00700.HK --log-level DEBUG
```

## 📈 性能优化

### 轮询间隔调整

根据需求调整数据更新频率:
```bash
# 高频更新（1秒）
python3 subscribe_client.py --symbols 00700.HK --interval 1.0

# 低频更新（5秒）
python3 subscribe_client.py --symbols 00700.HK --interval 5.0
```

### 连接数限制

默认支持多客户端连接，可根据需要调整:
```python
# 在代码中调整最大连接数
server = StockWSServer(node_url=..., symbols=...)
server.max_connections = 10  # 默认无限制
```

## 🤝 贡献指南

欢迎贡献代码和提出建议！

1. Fork本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request

## 📄 许可证

本项目采用MIT许可证 - 查看LICENSE文件了解详情

## 🙏 致谢

感谢所有贡献者和用户的支持！

---

**💡 提示**: 使用前请确保已获得相关数据使用权限，遵守相关法律法规。