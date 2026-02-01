"""
Risk Analyst Agent

Agent responsible for analyzing risk exposure and suggesting risk management measures.
"""

import json
import logging
import uuid
from typing import Any, Dict, List

from ..models import AgentConfig, AgentRole, ArenaStrategy, CompetitionStage
from .base import ArenaAgentBase

logger = logging.getLogger(__name__)


class RiskAnalystAgent(ArenaAgentBase):
    """Agent that analyzes risk exposure in trading strategies.
    
    This agent specializes in identifying and quantifying risks,
    and suggesting appropriate risk management measures.
    """
    
    @property
    def role_name(self) -> str:
        return "Risk Analyst"
    
    def get_system_prompt(self) -> str:
        """Get system prompt for risk analysis."""
        return """你是一个专业的量化风险分析师。

你的职责是:
1. 分析交易策略的风险敞口
2. 识别潜在的系统性风险
3. 评估最大回撤和VaR
4. 提出风险管理建议

在分析风险时，请确保:
- 量化风险指标（如VaR、最大回撤等）
- 考虑尾部风险和黑天鹅事件
- 分析策略在极端市场条件下的表现
- 给出具体的风险控制参数建议

你应该像一个谨慎的风险管理官一样思考问题。
"""
    
    async def generate_strategy(
        self,
        symbols: List[str],
        market_context: Dict[str, Any] = None,
        round_id: str = "",
    ) -> ArenaStrategy:
        """Generate a low-risk focused strategy."""
        await self.think(
            "从风险管理角度出发，生成一个以控制风险为核心的策略...",
            round_id=round_id,
        )
        
        prompt = f"""作为风险分析师，请生成一个以风险控制为核心的交易策略。

目标股票: {', '.join(symbols[:10])}

请特别关注:
1. 严格的止损机制
2. 分散化投资
3. 仓位控制
4. 回撤管理

输出一个风险优先的策略，包括名称、描述、逻辑和交易规则。
"""
        
        response = await self._call_llm(prompt)
        
        strategy = ArenaStrategy(
            id=str(uuid.uuid4())[:8],
            arena_id=self.arena_id,
            agent_id=self.agent_id,
            agent_role=self.role.value if hasattr(self.role, 'value') else str(self.role),
            name="低风险策略",
            description="以风险控制为核心的保守型策略",
            logic=response,
            rules={
                "entry_conditions": [],
                "exit_conditions": [],
                "position_size": 0.05,
                "stop_loss": -0.03,
                "take_profit": 0.08,
                "max_portfolio_risk": 0.1,
            },
            symbols=symbols,
            stage=CompetitionStage.BACKTEST,
            discussion_rounds=[round_id] if round_id else [],
        )
        
        await self.conclude(
            f"风险导向策略生成完成: {strategy.name}",
            round_id=round_id,
        )
        
        return strategy
    
    async def critique_strategy(
        self,
        strategy: ArenaStrategy,
        market_context: Dict[str, Any] = None,
        round_id: str = "",
    ) -> Dict[str, Any]:
        """Analyze risk exposure in a strategy."""
        await self.think(
            f"开始分析策略 {strategy.name} 的风险敞口...",
            round_id=round_id,
        )
        
        prompt = f"""请从风险分析角度评估以下交易策略:

策略名称: {strategy.name}
策略逻辑: {strategy.logic}
交易规则: {json.dumps(strategy.rules, ensure_ascii=False, indent=2)}

请分析以下风险指标:
1. 预估最大回撤
2. VaR (Value at Risk) 估计
3. 尾部风险评估
4. 流动性风险
5. 集中度风险
6. 极端市场表现预测

请输出详细的风险分析报告（JSON格式）:
{{
    "risk_metrics": {{
        "estimated_max_drawdown": 0.0-1.0,
        "var_95": 0.0-1.0,
        "var_99": 0.0-1.0,
        "tail_risk_score": 0-100,
        "liquidity_risk": "low/medium/high",
        "concentration_risk": "low/medium/high"
    }},
    "strengths": ["风险控制优点"],
    "weaknesses": ["风险控制缺点"],
    "risk_scenarios": [
        {{"scenario": "市场暴跌20%", "expected_loss": -0.15}}
    ],
    "suggestions": ["风险管理建议"],
    "overall_score": 0-100,
    "risk_adjusted_recommendation": "approve/revise/reject"
}}
"""
        
        response = await self._call_llm(prompt)
        
        try:
            critique = self._extract_json(response)
        except:
            critique = {
                "risk_metrics": {
                    "estimated_max_drawdown": 0.2,
                    "var_95": 0.1,
                    "var_99": 0.15,
                    "tail_risk_score": 50,
                    "liquidity_risk": "medium",
                    "concentration_risk": "medium",
                },
                "strengths": [],
                "weaknesses": ["无法完成详细分析"],
                "risk_scenarios": [],
                "suggestions": [],
                "overall_score": 50,
                "risk_adjusted_recommendation": "revise",
                "raw_response": response,
            }
        
        # Ensure required fields
        critique.setdefault("risk_metrics", {})
        critique.setdefault("strengths", [])
        critique.setdefault("weaknesses", [])
        critique.setdefault("risk_scenarios", [])
        critique.setdefault("suggestions", [])
        critique.setdefault("overall_score", 50)
        
        metrics = critique.get("risk_metrics", {})
        
        await self.argue(
            f"## 风险分析报告: {strategy.name}\n\n" +
            f"### 风险指标\n" +
            f"- 预估最大回撤: {metrics.get('estimated_max_drawdown', 'N/A'):.1%}\n" +
            f"- 95% VaR: {metrics.get('var_95', 'N/A'):.1%}\n" +
            f"- 99% VaR: {metrics.get('var_99', 'N/A'):.1%}\n" +
            f"- 尾部风险评分: {metrics.get('tail_risk_score', 'N/A')}/100\n" +
            f"- 流动性风险: {metrics.get('liquidity_risk', 'N/A')}\n" +
            f"- 集中度风险: {metrics.get('concentration_risk', 'N/A')}\n\n" +
            f"### 风险控制建议\n" +
            "\n".join(f"- {s}" for s in critique.get('suggestions', [])),
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
        """Refine strategy with focus on risk management."""
        await self.think(
            "正在优化策略的风险管理措施...",
            round_id=round_id,
        )
        
        # Extract risk-related suggestions
        all_suggestions = []
        risk_issues = []
        
        for critique in critiques:
            all_suggestions.extend(critique.get("suggestions", []))
            if "risk_metrics" in critique:
                metrics = critique["risk_metrics"]
                if metrics.get("estimated_max_drawdown", 0) > 0.2:
                    risk_issues.append("最大回撤过高")
                if metrics.get("tail_risk_score", 0) > 70:
                    risk_issues.append("尾部风险较大")
        
        prompt = f"""请优化策略的风险管理:

原策略:
- 名称: {strategy.name}
- 规则: {json.dumps(strategy.rules, ensure_ascii=False)}

发现的风险问题:
{chr(10).join(f'- {r}' for r in risk_issues)}

风险管理建议:
{chr(10).join(f'- {s}' for s in all_suggestions)}

请调整策略参数，加强风险控制。
"""
        
        response = await self._call_llm(prompt)
        
        # Apply stricter risk parameters
        refined_rules = dict(strategy.rules)
        refined_rules["stop_loss"] = min(refined_rules.get("stop_loss", -0.08), -0.05)
        refined_rules["position_size"] = min(refined_rules.get("position_size", 0.2), 0.15)
        refined_rules["max_portfolio_risk"] = 0.15
        
        refined = ArenaStrategy(
            id=str(uuid.uuid4())[:8],
            arena_id=self.arena_id,
            agent_id=self.agent_id,
            agent_role=self.role.value if hasattr(self.role, 'value') else str(self.role),
            name=f"{strategy.name} (风控优化版)",
            description=strategy.description,
            logic=response,
            rules=refined_rules,
            symbols=strategy.symbols,
            stage=CompetitionStage.BACKTEST,
            refinement_history=strategy.refinement_history + [{
                "risk_analyst_id": self.agent_id,
                "risk_issues_addressed": len(risk_issues),
            }],
            discussion_rounds=strategy.discussion_rounds + [round_id] if round_id else strategy.discussion_rounds,
        )
        
        await self.conclude(
            f"风险优化完成: {refined.name}\n" +
            f"止损调整为: {refined_rules['stop_loss']:.1%}\n" +
            f"仓位调整为: {refined_rules['position_size']:.1%}",
            round_id=round_id,
        )
        
        return refined
    
    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract JSON from text."""
        import re
        
        # Look for nested JSON (may contain nested objects)
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
