"""
Strategy Generator Agent

Agent responsible for generating trading strategies based on market analysis.
"""

import json
import logging
import uuid
from typing import Any, Dict, List

from ..models import AgentConfig, AgentRole, ArenaStrategy, CompetitionStage
from .base import ArenaAgentBase

logger = logging.getLogger(__name__)


class StrategyGeneratorAgent(ArenaAgentBase):
    """Agent that generates trading strategies.
    
    This agent analyzes market conditions and generates actionable trading
    strategies with clear entry/exit rules.
    """
    
    @property
    def role_name(self) -> str:
        return "Strategy Generator"
    
    def get_system_prompt(self) -> str:
        """Get system prompt for strategy generation."""
        personality_desc = f"Your investment style is {self.personality}." if self.personality else ""
        focus_desc = f"You focus on: {', '.join(self.focus_areas)}." if self.focus_areas else ""
        
        return f"""你是一个专业的量化交易策略生成器。{personality_desc} {focus_desc}

你的职责是:
1. 分析市场环境和股票数据
2. 制定清晰的交易策略
3. 定义明确的入场和出场规则
4. 解释策略的逻辑和预期收益

在生成策略时，请确保:
- 策略逻辑清晰可执行
- 风险控制措施到位
- 考虑当前市场环境
- 给出明确的参数和阈值

输出格式要求:
- 使用结构化的JSON格式输出策略规则
- 用自然语言解释策略逻辑
- 列出潜在风险和应对措施
"""
    
    async def generate_strategy(
        self,
        symbols: List[str],
        market_context: Dict[str, Any] = None,
        round_id: str = "",
    ) -> ArenaStrategy:
        """Generate a trading strategy.
        
        Args:
            symbols: Stock symbols to consider
            market_context: Current market data and analysis
            round_id: Current discussion round ID
            
        Returns:
            Generated ArenaStrategy
        """
        context = market_context or self._market_context
        
        # Start thinking
        await self.think(
            f"开始分析市场环境和{len(symbols)}只股票...",
            round_id=round_id,
        )
        
        # Build prompt
        prompt = self._build_strategy_prompt(symbols, context)
        
        # Call LLM with streaming
        await self.think("正在生成策略...", round_id=round_id)
        response = await self._call_llm(prompt)
        
        # Parse response
        strategy = self._parse_strategy_response(response, symbols, round_id)
        
        # Publish conclusion
        await self.conclude(
            f"策略生成完成: {strategy.name}\n{strategy.description}",
            round_id=round_id,
            metadata={"strategy_id": strategy.id},
        )
        
        return strategy
    
    async def critique_strategy(
        self,
        strategy: ArenaStrategy,
        market_context: Dict[str, Any] = None,
        round_id: str = "",
    ) -> Dict[str, Any]:
        """Critique another agent's strategy."""
        await self.think(
            f"正在评估策略: {strategy.name}",
            round_id=round_id,
        )
        
        prompt = f"""请评估以下交易策略:

策略名称: {strategy.name}
策略描述: {strategy.description}
策略逻辑: {strategy.logic}
交易规则: {json.dumps(strategy.rules, ensure_ascii=False, indent=2)}

请从以下角度进行评估:
1. 策略逻辑是否合理
2. 参数设置是否恰当
3. 风险控制是否充分
4. 市场适应性如何

请输出JSON格式的评估结果:
{{
    "strengths": ["优点1", "优点2"],
    "weaknesses": ["缺点1", "缺点2"],
    "suggestions": ["建议1", "建议2"],
    "overall_score": 0-100
}}
"""
        
        response = await self._call_llm(prompt)
        
        try:
            # Try to extract JSON from response
            critique = self._extract_json(response)
        except:
            critique = {
                "strengths": [],
                "weaknesses": [],
                "suggestions": [],
                "overall_score": 50,
                "raw_response": response,
            }
        
        await self.argue(
            f"对策略 {strategy.name} 的评估:\n" +
            f"优点: {', '.join(critique.get('strengths', []))}\n" +
            f"缺点: {', '.join(critique.get('weaknesses', []))}\n" +
            f"评分: {critique.get('overall_score', 'N/A')}",
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
        """Refine strategy based on critiques."""
        await self.think(
            f"正在根据{len(critiques)}条评论优化策略...",
            round_id=round_id,
        )
        
        # Summarize critiques
        all_suggestions = []
        for critique in critiques:
            all_suggestions.extend(critique.get("suggestions", []))
        
        prompt = f"""请根据以下反馈优化交易策略:

原策略:
- 名称: {strategy.name}
- 描述: {strategy.description}
- 逻辑: {strategy.logic}
- 规则: {json.dumps(strategy.rules, ensure_ascii=False, indent=2)}

收到的建议:
{chr(10).join(f'- {s}' for s in all_suggestions)}

请输出优化后的策略，格式同原策略。
"""
        
        response = await self._call_llm(prompt)
        
        # Create refined strategy
        refined = ArenaStrategy(
            id=str(uuid.uuid4())[:8],
            arena_id=self.arena_id,
            agent_id=self.agent_id,
            agent_role=self.role.value,
            name=f"{strategy.name} (优化版)",
            description=strategy.description,
            logic=response,
            rules=strategy.rules,  # Would parse from response in production
            symbols=strategy.symbols,
            stage=CompetitionStage.BACKTEST,
        )
        
        # Track refinement history
        refined.refinement_history = strategy.refinement_history + [{
            "original_id": strategy.id,
            "critiques_count": len(critiques),
            "suggestions": all_suggestions,
        }]
        refined.discussion_rounds = strategy.discussion_rounds + [round_id] if round_id else strategy.discussion_rounds
        
        await self.conclude(
            f"策略优化完成: {refined.name}",
            round_id=round_id,
            metadata={"strategy_id": refined.id, "original_id": strategy.id},
        )
        
        return refined
    
    def _build_strategy_prompt(self, symbols: List[str], context: Dict[str, Any]) -> str:
        """Build the strategy generation prompt."""
        symbols_str = ", ".join(symbols[:10])
        if len(symbols) > 10:
            symbols_str += f" 等{len(symbols)}只股票"
        
        context_str = ""
        if context:
            if "market_summary" in context:
                context_str += f"\n市场概况: {context['market_summary']}"
            if "technical" in context:
                context_str += f"\n技术面: {json.dumps(context['technical'], ensure_ascii=False)}"
            if "sentiment" in context:
                context_str += f"\n市场情绪: {context['sentiment']}"
        
        return f"""请为以下股票生成一个量化交易策略:

目标股票: {symbols_str}
{context_str}

请生成一个完整的交易策略，包括:
1. 策略名称
2. 策略描述（一句话概括）
3. 详细的策略逻辑
4. 具体的交易规则（JSON格式）

交易规则JSON格式示例:
{{
    "entry_conditions": [
        {{"indicator": "MA5", "operator": ">", "value": "MA20"}},
        {{"indicator": "volume", "operator": ">", "value": "avg_volume_20d"}}
    ],
    "exit_conditions": [
        {{"indicator": "MA5", "operator": "<", "value": "MA10"}},
        {{"indicator": "pct_change", "operator": "<", "value": -0.05}}
    ],
    "position_size": 0.2,
    "stop_loss": -0.08,
    "take_profit": 0.15
}}
"""
    
    def _parse_strategy_response(
        self,
        response: str,
        symbols: List[str],
        round_id: str,
    ) -> ArenaStrategy:
        """Parse LLM response into ArenaStrategy."""
        # Try to extract JSON rules
        try:
            rules = self._extract_json(response)
        except:
            rules = {
                "entry_conditions": [],
                "exit_conditions": [],
                "position_size": 0.2,
                "stop_loss": -0.08,
                "take_profit": 0.15,
            }
        
        # Extract strategy name and description from response
        lines = response.split("\n")
        name = "AI生成策略"
        description = ""
        
        for line in lines:
            line = line.strip()
            if "策略名称" in line or "名称:" in line:
                name = line.split(":")[-1].strip() if ":" in line else "AI生成策略"
            elif "策略描述" in line or "描述:" in line:
                description = line.split(":")[-1].strip() if ":" in line else ""
        
        if not name or name == "AI生成策略":
            name = f"{self.personality.capitalize()} 策略 #{uuid.uuid4().hex[:4]}"
        
        return ArenaStrategy(
            id=str(uuid.uuid4())[:8],
            arena_id=self.arena_id,
            agent_id=self.agent_id,
            agent_role=self.role.value if hasattr(self.role, 'value') else str(self.role),
            name=name,
            description=description or f"由{self.role_name}生成的交易策略",
            logic=response,
            rules=rules,
            symbols=symbols,
            stage=CompetitionStage.BACKTEST,
            discussion_rounds=[round_id] if round_id else [],
        )
    
    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract JSON from text."""
        import re
        
        # Try to find JSON block
        json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # Try to find JSON in code blocks
        code_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if code_match:
            try:
                return json.loads(code_match.group(1))
            except json.JSONDecodeError:
                pass
        
        raise ValueError("No valid JSON found in text")
