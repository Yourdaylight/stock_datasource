# A股赛博操盘手 🤖📈

**AI 原生的 A 股智能投资助手——赛博操盘手** —— 基于大语言模型和 LangGraph 多智能体架构，为个人投资者提供专业级的股票分析、智能选股、投资组合管理、策略回测、AI 生成量化策略能力。

![alt text](screenshot/chat.png)

--------


## 🧠 AI 原生能力

### 多智能体协作架构

系统采用 **LangGraph** 构建的多智能体架构，由 **OrchestratorAgent（编排器）** 统一协调 **15 个专业 Agent**，实现智能意图识别和任务分发：

```
用户输入 → OrchestratorAgent → 意图识别 → 路由到专业Agent → 工具调用 → 自然语言回复
```

| Agent                     | 功能定位   | 典型场景                                        |
| ------------------------- | ---------- | ----------------------------------------------- |
| **OverviewAgent**         | 市场概览   | "今日大盘走势"、"市场情绪如何"                |
| **MarketAgent**           | 技术分析   | "分析贵州茅台走势"、"600519 估值如何"         |
| **ScreenerAgent**         | 智能选股   | "找出低估值高成长股票"、"筛选股息率>5%的股票" |
| **ReportAgent**           | 财报分析   | "分析宁德时代财务状况"、"比较茅台和五粮液财报"|
| **HKReportAgent**         | 港股财报   | "分析腾讯财报"、"00700 财务健康度"            |
| **PortfolioAgent**        | 持仓管理   | "查看我的持仓"、"分析投资组合风险"            |
| **BacktestAgent**         | 策略回测   | "回测双均线策略"、"测试选股条件历史收益"      |
| **IndexAgent**            | 指数分析   | "分析沪深300走势"、"创业板指技术形态"         |
| **EtfAgent**              | ETF 分析   | "分析科创50ETF"、"对比各行业ETF表现"          |
| **TopListAgent**          | 龙虎榜     | "今日龙虎榜"、"查看机构席位动向"              |
| **NewsAnalystAgent**      | 新闻分析   | "今天有什么热点新闻"、"分析市场情绪"          |
| **KnowledgeAgent**        | 知识库     | "搜索相关研报"、"查找财报公告"（RAG）        |
| **MemoryAgent**           | 用户记忆   | "记住我的自选股"、"我的投资偏好是什么"        |
| **DataManageAgent**       | 数据管理   | "更新今日数据"、"检查数据质量"                |
| **ChatAgent**             | 通用对话   | 其他投资相关问题、AI工作流调用                 |

### 核心 AI 能力

- **🎯 智能意图识别**：自动理解用户自然语言，精准路由到对应 Agent，支持并发执行和 Agent 间交接
- **🔧 Function Calling**：每个 Agent 配备专业工具集，精准调用数据接口
- **💬 流式响应**：实时展示 AI 思考过程和工具调用状态
- **🔗 会话记忆**：支持多轮对话，保持上下文连贯
- **📊 Langfuse 可观测**：完整的 AI 调用链路追踪、Token 统计、性能分析
- **🔌 MCP Server**：支持 Claude Code、Cursor 等 AI IDE 直接调用

### 可AI拓展的数据采集能力

我们定义了一套 Skill 可以一键基于 Tushare 的文档生成插件代码，插件是我们整套系统的数据采集基础，可以方便地扩展新的数据源和数据表。每个插件包括数据采集、数据清洗、数据入库等功能模块，并提供统一的 HTTP 接口与 MCP Tool 给 Agent 调用。当然也支持除 Tushare 之外的 AKShare、Baostock 等数据源。

![alt text](screenshot/plugins.png)

### 🔍 数据探索中心

可视化浏览所有插件数据表，支持 SQL 查询、数据预览、导出等功能：

- **数据表浏览**：按分类查看所有插件数据表（A股、港股、指数、ETF等）
- **SQL 查询**：在线执行 SQL，支持语法高亮和自动补全
- **数据导出**：支持 CSV、Excel、JSON 格式导出
- **SQL 模板**：保存常用查询模板，方便复用

![数据探索](screenshot/data_explorer.png)

### 📊 AI 财报分析中心

专业级财报分析平台，支持 A股/港股 财报浏览与 AI 深度分析：

- **公司列表**：支持按市场、行业筛选，关键词搜索
- **财报浏览**：查看历史财报列表，快速定位报告期
- **双模式 AI 分析**：
  - ⚡ **快速规则分析**：基于预设规则引擎，秒级出结果
  - 🤖 **AI 大模型深度分析**：调用 LLM 深度分析，约 10-60 秒，洞察更深
- **分析历史**：保存分析记录，支持对比查看

![财报分析](screenshot/financial_analysis.png)

### 🇭🇰 港股数据获取

系统支持港股日线数据的自动采集，使用 **AKShare** 作为数据源（免费、无权限限制）。

#### 快速开始

```bash
# 1. 确保港股基础数据已加载
uv run cli.py load-hk-basic

# 2. 获取所有港股最近一年的历史日线数据
uv run scripts/fetch_hk_daily_from_akshare.py

# 3. 测试模式（仅获取前10只股票）
uv run scripts/fetch_hk_daily_from_akshare.py --max-stocks 10
```

#### 数据更新

建议每日收盘后更新最新数据：

```bash
# 更新最近3天的数据
uv run scripts/fetch_hk_daily_from_akshare.py \
  --start-date $(date -d "3 days ago" +%Y%m%d) \
  --end-date $(date +%Y%m%d)
```

#### 数据统计

- **股票覆盖**：2,700+ 只港股
- **时间范围**：最近一年历史数据
- **数据字段**：开盘价、最高价、最低价、收盘价、成交量、涨跌幅等
- **数据源**：AKShare（免费、无限制）

#### 注意事项

1. **数据完整性**：每只股票数据获取后立即入库，确保数据不丢失
2. **错误处理**：约 0.7% 的股票可能因退市、新上市等原因获取失败，属于正常现象
3. **智能选股**：港股数据已集成到智能选股系统，支持港股筛选和分析
4. **性能**：全量获取约 2,700 只股票需 40-45 分钟

详细文档请参考 [港股日线数据迁移总结](HK_DAILY_MIGRATION_SUMMARY.md)。

### AI 工作流引擎

支持自定义 AI 工作流，串联多个 Agent 完成复杂任务：

```yaml
# 示例：每日复盘工作流
steps:
  - agent: OverviewAgent
    action: 获取市场概览
  - agent: ScreenerAgent  
    action: 筛选涨停股票
  - agent: ReportAgent
    action: 分析龙头股财务
```

---

## ✨ 核心特性

### 📊 智能选股系统

- 实时行情展示：分页展示全市场股票，支持排序和搜索
- 多维度筛选：PE、PB、市值、涨跌幅、换手率等多条件组合
- AI 辅助选股：自然语言描述条件，AI 自动生成筛选策略
  ![screener](screenshot/screener.png)

### 📈 专业行情分析

- K 线图表：交互式 K 线，支持多种技术指标
- 趋势分析：均线系统、MACD、RSI 等技术分析
- 估值分析：PE、PB、市值等基本面指标
  ![股票详情](screenshot/股票详情.png)
  ![行情看板](screenshot/market.png)

### 💼 投资组合管理

- 持仓跟踪：实时计算持仓盈亏
- 风险分析：波动率、最大回撤等风险指标
- 收益归因：分析收益来源
- AI 基于个人持仓定期分析

### 智能对话

实时展示Agent的思考与工具调用过程，实时渲染相关技术指标图
![股票详情](screenshot/chat2.png)
![股票详情](screenshot/chat3.png)

### 🔄 策略回测

- 可视化回测：图表展示策略表现
- 多策略支持：均线、动量、价值等策略模板
- 参数优化：自动寻找最优参数
- 多AI Agent对抗寻找最佳策略
  ![策略生成](screenshot/strategies.png)

### 📊 量化选股系统

- 全市场初筛：多因子模型初筛候选标的
- RPS 排名：相对强度排名筛选强势股
- 深度分析：基本面 + 技术面多维度综合评分
- 交易信号：基于量化模型自动生成买卖信号
- 模型配置：自定义因子权重和参数

### 知识库集成（可选配置）

使用Weknora开源知识库，需要手动配置
基于该知识库实现将财报内容存入知识库用于后续分析

### 📰 新闻资讯中心

- 实时新闻：自动抓取财经新闻，情绪分析
- 热点追踪：追踪市场热点板块和概念
- 新闻筛选：按情绪、板块、来源过滤

### 🤖 多 Agent 竞技场

- 策略对抗：多个 Agent 执行不同策略，对比表现
- 淘汰赛制：自动淘汰弱势策略，留存强策略
- 可视化分析：收益曲线对比、雷达图评分

------------------------------------------------
## 📱联动OpenClaw
这里我们基于这个项目构建了财经股，基于财经库制作了基于热点新闻与各个公司的财报分析

![AI看公司](image.png)
AI看公司
--------
## 🚀 快速开始

### 方式一：Docker 一键部署（推荐新用户）

适合**没有现成 ClickHouse/Redis** 的用户，所有基础设施由 docker-compose 一起启动。

```bash
# 1. 克隆项目
git clone https://github.com/Yourdaylight/stock_datasource.git
cd stock_datasource

# 2. 安装依赖
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync

# 3. 交互式配置向导（自动验证 Tushare/LLM/数据库连通性，生成 .env）
uv run cli.py setup

# 4. 一键启动全部服务（ClickHouse + Redis + 后端 + 前端）
uv run cli.py server start --docker --with-infra

# 5. 初始化数据
docker compose exec backend bash -c "
  uv run python cli.py init-db &&
  uv run python cli.py load-stock-basic &&
  uv run python cli.py load-trade-calendar --start-date 20240101 --end-date 20261231
"
```

访问：**前端** http://localhost:18080 | **API 文档** http://localhost:18080/docs

> 已有 ClickHouse/Langfuse？运行 `setup` 时选择自定义地址，向导会自动验证连通性。

**Docker 日常运维：**

```bash
uv run cli.py server start --docker          # 启动
uv run cli.py server stop --docker            # 停止
uv run cli.py server restart --docker         # 重启
uv run cli.py server status --docker          # 查看状态
```

---

### 方式二：本地开发部署

适合开发调试，需要本地安装依赖。

```bash
# 1. 克隆项目 & 安装依赖
git clone https://github.com/Yourdaylight/stock_datasource.git
cd stock_datasource
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
cd frontend && npm install && cd ..

# 2. 启动基础设施（Docker 仅启动 ClickHouse + Redis）
docker compose -f docker-compose.infra.yml up -d clickhouse redis

# 3. 交互式配置（自动创建 .env 并验证所有连通性）
uv run cli.py setup

# 4. 环境健康检查（一键诊断 6 项依赖）
uv run cli.py doctor

# 5. 初始化数据库
uv run cli.py init-db
uv run cli.py load-stock-basic
uv run cli.py load-trade-calendar --start-date 20240101 --end-date 20261231

# 6. 一键启动所有服务（后端 + MCP + 前端，后台运行）
uv run cli.py server start
```

访问：**前端** http://localhost:5173 | **API 文档** http://localhost:6666/docs

**日常开发命令：**

```bash
uv run cli.py server restart                   # 重启所有服务
uv run cli.py server stop -s backend           # 仅停止后端
uv run cli.py server status                    # 查看服务状态
uv run cli.py doctor                          # 环境健康检查
uv run cli.py config show                     # 查看配置（密钥脱敏）
uv run cli.py config set OPENAI_MODEL=gpt-4o  # 修改配置项
```

**数据采集：**

```bash
# A股/ETF/指数日线
uv run cli.py ingest-daily --date 20250119                # 采集单日
uv run cli.py backfill --start-date 20250101 --end-date 20250119  # 区间回补

# 港股
uv run cli.py load-hk-stock-list                           # 加载港股列表
uv run cli.py load-hk-daily --symbol 00700 --start-date 20250101  # 采集单只

# 通用插件运行
uv run cli.py run-plugin tushare_daily --trade-date 20250119     # 运行指定插件
uv run cli.py list-plugins                                       # 查看所有插件
```

---

### 🛠️ CLI 工具一览

系统提供了完整的命令行工具，覆盖配置、部署、数据采集全流程：

| 命令 | 说明 |
|------|------|
| `uv run cli.py setup` | 交互式配置向导（自动验证连通性） |
| `uv run cli.py doctor` | 环境健康检查（ClickHouse/Redis/Tushare/LLM/Proxy） |
| `uv run cli.py server start/stop/restart/status` | 服务生命周期管理 |
| `uv run cli.py config show/set` | 查看/修改配置（密钥自动脱敏） |
| `uv run cli.py init-db` | 初始化数据库表结构 |
| `uv run cli.py ingest-daily` | 采集单日数据 |
| `uv run cli.py backfill` | 区间数据回补 |
| `uv run cli.py run-plugin <name>` | 运行任意数据插件 |
| `uv run cli.py list-plugins` | 查看所有已注册插件 |
| `uv run cli.py proxy status/set/test` | 代理配置管理 |
| `uv run cli.py task list/stats/cancel` | 任务队列管理 |

详细用法请参考 [CLI 使用指南](docs/CLI_GUIDE.md)。

---

## 🔌 MCP Server 集成

系统提供 MCP (Model Context Protocol) Server，可集成到 Claude Code、Cursor 等 AI IDE：

### 启动 MCP Server

```bash
uv run python -m stock_datasource.services.mcp_server
```

### 配置 AI IDE

在 Claude Code 或 Cursor 中添加配置：

```json
{
  "mcpServers": {
    "stock_datasource": {
      "url": "http://localhost:8001/messages",
      "transport": "streamable-http"
    }
  }
}
```

---

## 🔓 开放 API 网关（Open API Gateway）

系统提供标准 HTTP 数据查询接口，复用 MCP API Key 认证体系，让外部用户可通过 `curl` / Python / 任何 HTTP 客户端查询数据。

> **安全边界**：仅开放 Plugin 数据查询接口（纯数据库查询），AI/管理/用户隐私路由一律不开放。

### 快速使用

```bash
# 1. 在前端「个人中心」创建 API Key (sk-xxx)

# 2. 调用开放数据接口
curl -X POST http://localhost:18080/api/open/v1/tushare_daily/query \
  -H "Authorization: Bearer sk-YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"trade_date": "20250301", "ts_code": "600519.SH"}'

# 3. 查看已开放的接口文档
curl http://localhost:18080/api/open/docs \
  -H "Authorization: Bearer sk-YOUR_API_KEY"
```

### 核心特性

- **认证机制**：复用 MCP API Key (`sk-xxx`)，支持 Header 和 Query 两种传入方式
- **访问策略**：每个接口独立控制启用/禁用、速率限制、最大返回记录数
- **速率限制**：滑动窗口算法，按分钟（默认 60/min）和按天（默认 10000/day）两维度
- **响应截断**：超出最大记录数自动截断（默认 5000 条）
- **用量追踪**：每次调用记录到 ClickHouse `api_usage_log` 表
- **管理面板**：管理员在 `/api-access` 页面配置可开放接口

### 可开放接口范围

| 类别 | 示例 | 状态 |
|------|------|------|
| A股日线 | `/api/open/v1/tushare_daily/query` | 需手动启用 |
| ETF日线 | `/api/open/v1/tushare_etf_fund_daily/query` | 需手动启用 |
| 港股日线 | `/api/open/v1/akshare_hk_daily/query` | 需手动启用 |
| 股票基本信息 | `/api/open/v1/tushare_stock_basic/query` | 需手动启用 |
| 财务报表 | `/api/open/v1/tushare_income/query` | 需手动启用 |
| 其他插件 | 全部 80+ 数据插件 | 需手动启用 |

> **绝对不开放的接口**：`/auth/*`、`/chat/*`、`/datamanage/*`、`/portfolio/*`、`/memory/*`、`/mcp_api_key/*` 等系统/管理/AI路由。

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     前端 (Vue 3 + TypeScript + TDesign)                 │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────────┐     │
│  │ 智能对话 │ │ 智能选股 │ │ 行情分析 │ │ 持仓管理 │ │ 财报分析  │     │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬─────┘     │
│  ┌────┴────┐ ┌────┴────┐ ┌────┴────┐ ┌────┴────┐ ┌────┴─────┐     │
│  │量化选股 │ │新闻资讯 │ │策略工具台│ │多Agent场│ │ 开放API  │     │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬─────┘     │
└───────┼──────────┼──────────┼──────────┼──────────┼──────────┘
        │          │          │          │          │
        ▼          ▼          ▼          ▼          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API Layer (FastAPI)                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                  OrchestratorAgent (15 Agents)               │   │
│  │    ┌──────────────────────────────────────────────┐      │   │
│  │    │      意图识别 → 并发路由 → Agent交接 → 聚合    │      │   │
│  │    └──────────────────────────────────────────────┘      │   │
│  │         │         │         │         │         │         │   │
│  │    ┌────▼───┐ ┌───▼────┐ ┌──▼───┐ ┌──▼───┐ ┌───▼────┐   │   │
│  │    │Overview│ │Screener│ │Report│ │Market│ │Backtest│   │   │
│  │    │ Agent  │ │ Agent  │ │Agent │ │Agent │ │ Agent  │   │   │
│  │    └────────┘ └────────┘ └──────┘ └──────┘ └────────┘   │   │
│  │    + IndexAgent, EtfAgent, PortfolioAgent, MemoryAgent      │   │
│    + TopListAgent, NewsAnalystAgent, KnowledgeAgent         │   │
│    + DataManageAgent, ChatAgent, WorkflowAgent              │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │            Open API Gateway (/api/open/v1/*)               │   │
│  │      API Key 认证 → 速率限制 → Plugin数据查询 → 用量追踪  │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
        │                                  │                │
        ▼                                  ▼                ▼
┌───────────────────┐    ┌─────────────┐   ┌────────────────────┐
│   LLM Provider    │    │    Redis    │   │     Task Worker    │
│ OpenAI / 国产大模型│    │ 队列 & 缓存 │   │ 任务调度/采集执行    │
└───────────────────┘    └─────────────┘   └────────────────────┘
        │                                  │
        ▼                                  ▼
┌───────────────────┐    ┌───────────────────┐
│     Langfuse      │    │  ClickHouse DB    │
│   AI 可观测平台    │    │  A股/港股全量数据   │
└───────────────────┘    └───────────────────┘
```

### 技术栈

| 层级       | 技术                                                    |
| ---------- | ------------------------------------------------------- |
| **前端**   | Vue 3, TypeScript, TDesign, ECharts, Pinia              |
| **后端**   | Python 3.11+, FastAPI, LangGraph, DeepAgents            |
| **数据库** | ClickHouse（列式存储，高性能分析）                      |
| **缓存**   | Redis（会话缓存、数据缓存）                             |
| **数据源** | TuShare Pro（A股）、AKShare（港股）                     |
| **AI**     | OpenAI GPT-4 / Kimi / 国产大模型，Function Calling      |
| **可观测** | Langfuse（AI 调用链路追踪）                             |
| **开放接口** | Open API Gateway + MCP Server（外部数据查询）          |

---

## 📁 项目结构

```
stock_datasource/
├── src/stock_datasource/
│   ├── agents/                # AI Agent 层（15个专业Agent）
│   │   ├── orchestrator.py    # 编排器（意图路由、并发执行、Agent交接）
│   │   ├── base_agent.py      # Agent 基类
│   │   ├── overview_agent.py  # 市场概览
│   │   ├── market_agent.py    # 技术分析
│   │   ├── screener_agent.py  # 智能选股
│   │   ├── report_agent.py    # A股财报分析
│   │   ├── hk_report_agent.py # 港股财报分析
│   │   ├── portfolio_agent.py # 持仓管理
│   │   ├── backtest_agent.py  # 策略回测
│   │   ├── index_agent.py     # 指数分析
│   │   ├── etf_agent.py       # ETF分析
│   │   ├── news_analyst_agent.py # 新闻分析
│   │   ├── knowledge_agent.py # 知识库（RAG）
│   │   ├── memory_agent.py    # 用户记忆
│   │   ├── datamanage_agent.py # 数据管理
│   │   ├── chat_agent.py      # 通用对话
│   │   ├── workflow_agent.py  # 工作流执行
│   │   └── *_tools.py         # Agent 工具集
│   ├── plugins/               # 数据采集插件（80+）
│   ├── modules/               # 功能模块（22个）
│   │   ├── auth/              # 认证模块
│   │   ├── chat/              # 对话交互
│   │   ├── market/            # 行情分析
│   │   ├── screener/          # 选股模块
│   │   ├── report/            # 财报研读
│   │   ├── hk_report/         # 港股财报
│   │   ├── financial_analysis/ # 财务分析中心
│   │   ├── overview/          # 市场概览
│   │   ├── news/              # 新闻资讯
│   │   ├── etf/               # ETF基金
│   │   ├── index/             # 指数选股
│   │   ├── portfolio/         # 持仓管理
│   │   ├── backtest/          # 策略回测
│   │   ├── arena/             # 多Agent竞技场
│   │   ├── quant/             # 量化选股
│   │   ├── memory/            # 用户记忆
│   │   ├── datamanage/        # 数据管理
│   │   ├── open_api/          # 开放API网关（NEW）
│   │   ├── mcp_api_key/       # MCP API Key 管理
│   │   ├── token_usage/       # Token用量统计
│   │   └── mcp_usage/         # MCP调用统计
│   ├── services/              # HTTP / MCP / 任务队列等核心服务
│   ├── tasks/                 # 定时任务与调度
│   └── core/                  # 核心组件（插件管理、服务生成器等）
├── skills/                   # 技能包（tushare-plugin-builder、stock-rt-subscribe等）
├── frontend/                  # Vue 3 前端
├── scripts/                   # 数据采集脚本
├── docker/                    # Docker 配置
├── docs/                      # 文档
├── cli.py                     # 命令行工具
├── docker-compose.yml         # 应用服务
├── docker-compose.infra.yml   # 基础设施
└── tests/                     # 测试
```

---

## 🧪 测试

```bash
# 运行所有测试
uv run pytest tests/

# 测试 AI Agent
uv run python -c "
from dotenv import load_dotenv; load_dotenv()
from stock_datasource.agents import get_orchestrator
import asyncio

async def test():
    orch = get_orchestrator()
    result = await orch.execute('今日大盘走势如何')
    print(result.response)

asyncio.run(test())
"
```

---

## 📚 文档

| 文档                           | 说明                   |
| ------------------------------ | ---------------------- |
| [CLI 使用指南](docs/CLI_GUIDE.md) | 命令行工具详细使用说明 |
| [开发指南](DEVELOPMENT_GUIDE.md)  | 开发者文档             |
| [插件开发](PLUGIN_QUICK_START.md) | 新建数据插件快速参考   |

---

## 🔧 常见问题

### Q: Docker 启动后前端访问不了？

检查端口配置 `APP_PORT`，确保没有被占用。查看日志 `docker-compose logs frontend`。

### Q: AI 返回错误 "Invalid API key"？

检查 `.env.docker` 中的 `OPENAI_API_KEY` 是否正确配置，然后重建容器：

```bash
docker-compose build backend && docker-compose up -d backend
```

### Q: 如何使用国产大模型？

修改 `.env` 中的配置：

```env
OPENAI_BASE_URL=https://your-provider-url/v1
OPENAI_MODEL=your-model-name
OPENAI_API_KEY=your-api-key
```

### Q: 数据采集失败？

确保 TuShare Token 有效且有足够积分。可通过 `uv run cli.py doctor` 检查所有依赖连通性。

---

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
6. 开启 Pull Request
   
## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=Yourdaylight/stock_datasource&type=date)](https://star-history.com/#Yourdaylight/stock_datasource&Date)
