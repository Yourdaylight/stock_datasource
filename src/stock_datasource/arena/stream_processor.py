"""
Thinking Stream Processor

Handles real-time thinking stream output with dual-write to SSE and persistence.
Provides message publishing, subscription, and history retrieval.
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional
from dataclasses import dataclass, field
import uuid

from .models import ThinkingMessage, MessageType
from .exceptions import ThinkingStreamError

logger = logging.getLogger(__name__)


# =============================================================================
# In-Memory Message Store (for development, replace with Redis in production)
# =============================================================================

@dataclass
class MessageStore:
    """In-memory message store for thinking streams.
    
    In production, this should be replaced with Redis Streams.
    """
    # Messages by arena: {arena_id: [ThinkingMessage]}
    messages: Dict[str, List[ThinkingMessage]] = field(default_factory=dict)
    
    # Subscribers by arena: {arena_id: [callback]}
    subscribers: Dict[str, List[Callable]] = field(default_factory=dict)
    
    # Message TTL in seconds
    message_ttl: int = 86400 * 30  # 30 days
    
    # Max messages per arena
    max_messages_per_arena: int = 10000
    
    def add_message(self, message: ThinkingMessage) -> None:
        """Add a message to the store."""
        arena_id = message.arena_id
        
        if arena_id not in self.messages:
            self.messages[arena_id] = []
        
        self.messages[arena_id].append(message)
        
        # Trim if exceeds max
        if len(self.messages[arena_id]) > self.max_messages_per_arena:
            self.messages[arena_id] = self.messages[arena_id][-self.max_messages_per_arena:]
    
    def get_messages(
        self, 
        arena_id: str, 
        round_id: str = None,
        agent_id: str = None,
        message_type: MessageType = None,
        since: datetime = None,
        limit: int = 100
    ) -> List[ThinkingMessage]:
        """Get messages with optional filters."""
        messages = self.messages.get(arena_id, [])
        
        # Apply filters
        if round_id:
            messages = [m for m in messages if m.round_id == round_id]
        if agent_id:
            messages = [m for m in messages if m.agent_id == agent_id]
        if message_type:
            messages = [m for m in messages if m.message_type == message_type]
        if since:
            messages = [m for m in messages if m.timestamp > since]
        
        # Apply limit
        return messages[-limit:]
    
    def clear_arena(self, arena_id: str) -> None:
        """Clear all messages for an arena."""
        if arena_id in self.messages:
            del self.messages[arena_id]
    
    def add_subscriber(self, arena_id: str, callback: Callable) -> str:
        """Add a subscriber for an arena. Returns subscriber ID."""
        if arena_id not in self.subscribers:
            self.subscribers[arena_id] = []
        
        self.subscribers[arena_id].append(callback)
        return str(len(self.subscribers[arena_id]) - 1)
    
    def remove_subscriber(self, arena_id: str, subscriber_id: str) -> None:
        """Remove a subscriber."""
        try:
            idx = int(subscriber_id)
            if arena_id in self.subscribers and idx < len(self.subscribers[arena_id]):
                self.subscribers[arena_id][idx] = None  # Mark as removed
        except (ValueError, IndexError):
            pass
    
    def get_subscribers(self, arena_id: str) -> List[Callable]:
        """Get active subscribers for an arena."""
        return [s for s in self.subscribers.get(arena_id, []) if s is not None]


# Global message store instance
_message_store: Optional[MessageStore] = None


def get_message_store() -> MessageStore:
    """Get global message store instance."""
    global _message_store
    if _message_store is None:
        _message_store = MessageStore()
    return _message_store


# =============================================================================
# Thinking Stream Processor
# =============================================================================

class ThinkingStreamProcessor:
    """Processes thinking stream messages with dual-write to SSE and persistence.
    
    Features:
    - Real-time message publishing
    - SSE streaming support
    - Message persistence (ClickHouse)
    - History retrieval
    - Subscriber management
    """
    
    def __init__(self, arena_id: str):
        self.arena_id = arena_id
        self.store = get_message_store()
        self._db_writer = None  # Lazy loaded ClickHouse writer
    
    async def publish(
        self,
        agent_id: str,
        agent_role: str,
        content: str,
        message_type: MessageType = MessageType.THINKING,
        round_id: str = "",
        metadata: Dict[str, Any] = None,
    ) -> ThinkingMessage:
        """Publish a thinking message.
        
        This performs dual-write:
        1. In-memory store (for real-time SSE)
        2. ClickHouse (for persistence) - async, non-blocking
        
        Args:
            agent_id: ID of the agent sending the message
            agent_role: Role of the agent
            content: Message content
            message_type: Type of message
            round_id: Discussion round ID
            metadata: Additional metadata
            
        Returns:
            Published ThinkingMessage
        """
        message = ThinkingMessage(
            arena_id=self.arena_id,
            agent_id=agent_id,
            agent_role=agent_role,
            round_id=round_id,
            message_type=message_type,
            content=content,
            metadata=metadata or {},
        )
        
        try:
            # Write to in-memory store
            self.store.add_message(message)
            
            # Notify subscribers
            await self._notify_subscribers(message)
            
            # Async persistence (fire and forget)
            asyncio.create_task(self._persist_message(message))
            
            logger.debug(f"Published message: {message.id} from {agent_role}")
            return message
            
        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
            raise ThinkingStreamError(self.arena_id, "publish", str(e))
    
    async def publish_system(self, content: str, metadata: Dict[str, Any] = None) -> ThinkingMessage:
        """Publish a system message."""
        return await self.publish(
            agent_id="system",
            agent_role="system",
            content=content,
            message_type=MessageType.SYSTEM,
            metadata=metadata,
        )
    
    async def publish_error(self, error: str, metadata: Dict[str, Any] = None) -> ThinkingMessage:
        """Publish an error message."""
        return await self.publish(
            agent_id="system",
            agent_role="system",
            content=error,
            message_type=MessageType.ERROR,
            metadata=metadata,
        )
    
    async def _notify_subscribers(self, message: ThinkingMessage) -> None:
        """Notify all subscribers of a new message."""
        subscribers = self.store.get_subscribers(self.arena_id)
        for callback in subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(message)
                else:
                    callback(message)
            except Exception as e:
                logger.warning(f"Subscriber callback failed: {e}")
    
    async def _persist_message(self, message: ThinkingMessage) -> None:
        """Persist message to ClickHouse (async, non-blocking)."""
        try:
            writer = await self._get_db_writer()
            if writer:
                await writer.write(message)
        except Exception as e:
            # Log but don't fail - persistence is secondary
            logger.warning(f"Failed to persist message to ClickHouse: {e}")
    
    async def _get_db_writer(self):
        """Lazy load ClickHouse writer."""
        if self._db_writer is None:
            try:
                from .persistence import ThinkingMessageWriter
                self._db_writer = ThinkingMessageWriter()
            except ImportError:
                logger.debug("ClickHouse persistence not available")
                self._db_writer = False  # Mark as unavailable
        return self._db_writer if self._db_writer else None
    
    def get_history(
        self,
        round_id: str = None,
        agent_id: str = None,
        message_type: MessageType = None,
        since: datetime = None,
        limit: int = 100,
    ) -> List[ThinkingMessage]:
        """Get message history with optional filters.
        
        Args:
            round_id: Filter by discussion round
            agent_id: Filter by agent
            message_type: Filter by message type
            since: Get messages after this time
            limit: Maximum messages to return
            
        Returns:
            List of ThinkingMessage
        """
        return self.store.get_messages(
            arena_id=self.arena_id,
            round_id=round_id,
            agent_id=agent_id,
            message_type=message_type,
            since=since,
            limit=limit,
        )
    
    async def stream(
        self,
        round_id: str = None,
        since: datetime = None,
        include_history: bool = True,
    ) -> AsyncGenerator[ThinkingMessage, None]:
        """Stream messages as they arrive.
        
        This is an async generator that:
        1. Yields historical messages (if include_history)
        2. Yields new messages as they arrive
        
        Args:
            round_id: Filter by discussion round
            since: Start from this time
            include_history: Include historical messages
            
        Yields:
            ThinkingMessage as they arrive
        """
        # Create a queue for new messages
        queue: asyncio.Queue = asyncio.Queue()
        
        async def on_message(message: ThinkingMessage):
            if round_id and message.round_id != round_id:
                return
            await queue.put(message)
        
        # Subscribe to new messages
        subscriber_id = self.store.add_subscriber(self.arena_id, on_message)
        
        try:
            # Yield historical messages first
            if include_history:
                history = self.get_history(round_id=round_id, since=since)
                for message in history:
                    yield message
            
            # Yield new messages as they arrive
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield message
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield ThinkingMessage(
                        arena_id=self.arena_id,
                        agent_id="system",
                        agent_role="system",
                        message_type=MessageType.SYSTEM,
                        content="keepalive",
                        metadata={"keepalive": True},
                    )
        finally:
            # Unsubscribe
            self.store.remove_subscriber(self.arena_id, subscriber_id)
    
    def clear(self) -> None:
        """Clear all messages for this arena."""
        self.store.clear_arena(self.arena_id)


# =============================================================================
# SSE Response Generator
# =============================================================================

async def generate_sse_stream(
    arena_id: str,
    round_id: str = None,
    since: datetime = None,
) -> AsyncGenerator[str, None]:
    """Generate SSE formatted stream for thinking messages.
    
    Args:
        arena_id: Arena ID to stream
        round_id: Optional round filter
        since: Optional start time
        
    Yields:
        SSE formatted strings
    """
    processor = ThinkingStreamProcessor(arena_id)
    
    async for message in processor.stream(round_id=round_id, since=since):
        # Format as SSE
        data = json.dumps(message.to_dict(), ensure_ascii=False)
        event_type = message.message_type.value if isinstance(message.message_type, MessageType) else message.message_type
        
        yield f"event: {event_type}\n"
        yield f"data: {data}\n\n"
