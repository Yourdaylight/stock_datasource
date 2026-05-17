"""Bridges chat sessions with arena discussions.

This module enables the chat system to trigger multi-agent arena discussions
when multi-agent routing is detected, allowing decision signals to be displayed
in the chat "决策" (Decision) sidebar.
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Optional

import pandas as pd

from stock_datasource.arena.discussion_orchestrator import (
    AgentDiscussionOrchestrator,
)
from stock_datasource.arena.models import (
    AgentConfig,
    AgentRole,
    Arena,
    ArenaConfig,
    ArenaStrategy,
    DiscussionMode,
)
from stock_datasource.models.database import db_client

logger = logging.getLogger(__name__)


# Table DDL for session-arena mapping
_MAPPING_TABLE_CREATED = False
CREATE_MAPPING_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS chat_session_arenas (
    session_id String,
    arena_id String,
    user_id String,
    stock_codes Array(String),
    agents_in_discussion Array(String),
    discussion_mode String,
    created_at DateTime,
    decision_summary_id String DEFAULT '',
) ENGINE = MergeTree()
ORDER BY (user_id, session_id)
"""


def _ensure_mapping_table():
    """Create mapping table if not exists."""
    global _MAPPING_TABLE_CREATED
    if _MAPPING_TABLE_CREATED:
        return
    try:
        db_client.execute(CREATE_MAPPING_TABLE_SQL)
        _MAPPING_TABLE_CREATED = True
        logger.info("Created chat_session_arenas table")
    except Exception as e:
        logger.warning(f"Failed to create chat_session_arenas table: {e}")


class ChatArenaAdapter:
    """Bridges chat sessions with arena discussions.
    
    Responsibilities:
    1. Detect multi-agent scenarios in chat orchestrator
    2. Create Arena instances tied to chat sessions
    3. Run parallel arena discussions while agents execute
    4. Convert ThinkingMessages to chat-compatible debug events
    5. Provide decision summary retrieval for sidebar
    6. Store session-arena mappings in ClickHouse
    
    Example Usage:
        adapter = ChatArenaAdapter()
        arena_id = await adapter.create_arena_for_chat_session(
            session_id="sess_123",
            user_id="user_456",
            stock_codes=["000001", "000002"],
            agents_in_plan=["MarketAgent", "ReportAgent"],
            market_context={...}
        )
        
        async for event in adapter.run_discussion_and_collect_signals(arena_id):
            yield event  # Forward to frontend SSE
    """

    def __init__(self):
        """Initialize adapter."""
        _ensure_mapping_table()
        self._arena_cache: dict[str, Arena] = {}
        self._orchestrator_cache: dict[str, AgentDiscussionOrchestrator] = {}

    async def create_arena_for_chat_session(
        self,
        session_id: str,
        user_id: str,
        stock_codes: list[str],
        agents_in_plan: list[str],
        market_context: dict[str, Any],
    ) -> str:
        """Create Arena instance tied to chat session.
        
        Args:
            session_id: Chat session ID from chat_sessions table
            user_id: User ID who initiated the chat
            stock_codes: Stock symbols being analyzed
            agents_in_plan: List of agent names from orchestrator plan
            market_context: Current market data context
            
        Returns:
            arena_id: Unique ID for this arena instance (for later retrieval)
            
        Raises:
            ValueError: If unable to create arena or store mapping
        """
        try:
            arena_id = f"a_{session_id[:20]}_{int(time.time())}"

            # Map chat agent names to arena agent configs
            agent_configs = []
            for agent_name in agents_in_plan:
                role = self._infer_arena_role(agent_name)
                agent_configs.append(
                    AgentConfig(
                        role=role,
                        personality=agent_name,
                        focus_areas=[agent_name],
                    )
                )

            # If we have fewer than 3 agents, pad with default reviewers
            while len(agent_configs) < 3:
                agent_configs.append(
                    AgentConfig(
                        role=AgentRole.STRATEGY_REVIEWER,
                        personality="critical",
                        focus_areas=["risk", "logic"],
                    )
                )

            # Build proper ArenaConfig (required by Arena dataclass)
            arena_config = ArenaConfig(
                name=f"ChatDiscussion-{session_id[:8]}",
                description=f"Multi-agent discussion for chat session {session_id}",
                agent_count=len(agent_configs),
                agents=agent_configs,
                symbols=stock_codes,
            )

            # Create strategies for each chat agent
            strategies = [
                ArenaStrategy(
                    id=f"strat_{i}_{agent_name}",
                    arena_id=arena_id,
                    user_id=user_id,
                    name=f"{agent_name}_strategy",
                    agent_id=agent_configs[i].agent_id,
                    agent_role=agent_configs[i].role
                    if isinstance(agent_configs[i].role, str)
                    else agent_configs[i].role.value
                    if hasattr(agent_configs[i].role, "value")
                    else str(agent_configs[i].role),
                    symbols=stock_codes,
                )
                for i, agent_name in enumerate(agents_in_plan)
            ]

            # Create Arena with proper dataclass fields
            arena = Arena(
                id=arena_id,
                user_id=user_id,
                config=arena_config,
                strategies=strategies,
            )

            # Store market context as a runtime attribute (not a dataclass field)
            arena._market_context = market_context
            
            # Cache arena for later retrieval
            self._arena_cache[arena_id] = arena
            
            # Store session-arena mapping in ClickHouse
            await self._store_session_arena_mapping(
                session_id=session_id,
                arena_id=arena_id,
                user_id=user_id,
                stock_codes=stock_codes,
                agents=agents_in_plan,
                discussion_mode="debate",
            )
            
            logger.info(
                f"Created arena {arena_id} for chat session {session_id} "
                f"with agents: {agents_in_plan}"
            )
            return arena_id

        except Exception as e:
            logger.error(f"Failed to create arena for chat session: {e}")
            raise ValueError(f"Arena creation failed: {e}") from e

    async def run_discussion_and_collect_signals(
        self,
        arena_id: str,
        discussion_mode: str = "debate",
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Run arena discussion, yield events in real-time as agents speak.

        Uses ThinkingStreamProcessor subscription to get events as they happen,
        rather than waiting for the full discussion to complete.

        Args:
            arena_id: Arena instance ID from create_arena_for_chat_session()
            discussion_mode: "debate" | "collaboration" | "review"

        Yields:
            dict[str, Any]: Debug events (discussion_argument, preview_signal, decision_summary)
        """
        try:
            arena = self._arena_cache.get(arena_id)
            if not arena:
                logger.error(f"Arena {arena_id} not found in cache")
                return

            try:
                orchestrator = AgentDiscussionOrchestrator(arena)
            except Exception as e:
                logger.warning(f"Failed to create orchestrator for arena {arena_id}: {e}")
                return

            # Subscribe to real-time events via ThinkingStreamProcessor
            event_queue: asyncio.Queue = asyncio.Queue()

            async def _on_message(msg):
                await event_queue.put(msg)

            stream_processor = orchestrator.stream_processor
            subscriber_id = stream_processor.store.add_subscriber(arena_id, _on_message)

            try:
                market_ctx = getattr(arena, "_market_context", {})

                # Run discussion in background task
                discussion_task = asyncio.create_task(
                    orchestrator.run_discussion(
                        strategies=arena.strategies,
                        mode=DiscussionMode(discussion_mode),
                        market_context=market_ctx,
                    )
                )

                # Yield events in real-time as they arrive from ThinkingStreamProcessor
                while True:
                    # Check if discussion is done
                    if discussion_task.done():
                        # Drain remaining events
                        while not event_queue.empty():
                            try:
                                msg = event_queue.get_nowait()
                                converted = self._convert_thinking_msg_to_debug(msg, arena_id)
                                if converted:
                                    yield converted
                            except asyncio.QueueEmpty:
                                break
                        break

                    try:
                        msg = await asyncio.wait_for(event_queue.get(), timeout=1.0)
                        converted = self._convert_thinking_msg_to_debug(msg, arena_id)
                        if converted:
                            yield converted
                    except asyncio.TimeoutError:
                        continue

                # Get the discussion result for decision summaries
                try:
                    discussion_round = await discussion_task
                except Exception as e:
                    logger.error(f"Arena discussion failed: {e}")
                    yield {
                        "type": "debug",
                        "debug_type": "arena_error",
                        "agent": "ChatArenaAdapter",
                        "content": f"Arena discussion failed: {str(e)[:100]}",
                        "timestamp": time.time(),
                        "data": {},
                    }
                    return

                # Yield decision summaries (stored on arena by _generate_decision_summary)
                decision_summaries = getattr(arena, "_decision_summaries", [])
                if decision_summaries:
                    for summary in decision_summaries:
                        event = self._convert_decision_summary_to_debug_event(
                            summary, arena_id
                        )
                        yield event

                logger.info(
                    f"Completed arena discussion {arena_id} in {discussion_mode} mode"
                )

            finally:
                stream_processor.store.remove_subscriber(arena_id, subscriber_id)

        except Exception as e:
            logger.error(f"Unexpected error in run_discussion_and_collect_signals: {e}")
            yield {
                "type": "debug",
                "debug_type": "arena_error",
                "agent": "ChatArenaAdapter",
                "content": f"Arena adapter error: {str(e)[:100]}",
                "timestamp": time.time(),
                "data": {},
            }

    def _convert_thinking_msg_to_debug(
        self,
        msg: Any,
        arena_id: str,
    ) -> dict[str, Any] | None:
        """Convert a ThinkingMessage from stream processor to a chat debug event."""
        try:
            # Skip keepalive and system announcements
            if not msg or not hasattr(msg, "content"):
                return None
            if msg.metadata.get("keepalive"):
                return None
            # Skip round start/end system messages (noisy)
            if msg.agent_id == "system" and msg.metadata.get("type") not in (
                "preview_signal",
                "decision_summary",
            ):
                return None

            ts = time.time()
            try:
                ts = msg.timestamp.timestamp() if hasattr(msg.timestamp, "timestamp") else time.time()
            except (AttributeError, TypeError):
                pass

            # Preview signal
            if msg.metadata.get("type") == "preview_signal":
                return {
                    "type": "debug",
                    "debug_type": "preview_signal",
                    "agent": "ChatArenaAdapter",
                    "arena_id": arena_id,
                    "timestamp": ts,
                    "data": {
                        "signal": msg.metadata.get("signal", "HOLD"),
                        "confidence": msg.metadata.get("confidence", 0),
                        "bull_count": msg.metadata.get("bull_count", 0),
                        "bear_count": msg.metadata.get("bear_count", 0),
                        "neutral_count": msg.metadata.get("neutral_count", 0),
                        "is_preview": True,
                        "stock_code": msg.metadata.get("stock_code", ""),
                    },
                }

            # Regular discussion message (argument/conclusion)
            return {
                "type": "debug",
                "debug_type": "discussion_argument",
                "agent": msg.agent_id or "unknown",
                "arena_id": arena_id,
                "timestamp": ts,
                "data": {
                    "content": msg.content[:300] if msg.content else "",
                    "agent_role": msg.agent_role,
                    "round_id": msg.round_id,
                    "message_type": msg.message_type.value
                    if hasattr(msg.message_type, "value")
                    else str(msg.message_type),
                    "direction": msg.metadata.get("direction", "neutral"),
                    "confidence": msg.metadata.get("confidence", 0),
                    "key_point": msg.metadata.get("key_point", ""),
                },
            }
        except Exception as e:
            logger.debug(f"Failed to convert thinking message: {e}")
            return None

    async def get_decision_summary_for_session(
        self,
        session_id: str,
    ) -> Optional[dict[str, Any]]:
        """Retrieve decision summary for display in chat sidebar.
        
        This is called by the frontend to populate the "决策" sidebar.
        
        Args:
            session_id: Chat session ID
            
        Returns:
            dict with keys: signal (BUY|SELL|HOLD), confidence, bull_count,
            bear_count, neutral_count, suggested_action
            
            Returns None if no decision summary available yet.
            
        Example:
            summary = await adapter.get_decision_summary_for_session("sess_123")
            if summary:
                # {"signal": "BUY", "confidence": 0.75, ...}
        """
        try:
            # Query mapping table to get arena_id
            df_mapping = db_client.execute_query(f"""
                SELECT arena_id FROM chat_session_arenas
                WHERE session_id = '{session_id}'
                ORDER BY created_at DESC
                LIMIT 1
            """)

            if df_mapping.empty:
                logger.debug(f"No arena mapping found for session {session_id}")
                return None

            arena_id = df_mapping.iloc[0]["arena_id"]

            # Query thinking_messages to find decision summary
            df_summary = db_client.execute_query(f"""
                SELECT content, metadata
                FROM thinking_messages
                WHERE arena_id = '{arena_id}'
                  AND message_type = 'CONCLUSION'
                ORDER BY created_at DESC
                LIMIT 1
            """)

            if df_summary.empty:
                logger.debug(f"No decision summary found for arena {arena_id}")
                return None

            # Parse decision summary from message
            content = df_summary.iloc[0].get("content", "{}")
            metadata = df_summary.iloc[0].get("metadata", "{}")

            try:
                if isinstance(metadata, str):
                    meta_dict = json.loads(metadata)
                else:
                    meta_dict = metadata or {}
            except Exception:
                meta_dict = {}

            return {
                "signal": meta_dict.get("signal", "NONE"),
                "confidence": meta_dict.get("confidence", 0),
                "bull_count": meta_dict.get("bull_count", 0),
                "bear_count": meta_dict.get("bear_count", 0),
                "neutral_count": meta_dict.get("neutral_count", 0),
                "suggested_action": meta_dict.get("suggested_action", ""),
                "content": content,
            }

        except Exception as e:
            logger.warning(f"Failed to retrieve decision summary for {session_id}: {e}")
            return None

    def _infer_arena_role(self, agent_name: str) -> AgentRole:
        """Map chat agent name to Arena AgentRole enum."""
        role_map = {
            "MarketAgent": AgentRole.MARKET_SENTIMENT,
            "ReportAgent": AgentRole.STRATEGY_GENERATOR,
            "HKReportAgent": AgentRole.STRATEGY_GENERATOR,
            "ScreenerAgent": AgentRole.QUANT_RESEARCHER,
            "EtfAgent": AgentRole.QUANT_RESEARCHER,
            "IndexAgent": AgentRole.QUANT_RESEARCHER,
            "NewsAnalystAgent": AgentRole.MARKET_SENTIMENT,
            "BacktestAgent": AgentRole.STRATEGY_REVIEWER,
            "OverviewAgent": AgentRole.MARKET_SENTIMENT,
        }
        return role_map.get(agent_name, AgentRole.STRATEGY_GENERATOR)

    def _infer_agent_role(self, agent_name: str) -> str:
        """Infer agent role from name for arena configuration (legacy string version)."""
        return self._infer_arena_role(agent_name).value

    async def _store_session_arena_mapping(
        self,
        session_id: str,
        arena_id: str,
        user_id: str,
        stock_codes: list[str],
        agents: list[str],
        discussion_mode: str,
    ) -> None:
        """Store session-arena mapping in ClickHouse.
        
        This enables later retrieval of decision summaries from the sidebar.
        
        Args:
            session_id: Chat session ID
            arena_id: Arena instance ID
            user_id: User ID
            stock_codes: Stock symbols
            agents: Agent names involved
            discussion_mode: "debate" | "collaboration" | "review"
        """
        try:
            _ensure_mapping_table()

            row = {
                "session_id": session_id,
                "arena_id": arena_id,
                "user_id": user_id,
                "stock_codes": stock_codes,
                "agents_in_discussion": agents,
                "discussion_mode": discussion_mode,
                "created_at": datetime.now(),
                "decision_summary_id": "",
            }

            df = pd.DataFrame([row])
            db_client.insert_dataframe("chat_session_arenas", df)
            logger.debug(f"Stored mapping for session {session_id} -> arena {arena_id}")

        except Exception as e:
            logger.warning(f"Failed to store session-arena mapping: {e}")

    def _convert_decision_summary_to_debug_event(
        self,
        summary: Any,
        arena_id: str,
    ) -> dict[str, Any]:
        """Convert Arena DecisionSummary to chat debug event.
        
        Args:
            summary: DecisionSummary object from arena
            arena_id: Arena instance ID
            
        Returns:
            dict: Debug event compatible with chat frontend
        """
        return {
            "type": "debug",
            "debug_type": "decision_summary",
            "agent": "ChatArenaAdapter",
            "arena_id": arena_id,
            "content": (
                f"决策信号: {summary.signal} "
                f"(置信度: {summary.confidence:.0%}) | "
                f"看多: {summary.bull_count} | "
                f"看空: {summary.bear_count} | "
                f"中性: {summary.neutral_count}"
            ),
            "timestamp": time.time(),
            "data": {
                "signal": summary.signal.upper(),
                "confidence": summary.confidence,
                "bull_count": summary.bull_count,
                "bear_count": summary.bear_count,
                "neutral_count": summary.neutral_count,
                "suggested_action": summary.suggested_action,
                "consensus_ratio": summary.consensus_ratio,
                "key_arguments": summary.key_arguments,
                "dissent_points": summary.dissent_points,
            },
        }


# Singleton instance
_adapter: Optional[ChatArenaAdapter] = None


def get_chat_arena_adapter() -> ChatArenaAdapter:
    """Get or create singleton ChatArenaAdapter instance."""
    global _adapter
    if _adapter is None:
        _adapter = ChatArenaAdapter()
    return _adapter

