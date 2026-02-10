"""Base Agent class using LangGraph/DeepAgents framework.

All agents in this platform should inherit from LangGraphAgent.

Memory Architecture (A + B + D):
- A: LangGraph MemorySaver for automatic checkpoint
- B: Tool result compression to reduce context size
- D: Shared state storage for cross-turn data caching
"""

import os
import time
import hashlib
import logging
from urllib.parse import urlparse
from abc import ABC, abstractmethod
from typing import Any, Dict, List, AsyncGenerator, Optional, Callable
from collections import defaultdict
from deepagents import create_deep_agent
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration Models
# =============================================================================

class AgentConfig(BaseModel):
    """Agent configuration."""
    name: str = Field(..., description="Agent name")
    description: str = Field(..., description="Agent description")
    model: str = Field(default="gpt-4", description="LLM model name")
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=4000, ge=1)
    recursion_limit: int = Field(default=50, description="LangGraph recursion limit")
    # Memory settings
    max_history_messages: int = Field(default=20, description="Max messages to keep in history")
    max_history_chars: int = Field(default=12000, description="Max chars before triggering summarization")
    history_ttl_seconds: int = Field(default=3600, description="History TTL in seconds (default 1 hour)")


class ToolDefinition(BaseModel):
    """Tool definition for agents."""
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    parameters: Dict[str, Any] = Field(default_factory=dict)


class AgentContext(BaseModel):
    """Context passed to agent during execution."""
    session_id: str = ""
    user_id: str = ""
    stock_codes: List[str] = Field(default_factory=list)
    preferences: Dict[str, Any] = Field(default_factory=dict)
    history: List[Dict[str, str]] = Field(default_factory=list)
    intent: str = ""


class AgentResult(BaseModel):
    """Result from agent execution."""
    response: str
    success: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)


# =============================================================================
# Global Shared Resources
# =============================================================================

# Lazy-loaded LangGraph model
_langchain_model = None

# Lazy-loaded Langfuse handler
_langfuse_handler = None

# Lazy-loaded MemorySaver (LangGraph checkpoint)
_memory_saver = None


def _append_no_proxy(host: Optional[str]) -> None:
    if not host:
        return
    existing = os.getenv("NO_PROXY", "")
    parts = [p.strip() for p in existing.split(",") if p.strip()]
    if host not in parts:
        parts.append(host)
        os.environ["NO_PROXY"] = ",".join(parts)


def get_langchain_model():
    """Get shared LangChain model instance."""
    global _langchain_model
    if _langchain_model is None:
        try:
            from langchain_openai import ChatOpenAI
            
            api_key = os.getenv("OPENAI_API_KEY")
            base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
            model_name = os.getenv("OPENAI_MODEL", "gpt-4")
            
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")
            
            host = urlparse(base_url).hostname
            _append_no_proxy(host)
            
            _langchain_model = ChatOpenAI(
                model=model_name,
                api_key=api_key,
                base_url=base_url,
                temperature=0.7,
            )
            logger.info(f"LangChain model initialized: {model_name} @ {base_url}")
        except Exception as e:
            logger.error(f"Failed to init LangChain model: {e}")
            raise
    return _langchain_model


def get_langfuse_handler(
    user_id: str = None,
    session_id: str = None,
    trace_name: str = None,
    tags: list = None,
    metadata: dict = None
):
    """Get Langfuse callback handler for LangChain.
    
    Note: In Langfuse 3.x, user_id and session_id should be passed via
    LangChain config metadata (langfuse_user_id, langfuse_session_id),
    not via CallbackHandler constructor.
    
    Args:
        user_id: User identifier (for logging only in 3.x)
        session_id: Session identifier (for logging only in 3.x)
        trace_name: Custom name for the trace
        tags: List of tags to attach to the trace
        metadata: Additional metadata to attach
    
    Returns:
        Langfuse CallbackHandler instance or None
    """
    try:
        from langfuse.langchain import CallbackHandler
        
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
        secret_key = os.getenv("LANGFUSE_SECRET_KEY")
        host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        enabled = os.getenv("LANGFUSE_ENABLED", "true").lower() == "true"
        
        if not enabled or not public_key or not secret_key:
            logger.debug("Langfuse disabled or not configured")
            return None
        
        # Langfuse 3.x: user_id and session_id are passed via LangChain config metadata
        # CallbackHandler now only needs update_trace flag
        handler = CallbackHandler(update_trace=True)
        
        logger.info(f"Langfuse handler created for user={user_id}, session={session_id}, trace={trace_name}")
        return handler
        
    except Exception as e:
        logger.warning(f"Failed to create Langfuse handler: {e}")
        return None


def get_memory_saver():
    """Get LangGraph MemorySaver for checkpoint-based memory.
    
    This enables automatic state persistence across conversation turns.
    """
    global _memory_saver
    if _memory_saver is None:
        try:
            from langgraph.checkpoint.memory import MemorySaver
            _memory_saver = MemorySaver()
            logger.info("LangGraph MemorySaver initialized")
        except ImportError:
            logger.warning("langgraph.checkpoint.memory not available, using fallback memory")
            _memory_saver = None
        except Exception as e:
            logger.warning(f"Failed to initialize MemorySaver: {e}")
            _memory_saver = None
    return _memory_saver


# =============================================================================
# Memory Management (D: Shared State Storage)
# =============================================================================

class SessionMemory:
    """Session-based memory manager for conversation history and shared state.
    
    Features:
    - Conversation history with TTL
    - Automatic summarization when context grows too large
    - Shared state cache for tool results
    """
    
    def __init__(self):
        # Conversation history: {session_id: [{"role": str, "content": str, "timestamp": float}]}
        self._history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        # Shared state cache: {session_id: {key: {"value": Any, "timestamp": float}}}
        self._cache: Dict[str, Dict[str, Any]] = defaultdict(dict)
        # Session metadata: {session_id: {"created": float, "last_access": float}}
        self._sessions: Dict[str, Dict[str, float]] = {}
    
    def get_session_id(self, agent_name: str, user_id: str = "default", context_key: str = "") -> str:
        """Generate unique session ID."""
        key = f"{agent_name}:{user_id}:{context_key}"
        return hashlib.md5(key.encode()).hexdigest()[:16]
    
    def add_message(
        self, 
        session_id: str, 
        role: str, 
        content: str,
        max_messages: int = 20
    ):
        """Add message to conversation history."""
        now = time.time()
        
        # Initialize session if needed
        if session_id not in self._sessions:
            self._sessions[session_id] = {"created": now, "last_access": now}
        else:
            self._sessions[session_id]["last_access"] = now
        
        # Add message
        self._history[session_id].append({
            "role": role,
            "content": content,
            "timestamp": now
        })
        
        # Trim if exceeds max
        if len(self._history[session_id]) > max_messages:
            self._history[session_id] = self._history[session_id][-max_messages:]
    
    def get_history(
        self, 
        session_id: str, 
        ttl_seconds: int = 3600,
        max_chars: int = 12000
    ) -> List[Dict[str, str]]:
        """Get conversation history, filtering expired messages and applying summarization if needed."""
        now = time.time()
        history = self._history.get(session_id, [])
        
        # Filter by TTL
        valid_history = [
            {"role": h["role"], "content": h["content"]}
            for h in history
            if now - h["timestamp"] < ttl_seconds
        ]
        
        # Check if summarization needed
        total_chars = sum(len(h["content"]) for h in valid_history)
        if total_chars > max_chars and len(valid_history) > 4:
            valid_history = self._summarize_history(valid_history, max_chars)
        
        return valid_history
    
    def _summarize_history(
        self, 
        history: List[Dict[str, str]], 
        max_chars: int
    ) -> List[Dict[str, str]]:
        """Summarize middle portion of history to reduce context size.
        
        Strategy: Keep first 2 + last 2 messages, summarize middle.
        """
        if len(history) <= 4:
            return history
        
        first_msgs = history[:2]
        last_msgs = history[-2:]
        middle_msgs = history[2:-2]
        
        if not middle_msgs:
            return history
        
        # Create summary of middle messages
        summary_parts = []
        for msg in middle_msgs:
            role = msg["role"]
            content = msg["content"]
            # Truncate long content
            if len(content) > 150:
                content = content[:150] + "..."
            summary_parts.append(f"[{role}]: {content}")
        
        summary = {
            "role": "system",
            "content": f"[对话历史摘要 - {len(middle_msgs)}条消息]\n" + "\n".join(summary_parts)
        }
        
        result = first_msgs + [summary] + last_msgs
        logger.debug(f"Summarized history: {len(history)} -> {len(result)} messages")
        return result
    
    def set_cache(self, session_id: str, key: str, value: Any, ttl_seconds: int = 300):
        """Set cached value for session (default 5 min TTL)."""
        self._cache[session_id][key] = {
            "value": value,
            "timestamp": time.time(),
            "ttl": ttl_seconds
        }
    
    def get_cache(self, session_id: str, key: str) -> Optional[Any]:
        """Get cached value if not expired."""
        cache_entry = self._cache.get(session_id, {}).get(key)
        if not cache_entry:
            return None
        
        if time.time() - cache_entry["timestamp"] > cache_entry["ttl"]:
            # Expired
            del self._cache[session_id][key]
            return None
        
        return cache_entry["value"]
    
    def clear_session(self, session_id: str):
        """Clear all data for a session."""
        if session_id in self._history:
            del self._history[session_id]
        if session_id in self._cache:
            del self._cache[session_id]
        if session_id in self._sessions:
            del self._sessions[session_id]
    
    def cleanup_expired(self, ttl_seconds: int = 3600):
        """Clean up expired sessions."""
        now = time.time()
        expired = [
            sid for sid, meta in self._sessions.items()
            if now - meta["last_access"] > ttl_seconds
        ]
        for sid in expired:
            self.clear_session(sid)
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")


# Global session memory instance
_session_memory: Optional[SessionMemory] = None


def get_session_memory() -> SessionMemory:
    """Get global session memory instance."""
    global _session_memory
    if _session_memory is None:
        _session_memory = SessionMemory()
    return _session_memory


# =============================================================================
# Tool Result Compression (B: Compress large tool outputs)
# =============================================================================

def compress_tool_result(result: Any, max_chars: int = 2000) -> Any:
    """Compress tool result to reduce context size.
    
    Strategies:
    - Truncate long strings
    - Limit list items
    - Remove verbose nested data
    """
    if isinstance(result, str):
        if len(result) > max_chars:
            return result[:max_chars] + f"\n...[截断，原长度{len(result)}字符]"
        return result
    
    if isinstance(result, dict):
        compressed = {}
        for key, value in result.items():
            # Skip very large nested data
            if key in ("raw_data", "full_data", "debug"):
                compressed[key] = f"[数据已省略]"
            elif isinstance(value, list) and len(value) > 10:
                # Keep first 10 items for lists
                compressed[key] = value[:10]
                if len(value) > 10:
                    compressed[f"{key}_note"] = f"[仅显示前10条，共{len(value)}条]"
            elif isinstance(value, str) and len(value) > 500:
                compressed[key] = value[:500] + "..."
            else:
                compressed[key] = compress_tool_result(value, max_chars // 2)
        return compressed
    
    if isinstance(result, list):
        if len(result) > 20:
            return result[:20] + [f"...[共{len(result)}项]"]
        return [compress_tool_result(item, max_chars // len(result)) for item in result]
    
    return result


# =============================================================================
# LangGraphAgent Base Class
# =============================================================================

class LangGraphAgent(ABC):
    """Base class for all agents using LangGraph/DeepAgents framework.
    
    All agents should inherit from this class and implement:
    - get_tools(): Return list of tool functions
    - get_system_prompt(): Return system prompt string
    
    Memory Features:
    - Automatic conversation history management
    - LangGraph checkpoint support (when available)
    - Tool result caching to avoid redundant calls
    - Automatic summarization for long conversations
    """
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self._agent = None
        self._model = None
        self._checkpointer = None
        self._memory = get_session_memory()
    
    @abstractmethod
    def get_tools(self) -> List[Callable]:
        """Return list of tool functions for this agent.
        
        Each tool should be a function with:
        - Type hints for parameters
        - Docstring describing the tool
        """
        pass
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return system prompt for this agent."""
        pass
    
    def _get_model(self):
        """Get LangChain model."""
        if self._model is None:
            self._model = get_langchain_model()
        return self._model
    
    def _get_checkpointer(self):
        """Get LangGraph checkpointer for memory persistence."""
        if self._checkpointer is None:
            self._checkpointer = get_memory_saver()
        return self._checkpointer
    
    def _get_callbacks(self, session_id: str = None, user_id: str = None, context: Dict[str, Any] = None) -> List:
        """Get callback handlers including Langfuse with user context.
        
        Args:
            session_id: Session identifier
            user_id: User identifier for Langfuse tracking
            context: Additional context for metadata
        
        Returns:
            List of callback handlers
        """
        callbacks = []
        
        # Build metadata from context
        metadata = {}
        if context:
            metadata["intent"] = context.get("intent", "")
            metadata["stock_codes"] = context.get("stock_codes", [])
        
        handler = get_langfuse_handler(
            user_id=user_id,
            session_id=session_id,
            trace_name=self.config.name,
            tags=[self.config.name],
            metadata=metadata if metadata else None
        )
        
        if handler:
            callbacks.append(handler)
        return callbacks
    
    # Common output rules appended to all system prompts
    COMMON_OUTPUT_RULES = """

## 输出格式规则（必须遵守）
- **禁止**直接输出工具返回的原始JSON或字典数据
- 必须用自然语言解读、总结和分析工具返回的数据
- 使用Markdown格式（标题、表格、列表）让输出更易读
- 数值要有单位和解释，如"上证指数下跌0.64%"而非输出{"pct_chg": -0.64}
"""
    
    def _init_agent(self, checkpointer=None):
        """Initialize the DeepAgent with optional checkpointer."""
        # If checkpointer changed, recreate agent
        if self._agent is not None and checkpointer is None:
            return self._agent
        
        try:
            model = self._get_model()
            tools = self.get_tools()
            # Append common output rules to system prompt
            system_prompt = self.get_system_prompt() + self.COMMON_OUTPUT_RULES
            
            # Create agent with checkpointer if available
            create_kwargs = {
                "model": model,
                "tools": tools,
                "system_prompt": system_prompt,
            }
            
            if checkpointer:
                create_kwargs["checkpointer"] = checkpointer
            
            self._agent = create_deep_agent(**create_kwargs)
            logger.info(f"{self.config.name} initialized with DeepAgents (checkpointer={checkpointer is not None})")
            return self._agent
        except Exception as e:
            logger.error(f"Failed to init {self.config.name}: {e}")
            raise
    
    def _build_messages(
        self, 
        task: str, 
        session_id: str,
        context: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Build messages list with history and current task."""
        messages = []
        
        # Get history from session memory
        history = self._memory.get_history(
            session_id,
            ttl_seconds=self.config.history_ttl_seconds,
            max_chars=self.config.max_history_chars
        )
        
        # Also merge any history passed in context
        context_history = context.get("history", [])
        if context_history and not history:
            # Use context history if session memory is empty
            history = context_history[-self.config.max_history_messages:]
        
        # Add history messages
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant", "system") and content:
                messages.append({"role": role, "content": content})
        
        # Add current task
        messages.append({"role": "user", "content": task})
        
        return messages
    
    async def execute(
        self, 
        task: str, 
        context: Dict[str, Any] = None
    ) -> AgentResult:
        """Execute a task using DeepAgent with memory support.
        
        Args:
            task: User's query or task
            context: Optional context with:
                - session_id: Unique session identifier
                - user_id: User identifier
                - history: Previous conversation (fallback if session memory empty)
                - clear_history: If True, clear session before execution
            
        Returns:
            AgentResult with response and metadata
        """
        context = context or {}
        
        # Generate or use provided session_id
        user_id = context.get("user_id", "default")
        context_key = context.get("context_key", "")
        session_id = context.get("session_id") or self._memory.get_session_id(
            self.config.name, user_id, context_key
        )
        
        # Clear history if requested
        if context.get("clear_history"):
            self._memory.clear_session(session_id)
            logger.info(f"Cleared session {session_id}")
        
        # Opportunistic cleanup to avoid unbounded memory growth
        self._memory.cleanup_expired(ttl_seconds=self.config.history_ttl_seconds)

        try:
            # Get checkpointer for LangGraph memory
            checkpointer = self._get_checkpointer()
            agent = self._init_agent(checkpointer)
            callbacks = self._get_callbacks(session_id, user_id=user_id, context=context)
            
            # Build messages with history
            messages = self._build_messages(task, session_id, context)
            
            # Save user message to history
            self._memory.add_message(
                session_id, "user", task,
                max_messages=self.config.max_history_messages
            )
            
            # Execute agent
            config = {
                "recursion_limit": self.config.recursion_limit,
                "configurable": {"thread_id": session_id},  # For LangGraph checkpoint
                "metadata": {
                    "langfuse_user_id": user_id,
                    "langfuse_session_id": session_id,
                    "langfuse_tags": [self.config.name],
                }
            }
            if callbacks:
                config["callbacks"] = callbacks
            
            result = agent.invoke({"messages": messages}, config=config)
            
            # Extract response - find the last AI message with content
            response = ""
            messages_list = result.get("messages", [])
            
            for msg in reversed(messages_list):
                msg_type = type(msg).__name__
                if msg_type == "AIMessage" and hasattr(msg, "content") and msg.content:
                    response = msg.content
                    break
            
            if not response:
                response = "无法生成回复"
                logger.warning(f"No AI response found in {len(messages_list)} messages")
            
            # Save assistant response to history (truncate if too long)
            response_for_history = response
            if len(response_for_history) > 2000:
                response_for_history = response_for_history[:2000] + "\n...[内容已截断]"
            self._memory.add_message(
                session_id, "assistant", response_for_history,
                max_messages=self.config.max_history_messages
            )
            
            # Extract tool calls
            tool_calls = []
            for msg in messages_list:
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_calls.append({
                            "name": tc.get("name", "unknown"),
                            "args": tc.get("args", {}),
                        })
            
            return AgentResult(
                response=response,
                success=True,
                metadata={
                    "agent": self.config.name,
                    "session_id": session_id,
                    "message_count": len(messages_list),
                    "history_length": len(self._memory.get_history(session_id)),
                },
                tool_calls=tool_calls,
            )
            
        except Exception as e:
            logger.error(f"{self.config.name} execution failed: {e}")
            return AgentResult(
                response=f"执行出错: {str(e)}",
                success=False,
                metadata={"error": str(e), "agent": self.config.name, "session_id": session_id},
            )
    
    async def execute_stream(
        self, 
        task: str, 
        context: Dict[str, Any] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute task with streaming response.
        
        Args:
            task: User's query
            context: Optional context
            
        Yields:
            Dict with type (thinking/content/done/error) and data
        """
        context = context or {}
        
        # Generate or use provided session_id
        user_id = context.get("user_id", "default")
        context_key = context.get("context_key", "")
        session_id = context.get("session_id") or self._memory.get_session_id(
            self.config.name, user_id, context_key
        )
        
        # Clear history if requested
        if context.get("clear_history"):
            self._memory.clear_session(session_id)
        
        # Opportunistic cleanup to avoid unbounded memory growth
        self._memory.cleanup_expired(ttl_seconds=self.config.history_ttl_seconds)

        try:
            checkpointer = self._get_checkpointer()
            agent = self._init_agent(checkpointer)
            callbacks = self._get_callbacks(session_id, user_id=user_id, context=context)
            
            # Build messages with history
            messages = self._build_messages(task, session_id, context)
            
            # Save user message to history
            self._memory.add_message(
                session_id, "user", task,
                max_messages=self.config.max_history_messages
            )
            
            # Yield thinking status
            yield {
                "type": "thinking",
                "agent": self.config.name,
                "status": "分析中...",
                "session_id": session_id,
            }
            
            # Execute with streaming
            config = {
                "recursion_limit": self.config.recursion_limit,
                "configurable": {"thread_id": session_id},
                # Pass Langfuse metadata for user/session tracking
                "metadata": {
                    "langfuse_user_id": user_id,
                    "langfuse_session_id": session_id,
                    "langfuse_tags": [self.config.name],
                }
            }
            if callbacks:
                config["callbacks"] = callbacks
            
            tool_calls_seen = []
            full_response = ""
            
            async for event in agent.astream_events(
                {"messages": messages}, 
                config=config,
                version="v2"
            ):
                event_type = event.get("event", "")
                
                try:
                    if event_type == "on_tool_start":
                        tool_name = event.get("name", "unknown")
                        tool_calls_seen.append(tool_name)
                        yield {
                            "type": "thinking",
                            "agent": self.config.name,
                            "status": f"正在调用: {tool_name}",
                            "tool": tool_name,
                        }
                    
                    elif event_type == "on_chat_model_stream":
                        chunk = event.get("data", {}).get("chunk")
                        if chunk:
                            content = None
                            if hasattr(chunk, "content") and chunk.content:
                                content = chunk.content
                            elif isinstance(chunk, dict) and chunk.get("content"):
                                content = chunk["content"]
                            
                            if content and isinstance(content, str):
                                full_response += content
                                yield {
                                    "type": "content",
                                    "content": content,
                                }
                    
                    elif event_type == "on_chain_end":
                        # Skip on_chain_end content to avoid duplication
                        # The content has already been streamed via on_chat_model_stream
                        pass
                except Exception as e:
                    logger.debug(f"Error processing event {event_type}: {e}")
            
            # Save assistant response to history
            if full_response:
                response_for_history = full_response
                if len(response_for_history) > 2000:
                    response_for_history = response_for_history[:2000] + "\n...[内容已截断]"
                self._memory.add_message(
                    session_id, "assistant", response_for_history,
                    max_messages=self.config.max_history_messages
                )
            
            # Yield done
            yield {
                "type": "done",
                "metadata": {
                    "agent": self.config.name,
                    "tool_calls": tool_calls_seen,
                    "session_id": session_id,
                    "history_length": len(self._memory.get_history(session_id)),
                },
            }
            
            # Fallback to sync if no content streamed
            if not full_response:
                logger.info(f"{self.config.name}: No streamed content, falling back to sync")
                result = agent.invoke({"messages": messages}, config=config)
                
                for msg in reversed(result.get("messages", [])):
                    msg_type = type(msg).__name__
                    if msg_type == "AIMessage" and hasattr(msg, "content") and msg.content:
                        yield {
                            "type": "content",
                            "content": msg.content,
                        }
                        # Save to history
                        self._memory.add_message(
                            session_id, "assistant", msg.content[:2000],
                            max_messages=self.config.max_history_messages
                        )
                        break
            
        except Exception as e:
            logger.error(f"{self.config.name} stream execution failed: {e}")
            yield {
                "type": "error",
                "error": str(e),
            }
    
    # =========================================================================
    # Cache utilities for tool result caching
    # =========================================================================
    
    def get_cached(self, session_id: str, key: str) -> Optional[Any]:
        """Get cached tool result."""
        return self._memory.get_cache(session_id, key)
    
    def set_cached(self, session_id: str, key: str, value: Any, ttl_seconds: int = 300):
        """Cache tool result."""
        self._memory.set_cache(session_id, key, value, ttl_seconds)
    
    def clear_session(self, session_id: str):
        """Clear session history and cache."""
        self._memory.clear_session(session_id)


# Backward compatibility aliases
BaseTool = ToolDefinition
BaseAgent = LangGraphAgent
BaseStockAgent = LangGraphAgent
