"""Asynchronous memory update queue with debounce.

Processes fact extraction and store updates in the background,
without blocking the main request flow.

Features:
- 30s debounce per user_id
- Background asyncio.create_task execution
- Auto-retry once on failure
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from .fact_extractor import FactExtractor
from .models import FactItem, SignalResult
from .store import MemoryStore, get_memory_store

logger = logging.getLogger(__name__)


class MemoryUpdateQueue:
    """Asynchronous queue for memory updates with debounce.

    Usage:
        queue = MemoryUpdateQueue()
        await queue.enqueue(user_id, session_id, user_msg, agent_response, signal)
    """

    DEBOUNCE_SECONDS: float = 30.0
    MAX_RETRIES: int = 1

    def __init__(self, store: Optional[MemoryStore] = None, extractor: Optional[FactExtractor] = None):
        self._store = store or get_memory_store()
        self._extractor = extractor or FactExtractor()
        # Track last enqueue time per user_id for debounce
        self._last_enqueue: Dict[str, float] = {}
        # Pending debounce tasks
        self._pending_tasks: Dict[str, asyncio.Task] = {}
        # Buffered messages per user_id
        self._buffer: Dict[str, List[Tuple[str, str, Optional[SignalResult]]]] = {}

    async def enqueue(
        self,
        user_id: str,
        session_id: str,
        user_message: str,
        agent_response: str,
        signal: Optional[SignalResult] = None,
    ) -> None:
        """Enqueue a message pair for fact extraction.

        Debounced: same user_id within DEBOUNCE_SECONDS will be merged.
        """
        now = time.time()
        last = self._last_enqueue.get(user_id, 0)

        # Buffer the message
        if user_id not in self._buffer:
            self._buffer[user_id] = []
        self._buffer[user_id].append((user_message, agent_response, signal))

        # Cancel existing pending task for this user (debounce)
        if user_id in self._pending_tasks:
            self._pending_tasks[user_id].cancel()

        # Schedule new task
        delay = max(0, self.DEBOUNCE_SECONDS - (now - last))
        task = asyncio.create_task(
            self._process_after_delay(user_id, session_id, delay)
        )
        self._pending_tasks[user_id] = task
        self._last_enqueue[user_id] = now

    async def _process_after_delay(self, user_id: str, session_id: str, delay: float) -> None:
        """Wait for debounce period, then process buffered messages."""
        try:
            if delay > 0:
                await asyncio.sleep(delay)

            # Get buffered messages
            messages = self._buffer.pop(user_id, [])
            if not messages:
                return

            await self._process_with_retry(user_id, session_id, messages)

        except asyncio.CancelledError:
            # Debounce cancelled (newer message arrived), do nothing
            pass
        except Exception as e:
            logger.warning("Memory update failed for user %s: %s", user_id, e)
        finally:
            self._pending_tasks.pop(user_id, None)

    async def _process_with_retry(
        self,
        user_id: str,
        session_id: str,
        messages: List[Tuple[str, str, Optional[SignalResult]]],
    ) -> None:
        """Process buffered messages with retry."""
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                await self._process_messages(user_id, session_id, messages)
                return
            except Exception as e:
                if attempt < self.MAX_RETRIES:
                    logger.info("Retrying memory update for user %s (attempt %d)", user_id, attempt + 1)
                    await asyncio.sleep(1)
                else:
                    logger.warning("Memory update failed after %d retries for user %s: %s",
                                   self.MAX_RETRIES, user_id, e)

    async def _process_messages(
        self,
        user_id: str,
        session_id: str,
        messages: List[Tuple[str, str, Optional[SignalResult]]],
    ) -> None:
        """Extract facts from buffered messages and write to store."""
        all_facts: List[FactItem] = []

        for user_msg, agent_resp, signal in messages:
            # Detect signal if not provided
            if signal is None:
                signal = await self._extractor.detect_signal(user_msg)

            # Extract facts
            facts = await self._extractor.extract_facts(
                user_message=user_msg,
                agent_response=agent_resp,
                signal=signal,
                source=f"session:{session_id}",
            )
            all_facts.extend(facts)

            # Handle reinforcement/contradiction of existing facts
            if signal.is_reinforcement or signal.is_correction:
                await self._apply_signal_to_existing_facts(user_id, signal)

        # Write new facts to store
        for fact in all_facts:
            fact_id = f"fact_{int(time.time() * 1000)}_{hash(fact.content) % 10000}"
            self._store.put_fact(user_id, fact_id, fact)

        # Decay stale facts
        self._store.decay_facts(user_id)

        if all_facts:
            logger.info("Extracted %d facts for user %s", len(all_facts), user_id)

    async def _apply_signal_to_existing_facts(self, user_id: str, signal: SignalResult) -> None:
        """Apply reinforcement/contradiction to existing facts matching the signal target."""
        if signal.signal == "neutral" or not signal.target_fact:
            return

        existing_facts = self._store.search_facts(user_id, limit=50)
        target_lower = signal.target_fact.lower()

        for fact in existing_facts:
            # Simple matching: if target_fact keywords appear in fact content
            if target_lower in fact.content.lower() or any(
                word in fact.content.lower()
                for word in target_lower.split()
                if len(word) > 1
            ):
                if signal.is_reinforcement:
                    fact.reinforce()
                elif signal.is_correction:
                    fact.contradict()

                # Update in store (re-put with same key would need the key; search by content)
                # For simplicity, we'll do a full re-index
                fact_id = f"fact_{int(fact.created_at * 1000)}_{hash(fact.content) % 10000}"
                self._store.put_fact(user_id, fact_id, fact)

    @property
    def pending_count(self) -> int:
        """Number of users with pending updates."""
        return len(self._pending_tasks)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_queue: Optional[MemoryUpdateQueue] = None


def get_memory_update_queue() -> MemoryUpdateQueue:
    """Get or create the global MemoryUpdateQueue instance."""
    global _queue
    if _queue is None:
        _queue = MemoryUpdateQueue()
    return _queue
