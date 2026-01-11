"""
双均线策略 (Dual Moving Average Strategy)

基于两条不同周期移动平均线的交叉信号进行交易。
相比单一均线策略，增加了趋势确认和过滤机制。
"""

from typing import List, Dict, Any
import pandas as pd
import numpy as np
from datetime import datetime

from ..base import BaseStrategy, StrategyMetadata, StrategyCategory, RiskLevel, ParameterSchema, TradingSignal


class DualMAStrategy(BaseStrategy):
    """双均线策略"""
    
    def _create_metadata(self) -> StrategyMetadata:
        """创建策略元数据"""
        return StrategyMetadata(
            id="dual_ma_strategy",
            name="双均线策略",
            description="基于快慢双均线交叉的趋势跟踪策略，增加趋势过滤和确认机制。",
            category=StrategyCategory.TREND,
            author="system",
            version="1.0.0",
            tags=["双均线", "趋势跟踪", "交叉信号", "趋势过滤"],
            risk_level=RiskLevel.MEDIUM
        )
    
    def get_parameter_schema(self) -> List[ParameterSchema]:
        """获取参数配置schema"""
        return [
            ParameterSchema(
                name="fast_period",
                type="int",
                default=10,
                min_value=5,
                max_value=50,
                description="快速均线周期",
                required=True
            ),
            ParameterSchema(
                name="slow_period",
                type="int",
                default=30,
                min_value=10,
                max_value=100,
                description="慢速均线周期",
                required=True
            ),
            ParameterSchema(
                name="trend_filter_period",
                type="int",
                default=60,
                min_value=30,
                max_value=200,
                description="趋势过滤均线周期",
                required=False
            ),
            ParameterSchema(
                name="use_trend_filter",
                type="bool",
                default=True,
                description="是否使用趋势过滤",
                required=False
            ),
            ParameterSchema(
                name="min_separation",
                type="float",
                default=0.01,
                min_value=0.0,
                max_value=0.05,
                description="最小均线分离度（避免假信号）",
                required=False
            ),
            ParameterSchema(
                name="ma_type",
                type="str",
                default="EMA",
                description="均线类型: SMA, EMA, WMA",
                required=False
            )
        ]
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """计算双均线指标"""
        df = data.copy()
        
        fast_period = self.params.get('fast_period', 10)
        slow_period = self.params.get('slow_period', 30)
        trend_filter_period = self.params.get('trend_filter_period', 60)
        ma_type = self.params.get('ma_type', 'EMA')
        
        # 计算均线
        if ma_type == 'SMA':
            df['ma_fast'] = df['close'].rolling(fast_period).mean()
            df['ma_slow'] = df['close'].rolling(slow_period).mean()
            if self.params.get('use_trend_filter', True):
                df['ma_trend'] = df['close'].rolling(trend_filter_period).mean()
        elif ma_type == 'WMA':
            weights_fast = np.arange(1, fast_period + 1)
            weights_slow = np.arange(1, slow_period + 1)
            df['ma_fast'] = df['close'].rolling(fast_period).apply(
                lambda x: np.average(x, weights=weights_fast), raw=True
            )
            df['ma_slow'] = df['close'].rolling(slow_period).apply(
                lambda x: np.average(x, weights=weights_slow), raw=True
            )
            if self.params.get('use_trend_filter', True):
                weights_trend = np.arange(1, trend_filter_period + 1)
                df['ma_trend'] = df['close'].rolling(trend_filter_period).apply(
                    lambda x: np.average(x, weights=weights_trend), raw=True
                )
        else:  # EMA
            df['ma_fast'] = df['close'].ewm(span=fast_period).mean()
            df['ma_slow'] = df['close'].ewm(span=slow_period).mean()
            if self.params.get('use_trend_filter', True):
                df['ma_trend'] = df['close'].ewm(span=trend_filter_period).mean()
        
        # 计算均线差值和分离度
        df['ma_diff'] = df['ma_fast'] - df['ma_slow']
        df['ma_separation'] = abs(df['ma_diff']) / df['close']
        
        # 计算均线斜率（趋势强度）
        df['ma_fast_slope'] = df['ma_fast'].diff(5) / df['ma_fast']
        df['ma_slow_slope'] = df['ma_slow'].diff(5) / df['ma_slow']
        
        # 生成交易信号
        df['dual_ma_signal'] = 0
        
        min_separation = self.params.get('min_separation', 0.01)
        use_trend_filter = self.params.get('use_trend_filter', True)
        
        # 基础交叉信号
        golden_cross = ((df['ma_fast'] > df['ma_slow']) & 
                       (df['ma_fast'].shift(1) <= df['ma_slow'].shift(1)))
        
        death_cross = ((df['ma_fast'] < df['ma_slow']) & 
                      (df['ma_fast'].shift(1) >= df['ma_slow'].shift(1)))
        
        # 添加分离度过滤
        sufficient_separation = df['ma_separation'] > min_separation
        
        # 添加趋势过滤
        if use_trend_filter and 'ma_trend' in df.columns:
            uptrend = df['close'] > df['ma_trend']
            downtrend = df['close'] < df['ma_trend']
            
            # 只在趋势方向一致时产生信号
            buy_condition = golden_cross & sufficient_separation & uptrend
            sell_condition = death_cross & sufficient_separation & downtrend
        else:
            buy_condition = golden_cross & sufficient_separation
            sell_condition = death_cross & sufficient_separation
        
        df.loc[buy_condition, 'dual_ma_signal'] = 1
        df.loc[sell_condition, 'dual_ma_signal'] = -1
        
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
            if (pd.isna(row['dual_ma_signal']) or row['dual_ma_signal'] == 0 or 
                pd.isna(row['ma_fast']) or pd.isna(row['ma_slow'])):
                continue
            
            timestamp = pd.to_datetime(row['timestamp'])
            price = row['close']
            
            if row['dual_ma_signal'] == 1:  # 买入信号
                reason = self._get_buy_reason(row)
                signal = TradingSignal(
                    timestamp=timestamp,
                    symbol=symbol,
                    action='buy',
                    price=price,
                    confidence=self._calculate_signal_confidence(row, 'buy'),
                    reason=reason
                )
                signals.append(signal)
            
            elif row['dual_ma_signal'] == -1:  # 卖出信号
                reason = self._get_sell_reason(row)
                signal = TradingSignal(
                    timestamp=timestamp,
                    symbol=symbol,
                    action='sell',
                    price=price,
                    confidence=self._calculate_signal_confidence(row, 'sell'),
                    reason=reason
                )
                signals.append(signal)
        
        return signals
    
    def _get_buy_reason(self, row: pd.Series) -> str:
        """获取买入信号原因"""
        fast_ma = row['ma_fast']
        slow_ma = row['ma_slow']
        separation = row['ma_separation']
        
        reason = f"快线({self.params['fast_period']})上穿慢线({self.params['slow_period']}) "
        reason += f"(快线: {fast_ma:.2f}, 慢线: {slow_ma:.2f}, 分离度: {separation:.2%})"
        
        if self.params.get('use_trend_filter', True) and 'ma_trend' in row:
            trend_ma = row['ma_trend']
            reason += f", 趋势过滤: {trend_ma:.2f}"
        
        return reason
    
    def _get_sell_reason(self, row: pd.Series) -> str:
        """获取卖出信号原因"""
        fast_ma = row['ma_fast']
        slow_ma = row['ma_slow']
        separation = row['ma_separation']
        
        reason = f"快线({self.params['fast_period']})下穿慢线({self.params['slow_period']}) "
        reason += f"(快线: {fast_ma:.2f}, 慢线: {slow_ma:.2f}, 分离度: {separation:.2%})"
        
        if self.params.get('use_trend_filter', True) and 'ma_trend' in row:
            trend_ma = row['ma_trend']
            reason += f", 趋势过滤: {trend_ma:.2f}"
        
        return reason
    
    def _calculate_signal_confidence(self, row: pd.Series, signal_type: str) -> float:
        """计算信号置信度"""
        separation = row.get('ma_separation', 0)
        fast_slope = row.get('ma_fast_slope', 0)
        slow_slope = row.get('ma_slow_slope', 0)
        
        # 基于分离度的置信度
        separation_confidence = min(separation / 0.05, 1.0)
        
        # 基于均线斜率的置信度
        if signal_type == 'buy':
            slope_confidence = max(0, fast_slope) * 10
        else:  # sell
            slope_confidence = max(0, -fast_slope) * 10
        
        slope_confidence = min(slope_confidence, 1.0)
        
        # 趋势一致性加分
        trend_bonus = 0
        if self.params.get('use_trend_filter', True):
            price = row['close']
            trend_ma = row.get('ma_trend', price)
            
            if signal_type == 'buy' and price > trend_ma:
                trend_bonus = 0.2
            elif signal_type == 'sell' and price < trend_ma:
                trend_bonus = 0.2
        
        # 综合置信度
        confidence = (separation_confidence * 0.4 + 
                     slope_confidence * 0.4 + 
                     trend_bonus + 0.3)
        
        return max(0.3, min(1.0, confidence))
    
    def _explain_strategy_logic(self) -> str:
        """解释策略逻辑"""
        fast_period = self.params.get('fast_period', 10)
        slow_period = self.params.get('slow_period', 30)
        trend_filter_period = self.params.get('trend_filter_period', 60)
        use_trend_filter = self.params.get('use_trend_filter', True)
        ma_type = self.params.get('ma_type', 'EMA')
        
        return f"""
双均线策略是经典趋势跟踪策略的改进版本：

**核心逻辑**:
1. 计算{fast_period}日快速{ma_type}和{slow_period}日慢速{ma_type}
2. {'同时计算' + str(trend_filter_period) + '日趋势过滤线' if use_trend_filter else ''}
3. 快线上穿慢线产生买入信号
4. 快线下穿慢线产生卖出信号

**信号过滤机制**:
- 最小分离度过滤：避免均线纠缠时的假信号
- {'趋势过滤：只在主趋势方向交易' if use_trend_filter else ''}
- 均线斜率确认：增强信号可靠性

**相比单均线优势**:
- 双重确认机制，减少假信号
- 更好的趋势识别能力
- 可配置的过滤条件

**参数说明**:
- 快线周期越短，信号越敏感
- 慢线周期越长，信号越稳定
- 趋势过滤线帮助识别主要趋势方向

**适用场景**:
- 中长期趋势性行情
- 适合波动较大的市场
- 需要明确趋势方向的交易

**风险控制**:
- 设置合理的止损位
- 注意均线系统的滞后性
- 在震荡市中谨慎使用
        """.strip()