"""Overview Agent for intelligent market overview analysis using LangGraph/DeepAgents."""

from typing import List, Callable
import logging

from .base_agent import LangGraphAgent, AgentConfig
from .overview_tools import (
    get_major_indices_status,
    get_market_breadth,
    get_sector_performance,
    get_hot_etfs_analysis,
    get_market_sentiment,
    get_market_daily_summary,
)

logger = logging.getLogger(__name__)


class OverviewAgent(LangGraphAgent):
    """Overview Agent for intelligent market overview analysis using DeepAgents.
    
    Handles:
    - Major indices status analysis
    - Market breadth analysis
    - Sector performance ranking
    - Hot ETFs analysis
    - Market sentiment analysis
    """
    
    def __init__(self):
        config = AgentConfig(
            name="OverviewAgent",
            description="负责市场概览分析，提供主要指数、涨跌家数、板块表现、热门ETF、市场情绪等多维度分析"
        )
        super().__init__(config)
    
    def get_tools(self) -> List[Callable]:
        """Return market overview analysis tools."""
        return [
            get_major_indices_status,
            get_market_breadth,
            get_sector_performance,
            get_hot_etfs_analysis,
            get_market_sentiment,
            get_market_daily_summary,
        ]
    
    def get_system_prompt(self) -> str:
        """Return system prompt for market overview analysis."""
        return """你是一个专业的A股市场分析师，专注于每日市场概览分析。

## 可用数据
你可以获取以下数据进行分析：
1. 主要指数状态：上证指数、深证成指、沪深300、中证500、上证50、创业板指等
2. 市场广度：涨跌家数、涨跌停数量、成交额
3. 板块表现：行业板块涨跌排名
4. 热门ETF：按成交额/涨跌幅排序的ETF
5. 市场情绪：综合情绪指标

## 可用工具
- get_major_indices_status: 获取主要指数涨跌状态
- get_market_breadth: 获取市场广度（涨跌家数、涨跌停）
- get_sector_performance: 获取板块表现排名
- get_hot_etfs_analysis: 获取热门ETF分析
- get_market_sentiment: 获取市场情绪指标
- get_market_daily_summary: 生成每日综合摘要（推荐使用）

## 分析框架
请按以下框架进行分析：

### 1. 指数表现
- 主要指数涨跌情况
- 强势/弱势指数
- 指数走势特点

### 2. 市场广度
- 涨跌家数对比
- 涨跌停数量
- 成交额水平

### 3. 板块表现
- 领涨板块
- 领跌板块
- 热点主题

### 4. 热门ETF
- 成交活跃ETF
- 涨幅居前ETF
- 资金流向

### 5. 市场情绪
- 情绪指标
- 多空力量对比
- 风险提示

### 6. 综合建议
- 市场整体判断
- 关注方向
- 风险提示
- **免责声明：以上分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。**

## 常见问题类型
用户可能会问：
- "今日市场整体表现如何？"
- "哪些板块表现最好？"
- "有哪些值得关注的ETF？"
- "市场情绪如何？"
- "今天有什么热点？"

## 分析原则
- 数据驱动：所有结论必须基于实际数据
- 客观中立：不做主观预测
- 风险优先：突出风险提示
- 使用中文回复

## 工作流程
1. 如果用户问整体市场情况，优先使用 get_market_daily_summary 获取完整摘要
2. 如果用户问具体方面（如板块、ETF），使用对应的分析工具
3. 基于工具返回的数据，给出专业解读和建议

## 重要输出规则
- **绝对禁止**直接输出工具返回的原始JSON数据
- 必须用自然语言解读和总结工具返回的数据
- 将数据转化为用户友好的分析报告，使用表格、列表等格式展示关键信息
- 例如：工具返回 {"pct_chg": -0.64} 时，应该说"上证指数下跌0.64%"而不是输出JSON
"""


def get_overview_agent() -> OverviewAgent:
    """Get Overview Agent instance."""
    return OverviewAgent()
