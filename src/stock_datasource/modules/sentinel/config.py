"""Sentinel system configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class SentinelConfig:
    """Configuration for the sentinel system."""

    # Redis connection
    redis_url: str = field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )
    redis_stream_maxlen: int = 10000  # Max messages in Redis Stream

    # Channel prefixes
    sentinel_channel_prefix: str = "sentinel"
    analyst_channel_prefix: str = "analyst"

    # Cooldown (seconds) - same alert won't fire within this window
    default_cooldown_seconds: int = 3600  # 1 hour

    # Analyst thresholds
    min_conviction_to_escalate: float = 0.3
    analyst_buffer_max_size: int = 100
    analyst_analysis_window_seconds: int = 600  # 10 min

    # Director
    use_llm: bool = True
    llm_temperature: float = 0.3
    llm_max_tokens: int = 4000

    # Scheduler
    daily_scan_time: str = "18:45"
    intraday_interval_minutes: int = 30
    intraday_start_hour: int = 9
    intraday_end_hour: int = 15

    # Persistence
    alert_ttl_days: int = 90
    decision_ttl_days: int = 365


def get_sentinel_config() -> SentinelConfig:
    """Get sentinel config from environment."""
    return SentinelConfig()
