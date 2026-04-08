#!/usr/bin/env python3
"""
generate_picoclaw_config.py — 从项目 .env 生成 picoclaw 配置文件

用法:
  python3 skills/stock-data-assistant/generate_picoclaw_config.py [选项]

选项:
  --output PATH    输出配置文件路径 (默认: .local/picoclaw.yaml)
  --mcp-url URL     MCP 服务 URL (默认: 从环境变量或 http://localhost:8001/messages)
  --mcp-token TOKEN MCP 认证 token (默认: 从 STOCK_MCP_TOKEN 环境变量读取)
  --ws-url URL      实时数据 WebSocket 地址 (默认: ws://localhost:8765)
  --help            显示帮助信息

生成的配置包含:
  1. LLM 模型配置（复用项目的 OPENAI_API_KEY/BASE_URL/MODEL）
  2. MCP Server 连接（连接 stock_datasource 的 MCP 服务）
  3. 微信 Channel 配置
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
        description="从项目 .env 生成 picoclaw 配置",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 generate_picoclaw_config.py
  python3 generate_picoclaw_config.py --output ./my-picoclaw.yaml
  python3 generate_picoclaw_config.py --mcp-token sk-xxx123
  STOCK_MCP_TOKEN=sk-xxx python3 generate_picoclaw_config.py
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
    args = parser.parse_args()

    # 加载 .env
    env = load_env()

    # 输出路径
    default_output = PROJECT_ROOT / ".local" / "picoclaw.yaml"
    output_path = Path(args.output) if args.output else default_output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 生成配置
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


if __name__ == "__main__":
    main()
