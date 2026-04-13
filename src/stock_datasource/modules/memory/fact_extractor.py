"""FactExtractor with 3-layer signal detection.

Layer 1: Regex quick signal (financial scenario keywords)
Layer 2: LLM intent classification (lightweight, only when Layer 1 misses)
Layer 3: FactExtractor deep extraction (with correction/reinforcement hints)
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from .models import FactCategory, FactItem, SignalResult, SignalType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Layer 1: Regex signal patterns (financial scenario)
# ---------------------------------------------------------------------------

# Correction signals
_CORRECTION_PATTERNS = [
    r"不对", r"错了", r"不是这样", r"数据有误", r"应该是", r"我说的是",
    r"不准确", r"搞错了", r"弄错了", r"不是这个", r"反了",
    r"不正确", r"有误", r"算错了", r"看错了",
    r"that'?s wrong", r"incorrect", r"not right", r"mistake",
    r"不是.*而是", r"不是.*是",
]

# Reinforcement signals
_REINFORCEMENT_PATTERNS = [
    r"没错", r"就是这个", r"数据准确", r"分析到位", r"说对了",
    r"完全正确", r"对的", r"确实", r"正是", r"对的",
    r"到位", r"准确", r"正确",
    r"exactly", r"correct", r"right", r"spot on", r"accurate",
    r"就是.*这样", r"没错.*就是这样",
]

# Negative/uncertainty words that may trigger Layer 2
_NEGATION_WORDS = [
    "不", "没", "非", "错", "误", "反", "但是", "可是", "然而", "不过",
    "应该", "实际", "真实", "正确",
]


class RegexSignalDetector:
    """Layer 1: Fast regex-based signal detection."""

    def __init__(self):
        self._correction_re = [re.compile(p, re.IGNORECASE) for p in _CORRECTION_PATTERNS]
        self._reinforcement_re = [re.compile(p, re.IGNORECASE) for p in _REINFORCEMENT_PATTERNS]

    def detect(self, message: str) -> SignalResult:
        """Detect correction/reinforcement signal via regex.

        Returns SignalResult with detected_by="regex" if matched, else neutral.
        """
        for pattern in self._correction_re:
            if pattern.search(message):
                return SignalResult(
                    signal="correction",
                    detected_by="regex",
                )

        for pattern in self._reinforcement_re:
            if pattern.search(message):
                return SignalResult(
                    signal="reinforcement",
                    detected_by="regex",
                )

        return SignalResult(signal="neutral", detected_by="none")

    def should_trigger_layer2(self, message: str) -> bool:
        """Check if Layer 2 LLM intent classification should be triggered.

        Triggered when regex didn't match but message contains negation/uncertainty words.
        """
        return any(word in message for word in _NEGATION_WORDS)


# ---------------------------------------------------------------------------
# Layer 2: LLM intent classification
# ---------------------------------------------------------------------------

_INTENT_CLASSIFICATION_PROMPT = """判断用户最新消息是否在修正或强化之前的分析结论。

用户消息: {message}

信号类型:
- correction: 用户指出错误或不准确之处
- reinforcement: 用户确认分析正确
- neutral: 普通对话，无修正/强化意图

仅输出JSON: {{"signal": "correction|reinforcement|neutral", "target_fact": "...", "correct_value": "..."}}
target_fact: 涉及的事实主题（如有）
correct_value: 用户认为正确的理解（仅correction时填写）"""


class LLMIntentClassifier:
    """Layer 2: Lightweight LLM intent classification."""

    def __init__(self, model=None):
        self._model = model

    def _get_model(self):
        if self._model is None:
            from stock_datasource.agents.base_agent import get_langchain_model
            self._model = get_langchain_model()
        return self._model

    async def classify(self, message: str) -> SignalResult:
        """Classify user message intent via LLM.

        Returns SignalResult with detected_by="llm_intent".
        """
        try:
            model = self._get_model()
            prompt = _INTENT_CLASSIFICATION_PROMPT.format(message=message)
            response = await model.ainvoke([{"role": "user", "content": prompt}])

            content = response.content if hasattr(response, "content") else str(response)
            # Parse JSON from response
            parsed = _extract_json_from_text(content)
            if not parsed:
                return SignalResult(signal="neutral", detected_by="llm_intent")

            signal_str = parsed.get("signal", "neutral")
            if signal_str not in ("correction", "reinforcement", "neutral"):
                signal_str = "neutral"

            return SignalResult(
                signal=signal_str,
                target_fact=parsed.get("target_fact", ""),
                correct_value=parsed.get("correct_value", ""),
                detected_by="llm_intent",
            )
        except Exception as e:
            logger.warning("LLM intent classification failed: %s", e)
            return SignalResult(signal="neutral", detected_by="llm_intent")


# ---------------------------------------------------------------------------
# Layer 3: FactExtractor deep extraction
# ---------------------------------------------------------------------------

_FACT_EXTRACTION_PROMPT = """从以下对话中提取关于用户的事实。只提取与投资相关的事实：
- 风险偏好（保守/稳健/激进）
- 行业偏好（看好/看空哪些行业）
- 个股观点（关注/持有/回避哪些股票）
- 交易风格（短线/中线/长线）
- 分析结论（对某只股票的判断）

对话内容:
{conversation}

{correction_hint}

输出JSON数组: [{{"content": "...", "category": "risk_preference|sector_focus|stock_opinion|trading_style|conclusion", "confidence": 0.7}}]
如果无可提取事实，返回空数组 []"""


class FactExtractor:
    """Layer 3: Deep fact extraction from conversation."""

    def __init__(self, model=None):
        self._model = model
        self._regex_detector = RegexSignalDetector()
        self._intent_classifier = LLMIntentClassifier(model)

    def _get_model(self):
        if self._model is None:
            from stock_datasource.agents.base_agent import get_langchain_model
            self._model = get_langchain_model()
        return self._model

    async def detect_signal(self, user_message: str) -> SignalResult:
        """Run 3-layer signal detection on user message.

        Layer 1: Regex quick scan
        Layer 2: LLM intent (only if Layer 1 missed and negation words present)
        """
        # Layer 1: Regex
        result = self._regex_detector.detect(user_message)
        if result.signal != "neutral":
            return result

        # Layer 2: LLM intent (conditional)
        if self._regex_detector.should_trigger_layer2(user_message):
            result = await self._intent_classifier.classify(user_message)
            if result.signal != "neutral":
                return result

        return SignalResult(signal="neutral", detected_by="none")

    async def extract_facts(
        self,
        user_message: str,
        agent_response: str,
        signal: Optional[SignalResult] = None,
        source: str = "",
    ) -> List[FactItem]:
        """Extract facts from a conversation turn.

        Args:
            user_message: The user's message.
            agent_response: The agent's response.
            signal: Pre-detected signal from detect_signal(). If None, will detect.
            source: Source identifier (agent name, session, etc.).

        Returns:
            List of extracted FactItem objects.
        """
        if signal is None:
            signal = await self.detect_signal(user_message)

        # Build correction hint
        correction_hint = ""
        if signal.is_correction:
            correction_hint = "注意：用户在纠正之前的错误，提取的事实的confidence应设为0.95。"
            if signal.correct_value:
                correction_hint += f"\n用户认为正确的理解: {signal.correct_value}"
        elif signal.is_reinforcement:
            correction_hint = "注意：用户确认了之前的分析，这次提取的事实是对现有事实的强化。"

        conversation = f"用户: {user_message}\n助手: {agent_response}"

        try:
            model = self._get_model()
            prompt = _FACT_EXTRACTION_PROMPT.format(
                conversation=conversation,
                correction_hint=correction_hint,
            )
            response = await model.ainvoke([{"role": "user", "content": prompt}])

            content = response.content if hasattr(response, "content") else str(response)
            parsed = _extract_json_from_text(content)

            if not parsed or not isinstance(parsed, list):
                return []

            facts = []
            for item in parsed:
                if not isinstance(item, dict) or "content" not in item:
                    continue
                category = item.get("category", "conclusion")
                if category not in ("risk_preference", "sector_focus", "stock_opinion", "trading_style", "conclusion"):
                    category = "conclusion"

                confidence = item.get("confidence", 0.7)
                # Override confidence for corrections
                if signal.is_correction:
                    confidence = max(confidence, 0.95)
                confidence = max(0.0, min(1.0, confidence))

                facts.append(FactItem(
                    content=item["content"],
                    category=category,
                    confidence=confidence,
                    source=source,
                ))

            return facts

        except Exception as e:
            logger.warning("Fact extraction failed: %s", e)
            return []


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _extract_json_from_text(text: str) -> Optional[Any]:
    """Extract JSON from text that may contain extra content."""
    if not text:
        return None

    # Try direct parse
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try finding JSON array or object
    for pattern in [r'\[.*\]', r'\{.*\}']:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                continue

    return None
