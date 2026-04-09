"""Backend container entrypoint that runs API and MCP processes together."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def _build_commands() -> list[list[str]]:
    python_bin = sys.executable
    api_port = os.getenv("BACKEND_PORT", "6666")
    debug = os.getenv("DEBUG", "").lower() in ("1", "true", "yes")

    api_cmd = [
        python_bin,
        "-u",
        "-m",
        "uvicorn",
        "stock_datasource.services.http_server:app",
        "--host",
        "0.0.0.0",
        "--port",
        api_port,
    ]
    if debug:
        api_cmd.append("--reload")

    return [
        api_cmd,
        [
            python_bin,
            "-u",
            "-m",
            "stock_datasource.services.mcp_server",
        ],
    ]


def _terminate(processes: list[subprocess.Popen[bytes]], sig: int) -> None:
    for process in processes:
        if process.poll() is None:
            try:
                process.send_signal(sig)
            except ProcessLookupError:
                pass


def main() -> int:
    processes: list[subprocess.Popen[bytes]] = []
    shutting_down = False

    def _handle_signal(signum: int, _frame) -> None:
        nonlocal shutting_down
        if shutting_down:
            return
        shutting_down = True
        _terminate(processes, signum)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    for command in _build_commands():
        processes.append(subprocess.Popen(command, cwd=str(Path(__file__).resolve().parents[3])))

    exit_code = 0
    try:
        while True:
            for process in processes:
                code = process.poll()
                if code is None:
                    continue
                exit_code = code
                shutting_down = True
                _terminate([p for p in processes if p is not process], signal.SIGTERM)
                time.sleep(2)
                _terminate([p for p in processes if p is not process], signal.SIGKILL)
                return exit_code
            time.sleep(1)
    finally:
        _terminate(processes, signal.SIGTERM)
        deadline = time.time() + 10
        for process in processes:
            while process.poll() is None and time.time() < deadline:
                time.sleep(0.2)
            if process.poll() is None:
                _terminate([process], signal.SIGKILL)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())