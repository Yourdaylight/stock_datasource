"""CrossValidationMiddleware: Cross-validate conclusions from multiple agents.

Only triggered during DeepResearch (is_deep_research=True) when
2+ sub-agents have completed. Uses lightweight LLM to compare
conclusions and detect contradictions.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from .base import AgentContext, AgentResponse, BaseMiddleware
from stock_datasource.modules.memory.store import MemoryStore, get_memory_store

logger = logging.getLogger(__name__)

_CROSS_VALIDATION_PROMPT = """你是一个金融分析交叉验证专家。对比以下不同分析Agent的结论，检测矛盾和一致之处。

重点关注：
- 对同一股票/行业的方向性判断是否矛盾（看涨 vs 看跌）
- 关键数据点是否冲突（如PE值、营收数据）
- 结论的逻辑前提是否一致

Agent结论:
{agent_conclusions}

输出JSON:
{{
  "consistencies": ["一致的结论1", "一致的结论2"],
  "contradictions": [{{"agent_a": "...", "agent_b": "...", "topic": "...", "view_a": "...", "view_b": "...", "severity": "high|medium|low"}}],
  "partial_overlaps": [{{"topic": "...", "common": "...", "diff": "..."}}]
}}"""


class CrossValidationMiddleware(BaseMiddleware):
    """Cross-validate conclusions from multiple sub-agents.

    Only active when context.is_deep_research=True and ≥2 agents have results.
    """

    def __init__(self, store: Optional[MemoryStore] = None):
        super().__init__()
        self._store = store or get_memory_store()

    async def before(self, context: AgentContext) -> AgentContext:
        """No pre-processing needed for cross-validation."""
        if not self.enabled:
            return context
        context.trace(self.name, "skip_before")
        return context

    async def after(self, context: AgentContext, response: AgentResponse) -> AgentResponse:
        """Cross-validate agent conclusions if deep research."""
        if not self.enabled:
            return response

        if not context.is_deep_research:
            context.trace(self.name, "skip_not_deep")
            return response

        try:
            shared_results = self._store.get_shared_results(context.session_id)
            if len(shared_results) < 2:
                context.trace(self.name, "skip_insufficient_agents")
                return response

            context.trace(self.name, "validating")
            result = await self._validate(shared_results)

            if result:
                response.validation_result = result
                # Append validation summary to response
                validation_summary = self._format_validation_result(result)
                if validation_summary:
                    response.content += f"\n\n{validation_summary}"
                context.trace(self.name, "validated")

        except Exception as e:
            logger.warning("Cross-validation failed: %s", e)
            context.trace(self.name, "failed")

        return response

    async def _validate(self, shared_results: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Run LLM cross-validation on agent results."""
        try:
            from stock_datasource.agents.base_agent import get_langchain_model

            # Build agent conclusions text
            conclusions = []
            for key, result in shared_results.items():
                findings = "; ".join(result.key_findings) if result.key_findings else "已执行分析"
                conclusions.append(f"- {result.agent_name}: {findings}")

            if len(conclusions) < 2:
                return None

            agent_conclusions = "\n".join(conclusions)
            prompt = _CROSS_VALIDATION_PROMPT.format(agent_conclusions=agent_conclusions)

            model = get_langchain_model()
            llm_response = await model.ainvoke([{"role": "user", "content": prompt}])

            content = llm_response.content if hasattr(llm_response, "content") else str(llm_response)

            # Parse JSON response
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                return json.loads(match.group(0))

        except Exception as e:
            logger.warning("LLM cross-validation failed: %s", e)

        return None

    @staticmethod
    def _format_validation_result(result: Dict[str, Any]) -> str:
        """Format validation result for user display."""
        lines = []

        consistencies = result.get("consistencies", [])
        contradictions = result.get("contradictions", [])
        partial_overlaps = result.get("partial_overlaps", [])

        if consistencies:
            lines.append("📊 交叉验证结果：")
            for c in consistencies[:3]:
                lines.append(f"✅ 一致：{c}")

        if contradictions:
            for ct in contradictions[:3]:
                severity = ct.get("severity", "medium")
                icon = "🔴" if severity == "high" else "⚠️"
                lines.append(f"{icon} 分歧：{ct.get('topic', '')}")
                lines.append(f"   - {ct.get('agent_a', '')}：{ct.get('view_a', '')}")
                lines.append(f"   - {ct.get('agent_b', '')}：{ct.get('view_b', '')}")
                if severity == "high":
                    lines.append("   → 建议：结合基本面进一步确认")

        if partial_overlaps:
            for po in partial_overlaps[:3]:
                lines.append(f"💡 部分一致：{po.get('common', '')}，但{po.get('diff', '')}")

        return "\n".join(lines) if lines else ""
