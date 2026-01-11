"""
移动平均策略 (Moving Average Strategy)

基于短期和长期移动平均线的交叉信号进行交易。
当短期均线上穿长期均线时买入，下穿时卖出。
"""

from typing import List, Dict, Any
import pandas as pd
import numpy as np
from datetime import datetime

from ..base import BaseStrategy, StrategyMetadata, StrategyCategory, RiskLevel, ParameterSchema, TradingSignal


class MAStrategy(BaseStrategy):
    """移动平均策略"""
    
    def _create_metadata(self) -> StrategyMetadata:
        """创建策略元数据"""
        return StrategyMetadata(
            id="ma_strategy",
            name="移动平均策略",
            description="基于短期和长期移动平均线交叉的趋势跟踪策略。金叉买入，死叉卖出。",
            category=StrategyCategory.TREND,
            author="system",
            version="1.0.0",
            tags=["移动平均", "趋势跟踪", "技术分析", "经典策略"],
            risk_level=RiskLevel.MEDIUM
        )
    
    def get_parameter_schema(self) -> List[ParameterSchema]:
        """获取参数配置schema"""
        return [
            ParameterSchema(
                name="short_period",
                type="int",
                default=5,
                min_value=1,
                max_value=50,
                description="短期移动平均周期",
                required=True
            ),
            ParameterSchema(
                name="long_period", 
                type="int",
                default=20,
                min_value=2,
                max_value=200,
                description="长期移动平均周期",
                required=True
            ),
            ParameterSchema(
                name="ma_type",
                type="str",
                default="SMA",
                description="移动平均类型: SMA(简单), EMA(指数), WMA(加权)",
                required=False
            )
        ]
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """计算移动平均指标"""
        df = data.copy()
        
        short_period = self.params.get('short_period', 5)
        long_period = self.params.get('long_period', 20)
        ma_type = self.params.get('ma_type', 'SMA')
        
        # 计算移动平均
        if ma_type == 'EMA':
            df['ma_short'] = df['close'].ewm(span=short_period).mean()
            df['ma_long'] = df['close'].ewm(span=long_period).mean()
        elif ma_type == 'WMA':
            weights_short = np.arange(1, short_period + 1)
            weights_long = np.arange(1, long_period + 1)
            df['ma_short'] = df['close'].rolling(short_period).apply(
                lambda x: np.average(x, weights=weights_short), raw=True
            )
            df['ma_long'] = df['close'].rolling(long_period).apply(
                lambda x: np.average(x, weights=weights_long), raw=True
            )
        else:  # SMA
            df['ma_short'] = df['close'].rolling(short_period).mean()
            df['ma_long'] = df['close'].rolling(long_period).mean()
        
        # 计算交叉信号
        df['ma_diff'] = df['ma_short'] - df['ma_long']
        df['ma_signal'] = 0
        
        # 金叉：短均线上穿长均线
        df.loc[(df['ma_diff'] > 0) & (df['ma_diff'].shift(1) <= 0), 'ma_signal'] = 1
        # 死叉：短均线下穿长均线  
        df.loc[(df['ma_diff'] < 0) & (df['ma_diff'].shift(1) >= 0), 'ma_signal'] = -1
        
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
        
        # 假设有symbol列，如果没有则使用默认值
        symbol = df['symbol'].iloc[0] if 'symbol' in df.columns else 'UNKNOWN'
        
        for idx, row in df.iterrows():
            if pd.isna(row['ma_signal']) or row['ma_signal'] == 0:
                continue
            
            timestamp = pd.to_datetime(row['timestamp'])
            price = row['close']
            
            if row['ma_signal'] == 1:  # 买入信号
                signal = TradingSignal(
                    timestamp=timestamp,
                    symbol=symbol,
                    action='buy',
                    price=price,
                    confidence=self._calculate_signal_confidence(row),
                    reason=f"短期均线({self.params['short_period']})上穿长期均线({self.params['long_period']})"
                )
                signals.append(signal)
            
            elif row['ma_signal'] == -1:  # 卖出信号
                signal = TradingSignal(
                    timestamp=timestamp,
                    symbol=symbol,
                    action='sell',
                    price=price,
                    confidence=self._calculate_signal_confidence(row),
                    reason=f"短期均线({self.params['short_period']})下穿长期均线({self.params['long_period']})"
                )
                signals.append(signal)
        
        return signals
    
    def _calculate_signal_confidence(self, row: pd.Series) -> float:
        """计算信号置信度"""
        # 基于均线差值的绝对值计算置信度
        ma_diff_abs = abs(row['ma_diff'])
        price = row['close']
        
        # 差值占价格的比例作为置信度基础
        confidence = min(ma_diff_abs / price * 100, 1.0)
        
        # 确保置信度在合理范围内
        return max(0.3, min(1.0, confidence))
    
    def _explain_strategy_logic(self) -> str:
        """解释策略逻辑"""
        short_period = self.params.get('short_period', 5)
        long_period = self.params.get('long_period', 20)
        ma_type = self.params.get('ma_type', 'SMA')
        
        return f"""
移动平均策略是最经典的趋势跟踪策略之一：

**核心逻辑**:
1. 计算{short_period}日短期{ma_type}和{long_period}日长期{ma_type}
2. 当短期均线上穿长期均线时产生买入信号（金叉）
3. 当短期均线下穿长期均线时产生卖出信号（死叉）

**适用市场**:
- 趋势明显的市场环境
- 避免在震荡市中使用，容易产生假信号

**风险控制**:
- 建议结合其他指标过滤信号
- 设置止损位控制风险
- 注意均线滞后性，可能错过最佳入场点

**参数说明**:
- 短期周期越小，信号越敏感但噪音越多
- 长期周期越大，信号越稳定但滞后性越强
- EMA比SMA更敏感，WMA介于两者之间
        """.strip()