"""Interactive setup wizard for first-time deployment configuration.

Guides users step-by-step through configuring:
  1. Tushare Token (required)
  2. LLM / OpenAI API (required)
  3. ClickHouse connection
  4. Redis connection
  5. Langfuse (optional)
  6. HTTP Proxy (optional)

Each step supports connectivity validation, skip (use defaults), and retry.
Final result is written to the project-root `.env` file.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import click

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PROJECT_ROOT = (
    Path(__file__).resolve().parents[3]
)  # src/stock_datasource/cli -> project root
_ENV_FILE = _PROJECT_ROOT / ".env"
_ENV_EXAMPLE = _PROJECT_ROOT / ".env.example"


def _mask(value: str, visible: int = 4) -> str:
    """Mask a secret string, showing only the first *visible* characters."""
    if not value:
        return "(not set)"
    if len(value) <= visible:
        return value
    return value[:visible] + "****"


def _read_env_dict() -> dict[str, str]:
    """Read existing .env file into an ordered dict (preserving order)."""
    env: dict[str, str] = {}
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


def _write_env_file(updates: dict[str, str]) -> None:
    """Write *updates* into .env, preserving comments and order.

    If a key already exists the line is replaced in-place; new keys are
    appended at the end.  A `.env.bak` backup is created before writing.
    """
    # Ensure we have a base file
    if not _ENV_FILE.exists():
        if _ENV_EXAMPLE.exists():
            shutil.copy2(_ENV_EXAMPLE, _ENV_FILE)
        else:
            _ENV_FILE.write_text("", encoding="utf-8")

    # Backup
    backup = _ENV_FILE.with_suffix(".env.bak")
    shutil.copy2(_ENV_FILE, backup)

    lines = _ENV_FILE.read_text(encoding="utf-8").splitlines()
    remaining = dict(updates)  # keys still to write
    new_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in remaining:
                new_lines.append(f"{key}={remaining.pop(key)}")
                continue
        new_lines.append(line)

    # Append any remaining new keys
    if remaining:
        new_lines.append("")
        new_lines.append("# --- Added by setup wizard ---")
        for key, value in remaining.items():
            new_lines.append(f"{key}={value}")

    _ENV_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Connectivity validators (each returns (ok: bool, message: str))
# ---------------------------------------------------------------------------


def _validate_tushare(token: str) -> tuple[bool, str]:
    """Validate Tushare token by calling a lightweight API."""
    try:
        import tushare as ts

        pro = ts.pro_api(token)
        df = pro.trade_cal(exchange="SSE", start_date="20250101", end_date="20250105")
        if df is not None and len(df) > 0:
            return True, f"OK — retrieved {len(df)} calendar rows"
        return False, "API returned empty data, token may be invalid"
    except Exception as e:
        return False, f"Connection failed: {e}"


def _validate_llm(api_key: str, base_url: str, model: str) -> tuple[bool, str]:
    """Validate LLM API by sending a tiny completion request."""
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url, timeout=15)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=5,
        )
        content = resp.choices[0].message.content or ""
        return True, f"OK — model responded: {content[:30]}"
    except Exception as e:
        return False, f"LLM call failed: {e}"


def _validate_clickhouse(
    host: str, port: int, user: str, password: str, database: str
) -> tuple[bool, str]:
    """Validate ClickHouse connectivity."""
    try:
        from clickhouse_driver import Client

        client = Client(
            host=host,
            port=port,
            user=user,
            password=password,
            database="default",
            connect_timeout=5,
            send_receive_timeout=5,
        )
        result = client.execute("SELECT version()")
        version = result[0][0] if result else "unknown"
        return True, f"OK — ClickHouse {version}"
    except Exception as e:
        return False, f"Connection failed: {e}"


def _validate_redis(
    host: str, port: int, password: str | None, db: int
) -> tuple[bool, str]:
    """Validate Redis connectivity."""
    try:
        import redis

        r = redis.Redis(
            host=host,
            port=port,
            password=password or None,
            db=db,
            socket_timeout=5,
            socket_connect_timeout=5,
        )
        info = r.info("server")
        version = info.get("redis_version", "unknown")
        return True, f"OK — Redis {version}"
    except Exception as e:
        return False, f"Connection failed: {e}"


# ---------------------------------------------------------------------------
# Step definitions
# ---------------------------------------------------------------------------


def _step_tushare(env: dict[str, str]) -> dict[str, str]:
    click.echo("")
    click.secho("━" * 50, fg="cyan")
    click.secho("  Step 1/6: Tushare Token (Required)", fg="cyan", bold=True)
    click.secho("━" * 50, fg="cyan")
    click.echo("  Tushare provides A-share market data.")
    click.echo("  Get your token at: https://tushare.pro/register?reg=7")
    click.echo("")

    current = env.get("TUSHARE_TOKEN", "")
    if current and current != "your_tushare_token_here":
        click.echo(f"  Current: {_mask(current)}")
        if not click.confirm("  Change it?", default=False):
            return {}

    while True:
        token = click.prompt(
            "  Tushare Token",
            default=current if current != "your_tushare_token_here" else "",
        )
        if not token:
            click.secho("  ✗ Token is required, please enter a valid token.", fg="red")
            continue

        click.echo("  Validating...")
        ok, msg = _validate_tushare(token)
        if ok:
            click.secho(f"  ✓ {msg}", fg="green")
            return {"TUSHARE_TOKEN": token}
        else:
            click.secho(f"  ✗ {msg}", fg="red")
            if not click.confirm("  Retry?", default=True):
                return {"TUSHARE_TOKEN": token}


def _step_llm(env: dict[str, str]) -> dict[str, str]:
    click.echo("")
    click.secho("━" * 50, fg="cyan")
    click.secho("  Step 2/6: LLM / OpenAI API (Required)", fg="cyan", bold=True)
    click.secho("━" * 50, fg="cyan")
    click.echo("  Used for AI-powered stock analysis.")
    click.echo("  Supports OpenAI-compatible APIs (e.g. DeepSeek, Moonshot).")
    click.echo("")

    current_key = env.get("OPENAI_API_KEY", "")
    current_url = env.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    current_model = env.get("OPENAI_MODEL", "gpt-4")

    if current_key and current_key != "your_openai_api_key_here":
        click.echo(
            f"  Current: key={_mask(current_key)}, url={current_url}, model={current_model}"
        )
        if not click.confirm("  Change it?", default=False):
            return {}

    api_key = click.prompt(
        "  API Key",
        default=current_key if current_key != "your_openai_api_key_here" else "",
    )
    base_url = click.prompt("  Base URL", default=current_url)
    model = click.prompt("  Model name", default=current_model)

    if api_key:
        click.echo("  Validating...")
        ok, msg = _validate_llm(api_key, base_url, model)
        if ok:
            click.secho(f"  ✓ {msg}", fg="green")
        else:
            click.secho(f"  ✗ {msg}", fg="yellow")
            click.echo(
                "  (Saved anyway — you can fix it later with `stock-ds config set`)"
            )

    result = {}
    if api_key:
        result["OPENAI_API_KEY"] = api_key
    result["OPENAI_BASE_URL"] = base_url
    result["OPENAI_MODEL"] = model
    return result


def _step_clickhouse(env: dict[str, str]) -> dict[str, str]:
    click.echo("")
    click.secho("━" * 50, fg="cyan")
    click.secho("  Step 3/6: ClickHouse Database", fg="cyan", bold=True)
    click.secho("━" * 50, fg="cyan")
    click.echo("  ClickHouse stores all time-series market data.")
    click.echo("  If using docker-compose.infra.yml, keep defaults.")
    click.echo("")

    defaults = {
        "CLICKHOUSE_HOST": env.get("CLICKHOUSE_HOST", "localhost"),
        "CLICKHOUSE_PORT": env.get("CLICKHOUSE_PORT", "9000"),
        "CLICKHOUSE_USER": env.get("CLICKHOUSE_USER", "clickhouse"),
        "CLICKHOUSE_PASSWORD": env.get("CLICKHOUSE_PASSWORD", "clickhouse"),
        "CLICKHOUSE_DATABASE": env.get("CLICKHOUSE_DATABASE", "stock_datasource"),
    }

    if click.confirm("  Use default ClickHouse settings?", default=True):
        click.echo(f"  → {defaults['CLICKHOUSE_HOST']}:{defaults['CLICKHOUSE_PORT']}")
        result = dict(defaults)
    else:
        host = click.prompt("  Host", default=defaults["CLICKHOUSE_HOST"])
        port = click.prompt("  Native port", default=defaults["CLICKHOUSE_PORT"])
        user = click.prompt("  User", default=defaults["CLICKHOUSE_USER"])
        password = click.prompt(
            "  Password",
            default=defaults["CLICKHOUSE_PASSWORD"],
            hide_input=True,
            show_default=False,
            prompt_suffix=" (hidden): ",
        )
        database = click.prompt("  Database", default=defaults["CLICKHOUSE_DATABASE"])
        result = {
            "CLICKHOUSE_HOST": host,
            "CLICKHOUSE_PORT": str(port),
            "CLICKHOUSE_USER": user,
            "CLICKHOUSE_PASSWORD": password,
            "CLICKHOUSE_DATABASE": database,
        }

    # Validate
    click.echo("  Validating...")
    ok, msg = _validate_clickhouse(
        result["CLICKHOUSE_HOST"],
        int(result["CLICKHOUSE_PORT"]),
        result["CLICKHOUSE_USER"],
        result["CLICKHOUSE_PASSWORD"],
        result["CLICKHOUSE_DATABASE"],
    )
    if ok:
        click.secho(f"  ✓ {msg}", fg="green")
    else:
        click.secho(f"  ✗ {msg}", fg="yellow")
        click.echo(
            "  (Saved anyway — make sure ClickHouse is running before starting services)"
        )
    return result


def _step_redis(env: dict[str, str]) -> dict[str, str]:
    click.echo("")
    click.secho("━" * 50, fg="cyan")
    click.secho("  Step 4/6: Redis", fg="cyan", bold=True)
    click.secho("━" * 50, fg="cyan")
    click.echo("  Redis is used for task queue, caching, and real-time data streams.")
    click.echo("")

    defaults = {
        "REDIS_HOST": env.get("REDIS_HOST", "localhost"),
        "REDIS_PORT": env.get("REDIS_PORT", "6379"),
        "REDIS_PASSWORD": env.get("REDIS_PASSWORD", ""),
        "REDIS_DB": env.get("REDIS_DB", "1"),
    }

    if click.confirm("  Use default Redis settings?", default=True):
        click.echo(f"  → {defaults['REDIS_HOST']}:{defaults['REDIS_PORT']}")
        result = dict(defaults)
    else:
        host = click.prompt("  Host", default=defaults["REDIS_HOST"])
        port = click.prompt("  Port", default=defaults["REDIS_PORT"])
        password = click.prompt(
            "  Password",
            default=defaults["REDIS_PASSWORD"],
            hide_input=True,
            show_default=False,
            prompt_suffix=" (hidden, empty for none): ",
        )
        db = click.prompt("  DB number", default=defaults["REDIS_DB"])
        result = {
            "REDIS_HOST": host,
            "REDIS_PORT": str(port),
            "REDIS_PASSWORD": password,
            "REDIS_DB": str(db),
        }

    click.echo("  Validating...")
    ok, msg = _validate_redis(
        result["REDIS_HOST"],
        int(result["REDIS_PORT"]),
        result["REDIS_PASSWORD"] or None,
        int(result["REDIS_DB"]),
    )
    if ok:
        click.secho(f"  ✓ {msg}", fg="green")
    else:
        click.secho(f"  ✗ {msg}", fg="yellow")
        click.echo(
            "  (Saved anyway — make sure Redis is running before starting services)"
        )
    return result


def _step_langfuse(env: dict[str, str]) -> dict[str, str]:
    click.echo("")
    click.secho("━" * 50, fg="cyan")
    click.secho(
        "  Step 5/6: Langfuse — AI Observability (Optional)", fg="cyan", bold=True
    )
    click.secho("━" * 50, fg="cyan")
    click.echo("  Langfuse tracks LLM calls, costs, and latency.")
    click.echo("")

    if not click.confirm("  Configure Langfuse?", default=False):
        click.echo("  → Skipped")
        return {}

    host = click.prompt("  Langfuse Host URL", default=env.get("LANGFUSE_HOST", ""))
    public_key = click.prompt(
        "  Public Key", default=env.get("LANGFUSE_PUBLIC_KEY", "")
    )
    secret_key = click.prompt(
        "  Secret Key",
        default=env.get("LANGFUSE_SECRET_KEY", ""),
        hide_input=True,
        show_default=False,
        prompt_suffix=" (hidden): ",
    )

    result: dict[str, str] = {}
    if host:
        result["LANGFUSE_HOST"] = host
    if public_key:
        result["LANGFUSE_PUBLIC_KEY"] = public_key
    if secret_key:
        result["LANGFUSE_SECRET_KEY"] = secret_key
    return result


def _step_proxy(env: dict[str, str]) -> dict[str, str]:
    click.echo("")
    click.secho("━" * 50, fg="cyan")
    click.secho("  Step 6/6: HTTP Proxy (Optional)", fg="cyan", bold=True)
    click.secho("━" * 50, fg="cyan")
    click.echo(
        "  Required if your network restricts direct access to Tushare / OpenAI."
    )
    click.echo("")

    if not click.confirm("  Configure HTTP proxy?", default=False):
        click.echo("  → Skipped")
        return {"HTTP_PROXY_ENABLED": "false"}

    host = click.prompt("  Proxy host", default=env.get("HTTP_PROXY_HOST", ""))
    port = click.prompt("  Proxy port", default=env.get("HTTP_PROXY_PORT", ""))

    result = {
        "HTTP_PROXY_ENABLED": "true",
        "HTTP_PROXY_HOST": host,
        "HTTP_PROXY_PORT": str(port),
    }
    return result


# ---------------------------------------------------------------------------
# Main command
# ---------------------------------------------------------------------------


@click.command("setup")
@click.option(
    "--non-interactive",
    is_flag=True,
    default=False,
    help="Skip interactive prompts, validate existing .env only",
)
def setup(non_interactive: bool):
    """Interactive setup wizard for first-time deployment.

    Walks you through configuring all required services (Tushare, LLM,
    ClickHouse, Redis) and optional integrations (Langfuse, Proxy).
    Results are saved to the .env file.

    Example:

      \b
      stock-ds setup          # Interactive wizard
      stock-ds setup --non-interactive  # Validate existing .env only
    """
    click.echo("")
    click.secho(
        "╔══════════════════════════════════════════════════╗", fg="bright_blue"
    )
    click.secho("║     Stock Datasource — Setup Wizard             ║", fg="bright_blue")
    click.secho(
        "╚══════════════════════════════════════════════════╝", fg="bright_blue"
    )
    click.echo("")

    env = _read_env_dict()

    if non_interactive:
        click.echo(
            "Running in non-interactive mode — validating existing configuration..."
        )
        _validate_existing(env)
        return

    click.echo("This wizard will guide you through the initial configuration.")
    click.echo("Press Ctrl+C at any time to abort (changes won't be saved).")
    click.echo("")

    all_updates: dict[str, str] = {}

    try:
        steps = [
            _step_tushare,
            _step_llm,
            _step_clickhouse,
            _step_redis,
            _step_langfuse,
            _step_proxy,
        ]
        for step_fn in steps:
            updates = step_fn(env)
            all_updates.update(updates)
            # Merge into env so subsequent steps see updated values
            env.update(updates)
    except click.Abort:
        click.echo("")
        click.secho("  Setup aborted — no changes were saved.", fg="yellow")
        return

    # Write to .env
    click.echo("")
    click.secho("━" * 50, fg="green")
    click.secho("  Writing configuration...", fg="green", bold=True)
    click.secho("━" * 50, fg="green")

    if all_updates:
        _write_env_file(all_updates)
        click.secho(f"  ✓ {len(all_updates)} settings saved to {_ENV_FILE}", fg="green")
        if (_ENV_FILE.with_suffix(".env.bak")).exists():
            click.echo(f"  ✓ Backup saved to {_ENV_FILE.with_suffix('.env.bak')}")
    else:
        click.echo("  No changes to write.")

    # Summary
    click.echo("")
    click.secho("━" * 50, fg="bright_blue")
    click.secho("  Configuration Summary", fg="bright_blue", bold=True)
    click.secho("━" * 50, fg="bright_blue")
    _print_summary(env)

    # Next steps
    click.echo("")
    click.secho("  Next steps:", bold=True)
    click.echo(
        "  1. Start infrastructure:  docker compose -f docker-compose.infra.yml up -d"
    )
    click.echo("  2. Check environment:     stock-ds doctor")
    click.echo("  3. Initialize database:   stock-ds init-db")
    click.echo("  4. Start services:        stock-ds server start")
    click.echo("")


def _validate_existing(env: dict[str, str]):
    """Validate existing configuration without prompting."""
    checks = [
        (
            "Tushare Token",
            bool(env.get("TUSHARE_TOKEN"))
            and env.get("TUSHARE_TOKEN") != "your_tushare_token_here",
        ),
        (
            "OpenAI API Key",
            bool(env.get("OPENAI_API_KEY"))
            and env.get("OPENAI_API_KEY") != "your_openai_api_key_here",
        ),
        ("ClickHouse Host", bool(env.get("CLICKHOUSE_HOST"))),
        ("Redis Host", bool(env.get("REDIS_HOST"))),
    ]
    all_ok = True
    for name, ok in checks:
        if ok:
            click.secho(f"  ✓ {name}", fg="green")
        else:
            click.secho(f"  ✗ {name} — not configured", fg="red")
            all_ok = False

    if all_ok:
        click.secho("\n  All required settings are present.", fg="green")
    else:
        click.secho(
            "\n  Some required settings are missing. Run `stock-ds setup` interactively.",
            fg="yellow",
        )


def _print_summary(env: dict[str, str]):
    """Print a masked configuration summary."""
    rows = [
        ("Tushare Token", _mask(env.get("TUSHARE_TOKEN", ""))),
        ("OpenAI API Key", _mask(env.get("OPENAI_API_KEY", ""))),
        ("OpenAI Base URL", env.get("OPENAI_BASE_URL", "")),
        ("OpenAI Model", env.get("OPENAI_MODEL", "")),
        (
            "ClickHouse",
            f"{env.get('CLICKHOUSE_HOST', '')}:{env.get('CLICKHOUSE_PORT', '')}",
        ),
        ("Redis", f"{env.get('REDIS_HOST', '')}:{env.get('REDIS_PORT', '')}"),
        (
            "Langfuse Host",
            env.get("LANGFUSE_HOST", "(not configured)") or "(not configured)",
        ),
        (
            "HTTP Proxy",
            "enabled"
            if env.get("HTTP_PROXY_ENABLED", "").lower() == "true"
            else "disabled",
        ),
    ]
    max_label = max(len(r[0]) for r in rows)
    for label, value in rows:
        click.echo(f"  {label:<{max_label}}  {value}")
