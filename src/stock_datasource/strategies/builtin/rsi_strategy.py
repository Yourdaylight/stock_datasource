"""
RSI策略 (Relative Strength Index Strategy)

基于RSI指标的超买超卖信号进行交易。
当RSI低于超卖线时买入，高于超买线时卖出。
"""

from typing import List, Dict, Any
import pandas as pd
import numpy as np
from datetime import datetime

from ..base import BaseStrategy, StrategyMetadata, StrategyCategory, RiskLevel, ParameterSchema, TradingSignal


class RSIStrategy(BaseStrategy):
    """RSI策略"""
    
    def _create_metadata(self) -> StrategyMetadata:
        """创建策略元数据"""
        return StrategyMetadata(
            id="rsi_strategy",
            name="RSI策略",
            description="基于RSI指标超买超卖的均值回归策略。超卖买入，超买卖出。",
            category=StrategyCategory.MEAN_REVERSION,
            author="system",
            version="1.0.0",
            tags=["RSI", "超买超卖", "均值回归", "震荡指标"],
            risk_level=RiskLevel.MEDIUM
        )
    
    def get_parameter_schema(self) -> List[ParameterSchema]:
        """获取参数配置schema"""
        return [
            ParameterSchema(
                name="period",
                type="int",
                default=14,
                min_value=5,
                max_value=50,
                description="RSI计算周期",
                required=True
            ),
            ParameterSchema(
                name="oversold_threshold",
                type="float",
                default=30.0,
                min_value=10.0,
                max_value=40.0,
                description="超卖阈值",
                required=True
            ),
            ParameterSchema(
                name="overbought_threshold",
                type="float",
                default=70.0,
                min_value=60.0,
                max_value=90.0,
                description="超买阈值",
                required=True
            ),
            ParameterSchema(
                name="use_divergence",
                type="bool",
                default=False,
                description="是否使用背离信号",
                required=False
            )
        ]
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """计算RSI指标"""
        df = data.copy()
        
        period = self.params.get('period', 14)
        oversold = self.params.get('oversold_threshold', 30.0)
        overbought = self.params.get('overbought_threshold', 70.0)
        
        # 计算价格变化
        df['price_change'] = df['close'].diff()
        
        # 计算上涨和下跌
        df['gain'] = df['price_change'].where(df['price_change'] > 0, 0)
        df['loss'] = -df['price_change'].where(df['price_change'] < 0, 0)
        
        # 计算平均收益和平均损失
        df['avg_gain'] = df['gain'].rolling(window=period).mean()
        df['avg_loss'] = df['loss'].rolling(window=period).mean()
        
        # 计算RS和RSI
        df['rs'] = df['avg_gain'] / df['avg_loss']
        df['rsi'] = 100 - (100 / (1 + df['rs']))
        
        # 生成交易信号
        df['rsi_signal'] = 0
        
        # 超卖买入信号
        df.loc[(df['rsi'] < oversold) & (df['rsi'].shift(1) >= oversold), 'rsi_signal'] = 1
        
        # 超买卖出信号
        df.loc[(df['rsi'] > overbought) & (df['rsi'].shift(1) <= overbought), 'rsi_signal'] = -1
        
        # 如果启用背离，添加背离信号
        if self.params.get('use_divergence', False):
            df = self._add_divergence_signals(df)
        
        return df
    
    def _add_divergence_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加背离信号"""
        # 简化的背离检测逻辑
        window = 20  # 检测窗口
        
        for i in range(window, len(df)):
            # 检测价格新高但RSI未创新高（顶背离）
            price_window = df['close'].iloc[i-window:i+1]
            rsi_window = df['rsi'].iloc[i-window:i+1]
            
            if (df['close'].iloc[i] == price_window.max() and 
                df['rsi'].iloc[i] < rsi_window.max() and
                df['rsi'].iloc[i] > self.params.get('overbought_threshold', 70)):
                df.loc[df.index[i], 'rsi_signal'] = -1  # 卖出信号
            
            # 检测价格新低但RSI未创新低（底背离）
            if (df['close'].iloc[i] == price_window.min() and 
                df['rsi'].iloc[i] > rsi_window.min() and
                df['rsi'].iloc[i] < self.params.get('oversold_threshold', 30)):
                df.loc[df.index[i], 'rsi_signal'] = 1  # 买入信号
        
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
            if pd.isna(row['rsi_signal']) or row['rsi_signal'] == 0 or pd.isna(row['rsi']):
                continue
            
            timestamp = pd.to_datetime(row['timestamp'])
            price = row['close']
            rsi_value = row['rsi']
            
            if row['rsi_signal'] == 1:  # 买入信号
                reason = self._get_buy_reason(rsi_value)
                signal = TradingSignal(
                    timestamp=timestamp,
                    symbol=symbol,
                    action='buy',
                    price=price,
                    confidence=self._calculate_signal_confidence(rsi_value, 'buy'),
                    reason=reason
                )
                signals.append(signal)
            
            elif row['rsi_signal'] == -1:  # 卖出信号
                reason = self._get_sell_reason(rsi_value)
                signal = TradingSignal(
                    timestamp=timestamp,
                    symbol=symbol,
                    action='sell',
                    price=price,
                    confidence=self._calculate_signal_confidence(rsi_value, 'sell'),
                    reason=reason
                )
                signals.append(signal)
        
        return signals
    
    def _get_buy_reason(self, rsi_value: float) -> str:
        """获取买入信号原因"""
        oversold = self.params.get('oversold_threshold', 30.0)
        if self.params.get('use_divergence', False) and rsi_value > oversold:
            return f"RSI底背离信号 (RSI: {rsi_value:.2f})"
        else:
            return f"RSI超卖信号 (RSI: {rsi_value:.2f} < {oversold})"
    
    def _get_sell_reason(self, rsi_value: float) -> str:
        """获取卖出信号原因"""
        overbought = self.params.get('overbought_threshold', 70.0)
        if self.params.get('use_divergence', False) and rsi_value < overbought:
            return f"RSI顶背离信号 (RSI: {rsi_value:.2f})"
        else:
            return f"RSI超买信号 (RSI: {rsi_value:.2f} > {overbought})"
    
    def _calculate_signal_confidence(self, rsi_value: float, signal_type: str) -> float:
        """计算信号置信度"""
        oversold = self.params.get('oversold_threshold', 30.0)
        overbought = self.params.get('overbought_threshold', 70.0)
        
        if signal_type == 'buy':
            # RSI越低，买入信号置信度越高
            if rsi_value <= oversold:
                confidence = (oversold - rsi_value) / oversold + 0.5
            else:
                confidence = 0.4  # 背离信号的基础置信度
        else:  # sell
            # RSI越高，卖出信号置信度越高
            if rsi_value >= overbought:
                confidence = (rsi_value - overbought) / (100 - overbought) + 0.5
            else:
                confidence = 0.4  # 背离信号的基础置信度
        
        return max(0.3, min(1.0, confidence))
    
    def _explain_strategy_logic(self) -> str:
        """解释策略逻辑"""
        period = self.params.get('period', 14)
        oversold = self.params.get('oversold_threshold', 30.0)
        overbought = self.params.get('overbought_threshold', 70.0)
        use_divergence = self.params.get('use_divergence', False)
        
        return f"""
RSI策略是基于相对强弱指数的均值回归策略：

**核心逻辑**:
1. 计算{period}日RSI指标
2. RSI = 100 - (100 / (1 + RS))
3. RS = 平均收益 / 平均损失

**交易信号**:
- RSI < {oversold} 时买入（超卖）
- RSI > {overbought} 时卖出（超买）
{'- 启用背离信号检测' if use_divergence else ''}

**指标含义**:
- RSI在0-100之间波动
- RSI > 70通常表示超买
- RSI < 30通常表示超卖
- RSI = 50表示多空力量平衡

**适用场景**:
- 震荡行情中效果较好
- 适合捕捉短期反转机会
- 在强趋势中可能产生过早信号

**策略优势**:
- 能够识别超买超卖状态
- 信号相对明确，易于执行
- 可以结合背离提高信号质量

**风险提示**:
- 在强趋势中RSI可能长期处于极值区域
- 建议结合趋势指标过滤信号
- 注意设置合理的止损位
        """.strip()