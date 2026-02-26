"""
Z-Score移动平均平稳化策略 (Z-Score MA Stationary Strategy)

基于Z-Score标准化的移动平均线平稳化交易策略，通过统计方法消除MA的非平稳性，
提高信号质量和策略稳定性。结合Z-Score、相对强度和动量确认等多重过滤机制。
"""

from typing import List, Dict, Any
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

from ..base import BaseStrategy, StrategyMetadata, StrategyCategory, RiskLevel, ParameterSchema, TradingSignal


class ZScoreMAStationaryStrategy(BaseStrategy):
    """Z-Score移动平均平稳化策略"""
    
    def _create_metadata(self) -> StrategyMetadata:
        """创建策略元数据"""
        return StrategyMetadata(
            id="zscore_ma_stationary_strategy",
            name="Z-Score移动平均平稳化策略",
            description="基于Z-Score标准化的移动平均线平稳化策略，使用统计方法消除非平稳性，提高信号质量和策略稳定性。",
            category=StrategyCategory.TREND,
            author="quant_researcher",
            version="1.0.0",
            tags=["平稳化", "移动平均", "Z-Score", "相对强度", "统计套利"],
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
                max_value=30,
                description="快速移动平均周期",
                required=True
            ),
            ParameterSchema(
                name="slow_period",
                type="int",
                default=30,
                min_value=20,
                max_value=100,
                description="慢速移动平均周期",
                required=True
            ),
            ParameterSchema(
                name="zscore_lookback",
                type="int",
                default=60,
                min_value=30,
                max_value=120,
                description="Z-Score计算回望期",
                required=True
            ),
            ParameterSchema(
                name="zscore_threshold",
                type="float",
                default=1.5,
                min_value=0.5,
                max_value=3.0,
                description="Z-Score信号阈值",
                required=True
            ),
            ParameterSchema(
                name="rs_threshold",
                type="float",
                default=1.0,
                min_value=0.5,
                max_value=2.5,
                description="相对强度信号阈值",
                required=True
            ),
            ParameterSchema(
                name="volume_filter",
                type="bool",
                default=True,
                description="是否启用成交量过滤",
                required=False
            ),
            ParameterSchema(
                name="momentum_filter",
                type="bool",
                default=True,
                description="是否启用动量过滤",
                required=False
            ),
            ParameterSchema(
                name="ma_type",
                type="str",
                default="EMA",
                description="移动平均类型: SMA, EMA",
                required=False
            ),
            ParameterSchema(
                name="min_confidence",
                type="float",
                default=0.6,
                min_value=0.3,
                max_value=1.0,
                description="最小信号置信度",
                required=False
            )
        ]
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """计算平稳化移动平均指标"""
        df = data.copy()
        
        # 获取参数
        fast_period = self.params.get('fast_period', 10)
        slow_period = self.params.get('slow_period', 30)
        zscore_lookback = self.params.get('zscore_lookback', 60)
        ma_type = self.params.get('ma_type', 'EMA')
        
        # 1. 计算基础移动平均
        if ma_type == 'EMA':
            df['ma_fast'] = df['close'].ewm(span=fast_period, adjust=False).mean()
            df['ma_slow'] = df['close'].ewm(span=slow_period, adjust=False).mean()
        else:  # SMA
            df['ma_fast'] = df['close'].rolling(fast_period).mean()
            df['ma_slow'] = df['close'].rolling(slow_period).mean()
        
        # 2. 计算MA价差（核心信号源）
        df['ma_spread'] = df['ma_fast'] - df['ma_slow']
        df['ma_spread_pct'] = df['ma_spread'] / df['close']  # 标准化价差
        
        # 3. 平稳化处理
        # 方法1: Z-Score标准化
        df['ma_spread_mean'] = df['ma_spread'].rolling(zscore_lookback).mean()
        df['ma_spread_std'] = df['ma_spread'].rolling(zscore_lookback).std()
        df['ma_spread_zscore'] = (df['ma_spread'] - df['ma_spread_mean']) / df['ma_spread_std']
        
        # 方法2: 相对强度分析
        df['ma_relative_strength'] = df['ma_fast'] / df['ma_slow'] - 1
        df['ma_rs_mean'] = df['ma_relative_strength'].rolling(zscore_lookback).mean()
        df['ma_rs_std'] = df['ma_relative_strength'].rolling(zscore_lookback).std()
        df['ma_rs_zscore'] = (df['ma_relative_strength'] - df['ma_rs_mean']) / df['ma_rs_std']
        
        # 方法3: 价格相对MA的标准化
        df['price_ma_deviation'] = (df['close'] - df['ma_slow']) / df['ma_slow']
        df['price_ma_zscore'] = (
            (df['price_ma_deviation'] - df['price_ma_deviation'].rolling(zscore_lookback).mean()) /
            df['price_ma_deviation'].rolling(zscore_lookback).std()
        )
        
        # 4. 辅助指标
        # 成交量相对强度
        if 'volume' in df.columns:
            df['volume_ma'] = df['volume'].rolling(20).mean()
            df['volume_ratio'] = df['volume'] / df['volume_ma']
        else:
            df['volume_ratio'] = 1.0
        
        # 价格动量
        df['momentum_5'] = df['close'].pct_change(5)
        df['momentum_10'] = df['close'].pct_change(10)
        
        # ATR用于风险控制
        df['high_low'] = df['high'] - df['low']
        df['high_close'] = np.abs(df['high'] - df['close'].shift(1))
        df['low_close'] = np.abs(df['low'] - df['close'].shift(1))
        df['true_range'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
        df['atr'] = df['true_range'].rolling(14).mean()
        
        return df
    
    def generate_signals(self, data: pd.DataFrame) -> List[TradingSignal]:
        """生成交易信号"""
        df = self.calculate_indicators(data)
        signals = []
        
        # 获取参数
        zscore_threshold = self.params.get('zscore_threshold', 1.5)
        rs_threshold = self.params.get('rs_threshold', 1.0)
        volume_filter = self.params.get('volume_filter', True)
        momentum_filter = self.params.get('momentum_filter', True)
        min_confidence = self.params.get('min_confidence', 0.6)
        
        # 确保有时间戳列
        if 'timestamp' not in df.columns:
            if df.index.name == 'timestamp' or 'date' in str(df.index.dtype):
                df = df.reset_index()
                df.rename(columns={df.columns[0]: 'timestamp'}, inplace=True)
            else:
                df['timestamp'] = pd.date_range(start='2023-01-01', periods=len(df), freq='D')
        
        # 假设有symbol列，如果没有则使用默认值
        symbol = df['symbol'].iloc[0] if 'symbol' in df.columns else 'UNKNOWN'
        
        # 生成信号
        for idx, row in df.iterrows():
            # 跳过数据不足的行
            if (pd.isna(row['ma_spread_zscore']) or 
                pd.isna(row['ma_rs_zscore']) or 
                pd.isna(row['price_ma_zscore'])):
                continue
            
            timestamp = pd.to_datetime(row['timestamp'])
            price = row['close']
            
            # 计算综合信号强度
            signal_strength = self._calculate_signal_strength(row, zscore_threshold, rs_threshold)
            
            if abs(signal_strength) < 0.3:  # 信号太弱，跳过
                continue
            
            # 应用过滤条件
            if not self._apply_filters(row, volume_filter, momentum_filter):
                continue
            
            # 计算信号置信度
            confidence = self._calculate_confidence(row, signal_strength)
            
            if confidence < min_confidence:
                continue
            
            # 生成交易信号
            if signal_strength > 0.5:  # 买入信号
                signal = TradingSignal(
                    timestamp=timestamp,
                    symbol=symbol,
                    action='buy',
                    price=price,
                    confidence=confidence,
                    reason=self._get_signal_reason(row, 'buy')
                )
                signals.append(signal)
            
            elif signal_strength < -0.5:  # 卖出信号
                signal = TradingSignal(
                    timestamp=timestamp,
                    symbol=symbol,
                    action='sell',
                    price=price,
                    confidence=confidence,
                    reason=self._get_signal_reason(row, 'sell')
                )
                signals.append(signal)
        
        return signals
    
    def _calculate_signal_strength(self, row: pd.Series, zscore_threshold: float, rs_threshold: float) -> float:
        """计算综合信号强度"""
        
        # Z-Score信号 (权重: 40%)
        zscore_signal = 0
        if row['ma_spread_zscore'] > zscore_threshold:
            zscore_signal = min(row['ma_spread_zscore'] / zscore_threshold, 2.0) * 0.4
        elif row['ma_spread_zscore'] < -zscore_threshold:
            zscore_signal = max(row['ma_spread_zscore'] / zscore_threshold, -2.0) * 0.4
        
        # 相对强度信号 (权重: 30%)
        rs_signal = 0
        if row['ma_rs_zscore'] > rs_threshold:
            rs_signal = min(row['ma_rs_zscore'] / rs_threshold, 2.0) * 0.3
        elif row['ma_rs_zscore'] < -rs_threshold:
            rs_signal = max(row['ma_rs_zscore'] / rs_threshold, -2.0) * 0.3
        
        # 价格相对MA信号 (权重: 30%)
        price_ma_signal = 0
        if row['price_ma_zscore'] > 1.0:
            price_ma_signal = min(row['price_ma_zscore'], 2.0) * 0.3
        elif row['price_ma_zscore'] < -1.0:
            price_ma_signal = max(row['price_ma_zscore'], -2.0) * 0.3
        
        # 综合信号强度
        total_signal = zscore_signal + rs_signal + price_ma_signal
        
        # 限制在[-1, 1]范围内
        return max(-1.0, min(1.0, total_signal))
    
    def _apply_filters(self, row: pd.Series, volume_filter: bool, momentum_filter: bool) -> bool:
        """应用过滤条件"""
        
        # 成交量过滤
        if volume_filter and row['volume_ratio'] < 0.8:
            return False  # 成交量不足，跳过信号
        
        # 动量过滤
        if momentum_filter:
            # 买入信号需要正动量支持
            if (row['ma_spread_zscore'] > 0 and 
                row['momentum_5'] < -0.02):  # 5日动量为负
                return False
            
            # 卖出信号需要负动量支持
            if (row['ma_spread_zscore'] < 0 and 
                row['momentum_5'] > 0.02):  # 5日动量为正
                return False
        
        return True
    
    def _calculate_confidence(self, row: pd.Series, signal_strength: float) -> float:
        """计算信号置信度"""
        
        # 基础置信度基于信号强度
        base_confidence = min(abs(signal_strength), 1.0)
        
        # 成交量加成
        volume_boost = min((row['volume_ratio'] - 1.0) * 0.2, 0.2) if row['volume_ratio'] > 1.0 else 0
        
        # 动量一致性加成
        momentum_boost = 0
        if signal_strength > 0 and row['momentum_5'] > 0:
            momentum_boost = min(row['momentum_5'] * 5, 0.15)
        elif signal_strength < 0 and row['momentum_5'] < 0:
            momentum_boost = min(abs(row['momentum_5']) * 5, 0.15)
        
        # Z-Score极值加成
        zscore_boost = 0
        if abs(row['ma_spread_zscore']) > 2.0:
            zscore_boost = min((abs(row['ma_spread_zscore']) - 2.0) * 0.1, 0.1)
        
        # 综合置信度
        total_confidence = base_confidence + volume_boost + momentum_boost + zscore_boost
        
        return max(0.3, min(1.0, total_confidence))
    
    def _get_signal_reason(self, row: pd.Series, action: str) -> str:
        """获取信号原因说明"""
        
        reasons = []
        
        # Z-Score信号
        if abs(row['ma_spread_zscore']) > self.params.get('zscore_threshold', 1.5):
            reasons.append(f"MA价差Z-Score: {row['ma_spread_zscore']:.2f}")
        
        # 相对强度信号
        if abs(row['ma_rs_zscore']) > self.params.get('rs_threshold', 1.0):
            reasons.append(f"相对强度Z-Score: {row['ma_rs_zscore']:.2f}")
        
        # 价格偏离信号
        if abs(row['price_ma_zscore']) > 1.0:
            reasons.append(f"价格偏离Z-Score: {row['price_ma_zscore']:.2f}")
        
        # 成交量确认
        if row['volume_ratio'] > 1.2:
            reasons.append(f"成交量放大: {row['volume_ratio']:.1f}x")
        
        # 动量确认
        if abs(row['momentum_5']) > 0.01:
            reasons.append(f"5日动量: {row['momentum_5']:.2%}")
        
        action_text = "买入" if action == 'buy' else "卖出"
        return f"{action_text}信号 - " + ", ".join(reasons)
    
    def _explain_strategy_logic(self) -> str:
        """解释策略逻辑"""
        fast_period = self.params.get('fast_period', 10)
        slow_period = self.params.get('slow_period', 30)
        zscore_lookback = self.params.get('zscore_lookback', 60)
        zscore_threshold = self.params.get('zscore_threshold', 1.5)
        
        return f"""
平稳化移动平均策略是对传统MA策略的重大改进：

**核心创新**:
1. 平稳化处理：将非平稳的MA序列转换为平稳序列
2. Z-Score标准化：基于{zscore_lookback}日滚动窗口标准化MA价差
3. 相对强度分析：计算快慢MA的相对强度并标准化
4. 多重确认机制：结合成交量、动量等多个维度

**信号生成逻辑**:
1. 计算{fast_period}日和{slow_period}日移动平均线
2. 计算MA价差的Z-Score，阈值为±{zscore_threshold}
3. 计算相对强度的Z-Score，识别MA背离
4. 结合价格相对MA的偏离程度
5. 通过成交量和动量过滤假信号

**平稳化优势**:
- 消除MA的趋势性和异方差性
- 提高信号的统计显著性
- 减少假突破和滞后性问题
- 更好的风险控制和仓位管理

**适用场景**:
- 中长期趋势跟踪
- 统计套利策略
- 均值回归交易
- 多品种组合策略

**风险控制**:
- 基于ATR的动态止损
- 多重过滤减少假信号
- 置信度评分系统
- 严格的参数验证机制
        """.strip()
    
    def get_risk_metrics(self, data: pd.DataFrame) -> Dict[str, float]:
        """计算策略风险指标"""
        df = self.calculate_indicators(data)
        
        if len(df) < self.params.get('zscore_lookback', 60):
            return {"insufficient_data": True}
        
        # 计算各种风险指标
        ma_spread_volatility = df['ma_spread_zscore'].std()
        max_zscore = df['ma_spread_zscore'].abs().max()
        signal_frequency = (df['ma_spread_zscore'].abs() > self.params.get('zscore_threshold', 1.5)).mean()
        
        return {
            "ma_spread_volatility": ma_spread_volatility,
            "max_zscore": max_zscore,
            "signal_frequency": signal_frequency,
            "avg_atr_pct": (df['atr'] / df['close']).mean() if 'atr' in df.columns else 0.02
        }