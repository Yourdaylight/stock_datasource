"""Service layer for WeChat Bridge (picoclaw) operations."""

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

# Paths relative to project root
PROJECT_ROOT = Path(__file__).resolve().parents[4]
LOCAL_DIR = PROJECT_ROOT / ".local"
BIN_DIR = LOCAL_DIR / "bin"
PICOCLAW_BIN = BIN_DIR / "picoclaw"
PID_FILE = LOCAL_DIR / "picoclaw.pid"
RT_PID_FILE = LOCAL_DIR / "subscribe_rt.pid"
CONFIG_FILE = LOCAL_DIR / "picoclaw.yaml"
LOG_FILE = LOCAL_DIR / "picoclaw.log"

# GitHub release info
PICOCLAW_GITHUB_REPO = "sipeed/picoclaw"

# 国内镜像列表（按优先级排列，DIRECT 表示 GitHub 直连）
_DEFAULT_MIRRORS = [
    "https://ghfast.top",
    "https://ghproxy.cc",
    "DIRECT",
]


def _detect_arch() -> tuple[str, str]:
    """Detect system architecture for binary download.

    Returns (os_part, arch_part) matching GitHub release naming convention:
      picoclaw_{OS}_{ARCH}.tar.gz
    """
    import platform as _pf

    machine = _pf.machine().lower()
    system = _pf.system().lower()

    # OS mapping
    if system == "linux":
        os_name = "Linux"
    elif system in ("darwin", "macos"):
        os_name = "Darwin"
    elif system == "freebsd":
        os_name = "Freebsd"
    else:
        raise RuntimeError(f"Unsupported OS: {system}")

    # Arch mapping (GitHub release uses GoReleaser conventions)
    arch_map = {
        "x86_64": "x86_64",
        "amd64": "x86_64",
        "aarch64": "aarch64",
        "arm64": "aarch64",
        "riscv64": "riscv64",
    }
    arch = arch_map.get(machine)
    if not arch:
        raise RuntimeError(f"Unsupported architecture: {machine}")

    return os_name, arch


def _get_latest_version() -> str:
    """Query GitHub API for latest picoclaw release tag.

    Tries GitHub API directly first, then falls back to mirror proxies
    for users in China where api.github.com may be blocked.
    """
    api_url = f"https://api.github.com/repos/{PICOCLAW_GITHUB_REPO}/releases/latest"

    # Try direct connection first
    req = urllib.request.Request(
        api_url,
        headers={
            "User-Agent": "stock-datasource",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        tag = data.get("tag_name")
        if tag:
            return tag
    except Exception as e:
        logger.warning(f"GitHub API direct failed ({e}), trying mirrors...")

    # Fallback to mirror proxies for GitHub API
    for mirror in _DEFAULT_MIRRORS:
        if mirror == "DIRECT":
            continue
        mirrored_url = f"{mirror}/{api_url}"
        try:
            req = urllib.request.Request(
                mirrored_url, headers={"User-Agent": "stock-datasource"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            tag = data.get("tag_name")
            if tag:
                logger.info(f"Got version via mirror {mirror}: {tag}")
                return tag
        except Exception:
            continue

    # Last resort: known good version
    logger.warning("All GitHub API sources failed, falling back to v0.2.6")
    return "v0.2.6"


def _download_with_mirrors(github_path: str, dest_path: str) -> None:
    """Download a file from GitHub with mirror fallback for China users.

    Tries each mirror in order.  The PICOCLAW_MIRROR env var can be set
    to force a specific mirror prefix (e.g. "https://ghfast.top").
    """
    mirrors = list(_DEFAULT_MIRRORS)
    custom = os.environ.get("PICOCLAW_MIRROR")
    if custom:
        mirrors = [custom, "DIRECT"]

    github_base = "https://github.com"
    errors: list[str] = []

    for mirror in mirrors:
        if mirror == "DIRECT":
            url = f"{github_base}{github_path}"
        else:
            url = f"{mirror}/{github_base}{github_path}"

        logger.info(f"Trying download: {url}")
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "stock-datasource"}
            )
            with urllib.request.urlopen(req, timeout=180) as resp:
                with open(dest_path, "wb") as f:
                    shutil.copyfileobj(resp, f)
            logger.info(f"Download succeeded via {mirror}")
            return
        except Exception as e:
            errors.append(f"{mirror}: {e}")
            logger.warning(f"Download failed via {mirror}: {e}")
            continue

    raise RuntimeError(
        f"All download sources failed for {github_path}. Errors:\n"
        + "\n".join(f"  - {e}" for e in errors)
    )


def _download_picoclaw(version: str | None = None) -> str:
    """Download picoclaw binary from GitHub releases and install to BIN_DIR.

    Uses mirror proxies (ghfast.top, ghproxy.cc) as fallback when GitHub
    is not directly accessible (common in mainland China).
    Returns version string of installed binary.
    """
    # Detect architecture
    os_part, arch_part = _detect_arch()

    # Determine version
    if not version:
        version = _get_latest_version()
    elif not version.startswith("v"):
        version = f"v{version}"

    # Build download path — matches GoReleaser output format:
    #   /sipeed/picoclaw/releases/download/v0.2.5/picoclaw_Linux_x86_64.tar.gz
    filename = f"picoclaw_{os_part}_{arch_part}.tar.gz"
    github_path = f"/{PICOCLAW_GITHUB_REPO}/releases/download/{version}/{filename}"

    logger.info(f"Downloading picoclaw {version} ({os_part}-{arch_part})")

    # Download tar.gz to temp file (with mirror fallback)
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".tar.gz", prefix="picoclaw_")
    try:
        os.close(tmp_fd)  # _download_with_mirrors opens its own file handle
        _download_with_mirrors(github_path, tmp_path)
    except Exception:
        os.unlink(tmp_path)
        raise

    # Extract tar.gz and install binary
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    dest = str(PICOCLAW_BIN)
    try:
        import tarfile

        with tarfile.open(tmp_path, "r:gz") as tar:
            # Find the picoclaw member
            member = None
            for m in tar.getmembers():
                name = m.name.split("/")[-1]
                if name == "picoclaw":
                    member = m
                    break
            if member is None:
                raise RuntimeError(
                    f"'picoclaw' not found inside {filename}. "
                    f"Available members: {[m.name for m in tar.getmembers()[:10]]}"
                )
            with open(dest, "wb") as out_f:
                shutil.copyfileobj(tar.extractfile(member), out_f)
            os.chmod(dest, 0o755)
    except Exception:
        # Clean up partial file
        if os.path.exists(dest):
            os.unlink(dest)
        raise
    finally:
        os.unlink(tmp_path)

    # Verify installation
    try:
        ver_result = subprocess.run(
            [dest, "--version"], capture_output=True, text=True, timeout=5
        )
        installed_ver = (
            ver_result.stdout.strip() or ver_result.stderr.strip() or "unknown"
        )
    except Exception:
        installed_ver = "unknown"

    logger.info(f"Picoclaw installed to {dest} (version: {installed_ver})")
    return installed_ver


def _read_pid(file_path: Path) -> int | None:
    """Read PID from file, return None if not running."""
    if not file_path.exists():
        return None
    try:
        pid_str = file_path.read_text().strip()
        pid = int(pid_str)
        os.kill(pid, 0)  # Check if process exists
        return pid
    except (ValueError, ProcessLookupError, OSError):
        return None


def get_status() -> dict:
    """Get current status of all picoclaw-related services."""
    # Check if binary is installed
    installed = PICOCLAW_BIN.is_file() and os.access(PICOCLAW_BIN, os.X_OK)

    # Get version if installed (extract clean version from output)
    version = None
    if installed:
        try:
            result = subprocess.run(
                [str(PICOCLAW_BIN), "version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            raw = result.stdout + result.stderr
            # Strip ANSI escape codes
            import re

            clean = re.sub(r"\x1b\[[0-9;]*m", "", raw)
            # Find version pattern like "picoclaw 0.2.5" or "v0.2.5"
            m = re.search(r"picoclaw\s+(v?[\d.]+)", clean)
            if m:
                version = m.group(1)
            else:
                # Fallback: find any semver
                m2 = re.search(r"(v?\d+\.\d+\.\d+)", clean)
                version = m2.group(1) if m2 else "unknown"
        except Exception:
            version = "unknown"

    # Check if running
    main_pid = _read_pid(PID_FILE)
    rt_pid = _read_pid(RT_PID_FILE)

    return {
        "installed": installed,
        "version": version,
        "running": main_pid is not None,
        "pid": main_pid,
        "port": 18790 if main_pid else None,
        "gateway_url": "http://127.0.0.1:18790" if main_pid else None,
        "rt_running": rt_pid is not None,
        "rt_pid": rt_pid,
        "config_exists": PICOCLAW_CONFIG.exists(),
        "config_path": str(PICOCLAW_CONFIG),
    }


PICOCLAW_CONFIG = Path("/root/.picoclaw/config.json")


def generate_config(mcp_token: str | None = None) -> dict:
    """Update picoclaw config.json with model + MCP + weixin settings."""
    from dotenv import load_dotenv

    env_file = PROJECT_ROOT / ".env"
    load_dotenv(env_file)

    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip(
        "/"
    )
    model = os.environ.get("OPENAI_MODEL", "gpt-4")

    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in .env")

    token = mcp_token or os.environ.get("STOCK_MCP_TOKEN", "")

    # Initialize config from onboard if missing
    if not PICOCLAW_CONFIG.exists():
        PICOCLAW_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                [str(PICOCLAW_BIN), "onboard"],
                capture_output=True,
                timeout=10,
                check=False,
            )
        except Exception:
            pass

    # Load existing config or start fresh
    cfg = {}
    if PICOCLAW_CONFIG.exists():
        try:
            cfg = json.loads(PICOCLAW_CONFIG.read_text(encoding="utf-8"))
        except Exception:
            cfg = {}

    # Set model_list (picoclaw requires both "model" and "model_name")
    cfg["model_list"] = [
        {
            "model": model,
            "model_name": model,
            "base_url": base_url,
            "api_key": api_key,
            "model_type": "openai-chat",
        }
    ]

    # Set gateway
    cfg["gateway"] = {"host": "0.0.0.0", "port": 18790}

    # Set weixin channel
    channels = cfg.get("channels", {})
    channels["weixin"] = channels.get("weixin", {})
    channels["weixin"]["enabled"] = True
    cfg["channels"] = channels

    # Set MCP
    tools = cfg.get("tools", {})
    mcp_cfg = tools.get("mcp", {"enabled": False})
    mcp_cfg["enabled"] = True
    if "servers" not in mcp_cfg:
        mcp_cfg["servers"] = {}
    mcp_cfg["servers"]["stock-data"] = {
        "type": "streamable-http",
        "url": "http://localhost:8001/messages",
        "headers": {"Authorization": f"Bearer {token}"} if token else {},
    }
    tools["mcp"] = mcp_cfg
    cfg["tools"] = tools

    PICOCLAW_CONFIG.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info(f"Config written to {PICOCLAW_CONFIG}")

    # Auto-inject workspace md files (AGENTS.md, SOUL.md, etc.)
    _inject_workspace_md(token)

    return {
        "llm_model": model,
        "llm_base_url": base_url,
        "mcp_server_url": "http://localhost:8001/messages",
        "mcp_connected": bool(token),
        "channel_weixin_enabled": True,
        "config_path": str(PICOCLAW_CONFIG),
    }


PICOCLAW_WORKSPACE = Path.home() / ".picoclaw" / "workspace"


def _inject_workspace_md(mcp_token: str | None = None) -> dict:
    """Inject workspace md files into PicoClaw's ~/.picoclaw/workspace/.

    This ensures PicoClaw has full knowledge of stock_datasource's
    agent capabilities, personality, and tool configuration.

    Each md file serves a distinct purpose:
      AGENTS.md     — Agent behavior guide + capability routing (highest priority)
      SOUL.md       — Personality and communication style
      IDENTITY.md   — Agent name and role definition
      USER.md       — User preferences (language, markets, data habits)
      TOOLS.md      — MCP / WebSocket tool descriptions
      HEARTBEAT.md  — Periodic task prompts (checked every 30 min)
    """
    try:
        from stock_datasource.services.agent_registrations import register_all_agents
        from stock_datasource.services.agent_registry import (
            AgentRole,
            get_agent_registry,
        )

        register_all_agents()
        registry = get_agent_registry()

        agents = []
        for desc in registry.list_descriptors(role=AgentRole.AGENT, enabled_only=True):
            agents.append(
                {
                    "name": desc.name,
                    "description": desc.description,
                    "markets": desc.capability.markets,
                    "intents": desc.capability.intents,
                    "tags": desc.capability.tags,
                    "priority": desc.priority,
                }
            )
    except Exception as e:
        logger.warning(f"Failed to collect agent capabilities from registry: {e}")
        agents = []

    PICOCLAW_WORKSPACE.mkdir(parents=True, exist_ok=True)
    for subdir in ("memory", "sessions", "state", "cron", "skills"):
        (PICOCLAW_WORKSPACE / subdir).mkdir(exist_ok=True)

    mcp_url = "http://localhost:8001/messages"
    ws_url = "ws://localhost:8765"

    # Generate and write each md file
    files_to_write = {
        "AGENTS.md": _build_agents_md(agents),
        "SOUL.md": _build_soul_md(),
        "IDENTITY.md": _build_identity_md(),
        "USER.md": _build_user_md(),
        "TOOLS.md": _build_tools_md(mcp_url, ws_url, mcp_token),
        "HEARTBEAT.md": _build_heartbeat_md(),
    }

    written = []
    for filename, content in files_to_write.items():
        path = PICOCLAW_WORKSPACE / filename
        path.write_text(content, encoding="utf-8")
        written.append(filename)

    logger.info(
        f"Injected {len(written)} workspace md files to {PICOCLAW_WORKSPACE}: {', '.join(written)}"
    )
    return {"workspace_dir": str(PICOCLAW_WORKSPACE), "files": written}


def _build_agents_md(agents: list[dict]) -> str:
    """Build AGENTS.md — Agent behavior guide (highest priority)."""
    if not agents:
        agent_section = "- MarketAgent: A股和港股行情分析 (市场: A, HK)\n- ChatAgent: 通用对话助手 (市场: 通用)"
    else:
        lines = []
        for a in sorted(agents, key=lambda x: -x["priority"]):
            markets = ", ".join(a["markets"]) if a["markets"] else "通用"
            lines.append(f"- **{a['name']}**: {a['description']} (市场: {markets})")
        agent_section = "\n".join(lines)

    return f"""# Stock Datasource — Agent 行为指南

你是 **Stock Datasource** 智能股票分析平台的 AI 助手。

## 可用 Agent

{agent_section}

## 路由规则

1. 行情/K线/技术分析 → MarketAgent
2. A股财报/基本面 → ReportAgent
3. 港股财报 → HKReportAgent
4. 选股筛选 → ScreenerAgent
5. 策略回测 → BacktestAgent
6. 投资组合 → PortfolioAgent
7. 指数分析 → IndexAgent
8. ETF分析 → EtfAgent
9. 市场概览 → OverviewAgent
10. 龙虎榜 → TopListAgent
11. 新闻 → NewsAnalystAgent
12. 研报/公告 → KnowledgeAgent
13. 自选股/偏好 → MemoryAgent
14. 数据管理 → DataManageAgent
15. 一般对话 → ChatAgent

## MCP 工具

通过 MCP Server 连接 76+ 数据查询工具。优先使用 MCP 获取数据。
A股代码: 600519.SH | 港股代码: 00700.HK

## 安全边界

- 不提供投资建议
- 不预测股价涨跌
- 历史数据不代表未来表现
"""


def _build_soul_md() -> str:
    return """# Stock Datasource — 灵魂设定

## 性格
专业、严谨、耐心的股票数据分析助手。

## 沟通风格
- 中文回复，专业术语保留英文
- 数据标注来源和时效
- 先结论后细节
- 表格整理对比数据
- 模糊问题主动澄清

## 决策原则
1. 数据准确 > 回复速度
2. 客观事实 > 主观判断
3. 风险提示 > 收益描述
"""


def _build_identity_md() -> str:
    return """# Stock Datasource — 身份设定

- **名称**: Stock Datasource 助手
- **类型**: 专业股票数据分析 AI
- **版本**: 1.0
"""


def _build_user_md() -> str:
    return """# Stock Datasource — 用户偏好

- **语言**: 中文
- **时区**: Asia/Shanghai (UTC+8)
- **A股交易时间**: 09:30-15:00
- **港股交易时间**: 09:30-16:00
- **金额单位**: 人民币(CNY)，港股标注港币(HKD)
"""


def _build_tools_md(mcp_url: str, ws_url: str, mcp_token: str | None) -> str:
    auth = f"Bearer {mcp_token}" if mcp_token else "未设置"
    return f"""# Stock Datasource — 工具配置

## MCP Server
- URL: {mcp_url}
- 认证: {auth}
- 工具数: 76+

## 实时数据
- WebSocket: {ws_url}
- 默认订阅: 00700.HK, 09988.HK, 600519.SH

## 微信 Channel
- 类型: weixin
- 状态: 已启用
"""


def _build_heartbeat_md() -> str:
    return """# Stock Datasource — 周期任务

## 每30分钟检查
- 检查新用户消息
- 关注股票涨跌幅超5%时推送提醒
- 盘中检查实时数据连接

## 注意
- 非交易时段不推送行情
- 不主动打扰用户
"""


def start_bridge(symbols: str | None = None, no_rt: bool = False) -> dict:
    """Start picoclaw + realtime subscription."""
    status = get_status()

    # Auto-download if binary missing
    if not status["installed"]:
        logger.info("Picoclaw not installed, downloading...")
        try:
            installed_ver = _download_picoclaw()
        except Exception as e:
            raise RuntimeError(f"Failed to download picoclaw: {e}")

    # Generate config
    generate_config()

    # Kill old process if any
    old_pid = _read_pid(PID_FILE)
    if old_pid:
        try:
            os.kill(old_pid, 15)  # SIGTERM
        except OSError:
            pass
        if PID_FILE.exists():
            PID_FILE.unlink()

    if RT_PID_FILE.exists() and _read_pid(RT_PID_FILE):
        try:
            os.kill(_read_pid(RT_PID_FILE), 15)
        except OSError:
            pass
        if RT_PID_FILE.exists():
            RT_PID_FILE.unlink()

    # Ensure bin dir in PATH
    env = os.environ.copy()
    env["PATH"] = str(BIN_DIR) + ":" + env.get("PATH", "")

    # Start picoclaw
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    log_fh = open(LOG_FILE, "w")

    proc = subprocess.Popen(
        [str(PICOCLAW_BIN), "gateway"],
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        env=env,
        cwd=str(PROJECT_ROOT),
        start_new_session=True,
    )

    PID_FILE.write_text(str(proc.pid))

    # Start realtime subscription unless disabled
    rt_pid = None
    if not no_rt:
        subscribe_script = (
            PROJECT_ROOT
            / "skills"
            / "stock-rt-subscribe"
            / "scripts"
            / "subscribe_client.py"
        )
        if subscribe_script.exists():
            default_symbols = symbols or "00700.HK,09988.HK,600519.SH"
            rt_symbols = default_symbols.replace(",", " ")

            rt_log = LOCAL_DIR / "subscribe_rt.log"
            rt_log_f = open(rt_log, "w")

            rt_proc = subprocess.Popen(
                [sys.executable, str(subscribe_script), "--symbols"]
                + rt_symbols.split(),
                stdout=rt_log_f,
                stderr=rt_log_f,
                cwd=str(PROJECT_ROOT),
                start_new_session=True,
            )
            RT_PID_FILE.write_text(str(rt_proc.pid))
            rt_pid = rt_proc.pid
            logger.info(f"RT subscription started (PID: {rt_pid})")
        else:
            logger.warning(
                f"RT subscribe script not found at {subscribe_script}. "
                f"Skipping realtime data subscription."
            )

    return {
        "success": True,
        "message": f"Picoclaw started (PID: {proc.pid})"
        + (f", RT subscription started (PID: {rt_pid})" if rt_pid else ""),
        "pid": proc.pid,
        "rt_pid": rt_pid,
    }


def stop_bridge() -> dict:
    """Stop all picoclaw-related processes."""
    stopped = []

    main_pid = _read_pid(PID_FILE)
    if main_pid:
        try:
            os.kill(main_pid, 15)
            stopped.append(f"picoclaw ({main_pid})")
        except OSError:
            pass
        if PID_FILE.exists():
            PID_FILE.unlink()

    rt_pid = _read_pid(RT_PID_FILE)
    if rt_pid:
        try:
            os.kill(rt_pid, 15)
            stopped.append(f"RT subscription ({rt_pid})")
        except OSError:
            pass
        if RT_PID_FILE.exists():
            RT_PID_FILE.unlink()

    return {
        "success": True,
        "message": f"Stopped: {', '.join(stopped) or 'nothing running'}",
    }


def get_config_preview() -> dict:
    """Return current config preview without secrets."""
    if PICOCLAW_CONFIG.exists():
        try:
            cfg = json.loads(PICOCLAW_CONFIG.read_text(encoding="utf-8"))
        except Exception:
            return {
                "exists": False,
                "error": "config parse error",
                "config_path": str(PICOCLAW_CONFIG),
            }

        # Extract key info, mask secrets
        model_list = cfg.get("model_list", [])
        m = model_list[0] if model_list else {}
        channels = cfg.get("channels", {})
        weixin = channels.get("weixin", {})

        # Build safe config text
        safe_cfg = json.loads(json.dumps(cfg))
        for item in safe_cfg.get("model_list", []):
            if "api_key" in item:
                item["api_key"] = "***masked***"

        return {
            "llm_model": m.get("model_name", ""),
            "llm_base_url": m.get("base_url", ""),
            "mcp_server_url": "",
            "mcp_connected": False,
            "channel_weixin_enabled": weixin.get("enabled", False),
            "config_path": str(PICOCLAW_CONFIG),
            "raw_config": json.dumps(safe_cfg, indent=2, ensure_ascii=False)[:3000],
        }

    return {
        "llm_model": "",
        "llm_base_url": "",
        "mcp_server_url": "",
        "mcp_connected": False,
        "ws_realtime_url": "ws://localhost:8765",
        "channel_weixin_enabled": False,
        "config_path": str(CONFIG_FILE),
        "raw_config": "# No config generated yet",
    }
