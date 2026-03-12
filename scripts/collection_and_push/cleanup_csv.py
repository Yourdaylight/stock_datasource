#!/usr/bin/env python3
"""Standalone CSV cleanup script.

特点：
1) 不依赖 Redis / ClickHouse / FastAPI
2) 清理指定目录下超过 N 天（默认 2 天）的 CSV 文件
3) 支持两种 CSV 命名模式：
   - append 模式: {market}.csv — 按文件修改时间判断
   - 时间戳模式: {market}_{YYYYMMDD_HHMMSS}.csv — 按文件名中的时间戳判断
4) 支持循环模式（--loop），定期自动清理
5) 支持 dry-run 预览，不实际删除
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger("cleanup_csv")

# 文件名中的时间戳正则：{market}_{YYYYMMDD}_{HHMMSS}.csv
TIMESTAMP_PATTERN = re.compile(r"^(.+)_(\d{8})_(\d{6})\.csv$")


def parse_filename_timestamp(filename: str) -> datetime | None:
    """从文件名中提取时间戳，如 a_stock_20260310_093000.csv -> datetime。"""
    m = TIMESTAMP_PATTERN.match(filename)
    if not m:
        return None
    try:
        return datetime.strptime(f"{m.group(2)}_{m.group(3)}", "%Y%m%d_%H%M%S")
    except ValueError:
        return None


def get_file_age(filepath: Path) -> datetime:
    """获取文件的修改时间。"""
    return datetime.fromtimestamp(filepath.stat().st_mtime)


def scan_expired_files(
    csv_dir: Path,
    max_age_days: float,
    cutoff: datetime | None = None,
) -> List[Tuple[Path, str, datetime]]:
    """扫描过期的 CSV 文件。

    Returns:
        List of (file_path, reason, file_time)
    """
    if cutoff is None:
        cutoff = datetime.now() - timedelta(days=max_age_days)

    expired: List[Tuple[Path, str, datetime]] = []

    if not csv_dir.exists():
        logger.warning("CSV 目录不存在: %s", csv_dir)
        return expired

    for f in sorted(csv_dir.iterdir()):
        if not f.is_file() or not f.name.endswith(".csv"):
            continue

        # 1) 尝试从文件名解析时间戳
        ts = parse_filename_timestamp(f.name)
        if ts is not None:
            if ts < cutoff:
                expired.append((f, "filename_timestamp", ts))
            continue

        # 2) 无时间戳的文件（append 模式），按修改时间判断
        mtime = get_file_age(f)
        if mtime < cutoff:
            expired.append((f, "mtime", mtime))

    return expired


def cleanup_checkpoint(csv_dir: Path, max_age_days: float) -> int:
    """清理 push_checkpoint.json 中已删除文件的记录。

    Returns:
        清理的记录数
    """
    import json

    checkpoint_file = csv_dir / "push_checkpoint.json"
    if not checkpoint_file.exists():
        return 0

    try:
        data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0

    if not isinstance(data, dict):
        return 0

    original_keys = set(data.keys())
    # 移除指向已不存在文件的记录
    cleaned = {k: v for k, v in data.items() if (csv_dir / k).exists()}
    removed = len(original_keys) - len(cleaned)

    if removed > 0:
        checkpoint_file.write_text(
            json.dumps(cleaned, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("checkpoint 清理了 %d 条过期记录", removed)

    return removed


def do_cleanup(
    csv_dir: Path,
    max_age_days: float,
    dry_run: bool = False,
    clean_checkpoint: bool = True,
) -> Dict[str, int]:
    """执行一轮清理。

    Returns:
        {"deleted": N, "skipped": M, "checkpoint_cleaned": C}
    """
    cutoff = datetime.now() - timedelta(days=max_age_days)
    expired = scan_expired_files(csv_dir, max_age_days, cutoff)

    stats: Dict[str, int] = {"deleted": 0, "skipped": 0, "checkpoint_cleaned": 0}

    if not expired:
        logger.info("没有过期的 CSV 文件（cutoff=%s）", cutoff.strftime("%Y-%m-%d %H:%M:%S"))
        return stats

    for filepath, reason, file_time in expired:
        size_mb = filepath.stat().st_size / (1024 * 1024)
        age_hours = (datetime.now() - file_time).total_seconds() / 3600

        if dry_run:
            logger.info(
                "[DRY-RUN] 将删除: %s (%.2fMB, %.1f小时前, 判断依据=%s)",
                filepath.name, size_mb, age_hours, reason,
            )
            stats["skipped"] += 1
        else:
            try:
                filepath.unlink()
                logger.info(
                    "已删除: %s (%.2fMB, %.1f小时前, 判断依据=%s)",
                    filepath.name, size_mb, age_hours, reason,
                )
                stats["deleted"] += 1
            except OSError as e:
                logger.error("删除失败: %s — %s", filepath.name, e)
                stats["skipped"] += 1

    # 清理 push_checkpoint.json 中的过期记录
    if clean_checkpoint and not dry_run:
        stats["checkpoint_cleaned"] = cleanup_checkpoint(csv_dir, max_age_days)

    return stats


def build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="清理过期的 CSV 文件（默认清理 2 天以外的）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 预览哪些文件会被清理（不实际删除）
  python scripts/cleanup_csv.py --csv-dir data/tushare_csv --dry-run

  # 清理 2 天以外的 CSV
  python scripts/cleanup_csv.py --csv-dir data/tushare_csv

  # 清理 1 天以外的 CSV
  python scripts/cleanup_csv.py --csv-dir data/tushare_csv --max-age-days 1

  # 循环模式，每 6 小时清理一次
  python scripts/cleanup_csv.py --csv-dir data/tushare_csv --loop --interval 21600

  # 清理 12 小时以外的（支持小数）
  python scripts/cleanup_csv.py --csv-dir data/tushare_csv --max-age-days 0.5
        """,
    )
    parser.add_argument(
        "--csv-dir",
        default=os.getenv("CSV_DIR", "data/tushare_csv"),
        help="CSV 文件目录（默认 data/tushare_csv）",
    )
    parser.add_argument(
        "--max-age-days",
        type=float,
        default=float(os.getenv("CSV_MAX_AGE_DAYS", "2")),
        help="保留天数，超过此天数的文件将被清理（默认 2，支持小数如 0.5=12小时）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="预览模式，只打印将要删除的文件，不实际删除",
    )
    parser.add_argument(
        "--no-clean-checkpoint",
        action="store_true",
        default=False,
        help="不清理 push_checkpoint.json 中的过期记录",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        default=False,
        help="循环模式，定期执行清理",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=float(os.getenv("CLEANUP_INTERVAL", "3600")),
        help="循环模式下的清理间隔（秒），默认 3600（1 小时）",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别（默认 INFO）",
    )
    return parser.parse_args()


def main() -> int:
    args = build_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    csv_dir = Path(args.csv_dir)
    logger.info(
        "CSV 清理器启动 — 目录=%s, 保留天数=%.1f, dry_run=%s, loop=%s",
        csv_dir, args.max_age_days, args.dry_run, args.loop,
    )

    round_no = 0
    while True:
        round_no += 1
        t0 = time.monotonic()

        logger.info("===== 第 %d 轮清理 =====", round_no)
        stats = do_cleanup(
            csv_dir=csv_dir,
            max_age_days=args.max_age_days,
            dry_run=args.dry_run,
            clean_checkpoint=not args.no_clean_checkpoint,
        )
        logger.info(
            "第 %d 轮完成: 删除=%d, 跳过=%d, checkpoint清理=%d",
            round_no, stats["deleted"], stats["skipped"], stats["checkpoint_cleaned"],
        )

        if not args.loop:
            break

        elapsed = time.monotonic() - t0
        wait_s = max(0.0, args.interval - elapsed)
        if wait_s > 0:
            logger.info("下次清理在 %.0f 秒后", wait_s)
            time.sleep(wait_s)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
