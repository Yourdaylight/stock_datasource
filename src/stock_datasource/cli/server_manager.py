"""Service lifecycle management (``server start/stop/restart/status``).

Provides a Python-native replacement for ``restart.sh``, managing three
local services:
  - **backend** — FastAPI HTTP server (port 8000)
  - **mcp** — MCP server (port 8001)
  - **frontend** — Vite dev server (port 3000+)

Also supports Docker Compose mode when ``--docker`` is passed.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import click

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_LOG_DIR = _PROJECT_ROOT / "logs"
_PID_DIR = _LOG_DIR / "pids"

_SERVICES = {
    "backend": {
        "cmd": ["uv", "run", "python", "-m", "stock_datasource.services.http_server"],
        "cwd": str(_PROJECT_ROOT),
        "log": "backend.log",
        "pid": "backend.pid",
        "port": 8000,
        "health_url": "http://localhost:8000/health",
        "health_timeout": 120,
        "label": "Backend API",
    },
    "mcp": {
        "cmd": ["uv", "run", "python", "-m", "stock_datasource.services.mcp_server"],
        "cwd": str(_PROJECT_ROOT),
        "log": "mcp.log",
        "pid": "mcp.pid",
        "port": 8001,
        "health_url": "http://localhost:8001/health",
        "health_timeout": 30,
        "label": "MCP Server",
    },
    "frontend": {
        "cmd": ["npm", "run", "dev"],
        "cwd": str(_PROJECT_ROOT / "frontend"),
        "log": "frontend.log",
        "pid": "frontend.pid",
        "port": 3000,
        "health_url": None,  # frontend health checked by port
        "health_timeout": 25,
        "label": "Frontend",
    },
}

ALL_SERVICE_NAMES = list(_SERVICES.keys())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_dirs():
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    _PID_DIR.mkdir(parents=True, exist_ok=True)


def _read_pid(name: str) -> Optional[int]:
    pid_file = _PID_DIR / _SERVICES[name]["pid"]
    if not pid_file.exists():
        return None
    try:
        pid = int(pid_file.read_text().strip())
        return pid
    except (ValueError, OSError):
        return None


def _write_pid(name: str, pid: int):
    pid_file = _PID_DIR / _SERVICES[name]["pid"]
    pid_file.write_text(str(pid))


def _remove_pid(name: str):
    pid_file = _PID_DIR / _SERVICES[name]["pid"]
    pid_file.unlink(missing_ok=True)


def _is_running(pid: int) -> bool:
    """Check if a process is alive."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _stop_process(pid: int, label: str, timeout: int = 10) -> bool:
    """Gracefully stop a process (SIGTERM, then SIGKILL after timeout)."""
    if not _is_running(pid):
        return True

    click.echo(f"  Stopping {label} (PID: {pid})...")
    try:
        os.kill(pid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        return True

    for _ in range(timeout * 2):
        time.sleep(0.5)
        if not _is_running(pid):
            return True

    # Force kill
    click.echo(f"  Force killing {label} (PID: {pid})...")
    try:
        os.kill(pid, signal.SIGKILL)
        time.sleep(0.5)
    except (OSError, ProcessLookupError):
        pass
    return not _is_running(pid)


def _wait_for_health(service_name: str, pid: int) -> bool:
    """Wait for a service to become healthy."""
    svc = _SERVICES[service_name]
    timeout = svc["health_timeout"]
    health_url = svc["health_url"]

    if health_url:
        import requests
        for i in range(timeout):
            time.sleep(1)
            if not _is_running(pid):
                return False
            try:
                resp = requests.get(health_url, timeout=2)
                if resp.status_code == 200:
                    return True
            except Exception:
                pass
        return False
    else:
        # For frontend, check if port is listening
        import socket
        port = svc["port"]
        for i in range(timeout):
            time.sleep(1)
            if not _is_running(pid):
                return False
            # Check ports 3000-3005 and 5173
            for p in [port, 3001, 3002, 3003, 3004, 3005, 5173]:
                try:
                    with socket.create_connection(("localhost", p), timeout=1):
                        # Update the port if different from default
                        if p != port:
                            svc["_actual_port"] = p
                        return True
                except OSError:
                    continue
        return False


def _get_service_status(name: str) -> Dict:
    """Get status info for a single service."""
    pid = _read_pid(name)
    svc = _SERVICES[name]
    result = {
        "name": name,
        "label": svc["label"],
        "port": svc.get("_actual_port", svc["port"]),
        "pid": pid,
        "running": False,
    }
    if pid and _is_running(pid):
        result["running"] = True
    return result


# ---------------------------------------------------------------------------
# Docker compose helpers
# ---------------------------------------------------------------------------

def _has_docker() -> bool:
    """Check if docker and docker compose are available."""
    try:
        subprocess.run(["docker", "compose", "version"], capture_output=True, timeout=5)
        return True
    except Exception:
        pass
    try:
        subprocess.run(["docker-compose", "version"], capture_output=True, timeout=5)
        return True
    except Exception:
        return False


def _docker_compose_cmd() -> List[str]:
    """Return the appropriate docker compose command."""
    try:
        subprocess.run(["docker", "compose", "version"], capture_output=True, timeout=5, check=True)
        return ["docker", "compose"]
    except Exception:
        return ["docker-compose"]


def _docker_compose_files(include_infra: bool = False) -> List[str]:
    """Build the list of -f flags for docker compose."""
    files = ["-f", str(_PROJECT_ROOT / "docker-compose.yml")]
    if include_infra:
        infra = _PROJECT_ROOT / "docker-compose.infra.yml"
        if infra.exists():
            files.extend(["-f", str(infra)])
    return files


# ---------------------------------------------------------------------------
# Click commands
# ---------------------------------------------------------------------------

@click.group("server")
def server():
    """Manage application services (start/stop/restart/status).

    Supports two modes:
      - **Local mode** (default): manages backend, mcp, and frontend processes
      - **Docker mode** (--docker): uses docker compose
    """
    pass


@server.command("start")
@click.option("--service", "-s", multiple=True, type=click.Choice(ALL_SERVICE_NAMES + ["all"]),
              default=["all"], help="Service(s) to start (default: all)")
@click.option("--docker", "use_docker", is_flag=True, default=False,
              help="Use Docker Compose instead of local processes")
@click.option("--with-infra", is_flag=True, default=False,
              help="(Docker mode) Also start infrastructure (ClickHouse, Redis)")
def start(service, use_docker, with_infra):
    """Start application services.

    Examples:

      \b
      stock-ds server start                  # Start all local services
      stock-ds server start -s backend       # Start backend only
      stock-ds server start --docker         # Start via docker compose
      stock-ds server start --docker --with-infra  # Start app + infrastructure
    """
    if use_docker:
        _docker_start(with_infra)
        return

    _ensure_dirs()
    services_to_start = ALL_SERVICE_NAMES if "all" in service else list(service)

    click.echo("")
    click.secho("  Starting services...", fg="bright_blue", bold=True)
    click.echo("")

    for idx, name in enumerate(services_to_start, 1):
        svc = _SERVICES[name]
        click.echo(f"  [{idx}/{len(services_to_start)}] Starting {svc['label']}...")

        # Check if already running
        existing_pid = _read_pid(name)
        if existing_pid and _is_running(existing_pid):
            click.secho(f"  → Already running (PID: {existing_pid})", fg="yellow")
            continue

        # Check if cwd exists (especially for frontend)
        cwd = Path(svc["cwd"])
        if not cwd.exists():
            click.secho(f"  ✗ Directory not found: {cwd}", fg="red")
            continue

        # Start the process
        log_file = _LOG_DIR / svc["log"]
        with open(log_file, "a") as log_f:
            try:
                proc = subprocess.Popen(
                    svc["cmd"],
                    cwd=svc["cwd"],
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,  # Detach from terminal
                )
            except FileNotFoundError as e:
                click.secho(f"  ✗ Command not found: {e}", fg="red")
                if name == "frontend":
                    click.echo("    Hint: Run 'cd frontend && npm install' first")
                elif "uv" in svc["cmd"][0]:
                    click.echo("    Hint: Install uv: https://docs.astral.sh/uv/")
                continue

        _write_pid(name, proc.pid)
        click.echo(f"  → PID: {proc.pid}, waiting for health check...")

        # Wait for health
        if _wait_for_health(name, proc.pid):
            actual_port = svc.get("_actual_port", svc["port"])
            click.secho(f"  ✓ {svc['label']} started (http://localhost:{actual_port})", fg="green")
        else:
            if _is_running(proc.pid):
                click.secho(f"  ⚠ {svc['label']} started but health check timed out", fg="yellow")
                click.echo(f"    Check logs: tail -f {log_file}")
            else:
                click.secho(f"  ✗ {svc['label']} process exited unexpectedly", fg="red")
                click.echo(f"    Check logs: tail -f {log_file}")
                _remove_pid(name)
        click.echo("")

    _print_status_summary()


@server.command("stop")
@click.option("--service", "-s", multiple=True, type=click.Choice(ALL_SERVICE_NAMES + ["all"]),
              default=["all"], help="Service(s) to stop (default: all)")
@click.option("--docker", "use_docker", is_flag=True, default=False,
              help="Use Docker Compose instead of local processes")
def stop(service, use_docker):
    """Stop application services.

    Examples:

      \b
      stock-ds server stop              # Stop all services
      stock-ds server stop -s backend   # Stop backend only
      stock-ds server stop --docker     # Stop docker compose services
    """
    if use_docker:
        _docker_stop()
        return

    services_to_stop = ALL_SERVICE_NAMES if "all" in service else list(service)

    click.echo("")
    click.secho("  Stopping services...", fg="bright_blue", bold=True)
    click.echo("")

    for name in services_to_stop:
        svc = _SERVICES[name]
        pid = _read_pid(name)
        if not pid:
            click.echo(f"  {svc['label']}: not running (no PID file)")
            continue

        if not _is_running(pid):
            click.echo(f"  {svc['label']}: not running (stale PID {pid})")
            _remove_pid(name)
            continue

        if _stop_process(pid, svc["label"]):
            click.secho(f"  ✓ {svc['label']} stopped", fg="green")
        else:
            click.secho(f"  ✗ Failed to stop {svc['label']} (PID: {pid})", fg="red")
        _remove_pid(name)

    click.echo("")


@server.command("restart")
@click.option("--service", "-s", multiple=True, type=click.Choice(ALL_SERVICE_NAMES + ["all"]),
              default=["all"], help="Service(s) to restart (default: all)")
@click.option("--docker", "use_docker", is_flag=True, default=False,
              help="Use Docker Compose instead of local processes")
@click.option("--with-infra", is_flag=True, default=False,
              help="(Docker mode) Also restart infrastructure")
def restart(service, use_docker, with_infra):
    """Restart application services (stop then start).

    Examples:

      \b
      stock-ds server restart
      stock-ds server restart -s backend
      stock-ds server restart --docker --with-infra
    """
    ctx = click.get_current_context()

    # Invoke stop
    ctx.invoke(stop, service=service, use_docker=use_docker)
    # Invoke start
    ctx.invoke(start, service=service, use_docker=use_docker, with_infra=with_infra)


@server.command("status")
@click.option("--docker", "use_docker", is_flag=True, default=False,
              help="Show Docker Compose status instead")
def status(use_docker):
    """Show service status.

    Examples:

      \b
      stock-ds server status
      stock-ds server status --docker
    """
    if use_docker:
        _docker_status()
        return

    click.echo("")
    click.secho("╔══════════════════════════════════════════════════╗", fg="bright_blue")
    click.secho("║     Service Status                              ║", fg="bright_blue")
    click.secho("╚══════════════════════════════════════════════════╝", fg="bright_blue")
    click.echo("")

    _print_status_summary()

    # Also show Docker infra status if available
    if _has_docker():
        click.echo("  Docker Infrastructure:")
        for container in ["stock-clickhouse", "stock-redis", "stock-postgres"]:
            try:
                result = subprocess.run(
                    ["docker", "inspect", "-f", "{{.State.Status}}", container],
                    capture_output=True, text=True, timeout=5,
                )
                state = result.stdout.strip() if result.returncode == 0 else "not found"
                if state == "running":
                    click.secho(f"    {container}: running", fg="green")
                else:
                    click.secho(f"    {container}: {state}", fg="red")
            except Exception:
                click.echo(f"    {container}: unknown")
        click.echo("")


def _print_status_summary():
    """Print a summary table of local service status."""
    for name in ALL_SERVICE_NAMES:
        info = _get_service_status(name)
        if info["running"]:
            click.secho(
                f"  {info['label']:<16} {click.style('● running', fg='green')}  "
                f"PID: {info['pid']}  http://localhost:{info['port']}",
            )
        else:
            click.secho(
                f"  {info['label']:<16} {click.style('○ stopped', fg='red')}",
            )

    click.echo("")
    click.echo("  Logs directory: " + str(_LOG_DIR))
    click.echo("")


# ---------------------------------------------------------------------------
# Docker helpers
# ---------------------------------------------------------------------------

def _docker_start(with_infra: bool):
    click.echo("")
    click.secho("  Starting services via Docker Compose...", fg="bright_blue", bold=True)
    click.echo("")
    cmd = _docker_compose_cmd() + _docker_compose_files(include_infra=with_infra) + ["up", "-d"]
    click.echo(f"  $ {' '.join(cmd)}")
    click.echo("")
    result = subprocess.run(cmd, cwd=str(_PROJECT_ROOT))
    if result.returncode == 0:
        click.secho("  ✓ Docker Compose services started", fg="green")
    else:
        click.secho("  ✗ Docker Compose failed", fg="red")
    click.echo("")


def _docker_stop():
    click.echo("")
    click.secho("  Stopping Docker Compose services...", fg="bright_blue", bold=True)
    click.echo("")
    cmd = _docker_compose_cmd() + ["-f", str(_PROJECT_ROOT / "docker-compose.yml"), "down"]
    click.echo(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(_PROJECT_ROOT))
    if result.returncode == 0:
        click.secho("  ✓ Services stopped", fg="green")
    else:
        click.secho("  ✗ Docker Compose stop failed", fg="red")
    click.echo("")


def _docker_status():
    click.echo("")
    click.secho("  Docker Compose Status:", fg="bright_blue", bold=True)
    click.echo("")
    cmd = _docker_compose_cmd() + ["-f", str(_PROJECT_ROOT / "docker-compose.yml"), "ps"]
    subprocess.run(cmd, cwd=str(_PROJECT_ROOT))
    click.echo("")
