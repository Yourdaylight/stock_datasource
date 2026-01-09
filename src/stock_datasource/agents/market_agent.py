"""Market Agent for stock market analysis using LangGraph/DeepAgents."""

from typing import Dict, Any, List, Callable
import logging

from .base_agent import LangGraphAgent, AgentConfig
from .tools import (
    get_stock_info,
    get_stock_kline,
    get_stock_valuation,
    calculate_technical_indicators,
    get_market_overview,
)

logger = logging.getLogger(__name__)


class MarketAgent(LangGraphAgent):
    """Market Agent for stock market analysis using DeepAgents.
    
    Handles:
    - K-line data queries from ClickHouse
    - Technical indicator calculations
    - AI-powered trend analysis with real data
    - Valuation analysis
    """
    
    def __init__(self):
        config = AgentConfig(
            name="MarketAgent",
            description="负责A股股票行情分析，包括K线数据、技术指标计算、走势分析、估值分析等。"
        )
        super().__init__(config)
    
    def get_tools(self) -> List[Callable]:
        """Return market analysis tools."""
        return [
            get_stock_info,
            get_stock_kline,
            get_stock_valuation,
            calculate_technical_indicators,
            get_market_overview,
        ]
    
    def get_system_prompt(self) -> str:
        """Return system prompt for market analysis."""
        return """你是一个专业的A股行情分析师。

## 可用工具
- get_stock_info: 获取股票基本信息和最新行情
- get_stock_kline: 获取K线数据
- get_stock_valuation: 获取PE、PB等估值指标
- calculate_technical_indicators: 计算均线、趋势等技术指标
- get_market_overview: 获取大盘整体情况

## 分析流程
1. 使用 get_stock_info 获取股票基本信息
2. 使用 get_stock_kline 获取K线数据
3. 使用 get_stock_valuation 获取估值数据
4. 使用 calculate_technical_indicators 分析技术面
5. 综合分析并给出结论

## 常用股票代码
- 贵州茅台: 600519
- 平安银行: 000001
- 比亚迪: 002594

## 分析原则
- 基于真实数据分析，不编造
- 技术面结合基本面
- 明确指出风险
- 使用中文，简洁专业

## 免责声明
分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。
"""
