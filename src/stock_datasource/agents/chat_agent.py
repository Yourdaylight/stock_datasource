"""Chat Agent for A-share stock conversations using LangGraph/DeepAgents."""

from typing import Dict, Any, List, Callable
import logging

from .base_agent import LangGraphAgent, AgentConfig
from .tools import get_market_overview, get_stock_info

logger = logging.getLogger(__name__)


# A股知识工具
def get_astock_knowledge() -> str:
    """获取A股基础知识。
    
    Returns:
        A股交易规则、涨跌停限制、主要指数等基础知识。
    """
    return """## A股基础知识

### 交易时间
- 开盘集合竞价: 9:15-9:25
- 连续竞价: 9:30-11:30, 13:00-15:00
- 收盘集合竞价: 14:57-15:00

### 涨跌停限制
- 主板: 10%
- 创业板/科创板: 20%
- ST股票: 5%
- 北交所: 30%

### 交易规则
- T+1交易制度
- 最小交易单位: 100股（1手）
- 科创板/创业板: 最小200股

### 主要指数
- 上证指数: 上海证券交易所综合指数
- 深证成指: 深圳证券交易所成分指数
- 创业板指: 创业板市场指数
- 科创50: 科创板50指数
- 沪深300: 沪深两市300只大盘股
- 中证500: 中盘股指数
"""


def get_platform_help() -> str:
    """获取平台使用帮助。
    
    Returns:
        AI智能选股平台的功能介绍和使用指南。
    """
    return """**AI智能选股平台使用指南**

📊 **行情分析**
- 输入"分析 + 股票名称/代码"查看技术分析
- 例如："分析贵州茅台"或"分析600519"

🔍 **智能选股**
- 描述您的选股条件，AI会帮您筛选
- 例如："找出市盈率低于20的股票"

📈 **财报研读**
- 输入"财报 + 股票名称"查看财务分析
- 例如："贵州茅台财报分析"

💼 **持仓管理**
- 在"持仓管理"页面添加和管理您的模拟持仓

📉 **策略回测**
- 在"策略回测"页面测试各种交易策略

如需更多帮助，请随时提问！
"""


class ChatAgent(LangGraphAgent):
    """Chat Agent for handling A-share stock conversations using DeepAgents.
    
    Handles:
    - General greetings and small talk
    - Questions about the platform
    - A-share market general questions
    - Fallback for unrecognized intents
    """
    
    def __init__(self):
        config = AgentConfig(
            name="ChatAgent",
            description="负责处理A股相关的一般性对话和问答"
        )
        super().__init__(config)
    
    def get_tools(self) -> List[Callable]:
        """Return chat tools."""
        return [
            get_astock_knowledge,
            get_platform_help,
            get_market_overview,
            get_stock_info,
        ]
    
    def get_system_prompt(self) -> str:
        """Return system prompt for chat agent."""
        return """你是一个专业的A股投资助手，专注于中国A股市场的问答和分析。

## 可用工具
- get_astock_knowledge: 获取A股基础知识（交易规则、涨跌停等）
- get_platform_help: 获取平台使用帮助
- get_market_overview: 获取市场整体情况
- get_stock_info: 获取股票信息

## 你的职责
1. 回答用户关于A股市场的各种问题
2. 提供平台使用帮助
3. 解答股票投资基础知识
4. 引导用户使用合适的功能

## 回答原则
1. 专注于A股市场，不涉及其他市场
2. 回答要专业、准确、简洁
3. 涉及投资建议时，提醒风险
4. 如果问题超出能力范围，引导用户使用其他功能

## 常见问题快速回答
- 问候语：友好回应并介绍功能
- 帮助：调用 get_platform_help
- A股规则：调用 get_astock_knowledge

## 免责声明
分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。
"""
