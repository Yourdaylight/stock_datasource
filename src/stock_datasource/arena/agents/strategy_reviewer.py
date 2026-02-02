"""
Strategy Reviewer Agent

Agent responsible for critically reviewing and validating trading strategies.
"""

import json
import logging
import uuid
from typing import Any, Dict, List

from ..models import AgentConfig, AgentRole, ArenaStrategy, CompetitionStage
from .base import ArenaAgentBase

logger = logging.getLogger(__name__)


class StrategyReviewerAgent(ArenaAgentBase):
    """Agent that reviews and validates trading strategies.
    
    This agent critically examines strategies for logical flaws,
    missing risk controls, and optimization opportunities.
    """
    
    @property
    def role_name(self) -> str:
        return "Strategy Reviewer"
    
    def get_system_prompt(self) -> str:
        """Get system prompt for strategy review."""
        return """你是一个专业的量化策略评审专家。

你的职责是:
1. 严格审查交易策略的逻辑完整性
2. 识别策略中的潜在风险和漏洞
3. 验证参数设置的合理性
4. 提出具体可行的改进建议

在评审策略时，请确保:
- 用批判性思维分析策略
- 不放过任何逻辑漏洞
- 考虑各种市场环境下的表现
- 给出量化的评估分数

你应该像一个严格的风控经理一样审查每一个策略。
"""
    
    async def generate_strategy(
        self,
        symbols: List[str],
        market_context: Dict[str, Any] = None,
        round_id: str = "",
    ) -> ArenaStrategy:
        """Reviewers can also generate strategies, typically more conservative ones."""
        await self.think(
            "作为评审者，我将生成一个更加保守稳健的策略...",
            round_id=round_id,
        )
        
        prompt = f"""作为一个策略评审专家，请生成一个稳健保守的交易策略。

目标股票: {', '.join(symbols[:10])}

请特别关注:
1. 风险控制措施
2. 止损机制
3. 仓位管理
4. 市场环境适应性

输出一个完整的策略，包括名称、描述、逻辑和交易规则（JSON格式）。
"""
        
        response = await self._call_llm(prompt)
        
        strategy = ArenaStrategy(
            id=str(uuid.uuid4())[:8],
            arena_id=self.arena_id,
            agent_id=self.agent_id,
            agent_role=self.role.value if hasattr(self.role, 'value') else str(self.role),
            name="稳健型策略",
            description="由策略评审专家生成的保守型策略",
            logic=response,
            rules={
                "entry_conditions": [],
                "exit_conditions": [],
                "position_size": 0.1,
                "stop_loss": -0.05,
                "take_profit": 0.1,
            },
            symbols=symbols,
            stage=CompetitionStage.BACKTEST,
            discussion_rounds=[round_id] if round_id else [],
        )
        
        await self.conclude(
            f"策略生成完成: {strategy.name}",
            round_id=round_id,
        )
        
        return strategy
    
    async def critique_strategy(
        self,
        strategy: ArenaStrategy,
        market_context: Dict[str, Any] = None,
        round_id: str = "",
    ) -> Dict[str, Any]:
        """Thoroughly critique a strategy."""
        await self.think(
            f"开始严格审查策略: {strategy.name}",
            round_id=round_id,
        )
        
        prompt = f"""请严格审查以下交易策略，找出所有潜在问题:

策略名称: {strategy.name}
策略描述: {strategy.description}
策略逻辑: {strategy.logic}
交易规则: {json.dumps(strategy.rules, ensure_ascii=False, indent=2)}

请从以下角度进行严格审查:
1. 逻辑完整性: 策略逻辑是否有漏洞?
2. 风险控制: 止损止盈设置是否合理?
3. 参数合理性: 参数是否有优化空间?
4. 市场适应性: 在不同市场环境下表现如何?
5. 执行可行性: 策略是否可以实际执行?

请输出详细的审查报告（JSON格式）:
{{
    "strengths": ["优点1", "优点2"],
    "weaknesses": ["缺点1", "缺点2"],
    "risks": ["风险1", "风险2"],
    "suggestions": ["建议1", "建议2"],
    "overall_score": 0-100,
    "risk_level": "low/medium/high",
    "recommendation": "approve/revise/reject"
}}
"""
        
        response = await self._call_llm(prompt)
        
        try:
            critique = self._extract_json(response)
        except:
            critique = {
                "strengths": [],
                "weaknesses": ["无法解析评审结果"],
                "risks": [],
                "suggestions": [],
                "overall_score": 50,
                "risk_level": "medium",
                "recommendation": "revise",
                "raw_response": response,
            }
        
        # Ensure all required fields
        critique.setdefault("strengths", [])
        critique.setdefault("weaknesses", [])
        critique.setdefault("risks", [])
        critique.setdefault("suggestions", [])
        critique.setdefault("overall_score", 50)
        critique.setdefault("risk_level", "medium")
        critique.setdefault("recommendation", "revise")
        
        await self.argue(
            f"## 策略审查报告: {strategy.name}\n\n" +
            f"**评分**: {critique['overall_score']}/100\n" +
            f"**风险等级**: {critique['risk_level']}\n" +
            f"**建议**: {critique['recommendation']}\n\n" +
            f"### 优点\n" + "\n".join(f"- {s}" for s in critique['strengths']) + "\n\n" +
            f"### 问题\n" + "\n".join(f"- {w}" for w in critique['weaknesses']) + "\n\n" +
            f"### 风险\n" + "\n".join(f"- {r}" for r in critique['risks']) + "\n\n" +
            f"### 改进建议\n" + "\n".join(f"- {s}" for s in critique['suggestions']),
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
        """Refine strategy with focus on addressing identified issues."""
        await self.think(
            "正在根据审查意见优化策略，重点关注风险控制...",
            round_id=round_id,
        )
        
        # Collect all issues and suggestions
        all_weaknesses = []
        all_risks = []
        all_suggestions = []
        
        for critique in critiques:
            all_weaknesses.extend(critique.get("weaknesses", []))
            all_risks.extend(critique.get("risks", []))
            all_suggestions.extend(critique.get("suggestions", []))
        
        prompt = f"""请根据以下审查意见优化策略:

原策略:
- 名称: {strategy.name}
- 逻辑: {strategy.logic}
- 规则: {json.dumps(strategy.rules, ensure_ascii=False)}

发现的问题:
{chr(10).join(f'- {w}' for w in all_weaknesses)}

识别的风险:
{chr(10).join(f'- {r}' for r in all_risks)}

改进建议:
{chr(10).join(f'- {s}' for s in all_suggestions)}

请输出优化后的策略，特别关注风险控制。
"""
        
        response = await self._call_llm(prompt)
        
        refined = ArenaStrategy(
            id=str(uuid.uuid4())[:8],
            arena_id=self.arena_id,
            agent_id=self.agent_id,
            agent_role=self.role.value if hasattr(self.role, 'value') else str(self.role),
            name=f"{strategy.name} (审核优化版)",
            description=strategy.description,
            logic=response,
            rules=strategy.rules,
            symbols=strategy.symbols,
            stage=CompetitionStage.BACKTEST,
            refinement_history=strategy.refinement_history + [{
                "reviewer_id": self.agent_id,
                "issues_addressed": len(all_weaknesses) + len(all_risks),
            }],
            discussion_rounds=strategy.discussion_rounds + [round_id] if round_id else strategy.discussion_rounds,
        )
        
        await self.conclude(
            f"策略审核优化完成: {refined.name}",
            round_id=round_id,
        )
        
        return refined
    
    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract JSON from text."""
        import re
        
        json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        code_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if code_match:
            try:
                return json.loads(code_match.group(1))
            except json.JSONDecodeError:
                pass
        
        raise ValueError("No valid JSON found in text")
