"""Signal Extraction Middleware - Agent after() 自动提取信号 Fact 写入 MemoryStore.

在 NewsAnalystAgent / ToplistAgent 执行完成后，自动将关键信号结论
提取为 market_signal / capital_flow 类型的 Fact 写入 MemoryStore.

仅提取高置信度信号(impact_level=high 或 confidence≥0.8)，避免噪声.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from stock_datasource.modules.memory.models import FactItem
from stock_datasource.modules.memory.store import MemoryStore, get_memory_store

from .base import AgentContext, AgentResponse, BaseMiddleware

logger = logging.getLogger(__name__)

# 高置信度阈值
_HIGH_CONFIDENCE_THRESHOLD = 0.8


class SignalExtractionMiddleware(BaseMiddleware):
    """从Agent响应中提取信号并写入MemoryStore.

    工作方式:
    1. after() 检查Agent名称是否为信号相关Agent
    2. 从响应内容中提取股票代码和信号结论
    3. 仅在 impact_level=high 或 confidence≥0.8 时创建Fact
    4. 写入 MemoryStore 的 facts 命名空间
    """

    # 需要提取信号的Agent
    SIGNAL_AGENTS = {"NewsAnalystAgent", "toplist_agent", "news_analyst_agent"}

    def __init__(self, store: MemoryStore | None = None):
        super().__init__()
        self._store = store or get_memory_store()

    async def before(self, context: AgentContext) -> AgentContext:
        """No-op for signal extraction."""
        return context

    async def after(
        self, context: AgentContext, response: AgentResponse
    ) -> AgentResponse:
        """Extract signal facts from agent response."""
        if not self.enabled:
            return response

        agent_name = response.metadata.get("agent", "")
        if agent_name not in self.SIGNAL_AGENTS:
            return response

        context.trace(self.name, "start")

        try:
            facts = self._extract_signal_facts(agent_name, response)
            for fact in facts:
                fact_id = f"sig_{int(time.time() * 1000)}_{hash(fact.content) % 10000}"
                self._store.put_fact(context.user_id, fact_id, fact)
                logger.info(
                    "Signal fact created: [%s] %s",
                    fact.category,
                    fact.content[:80],
                )

            context.trace(self.name, f"extracted_{len(facts)}")
        except Exception as e:
            logger.warning("Signal extraction failed: %s", e)
            context.trace(self.name, "failed")

        return response

    def _extract_signal_facts(
        self, agent_name: str, response: AgentResponse
    ) -> list[FactItem]:
        """从Agent响应中提取信号Facts."""
        content = response.content
        if not content:
            return []

        facts: list[FactItem] = []

        # 提取涉及的股票代码
        ts_codes = re.findall(r"\d{6}\.[A-Z]{2}", content)
        if not ts_codes:
            return []

        if agent_name in ("NewsAnalystAgent", "news_analyst_agent"):
            facts.extend(self._extract_news_facts(content, ts_codes))
        elif agent_name == "toplist_agent":
            facts.extend(self._extract_capital_facts(content, ts_codes))

        return facts

    def _extract_news_facts(
        self, content: str, ts_codes: list[str]
    ) -> list[FactItem]:
        """从新闻分析结果中提取 market_signal Facts."""
        facts = []

        # 检测高impact信号
        high_impact_indicators = [
            "重大", "重要", "关键", "突破", "暴涨", "暴跌",
            "利好", "利空", "重大利好", "重大利空",
            "impact_level.*high", "影响程度.*重大",
        ]
        is_high_impact = any(
            re.search(pattern, content, re.IGNORECASE)
            for pattern in high_impact_indicators
        )

        # 检测情绪方向
        sentiment = "neutral"
        if re.search(r"偏利好|利好|positive|看涨|上涨", content):
            sentiment = "positive"
        elif re.search(r"偏利空|利空|negative|看跌|下跌", content, re.IGNORECASE):
            sentiment = "negative"

        if is_high_impact or sentiment != "neutral":
            # 为每个股票代码创建Fact
            seen_codes = set()
            for ts_code in ts_codes:
                if ts_code in seen_codes:
                    continue
                seen_codes.add(ts_code)

                # 提取与该股票相关的关键句子
                relevant_sentences = self._extract_relevant_sentences(
                    content, ts_code, max_sentences=3
                )
                if not relevant_sentences:
                    continue

                fact_content = f"{ts_code} 消息面信号({sentiment}): {'; '.join(relevant_sentences)}"
                confidence = 0.9 if is_high_impact else 0.8

                facts.append(
                    FactItem(
                        content=fact_content[:200],  # 限制长度
                        category="market_signal",
                        confidence=confidence,
                        source="NewsAnalystAgent",
                    )
                )

        return facts

    def _extract_capital_facts(
        self, content: str, ts_codes: list[str]
    ) -> list[FactItem]:
        """从龙虎榜分析结果中提取 capital_flow Facts."""
        facts = []

        # 检测资金流向方向
        flow_direction = "neutral"
        if re.search(r"净买入|净流入|资金流入|买入为主", content):
            flow_direction = "inflow"
        elif re.search(r"净卖出|净流出|资金流出|卖出为主", content):
            flow_direction = "outflow"

        # 检测高置信度信号
        high_confidence_indicators = [
            "机构.*抱团", "游资.*集中", "集中度.*高",
            "异动.*严重", "大幅.*流入", "大幅.*流出",
            "北向.*大幅", r"HHI.*0\.[3-9]",
        ]
        is_high_confidence = any(
            re.search(pattern, content)
            for pattern in high_confidence_indicators
        )

        if flow_direction != "neutral" or is_high_confidence:
            seen_codes = set()
            for ts_code in ts_codes:
                if ts_code in seen_codes:
                    continue
                seen_codes.add(ts_code)

                relevant_sentences = self._extract_relevant_sentences(
                    content, ts_code, max_sentences=3
                )
                if not relevant_sentences:
                    continue

                direction_label = {
                    "inflow": "资金流入",
                    "outflow": "资金流出",
                    "neutral": "资金面中性",
                }.get(flow_direction, "资金面")

                fact_content = f"{ts_code} 资金面({direction_label}): {'; '.join(relevant_sentences)}"
                confidence = 0.9 if is_high_confidence else 0.8

                facts.append(
                    FactItem(
                        content=fact_content[:200],
                        category="capital_flow",
                        confidence=confidence,
                        source="ToplistAgent",
                    )
                )

        return facts

    @staticmethod
    def _extract_relevant_sentences(
        content: str, ts_code: str, max_sentences: int = 3
    ) -> list[str]:
        """提取与特定股票代码相关的句子."""
        sentences = []
        # Split by Chinese/English sentence endings
        parts = re.split(r"[。\n]", content)

        for part in parts:
            part = part.strip()
            if not part or ts_code not in part:
                continue
            # Clean up
            if len(part) > 80:
                part = part[:80] + "..."
            sentences.append(part)
            if len(sentences) >= max_sentences:
                break

        return sentences
