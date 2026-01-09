"""Report Agent for financial report analysis using LangGraph/DeepAgents."""

from typing import Dict, Any, List, Callable
import logging

from .base_agent import LangGraphAgent, AgentConfig
from .tools import get_stock_info, get_stock_valuation

logger = logging.getLogger(__name__)


def get_financial_summary(ts_code: str) -> str:
    """获取股票财务摘要信息。
    
    Args:
        ts_code: 股票代码，如 600519 或 600519.SH
        
    Returns:
        财务摘要信息，包括主要财务指标。
    """
    # Auto-complete code suffix
    if len(ts_code) == 6 and ts_code.isdigit():
        if ts_code.startswith('6'):
            ts_code = f"{ts_code}.SH"
        elif ts_code.startswith(('0', '3')):
            ts_code = f"{ts_code}.SZ"
    
    # 目前使用估值数据作为财务摘要的一部分
    # 后续可以扩展接入更多财务数据
    return f"""## {ts_code} 财务摘要

### 关键财务指标
- 营业收入: 待获取（需接入财务数据源）
- 净利润: 待获取
- 毛利率: 待获取
- 净利率: 待获取
- ROE: 待获取

### 成长性分析
- 营收增速: 待计算
- 净利润增速: 待计算

### 偿债能力
- 资产负债率: 待计算
- 流动比率: 待计算

💡 提示：完整财务数据需要接入财务报表数据源。目前可通过 get_stock_valuation 获取估值指标。
"""


class ReportAgent(LangGraphAgent):
    """Report Agent for financial report analysis using DeepAgents.
    
    Handles:
    - Financial statement retrieval
    - Key metrics analysis
    - AI-powered report interpretation
    """
    
    def __init__(self):
        config = AgentConfig(
            name="ReportAgent",
            description="负责财报研读，包括财务指标分析、估值分析、AI解读等"
        )
        super().__init__(config)
    
    def get_tools(self) -> List[Callable]:
        """Return report analysis tools."""
        return [
            get_stock_info,
            get_stock_valuation,
            get_financial_summary,
        ]
    
    def get_system_prompt(self) -> str:
        """Return system prompt for report analysis."""
        return """你是一个专业的财务分析师，专注于A股上市公司的财报分析。

## 可用工具
- get_stock_info: 获取股票基本信息和最新行情
- get_stock_valuation: 获取PE、PB等估值指标
- get_financial_summary: 获取财务摘要信息

## 分析框架
1. **盈利能力**: ROE、毛利率、净利率
2. **成长性**: 营收增速、利润增速
3. **偿债能力**: 资产负债率、流动比率
4. **估值水平**: PE、PB、PS

## 分析流程
1. 获取股票基本信息
2. 获取估值指标
3. 获取财务摘要
4. 综合分析并给出评价

## 常用股票代码
- 贵州茅台: 600519
- 平安银行: 000001
- 比亚迪: 002594

## 分析原则
- 基于真实数据
- 横向对比同行业
- 纵向对比历史
- 明确指出风险点

## 免责声明
财务分析仅供参考，不构成投资建议。
"""
