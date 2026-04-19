"""SummarizationMiddleware: Fraction-based conversation summarization.

Reference: deer-flow's SummarizationMiddleware design.
Uses model context window fraction as the primary trigger dimension,
with tokens and messages as fallback triggers.

Financial-scenario customized summary prompt that preserves key numbers.
"""

from __future__ import annotations

import logging

from stock_datasource.modules.memory.models import ContextSize

from .base import AgentContext, AgentResponse, BaseMiddleware

logger = logging.getLogger(__name__)

# Default summary prompt for financial scenario
_FINANCIAL_SUMMARY_PROMPT = """请总结以下对话内容。在总结时务必保留：
1. 所有具体的数字和百分比（如股价、PE值、市值、涨跌幅等）
2. 明确的股票代码和名称
3. 关键的技术指标数值（如MACD、RSI、支撑位/阻力位）
4. 用户的明确偏好或指令

输出简洁的摘要，保留关键数据点，省略重复的分析过程。"""


class SummarizationMiddleware(BaseMiddleware):
    """Fraction-based conversation summarization middleware.

    Trigger conditions (OR logic, any condition triggers summarization):
    - fraction: % of model's max input tokens
    - tokens: absolute token count
    - messages: message count

    Keep policy: how much recent context to preserve after summarization.
    """

    # Default model context window sizes
    MODEL_WINDOWS = {
        "gpt-4": 128000,
        "gpt-4o": 128000,
        "gpt-4o-mini": 128000,
        "gpt-3.5-turbo": 16385,
        "claude-3-opus": 200000,
        "claude-3-sonnet": 200000,
        "claude-3-haiku": 200000,
    }

    # Characters per token (approximate)
    CHARS_PER_TOKEN: float = 3.3

    def __init__(
        self,
        trigger: list[ContextSize] | None = None,
        keep: ContextSize | None = None,
        summary_prompt: str | None = None,
        model_name: str = "",
        model_max_tokens: int = 0,
    ):
        super().__init__()
        self._trigger = trigger or [
            ContextSize(type="fraction", value=0.7),
            ContextSize(type="tokens", value=6000),
        ]
        self._keep = keep or ContextSize(type="fraction", value=0.3)
        self._summary_prompt = summary_prompt or _FINANCIAL_SUMMARY_PROMPT
        self._model_name = model_name
        self._model_max_tokens = model_max_tokens or self._detect_model_window()

    def _detect_model_window(self) -> int:
        """Detect model context window size from model name."""
        import os

        model = self._model_name or os.getenv("OPENAI_MODEL", "gpt-4")

        for key, window in self.MODEL_WINDOWS.items():
            if key in model.lower():
                return window

        return 128000  # Default assumption

    async def before(self, context: AgentContext) -> AgentContext:
        """Check if summarization should be triggered based on context size."""
        if not self.enabled:
            return context

        context.trace(self.name, "start")

        # Estimate current token usage from context
        # This is a heuristic; actual token counting would require tiktoken
        context_chars = len(context.query) + len(context.memory_block)
        context_tokens = int(context_chars / self.CHARS_PER_TOKEN)

        # Check trigger conditions (OR logic)
        should_summarize = False
        for trigger in self._trigger:
            threshold = trigger.resolve(self._model_max_tokens)
            if (trigger.type == "fraction" and context_tokens >= threshold) or (
                trigger.type == "tokens" and context_tokens >= threshold
            ):
                should_summarize = True
                break

        if should_summarize:
            context.extra["summarization_needed"] = True
            context.trace(self.name, "triggered")

        context.trace(self.name, "done")
        return context

    async def after(
        self, context: AgentContext, response: AgentResponse
    ) -> AgentResponse:
        """No post-processing needed for summarization in this implementation.

        Actual summarization is handled by LangGraph's built-in mechanisms
        or by modifying the message history before the next call.
        """
        return response
