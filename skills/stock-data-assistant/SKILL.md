---
name: stock-data-assistant
description: >
  统一的股票数据助手 Skill，整合：
  (1) 数据查询 — 通过 MCP 协议查询历史 K 线、财务报表等（A 股/港股/ETF/指数）；
  (2) 实时搜索 — 通过 WebSocket 订阅实时行情推送（每 3~5 秒更新）；
  (3) 微信联动 — 通过 picoclaw + WeChat Channel 实现微信端操作数据库和订阅实时数据。
  触发此 Skill 时会自动下载 picoclaw、复用项目 LLM 配置、启动微信登录。
---

# Stock Data Assistant（股票数据统一助手）

整合 **历史数据查询**、**实时行情搜索** 和 **微信联动** 三大能力的统一 Skill。

## 架构总览

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   微信用户    │────▶│  picoclaw     │────▶│ stock-mcp (8001) │
│  (WeChat)   │     │  (LLM Gateway)│     │  历史数据查询     │
└─────────────┘     │  port:18790  │     ├─────────────────┤
                    │  微信 Channel │     │  WS (8765)       │
┌─────────────┐     │              │────▶│  实时行情推送     │
│  Web 前端    │────▶│  MCP Client  │     └─────────────────┘
│  (18080)    │     └──────────────┘
└─────────────┘
```

## 核心能力

| 能力 | 协议 | 端口 | 说明 |
|------|------|------|------|
| 历史数据查询 | MCP (streamable-http) | 8001 | K线/财务/指数/ETF 等 |
| 实时行情推送 | WebSocket | 8765 | A股/港股/ETF 逐笔 |
| 微信交互 | picoclaw WeChat Channel | — | 自然语言 → MCP 工具调用 |

## 快速开始

### 一键启动

```bash
bash skills/stock-data-assistant/start_wechat_bridge.sh
```

该命令会依次完成：

1. **检查/下载 picoclaw** — 自动检测系统架构，从 GitHub Releases 下载
2. **生成配置** — 从 `.env` 读取 LLM 配置，生成 `picoclaw.yaml`
3. **启动 picoclaw** — 启动 Gateway (18790) + 微信 Channel
4. **启动实时订阅** — 启动 WebSocket 推送服务 (8765)

### 微信登录

```bash
# 显示微信登录二维码（扫码后即绑定）
.local/bin/picoclaw auth weixin

# 或者使用完整路径
./.local/bin/picoclaw auth weixin
```

扫码成功后，在微信中直接发消息即可操作股票数据。

### 微信对话示例

```
📱 你: 查一下贵州茅台最近的日K线
🤖 AI: 正在为您查询贵州茅台(600519.SH)的日线数据...

📱 你: 腾讯控股现在价格多少？
🤖 AI: 腾讯控股(00700.HK) 当前价 XXX.XX 港元，涨幅 X.XX%

📱 你: 监控 00700.HK 涨跌超过2%就通知我
🤖 AI: 已设置涨跌幅告警，触发条件：±2.00%

📱 你: 列出今天涨幅最大的10只A股
🤖 AI: 正在筛选今日涨幅榜 Top 10...
```

## 手动分步操作

### Step 1: 安装 picoclaw

```bash
bash skills/stock-data-assistant/setup_picoclaw.sh
# 或指定版本
bash skills/stock-data-assistant/setup_picoclaw.sh v0.2.5
```

### Step 2: 生成 picoclaw 配置

```bash
python3 skills/stock-data-assistant/generate_picoclaw_config.py
# 自定义参数
python3 skills/stock-data-assistant/generate_picoclaw_config.py \
    --mcp-token sk-your-token-here \
    --output ./my-config.yaml
```

### Step 3: 启动 picoclaw

```bash
export PATH=".local/bin:$PATH"
picoclaw run --config .local/picoclaw.yaml
```

### Step 4: 登录微信

```bash
picoclaw auth weixin
```

## 配置说明

### LLM 配置（自动从 .env 复用）

配置生成器会自动读取以下环境变量：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OPENAI_API_KEY` | API 密钥 | *(必填)* |
| `OPENAI_BASE_URL` | API 端点 | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | 模型名称 | `gpt-4` |

### MCP Server 配置

| 变量 | 说明 |
|------|------|
| `STOCK_MCP_SERVER_URL` | MCP 服务地址（默认 `http://localhost:8001/messages`） |
| `STOCK_MCP_TOKEN` | MCP 认证令牌 |

### 生成的配置文件结构

见 [references/picoclaw_config_example.yaml](references/picoclaw_config_example.yaml)

## 管理命令

```bash
# 查看状态
bash skills/stock-data-assistant/start_wechat_bridge.sh --status

# 停止所有服务
bash skills/stock-data-assistant/start_wechat_bridge.sh --stop

# 仅启动（不启用实时订阅）
bash skills/stock-data-assistant/start_wechat_bridge.sh --no-rt

# 指定订阅股票
bash skills/stock-data-assistant/start_wechat_bridge.sh --symbols 00700.HK,600519.SH
```

## MCP 工具一览（通过微信可用）

picoclaw 通过 MCP 协议连接到 stock_datasource 后，以下工具在微信中均可使用：

### K 线数据
- `tushare_daily_get_daily_data` — 日 K 线 (OHLCV)
- `tushare_daily_get_latest_daily` — 最新交易日数据
- `akshare_hk_*` — 港股日线数据

### 基本面
- `tushare_daily_basic_get_daily_basic` — PE/PB/市值等指标
- `tushare_balancesheet_*` — 资产负债表
- `tushare_income_*` — 利润表
- `tushare_cashflow_*` — 现金流量表

### 指数与 ETF
- `tushare_index_*` — 指数数据
- `tushare_fund_*` — ETF 数据

### 市场
- `tushare_trade_cal_get_cal` — 交易日历

> 完整工具列表可通过 MCP `tools/list` 接口动态获取（约 76+ 个工具）

## 实时数据（WebSocket）

通过 `skills/stock-rt-subscribe` 提供，支持：

- **实时推送**: 每 3~5 秒更新行情
- **多市场**: A 股 / 港股 / ETF
- **告警策略**: 涨停跌停、大幅波动、量能异动、价格突破

详细文档: [../stock-rt-subscribe/SKILL.md](../stock-rt-subscribe/SKILL.md)

## 目录结构

```
skills/stock-data-assistant/
├── SKILL.md                              # 本文档
├── setup_picoclaw.sh                     # 自动下载 picoclaw
├── generate_picoclaw_config.py           # 从 .env 生成配置
├── start_wechat_bridge.sh                # 一键启动脚本
└── references/
    └── picoclaw_config_example.yaml     # 配置示例
```

## 故障排查

| 问题 | 解决方案 |
|------|----------|
| picoclaw 下载失败 | 检查网络/代理；或手动从 GitHub 下载放入 `.local/bin/` |
| `OPENAI_API_KEY not set` | 确保 `.env` 文件中有 `OPENAI_API_KEY` 字段 |
| `API key required` (MCP) | 设置 `STOCK_MCP_TOKEN` 环境变量或编辑配置文件 |
| 微信二维码过期 | 重新运行 `picoclaw auth weixin` |
| 实时数据无推送 | 检查 `subscribe_client.py` 是否正常运行，端口 8765 是否可达 |
| picoclaw 无法调用 MCP 工具 | 确认 MCP 服务 (8001) 正常运行且 token 有效 |

## 依赖关系

- **Python >= 3.9** — 用于配置生成和实时数据订阅
- **picoclaw >= v0.2.5** — 由 `setup_picoclaw.sh` 自动安装
- **stock_datasource MCP 服务** — 端口 8001（需先启动）
- **stock_datasource Backend** — 端口 6666（需先启动）
