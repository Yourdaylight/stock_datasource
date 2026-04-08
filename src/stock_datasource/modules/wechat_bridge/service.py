"""Service layer for WeChat Bridge (picoclaw) operations."""

import subprocess
import os
import sys
import json
import logging
import platform
import urllib.request
import tempfile
import shutil
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

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
        "amd64":  "x86_64",
        "aarch64": "aarch64",
        "arm64":  "aarch64",
        "riscv64":"riscv64",
    }
    arch = arch_map.get(machine)
    if not arch:
        raise RuntimeError(f"Unsupported architecture: {machine}")
    
    return os_name, arch


def _get_latest_version() -> str:
    """Query GitHub API for latest picoclaw release tag."""
    url = f"https://api.github.com/repos/{PICOCLAW_GITHUB_REPO}/releases/latest"
    req = urllib.request.Request(url, headers={
        "User-Agent": "stock-datasource",
        "Accept": "application/vnd.github+json",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        tag = data.get("tag_name")
        if not tag:
            raise RuntimeError("No tag_name in GitHub release response")
        return tag
    except Exception as e:
        # Fallback to a known good version
        logger.warning(f"Failed to fetch latest version from GitHub API ({e}), falling back to v0.2.5")
        return "v0.2.5"


def _download_picoclaw(version: Optional[str] = None) -> str:
    """Download picoclaw binary from GitHub releases and install to BIN_DIR.
    
    The release asset is a .tar.gz archive containing the 'picoclaw' binary.
    Returns version string of installed binary.
    """
    # Detect architecture
    os_part, arch_part = _detect_arch()

    # Determine version
    if not version:
        version = _get_latest_version()
    elif not version.startswith("v"):
        version = f"v{version}"

    # Build download URL — matches GoReleaser output format:
    #   https://github.com/sipeed/picoclaw/releases/download/v0.2.5/picoclaw_Linux_x86_64.tar.gz
    filename = f"picoclaw_{os_part}_{arch_part}.tar.gz"
    download_url = (
        f"https://github.com/{PICOCLAW_GITHUB_REPO}"
        f"/releases/download/{version}/{filename}"
    )

    logger.info(f"Downloading picoclaw {version} ({os_part}-{arch_part}) -> {download_url}")

    # Download tar.gz to temp file
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".tar.gz", prefix="picoclaw_")
    try:
        req = urllib.request.Request(download_url, headers={"User-Agent": "stock-datasource"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            with os.fdopen(tmp_fd, "wb") as f:
                shutil.copyfileobj(resp, f)
    except Exception:
        os.unlink(tmp_path)
        raise RuntimeError(
            f"Failed to download picoclaw from {download_url}. "
            f"Check network connectivity and verify URL."
        )

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
        ver_result = subprocess.run([dest, "--version"], capture_output=True, text=True, timeout=5)
        installed_ver = ver_result.stdout.strip() or ver_result.stderr.strip() or "unknown"
    except Exception:
        installed_ver = "unknown"

    logger.info(f"Picoclaw installed to {dest} (version: {installed_ver})")
    return installed_ver


def _read_pid(file_path: Path) -> Optional[int]:
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
                capture_output=True, text=True, timeout=5,
            )
            raw = result.stdout + result.stderr
            # Strip ANSI escape codes
            import re
            clean = re.sub(r'\x1b\[[0-9;]*m', '', raw)
            # Find version pattern like "picoclaw 0.2.5" or "v0.2.5"
            m = re.search(r'picoclaw\s+(v?[\d.]+)', clean)
            if m:
                version = m.group(1)
            else:
                # Fallback: find any semver
                m2 = re.search(r'(v?\d+\.\d+\.\d+)', clean)
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
        "gateway_url": f"http://127.0.0.1:18790" if main_pid else None,
        "rt_running": rt_pid is not None,
        "rt_pid": rt_pid,
        "config_exists": PICOCLAW_CONFIG.exists(),
        "config_path": str(PICOCLAW_CONFIG),
    }


PICOCLAW_CONFIG = Path("/root/.picoclaw/config.json")


def generate_config(mcp_token: Optional[str] = None) -> dict:
    """Update picoclaw config.json with model + MCP + weixin settings."""
    from dotenv import load_dotenv

    env_file = PROJECT_ROOT / ".env"
    load_dotenv(env_file)

    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
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
                capture_output=True, timeout=10, check=False,
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
    cfg["model_list"] = [{
        "model": model,
        "model_name": model,
        "base_url": base_url,
        "api_key": api_key,
        "model_type": "openai-chat",
    }]

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

    PICOCLAW_CONFIG.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Config written to {PICOCLAW_CONFIG}")

    return {
        "llm_model": model,
        "llm_base_url": base_url,
        "mcp_server_url": "http://localhost:8001/messages",
        "mcp_connected": bool(token),
        "channel_weixin_enabled": True,
        "config_path": str(PICOCLAW_CONFIG),
    }


def start_bridge(symbols: Optional[str] = None, no_rt: bool = False) -> dict:
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
            PROJECT_ROOT / "skills" / "stock-rt-subscribe" / "scripts" / "subscribe_client.py"
        )
        if subscribe_script.exists():
            default_symbols = symbols or "00700.HK,09988.HK,600519.SH"
            rt_symbols = default_symbols.replace(",", " ")
            
            rt_log = LOCAL_DIR / "subscribe_rt.log"
            rt_log_f = open(rt_log, "w")
            
            rt_proc = subprocess.Popen(
                [sys.executable, str(subscribe_script), "--symbols"] + rt_symbols.split(),
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
        "message": f"Picoclaw started (PID: {proc.pid})" + (f", RT subscription started (PID: {rt_pid})" if rt_pid else ""),
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
    
    return {"success": True, "message": f"Stopped: {', '.join(stopped) or 'nothing running'}"}


def get_config_preview() -> dict:
    """Return current config preview without secrets."""
    if PICOCLAW_CONFIG.exists():
        try:
            cfg = json.loads(PICOCLAW_CONFIG.read_text(encoding="utf-8"))
        except Exception:
            return {"exists": False, "error": "config parse error", "config_path": str(PICOCLAW_CONFIG)}

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
