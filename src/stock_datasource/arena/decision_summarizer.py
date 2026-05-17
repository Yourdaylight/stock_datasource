"""
Decision Summarizer

Generates buy/sell/hold decision summaries after Agent discussions complete.
Uses hybrid approach: rule-based vote counting + LLM synthesis.
"""

import json
import logging
import re
from datetime import datetime
from typing import Any

from .models import (
    DecisionSummary,
    DiscussionRound,
    MessageType,
    ThinkingMessage,
)

logger = logging.getLogger(__name__)


class DecisionSummarizer:
    """Generates structured decision summaries from Agent discussions.

    Approach:
    1. Count directional votes from message metadata (rule-based, instant)
    2. Call LLM to synthesize a final recommendation with reasoning
    3. Produce a DecisionSummary with signal, confidence, and dissent points
    """

    def __init__(self):
        self._llm_client = None

    @property
    def llm_client(self):
        """Lazy load LLM client."""
        if self._llm_client is None:
            try:
                from stock_datasource.llm.client import get_llm_client

                self._llm_client = get_llm_client()
            except Exception as e:
                logger.warning(f"Failed to get LLM client for summarizer: {e}")
        return self._llm_client

    async def generate_summary(
        self,
        discussion_round: DiscussionRound,
        stock_code: str = "",
        market_context: dict[str, Any] | None = None,
        arena_id: str = "",
        user_id: str = "",
    ) -> DecisionSummary:
        """Generate a decision summary from a completed discussion round.

        Args:
            discussion_round: Completed discussion round with messages
            stock_code: Target stock code
            market_context: Current market context
            arena_id: Arena ID
            user_id: User ID for data isolation

        Returns:
            DecisionSummary with buy/sell/hold signal
        """
        # Phase 1: Rule-based vote counting from metadata
        vote_result = self._count_votes(discussion_round.messages)

        # Phase 2: Collect key arguments for LLM synthesis
        key_arguments = self._extract_key_arguments(discussion_round.messages)

        # Phase 3: LLM synthesis (if available)
        llm_result = await self._llm_synthesize(
            vote_result=vote_result,
            key_arguments=key_arguments,
            stock_code=stock_code,
            market_context=market_context,
        )

        # Determine final signal based on votes + LLM
        signal, confidence = self._determine_signal(vote_result, llm_result)

        # Calculate consensus ratio
        total_votes = (
            vote_result["bull_count"]
            + vote_result["bear_count"]
            + vote_result["neutral_count"]
        )
        max_votes = max(
            vote_result["bull_count"],
            vote_result["bear_count"],
            vote_result["neutral_count"],
        )
        consensus_ratio = max_votes / total_votes if total_votes > 0 else 0.0

        return DecisionSummary(
            arena_id=arena_id,
            round_id=discussion_round.id,
            user_id=user_id,
            stock_code=stock_code,
            signal=signal,
            confidence=confidence,
            consensus_ratio=round(consensus_ratio, 2),
            bull_count=vote_result["bull_count"],
            bear_count=vote_result["bear_count"],
            neutral_count=vote_result["neutral_count"],
            key_arguments=key_arguments,
            dissent_points=llm_result.get("dissent_points", []),
            suggested_action=llm_result.get("suggested_action", ""),
            generated_at=datetime.now(),
        )

    def _count_votes(self, messages: list[ThinkingMessage]) -> dict[str, int]:
        """Count directional votes from message metadata.

        Only counts ARGUMENT and CONCLUSION messages that have direction metadata.
        Each agent's latest vote counts (overwrites previous votes from same agent).
        """
        agent_votes: dict[str, str] = {}  # agent_id -> latest direction

        for msg in messages:
            if msg.message_type not in [MessageType.ARGUMENT, MessageType.CONCLUSION]:
                continue

            direction = msg.metadata.get("direction")
            if direction and msg.agent_id and msg.agent_id != "system":
                agent_votes[msg.agent_id] = direction

        bull_count = sum(1 for v in agent_votes.values() if v == "bullish")
        bear_count = sum(1 for v in agent_votes.values() if v == "bearish")
        neutral_count = sum(1 for v in agent_votes.values() if v == "neutral")

        return {
            "bull_count": bull_count,
            "bear_count": bear_count,
            "neutral_count": neutral_count,
            "agent_votes": agent_votes,
        }

    def _extract_key_arguments(
        self, messages: list[ThinkingMessage]
    ) -> list[dict[str, Any]]:
        """Extract key arguments from discussion messages."""
        arguments = []

        for msg in messages:
            if msg.message_type not in [MessageType.ARGUMENT, MessageType.CONCLUSION]:
                continue
            if msg.agent_id == "system":
                continue

            direction = msg.metadata.get("direction", "neutral")
            confidence = msg.metadata.get("confidence", 0.5)
            key_point = msg.metadata.get("key_point", msg.content[:80])

            arguments.append(
                {
                    "agent_id": msg.agent_id,
                    "agent_role": msg.agent_role,
                    "direction": direction,
                    "confidence": confidence,
                    "key_point": key_point,
                }
            )

        return arguments

    async def _llm_synthesize(
        self,
        vote_result: dict[str, Any],
        key_arguments: list[dict[str, Any]],
        stock_code: str = "",
        market_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Use LLM to synthesize a final decision from all arguments.

        Returns structured decision with suggested_action and dissent_points.
        Falls back to rule-based decision if LLM is unavailable.
        """
        if not self.llm_client:
            return self._fallback_synthesis(vote_result, key_arguments)

        # Build prompt
        prompt = self._build_synthesis_prompt(
            vote_result, key_arguments, stock_code, market_context
        )

        try:
            result = await self.llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            response = (
                result.get("content", "") if isinstance(result, dict) else str(result)
            )
            return self._parse_synthesis_response(response)
        except Exception as e:
            logger.warning(f"LLM synthesis failed: {e}")
            return self._fallback_synthesis(vote_result, key_arguments)

    def _build_synthesis_prompt(
        self,
        vote_result: dict[str, Any],
        key_arguments: list[dict[str, Any]],
        stock_code: str,
        market_context: dict[str, Any] | None,
    ) -> str:
        """Build the LLM prompt for decision synthesis."""
        # Format arguments
        args_text = ""
        for arg in key_arguments[:10]:  # Limit to 10 arguments
            direction_label = {"bullish": "看多", "bearish": "看空", "neutral": "中性"}.get(
                arg["direction"], "中性"
            )
            args_text += (
                f"- [{arg['agent_role']}] {direction_label}({arg['confidence']:.0%}): "
                f"{arg['key_point']}\n"
            )

        market_text = ""
        if market_context:
            market_text = f"\n当前市场环境: {json.dumps(market_context, ensure_ascii=False)[:300]}"

        return f"""你是一个投资决策汇总系统。以下是多位分析师Agent对{stock_code or '目标标的'}的讨论结果。

## 投票统计
- 看多: {vote_result['bull_count']} 票
- 看空: {vote_result['bear_count']} 票
- 中性: {vote_result['neutral_count']} 票

## 各Agent观点
{args_text}
{market_text}

请基于以上信息，输出JSON格式的决策汇总:
{{
    "signal": "buy/sell/hold之一",
    "confidence": 0.0到1.0的数字,
    "suggested_action": "具体操作建议（50字以内，如：逢低分批买入，设5%止损）",
    "dissent_points": ["主要分歧点1", "主要分歧点2"],
    "reasoning": "决策理由（100字以内）"
}}

只输出JSON，不要其他文字。"""

    def _parse_synthesis_response(self, response: str) -> dict[str, Any]:
        """Parse LLM synthesis response."""
        try:
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return {
                    "signal": data.get("signal", "hold"),
                    "confidence": float(data.get("confidence", 0.5)),
                    "suggested_action": data.get("suggested_action", ""),
                    "dissent_points": data.get("dissent_points", []),
                    "reasoning": data.get("reasoning", ""),
                }
        except Exception as e:
            logger.warning(f"Failed to parse LLM synthesis response: {e}")

        return {"signal": "hold", "confidence": 0.5, "suggested_action": "", "dissent_points": []}

    def _fallback_synthesis(
        self,
        vote_result: dict[str, int],
        key_arguments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Rule-based fallback when LLM is unavailable."""
        bull = vote_result["bull_count"]
        bear = vote_result["bear_count"]
        total = bull + bear + vote_result["neutral_count"]

        if total == 0:
            return {
                "signal": "hold",
                "confidence": 0.3,
                "suggested_action": "观望等待更多信息",
                "dissent_points": [],
            }

        if bull > bear and bull / total >= 0.6:
            signal = "buy"
            confidence = min(bull / total, 0.85)
            action = "可考虑适当买入，注意控制仓位"
        elif bear > bull and bear / total >= 0.6:
            signal = "sell"
            confidence = min(bear / total, 0.85)
            action = "建议减仓或观望，注意风险控制"
        else:
            signal = "hold"
            confidence = 0.4 + abs(bull - bear) / max(total, 1) * 0.2
            action = "多空分歧较大，建议持有观望"

        # Extract dissent points from minority opinions
        dissent_points = []
        minority_direction = "bearish" if bull > bear else "bullish"
        for arg in key_arguments:
            if arg["direction"] == minority_direction:
                dissent_points.append(arg["key_point"])
                if len(dissent_points) >= 3:
                    break

        return {
            "signal": signal,
            "confidence": round(confidence, 2),
            "suggested_action": action,
            "dissent_points": dissent_points,
        }

    def _determine_signal(
        self,
        vote_result: dict[str, Any],
        llm_result: dict[str, Any],
    ) -> tuple[str, float]:
        """Determine final signal combining rule votes and LLM output.

        Priority: LLM signal is used if confidence > 0.5, otherwise falls back to vote majority.
        """
        llm_signal = llm_result.get("signal", "hold")
        llm_confidence = llm_result.get("confidence", 0.5)

        # If LLM is confident, use its signal
        if llm_confidence >= 0.5:
            return llm_signal, llm_confidence

        # Otherwise, use vote majority
        bull = vote_result["bull_count"]
        bear = vote_result["bear_count"]
        total = bull + bear + vote_result["neutral_count"]

        if total == 0:
            return "hold", 0.3

        if bull > bear:
            return "buy", min(bull / total, 0.8)
        elif bear > bull:
            return "sell", min(bear / total, 0.8)
        else:
            return "hold", 0.4


# Singleton instance
_decision_summarizer: DecisionSummarizer | None = None


def get_decision_summarizer() -> DecisionSummarizer:
    """Get DecisionSummarizer singleton."""
    global _decision_summarizer
    if _decision_summarizer is None:
        _decision_summarizer = DecisionSummarizer()
    return _decision_summarizer
