# A股赛博操盘手 🤖📈

**AI 原生的 A 股智能投资助手——赛博操盘手** —— 基于大语言模型和 LangGraph 多智能体架构，为个人投资者提供专业级的股票分析、智能选股、投资组合管理、策略回测、AI 生成量化策略能力。

![alt text](screenshot/chat.png)

--------


## 🧠 AI 原生能力

### 多智能体协作架构

系统采用 **LangGraph** 构建的多智能体架构，由 **OrchestratorAgent（编排器）** 统一协调 **13 个专业 Agent**，实现智能意图识别和任务分发：

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
| **MemoryAgent**           | 用户记忆   | "记住我的自选股"、"我的投资偏好是什么"        |
| **DataManageAgent**       | 数据管理   | "更新今日数据"、"检查数据质量"                |
| **WorkflowAgent**         | AI 工作流  | "创建每日复盘工作流"、"执行选股策略流程"      |
| **ChatAgent**             | 通用对话   | 其他投资相关问题                                |

### 核心 AI 能力

- **🎯 智能意图识别**：自动理解用户自然语言，精准路由到对应 Agent
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

### 知识库集成（可选配置）

使用Weknora开源知识库，需要手动配置
基于该知识库实现将财报内容存入知识库用于后续分析
------------------------------------------------
## 📱联动OpenClaw
这里我们基于这个项目构建了财经股，基于财经库制作了基于热点新闻与各个公司的财报分析

![AI看公司](image.png)
AI看公司
--------
## 🚀 快速开始

### 场景一：从 0 到 1 一键部署（新用户推荐）

适合**没有现成 ClickHouse/Redis** 的用户，所有基础设施由 docker-compose 一起启动。

#### 1. 克隆项目 & 配置

```bash
git clone https://github.com/Yourdaylight/stock_datasource.git
cd stock_datasource

# 复制配置模板
cp .env.example .env.docker
```

编辑 `.env.docker`，填写 **必填项**：

```env
# ======== 必填 ========
TUSHARE_TOKEN=your_tushare_token          # https://tushare.pro 获取
OPENAI_API_KEY=your_openai_api_key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4

# ======== 使用默认值即可 ========
CLICKHOUSE_HOST=clickhouse                # 容器名
CLICKHOUSE_USER=clickhouse
CLICKHOUSE_PASSWORD=clickhouse
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=stockredis123
REDIS_DB=1
```

#### 2. 一键启动

```bash
# 启动全部服务（ClickHouse + Redis + PostgreSQL + 后端 + 前端）
docker-compose -f docker-compose.yml -f docker-compose.infra.yml --env-file .env.docker up -d

# 查看状态
docker-compose -f docker-compose.yml -f docker-compose.infra.yml ps
```

#### 3. 初始化数据

```bash
docker-compose exec backend bash -c "
  uv run python cli.py init-db &&
  uv run python cli.py load-stock-basic &&
  uv run python cli.py load-trade-calendar --start-date 20240101 --end-date 20261231
"
```

#### 4. 访问

- **前端**：http://localhost:18080
- **API 文档**：http://localhost:18080/docs
- **健康检查**：http://localhost:18080/health

---

### 场景二：已有基础设施（ClickHouse/Langfuse 等）

适合**已有 ClickHouse、Langfuse 等服务**的用户，只需启动应用容器。

#### 1. 配置指向已有服务

```bash
cp .env.example .env.docker
```

编辑 `.env.docker`，关键是让容器能访问你的服务：

```env
# ======== 必填 ========
TUSHARE_TOKEN=your_tushare_token
OPENAI_API_KEY=your_openai_api_key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4

# ======== ClickHouse 配置 ========
# 如果你的 ClickHouse 也是 Docker 容器，填容器名（需在同一网络）
CLICKHOUSE_HOST=langfuse-clickhouse-1     # 或 your-clickhouse-container-name
CLICKHOUSE_PORT=9000
CLICKHOUSE_USER=clickhouse                # 或 default
CLICKHOUSE_PASSWORD=clickhouse            # 或留空
CLICKHOUSE_DATABASE=stock_datasource

# 如果 ClickHouse 是宿主机本地安装（监听 0.0.0.0）
# CLICKHOUSE_HOST=host.docker.internal
# CLICKHOUSE_PORT=9000
# CLICKHOUSE_USER=default
# CLICKHOUSE_PASSWORD=

# ======== Redis 配置 ========
REDIS_HOST=redis                          # 使用 docker-compose.infra.yml 的 Redis
REDIS_PORT=6379
REDIS_PASSWORD=stockredis123
REDIS_DB=1

# ======== Langfuse 配置（可选）========
# 如果有已运行的 Langfuse
LANGFUSE_HOST=http://host.docker.internal:3000
LANGFUSE_PUBLIC_KEY=your_public_key
LANGFUSE_SECRET_KEY=your_secret_key
```

#### 2. 确保网络互通

如果你的 ClickHouse 是另一个 Docker 容器，需要加入同一网络：

```bash
# 创建网络（如果不存在）
docker network create stock_network

# 把已有的 ClickHouse 容器加入网络
docker network connect stock_network your-clickhouse-container
```

#### 3. 只启动应用

```bash
# 只启动后端 + 前端 + Redis（不启动 ClickHouse）
docker-compose -f docker-compose.yml -f docker-compose.infra.yml --env-file .env.docker up -d backend frontend redis

# 或者如果 Redis 也已有
docker-compose --env-file .env.docker up -d
```

#### 4. 验证连接

```bash
# 检查健康状态
curl http://localhost:18080/health

# 应返回：{"status":"ok","clickhouse":"connected","cache":...}
```

---

### Docker 常用命令

```bash
# 代码更新后重建
docker-compose up -d --build

# 查看后端日志
docker-compose logs -f backend

# 进入容器调试
docker-compose exec backend bash

# 停止所有服务
docker-compose down

# 清理数据卷（危险！）
docker-compose down -v
```

---

### 方式二：本地开发部署

适合开发调试，需要本地安装依赖。

#### 1. 环境要求

- **Python 3.11+**
- **Node.js 18+**（前端）
- **ClickHouse**（数据库）
- **Redis**（缓存，可选）
- **uv**（Python 包管理器）

#### 2. 安装依赖

```bash
# 克隆项目
git clone <repository-url>
cd stock_datasource

# 安装 uv（如未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装 Python 依赖
uv sync

# 安装前端依赖
cd frontend && npm install && cd ..
```

#### 3. 配置环境变量

```bash
# 创建本地配置
cp .env.example .env
```

编辑 `.env` 文件：

```env
# TuShare Token
TUSHARE_TOKEN=your_tushare_token

# OpenAI API
OPENAI_API_KEY=your_openai_api_key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4

# ClickHouse（本地安装）
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=9000
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=
CLICKHOUSE_DATABASE=stock_datasource

# Redis（可选）
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=1
```

#### 4. 启动基础设施

**方式 A：使用 Docker 启动基础设施（推荐）**

```bash
# 只启动 ClickHouse 和 Redis
docker-compose -f docker-compose.infra.yml up -d clickhouse redis
```

**方式 B：本地安装 ClickHouse**

参考 [ClickHouse 官方文档](https://clickhouse.com/docs/en/install) 安装。

#### 5. 初始化数据库

```bash
# 初始化表结构
uv run cli.py init-db

# 加载股票基础信息
uv run cli.py load-stock-basic

# 加载交易日历
uv run cli.py load-trade-calendar --start-date 20240101 --end-date 20261231
```

#### 6. 日线数据采集（A股/ETF/指数/港股）

```bash
# A股/ETF/指数：采集某一交易日（日线）
uv run cli.py ingest-daily --date 20250119

# A股/ETF/指数：采集区间回补（日线）
uv run cli.py backfill --start-date 20250101 --end-date 20250119

# 可选：跳过质量检查（排障用）
uv run cli.py ingest-daily --date 20250119 --no-quality-checks

# 可选：忽略插件调度限制，强制拉取（排障/补数用）
uv run cli.py ingest-daily --date 20250119 --ignore-schedule

# 港股：先加载港股股票列表
uv run cli.py load-hk-stock-list

# 港股：采集单只港股日线（示例：腾讯 00700）
uv run cli.py load-hk-daily --symbol 00700 --start-date 20250101 --end-date 20250119
```

#### 7. 启动服务

**终端 1：启动后端**

```bash
uv run python -m stock_datasource.services.http_server
```

**终端 2：启动前端**

```bash
cd frontend
npm run dev
```

#### 8. 访问应用

- **前端界面**：http://localhost:5173
- **API 服务**：http://localhost:6666
- **API 文档**：http://localhost:6666/docs

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

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     前端 (Vue 3 + TypeScript)                    │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │ 智能对话 │ │ 智能选股 │ │ 行情分析 │ │ 持仓管理 │ │ 策略回测 │   │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘   │
└───────┼──────────┼──────────┼──────────┼──────────┼──────────┘
        │          │          │          │          │
        ▼          ▼          ▼          ▼          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API Layer (FastAPI)                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                  OrchestratorAgent                        │
│  │    ┌──────────────────────────────────────────────┐      │   │
│  │    │           意图识别 & 路由分发                   │      │   │
│  │    └──────────────────────────────────────────────┘      │   │
│  │         │         │         │         │         │         │   │
│  │    ┌────▼───┐ ┌───▼────┐ ┌──▼───┐ ┌──▼───┐ ┌───▼────┐   │   │
│  │    │Overview│ │Screener│ │Report│ │Market│ │Backtest│   │   │
│  │    │ Agent  │ │ Agent  │ │Agent │ │Agent │ │ Agent  │   │   │
│  │    └────────┘ └────────┘ └──────┘ └──────┘ └────────┘   │   │
│  │    + IndexAgent, EtfAgent, PortfolioAgent, MemoryAgent   │   │
│  │    + TopListAgent, WorkflowAgent, ChatAgent              │   │
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
│   AI 可观测平台    │    │   A股全量数据     │
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

---

## 📁 项目结构

```
stock_datasource/
├── src/stock_datasource/
│   ├── agents/                # AI Agent 层
│   │   ├── orchestrator.py    # 编排器（意图路由）
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
│   │   ├── memory_agent.py    # 用户记忆
│   │   └── *_tools.py         # Agent 工具集
│   ├── plugins/               # 数据采集插件
│   ├── services/              # HTTP / MCP 服务
│   ├── modules/               # 功能模块
│   │   ├── auth/              # 认证模块
│   │   ├── overview/          # 市场概览
│   │   ├── screener/          # 选股模块
│   │   ├── financial_analysis/# 财报分析中心
│   │   ├── datamanage/        # 数据探索中心
│   │   └── ...
│   └── core/                  # 核心组件
├── frontend/                  # Vue 前端
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

确保 TuShare Token 有效且有足够积分。可通过 `uv run cli.py check-tushare` 检查。

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
