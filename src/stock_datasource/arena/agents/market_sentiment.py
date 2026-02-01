"""
Market Sentiment Agent

Agent responsible for analyzing market sentiment and news impact.
"""

import json
import logging
import uuid
from typing import Any, Dict, List

from ..models import AgentConfig, AgentRole, ArenaStrategy, CompetitionStage
from .base import ArenaAgentBase

logger = logging.getLogger(__name__)


class MarketSentimentAgent(ArenaAgentBase):
    """Agent that analyzes market sentiment.
    
    This agent focuses on sentiment analysis from news, social media,
    and market indicators to provide market mood assessment.
    """
    
    @property
    def role_name(self) -> str:
        return "Market Sentiment Analyst"
    
    def get_system_prompt(self) -> str:
        """Get system prompt for sentiment analysis."""
        return """你是一个专业的市场情绪分析师。

你的职责是:
1. 分析市场整体情绪
2. 评估新闻对市场的影响
3. 监测投资者行为指标
4. 识别市场拐点信号

在分析情绪时，请关注:
- 市场成交量和资金流向
- 新闻舆情和热点话题
- 北向资金动向
- 涨跌比和情绪指标

你应该像一个敏锐的市场观察者一样捕捉情绪变化。
"""
    
    async def generate_strategy(
        self,
        symbols: List[str],
        market_context: Dict[str, Any] = None,
        round_id: str = "",
    ) -> ArenaStrategy:
        """Generate a sentiment-driven strategy."""
        await self.think(
            "基于市场情绪分析，生成情绪驱动的交易策略...",
            round_id=round_id,
        )
        
        context = market_context or self._market_context
        sentiment_data = context.get("sentiment", {}) if context else {}
        
        prompt = f"""作为市场情绪分析师，请生成一个基于市场情绪的交易策略。

目标股票: {', '.join(symbols[:10])}
当前市场情绪数据: {json.dumps(sentiment_data, ensure_ascii=False) if sentiment_data else '无'}

请基于情绪指标生成策略:
1. 情绪拐点识别
2. 恐惧贪婪指数运用
3. 资金流向跟踪
4. 舆情热度监测

输出一个情绪驱动的策略，包括名称、描述、逻辑和交易规则。
"""
        
        response = await self._call_llm(prompt)
        
        strategy = ArenaStrategy(
            id=str(uuid.uuid4())[:8],
            arena_id=self.arena_id,
            agent_id=self.agent_id,
            agent_role=self.role.value if hasattr(self.role, 'value') else str(self.role),
            name="情绪驱动策略",
            description="基于市场情绪指标的交易策略",
            logic=response,
            rules={
                "entry_conditions": [
                    {"indicator": "sentiment_score", "operator": ">", "value": 60},
                    {"indicator": "north_flow", "operator": ">", "value": 0},
                ],
                "exit_conditions": [
                    {"indicator": "sentiment_score", "operator": "<", "value": 40},
                ],
                "position_size": 0.15,
                "stop_loss": -0.06,
                "take_profit": 0.12,
            },
            symbols=symbols,
            stage=CompetitionStage.BACKTEST,
            discussion_rounds=[round_id] if round_id else [],
        )
        
        await self.conclude(
            f"情绪策略生成完成: {strategy.name}",
            round_id=round_id,
        )
        
        return strategy
    
    async def critique_strategy(
        self,
        strategy: ArenaStrategy,
        market_context: Dict[str, Any] = None,
        round_id: str = "",
    ) -> Dict[str, Any]:
        """Critique strategy from sentiment perspective."""
        await self.think(
            f"从市场情绪角度评估策略: {strategy.name}",
            round_id=round_id,
        )
        
        context = market_context or self._market_context
        
        prompt = f"""请从市场情绪角度评估以下策略:

策略名称: {strategy.name}
策略逻辑: {strategy.logic}
交易规则: {json.dumps(strategy.rules, ensure_ascii=False, indent=2)}

当前市场情绪: {json.dumps(context.get('sentiment', {}), ensure_ascii=False) if context else '无数据'}

请评估:
1. 策略与当前市场情绪是否匹配
2. 策略是否考虑了情绪因素
3. 在极端情绪下策略表现预测
4. 情绪相关的改进建议

输出JSON格式评估:
{{
    "sentiment_alignment": "aligned/neutral/misaligned",
    "current_market_mood": "bullish/bearish/neutral",
    "mood_stability": "stable/volatile",
    "strengths": ["情绪相关优点"],
    "weaknesses": ["情绪相关缺点"],
    "suggestions": ["情绪相关建议"],
    "extreme_scenario_assessment": {{
        "panic_selling": "策略在恐慌抛售时的表现",
        "fomo_buying": "策略在FOMO行情时的表现"
    }},
    "overall_score": 0-100
}}
"""
        
        response = await self._call_llm(prompt)
        
        try:
            critique = self._extract_json(response)
        except:
            critique = {
                "sentiment_alignment": "neutral",
                "current_market_mood": "neutral",
                "mood_stability": "stable",
                "strengths": [],
                "weaknesses": [],
                "suggestions": [],
                "extreme_scenario_assessment": {},
                "overall_score": 50,
                "raw_response": response,
            }
        
        critique.setdefault("sentiment_alignment", "neutral")
        critique.setdefault("strengths", [])
        critique.setdefault("weaknesses", [])
        critique.setdefault("suggestions", [])
        critique.setdefault("overall_score", 50)
        
        await self.argue(
            f"## 情绪视角评估: {strategy.name}\n\n" +
            f"**情绪匹配度**: {critique['sentiment_alignment']}\n" +
            f"**当前市场情绪**: {critique.get('current_market_mood', 'N/A')}\n" +
            f"**情绪稳定性**: {critique.get('mood_stability', 'N/A')}\n\n" +
            f"### 情绪相关优点\n" +
            "\n".join(f"- {s}" for s in critique['strengths']) + "\n\n" +
            f"### 情绪相关风险\n" +
            "\n".join(f"- {w}" for w in critique['weaknesses']) + "\n\n" +
            f"### 建议\n" +
            "\n".join(f"- {s}" for s in critique['suggestions']),
            round_id=round_id,
            target_strategy_id=strategy.id,
        )
        
        return critique
    
    async def refine_strategy(
        self,
        strategy: ArenaStrategy,
        critiques: List[Dict[str, Any]],
        round_id: str = "",
    ) -> ArenaStrategy:
        """Refine strategy with sentiment considerations."""
        await self.think(
            "正在将情绪因素整合到策略中...",
            round_id=round_id,
        )
        
        sentiment_suggestions = []
        for critique in critiques:
            if "sentiment" in str(critique).lower() or critique.get("sentiment_alignment"):
                sentiment_suggestions.extend(critique.get("suggestions", []))
        
        prompt = f"""请优化策略的情绪适应性:

原策略:
- 名称: {strategy.name}
- 规则: {json.dumps(strategy.rules, ensure_ascii=False)}

情绪相关建议:
{chr(10).join(f'- {s}' for s in sentiment_suggestions) if sentiment_suggestions else '- 加入情绪指标作为辅助判断'}

请在策略中加入情绪过滤条件。
"""
        
        response = await self._call_llm(prompt)
        
        refined_rules = dict(strategy.rules)
        # Add sentiment filter
        entry_conditions = refined_rules.get("entry_conditions", [])
        if not any("sentiment" in str(c).lower() for c in entry_conditions):
            entry_conditions.append({
                "indicator": "market_sentiment",
                "operator": "!=",
                "value": "extreme_fear"
            })
        refined_rules["entry_conditions"] = entry_conditions
        
        refined = ArenaStrategy(
            id=str(uuid.uuid4())[:8],
            arena_id=self.arena_id,
            agent_id=self.agent_id,
            agent_role=self.role.value if hasattr(self.role, 'value') else str(self.role),
            name=f"{strategy.name} (情绪优化版)",
            description=strategy.description,
            logic=response,
            rules=refined_rules,
            symbols=strategy.symbols,
            stage=CompetitionStage.BACKTEST,
            refinement_history=strategy.refinement_history + [{
                "sentiment_analyst_id": self.agent_id,
                "sentiment_filters_added": True,
            }],
            discussion_rounds=strategy.discussion_rounds + [round_id] if round_id else strategy.discussion_rounds,
        )
        
        await self.conclude(
            f"情绪优化完成: {refined.name}\n已添加市场情绪过滤条件",
            round_id=round_id,
        )
        
        return refined
    
    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract JSON from text."""
        import re
        
        start = text.find('{')
        if start != -1:
            depth = 0
            end = start
            for i, char in enumerate(text[start:], start):
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
        
        raise ValueError("No valid JSON found in text")
