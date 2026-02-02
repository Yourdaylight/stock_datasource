"""
Quant Researcher Agent

Agent responsible for quantitative research and factor-based analysis.
"""

import json
import logging
import uuid
from typing import Any, Dict, List

from ..models import AgentConfig, AgentRole, ArenaStrategy, CompetitionStage
from .base import ArenaAgentBase

logger = logging.getLogger(__name__)


class QuantResearcherAgent(ArenaAgentBase):
    """Agent that provides quantitative research insights.
    
    This agent specializes in factor analysis, statistical methods,
    and academic research-backed strategy optimization.
    """
    
    @property
    def role_name(self) -> str:
        return "Quant Researcher"
    
    def get_system_prompt(self) -> str:
        """Get system prompt for quant research."""
        return """你是一个专业的量化研究员。

你的职责是:
1. 进行因子分析和因子挖掘
2. 应用统计学方法优化策略
3. 参考学术研究成果
4. 进行回测数据的统计分析

在研究时，请关注:
- 因子有效性和因子衰减
- 策略的统计显著性
- 样本外测试结果
- 交易成本和滑点影响

你应该像一个严谨的学术研究者一样分析问题，用数据说话。
"""
    
    async def generate_strategy(
        self,
        symbols: List[str],
        market_context: Dict[str, Any] = None,
        round_id: str = "",
    ) -> ArenaStrategy:
        """Generate a factor-based strategy."""
        await self.think(
            "基于量化因子研究，生成因子驱动的交易策略...",
            round_id=round_id,
        )
        
        prompt = f"""作为量化研究员，请生成一个基于因子的交易策略。

目标股票: {', '.join(symbols[:10])}

请设计一个多因子策略，考虑:
1. 价值因子 (PB, PE, PCF)
2. 动量因子 (短期、中期、长期)
3. 质量因子 (ROE, 盈利稳定性)
4. 规模因子 (市值)
5. 波动率因子

输出一个因子驱动的策略，包括:
- 因子权重分配
- 因子组合方法
- 再平衡频率
- 风险预算
"""
        
        response = await self._call_llm(prompt)
        
        strategy = ArenaStrategy(
            id=str(uuid.uuid4())[:8],
            arena_id=self.arena_id,
            agent_id=self.agent_id,
            agent_role=self.role.value if hasattr(self.role, 'value') else str(self.role),
            name="多因子策略",
            description="基于学术研究的多因子量化策略",
            logic=response,
            rules={
                "factors": {
                    "value": {"weight": 0.25, "indicators": ["pb", "pe"]},
                    "momentum": {"weight": 0.25, "indicators": ["return_1m", "return_3m"]},
                    "quality": {"weight": 0.25, "indicators": ["roe", "profit_margin"]},
                    "volatility": {"weight": 0.25, "indicators": ["volatility_20d"]},
                },
                "rebalance_frequency": "monthly",
                "position_size": 0.1,
                "stop_loss": -0.1,
                "take_profit": 0.2,
            },
            symbols=symbols,
            stage=CompetitionStage.BACKTEST,
            discussion_rounds=[round_id] if round_id else [],
        )
        
        await self.conclude(
            f"多因子策略生成完成: {strategy.name}",
            round_id=round_id,
        )
        
        return strategy
    
    async def critique_strategy(
        self,
        strategy: ArenaStrategy,
        market_context: Dict[str, Any] = None,
        round_id: str = "",
    ) -> Dict[str, Any]:
        """Critique strategy from quantitative perspective."""
        await self.think(
            f"从量化研究角度评估策略: {strategy.name}",
            round_id=round_id,
        )
        
        prompt = f"""请从量化研究角度评估以下策略:

策略名称: {strategy.name}
策略逻辑: {strategy.logic}
交易规则: {json.dumps(strategy.rules, ensure_ascii=False, indent=2)}

请从以下角度进行量化评估:
1. 因子有效性分析
2. 策略统计显著性
3. 过拟合风险评估
4. 预期夏普比率
5. 换手率和交易成本影响
6. 样本外稳定性预测

输出JSON格式的量化评估报告:
{{
    "statistical_analysis": {{
        "expected_sharpe": 0.0-3.0,
        "expected_return": -0.5-1.0,
        "expected_volatility": 0.0-0.5,
        "turnover_rate": 0.0-5.0,
        "trading_cost_impact": 0.0-0.1
    }},
    "factor_assessment": {{
        "factor_validity": "high/medium/low",
        "factor_decay_risk": "high/medium/low",
        "factor_crowding": "high/medium/low"
    }},
    "overfitting_risk": "high/medium/low",
    "statistical_significance": 0.0-1.0,
    "strengths": ["量化优点"],
    "weaknesses": ["量化缺点"],
    "suggestions": ["优化建议"],
    "overall_score": 0-100
}}
"""
        
        response = await self._call_llm(prompt)
        
        try:
            critique = self._extract_json(response)
        except:
            critique = {
                "statistical_analysis": {
                    "expected_sharpe": 1.0,
                    "expected_return": 0.15,
                    "expected_volatility": 0.2,
                    "turnover_rate": 2.0,
                    "trading_cost_impact": 0.02,
                },
                "factor_assessment": {
                    "factor_validity": "medium",
                    "factor_decay_risk": "medium",
                    "factor_crowding": "medium",
                },
                "overfitting_risk": "medium",
                "statistical_significance": 0.5,
                "strengths": [],
                "weaknesses": [],
                "suggestions": [],
                "overall_score": 50,
                "raw_response": response,
            }
        
        critique.setdefault("statistical_analysis", {})
        critique.setdefault("factor_assessment", {})
        critique.setdefault("strengths", [])
        critique.setdefault("weaknesses", [])
        critique.setdefault("suggestions", [])
        critique.setdefault("overall_score", 50)
        
        stats = critique.get("statistical_analysis", {})
        factors = critique.get("factor_assessment", {})
        
        await self.argue(
            f"## 量化评估报告: {strategy.name}\n\n" +
            f"### 统计指标预测\n" +
            f"- 预期夏普比率: {stats.get('expected_sharpe', 'N/A'):.2f}\n" +
            f"- 预期年化收益: {stats.get('expected_return', 'N/A'):.1%}\n" +
            f"- 预期波动率: {stats.get('expected_volatility', 'N/A'):.1%}\n" +
            f"- 预期换手率: {stats.get('turnover_rate', 'N/A'):.1f}x/年\n" +
            f"- 交易成本影响: {stats.get('trading_cost_impact', 'N/A'):.1%}\n\n" +
            f"### 因子评估\n" +
            f"- 因子有效性: {factors.get('factor_validity', 'N/A')}\n" +
            f"- 因子衰减风险: {factors.get('factor_decay_risk', 'N/A')}\n" +
            f"- 因子拥挤度: {factors.get('factor_crowding', 'N/A')}\n\n" +
            f"### 风险评估\n" +
            f"- 过拟合风险: {critique.get('overfitting_risk', 'N/A')}\n" +
            f"- 统计显著性: {critique.get('statistical_significance', 'N/A'):.0%}\n\n" +
            f"### 优化建议\n" +
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
        """Refine strategy with quantitative improvements."""
        await self.think(
            "正在应用量化方法优化策略参数...",
            round_id=round_id,
        )
        
        # Extract quantitative suggestions
        quant_suggestions = []
        overfitting_warnings = []
        
        for critique in critiques:
            quant_suggestions.extend(critique.get("suggestions", []))
            if critique.get("overfitting_risk") == "high":
                overfitting_warnings.append("需要增加样本外验证")
            stats = critique.get("statistical_analysis", {})
            if stats.get("trading_cost_impact", 0) > 0.05:
                overfitting_warnings.append("需要降低换手率")
        
        prompt = f"""请应用量化方法优化策略:

原策略:
- 名称: {strategy.name}
- 规则: {json.dumps(strategy.rules, ensure_ascii=False)}

量化建议:
{chr(10).join(f'- {s}' for s in quant_suggestions)}

风险警告:
{chr(10).join(f'- {w}' for w in overfitting_warnings) if overfitting_warnings else '无'}

请优化因子权重和参数设置，降低过拟合风险。
"""
        
        response = await self._call_llm(prompt)
        
        refined_rules = dict(strategy.rules)
        # Add robustness measures
        refined_rules["out_of_sample_validation"] = True
        refined_rules["walk_forward_optimization"] = True
        refined_rules["rebalance_frequency"] = refined_rules.get("rebalance_frequency", "monthly")
        
        refined = ArenaStrategy(
            id=str(uuid.uuid4())[:8],
            arena_id=self.arena_id,
            agent_id=self.agent_id,
            agent_role=self.role.value if hasattr(self.role, 'value') else str(self.role),
            name=f"{strategy.name} (量化优化版)",
            description=strategy.description,
            logic=response,
            rules=refined_rules,
            symbols=strategy.symbols,
            stage=CompetitionStage.BACKTEST,
            refinement_history=strategy.refinement_history + [{
                "quant_researcher_id": self.agent_id,
                "robustness_measures_added": True,
            }],
            discussion_rounds=strategy.discussion_rounds + [round_id] if round_id else strategy.discussion_rounds,
        )
        
        await self.conclude(
            f"量化优化完成: {refined.name}\n已添加样本外验证和滚动优化",
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
