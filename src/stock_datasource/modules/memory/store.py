"""LangGraph Store wrapper for the memory system.

Provides a unified interface to LangGraph's BaseStore with:
- Namespace management for facts, profile, conclusions, shared data
- CRUD operations with proper serialization
- Decay/cleanup of stale facts

Uses InMemoryStore for development, easily swappable to SqliteStore for production.

Note: LangGraph Store uses tuple namespaces, e.g. ("user_id", "facts").
      The search() method takes namespace_prefix as a positional-only argument.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from .models import AgentSharedResult, FactItem, UserProfileEntry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Feature flag
# ---------------------------------------------------------------------------


def is_memory_store_enabled() -> bool:
    """Check whether the memory store is enabled."""
    import os

    return os.getenv("MEMORY_STORE_ENABLED", "false").lower() in ("true", "1", "yes")


# ---------------------------------------------------------------------------
# Namespace helpers
# ---------------------------------------------------------------------------


def _ns(*parts: str) -> tuple:
    """Build a namespace tuple from string parts."""
    return tuple(parts)


# ---------------------------------------------------------------------------
# MemoryStore: thin wrapper around LangGraph BaseStore
# ---------------------------------------------------------------------------


class MemoryStore:
    """Thin wrapper around LangGraph BaseStore for namespace-based memory.

    Namespace layout (as tuples):
        ("users", user_id, "facts")       -> FactItem entries
        ("users", user_id, "profile")     -> UserProfileEntry entries
        ("users", user_id, "conclusions") -> conclusion entries
        ("sessions", session_id, "shared") -> AgentSharedResult entries
    """

    def __init__(self):
        self._store = self._create_store()

    @staticmethod
    def _create_store():
        """Create the underlying LangGraph store."""
        import os

        backend = os.getenv("MEMORY_STORE_BACKEND", "memory").lower()

        if backend == "sqlite":
            try:
                from langgraph.store.sqlite import SqliteStore

                db_path = os.getenv("MEMORY_STORE_SQLITE_PATH", "memory_store.db")
                store = SqliteStore(conn_string=db_path)
                store.setup()
                logger.info("MemoryStore: Using SqliteStore at %s", db_path)
                return store
            except ImportError:
                logger.warning(
                    "SqliteStore not available, falling back to InMemoryStore"
                )

        # Default: InMemoryStore
        try:
            from langgraph.store.memory import InMemoryStore

            logger.info("MemoryStore: Using InMemoryStore")
            return InMemoryStore()
        except ImportError:
            logger.warning("langgraph.store.memory not available, using dict fallback")
            return _DictStoreFallback()

    @property
    def raw_store(self):
        """Access the underlying LangGraph store for supervisor.compile(store=...)."""
        return self._store

    # ------------------------------------------------------------------
    # Facts
    # ------------------------------------------------------------------

    def _facts_ns(self, user_id: str) -> tuple:
        return _ns("users", user_id, "facts")

    def put_fact(self, user_id: str, fact_id: str, fact: FactItem) -> None:
        """Store or update a fact."""
        try:
            self._store.put(
                namespace=self._facts_ns(user_id),
                key=fact_id,
                value=fact.to_dict(),
            )
        except Exception as e:
            logger.warning("Failed to put fact %s: %s", fact_id, e)

    def get_fact(self, user_id: str, fact_id: str) -> FactItem | None:
        """Retrieve a single fact by ID."""
        try:
            item = self._store.get(
                namespace=self._facts_ns(user_id),
                key=fact_id,
            )
            if item and item.value:
                return FactItem.from_dict(item.value)
        except Exception as e:
            logger.warning("Failed to get fact %s: %s", fact_id, e)
        return None

    def search_facts(
        self,
        user_id: str,
        limit: int = 15,
        min_confidence: float = 0.0,
    ) -> list[FactItem]:
        """Search facts for a user, sorted by confidence descending."""
        try:
            results = self._store.search(
                self._facts_ns(user_id),
                limit=100,
            )
            facts = []
            for item in results:
                if item.value:
                    fact = FactItem.from_dict(item.value)
                    if fact.confidence >= min_confidence and not fact.should_decay():
                        facts.append(fact)
            facts.sort(key=lambda f: f.confidence, reverse=True)
            return facts[:limit]
        except Exception as e:
            logger.warning("Failed to search facts for %s: %s", user_id, e)
            return []

    def delete_fact(self, user_id: str, fact_id: str) -> None:
        """Delete a fact."""
        try:
            self._store.delete(
                namespace=self._facts_ns(user_id),
                key=fact_id,
            )
        except Exception as e:
            logger.warning("Failed to delete fact %s: %s", fact_id, e)

    def decay_facts(self, user_id: str) -> int:
        """Remove decayed facts for a user. Returns count of removed facts."""
        try:
            results = self._store.search(
                self._facts_ns(user_id),
                limit=100,
            )
            removed = 0
            for item in results:
                if item.value:
                    fact = FactItem.from_dict(item.value)
                    if fact.should_decay():
                        self._store.delete(
                            namespace=self._facts_ns(user_id),
                            key=item.key,
                        )
                        removed += 1
            if removed > 0:
                logger.info("Decayed %d stale facts for user %s", removed, user_id)
            return removed
        except Exception as e:
            logger.warning("Failed to decay facts for %s: %s", user_id, e)
            return 0

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------

    def _profile_ns(self, user_id: str) -> tuple:
        return _ns("users", user_id, "profile")

    def put_profile_entry(self, user_id: str, key: str, value: Any) -> None:
        """Store or update a profile entry."""
        try:
            entry = UserProfileEntry(key=key, value=value)
            self._store.put(
                namespace=self._profile_ns(user_id),
                key=key,
                value=entry.to_dict(),
            )
        except Exception as e:
            logger.warning("Failed to put profile entry %s: %s", key, e)

    def get_profile(self, user_id: str) -> dict[str, Any]:
        """Get all profile entries for a user."""
        try:
            results = self._store.search(
                self._profile_ns(user_id),
                limit=50,
            )
            profile = {}
            for item in results:
                if item.value:
                    entry = UserProfileEntry.from_dict(item.value)
                    profile[entry.key] = entry.value
            return profile
        except Exception as e:
            logger.warning("Failed to get profile for %s: %s", user_id, e)
            return {}

    # ------------------------------------------------------------------
    # Conclusions
    # ------------------------------------------------------------------

    def _conclusions_ns(self, user_id: str) -> tuple:
        return _ns("users", user_id, "conclusions")

    def put_conclusion(
        self, user_id: str, conclusion_id: str, data: dict[str, Any]
    ) -> None:
        """Store a historical analysis conclusion."""
        try:
            data["stored_at"] = time.time()
            self._store.put(
                namespace=self._conclusions_ns(user_id),
                key=conclusion_id,
                value=data,
            )
        except Exception as e:
            logger.warning("Failed to put conclusion %s: %s", conclusion_id, e)

    def search_conclusions(self, user_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search historical conclusions for a user."""
        try:
            results = self._store.search(
                self._conclusions_ns(user_id),
                limit=limit,
            )
            conclusions = [item.value for item in results if item.value]
            conclusions.sort(key=lambda c: c.get("stored_at", 0), reverse=True)
            return conclusions[:limit]
        except Exception as e:
            logger.warning("Failed to search conclusions for %s: %s", user_id, e)
            return []

    # ------------------------------------------------------------------
    # Session shared data (cross-agent)
    # ------------------------------------------------------------------

    def _shared_ns(self, session_id: str) -> tuple:
        return _ns("sessions", session_id, "shared")

    def put_shared_result(
        self, session_id: str, agent_name: str, result: AgentSharedResult
    ) -> None:
        """Store an agent's result for cross-agent sharing within a session."""
        try:
            self._store.put(
                namespace=self._shared_ns(session_id),
                key=f"{agent_name}_result",
                value=result.to_dict(),
            )
        except Exception as e:
            logger.warning("Failed to put shared result for %s: %s", agent_name, e)

    def get_shared_results(self, session_id: str) -> dict[str, AgentSharedResult]:
        """Get all shared agent results for a session."""
        try:
            results = self._store.search(
                self._shared_ns(session_id),
                limit=20,
            )
            shared = {}
            for item in results:
                if item.value:
                    shared[item.key] = AgentSharedResult.from_dict(item.value)
            return shared
        except Exception as e:
            logger.warning(
                "Failed to get shared results for session %s: %s", session_id, e
            )
            return {}

    def clear_shared_results(self, session_id: str) -> None:
        """Clear all shared results for a session."""
        try:
            results = self._store.search(
                self._shared_ns(session_id),
                limit=100,
            )
            for item in results:
                self._store.delete(
                    namespace=self._shared_ns(session_id),
                    key=item.key,
                )
        except Exception as e:
            logger.warning(
                "Failed to clear shared results for session %s: %s", session_id, e
            )


# ---------------------------------------------------------------------------
# Dict-based fallback store (when LangGraph store is unavailable)
# ---------------------------------------------------------------------------


class _StoreItem:
    """Minimal store item for the dict fallback."""

    def __init__(self, key: str, value: Any, namespace: tuple):
        self.key = key
        self.value = value
        self.namespace = namespace


class _DictStoreFallback:
    """Simple dict-based fallback when LangGraph Store is not available.

    Implements the same put/get/search/delete interface as LangGraph BaseStore.
    """

    def __init__(self):
        self._data: dict[tuple, dict[str, Any]] = {}  # namespace -> {key -> StoreItem}

    def put(self, namespace: tuple, key: str, value: Any, **kwargs) -> None:
        if namespace not in self._data:
            self._data[namespace] = {}
        self._data[namespace][key] = _StoreItem(
            key=key, value=value, namespace=namespace
        )

    def get(self, namespace: tuple, key: str, **kwargs) -> _StoreItem | None:
        return self._data.get(namespace, {}).get(key)

    def search(
        self, namespace_prefix: tuple, *, limit: int = 10, **kwargs
    ) -> list[_StoreItem]:
        items = []
        for ns, entries in self._data.items():
            if ns[: len(namespace_prefix)] == namespace_prefix:
                items.extend(entries.values())
        return items[:limit]

    def delete(self, namespace: tuple, key: str, **kwargs) -> None:
        self._data.get(namespace, {}).pop(key, None)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_memory_store: MemoryStore | None = None


def get_memory_store() -> MemoryStore:
    """Get or create the global MemoryStore instance."""
    global _memory_store
    if _memory_store is None:
        _memory_store = MemoryStore()
    return _memory_store
