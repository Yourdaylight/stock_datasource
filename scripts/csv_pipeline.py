#!/usr/bin/env python3
"""CSV Pipeline 控制脚本 — 统一管理 采集 / 推送 / 清理 三个子流程。

特点：
1) 一键启动完整流水线：采集 → 推送 → 定期清理
2) 也可单独启动任意子流程组合
3) 统一的信号处理（Ctrl+C 优雅关闭所有子进程）
4) 子进程崩溃自动重启
5) 支持 .env 文件加载环境变量

用法示例：
  # 启动完整流水线（采集 + 推送 + 清理）
  python scripts/csv_pipeline.py --token $TUSHARE_TOKEN --push-url https://xxx/api/push

  # 只启动采集和清理（不推送）
  python scripts/csv_pipeline.py --token $TUSHARE_TOKEN --disable-push

  # 只启动推送（CSV 已经由别的方式生成）
  python scripts/csv_pipeline.py --disable-collect --disable-cleanup --push-url https://xxx/api/push

  # 使用 .env 文件
  python scripts/csv_pipeline.py --env-file .env
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("csv_pipeline")

# ---------------------------------------------------------------------------
# 脚本路径解析
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
COLLECT_SCRIPT = SCRIPT_DIR / "collect_tushare_to_csv.py"
PUSH_SCRIPT = SCRIPT_DIR / "push_csv_to_cloud.py"
CLEANUP_SCRIPT = SCRIPT_DIR / "cleanup_csv.py"


# ---------------------------------------------------------------------------
# 子进程管理
# ---------------------------------------------------------------------------

@dataclass
class WorkerSpec:
    """子进程规格定义。"""
    name: str
    script: Path
    args: List[str]
    enabled: bool = True
    restart_delay: float = 3.0
    max_restarts: int = 10
    restart_window: float = 300.0  # 在此窗口内的重启计数


@dataclass
class WorkerState:
    """子进程运行状态。"""
    process: Optional[subprocess.Popen] = None
    restart_count: int = 0
    last_restart_time: float = 0.0
    start_time: float = 0.0
    stop_requested: bool = False


class PipelineManager:
    """管理多个子进程的生命周期。"""

    def __init__(self, specs: List[WorkerSpec], log_level: str = "INFO"):
        self._specs = {s.name: s for s in specs if s.enabled}
        self._states: Dict[str, WorkerState] = {
            name: WorkerState() for name in self._specs
        }
        self._lock = threading.Lock()
        self._shutdown = threading.Event()
        self._log_level = log_level

    def start_all(self) -> None:
        """启动所有已启用的子进程。"""
        if not self._specs:
            logger.error("没有启用任何子流程，请检查参数")
            return

        logger.info("=" * 60)
        logger.info("CSV Pipeline 启动")
        logger.info("启用的子流程: %s", ", ".join(self._specs.keys()))
        logger.info("=" * 60)

        for name in self._specs:
            self._start_worker(name)

    def _start_worker(self, name: str) -> bool:
        """启动单个子进程。"""
        spec = self._specs[name]
        state = self._states[name]

        if state.stop_requested:
            return False

        cmd = [sys.executable, str(spec.script)] + spec.args
        logger.info("[%s] 启动: %s", name, " ".join(cmd))

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                universal_newlines=True,
            )
            state.process = process
            state.start_time = time.monotonic()

            # 启动日志转发线程
            log_thread = threading.Thread(
                target=self._forward_logs,
                args=(name, process),
                daemon=True,
            )
            log_thread.start()

            logger.info("[%s] 已启动 (PID=%d)", name, process.pid)
            return True

        except Exception as e:
            logger.error("[%s] 启动失败: %s", name, e)
            return False

    def _forward_logs(self, name: str, process: subprocess.Popen) -> None:
        """转发子进程的日志到主进程。"""
        prefix = f"[{name}]"
        try:
            if process.stdout:
                for line in process.stdout:
                    line = line.rstrip("\n\r")
                    if line:
                        logger.info("%s %s", prefix, line)
        except (ValueError, OSError):
            pass  # 进程已关闭

    def monitor(self) -> None:
        """监控所有子进程，崩溃时自动重启。"""
        while not self._shutdown.is_set():
            with self._lock:
                for name, state in self._states.items():
                    if state.stop_requested or state.process is None:
                        continue

                    ret = state.process.poll()
                    if ret is not None:
                        # 进程已退出
                        uptime = time.monotonic() - state.start_time
                        logger.warning(
                            "[%s] 进程退出 (code=%s, 运行了%.1f秒)",
                            name, ret, uptime,
                        )

                        if state.stop_requested:
                            continue

                        # 检查是否超过重启限制
                        spec = self._specs[name]
                        now = time.monotonic()

                        # 重启窗口外重置计数
                        if now - state.last_restart_time > spec.restart_window:
                            state.restart_count = 0

                        if state.restart_count >= spec.max_restarts:
                            logger.error(
                                "[%s] 重启次数已达上限 (%d), 停止重启",
                                name, spec.max_restarts,
                            )
                            continue

                        state.restart_count += 1
                        state.last_restart_time = now

                        logger.info(
                            "[%s] 将在 %.1f 秒后重启 (第 %d/%d 次)",
                            name, spec.restart_delay,
                            state.restart_count, spec.max_restarts,
                        )
                        # 在锁外执行 sleep + 重启
                        threading.Thread(
                            target=self._delayed_restart,
                            args=(name, spec.restart_delay),
                            daemon=True,
                        ).start()

            self._shutdown.wait(timeout=2.0)

    def _delayed_restart(self, name: str, delay: float) -> None:
        """延迟重启子进程。"""
        self._shutdown.wait(timeout=delay)
        if not self._shutdown.is_set():
            with self._lock:
                self._start_worker(name)

    def shutdown(self) -> None:
        """优雅关闭所有子进程。"""
        logger.info("正在关闭所有子流程...")
        self._shutdown.set()

        with self._lock:
            for name, state in self._states.items():
                state.stop_requested = True
                if state.process and state.process.poll() is None:
                    logger.info("[%s] 发送终止信号 (PID=%d)", name, state.process.pid)
                    try:
                        state.process.terminate()
                    except OSError:
                        pass

        # 等待所有进程退出（最多 10 秒）
        deadline = time.monotonic() + 10.0
        for name, state in self._states.items():
            if state.process and state.process.poll() is None:
                remaining = max(0.1, deadline - time.monotonic())
                try:
                    state.process.wait(timeout=remaining)
                    logger.info("[%s] 已停止", name)
                except subprocess.TimeoutExpired:
                    logger.warning("[%s] 超时未退出，强制杀死", name)
                    try:
                        state.process.kill()
                        state.process.wait(timeout=2)
                    except (OSError, subprocess.TimeoutExpired):
                        pass

        logger.info("所有子流程已关闭")

    def status(self) -> Dict[str, str]:
        """获取所有子进程的状态。"""
        result: Dict[str, str] = {}
        for name, state in self._states.items():
            if state.process is None:
                result[name] = "not_started"
            elif state.process.poll() is None:
                uptime = time.monotonic() - state.start_time
                result[name] = f"running (PID={state.process.pid}, uptime={uptime:.0f}s)"
            else:
                result[name] = f"exited (code={state.process.returncode})"
        return result


# ---------------------------------------------------------------------------
# .env 文件加载
# ---------------------------------------------------------------------------

def load_env_file(filepath: str) -> None:
    """加载 .env 文件中的环境变量（不覆盖已有的）。"""
    env_path = Path(filepath)
    if not env_path.exists():
        logger.warning(".env 文件不存在: %s", filepath)
        return

    loaded = 0
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue

        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("\"'")

        if key and key not in os.environ:
            os.environ[key] = value
            loaded += 1

    logger.info("从 %s 加载了 %d 个环境变量", filepath, loaded)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CSV Pipeline 控制脚本 — 统一管理采集/推送/清理子流程",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 完整流水线（需要 token 和 push-url）
  python scripts/csv_pipeline.py \\
    --token $TUSHARE_TOKEN \\
    --push-url https://your-cloud/api/push \\
    --push-token your_token

  # 只采集 + 清理（不推送）
  python scripts/csv_pipeline.py --token $TUSHARE_TOKEN --disable-push

  # 只推送（CSV 已存在）
  python scripts/csv_pipeline.py --disable-collect --disable-cleanup \\
    --push-url https://your-cloud/api/push

  # 使用 .env 文件配置所有参数
  python scripts/csv_pipeline.py --env-file .env

  # 自定义各子流程参数
  python scripts/csv_pipeline.py \\
    --token $TUSHARE_TOKEN \\
    --push-url https://your-cloud/api/push \\
    --collect-interval 2.0 \\
    --push-interval 5.0 \\
    --cleanup-interval 7200 \\
    --max-age-days 1
        """,
    )

    # 全局配置
    g = parser.add_argument_group("全局配置")
    g.add_argument("--env-file", default=None, help="加载 .env 文件")
    g.add_argument("--csv-dir", default=os.getenv("CSV_DIR", "data/tushare_csv"),
                    help="CSV 数据目录（三个子流程共享）")
    g.add_argument("--markets", default="a_stock,etf,index,hk",
                    help="市场列表（逗号分隔）")
    g.add_argument("--log-level", default="INFO",
                    choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                    help="日志级别")
    g.add_argument("--max-restarts", type=int, default=10,
                    help="子进程最大重启次数（5 分钟窗口内）")
    g.add_argument("--restart-delay", type=float, default=3.0,
                    help="子进程重启延迟（秒）")

    # 子流程开关
    sw = parser.add_argument_group("子流程开关")
    sw.add_argument("--disable-collect", action="store_true", help="禁用采集子流程")
    sw.add_argument("--disable-push", action="store_true", help="禁用推送子流程")
    sw.add_argument("--disable-cleanup", action="store_true", help="禁用清理子流程")

    # 采集参数
    c = parser.add_argument_group("采集参数 (collect_tushare_to_csv.py)")
    c.add_argument("--token", default=os.getenv("TUSHARE_TOKEN", ""),
                    help="TuShare token")
    c.add_argument("--api-url", default=os.getenv("TUSHARE_API_URL", ""),
                    help="TuShare API URL")
    c.add_argument("--proxy-url", default=os.getenv("HTTP_PROXY", ""),
                    help="HTTP 代理 URL")
    c.add_argument("--collect-interval", type=float, default=1.5,
                    help="采集轮次间隔（秒）")
    c.add_argument("--collect-append", action="store_true", default=True,
                    help="追加模式写入 CSV（默认开启）")
    c.add_argument("--no-collect-append", action="store_true",
                    help="关闭追加模式，每轮生成带时间戳的独立文件")
    c.add_argument("--trading-only", action=argparse.BooleanOptionalAction, default=True,
                    help="仅在交易时段采集")
    c.add_argument("--ignore-trading-window", action="store_true",
                    help="忽略交易时段限制")

    # 推送参数
    p = parser.add_argument_group("推送参数 (push_csv_to_cloud.py)")
    p.add_argument("--push-url", default=os.getenv("RT_KLINE_CLOUD_PUSH_URL", ""),
                    help="云端推送 URL")
    p.add_argument("--push-token", default=os.getenv("RT_KLINE_CLOUD_PUSH_TOKEN", ""),
                    help="推送鉴权 Token")
    p.add_argument("--push-interval", type=float, default=3.0,
                    help="推送轮次间隔（秒）")
    p.add_argument("--batch-size", type=int, default=1000,
                    help="每批推送条数")

    # 清理参数
    cl = parser.add_argument_group("清理参数 (cleanup_csv.py)")
    cl.add_argument("--max-age-days", type=float, default=2.0,
                     help="CSV 保留天数，超过则清理")
    cl.add_argument("--cleanup-interval", type=float, default=3600.0,
                     help="清理轮次间隔（秒），默认 1 小时")

    return parser.parse_args()


def build_collect_args(args: argparse.Namespace) -> List[str]:
    """构建采集脚本的命令行参数。"""
    cmd: List[str] = [
        "--token", args.token,
        "--output-dir", args.csv_dir,
        "--markets", args.markets,
        "--interval", str(args.collect_interval),
        "--loop",
        "--log-level", args.log_level,
    ]
    if args.no_collect_append:
        pass  # 不加 --append
    elif args.collect_append:
        cmd.append("--append")

    if args.api_url:
        cmd.extend(["--api-url", args.api_url])
    if args.proxy_url:
        cmd.extend(["--proxy-url", args.proxy_url])
    if args.ignore_trading_window:
        cmd.append("--ignore-trading-window")
    elif not args.trading_only:
        cmd.append("--no-trading-only")

    return cmd


def build_push_args(args: argparse.Namespace) -> List[str]:
    """构建推送脚本的命令行参数。"""
    cmd: List[str] = [
        "--csv-dir", args.csv_dir,
        "--markets", args.markets,
        "--push-url", args.push_url,
        "--interval", str(args.push_interval),
        "--batch-size", str(args.batch_size),
        "--loop",
        "--log-level", args.log_level,
    ]
    if args.push_token:
        cmd.extend(["--push-token", args.push_token])
    return cmd


def build_cleanup_args(args: argparse.Namespace) -> List[str]:
    """构建清理脚本的命令行参数。"""
    return [
        "--csv-dir", args.csv_dir,
        "--max-age-days", str(args.max_age_days),
        "--interval", str(args.cleanup_interval),
        "--loop",
        "--log-level", args.log_level,
    ]


def validate_args(args: argparse.Namespace) -> List[str]:
    """校验参数，返回错误列表。"""
    errors: List[str] = []

    if not args.disable_collect and not args.token:
        errors.append("采集已启用但未提供 --token（或设置 TUSHARE_TOKEN 环境变量）")

    if not args.disable_push and not args.push_url:
        errors.append("推送已启用但未提供 --push-url（或设置 RT_KLINE_CLOUD_PUSH_URL 环境变量）")

    if not args.disable_collect and not COLLECT_SCRIPT.exists():
        errors.append(f"采集脚本不存在: {COLLECT_SCRIPT}")

    if not args.disable_push and not PUSH_SCRIPT.exists():
        errors.append(f"推送脚本不存在: {PUSH_SCRIPT}")

    if not args.disable_cleanup and not CLEANUP_SCRIPT.exists():
        errors.append(f"清理脚本不存在: {CLEANUP_SCRIPT}")

    if args.disable_collect and args.disable_push and args.disable_cleanup:
        errors.append("所有子流程都已禁用，至少需要启用一个")

    return errors


def main() -> int:
    args = build_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 加载 .env 文件
    if args.env_file:
        load_env_file(args.env_file)
        # 重新解析参数（.env 中的变量可能影响默认值）
        args = build_args()

    # 校验参数
    errors = validate_args(args)
    if errors:
        for e in errors:
            logger.error("参数错误: %s", e)
        return 1

    # 确保 CSV 目录存在
    Path(args.csv_dir).mkdir(parents=True, exist_ok=True)

    # 构建子进程规格
    specs: List[WorkerSpec] = [
        WorkerSpec(
            name="collect",
            script=COLLECT_SCRIPT,
            args=build_collect_args(args),
            enabled=not args.disable_collect,
            restart_delay=args.restart_delay,
            max_restarts=args.max_restarts,
        ),
        WorkerSpec(
            name="push",
            script=PUSH_SCRIPT,
            args=build_push_args(args),
            enabled=not args.disable_push,
            restart_delay=args.restart_delay,
            max_restarts=args.max_restarts,
        ),
        WorkerSpec(
            name="cleanup",
            script=CLEANUP_SCRIPT,
            args=build_cleanup_args(args),
            enabled=not args.disable_cleanup,
            restart_delay=args.restart_delay * 2,  # 清理重启慢一些
            max_restarts=args.max_restarts,
        ),
    ]

    manager = PipelineManager(specs, log_level=args.log_level)

    # 信号处理
    def signal_handler(sig: int, frame) -> None:
        sig_name = signal.Signals(sig).name
        logger.info("收到信号 %s，准备关闭...", sig_name)
        manager.shutdown()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 启动所有子进程
    manager.start_all()

    # 主线程监控
    try:
        manager.monitor()
    except KeyboardInterrupt:
        pass
    finally:
        manager.shutdown()

    logger.info("CSV Pipeline 已退出")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
