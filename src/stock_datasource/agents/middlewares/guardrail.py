"""GuardrailMiddleware: Input/output safety checks for financial scenarios.

Input: Detect non-financial queries and redirect.
Output: Detect hallucination signals via lightweight LLM check.
"""

from __future__ import annotations

import logging

from .base import AgentContext, AgentResponse, BaseMiddleware

logger = logging.getLogger(__name__)

# Financial-related keywords for input validation
_FINANCIAL_KEYWORDS = [
    "股票",
    "行情",
    "分析",
    "指数",
    "基金",
    "期货",
    "债券",
    "外汇",
    "财报",
    "营收",
    "利润",
    "市盈率",
    "市净率",
    "估值",
    "K线",
    "均线",
    "MACD",
    "RSI",
    "KDJ",
    "技术面",
    "基本面",
    "选股",
    "回测",
    "策略",
    "投资",
    "交易",
    "持仓",
    "仓位",
    "止损",
    "止盈",
    "涨跌",
    "振幅",
    "港股",
    "A股",
    "美股",
    "沪深",
    "上证",
    "深证",
    "创业板",
    "科创板",
    "板块",
    "行业",
    "概念",
    "龙头",
    "白马",
    "蓝筹",
    "红利",
    "ETF",
    "stock",
    "market",
    "invest",
    "trade",
    "portfolio",
    "fund",
    "bond",
    "analysis",
    "chart",
    "indicator",
    "price",
    "volume",
    "trend",
]

# Non-financial topic keywords (strong signal of off-topic)
_NON_FINANCIAL_KEYWORDS = [
    "做菜",
    "菜谱",
    "天气",
    "旅游",
    "电影",
    "音乐",
    "游戏攻略",
    "recipe",
    "weather",
    "movie",
    "music",
    "game walkthrough",
]


class GuardrailMiddleware(BaseMiddleware):
    """Input/output safety middleware for financial scenarios.

    Before execution:
    - Detect non-financial queries → reject with redirect message
    - Flag financial queries for context

    After execution:
    - Lightweight hallucination detection via LLM (optional, expensive)
    - Add warning if hallucination suspected
    """

    def __init__(self, hallucination_check_enabled: bool = False):
        super().__init__()
        self._hallucination_check = hallucination_check_enabled

    async def before(self, context: AgentContext) -> AgentContext:
        """Check if query is financial-related."""
        if not self.enabled:
            return context

        context.trace(self.name, "start")

        # Check for non-financial queries
        query_lower = context.query.lower()
        has_financial = any(kw in query_lower for kw in _FINANCIAL_KEYWORDS)
        has_non_financial = any(kw in query_lower for kw in _NON_FINANCIAL_KEYWORDS)

        if has_non_financial and not has_financial:
            context.is_financial_query = False
            context.trace(self.name, "non_financial")
            logger.info("Non-financial query detected: %s", context.query[:50])
            self._log.info(
                "middleware.non_financial_query",
                query_preview=context.query[:80],
                session_id=context.session_id,
            )
        else:
            context.is_financial_query = True
            context.trace(self.name, "financial")

        return context

    async def after(
        self, context: AgentContext, response: AgentResponse
    ) -> AgentResponse:
        """Optional hallucination check on agent response."""
        if not self.enabled:
            return response

        if self._hallucination_check and response.success and response.content:
            warning = await self._check_hallucination(context.query, response.content)
            if warning:
                response.hallucination_warning = warning
                response.warnings.append(warning)
                context.trace(self.name, "hallucination_warning")
                self._log.warning(
                    "middleware.hallucination_warning",
                    reason=warning[:200],
                    session_id=context.session_id,
                )

        # Add redirect for non-financial queries
        if not context.is_financial_query:
            response.content = (
                "抱歉，我是一个专业的股票分析助手，只能回答与金融投资相关的问题。\n\n"
                "您可以试试以下问题：\n"
                "- 查询某只股票的行情和走势\n"
                "- 对股票进行技术面或基本面分析\n"
                "- 筛选符合条件的股票\n"
                "- 制定投资策略和回测\n\n"
                f"您的问题：{context.query}"
            )
            context.trace(self.name, "redirected")

        return response

    async def _check_hallucination(self, query: str, response: str) -> str:
        """Lightweight hallucination detection via LLM.

        Returns warning string if hallucination suspected, empty string otherwise.
        """
        try:
            from stock_datasource.agents.base_agent import get_langchain_model

            prompt = f"""判断以下金融分析回复是否可能包含幻觉（无数据支撑的断言）。

用户问题: {query}
助手回复: {response[:1000]}

重点关注:
- 是否引用了具体数据但无法验证
- 是否做出了过于绝对的预测
- 是否编造了不存在的股票代码或指标

仅输出JSON: {{"hallucination": true/false, "reason": "..."}}"""

            model = get_langchain_model()
            result = await model.ainvoke([{"role": "user", "content": prompt}])
            content = result.content if hasattr(result, "content") else str(result)

            import json
            import re

            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                parsed = json.loads(match.group(0))
                if parsed.get("hallucination"):
                    reason = parsed.get("reason", "回复可能包含不准确的断言")
                    return f"⚠️ 请注意：{reason}，建议核实数据来源。"

        except Exception as e:
            logger.debug("Hallucination check failed: %s", e)

        return ""
