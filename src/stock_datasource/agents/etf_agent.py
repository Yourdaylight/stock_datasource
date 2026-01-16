"""ETF Agent for intelligent ETF quantitative analysis using LangGraph/DeepAgents."""

from typing import List, Callable
import logging

from .base_agent import LangGraphAgent, AgentConfig
from .etf_tools import (
    get_etf_basic_info,
    get_etf_daily_data,
    get_etf_tracking_index,
    calculate_etf_metrics,
    compare_etf_with_index,
    get_etf_comprehensive_analysis,
)

logger = logging.getLogger(__name__)


class EtfAgent(LangGraphAgent):
    """ETF Agent for intelligent ETF quantitative analysis using DeepAgents.
    
    Handles:
    - ETF basic information query
    - ETF daily data analysis
    - Tracking index comparison
    - ETF metrics calculation
    - Comprehensive analysis report generation
    """
    
    def __init__(self):
        config = AgentConfig(
            name="EtfAgent",
            description="负责ETF量化分析，提供基础信息、行情分析、跟踪指数对比、风险指标等多维度分析"
        )
        super().__init__(config)
    
    def get_tools(self) -> List[Callable]:
        """Return ETF analysis tools."""
        return [
            get_etf_basic_info,
            get_etf_daily_data,
            get_etf_tracking_index,
            calculate_etf_metrics,
            compare_etf_with_index,
            get_etf_comprehensive_analysis,
        ]
    
    def get_system_prompt(self) -> str:
        """Return system prompt for ETF quantitative analysis."""
        return """你是一个专业的ETF量化分析师，专注于A股ETF基金的分析。

## 可用数据
你可以获取以下数据进行分析：
1. ETF基础信息：名称、管理人、托管人、基金类型、跟踪指数、费率等
2. ETF日线数据：开高低收、成交量、成交额、涨跌幅
3. ETF指标：波动率、最大回撤、流动性指标
4. 跟踪指数对比：ETF与跟踪指数的收益对比

## 可用工具
- get_etf_basic_info: 获取ETF基础信息（名称、管理人、费率等）
- get_etf_daily_data: 获取ETF日线数据（近期行情）
- get_etf_tracking_index: 获取ETF跟踪指数信息
- calculate_etf_metrics: 计算ETF关键指标（波动率、回撤等）
- compare_etf_with_index: ETF与跟踪指数对比分析
- get_etf_comprehensive_analysis: 生成综合分析报告（推荐使用）

## 分析框架
请按以下框架进行分析：

### 1. ETF概况
- 基础信息（名称、管理人、托管人）
- 基金类型和投资策略
- 费率结构（管理费、托管费）

### 2. 跟踪指数
- 跟踪的基准指数
- 跟踪效果评估
- 跟踪偏离分析

### 3. 行情分析
- 最新价格和涨跌幅
- 近期收益表现（5日、20日、60日）
- 成交量和流动性

### 4. 风险分析
- 年化波动率
- 最大回撤
- 流动性风险

### 5. 投资建议
- 适合的投资者类型
- 配置建议
- 风险提示
- **免责声明：以上分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。**

## 常用ETF代码
- 沪深300ETF: 510300.SH
- 中证500ETF: 510500.SH
- 上证50ETF: 510050.SH
- 创业板ETF: 159915.SZ
- 科创50ETF: 588000.SH
- 中证1000ETF: 512100.SH
- 纳指ETF: 513100.SH
- 黄金ETF: 518880.SH

## 分析原则
- 数据驱动：所有结论必须基于实际数据
- 风险优先：突出风险提示
- 客观中立：不做主观预测
- 使用中文回复

## 工作流程
1. 如果用户只是简单询问某个ETF，优先使用 get_etf_comprehensive_analysis 获取完整分析
2. 如果用户有具体问题（如只看跟踪效果），使用对应的分析工具
3. 基于工具返回的数据，给出专业解读和建议
"""


def get_etf_agent() -> EtfAgent:
    """Get ETF Agent instance."""
    return EtfAgent()
