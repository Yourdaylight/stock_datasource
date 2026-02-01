"""
Arena Persistence Layer

Handles persistence of thinking messages and arena data to ClickHouse.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
import json

from .models import (
    Arena,
    ArenaState,
    ArenaStrategy,
    ThinkingMessage,
    DiscussionRound,
    StrategyEvaluation,
)

logger = logging.getLogger(__name__)


# =============================================================================
# ClickHouse Writer for Thinking Messages
# =============================================================================

class ThinkingMessageWriter:
    """Writes thinking messages to ClickHouse for persistence.
    
    Schema (to be created):
    CREATE TABLE IF NOT EXISTS arena_thinking_messages (
        id String,
        arena_id String,
        agent_id String,
        agent_role String,
        round_id String,
        message_type String,
        content String,
        metadata String,  -- JSON
        timestamp DateTime64(3)
    ) ENGINE = MergeTree()
    ORDER BY (arena_id, timestamp)
    TTL timestamp + INTERVAL 30 DAY;
    """
    
    def __init__(self):
        self._client = None
        self._table = "arena_thinking_messages"
    
    async def _get_client(self):
        """Lazy load ClickHouse client."""
        if self._client is None:
            try:
                from ..models.database import get_clickhouse_client
                self._client = get_clickhouse_client()
            except Exception as e:
                logger.warning(f"ClickHouse client not available: {e}")
                self._client = False
        return self._client if self._client else None
    
    async def write(self, message: ThinkingMessage) -> bool:
        """Write a single message to ClickHouse."""
        client = await self._get_client()
        if not client:
            return False
        
        try:
            query = f"""
            INSERT INTO {self._table} 
            (id, arena_id, agent_id, agent_role, round_id, message_type, content, metadata, timestamp)
            VALUES
            """
            data = [(
                message.id,
                message.arena_id,
                message.agent_id,
                message.agent_role,
                message.round_id,
                message.message_type.value if hasattr(message.message_type, 'value') else str(message.message_type),
                message.content,
                json.dumps(message.metadata, ensure_ascii=False),
                message.timestamp,
            )]
            client.execute(query, data)
            return True
        except Exception as e:
            logger.warning(f"Failed to write thinking message: {e}")
            return False
    
    async def write_batch(self, messages: List[ThinkingMessage]) -> bool:
        """Write multiple messages in batch."""
        client = await self._get_client()
        if not client or not messages:
            return False
        
        try:
            query = f"""
            INSERT INTO {self._table} 
            (id, arena_id, agent_id, agent_role, round_id, message_type, content, metadata, timestamp)
            VALUES
            """
            data = [
                (
                    m.id,
                    m.arena_id,
                    m.agent_id,
                    m.agent_role,
                    m.round_id,
                    m.message_type.value if hasattr(m.message_type, 'value') else str(m.message_type),
                    m.content,
                    json.dumps(m.metadata, ensure_ascii=False),
                    m.timestamp,
                )
                for m in messages
            ]
            client.execute(query, data)
            return True
        except Exception as e:
            logger.warning(f"Failed to write thinking messages batch: {e}")
            return False
    
    async def get_history(
        self,
        arena_id: str,
        round_id: str = None,
        agent_id: str = None,
        since: datetime = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get message history from ClickHouse."""
        client = await self._get_client()
        if not client:
            return []
        
        try:
            conditions = [f"arena_id = '{arena_id}'"]
            if round_id:
                conditions.append(f"round_id = '{round_id}'")
            if agent_id:
                conditions.append(f"agent_id = '{agent_id}'")
            if since:
                conditions.append(f"timestamp > '{since.isoformat()}'")
            
            where_clause = " AND ".join(conditions)
            
            query = f"""
            SELECT id, arena_id, agent_id, agent_role, round_id, 
                   message_type, content, metadata, timestamp
            FROM {self._table}
            WHERE {where_clause}
            ORDER BY timestamp ASC
            LIMIT {limit}
            """
            
            result = client.execute(query)
            return [
                {
                    "id": row[0],
                    "arena_id": row[1],
                    "agent_id": row[2],
                    "agent_role": row[3],
                    "round_id": row[4],
                    "message_type": row[5],
                    "content": row[6],
                    "metadata": json.loads(row[7]) if row[7] else {},
                    "timestamp": row[8].isoformat() if hasattr(row[8], 'isoformat') else str(row[8]),
                }
                for row in result
            ]
        except Exception as e:
            logger.warning(f"Failed to get thinking message history: {e}")
            return []


# =============================================================================
# Arena Repository
# =============================================================================

class ArenaRepository:
    """Repository for arena persistence.
    
    In-memory implementation with optional ClickHouse persistence.
    
    Schema (to be created):
    CREATE TABLE IF NOT EXISTS arenas (
        id String,
        config String,  -- JSON
        state String,
        strategies String,  -- JSON
        eliminated_strategies String,  -- JSON
        discussion_rounds String,  -- JSON
        current_round_id Nullable(String),
        evaluations String,  -- JSON
        last_evaluation Nullable(DateTime64(3)),
        last_error Nullable(String),
        error_count UInt32,
        created_at DateTime64(3),
        started_at Nullable(DateTime64(3)),
        completed_at Nullable(DateTime64(3)),
        updated_at DateTime64(3)
    ) ENGINE = MergeTree()
    ORDER BY (id, created_at);
    """
    
    def __init__(self):
        # In-memory cache
        self._arenas: Dict[str, Arena] = {}
        self._client = None
        self._table = "arenas"
    
    async def _get_client(self):
        """Lazy load ClickHouse client."""
        if self._client is None:
            try:
                from ..models.database import get_clickhouse_client
                self._client = get_clickhouse_client()
            except Exception as e:
                logger.debug(f"ClickHouse client not available: {e}")
                self._client = False
        return self._client if self._client else None
    
    def create(self, arena: Arena) -> Arena:
        """Create a new arena."""
        self._arenas[arena.id] = arena
        # Fire async persistence
        return arena
    
    def get(self, arena_id: str) -> Optional[Arena]:
        """Get arena by ID."""
        return self._arenas.get(arena_id)
    
    def update(self, arena: Arena) -> Arena:
        """Update an existing arena."""
        arena.updated_at = datetime.now()
        self._arenas[arena.id] = arena
        return arena
    
    def delete(self, arena_id: str) -> bool:
        """Delete an arena."""
        if arena_id in self._arenas:
            del self._arenas[arena_id]
            return True
        return False
    
    def list(
        self,
        state: ArenaState = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Arena]:
        """List arenas with optional filtering."""
        arenas = list(self._arenas.values())
        
        if state:
            arenas = [a for a in arenas if a.state == state]
        
        # Sort by created_at descending
        arenas.sort(key=lambda a: a.created_at, reverse=True)
        
        return arenas[offset:offset + limit]
    
    def count(self, state: ArenaState = None) -> int:
        """Count arenas with optional filtering."""
        if state:
            return len([a for a in self._arenas.values() if a.state == state])
        return len(self._arenas)


# =============================================================================
# Strategy Repository
# =============================================================================

class StrategyRepository:
    """Repository for strategy persistence."""
    
    def __init__(self):
        # Strategies indexed by arena: {arena_id: {strategy_id: ArenaStrategy}}
        self._strategies: Dict[str, Dict[str, ArenaStrategy]] = {}
    
    def create(self, strategy: ArenaStrategy) -> ArenaStrategy:
        """Create a new strategy."""
        arena_id = strategy.arena_id
        if arena_id not in self._strategies:
            self._strategies[arena_id] = {}
        self._strategies[arena_id][strategy.id] = strategy
        return strategy
    
    def get(self, arena_id: str, strategy_id: str) -> Optional[ArenaStrategy]:
        """Get strategy by ID."""
        return self._strategies.get(arena_id, {}).get(strategy_id)
    
    def update(self, strategy: ArenaStrategy) -> ArenaStrategy:
        """Update an existing strategy."""
        strategy.updated_at = datetime.now()
        arena_id = strategy.arena_id
        if arena_id not in self._strategies:
            self._strategies[arena_id] = {}
        self._strategies[arena_id][strategy.id] = strategy
        return strategy
    
    def delete(self, arena_id: str, strategy_id: str) -> bool:
        """Delete a strategy."""
        if arena_id in self._strategies and strategy_id in self._strategies[arena_id]:
            del self._strategies[arena_id][strategy_id]
            return True
        return False
    
    def list_by_arena(
        self,
        arena_id: str,
        active_only: bool = False,
    ) -> List[ArenaStrategy]:
        """List strategies for an arena."""
        strategies = list(self._strategies.get(arena_id, {}).values())
        
        if active_only:
            strategies = [s for s in strategies if s.is_active]
        
        # Sort by score descending
        strategies.sort(key=lambda s: s.current_score, reverse=True)
        
        return strategies
    
    def get_leaderboard(self, arena_id: str, limit: int = 10) -> List[ArenaStrategy]:
        """Get top strategies by score."""
        strategies = self.list_by_arena(arena_id, active_only=True)
        return strategies[:limit]


# =============================================================================
# Global Repository Instances
# =============================================================================

_arena_repository: Optional[ArenaRepository] = None
_strategy_repository: Optional[StrategyRepository] = None


def get_arena_repository() -> ArenaRepository:
    """Get global arena repository instance."""
    global _arena_repository
    if _arena_repository is None:
        _arena_repository = ArenaRepository()
    return _arena_repository


def get_strategy_repository() -> StrategyRepository:
    """Get global strategy repository instance."""
    global _strategy_repository
    if _strategy_repository is None:
        _strategy_repository = StrategyRepository()
    return _strategy_repository
