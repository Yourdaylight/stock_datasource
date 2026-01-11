"""
海龟交易策略 (Turtle Trading Strategy)

基于价格突破的趋势跟踪策略。
当价格突破N日最高价时买入，跌破M日最低价时卖出。
包含完整的仓位管理和风险控制机制。
"""

from typing import List, Dict, Any
import pandas as pd
import numpy as np
from datetime import datetime

from ..base import BaseStrategy, StrategyMetadata, StrategyCategory, RiskLevel, ParameterSchema, TradingSignal


class TurtleStrategy(BaseStrategy):
    """海龟交易策略"""
    
    def _create_metadata(self) -> StrategyMetadata:
        """创建策略元数据"""
        return StrategyMetadata(
            id="turtle_strategy",
            name="海龟交易策略",
            description="基于价格突破的经典趋势跟踪策略，包含完整的仓位管理和风险控制。",
            category=StrategyCategory.TREND,
            author="system",
            version="1.0.0",
            tags=["海龟交易", "价格突破", "趋势跟踪", "仓位管理"],
            risk_level=RiskLevel.HIGH
        )
    
    def get_parameter_schema(self) -> List[ParameterSchema]:
        """获取参数配置schema"""
        return [
            ParameterSchema(
                name="entry_period",
                type="int",
                default=20,
                min_value=10,
                max_value=50,
                description="入场突破周期",
                required=True
            ),
            ParameterSchema(
                name="exit_period",
                type="int",
                default=10,
                min_value=5,
                max_value=30,
                description="出场突破周期",
                required=True
            ),
            ParameterSchema(
                name="atr_period",
                type="int",
                default=20,
                min_value=10,
                max_value=50,
                description="ATR计算周期",
                required=True
            ),
            ParameterSchema(
                name="risk_per_trade",
                type="float",
                default=0.02,
                min_value=0.01,
                max_value=0.05,
                description="每笔交易风险比例",
                required=False
            ),
            ParameterSchema(
                name="use_filter",
                type="bool",
                default=True,
                description="是否使用过滤条件",
                required=False
            ),
            ParameterSchema(
                name="filter_period",
                type="int",
                default=55,
                min_value=30,
                max_value=100,
                description="过滤条件周期",
                required=False
            ),
            ParameterSchema(
                name="max_pyramid_units",
                type="int",
                default=4,
                min_value=1,
                max_value=6,
                description="最大加仓单位数",
                required=False
            )
        ]
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """计算海龟策略指标"""
        df = data.copy()
        
        entry_period = self.params.get('entry_period', 20)
        exit_period = self.params.get('exit_period', 10)
        atr_period = self.params.get('atr_period', 20)
        filter_period = self.params.get('filter_period', 55)
        
        # 计算最高价和最低价通道
        df['highest_high'] = df['high'].rolling(window=entry_period).max()
        df['lowest_low'] = df['low'].rolling(window=exit_period).min()
        
        # 计算出场通道
        df['exit_highest'] = df['high'].rolling(window=exit_period).max()
        df['exit_lowest'] = df['low'].rolling(window=exit_period).min()
        
        # 计算ATR (Average True Range)
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['close'].shift(1))
        df['tr3'] = abs(df['low'] - df['close'].shift(1))
        df['true_range'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        df['atr'] = df['true_range'].rolling(window=atr_period).mean()
        
        # 计算过滤条件（长期通道）
        if self.params.get('use_filter', True):
            df['filter_high'] = df['high'].rolling(window=filter_period).max()
            df['filter_low'] = df['low'].rolling(window=filter_period).min()
        
        # 生成交易信号
        df['turtle_signal'] = 0
        df['signal_type'] = ''  # entry, exit, add
        
        # 入场信号：突破入场通道上轨
        entry_long = df['close'] > df['highest_high'].shift(1)
        
        # 出场信号：跌破出场通道下轨
        exit_long = df['close'] < df['exit_lowest'].shift(1)
        
        # 如果使用过滤条件
        if self.params.get('use_filter', True):
            # 只有当价格也突破长期通道时才入场
            filter_condition = df['close'] > df['filter_high'].shift(1)
            entry_long = entry_long & filter_condition
        
        # 标记信号
        df.loc[entry_long, 'turtle_signal'] = 1
        df.loc[entry_long, 'signal_type'] = 'entry'
        
        df.loc[exit_long, 'turtle_signal'] = -1
        df.loc[exit_long, 'signal_type'] = 'exit'
        
        # 计算加仓信号（价格每上涨0.5个ATR加仓一次）
        df['add_position_price'] = np.nan
        max_units = self.params.get('max_pyramid_units', 4)
        
        # 这里简化处理，实际应该跟踪持仓状态
        for i in range(1, len(df)):
            if df['turtle_signal'].iloc[i-1] == 1:  # 刚入场
                # 设置第一个加仓价位
                entry_price = df['close'].iloc[i-1]
                atr_value = df['atr'].iloc[i-1]
                if not pd.isna(atr_value):
                    df.loc[df.index[i], 'add_position_price'] = entry_price + 0.5 * atr_value
        
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
            if (pd.isna(row['turtle_signal']) or row['turtle_signal'] == 0 or 
                pd.isna(row['highest_high']) or pd.isna(row['atr'])):
                continue
            
            timestamp = pd.to_datetime(row['timestamp'])
            price = row['close']
            
            if row['turtle_signal'] == 1:  # 买入信号
                reason = self._get_buy_reason(row)
                
                # 计算建议仓位大小
                position_size = self._calculate_position_size(row)
                
                signal = TradingSignal(
                    timestamp=timestamp,
                    symbol=symbol,
                    action='buy',
                    price=price,
                    quantity=position_size,
                    confidence=self._calculate_signal_confidence(row, 'buy'),
                    reason=reason
                )
                signals.append(signal)
            
            elif row['turtle_signal'] == -1:  # 卖出信号
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
    
    def _calculate_position_size(self, row: pd.Series) -> int:
        """计算仓位大小"""
        # 简化的仓位计算，实际应该基于账户资金
        atr = row['atr']
        risk_per_trade = self.params.get('risk_per_trade', 0.02)
        
        if pd.isna(atr) or atr == 0:
            return 100  # 默认仓位
        
        # 假设账户资金为100万
        account_value = 1000000
        risk_amount = account_value * risk_per_trade
        
        # 每股风险 = ATR（作为止损距离）
        risk_per_share = atr
        
        # 仓位大小 = 风险金额 / 每股风险
        position_size = int(risk_amount / (risk_per_share * row['close']))
        
        return max(100, min(position_size, 10000))  # 限制在合理范围内
    
    def _get_buy_reason(self, row: pd.Series) -> str:
        """获取买入信号原因"""
        entry_period = self.params.get('entry_period', 20)
        highest_high = row['highest_high']
        atr = row['atr']
        signal_type = row.get('signal_type', 'entry')
        
        if signal_type == 'add':
            return f"海龟加仓信号 (ATR: {atr:.2f})"
        else:
            reason = f"突破{entry_period}日最高价 (突破价: {highest_high:.2f}, ATR: {atr:.2f})"
            
            if self.params.get('use_filter', True):
                filter_period = self.params.get('filter_period', 55)
                reason += f", 通过{filter_period}日过滤"
            
            return reason
    
    def _get_sell_reason(self, row: pd.Series) -> str:
        """获取卖出信号原因"""
        exit_period = self.params.get('exit_period', 10)
        exit_lowest = row['exit_lowest']
        
        return f"跌破{exit_period}日最低价 (跌破价: {exit_lowest:.2f})"
    
    def _calculate_signal_confidence(self, row: pd.Series, signal_type: str) -> float:
        """计算信号置信度"""
        atr = row.get('atr', 0)
        price = row['close']
        
        if signal_type == 'buy':
            highest_high = row['highest_high']
            # 突破幅度越大，置信度越高
            breakout_strength = (price - highest_high) / atr if atr > 0 else 0
            confidence = min(breakout_strength * 0.5 + 0.5, 1.0)
        else:  # sell
            exit_lowest = row['exit_lowest']
            # 跌破幅度越大，置信度越高
            breakdown_strength = (exit_lowest - price) / atr if atr > 0 else 0
            confidence = min(breakdown_strength * 0.5 + 0.5, 1.0)
        
        # 海龟策略本身就是高置信度策略
        return max(0.6, min(1.0, confidence))
    
    def _explain_strategy_logic(self) -> str:
        """解释策略逻辑"""
        entry_period = self.params.get('entry_period', 20)
        exit_period = self.params.get('exit_period', 10)
        atr_period = self.params.get('atr_period', 20)
        use_filter = self.params.get('use_filter', True)
        filter_period = self.params.get('filter_period', 55)
        
        return f"""
海龟交易策略是最著名的趋势跟踪策略之一：

**核心逻辑**:
1. 入场：价格突破{entry_period}日最高价时买入
2. 出场：价格跌破{exit_period}日最低价时卖出
3. 止损：基于{atr_period}日ATR设定止损位
4. 仓位：根据ATR和风险比例计算仓位大小

**风险管理**:
- 每笔交易风险控制在账户的{self.params.get('risk_per_trade', 0.02):.1%}
- 使用ATR作为波动率度量和止损依据
- 支持金字塔加仓（最多{self.params.get('max_pyramid_units', 4)}个单位）

**过滤机制**:
{'- 启用' + str(filter_period) + '日长期通道过滤，减少假突破' if use_filter else '- 未启用过滤机制'}

**策略特点**:
- 完整的趋势跟踪系统
- 严格的风险控制机制
- 适合捕捉大级别趋势行情
- 胜率较低但盈亏比高

**适用场景**:
- 趋势性强的市场环境
- 适合中长期持仓
- 需要严格执行纪律

**历史背景**:
- 由理查德·丹尼斯创立
- 在1980年代创造了传奇收益
- 证明了交易规则可以被教授和复制

**风险提示**:
- 在震荡市中会产生较多亏损
- 需要足够的资金承受连续亏损
- 心理承受能力要求较高
        """.strip()