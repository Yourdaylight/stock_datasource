#!/usr/bin/env python3
"""
generate_picoclaw_config.py — 从项目 .env + AgentRegistry 生成 picoclaw 配置文件

用法:
  python3 skills/stock-data-assistant/generate_picoclaw_config.py [选项]

选项:
  --output PATH    输出配置文件路径 (默认: .local/picoclaw.yaml)
  --mcp-url URL     MCP 服务 URL (默认: 从环境变量或 http://localhost:8001/messages)
  --mcp-token TOKEN MCP 认证 token (默认: 从 STOCK_MCP_TOKEN 环境变量读取)
  --ws-url URL      实时数据 WebSocket 地址 (默认: ws://localhost:8765)
  --workspace DIR   PicoClaw workspace 目录 (默认: ~/.picoclaw/workspace)
  --no-workspace    不生成 workspace md 文件，仅生成 yaml 配置
  --help            显示帮助信息

生成的配置包含:
  1. LLM 模型配置（复用项目的 OPENAI_API_KEY/BASE_URL/MODEL）
  2. MCP Server 连接（连接 stock_datasource 的 MCP 服务）
  3. 微信 Channel 配置
  4. PicoClaw workspace md 文件（AGENTS.md / SOUL.md / TOOLS.md / USER.md / IDENTITY.md / HEARTBEAT.md）
     — 自动从 AgentRegistry 读取 Agent 能力描述注入
"""

import argparse
import os
import sys
from pathlib import Path

# 项目根目录
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent


def load_env(env_file: Path | None = None) -> dict[str, str]:
    """加载 .env 文件为字典"""
    result = {}
    target = env_file or PROJECT_ROOT / ".env"
    if not target.exists():
        print(f"[WARN] .env 文件不存在: {target}", file=sys.stderr)
        return result
    with open(target, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def detect_platform() -> str:
    """检测当前平台用于 picoclaw binary 名称"""
    import platform
    machine = platform.machine().lower()
    sys_name = platform.system().lower()
    if sys_name == "linux":
        if machine in ("x86_64", "amd64"):
            return "linux-x86_64"
        elif machine in ("aarch64", "arm64"):
            return "linux-aarch64"
        elif machine == "riscv64":
            return "linux-riscv64"
    elif sys_name == "darwin":
        if machine in ("x86_64", "amd64"):
            return "darwin-x86_64"
        elif machine in ("aarch64", "arm64"):
            return "darwin-aarch64"
    raise SystemExit(f"不支持的平台: {sys_name}-{machine}")


# ---------------------------------------------------------------------------
# Agent 能力收集（从 AgentRegistry 读取）
# ---------------------------------------------------------------------------

def collect_agent_capabilities() -> list[dict]:
    """从 AgentRegistry 收集所有已注册 Agent 的能力描述。

    Returns:
        List of dicts with keys: name, description, markets, intents, tags
    """
    try:
        # 延迟导入，避免循环依赖
        from stock_datasource.services.agent_registrations import register_all_agents
        from stock_datasource.services.agent_registry import get_agent_registry, AgentRole

        register_all_agents()
        registry = get_agent_registry()

        agents = []
        for desc in registry.list_descriptors(role=AgentRole.AGENT, enabled_only=True):
            agents.append({
                "name": desc.name,
                "description": desc.description,
                "markets": desc.capability.markets,
                "intents": desc.capability.intents,
                "tags": desc.capability.tags,
                "priority": desc.priority,
            })
        return agents
    except Exception as e:
        print(f"[WARN] 无法从 AgentRegistry 获取能力描述: {e}", file=sys.stderr)
        print("[WARN] 将使用默认 Agent 列表", file=sys.stderr)
        return _fallback_agent_list()


def _fallback_agent_list() -> list[dict]:
    """当 AgentRegistry 不可用时的 fallback Agent 列表。"""
    return [
        {"name": "MarketAgent", "description": "A股和港股行情分析Agent，提供K线、技术指标、趋势分析等", "markets": ["A", "HK"], "intents": ["market_analysis", "hk_market_analysis"], "tags": ["market", "technical", "kline"], "priority": 10},
        {"name": "ScreenerAgent", "description": "股票筛选Agent，支持多维度条件筛选", "markets": ["A"], "intents": ["stock_screening"], "tags": ["screener", "filter"], "priority": 5},
        {"name": "ReportAgent", "description": "A股财务报表分析Agent", "markets": ["A"], "intents": ["financial_report"], "tags": ["report", "financial", "fundamental"], "priority": 8},
        {"name": "HKReportAgent", "description": "港股财务报表分析Agent", "markets": ["HK"], "intents": ["hk_financial_report"], "tags": ["report", "financial", "hk"], "priority": 8},
        {"name": "PortfolioAgent", "description": "投资组合管理Agent", "markets": [], "intents": ["portfolio_management"], "tags": ["portfolio"], "priority": 5},
        {"name": "BacktestAgent", "description": "策略回测Agent", "markets": [], "intents": ["strategy_backtest"], "tags": ["backtest", "strategy"], "priority": 5},
        {"name": "IndexAgent", "description": "指数分析Agent", "markets": [], "intents": ["index_analysis"], "tags": ["index"], "priority": 5},
        {"name": "EtfAgent", "description": "ETF分析Agent", "markets": [], "intents": ["etf_analysis"], "tags": ["etf"], "priority": 5},
        {"name": "OverviewAgent", "description": "市场概览Agent", "markets": [], "intents": ["market_overview"], "tags": ["overview", "market"], "priority": 3},
        {"name": "TopListAgent", "description": "龙虎榜/排行Agent", "markets": [], "intents": ["toplist"], "tags": ["toplist", "ranking"], "priority": 3},
        {"name": "NewsAnalystAgent", "description": "新闻分析Agent", "markets": [], "intents": ["news_analysis"], "tags": ["news"], "priority": 3},
        {"name": "KnowledgeAgent", "description": "知识检索Agent(RAG)，用于研报、公告、政策文档查询", "markets": [], "intents": ["knowledge_search"], "tags": ["knowledge", "rag", "document"], "priority": 5},
        {"name": "MemoryAgent", "description": "负责用户记忆管理，包括偏好设置、自选股管理等", "markets": [], "intents": ["memory_management"], "tags": ["memory", "preference", "watchlist"], "priority": 2},
        {"name": "DataManageAgent", "description": "数据管理Agent，支持数据同步、状态查询等", "markets": [], "intents": ["data_management"], "tags": ["data", "management", "sync"], "priority": 2},
        {"name": "ChatAgent", "description": "通用对话助手，处理一般性问答", "markets": [], "intents": ["general_chat"], "tags": ["chat", "general"], "priority": 0},
    ]


# ---------------------------------------------------------------------------
# Workspace md 文件生成
# ---------------------------------------------------------------------------

def generate_agents_md(agents: list[dict]) -> str:
    """生成 AGENTS.md — Agent 行为指南（最高优先级）。

    这是 PicoClaw workspace 中最重要的文件，定义了：
    - 系统整体能力范围
    - 所有可用 Agent 及其职责
    - 用户请求路由规则
    - MCP 工具使用指南
    """
    agent_lines = []
    for a in sorted(agents, key=lambda x: -x["priority"]):
        markets = ", ".join(a["markets"]) if a["markets"] else "通用"
        intents = ", ".join(a["intents"]) if a["intents"] else ""
        agent_lines.append(
            f"### {a['name']}\n"
            f"- **描述**: {a['description']}\n"
            f"- **市场**: {markets}\n"
            f"- **能力标签**: {', '.join(a['tags']) if a['tags'] else '无'}\n"
        )

    agents_section = "\n".join(agent_lines)

    return f"""# Stock Datasource — Agent 行为指南

你是 **Stock Datasource** 智能股票分析平台的 AI 助手。本文件定义你的行为规范和能力边界。

## 系统概述

Stock Datasource 是一个专业的股票数据分析平台，提供以下核心能力：
- A股/港股行情查询与技术分析
- 财务报表分析与基本面研究
- 智能选股与筛选
- 策略回测
- 投资组合管理
- 实时行情推送（WebSocket）
- 研报/公告/政策文档检索（RAG）
- 市场新闻分析

## 可用 Agent 列表

{agents_section}

## 请求路由规则

1. **行情分析**（K线、技术指标、趋势） → MarketAgent
2. **A股财务分析**（财报、盈利、基本面） → ReportAgent
3. **港股财务分析** → HKReportAgent
4. **选股/筛选** → ScreenerAgent
5. **策略回测** → BacktestAgent
6. **投资组合** → PortfolioAgent
7. **指数分析** → IndexAgent
8. **ETF 分析** → EtfAgent
9. **市场概览** → OverviewAgent
10. **龙虎榜/排行** → TopListAgent
11. **新闻分析** → NewsAnalystAgent
12. **研报/公告/文档** → KnowledgeAgent
13. **自选股/偏好管理** → MemoryAgent
14. **数据同步/管理** → DataManageAgent
15. **一般对话** → ChatAgent

## MCP 工具使用

你通过 MCP Server 连接 Stock Datasource 的 76+ 数据查询工具。使用时注意：
- 优先使用 MCP 工具获取数据，不要凭记忆回答行情数据
- A股代码格式：`600519.SH`；港股代码格式：`00700.HK`
- 技术分析请求应明确指定周期（日K/周K/月K）
- 财务分析请求优先使用最新财报数据

## 安全边界

- **绝不**提供投资建议或推荐买卖某只股票
- **绝不**保证任何收益或预测股价涨跌
- 分析基于历史数据，提示用户注意风险
- 涉及港股时，提示汇率和交易规则差异
"""


def generate_soul_md() -> str:
    """生成 SOUL.md — Agent 灵魂设定（人格与行为风格）。"""
    return """# Stock Datasource — 灵魂设定

## 性格

你是一位专业、严谨、耐心的股票数据分析助手。你的核心特质：

- **专业**: 使用准确的金融术语，数据分析有据可查
- **严谨**: 对不确定的信息标注来源和时效，不编造数据
- **耐心**: 用清晰易懂的方式解释复杂概念
- **中立**: 不偏向任何投资标的，客观呈现事实

## 沟通风格

- 回复使用中文，专业术语保留英文原文
- 数据引用标注来源和更新时间
- 复杂分析先给结论，再展开细节
- 适当使用表格整理对比数据
- 遇到模糊问题主动澄清意图

## 决策原则

1. 数据准确性 > 回复速度
2. 客观事实 > 主观判断
3. 风险提示 > 收益描述
4. 历史依据 > 预测推断
"""


def generate_tools_md(mcp_url: str, ws_url: str, mcp_token: str | None) -> str:
    """生成 TOOLS.md — 工具说明（本地环境配置）。"""
    auth_line = f'Authorization: "Bearer {mcp_token}"' if mcp_token else "# 设置 MCP token 后启用认证"

    return f"""# Stock Datasource — 工具配置

## MCP Server

- **名称**: stock-data
- **类型**: streamable-http
- **URL**: {mcp_url}
- **认证**: {auth_line}
- **工具数量**: 76+

### 常用 MCP 工具分类

| 类别 | 工具示例 | 说明 |
|------|---------|------|
| 行情查询 | query_stock_daily, query_stock_kline | 日K/周K/月K数据 |
| 财务分析 | query_financial_report, query_balance_sheet | 财报/资产负债表 |
| 选股筛选 | screen_stocks, screen_by_indicator | 多维度条件筛选 |
| 指数数据 | query_index_daily, query_index_components | 指数行情/成分股 |
| ETF 数据 | query_etf_daily, query_etf_holdings | ETF 行情/持仓 |
| 港股数据 | query_hk_daily, query_hk_financial | 港股行情/财报 |
| 新闻研报 | search_knowledge, query_announcements | 研报/公告检索 |

## 实时数据

- **WebSocket**: {ws_url}
- **默认订阅**: 00700.HK, 09988.HK, 600519.SH
- **数据类型**: 逐笔成交、分钟K线、盘口快照

## 微信 Channel

- **类型**: weixin
- **状态**: 已启用
- **登录**: `picoclaw auth weixin`
"""


def generate_user_md() -> str:
    """生成 USER.md — 用户偏好。"""
    return """# Stock Datasource — 用户偏好

## 基本信息

- **语言**: 中文
- **时区**: Asia/Shanghai (UTC+8)
- **交易时间**: A股 09:30-15:00, 港股 09:30-16:00

## 沟通偏好

- 回复使用中文
- 数据展示优先使用表格
- 金额单位默认人民币（CNY），港股标注港币（HKD）
- 价格默认保留2位小数，百分比保留2位

## 关注市场

- A股（上海/深圳）
- 港股（港股通标的）

## 数据偏好

- 优先使用最新数据
- 技术指标默认日K周期
- 财务数据使用最近一期报告
"""


def generate_identity_md() -> str:
    """生成 IDENTITY.md — Agent 身份设定。"""
    return """# Stock Datasource — 身份设定

- **名称**: Stock Datasource 助手
- **类型**: 专业股票数据分析 AI
- **版本**: 1.0
- **创建者**: Stock Datasource Platform

你是 Stock Datasource 平台的智能助手，专注于为用户提供准确、专业的股票数据分析服务。你不是一个通用聊天机器人——你是金融数据分析专家。
"""


def generate_heartbeat_md() -> str:
    """生成 HEARTBEAT.md — 周期任务提示。"""
    return """# Stock Datasource — 周期任务

## 定时检查项（每30分钟）

- [ ] 检查是否有新的用户消息需要处理
- [ ] 如果用户关注了特定股票，可以主动推送重要行情变化（涨跌幅超5%）
- [ ] 盘中时段（09:30-15:00）检查实时数据连接状态

## 注意事项

- 非交易时段不推送行情提醒
- 不主动发送消息打扰用户，除非有重要变化
- 每日收盘后可提供当日市场总结（如果用户订阅）
"""


def write_workspace_files(workspace_dir: Path, agents: list[dict],
                          mcp_url: str, ws_url: str, mcp_token: str | None) -> None:
    """将所有 workspace md 文件写入 PicoClaw 的 ~/.picoclaw/workspace/ 目录。

    PicoClaw workspace 目录结构:
      ~/.picoclaw/workspace/
      ├── AGENTS.md          # Agent 行为指南（最高优先级，每次会话加载）
      ├── SOUL.md            # 灵魂设定（性格与风格，每次会话加载）
      ├── IDENTITY.md        # 身份设定（名称与角色）
      ├── USER.md            # 用户偏好（沟通方式、市场偏好）
      ├── TOOLS.md           # 工具说明（MCP配置、数据源）
      ├── HEARTBEAT.md       # 周期任务提示（每30分钟检查）
      ├── memory/            # 长期记忆目录
      ├── sessions/          # 对话历史
      ├── state/             # 运行状态
      ├── cron/              # 定时任务
      └── skills/            # 自定义技能
    """
    workspace_dir.mkdir(parents=True, exist_ok=True)

    # 创建子目录
    for subdir in ("memory", "sessions", "state", "cron", "skills"):
        (workspace_dir / subdir).mkdir(exist_ok=True)

    # 写入 md 文件
    files = {
        "AGENTS.md": generate_agents_md(agents),
        "SOUL.md": generate_soul_md(),
        "IDENTITY.md": generate_identity_md(),
        "USER.md": generate_user_md(),
        "TOOLS.md": generate_tools_md(mcp_url, ws_url, mcp_token),
        "HEARTBEAT.md": generate_heartbeat_md(),
    }

    for filename, content in files.items():
        path = workspace_dir / filename
        path.write_text(content, encoding="utf-8")
        print(f"  [OK] {path}")

    print(f"\n[OK] Workspace 文件已写入 {workspace_dir}")


# ---------------------------------------------------------------------------
# YAML 配置生成
# ---------------------------------------------------------------------------

def generate_config(
    env: dict[str, str],
    mcp_url: str,
    mcp_token: str | None,
    ws_url: str,
    gateway_port: int = 18790,
) -> str:
    """生成 picoclaw YAML 配置内容"""

    api_key = env.get("OPENAI_API_KEY", "")
    base_url = env.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = env.get("OPENAI_MODEL", "gpt-4")

    if not api_key:
        print("[ERROR] 未找到 OPENAI_API_KEY，请确保 .env 文件中已配置", file=sys.stderr)
        sys.exit(1)

    # 去掉 base_url 末尾的 /
    base_url = base_url.rstrip("/")

    config = f"""# ============================================
# PicoClaw 配置 — 自动生成于 stock_datasource
# 来源: generate_picoclaw_config.py
# ============================================

model_list:
  - model: "{model}"
    base_url: "{base_url}"
    api_key: "{api_key}"
    model_type: "openai-chat"

gateway:
  host: "127.0.0.1"
  port: {gateway_port}

# MCP Server 连接 — 连接 stock_datasource 的数据库查询能力
mcp_servers:
  stock-data:
    type: "streamable-http"
    url: "{mcp_url}"
    headers:
      Authorization: "Bearer {mcp_token or '<YOUR_MCP_TOKEN>'}"

# Channel 配置
channels:
  weixin:
    type: "weixin"
    enabled: true

# 实时数据订阅配置（供 Agent 使用）
# 通过 MCP 工具或 WebSocket 连接获取实时行情
realtime_data:
  websocket_url: "{ws_url}"
  symbols_default: ["00700.HK", "600519.SH", "09988.HK"]
"""
    return config


def main():
    parser = argparse.ArgumentParser(
        description="从项目 .env + AgentRegistry 生成 picoclaw 配置及 workspace 文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 generate_picoclaw_config.py
  python3 generate_picoclaw_config.py --output ./my-picoclaw.yaml
  python3 generate_picoclaw_config.py --mcp-token sk-xxx123
  python3 generate_picoclaw_config.py --no-workspace
  STOCK_MCP_TOKEN=sk-xxx python3 generate_picoclaw_config.py

PicoClaw workspace md 文件说明:
  AGENTS.md      — Agent 行为指南 + 能力路由（最高优先级，每次会话加载）
  SOUL.md        — 灵魂设定（性格与沟通风格）
  IDENTITY.md    — 身份设定（名称与角色定义）
  USER.md        — 用户偏好（语言、市场、数据习惯）
  TOOLS.md       — 工具说明（MCP Server、WebSocket 配置）
  HEARTBEAT.md   — 周期任务提示（每30分钟检查一次）
""",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="输出配置文件路径 (默认: <project>/.local/picoclaw.yaml)",
    )
    parser.add_argument(
        "--mcp-url",
        default=os.environ.get(
            "STOCK_MCP_SERVER_URL",
            "http://localhost:8001/messages",
        ),
        help="MCP 服务 URL",
    )
    parser.add_argument(
        "--mcp-token",
        default=os.environ.get("STOCK_MCP_TOKEN", ""),
        help="MCP 认证 token",
    )
    parser.add_argument(
        "--ws-url",
        default="ws://localhost:8765",
        help="实时数据 WebSocket 地址",
    )
    parser.add_argument(
        "--workspace",
        default=None,
        help="PicoClaw workspace 目录 (默认: ~/.picoclaw/workspace)",
    )
    parser.add_argument(
        "--no-workspace",
        action="store_true",
        help="不生成 workspace md 文件，仅生成 yaml 配置",
    )
    args = parser.parse_args()

    # 加载 .env
    env = load_env()

    # 输出路径
    default_output = PROJECT_ROOT / ".local" / "picoclaw.yaml"
    output_path = Path(args.output) if args.output else default_output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 生成 yaml 配置
    yaml_content = generate_config(
        env=env,
        mcp_url=args.mcp_url,
        mcp_token=args.mcp_token or None,
        ws_url=args.ws_url,
    )

    output_path.write_text(yaml_content, encoding="utf-8")
    print(f"[OK] 配置文件已生成: {output_path}")
    print(f"[OK] MCP URL: {args.mcp_url}")
    print(f"[OK] LLM 模型: {env.get('OPENAI_MODEL', 'unknown')}")

    if not args.mcp_token and not os.environ.get("STOCK_MCP_TOKEN"):
        print("[WARN] 未设置 MCP token，请在生成的配置文件中填入有效的认证令牌")

    # 生成 workspace md 文件
    if not args.no_workspace:
        # 收集 Agent 能力
        print("\n--- 收集 Agent 能力描述 ---")
        agents = collect_agent_capabilities()
        print(f"[OK] 发现 {len(agents)} 个已注册 Agent")

        # 确定 workspace 目录
        workspace_dir = (
            Path(args.workspace) if args.workspace
            else Path.home() / ".picoclaw" / "workspace"
        )

        print(f"\n--- 生成 PicoClaw Workspace 文件 ---")
        write_workspace_files(
            workspace_dir=workspace_dir,
            agents=agents,
            mcp_url=args.mcp_url,
            ws_url=args.ws_url,
            mcp_token=args.mcp_token or None,
        )


if __name__ == "__main__":
    main()
