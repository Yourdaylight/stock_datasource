"""Configuration viewer and editor (``config show`` / ``config set``).

Provides:
  - ``config show`` — Display current configuration grouped by category,
    with passwords and tokens masked for security.
  - ``config set KEY=VALUE`` — Safely modify a single entry in the ``.env``
    file while preserving comments and formatting.  A ``.env.bak`` backup
    is created before each write.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Dict, List, Tuple

import click

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_ENV_FILE = _PROJECT_ROOT / ".env"

# Keys that should be masked when displayed
_SECRET_KEYS = {
    "TUSHARE_TOKEN", "OPENAI_API_KEY", "FINNHUB_API_KEY",
    "LANGFUSE_SECRET_KEY", "LANGFUSE_PUBLIC_KEY",
    "CLICKHOUSE_PASSWORD", "REDIS_PASSWORD",
    "HTTP_PROXY_PASSWORD", "WEKNORA_API_KEY",
    "MCP_USAGE_REPORT_KEY",
}

# Configuration groups for display
_CONFIG_GROUPS: List[Tuple[str, List[str]]] = [
    ("API Keys", [
        "TUSHARE_TOKEN", "FINNHUB_API_KEY",
    ]),
    ("LLM / OpenAI", [
        "OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL",
    ]),
    ("ClickHouse", [
        "CLICKHOUSE_HOST", "CLICKHOUSE_PORT", "CLICKHOUSE_HTTP_PORT",
        "CLICKHOUSE_USER", "CLICKHOUSE_PASSWORD", "CLICKHOUSE_DATABASE",
    ]),
    ("Redis", [
        "REDIS_HOST", "REDIS_PORT", "REDIS_PASSWORD", "REDIS_DB",
    ]),
    ("Langfuse", [
        "LANGFUSE_HOST", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY",
    ]),
    ("HTTP Proxy", [
        "HTTP_PROXY_ENABLED", "HTTP_PROXY_HOST", "HTTP_PROXY_PORT",
    ]),
    ("WeKnora", [
        "WEKNORA_ENABLED", "WEKNORA_BASE_URL", "WEKNORA_API_KEY", "WEKNORA_KB_IDS",
    ]),
    ("Application", [
        "APP_PORT", "DEBUG", "LOG_LEVEL", "DATA_START_DATE",
        "DAILY_UPDATE_TIME", "TIMEZONE",
    ]),
]


def _mask(value: str, visible: int = 4) -> str:
    """Mask a secret value for display."""
    if not value:
        return "(not set)"
    if len(value) <= visible:
        return value
    return value[:visible] + "****"


def _read_env() -> Dict[str, str]:
    """Read .env file into a dict."""
    env: Dict[str, str] = {}
    if not _ENV_FILE.exists():
        return env
    for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" in stripped:
            key, _, value = stripped.partition("=")
            env[key.strip()] = value.strip()
    return env


def _set_env_value(key: str, value: str) -> bool:
    """Set a single key in the .env file, preserving format.

    Returns True if the key was found and updated, False if appended.
    """
    if not _ENV_FILE.exists():
        _ENV_FILE.write_text(f"{key}={value}\n", encoding="utf-8")
        return False

    # Backup
    backup = _PROJECT_ROOT / ".env.bak"
    shutil.copy2(_ENV_FILE, backup)

    lines = _ENV_FILE.read_text(encoding="utf-8").splitlines()
    found = False
    new_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            line_key = stripped.split("=", 1)[0].strip()
            if line_key == key:
                new_lines.append(f"{key}={value}")
                found = True
                continue
        new_lines.append(line)

    if not found:
        new_lines.append(f"{key}={value}")

    _ENV_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return found


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@click.group("config")
def config():
    """View and modify project configuration.

    Configuration is stored in the .env file at the project root.
    Use ``config show`` to view and ``config set`` to modify.
    """
    pass


@config.command("show")
@click.option("--reveal", is_flag=True, default=False, help="Show secrets in plain text (use with caution)")
@click.option("--group", "group_filter", default=None, help="Show only a specific group (e.g. 'ClickHouse', 'Redis')")
def show(reveal: bool, group_filter: str):
    """Display current configuration (secrets are masked by default).

    Examples:

      \b
      stock-ds config show
      stock-ds config show --reveal
      stock-ds config show --group ClickHouse
    """
    env = _read_env()

    if not env:
        click.secho("  No .env file found. Run `stock-ds setup` first.", fg="yellow")
        return

    click.echo("")
    click.secho("╔══════════════════════════════════════════════════╗", fg="bright_blue")
    click.secho("║     Current Configuration                       ║", fg="bright_blue")
    click.secho("╚══════════════════════════════════════════════════╝", fg="bright_blue")

    for group_name, keys in _CONFIG_GROUPS:
        if group_filter and group_filter.lower() != group_name.lower():
            continue

        click.echo("")
        click.secho(f"  [{group_name}]", fg="cyan", bold=True)

        for key in keys:
            value = env.get(key, "")
            if key in _SECRET_KEYS and not reveal:
                display_value = _mask(value)
            else:
                display_value = value or "(not set)"
            click.echo(f"    {key:<30} = {display_value}")

    # Show any keys not in predefined groups
    all_grouped_keys = {k for _, keys in _CONFIG_GROUPS for k in keys}
    extra_keys = sorted(set(env.keys()) - all_grouped_keys)
    if extra_keys and not group_filter:
        click.echo("")
        click.secho("  [Other]", fg="cyan", bold=True)
        for key in extra_keys:
            value = env[key]
            if key in _SECRET_KEYS and not reveal:
                display_value = _mask(value)
            else:
                display_value = value or "(not set)"
            click.echo(f"    {key:<30} = {display_value}")

    click.echo("")
    click.echo(f"  Config file: {_ENV_FILE}")
    if not reveal:
        click.echo("  (Use --reveal to show secrets in plain text)")
    click.echo("")


@config.command("set")
@click.argument("pairs", nargs=-1, required=True)
def set_config(pairs):
    """Set configuration value(s) in the .env file.

    Pass one or more KEY=VALUE pairs. A backup (.env.bak) is created
    before each write.

    Examples:

      \b
      stock-ds config set OPENAI_MODEL=gpt-4o
      stock-ds config set REDIS_HOST=localhost REDIS_PORT=6379
      stock-ds config set TUSHARE_TOKEN=your_token_here
    """
    click.echo("")

    for pair in pairs:
        if "=" not in pair:
            click.secho(f"  ✗ Invalid format: '{pair}', expected KEY=VALUE", fg="red")
            continue

        key, _, value = pair.partition("=")
        key = key.strip()
        value = value.strip()

        if not key:
            click.secho(f"  ✗ Empty key in: '{pair}'", fg="red")
            continue

        existed = _set_env_value(key, value)
        action = "updated" if existed else "added"

        # Show masked value for secrets
        display = _mask(value) if key in _SECRET_KEYS else value
        click.secho(f"  ✓ {key}={display} ({action})", fg="green")

    click.echo("")
    click.echo(f"  Backup saved to: {_PROJECT_ROOT / '.env.bak'}")
    click.echo("  Note: Restart services for changes to take effect.")
    click.echo("")
