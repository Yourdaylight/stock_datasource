"""
KDJ策略 (KDJ Stochastic Strategy)

基于KDJ随机指标的交易策略。
当K线上穿D线且处于低位时买入，K线下穿D线且处于高位时卖出。
"""

from typing import List, Dict, Any
import pandas as pd
import numpy as np
from datetime import datetime

from ..base import BaseStrategy, StrategyMetadata, StrategyCategory, RiskLevel, ParameterSchema, TradingSignal


class KDJStrategy(BaseStrategy):
    """KDJ策略"""
    
    def _create_metadata(self) -> StrategyMetadata:
        """创建策略元数据"""
        return StrategyMetadata(
            id="kdj_strategy",
            name="KDJ策略",
            description="基于KDJ随机指标的震荡策略。K线上穿D线低位买入，下穿高位卖出。",
            category=StrategyCategory.MEAN_REVERSION,
            author="system",
            version="1.0.0",
            tags=["KDJ", "随机指标", "震荡策略", "超买超卖"],
            risk_level=RiskLevel.MEDIUM
        )
    
    def get_parameter_schema(self) -> List[ParameterSchema]:
        """获取参数配置schema"""
        return [
            ParameterSchema(
                name="k_period",
                type="int",
                default=9,
                min_value=5,
                max_value=30,
                description="K值计算周期",
                required=True
            ),
            ParameterSchema(
                name="d_period",
                type="int",
                default=3,
                min_value=2,
                max_value=10,
                description="D值平滑周期",
                required=True
            ),
            ParameterSchema(
                name="j_period",
                type="int",
                default=3,
                min_value=2,
                max_value=10,
                description="J值平滑周期",
                required=True
            ),
            ParameterSchema(
                name="oversold_threshold",
                type="float",
                default=20.0,
                min_value=10.0,
                max_value=30.0,
                description="超卖阈值",
                required=True
            ),
            ParameterSchema(
                name="overbought_threshold",
                type="float",
                default=80.0,
                min_value=70.0,
                max_value=90.0,
                description="超买阈值",
                required=True
            ),
            ParameterSchema(
                name="use_j_filter",
                type="bool",
                default=True,
                description="是否使用J值过滤信号",
                required=False
            )
        ]
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """计算KDJ指标"""
        df = data.copy()
        
        k_period = self.params.get('k_period', 9)
        d_period = self.params.get('d_period', 3)
        j_period = self.params.get('j_period', 3)
        
        # 计算最高价和最低价的滚动窗口
        df['highest_high'] = df['high'].rolling(window=k_period).max()
        df['lowest_low'] = df['low'].rolling(window=k_period).min()
        
        # 计算RSV (Raw Stochastic Value)
        df['rsv'] = ((df['close'] - df['lowest_low']) / 
                     (df['highest_high'] - df['lowest_low']) * 100)
        
        # 处理除零情况
        df['rsv'] = df['rsv'].fillna(50)
        
        # 计算K值 (K = 2/3 * 前一日K值 + 1/3 * 当日RSV)
        df['k'] = 50  # 初始值
        for i in range(1, len(df)):
            if pd.notna(df['rsv'].iloc[i]):
                df.loc[df.index[i], 'k'] = (2/3 * df['k'].iloc[i-1] + 
                                           1/3 * df['rsv'].iloc[i])
        
        # 计算D值 (D = 2/3 * 前一日D值 + 1/3 * 当日K值)
        df['d'] = 50  # 初始值
        for i in range(1, len(df)):
            df.loc[df.index[i], 'd'] = (2/3 * df['d'].iloc[i-1] + 
                                       1/3 * df['k'].iloc[i])
        
        # 计算J值 (J = 3K - 2D)
        df['j'] = 3 * df['k'] - 2 * df['d']
        
        # 生成交易信号
        df['kdj_signal'] = 0
        
        oversold = self.params.get('oversold_threshold', 20.0)
        overbought = self.params.get('overbought_threshold', 80.0)
        use_j_filter = self.params.get('use_j_filter', True)
        
        # 买入信号：K上穿D且在低位
        buy_condition = ((df['k'] > df['d']) & 
                        (df['k'].shift(1) <= df['d'].shift(1)) & 
                        (df['k'] < oversold + 10))  # 在超卖区域附近
        
        if use_j_filter:
            buy_condition = buy_condition & (df['j'] < oversold)
        
        df.loc[buy_condition, 'kdj_signal'] = 1
        
        # 卖出信号：K下穿D且在高位
        sell_condition = ((df['k'] < df['d']) & 
                         (df['k'].shift(1) >= df['d'].shift(1)) & 
                         (df['k'] > overbought - 10))  # 在超买区域附近
        
        if use_j_filter:
            sell_condition = sell_condition & (df['j'] > overbought)
        
        df.loc[sell_condition, 'kdj_signal'] = -1
        
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
            if (pd.isna(row['kdj_signal']) or row['kdj_signal'] == 0 or 
                pd.isna(row['k']) or pd.isna(row['d'])):
                continue
            
            timestamp = pd.to_datetime(row['timestamp'])
            price = row['close']
            
            if row['kdj_signal'] == 1:  # 买入信号
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
            
            elif row['kdj_signal'] == -1:  # 卖出信号
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
        k_val = row['k']
        d_val = row['d']
        j_val = row['j'] if 'j' in row else None
        
        reason = f"K线上穿D线低位金叉 (K: {k_val:.2f}, D: {d_val:.2f}"
        if j_val is not None and self.params.get('use_j_filter', True):
            reason += f", J: {j_val:.2f}"
        reason += ")"
        
        return reason
    
    def _get_sell_reason(self, row: pd.Series) -> str:
        """获取卖出信号原因"""
        k_val = row['k']
        d_val = row['d']
        j_val = row['j'] if 'j' in row else None
        
        reason = f"K线下穿D线高位死叉 (K: {k_val:.2f}, D: {d_val:.2f}"
        if j_val is not None and self.params.get('use_j_filter', True):
            reason += f", J: {j_val:.2f}"
        reason += ")"
        
        return reason
    
    def _calculate_signal_confidence(self, row: pd.Series, signal_type: str) -> float:
        """计算信号置信度"""
        k_val = row['k']
        d_val = row['d']
        kd_diff = abs(k_val - d_val)
        
        oversold = self.params.get('oversold_threshold', 20.0)
        overbought = self.params.get('overbought_threshold', 80.0)
        
        if signal_type == 'buy':
            # K值越低且KD差值越大，置信度越高
            position_factor = max(0, (oversold + 20 - k_val) / (oversold + 20))
            diff_factor = min(kd_diff / 20, 1.0)
        else:  # sell
            # K值越高且KD差值越大，置信度越高
            position_factor = max(0, (k_val - overbought + 20) / (100 - overbought + 20))
            diff_factor = min(kd_diff / 20, 1.0)
        
        confidence = (position_factor + diff_factor) / 2 + 0.3
        
        return max(0.3, min(1.0, confidence))
    
    def _explain_strategy_logic(self) -> str:
        """解释策略逻辑"""
        k_period = self.params.get('k_period', 9)
        oversold = self.params.get('oversold_threshold', 20.0)
        overbought = self.params.get('overbought_threshold', 80.0)
        use_j_filter = self.params.get('use_j_filter', True)
        
        return f"""
KDJ策略是基于随机指标的震荡交易策略：

**核心逻辑**:
1. 计算{k_period}日RSV = (收盘价 - 最低价) / (最高价 - 最低价) × 100
2. K值 = 2/3 × 前日K值 + 1/3 × 当日RSV
3. D值 = 2/3 × 前日D值 + 1/3 × 当日K值
4. J值 = 3K - 2D

**交易信号**:
- K线上穿D线且K < {oversold + 10} 时买入
- K线下穿D线且K > {overbought - 10} 时卖出
{'- 使用J值作为辅助过滤条件' if use_j_filter else ''}

**指标特点**:
- K值反映当前价格在近期价格区间中的位置
- D值是K值的平滑线，减少噪音
- J值更敏感，能提前反映转向信号

**适用场景**:
- 震荡行情中表现优异
- 能够较好地捕捉短期反转
- 适合高频交易和短线操作

**策略优势**:
- 信号相对及时，滞后性较小
- 能够识别超买超卖状态
- KDJ组合提供多重确认

**注意事项**:
- 在强趋势中可能产生过多假信号
- 建议结合趋势指标使用
- 注意KDJ钝化现象，特别是在极端行情中
        """.strip()