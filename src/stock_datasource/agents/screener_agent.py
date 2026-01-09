"""Screener Agent for intelligent stock screening using LangGraph/DeepAgents."""

from typing import Dict, Any, List, Callable
import logging

from .base_agent import LangGraphAgent, AgentConfig
from .tools import screen_stocks, get_market_overview

logger = logging.getLogger(__name__)


class ScreenerAgent(LangGraphAgent):
    """Screener Agent for intelligent stock screening using DeepAgents.
    
    Handles:
    - Condition-based stock filtering
    - Natural language stock screening
    - Preset strategy application
    """
    
    def __init__(self):
        config = AgentConfig(
            name="ScreenerAgent",
            description="负责智能选股，支持条件筛选、自然语言选股、预设策略等"
        )
        super().__init__(config)
    
    def get_tools(self) -> List[Callable]:
        """Return screening tools."""
        return [
            screen_stocks,
            get_market_overview,
        ]
    
    def get_system_prompt(self) -> str:
        """Return system prompt for stock screening."""
        return """你是一个专业的A股选股分析师。

## 可用工具
- screen_stocks: 根据条件筛选股票（PE、PB、市值、行业等）
- get_market_overview: 获取市场整体情况

## 选股条件参数
- min_pe / max_pe: PE范围
- min_pb / max_pb: PB范围
- min_market_cap / max_market_cap: 市值范围（亿元）
- industry: 行业名称（模糊匹配）
- limit: 返回数量

## 预设策略
1. **低估值策略**: PE < 15, PB < 2
2. **高成长策略**: 关注营收和利润增速
3. **高股息策略**: 股息率 > 3%
4. **动量策略**: 近期涨幅较好

## 工作流程
1. 理解用户的选股需求
2. 转换为具体的筛选条件
3. 调用 screen_stocks 工具
4. 分析筛选结果并给出建议

## 注意事项
- 使用中文回复
- 解释选股逻辑
- 提示投资风险

## 免责声明
选股结果仅供参考，不构成投资建议。
"""
