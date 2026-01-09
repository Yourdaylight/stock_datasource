"""LLM client factory and implementations with Langfuse observability."""

import os
import logging
from typing import List, Dict, Any, AsyncGenerator, Optional

# Load .env file at module import
from dotenv import load_dotenv
load_dotenv()

from .base import BaseLLMClient

logger = logging.getLogger(__name__)

# Global Langfuse instance
_langfuse = None
_langfuse_handler = None


def get_langfuse():
    """Get or create Langfuse instance."""
    global _langfuse
    if _langfuse is None:
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
        secret_key = os.getenv("LANGFUSE_SECRET_KEY")
        host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        enabled = os.getenv("LANGFUSE_ENABLED", "true").lower() == "true"
        
        if enabled and public_key and secret_key:
            try:
                from langfuse import Langfuse
                _langfuse = Langfuse(
                    public_key=public_key,
                    secret_key=secret_key,
                    host=host
                )
                logger.info(f"Langfuse initialized with host: {host}")
            except ImportError:
                logger.warning("langfuse package not installed")
            except Exception as e:
                logger.warning(f"Failed to initialize Langfuse: {e}")
    return _langfuse


def get_langfuse_handler():
    """Get or create Langfuse callback handler for LangChain."""
    global _langfuse_handler
    if _langfuse_handler is None:
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
        secret_key = os.getenv("LANGFUSE_SECRET_KEY")
        host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        enabled = os.getenv("LANGFUSE_ENABLED", "true").lower() == "true"
        
        if enabled and public_key and secret_key:
            try:
                from langfuse.callback import CallbackHandler
                _langfuse_handler = CallbackHandler(
                    public_key=public_key,
                    secret_key=secret_key,
                    host=host
                )
                logger.info("Langfuse CallbackHandler initialized")
            except ImportError:
                logger.warning("langfuse package not installed")
            except Exception as e:
                logger.warning(f"Failed to initialize Langfuse handler: {e}")
    return _langfuse_handler


class MockLLMClient(BaseLLMClient):
    """Mock LLM client for development and testing."""
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> str:
        """Generate a mock response."""
        return f"[Mock LLM Response] 收到您的请求: {prompt[:50]}..."
    
    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> AsyncGenerator[str, None]:
        """Stream a mock response."""
        response = await self.generate(prompt, system_prompt, temperature, max_tokens)
        for chunk in response.split():
            yield chunk + " "
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        functions: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Chat with mock response."""
        last_message = messages[-1]["content"] if messages else ""
        return {
            "role": "assistant",
            "content": f"[Mock Response] 收到: {last_message[:50]}..."
        }


class OpenAIClient(BaseLLMClient):
    """OpenAI API client with Langfuse observability."""
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4")
        self._client = None
        self._langfuse = None
    
    @property
    def client(self):
        """Lazy load OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url
                )
            except ImportError:
                logger.warning("OpenAI package not installed, using mock client")
                return None
        return self._client
    
    @property
    def langfuse(self):
        """Lazy load Langfuse."""
        if self._langfuse is None:
            self._langfuse = get_langfuse()
        return self._langfuse
    
    def _create_trace(self, name: str, input_data: Any, metadata: Optional[Dict] = None):
        """Create a Langfuse trace for observability."""
        if self.langfuse:
            try:
                return self.langfuse.trace(
                    name=name,
                    input=input_data,
                    metadata=metadata or {}
                )
            except Exception as e:
                logger.debug(f"Failed to create Langfuse trace: {e}")
        return None
    
    def _create_generation(self, trace, name: str, model: str, input_data: Any):
        """Create a Langfuse generation span."""
        if trace:
            try:
                return trace.generation(
                    name=name,
                    model=model,
                    input=input_data
                )
            except Exception as e:
                logger.debug(f"Failed to create Langfuse generation: {e}")
        return None
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        trace_name: Optional[str] = None,
        trace_metadata: Optional[Dict] = None
    ) -> str:
        """Generate response using OpenAI API with Langfuse tracking."""
        if self.client is None:
            return f"[OpenAI not configured] {prompt[:50]}..."
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        # Create Langfuse trace
        trace = self._create_trace(
            name=trace_name or "llm_generate",
            input_data={"prompt": prompt, "system_prompt": system_prompt},
            metadata=trace_metadata
        )
        generation = self._create_generation(
            trace, "chat_completion", self.model, messages
        )
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            result = response.choices[0].message.content
            
            # Update Langfuse generation
            if generation:
                try:
                    generation.end(
                        output=result,
                        usage={
                            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                            "total_tokens": response.usage.total_tokens if response.usage else 0
                        }
                    )
                except Exception as e:
                    logger.debug(f"Failed to end Langfuse generation: {e}")
            
            return result
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            if generation:
                try:
                    generation.end(output=None, level="ERROR", status_message=str(e))
                except:
                    pass
            return f"API调用出错: {str(e)}"
    
    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        trace_name: Optional[str] = None,
        trace_metadata: Optional[Dict] = None
    ) -> AsyncGenerator[str, None]:
        """Stream response using OpenAI API with Langfuse tracking."""
        if self.client is None:
            yield f"[OpenAI not configured] {prompt[:50]}..."
            return
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        # Create Langfuse trace
        trace = self._create_trace(
            name=trace_name or "llm_stream",
            input_data={"prompt": prompt, "system_prompt": system_prompt},
            metadata=trace_metadata
        )
        generation = self._create_generation(
            trace, "chat_completion_stream", self.model, messages
        )
        
        full_response = ""
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    yield content
            
            # Update Langfuse generation
            if generation:
                try:
                    generation.end(output=full_response)
                except Exception as e:
                    logger.debug(f"Failed to end Langfuse generation: {e}")
                    
        except Exception as e:
            logger.error(f"OpenAI streaming error: {e}")
            if generation:
                try:
                    generation.end(output=None, level="ERROR", status_message=str(e))
                except:
                    pass
            yield f"API调用出错: {str(e)}"
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        functions: Optional[List[Dict[str, Any]]] = None,
        trace_name: Optional[str] = None,
        trace_metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Chat using OpenAI API with optional function calling and Langfuse tracking."""
        if self.client is None:
            return {"role": "assistant", "content": "[OpenAI not configured]"}
        
        # Create Langfuse trace
        trace = self._create_trace(
            name=trace_name or "llm_chat",
            input_data={"messages": messages, "functions": functions},
            metadata=trace_metadata
        )
        generation = self._create_generation(
            trace, "chat_completion", self.model, messages
        )
        
        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            if functions:
                kwargs["functions"] = functions
                kwargs["function_call"] = "auto"
            
            response = await self.client.chat.completions.create(**kwargs)
            message = response.choices[0].message
            
            result = {"role": "assistant", "content": message.content}
            if hasattr(message, "function_call") and message.function_call:
                result["function_call"] = {
                    "name": message.function_call.name,
                    "arguments": message.function_call.arguments
                }
            
            # Update Langfuse generation
            if generation:
                try:
                    generation.end(
                        output=result,
                        usage={
                            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                            "total_tokens": response.usage.total_tokens if response.usage else 0
                        }
                    )
                except Exception as e:
                    logger.debug(f"Failed to end Langfuse generation: {e}")
            
            return result
        except Exception as e:
            logger.error(f"OpenAI chat error: {e}")
            if generation:
                try:
                    generation.end(output=None, level="ERROR", status_message=str(e))
                except:
                    pass
            return {"role": "assistant", "content": f"API调用出错: {str(e)}"}


# Global client instance
_llm_client: Optional[BaseLLMClient] = None


def get_llm_client() -> BaseLLMClient:
    """Get or create LLM client instance.
    
    Returns:
        LLM client instance
    """
    global _llm_client
    
    if _llm_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            _llm_client = OpenAIClient(api_key=api_key)
            logger.info(f"Using OpenAI LLM client (model: {os.getenv('OPENAI_MODEL', 'gpt-4')})")
        else:
            _llm_client = MockLLMClient()
            logger.info("Using Mock LLM client (set OPENAI_API_KEY for real LLM)")
    
    return _llm_client


def flush_langfuse():
    """Flush Langfuse events (call before shutdown)."""
    if _langfuse:
        try:
            _langfuse.flush()
            logger.info("Langfuse events flushed")
        except Exception as e:
            logger.warning(f"Failed to flush Langfuse: {e}")
