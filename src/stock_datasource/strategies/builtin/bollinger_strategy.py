"""
布林带策略 (Bollinger Bands Strategy)

基于布林带上下轨的均值回归策略。
当价格触及下轨时买入，触及上轨时卖出。
"""

from typing import List, Dict, Any
import pandas as pd
import numpy as np
from datetime import datetime

from ..base import BaseStrategy, StrategyMetadata, StrategyCategory, RiskLevel, ParameterSchema, TradingSignal


class BollingerBandsStrategy(BaseStrategy):
    """布林带策略"""
    
    def _create_metadata(self) -> StrategyMetadata:
        """创建策略元数据"""
        return StrategyMetadata(
            id="bollinger_strategy",
            name="布林带策略",
            description="基于布林带上下轨的均值回归策略。价格触及下轨买入，触及上轨卖出。",
            category=StrategyCategory.MEAN_REVERSION,
            author="system",
            version="1.0.0",
            tags=["布林带", "均值回归", "波动率", "统计套利"],
            risk_level=RiskLevel.MEDIUM
        )
    
    def get_parameter_schema(self) -> List[ParameterSchema]:
        """获取参数配置schema"""
        return [
            ParameterSchema(
                name="period",
                type="int",
                default=20,
                min_value=10,
                max_value=50,
                description="移动平均周期",
                required=True
            ),
            ParameterSchema(
                name="std_dev",
                type="float",
                default=2.0,
                min_value=1.0,
                max_value=3.0,
                description="标准差倍数",
                required=True
            ),
            ParameterSchema(
                name="entry_threshold",
                type="float",
                default=0.02,
                min_value=0.0,
                max_value=0.1,
                description="入场阈值（价格偏离轨道的比例）",
                required=False
            ),
            ParameterSchema(
                name="use_squeeze",
                type="bool",
                default=False,
                description="是否使用布林带收缩信号",
                required=False
            ),
            ParameterSchema(
                name="squeeze_threshold",
                type="float",
                default=0.05,
                min_value=0.01,
                max_value=0.2,
                description="收缩阈值（带宽占中轨的比例）",
                required=False
            )
        ]
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """计算布林带指标"""
        df = data.copy()
        
        period = self.params.get('period', 20)
        std_dev = self.params.get('std_dev', 2.0)
        entry_threshold = self.params.get('entry_threshold', 0.02)
        
        # 计算中轨（移动平均）
        df['bb_middle'] = df['close'].rolling(window=period).mean()
        
        # 计算标准差
        df['bb_std'] = df['close'].rolling(window=period).std()
        
        # 计算上轨和下轨
        df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * std_dev)
        df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * std_dev)
        
        # 计算价格相对位置 %B
        df['bb_percent'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        # 计算带宽
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
        
        # 生成交易信号
        df['bb_signal'] = 0
        
        # 基础信号：价格触及轨道
        # 买入信号：价格跌破下轨
        buy_condition = (df['close'] <= df['bb_lower'] * (1 + entry_threshold))
        
        # 卖出信号：价格突破上轨
        sell_condition = (df['close'] >= df['bb_upper'] * (1 - entry_threshold))
        
        # 如果使用收缩信号
        if self.params.get('use_squeeze', False):
            squeeze_threshold = self.params.get('squeeze_threshold', 0.05)
            
            # 检测布林带收缩（低波动率）
            df['bb_squeeze'] = df['bb_width'] < squeeze_threshold
            
            # 收缩后的突破信号
            squeeze_breakout_up = (df['bb_squeeze'].shift(1) & 
                                  ~df['bb_squeeze'] & 
                                  (df['close'] > df['bb_middle']))
            
            squeeze_breakout_down = (df['bb_squeeze'].shift(1) & 
                                    ~df['bb_squeeze'] & 
                                    (df['close'] < df['bb_middle']))
            
            # 合并信号
            buy_condition = buy_condition | squeeze_breakout_down
            sell_condition = sell_condition | squeeze_breakout_up
        
        df.loc[buy_condition, 'bb_signal'] = 1
        df.loc[sell_condition, 'bb_signal'] = -1
        
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
            if (pd.isna(row['bb_signal']) or row['bb_signal'] == 0 or 
                pd.isna(row['bb_upper']) or pd.isna(row['bb_lower'])):
                continue
            
            timestamp = pd.to_datetime(row['timestamp'])
            price = row['close']
            
            if row['bb_signal'] == 1:  # 买入信号
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
            
            elif row['bb_signal'] == -1:  # 卖出信号
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
        price = row['close']
        lower_band = row['bb_lower']
        middle_band = row['bb_middle']
        
        if self.params.get('use_squeeze', False) and 'bb_squeeze' in row:
            if row.get('bb_squeeze', False):
                return f"布林带收缩后向下突破 (价格: {price:.2f}, 中轨: {middle_band:.2f})"
        
        percent_b = row.get('bb_percent', 0)
        return f"价格触及布林带下轨 (价格: {price:.2f}, 下轨: {lower_band:.2f}, %B: {percent_b:.2f})"
    
    def _get_sell_reason(self, row: pd.Series) -> str:
        """获取卖出信号原因"""
        price = row['close']
        upper_band = row['bb_upper']
        middle_band = row['bb_middle']
        
        if self.params.get('use_squeeze', False) and 'bb_squeeze' in row:
            if row.get('bb_squeeze', False):
                return f"布林带收缩后向上突破 (价格: {price:.2f}, 中轨: {middle_band:.2f})"
        
        percent_b = row.get('bb_percent', 1)
        return f"价格触及布林带上轨 (价格: {price:.2f}, 上轨: {upper_band:.2f}, %B: {percent_b:.2f})"
    
    def _calculate_signal_confidence(self, row: pd.Series, signal_type: str) -> float:
        """计算信号置信度"""
        percent_b = row.get('bb_percent', 0.5)
        bb_width = row.get('bb_width', 0.1)
        
        if signal_type == 'buy':
            # %B越小（越接近下轨），置信度越高
            position_confidence = max(0, (0.2 - percent_b) / 0.2)
        else:  # sell
            # %B越大（越接近上轨），置信度越高
            position_confidence = max(0, (percent_b - 0.8) / 0.2)
        
        # 带宽越窄，均值回归的可能性越大
        width_confidence = max(0, (0.1 - bb_width) / 0.1)
        
        # 综合置信度
        confidence = (position_confidence * 0.7 + width_confidence * 0.3) + 0.3
        
        return max(0.3, min(1.0, confidence))
    
    def _explain_strategy_logic(self) -> str:
        """解释策略逻辑"""
        period = self.params.get('period', 20)
        std_dev = self.params.get('std_dev', 2.0)
        use_squeeze = self.params.get('use_squeeze', False)
        
        return f"""
布林带策略是基于统计学原理的均值回归策略：

**核心逻辑**:
1. 计算{period}日移动平均作为中轨
2. 上轨 = 中轨 + {std_dev} × 标准差
3. 下轨 = 中轨 - {std_dev} × 标准差
4. %B = (价格 - 下轨) / (上轨 - 下轨)

**交易信号**:
- 价格触及或跌破下轨时买入
- 价格触及或突破上轨时卖出
{'- 启用布林带收缩突破信号' if use_squeeze else ''}

**理论基础**:
- 价格在统计上倾向于回归均值
- 约95%的价格应在±2σ范围内
- 轨道突破往往是短期极端情况

**指标含义**:
- 中轨代表价格的均值水平
- 上下轨代表价格的合理波动范围
- 带宽反映市场波动率的大小

**适用场景**:
- 震荡行情中效果显著
- 适合捕捉短期反转机会
- 在低波动率环境下表现较好

**策略优势**:
- 有明确的统计学基础
- 能够动态适应市场波动率
- 提供明确的入场和出场点位

**风险提示**:
- 在强趋势中可能产生连续亏损
- 需要严格的风险管理和止损
- 注意布林带的"走平"现象
        """.strip()