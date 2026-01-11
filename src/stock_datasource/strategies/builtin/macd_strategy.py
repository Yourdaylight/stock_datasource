"""
MACD策略 (Moving Average Convergence Divergence Strategy)

基于MACD指标的金叉死叉信号进行交易。
当DIF上穿DEA时买入，下穿时卖出。
"""

from typing import List, Dict, Any
import pandas as pd
import numpy as np
from datetime import datetime

from ..base import BaseStrategy, StrategyMetadata, StrategyCategory, RiskLevel, ParameterSchema, TradingSignal


class MACDStrategy(BaseStrategy):
    """MACD策略"""
    
    def _create_metadata(self) -> StrategyMetadata:
        """创建策略元数据"""
        return StrategyMetadata(
            id="macd_strategy",
            name="MACD策略",
            description="基于MACD指标金叉死叉的趋势跟踪策略。DIF上穿DEA买入，下穿卖出。",
            category=StrategyCategory.TREND,
            author="system",
            version="1.0.0",
            tags=["MACD", "趋势跟踪", "技术分析", "动量指标"],
            risk_level=RiskLevel.MEDIUM
        )
    
    def get_parameter_schema(self) -> List[ParameterSchema]:
        """获取参数配置schema"""
        return [
            ParameterSchema(
                name="fast_period",
                type="int",
                default=12,
                min_value=5,
                max_value=50,
                description="快速EMA周期",
                required=True
            ),
            ParameterSchema(
                name="slow_period",
                type="int", 
                default=26,
                min_value=10,
                max_value=100,
                description="慢速EMA周期",
                required=True
            ),
            ParameterSchema(
                name="signal_period",
                type="int",
                default=9,
                min_value=3,
                max_value=30,
                description="信号线EMA周期",
                required=True
            ),
            ParameterSchema(
                name="use_histogram",
                type="bool",
                default=False,
                description="是否使用MACD柱状图信号",
                required=False
            )
        ]
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """计算MACD指标"""
        df = data.copy()
        
        fast_period = self.params.get('fast_period', 12)
        slow_period = self.params.get('slow_period', 26)
        signal_period = self.params.get('signal_period', 9)
        
        # 计算快速和慢速EMA
        ema_fast = df['close'].ewm(span=fast_period).mean()
        ema_slow = df['close'].ewm(span=slow_period).mean()
        
        # 计算DIF (MACD线)
        df['macd_dif'] = ema_fast - ema_slow
        
        # 计算DEA (信号线)
        df['macd_dea'] = df['macd_dif'].ewm(span=signal_period).mean()
        
        # 计算MACD柱状图
        df['macd_histogram'] = df['macd_dif'] - df['macd_dea']
        
        # 生成交易信号
        df['macd_signal'] = 0
        
        if self.params.get('use_histogram', False):
            # 使用柱状图信号：柱状图由负转正买入，由正转负卖出
            df.loc[(df['macd_histogram'] > 0) & (df['macd_histogram'].shift(1) <= 0), 'macd_signal'] = 1
            df.loc[(df['macd_histogram'] < 0) & (df['macd_histogram'].shift(1) >= 0), 'macd_signal'] = -1
        else:
            # 使用DIF和DEA交叉信号
            df.loc[(df['macd_dif'] > df['macd_dea']) & (df['macd_dif'].shift(1) <= df['macd_dea'].shift(1)), 'macd_signal'] = 1
            df.loc[(df['macd_dif'] < df['macd_dea']) & (df['macd_dif'].shift(1) >= df['macd_dea'].shift(1)), 'macd_signal'] = -1
        
        return df
    
    def generate_signals(self, data: pd.DataFrame) -> List[TradingSignal]:
        """生成交易信号"""
        df = self.calculate_indicators(data)
        signals = []
        
        # 确保有时间戳列
        if 'timestamp' not in df.columns:
            if df.index.name == 'timestamp' or 'date' in str(df.index.dtype):
                df = df.reset_index()
                df.rename(columns={df.columns[0]: 'timestamp'}, inplace=True)
            else:
                df['timestamp'] = pd.date_range(start='2023-01-01', periods=len(df), freq='D')
        
        symbol = df['symbol'].iloc[0] if 'symbol' in df.columns else 'UNKNOWN'
        
        for idx, row in df.iterrows():
            if pd.isna(row['macd_signal']) or row['macd_signal'] == 0:
                continue
            
            timestamp = pd.to_datetime(row['timestamp'])
            price = row['close']
            
            if row['macd_signal'] == 1:  # 买入信号
                reason = self._get_buy_reason(row)
                signal = TradingSignal(
                    timestamp=timestamp,
                    symbol=symbol,
                    action='buy',
                    price=price,
                    confidence=self._calculate_signal_confidence(row),
                    reason=reason
                )
                signals.append(signal)
            
            elif row['macd_signal'] == -1:  # 卖出信号
                reason = self._get_sell_reason(row)
                signal = TradingSignal(
                    timestamp=timestamp,
                    symbol=symbol,
                    action='sell',
                    price=price,
                    confidence=self._calculate_signal_confidence(row),
                    reason=reason
                )
                signals.append(signal)
        
        return signals
    
    def _get_buy_reason(self, row: pd.Series) -> str:
        """获取买入信号原因"""
        if self.params.get('use_histogram', False):
            return f"MACD柱状图由负转正 (柱状图: {row['macd_histogram']:.4f})"
        else:
            return f"DIF上穿DEA (DIF: {row['macd_dif']:.4f}, DEA: {row['macd_dea']:.4f})"
    
    def _get_sell_reason(self, row: pd.Series) -> str:
        """获取卖出信号原因"""
        if self.params.get('use_histogram', False):
            return f"MACD柱状图由正转负 (柱状图: {row['macd_histogram']:.4f})"
        else:
            return f"DIF下穿DEA (DIF: {row['macd_dif']:.4f}, DEA: {row['macd_dea']:.4f})"
    
    def _calculate_signal_confidence(self, row: pd.Series) -> float:
        """计算信号置信度"""
        # 基于DIF和DEA的差值以及柱状图强度计算置信度
        dif_dea_diff = abs(row['macd_dif'] - row['macd_dea'])
        histogram_abs = abs(row['macd_histogram'])
        
        # 归一化置信度
        confidence = min(dif_dea_diff * 10 + histogram_abs * 5, 1.0)
        
        return max(0.3, min(1.0, confidence))
    
    def _explain_strategy_logic(self) -> str:
        """解释策略逻辑"""
        fast_period = self.params.get('fast_period', 12)
        slow_period = self.params.get('slow_period', 26)
        signal_period = self.params.get('signal_period', 9)
        use_histogram = self.params.get('use_histogram', False)
        
        signal_type = "MACD柱状图" if use_histogram else "DIF和DEA交叉"
        
        return f"""
MACD策略是基于指数移动平均线收敛发散的趋势跟踪策略：

**核心逻辑**:
1. 计算{fast_period}日快速EMA和{slow_period}日慢速EMA
2. DIF = 快速EMA - 慢速EMA
3. DEA = DIF的{signal_period}日EMA（信号线）
4. MACD柱状图 = DIF - DEA

**交易信号** ({signal_type}):
{'- 柱状图由负转正时买入，由正转负时卖出' if use_histogram else '- DIF上穿DEA时买入，下穿时卖出'}

**指标含义**:
- DIF反映短期和长期趋势的差异
- DEA是DIF的平滑线，减少噪音
- 柱状图反映DIF和DEA的背离程度

**适用场景**:
- 趋势性行情中效果较好
- 能够捕捉中期趋势转换
- 相比单纯均线策略，信号更加平滑

**注意事项**:
- 在震荡市中可能产生频繁的假信号
- MACD有一定滞后性，适合中长期交易
- 建议结合价格形态和成交量确认信号
        """.strip()