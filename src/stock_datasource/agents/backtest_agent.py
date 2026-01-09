"""Backtest Agent for strategy backtesting using LangGraph/DeepAgents."""

from typing import Dict, Any, List, Callable
import logging

from .base_agent import LangGraphAgent, AgentConfig
from .tools import get_stock_kline

logger = logging.getLogger(__name__)


def list_available_strategies() -> str:
    """获取可用的回测策略列表。
    
    Returns:
        策略列表，包含策略ID、名称、描述和参数说明
    """
    return """## 可用回测策略

### 趋势类策略

1. **均线策略 (ma)**
   - 描述: 基于短期和长期均线交叉
   - 参数: short_period(默认5), long_period(默认20)
   - 信号: 金叉买入，死叉卖出

2. **MACD策略 (macd)**
   - 描述: 基于MACD指标金叉死叉
   - 参数: fast_period(12), slow_period(26), signal_period(9)
   - 信号: DIF上穿DEA买入，下穿卖出

3. **海龟策略 (turtle)**
   - 描述: 经典趋势跟踪策略
   - 参数: entry_period(20), exit_period(10)
   - 信号: 突破N日高点买入，跌破M日低点卖出

### 震荡类策略

4. **RSI策略 (rsi)**
   - 描述: 基于RSI超买超卖
   - 参数: period(14), oversold(30), overbought(70)
   - 信号: 超卖买入，超买卖出

5. **KDJ策略 (kdj)**
   - 描述: 基于KDJ指标
   - 参数: period(9)
   - 信号: K线上穿D线买入，下穿卖出

6. **布林带策略 (boll)**
   - 描述: 基于布林带上下轨
   - 参数: period(20), std_dev(2)
   - 信号: 触及下轨买入，触及上轨卖出
"""


def run_simple_backtest(
    strategy: str,
    ts_code: str,
    days: int = 60
) -> str:
    """执行简单策略回测（基于均线）。
    
    Args:
        strategy: 策略名称，如 ma, macd, rsi
        ts_code: 股票代码
        days: 回测天数
        
    Returns:
        回测结果摘要
    """
    # Auto-complete code suffix
    if len(ts_code) == 6 and ts_code.isdigit():
        if ts_code.startswith('6'):
            ts_code = f"{ts_code}.SH"
        elif ts_code.startswith(('0', '3')):
            ts_code = f"{ts_code}.SZ"
    
    # 这里是简化的回测逻辑示例
    # 生产环境应该实现完整的回测引擎
    
    return f"""## {ts_code} {strategy.upper()}策略回测结果

### 回测参数
- 策略: {strategy}
- 标的: {ts_code}
- 回测周期: 最近{days}个交易日

### 回测结果（示例）
⚠️ 注意：这是简化的回测示例，完整回测需要接入回测引擎。

| 指标 | 数值 |
|------|------|
| 总收益率 | 待计算 |
| 年化收益 | 待计算 |
| 最大回撤 | 待计算 |
| 夏普比率 | 待计算 |
| 胜率 | 待计算 |
| 交易次数 | 待计算 |

### 建议
1. 使用 get_stock_kline 获取历史数据
2. 根据策略规则模拟交易
3. 计算各项绩效指标

💡 完整回测功能请前往"策略回测"页面使用。
"""


def get_backtest_guide() -> str:
    """获取策略回测使用指南。
    
    Returns:
        回测功能的详细使用说明
    """
    return """## 策略回测使用指南

### 功能介绍
策略回测帮助您验证交易策略在历史数据上的表现。

### 回测步骤
1. **选择策略**: 从预设策略中选择（均线、MACD、RSI等）
2. **选择标的**: 输入股票代码
3. **设置参数**: 配置策略参数和回测区间
4. **执行回测**: 系统模拟历史交易
5. **分析结果**: 查看绩效指标和交易记录

### 绩效指标说明
- **总收益率**: 回测期间的总收益
- **年化收益**: 换算成年化的收益率
- **最大回撤**: 期间最大亏损幅度
- **夏普比率**: 风险调整后收益
- **胜率**: 盈利交易占比
- **盈亏比**: 平均盈利/平均亏损

### 使用建议
1. 选择足够长的回测区间（建议1年以上）
2. 考虑交易成本（手续费、滑点）
3. 关注最大回撤，控制风险
4. 对比多个策略选择最优
5. 避免过度拟合历史数据

### 风险提示
历史表现不代表未来收益，回测结果仅供参考。
"""


class BacktestAgent(LangGraphAgent):
    """Backtest Agent for strategy backtesting using DeepAgents.
    
    Handles:
    - Strategy selection
    - Backtest execution
    - Result analysis
    - Strategy comparison
    """
    
    def __init__(self):
        config = AgentConfig(
            name="BacktestAgent",
            description="负责策略回测，包括策略选择、参数配置、回测执行、结果分析"
        )
        super().__init__(config)
    
    def get_tools(self) -> List[Callable]:
        """Return backtesting tools."""
        return [
            list_available_strategies,
            run_simple_backtest,
            get_backtest_guide,
            get_stock_kline,
        ]
    
    def get_system_prompt(self) -> str:
        """Return system prompt for backtesting."""
        return """你是策略回测助手，帮助用户验证和分析交易策略。

## 可用工具
- list_available_strategies: 列出可用策略
- run_simple_backtest: 执行简单回测
- get_backtest_guide: 获取回测使用指南
- get_stock_kline: 获取K线数据

## 支持的策略
- ma: 均线策略
- macd: MACD策略
- rsi: RSI策略
- kdj: KDJ策略
- boll: 布林带策略
- turtle: 海龟策略

## 工作流程
1. 了解用户想要回测的策略
2. 确认回测标的和参数
3. 执行回测或提供指导
4. 分析回测结果

## 回测指标
- 总收益率 / 年化收益率
- 最大回撤
- 夏普比率
- 胜率
- 盈亏比

## 注意事项
- 历史表现不代表未来
- 考虑交易成本
- 避免过度拟合
- 关注风险控制
"""
