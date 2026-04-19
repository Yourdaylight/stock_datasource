"""Environment health check command (``doctor``).

Runs connectivity and configuration checks for all external dependencies:
  - ClickHouse
  - Redis
  - Tushare Token
  - LLM / OpenAI API
  - HTTP Proxy (if enabled)

Each check is independent with its own timeout, so one failure won't block
others. Output is a neatly aligned status table with fix suggestions.
"""

from __future__ import annotations

import time

import click

# Status symbols
_PASS = click.style("✓ PASS", fg="green")
_WARN = click.style("⚠ WARN", fg="yellow")
_FAIL = click.style("✗ FAIL", fg="red")
_SKIP = click.style("- SKIP", fg="bright_black")


def _check_clickhouse() -> tuple[str, str, str]:
    """Check ClickHouse connectivity.

    Returns:
        (status_symbol, message, fix_hint)
    """
    try:
        from clickhouse_driver import Client

        from stock_datasource.config.settings import settings

        client = Client(
            host=settings.CLICKHOUSE_HOST,
            port=settings.CLICKHOUSE_PORT,
            user=settings.CLICKHOUSE_USER,
            password=settings.CLICKHOUSE_PASSWORD,
            database="default",
            connect_timeout=5,
            send_receive_timeout=5,
        )
        result = client.execute("SELECT version()")
        version = result[0][0] if result else "unknown"

        # Check if the target database exists
        dbs = [row[0] for row in client.execute("SHOW DATABASES")]
        if settings.CLICKHOUSE_DATABASE in dbs:
            return _PASS, f"v{version}, db '{settings.CLICKHOUSE_DATABASE}' exists", ""
        else:
            return (
                _WARN,
                f"v{version}, db '{settings.CLICKHOUSE_DATABASE}' NOT found",
                "Run: stock-ds init-db",
            )
    except Exception as e:
        return (
            _FAIL,
            str(e)[:80],
            "Check CLICKHOUSE_HOST/PORT in .env, ensure ClickHouse is running",
        )


def _check_redis() -> tuple[str, str, str]:
    """Check Redis connectivity."""
    try:
        import redis as redis_lib

        from stock_datasource.config.settings import settings

        r = redis_lib.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD or None,
            db=settings.REDIS_DB,
            socket_timeout=5,
            socket_connect_timeout=5,
        )
        info = r.info("server")
        version = info.get("redis_version", "?")
        return _PASS, f"v{version} at {settings.REDIS_HOST}:{settings.REDIS_PORT}", ""
    except Exception as e:
        return (
            _FAIL,
            str(e)[:80],
            "Check REDIS_HOST/PORT/PASSWORD in .env, ensure Redis is running",
        )


def _check_tushare() -> tuple[str, str, str]:
    """Check Tushare token validity."""
    try:
        from stock_datasource.config.settings import settings

        token = settings.TUSHARE_TOKEN
        if not token:
            return (
                _FAIL,
                "Token not set",
                "Set TUSHARE_TOKEN in .env or run: stock-ds setup",
            )

        import tushare as ts

        pro = ts.pro_api(token)
        df = pro.trade_cal(exchange="SSE", start_date="20250101", end_date="20250105")
        if df is not None and len(df) > 0:
            return _PASS, f"Token valid ({len(df)} calendar rows)", ""
        return (
            _WARN,
            "API returned empty data",
            "Token may have insufficient permissions",
        )
    except Exception as e:
        return _FAIL, str(e)[:80], "Check TUSHARE_TOKEN in .env"


def _check_llm() -> tuple[str, str, str]:
    """Check LLM / OpenAI API connectivity."""
    try:
        from stock_datasource.config.settings import settings

        api_key = settings.OPENAI_API_KEY
        if not api_key:
            return (
                _WARN,
                "API key not set",
                "Set OPENAI_API_KEY in .env (optional for data-only usage)",
            )

        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            base_url=settings.OPENAI_BASE_URL,
            timeout=15,
        )
        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
        )
        model_used = resp.model or settings.OPENAI_MODEL
        return _PASS, f"Model '{model_used}' responded", ""
    except Exception as e:
        return (
            _FAIL,
            str(e)[:80],
            "Check OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL in .env",
        )


def _check_proxy() -> tuple[str, str, str]:
    """Check HTTP proxy connectivity (if enabled)."""
    try:
        from stock_datasource.config.settings import settings

        if not settings.HTTP_PROXY_ENABLED:
            return _SKIP, "Proxy is disabled", ""

        proxy_url = settings.http_proxy_url
        if not proxy_url:
            return (
                _WARN,
                "Proxy enabled but URL is incomplete",
                "Check HTTP_PROXY_HOST/PORT in .env",
            )

        import requests

        proxies = {"http": proxy_url, "https": proxy_url}
        resp = requests.get("https://httpbin.org/ip", proxies=proxies, timeout=10)
        if resp.status_code == 200:
            return (
                _PASS,
                f"Proxy OK via {settings.HTTP_PROXY_HOST}:{settings.HTTP_PROXY_PORT}",
                "",
            )
        return _WARN, f"HTTP {resp.status_code}", "Proxy may be misconfigured"
    except Exception as e:
        return _FAIL, str(e)[:60], "Check proxy settings in .env or runtime config"


def _check_env_file() -> tuple[str, str, str]:
    """Check if .env file exists and has required keys."""
    from pathlib import Path

    env_file = Path(__file__).resolve().parents[3] / ".env"
    if not env_file.exists():
        return _FAIL, ".env file not found", "Run: stock-ds setup"

    content = env_file.read_text(encoding="utf-8")
    missing = []
    for key in ["TUSHARE_TOKEN", "CLICKHOUSE_HOST", "REDIS_HOST"]:
        if key not in content:
            missing.append(key)

    if missing:
        return _WARN, f"Missing keys: {', '.join(missing)}", "Run: stock-ds setup"
    return _PASS, f".env file OK ({len(content.splitlines())} lines)", ""


# ---------------------------------------------------------------------------
# Main command
# ---------------------------------------------------------------------------


@click.command("doctor")
@click.option(
    "--json-output",
    "json_out",
    is_flag=True,
    default=False,
    help="Output results as JSON",
)
def doctor(json_out: bool):
    """Check environment health and service connectivity.

    Runs connectivity tests for ClickHouse, Redis, Tushare, LLM API,
    and HTTP proxy. Each test runs independently with a 5-15s timeout.

    Example:

      \b
      stock-ds doctor
      stock-ds doctor --json-output
    """
    click.echo("")
    click.secho(
        "╔══════════════════════════════════════════════════╗", fg="bright_blue"
    )
    click.secho("║     Stock Datasource — Environment Doctor       ║", fg="bright_blue")
    click.secho(
        "╚══════════════════════════════════════════════════╝", fg="bright_blue"
    )
    click.echo("")

    checks = [
        (".env File", _check_env_file),
        ("ClickHouse", _check_clickhouse),
        ("Redis", _check_redis),
        ("Tushare API", _check_tushare),
        ("LLM / OpenAI", _check_llm),
        ("HTTP Proxy", _check_proxy),
    ]

    results: list[dict] = []
    pass_count = 0
    warn_count = 0
    fail_count = 0

    for name, check_fn in checks:
        click.echo(f"  Checking {name}...", nl=False)
        start = time.time()

        try:
            status, message, hint = check_fn()
        except Exception as e:
            status, message, hint = _FAIL, f"Unexpected error: {e}", ""

        elapsed = time.time() - start
        # Clear the "Checking..." line and print result
        click.echo(f"\r  {'':<40}\r", nl=False)

        # Count stats (compare on plain text)
        if "PASS" in status:
            pass_count += 1
        elif "WARN" in status:
            warn_count += 1
        elif "FAIL" in status:
            fail_count += 1

        click.echo(f"  {status}  {name:<16} {message}  ({elapsed:.1f}s)")
        if hint:
            click.echo(f"         {'':16} └─ {hint}")

        results.append(
            {
                "name": name,
                "status": "pass"
                if "PASS" in status
                else (
                    "warn"
                    if "WARN" in status
                    else ("skip" if "SKIP" in status else "fail")
                ),
                "message": message,
                "hint": hint,
                "elapsed_seconds": round(elapsed, 2),
            }
        )

    # Summary
    click.echo("")
    click.secho("━" * 50, fg="bright_blue")
    summary_parts = []
    if pass_count:
        summary_parts.append(click.style(f"{pass_count} passed", fg="green"))
    if warn_count:
        summary_parts.append(click.style(f"{warn_count} warnings", fg="yellow"))
    if fail_count:
        summary_parts.append(click.style(f"{fail_count} failed", fg="red"))
    click.echo(f"  Results: {', '.join(summary_parts)}")

    if fail_count == 0 and warn_count == 0:
        click.secho(
            "  ✓ All checks passed! Your environment is ready.", fg="green", bold=True
        )
    elif fail_count == 0:
        click.secho(
            "  ⚠ Some warnings — services may work with reduced functionality.",
            fg="yellow",
        )
    else:
        click.secho(
            "  ✗ Some checks failed — please fix them before starting services.",
            fg="red",
        )
    click.echo("")

    if json_out:
        import json

        click.echo(json.dumps(results, indent=2, ensure_ascii=False))
