"""MemoryInjectionMiddleware: Inject memory from LangGraph Store into agent context.

Reads facts, profile, and shared data from the Store and formats them
into a <memory> block appended to the system prompt.

After agent execution, writes shared results and triggers async fact extraction.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from .base import AgentContext, AgentResponse, BaseMiddleware
from stock_datasource.modules.memory.fact_extractor import FactExtractor
from stock_datasource.modules.memory.memory_update_queue import MemoryUpdateQueue, get_memory_update_queue
from stock_datasource.modules.memory.models import AgentSharedResult, FactItem
from stock_datasource.modules.memory.store import MemoryStore, get_memory_store

logger = logging.getLogger(__name__)


class MemoryInjectionMiddleware(BaseMiddleware):
    """Inject memory from LangGraph Store into agent context.

    Before execution:
    1. Read Top-K facts, profile, and shared data from Store
    2. Format into <memory> block with token budget control
    3. Append to context for system prompt injection

    After execution:
    1. Write agent result to session shared namespace
    2. Enqueue fact extraction via MemoryUpdateQueue
    """

    # Token budget as fraction of model context window
    MEMORY_BUDGET_FRACTION_MIN: float = 0.05  # 5%
    MEMORY_BUDGET_FRACTION_MAX: float = 0.08  # 8%

    # Budget allocation across memory types
    FACTS_BUDGET_RATIO: float = 0.6
    PROFILE_BUDGET_RATIO: float = 0.2
    SHARED_BUDGET_RATIO: float = 0.2

    # Max facts to inject
    MAX_FACTS: int = 15
    MIN_CONFIDENCE: float = 0.7

    # Approximate characters per token (for budget estimation)
    CHARS_PER_TOKEN: float = 3.3

    def __init__(
        self,
        store: Optional[MemoryStore] = None,
        update_queue: Optional[MemoryUpdateQueue] = None,
        model_max_tokens: int = 128000,
    ):
        super().__init__()
        self._store = store or get_memory_store()
        self._update_queue = update_queue or get_memory_update_queue()
        self._model_max_tokens = model_max_tokens

    async def before(self, context: AgentContext) -> AgentContext:
        """Read memory from Store and inject into context."""
        if not self.enabled:
            return context

        context.trace(self.name, "start")

        try:
            memory_block = self._build_memory_block(
                user_id=context.user_id,
                session_id=context.session_id,
            )
            context.memory_block = memory_block
            context.trace(self.name, "injected")
        except Exception as e:
            logger.warning("Memory injection failed: %s", e)
            context.trace(self.name, "failed")

        return context

    async def after(self, context: AgentContext, response: AgentResponse) -> AgentResponse:
        """Write shared results and trigger async fact extraction."""
        if not self.enabled:
            return response

        context.trace(self.name, "after_start")

        try:
            # 1. Write shared result for cross-agent sharing
            shared_result = AgentSharedResult(
                agent_name=response.metadata.get("agent", "unknown"),
                tool_calls=response.tool_calls,
                key_findings=self._extract_key_findings(response.content),
                token_count=int(len(response.content) / self.CHARS_PER_TOKEN),
            )
            self._store.put_shared_result(context.session_id, shared_result.agent_name, shared_result)

            # 2. Enqueue async fact extraction (non-blocking)
            await self._update_queue.enqueue(
                user_id=context.user_id,
                session_id=context.session_id,
                user_message=context.query,
                agent_response=response.content[:2000],  # Truncate for efficiency
                signal=context.signal,
            )

            context.trace(self.name, "after_complete")
        except Exception as e:
            logger.warning("Memory after-hook failed: %s", e)

        return response

    def _build_memory_block(self, user_id: str, session_id: str) -> str:
        """Build the <memory> block from Store data with token budget control."""
        budget_tokens = int(self._model_max_tokens * self.MEMORY_BUDGET_FRACTION_MAX)
        budget_chars = int(budget_tokens * self.CHARS_PER_TOKEN)

        # Read from store
        facts = self._store.search_facts(user_id, limit=self.MAX_FACTS, min_confidence=self.MIN_CONFIDENCE)
        profile = self._store.get_profile(user_id)
        shared_results = self._store.get_shared_results(session_id)

        # Allocate character budgets
        facts_budget = int(budget_chars * self.FACTS_BUDGET_RATIO)
        profile_budget = int(budget_chars * self.PROFILE_BUDGET_RATIO)
        shared_budget = int(budget_chars * self.SHARED_BUDGET_RATIO)

        # Build sections
        sections = []

        # Profile section
        profile_section = self._format_profile(profile, profile_budget)
        if profile_section:
            sections.append(profile_section)

        # Facts section
        facts_section = self._format_facts(facts, facts_budget)
        if facts_section:
            sections.append(facts_section)

        # Shared data section
        shared_section = self._format_shared(shared_results, shared_budget)
        if shared_section:
            sections.append(shared_section)

        if not sections:
            return ""

        return "<memory>\n" + "\n\n".join(sections) + "\n</memory>"

    def _format_profile(self, profile: Dict[str, Any], budget_chars: int) -> str:
        """Format profile entries."""
        if not profile:
            return ""

        lines = ["## 用户画像"]
        char_count = len("## 用户画像\n")

        # Map profile keys to Chinese labels
        labels = {
            "risk_preference": "风险偏好",
            "risk_level": "风险偏好",
            "focus_sectors": "关注行业",
            "focus_industries": "关注行业",
            "trading_style": "交易风格",
            "investment_style": "投资风格",
            "expertise_level": "专业程度",
        }

        for key, value in profile.items():
            label = labels.get(key, key)
            line = f"- {label}: {value}"
            if char_count + len(line) > budget_chars:
                break
            lines.append(line)
            char_count += len(line) + 1

        return "\n".join(lines)

    def _format_facts(self, facts: List[FactItem], budget_chars: int) -> str:
        """Format facts with confidence scores."""
        if not facts:
            return ""

        lines = ["## 已知事实（置信度 ≥ 0.7）"]
        char_count = len("## 已知事实（置信度 ≥ 0.7）\n")

        for i, fact in enumerate(facts, 1):
            line = f"{i}. [{fact.confidence:.2f}] {fact.content}"
            if char_count + len(line) > budget_chars:
                break
            lines.append(line)
            char_count += len(line) + 1

        return "\n".join(lines)

    def _format_shared(self, shared_results: Dict[str, AgentSharedResult], budget_chars: int) -> str:
        """Format shared agent results."""
        if not shared_results:
            return ""

        lines = ["## 本次研究共享数据"]
        char_count = len("## 本次研究共享数据\n")

        for key, result in shared_results.items():
            findings_str = "; ".join(result.key_findings[:3]) if result.key_findings else "已执行分析"
            line = f"- {result.agent_name}: {findings_str}"
            if char_count + len(line) > budget_chars:
                break
            lines.append(line)
            char_count += len(line) + 1

        return "\n".join(lines)

    @staticmethod
    def _extract_key_findings(content: str, max_findings: int = 3) -> List[str]:
        """Extract key findings from agent response (heuristic)."""
        # Simple heuristic: first sentence of each paragraph
        if not content:
            return []

        findings = []
        for paragraph in content.split("\n\n"):
            paragraph = paragraph.strip()
            if not paragraph or paragraph.startswith("#"):
                continue
            # Take first sentence (up to first period or 100 chars)
            first_sentence = paragraph.split("。")[0]
            if len(first_sentence) > 100:
                first_sentence = first_sentence[:100] + "..."
            if first_sentence:
                findings.append(first_sentence)
            if len(findings) >= max_findings:
                break

        return findings
