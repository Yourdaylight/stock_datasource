"""Base Agent class using LangGraph/DeepAgents framework.

All agents in this platform should inherit from LangGraphAgent.
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, AsyncGenerator, Optional, Callable
from deepagents import create_deep_agent
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AgentConfig(BaseModel):
    """Agent configuration."""
    name: str = Field(..., description="Agent name")
    description: str = Field(..., description="Agent description")
    model: str = Field(default="gpt-4", description="LLM model name")
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=4000, ge=1)
    recursion_limit: int = Field(default=50, description="LangGraph recursion limit")


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


# Lazy-loaded LangGraph model
_langchain_model = None


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


# Lazy-loaded Langfuse handler
_langfuse_handler = None


def get_langfuse_handler():
    """Get Langfuse callback handler for LangChain."""
    global _langfuse_handler
    if _langfuse_handler is None:
        try:
            from langfuse.langchain import CallbackHandler
            
            public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
            secret_key = os.getenv("LANGFUSE_SECRET_KEY")
            host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
            enabled = os.getenv("LANGFUSE_ENABLED", "true").lower() == "true"
            
            if enabled and public_key and secret_key:
                os.environ["LANGFUSE_PUBLIC_KEY"] = public_key
                os.environ["LANGFUSE_SECRET_KEY"] = secret_key
                os.environ["LANGFUSE_HOST"] = host
                
                _langfuse_handler = CallbackHandler()
                logger.info(f"Langfuse handler initialized: {host}")
            else:
                logger.info("Langfuse disabled or not configured")
        except Exception as e:
            logger.warning(f"Failed to initialize Langfuse handler: {e}")
    
    return _langfuse_handler


class LangGraphAgent(ABC):
    """Base class for all agents using LangGraph/DeepAgents framework.
    
    All agents should inherit from this class and implement:
    - get_tools(): Return list of tool functions
    - get_system_prompt(): Return system prompt string
    """
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self._agent = None
        self._model = None
    
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
    
    def _get_callbacks(self, session_id: str = None) -> List:
        """Get callback handlers including Langfuse."""
        callbacks = []
        handler = get_langfuse_handler()
        if handler:
            callbacks.append(handler)
        return callbacks
    
    def _init_agent(self):
        """Initialize the DeepAgent."""
        if self._agent is not None:
            return self._agent
        
        try:
            model = self._get_model()
            tools = self.get_tools()
            system_prompt = self.get_system_prompt()
            
            self._agent = create_deep_agent(
                model=model,
                tools=tools,
                system_prompt=system_prompt,
            )
            logger.info(f"{self.config.name} initialized with DeepAgents")
            return self._agent
        except Exception as e:
            logger.error(f"Failed to init {self.config.name}: {e}")
            raise
    
    async def execute(self, task: str, context: Dict[str, Any] = None) -> AgentResult:
        """Execute a task using DeepAgent.
        
        Args:
            task: User's query or task
            context: Optional context (session_id, history, etc.)
            
        Returns:
            AgentResult with response and metadata
        """
        context = context or {}
        session_id = context.get("session_id", "default")
        
        try:
            agent = self._init_agent()
            callbacks = self._get_callbacks(session_id)
            
            # Build messages
            messages = [{"role": "user", "content": task}]
            
            # Add history if available
            history = context.get("history", [])
            if history:
                history_messages = []
                for msg in history[-10:]:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role in ("user", "assistant") and content:
                        history_messages.append({"role": role, "content": content})
                messages = history_messages + messages
            
            # Execute agent
            config = {"recursion_limit": self.config.recursion_limit}
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
                },
                tool_calls=tool_calls,
            )
            
        except Exception as e:
            logger.error(f"{self.config.name} execution failed: {e}")
            return AgentResult(
                response=f"执行出错: {str(e)}",
                success=False,
                metadata={"error": str(e), "agent": self.config.name},
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
        session_id = context.get("session_id", "default")
        
        try:
            agent = self._init_agent()
            callbacks = self._get_callbacks(session_id)
            
            # Build messages
            messages = [{"role": "user", "content": task}]
            
            # Add history
            history = context.get("history", [])
            if history:
                history_messages = []
                for msg in history[-10:]:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role in ("user", "assistant") and content:
                        history_messages.append({"role": role, "content": content})
                messages = history_messages + messages
            
            # Yield thinking status
            yield {
                "type": "thinking",
                "agent": self.config.name,
                "status": "分析中...",
            }
            
            # Execute with streaming
            config = {"recursion_limit": self.config.recursion_limit}
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
                        output = event.get("data", {}).get("output")
                        if output and isinstance(output, dict) and "messages" in output:
                            msgs = output["messages"]
                            if msgs:
                                last_msg = msgs[-1]
                                if hasattr(last_msg, "content") and last_msg.content:
                                    if not full_response:
                                        full_response = last_msg.content
                                        yield {
                                            "type": "content",
                                            "content": last_msg.content,
                                        }
                except Exception as e:
                    logger.debug(f"Error processing event {event_type}: {e}")
            
            # Yield done
            yield {
                "type": "done",
                "metadata": {
                    "agent": self.config.name,
                    "tool_calls": tool_calls_seen,
                    "session_id": session_id,
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
                        break
            
        except Exception as e:
            logger.error(f"{self.config.name} stream execution failed: {e}")
            yield {
                "type": "error",
                "error": str(e),
            }


# Backward compatibility aliases
BaseTool = ToolDefinition
BaseAgent = LangGraphAgent
BaseStockAgent = LangGraphAgent
