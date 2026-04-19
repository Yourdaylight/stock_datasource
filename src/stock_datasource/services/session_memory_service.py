"""Session & Memory Service: Unified memory pipeline.

This is the **single source of truth** for all in-process session state:
1. Hot State: session lifecycle, conversation history (TTL + LRU eviction)
2. Session Cache: per-session tool-result caching with TTL
3. Long-term Memory: user-scoped preferences and watchlists

Other components (``SessionMemory`` in base_agent, ``ChatService``,
``MemoryAgent``) delegate to this service rather than maintaining their
own state – eliminating the duplicate-storage and cache-inconsistency
problems that existed before.

Observability counters (task 5.2) are exposed as properties so that
a ``/metrics`` endpoint or Langfuse trace can collect them cheaply.
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class SubAgentEnvelope:
    """Result envelope for SubAgent calls (task 4.3).

    Defines the contract between the runtime/supervisor and any
    sub-agent invocation – whether it's a business agent, a workflow
    adapter, or an arena adapter.
    """

    agent_name: str
    session_id: str
    user_id: str = "default"
    # Input
    query: str = ""
    scoped_history: list[dict[str, str]] = field(default_factory=list)
    shared_state_keys: list[str] = field(default_factory=list)
    # Output (filled by the sub-agent)
    response: str = ""
    success: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class MemoryEntry:
    """A single memory item."""

    key: str
    value: Any
    category: str = "general"
    user_id: str = "default"
    updated_at: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# SessionMemoryService
# ---------------------------------------------------------------------------


class SessionMemoryService:
    """Unified session and memory management."""

    MAX_HISTORY_PER_SESSION: int = 30
    MAX_HISTORY_CHARS: int = 15000
    HISTORY_TTL_SECONDS: int = 3600
    CACHE_TTL_SECONDS: int = 300
    MAX_SESSIONS: int = 1000

    def __init__(self) -> None:
        self._history: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._cache: dict[str, dict[str, Any]] = defaultdict(dict)
        self._session_meta: dict[str, dict[str, Any]] = {}
        self._user_preferences: dict[str, dict[str, MemoryEntry]] = defaultdict(dict)
        self._user_watchlists: dict[str, dict[str, list[str]]] = defaultdict(
            lambda: defaultdict(list)
        )
        # Observability counters (task 5.2)
        self._stats: dict[str, int] = defaultdict(int)

    # -- Session lifecycle --

    def make_session_id(
        self, agent_name: str, user_id: str = "default", context_key: str = ""
    ) -> str:
        raw = f"{agent_name}:{user_id}:{context_key}"
        return hashlib.md5(raw.encode()).hexdigest()[:16]

    def touch_session(self, session_id: str, user_id: str = "default") -> None:
        now = time.time()
        if session_id not in self._session_meta:
            self._session_meta[session_id] = {
                "created": now,
                "last_access": now,
                "user_id": user_id,
            }
            self._evict_if_needed()
        else:
            self._session_meta[session_id]["last_access"] = now

    def clear_session(self, session_id: str) -> None:
        self._history.pop(session_id, None)
        self._cache.pop(session_id, None)
        self._session_meta.pop(session_id, None)

    def _evict_if_needed(self) -> None:
        if len(self._session_meta) <= self.MAX_SESSIONS:
            return
        items = sorted(self._session_meta.items(), key=lambda x: x[1]["last_access"])
        to_evict = max(1, len(items) // 10)
        for sid, _ in items[:to_evict]:
            self.clear_session(sid)
        self._stats["sessions_evicted"] += to_evict
        logger.info("Evicted %d oldest sessions", to_evict)

    # -- Conversation history --

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        user_id: str = "default",
        max_messages: int = 0,
    ) -> None:
        max_msg = max_messages or self.MAX_HISTORY_PER_SESSION
        self.touch_session(session_id, user_id)
        self._history[session_id].append(
            {"role": role, "content": content, "timestamp": time.time()}
        )
        if len(self._history[session_id]) > max_msg:
            self._history[session_id] = self._history[session_id][-max_msg:]

    def get_history(
        self, session_id: str, ttl_seconds: int = 0, max_chars: int = 0
    ) -> list[dict[str, str]]:
        ttl = ttl_seconds or self.HISTORY_TTL_SECONDS
        max_c = max_chars or self.MAX_HISTORY_CHARS
        now = time.time()
        raw = self._history.get(session_id, [])
        valid = [
            {"role": h["role"], "content": h["content"]}
            for h in raw
            if now - h["timestamp"] < ttl
        ]
        total = sum(len(h["content"]) for h in valid)
        if total > max_c and len(valid) > 4:
            valid = self._summarize(valid)
        return valid

    def get_scoped_history(
        self, session_id: str, max_messages: int = 5
    ) -> list[dict[str, str]]:
        """Return recent N messages – lightweight context for sub-agents (task 3.2)."""
        raw = self._history.get(session_id, [])
        recent = raw[-max_messages:] if len(raw) > max_messages else raw
        return [{"role": h["role"], "content": h["content"]} for h in recent]

    def _summarize(self, history: list[dict[str, str]]) -> list[dict[str, str]]:
        if len(history) <= 4:
            return history
        first, last = history[:2], history[-2:]
        middle = history[2:-2]
        parts = []
        for m in middle:
            c = m["content"][:150] + "..." if len(m["content"]) > 150 else m["content"]
            parts.append(f"[{m['role']}]: {c}")
        summary = {
            "role": "system",
            "content": f"[对话历史摘要 - {len(middle)}条消息]\n" + "\n".join(parts),
        }
        return first + [summary] + last

    # -- Session cache (TTL-bounded) --

    def set_cache(self, session_id: str, key: str, value: Any, ttl: int = 0) -> None:
        ttl = ttl or self.CACHE_TTL_SECONDS
        self._cache[session_id][key] = {
            "value": value,
            "timestamp": time.time(),
            "ttl": ttl,
        }

    def get_cache(self, session_id: str, key: str) -> Any | None:
        entry = self._cache.get(session_id, {}).get(key)
        if not entry:
            self._stats["cache_misses"] += 1
            return None
        if time.time() - entry["timestamp"] > entry["ttl"]:
            del self._cache[session_id][key]
            self._stats["cache_misses"] += 1
            return None
        self._stats["cache_hits"] += 1
        return entry["value"]

    # -- Long-term memory (user-scoped) --

    def save_preference(
        self, user_id: str, key: str, value: Any, category: str = "general"
    ) -> None:
        self._user_preferences[user_id][key] = MemoryEntry(
            key=key,
            value=value,
            category=category,
            user_id=user_id,
        )

    def get_preference(self, user_id: str, key: str) -> Any | None:
        entry = self._user_preferences.get(user_id, {}).get(key)
        return entry.value if entry else None

    def list_preferences(self, user_id: str) -> dict[str, Any]:
        return {k: e.value for k, e in self._user_preferences.get(user_id, {}).items()}

    def add_to_watchlist(self, user_id: str, code: str, group: str = "default") -> bool:
        wl = self._user_watchlists[user_id][group]
        if code not in wl:
            wl.append(code)
            return True
        return False

    def remove_from_watchlist(
        self, user_id: str, code: str, group: str = "default"
    ) -> bool:
        wl = self._user_watchlists[user_id][group]
        if code in wl:
            wl.remove(code)
            return True
        return False

    def get_watchlist(self, user_id: str, group: str = "default") -> list[str]:
        return list(self._user_watchlists.get(user_id, {}).get(group, []))

    # -- Cleanup --

    def cleanup_expired(self, ttl_seconds: int = 0) -> int:
        ttl = ttl_seconds or self.HISTORY_TTL_SECONDS
        now = time.time()
        expired = [
            sid
            for sid, meta in self._session_meta.items()
            if now - meta["last_access"] > ttl
        ]
        for sid in expired:
            self.clear_session(sid)
        return len(expired)

    # -- Observability (task 5.2) --

    @property
    def active_session_count(self) -> int:
        return len(self._session_meta)

    @property
    def total_cached_keys(self) -> int:
        return sum(len(v) for v in self._cache.values())

    @property
    def stats(self) -> dict[str, Any]:
        """Return a snapshot of observability counters."""
        return {
            "active_sessions": self.active_session_count,
            "total_cached_keys": self.total_cached_keys,
            "cache_hits": self._stats.get("cache_hits", 0),
            "cache_misses": self._stats.get("cache_misses", 0),
            "sessions_evicted": self._stats.get("sessions_evicted", 0),
            "user_preference_count": sum(
                len(v) for v in self._user_preferences.values()
            ),
        }

    def record_stat(self, key: str, increment: int = 1) -> None:
        """Bump a named counter (used by AgentRuntime for task 5.2)."""
        self._stats[key] += increment


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_service: SessionMemoryService | None = None


def get_session_memory_service() -> SessionMemoryService:
    global _service
    if _service is None:
        _service = SessionMemoryService()
    return _service
