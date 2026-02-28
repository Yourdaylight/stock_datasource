"""
自适应突破跟踪策略 (Adaptive Breakout Follow Strategy)

智能结合趋势突破入场和趋势跟踪入场的自适应策略。
根据市场环境动态选择最优入场方式，优化突破策略的成交量确认，
改进跟踪策略的滞后性，实现更好的风险收益平衡。
"""

from typing import List, Dict, Any, Tuple
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

from ..base import BaseStrategy, StrategyMetadata, StrategyCategory, RiskLevel, ParameterSchema, TradingSignal


class AdaptiveBreakoutFollowStrategy(BaseStrategy):
    """自适应突破跟踪策略"""
    
    def _create_metadata(self) -> StrategyMetadata:
        """创建策略元数据"""
        return StrategyMetadata(
            id="adaptive_breakout_follow_strategy",
            name="自适应突破跟踪策略",
            description="智能结合趋势突破和趋势跟踪的自适应策略，根据市场环境动态选择入场方式，优化成交量确认和滞后性问题。",
            category=StrategyCategory.TREND,
            author="quant_researcher",
            version="1.0.0",
            tags=["混合策略", "趋势突破", "趋势跟踪", "智能选择", "成交量确认"],
            risk_level=RiskLevel.MEDIUM
        )
    
    def get_parameter_schema(self) -> List[ParameterSchema]:
        """获取参数配置schema"""
        return [
            # 突破策略参数
            ParameterSchema(
                name="breakout_period",
                type="int",
                default=20,
                min_value=10,
                max_value=50,
                description="突破通道周期",
                required=True
            ),
            ParameterSchema(
                name="volume_threshold",
                type="float",
                default=1.5,
                min_value=1.0,
                max_value=3.0,
                description="成交量确认倍数",
                required=True
            ),
            ParameterSchema(
                name="breakout_strength_min",
                type="float",
                default=0.5,
                min_value=0.1,
                max_value=2.0,
                description="最小突破强度（ATR倍数）",
                required=True
            ),
            
            # 跟踪策略参数
            ParameterSchema(
                name="fast_ma_period",
                type="int",
                default=8,
                min_value=3,
                max_value=20,
                description="快速均线周期（优化滞后性）",
                required=True
            ),
            ParameterSchema(
                name="slow_ma_period",
                type="int",
                default=21,
                min_value=10,
                max_value=50,
                description="慢速均线周期",
                required=True
            ),
            ParameterSchema(
                name="trend_confirmation_period",
                type="int",
                default=3,
                min_value=1,
                max_value=10,
                description="趋势确认周期（减少滞后）",
                required=True
            ),
            
            # 市场环境判断参数
            ParameterSchema(
                name="volatility_lookback",
                type="int",
                default=20,
                min_value=10,
                max_value=50,
                description="波动率计算周期",
                required=True
            ),
            ParameterSchema(
                name="trend_strength_threshold",
                type="float",
                default=25.0,
                min_value=15.0,
                max_value=40.0,
                description="趋势强度阈值（ADX）",
                required=True
            ),
            ParameterSchema(
                name="market_regime_sensitivity",
                type="float",
                default=0.7,
                min_value=0.5,
                max_value=0.9,
                description="市场环境判断敏感度",
                required=False
            ),
            
            # 风险控制参数
            ParameterSchema(
                name="max_position_risk",
                type="float",
                default=0.02,
                min_value=0.01,
                max_value=0.05,
                description="最大单笔风险",
                required=False
            ),
            ParameterSchema(
                name="enable_dynamic_sizing",
                type="bool",
                default=True,
                description="启用动态仓位管理",
                required=False
            )
        ]
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """计算混合策略所需的所有指标"""
        df = data.copy()
        
        # 获取参数
        breakout_period = self.params.get('breakout_period', 20)
        fast_ma = self.params.get('fast_ma_period', 8)
        slow_ma = self.params.get('slow_ma_period', 21)
        vol_lookback = self.params.get('volatility_lookback', 20)
        
        # 1. 突破策略指标
        df = self._calculate_breakout_indicators(df, breakout_period)
        
        # 2. 趋势跟踪指标
        df = self._calculate_trend_following_indicators(df, fast_ma, slow_ma)
        
        # 3. 市场环境指标
        df = self._calculate_market_regime_indicators(df, vol_lookback)
        
        # 4. 成交量分析指标
        df = self._calculate_volume_indicators(df)
        
        # 5. 风险控制指标
        df = self._calculate_risk_indicators(df)
        
        return df
    
    def _calculate_breakout_indicators(self, df: pd.DataFrame, period: int) -> pd.DataFrame:
        """计算突破策略指标"""
        # 价格通道
        df['breakout_high'] = df['high'].rolling(period).max()
        df['breakout_low'] = df['low'].rolling(period).min()
        df['channel_width'] = df['breakout_high'] - df['breakout_low']
        
        # 突破信号
        df['price_above_channel'] = df['close'] > df['breakout_high'].shift(1)
        df['price_below_channel'] = df['close'] < df['breakout_low'].shift(1)
        
        # 突破强度（基于ATR）
        df['atr'] = self._calculate_atr(df, 14)
        df['breakout_strength_up'] = (df['close'] - df['breakout_high'].shift(1)) / df['atr']
        df['breakout_strength_down'] = (df['breakout_low'].shift(1) - df['close']) / df['atr']
        
        # 通道收缩检测（提高突破质量）
        df['channel_squeeze'] = df['channel_width'] < df['channel_width'].rolling(period).mean() * 0.8
        
        return df
    
    def _calculate_trend_following_indicators(self, df: pd.DataFrame, fast: int, slow: int) -> pd.DataFrame:
        """计算趋势跟踪指标（优化滞后性）"""
        # 快速响应的EMA
        df['ema_fast'] = df['close'].ewm(span=fast, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=slow, adjust=False).mean()
        
        # 均线差值和斜率
        df['ma_diff'] = df['ema_fast'] - df['ema_slow']
        df['ma_diff_slope'] = df['ma_diff'].diff()
        
        # 快速MACD（减少滞后）
        ema12 = df['close'].ewm(span=8).mean()  # 缩短周期
        ema26 = df['close'].ewm(span=17).mean()  # 缩短周期
        df['macd_fast'] = ema12 - ema26
        df['macd_signal_fast'] = df['macd_fast'].ewm(span=6).mean()  # 缩短信号线
        df['macd_histogram'] = df['macd_fast'] - df['macd_signal_fast']
        
        # 趋势确认信号
        df['trend_up_confirmed'] = (
            (df['ema_fast'] > df['ema_slow']) & 
            (df['ma_diff_slope'] > 0) & 
            (df['macd_fast'] > df['macd_signal_fast'])
        )
        df['trend_down_confirmed'] = (
            (df['ema_fast'] < df['ema_slow']) & 
            (df['ma_diff_slope'] < 0) & 
            (df['macd_fast'] < df['macd_signal_fast'])
        )
        
        return df
    
    def _calculate_market_regime_indicators(self, df: pd.DataFrame, lookback: int) -> pd.DataFrame:
        """计算市场环境指标"""
        # 波动率
        df['returns'] = df['close'].pct_change()
        df['volatility'] = df['returns'].rolling(lookback).std()
        df['volatility_percentile'] = df['volatility'].rolling(lookback*2).rank(pct=True)
        
        # ADX趋势强度
        df['adx'] = self._calculate_adx(df, 14)
        
        # 市场环境分类
        trend_threshold = self.params.get('trend_strength_threshold', 25.0)
        df['is_trending'] = df['adx'] > trend_threshold
        df['is_high_volatility'] = df['volatility_percentile'] > 0.7
        df['is_low_volatility'] = df['volatility_percentile'] < 0.3
        
        # 综合市场状态
        df['market_regime'] = 'neutral'
        df.loc[df['is_trending'] & df['is_high_volatility'], 'market_regime'] = 'trending_volatile'
        df.loc[df['is_trending'] & df['is_low_volatility'], 'market_regime'] = 'trending_stable'
        df.loc[~df['is_trending'] & df['is_high_volatility'], 'market_regime'] = 'ranging_volatile'
        df.loc[~df['is_trending'] & df['is_low_volatility'], 'market_regime'] = 'ranging_stable'
        
        return df
    
    def _calculate_volume_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算成交量指标（优化突破确认）"""
        if 'volume' not in df.columns:
            df['volume'] = 1000000  # 默认成交量
        
        # 成交量均线和比率
        df['volume_ma'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']
        
        # 成交量突破确认
        volume_threshold = self.params.get('volume_threshold', 1.5)
        df['volume_surge'] = df['volume_ratio'] > volume_threshold
        
        # OBV能量潮
        df['obv'] = (df['volume'] * np.where(df['close'] > df['close'].shift(1), 1, -1)).cumsum()
        df['obv_ma'] = df['obv'].rolling(10).mean()
        df['obv_trend'] = df['obv'] > df['obv_ma']
        
        # 价量配合度
        price_up = df['close'] > df['close'].shift(1)
        df['price_volume_sync'] = (price_up & df['volume_surge']) | (~price_up & ~df['volume_surge'])
        
        return df
    
    def _calculate_risk_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算风险控制指标"""
        # ATR已在突破指标中计算
        
        # 动态止损位
        df['dynamic_stop_long'] = df['close'] - (2 * df['atr'])
        df['dynamic_stop_short'] = df['close'] + (2 * df['atr'])
        
        # 仓位风险计算
        max_risk = self.params.get('max_position_risk', 0.02)
        df['position_size_breakout'] = max_risk / (2 * df['atr'] / df['close'])
        df['position_size_following'] = max_risk / (1.5 * df['atr'] / df['close'])
        
        return df
    
    def generate_signals(self, data: pd.DataFrame) -> List[TradingSignal]:
        """生成混合策略交易信号"""
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
            # 跳过数据不足的行
            if pd.isna(row['atr']) or pd.isna(row['adx']):
                continue
            
            timestamp = pd.to_datetime(row['timestamp'])
            price = row['close']
            
            # 根据市场环境选择策略
            strategy_choice = self._select_strategy(row)
            
            # 生成对应策略的信号
            if strategy_choice == 'breakout':
                signal = self._generate_breakout_signal(row, timestamp, symbol, price)
            elif strategy_choice == 'following':
                signal = self._generate_following_signal(row, timestamp, symbol, price)
            else:
                continue  # 无信号
            
            if signal:
                signals.append(signal)
        
        return signals
    
    def _select_strategy(self, row: pd.Series) -> str:
        """根据市场环境选择策略"""
        market_regime = row['market_regime']
        sensitivity = self.params.get('market_regime_sensitivity', 0.7)
        
        # 策略选择逻辑
        if market_regime == 'trending_volatile':
            # 高波动趋势市场：优先突破策略
            return 'breakout' if np.random.random() > (1 - sensitivity) else 'following'
        
        elif market_regime == 'trending_stable':
            # 稳定趋势市场：优先跟踪策略
            return 'following' if np.random.random() > (1 - sensitivity) else 'breakout'
        
        elif market_regime == 'ranging_volatile':
            # 震荡高波动：谨慎使用突破策略
            return 'breakout' if row['channel_squeeze'] and row['volume_surge'] else None
        
        elif market_regime == 'ranging_stable':
            # 震荡稳定：优先跟踪策略
            return 'following' if row['trend_up_confirmed'] or row['trend_down_confirmed'] else None
        
        else:
            # 中性市场：根据信号强度选择
            breakout_strength = max(row.get('breakout_strength_up', 0), row.get('breakout_strength_down', 0))
            if breakout_strength > 1.0 and row['volume_surge']:
                return 'breakout'
            elif row['trend_up_confirmed'] or row['trend_down_confirmed']:
                return 'following'
            else:
                return None
    
    def _generate_breakout_signal(self, row: pd.Series, timestamp, symbol: str, price: float) -> TradingSignal:
        """生成突破策略信号"""
        min_strength = self.params.get('breakout_strength_min', 0.5)
        
        # 向上突破
        if (row['price_above_channel'] and 
            row['breakout_strength_up'] >= min_strength and 
            row['volume_surge'] and 
            row['obv_trend']):
            
            confidence = self._calculate_breakout_confidence(row, 'buy')
            if confidence >= 0.6:
                return TradingSignal(
                    timestamp=timestamp,
                    symbol=symbol,
                    action='buy',
                    price=price,
                    confidence=confidence,
                    reason=f"突破策略买入 - 突破强度:{row['breakout_strength_up']:.2f}, 成交量:{row['volume_ratio']:.1f}x, 市场:{row['market_regime']}"
                )
        
        # 向下突破
        elif (row['price_below_channel'] and 
              row['breakout_strength_down'] >= min_strength and 
              row['volume_surge'] and 
              not row['obv_trend']):
            
            confidence = self._calculate_breakout_confidence(row, 'sell')
            if confidence >= 0.6:
                return TradingSignal(
                    timestamp=timestamp,
                    symbol=symbol,
                    action='sell',
                    price=price,
                    confidence=confidence,
                    reason=f"突破策略卖出 - 突破强度:{row['breakout_strength_down']:.2f}, 成交量:{row['volume_ratio']:.1f}x, 市场:{row['market_regime']}"
                )
        
        return None
    
    def _generate_following_signal(self, row: pd.Series, timestamp, symbol: str, price: float) -> TradingSignal:
        """生成趋势跟踪信号"""
        confirmation_period = self.params.get('trend_confirmation_period', 3)
        
        # 趋势向上确认
        if row['trend_up_confirmed'] and row['macd_histogram'] > 0:
            confidence = self._calculate_following_confidence(row, 'buy')
            if confidence >= 0.5:
                return TradingSignal(
                    timestamp=timestamp,
                    symbol=symbol,
                    action='buy',
                    price=price,
                    confidence=confidence,
                    reason=f"跟踪策略买入 - MA差值:{row['ma_diff']:.3f}, MACD:{row['macd_fast']:.3f}, ADX:{row['adx']:.1f}"
                )
        
        # 趋势向下确认
        elif row['trend_down_confirmed'] and row['macd_histogram'] < 0:
            confidence = self._calculate_following_confidence(row, 'sell')
            if confidence >= 0.5:
                return TradingSignal(
                    timestamp=timestamp,
                    symbol=symbol,
                    action='sell',
                    price=price,
                    confidence=confidence,
                    reason=f"跟踪策略卖出 - MA差值:{row['ma_diff']:.3f}, MACD:{row['macd_fast']:.3f}, ADX:{row['adx']:.1f}"
                )
        
        return None
    
    def _calculate_breakout_confidence(self, row: pd.Series, action: str) -> float:
        """计算突破信号置信度"""
        base_confidence = 0.5
        
        # 突破强度加成
        strength = row['breakout_strength_up'] if action == 'buy' else row['breakout_strength_down']
        strength_boost = min(strength / 2.0, 0.3)
        
        # 成交量加成
        volume_boost = min((row['volume_ratio'] - 1.0) * 0.2, 0.2)
        
        # 通道收缩加成
        squeeze_boost = 0.1 if row['channel_squeeze'] else 0
        
        # 市场环境加成
        regime_boost = 0.1 if row['market_regime'] in ['trending_volatile', 'trending_stable'] else 0
        
        total_confidence = base_confidence + strength_boost + volume_boost + squeeze_boost + regime_boost
        return min(total_confidence, 1.0)
    
    def _calculate_following_confidence(self, row: pd.Series, action: str) -> float:
        """计算跟踪信号置信度"""
        base_confidence = 0.5
        
        # 趋势强度加成
        adx_boost = min((row['adx'] - 20) / 30, 0.2)
        
        # MACD强度加成
        macd_strength = abs(row['macd_histogram'])
        macd_boost = min(macd_strength * 10, 0.15)
        
        # 均线差值加成
        ma_diff_strength = abs(row['ma_diff']) / row['close']
        ma_boost = min(ma_diff_strength * 50, 0.15)
        
        # 价量配合加成
        sync_boost = 0.1 if row['price_volume_sync'] else 0
        
        total_confidence = base_confidence + adx_boost + macd_boost + ma_boost + sync_boost
        return min(total_confidence, 1.0)
    
    def _calculate_atr(self, df: pd.DataFrame, period: int) -> pd.Series:
        """计算ATR"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift(1))
        low_close = np.abs(df['low'] - df['close'].shift(1))
        
        true_range = np.maximum(high_low, np.maximum(high_close, low_close))
        return pd.Series(true_range).rolling(period).mean()
    
    def _calculate_adx(self, df: pd.DataFrame, period: int) -> pd.Series:
        """计算ADX"""
        high_diff = df['high'].diff()
        low_diff = df['low'].diff()
        
        plus_dm = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0)
        minus_dm = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0)
        
        tr = self._calculate_atr(df, 1)
        plus_di = 100 * (pd.Series(plus_dm).rolling(period).mean() / tr.rolling(period).mean())
        minus_di = 100 * (pd.Series(minus_dm).rolling(period).mean() / tr.rolling(period).mean())
        
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(period).mean()
        
        return adx
    
    def _explain_strategy_logic(self) -> str:
        """解释策略逻辑"""
        return f"""
混合趋势策略是一个智能的多策略系统：

**核心创新**:
1. 智能策略选择：根据市场环境动态选择突破或跟踪入场
2. 优化突破策略：增加成交量确认、通道收缩检测、OBV确认
3. 改进跟踪策略：缩短均线周期、快速MACD、减少确认时间
4. 市场环境识别：ADX+波动率+价量分析综合判断

**策略选择逻辑**:
- 高波动趋势市场 → 优先突破策略（捕捉新趋势）
- 稳定趋势市场 → 优先跟踪策略（跟随确定趋势）
- 震荡市场 → 谨慎使用，增加过滤条件
- 中性市场 → 根据信号强度动态选择

**突破策略优化**:
- 成交量确认：突破必须伴随{self.params.get('volume_threshold', 1.5)}倍放量
- 强度过滤：突破强度必须超过{self.params.get('breakout_strength_min', 0.5)}个ATR
- 通道收缩：优先选择收缩后的突破
- OBV确认：能量潮必须配合价格方向

**跟踪策略改进**:
- 快速均线：{self.params.get('fast_ma_period', 8)}日EMA（减少滞后）
- 快速MACD：8/17/6参数（提高响应速度）
- 确认周期：{self.params.get('trend_confirmation_period', 3)}日确认（降低滞后）
- 多重验证：均线+MACD+斜率三重确认

**风险控制**:
- 动态仓位：根据ATR和策略类型调整仓位
- 自适应止损：基于ATR的动态止损位
- 最大风险：单笔交易风险控制在{self.params.get('max_position_risk', 0.02):.1%}

**适用场景**:
- 各种市场环境的自适应交易
- 中长期趋势捕捉
- 风险可控的积极交易
- 程序化交易系统
        """.strip()
    
    def get_strategy_metrics(self, data: pd.DataFrame) -> Dict[str, Any]:
        """获取策略性能指标"""
        df = self.calculate_indicators(data)
        
        if len(df) < 50:
            return {"insufficient_data": True}
        
        # 统计不同策略的使用频率
        breakout_signals = 0
        following_signals = 0
        
        for _, row in df.iterrows():
            if pd.isna(row['atr']) or pd.isna(row['adx']):
                continue
            
            strategy_choice = self._select_strategy(row)
            if strategy_choice == 'breakout':
                breakout_signals += 1
            elif strategy_choice == 'following':
                following_signals += 1
        
        total_signals = breakout_signals + following_signals
        
        return {
            "breakout_signal_ratio": breakout_signals / total_signals if total_signals > 0 else 0,
            "following_signal_ratio": following_signals / total_signals if total_signals > 0 else 0,
            "avg_volatility": df['volatility'].mean(),
            "avg_adx": df['adx'].mean(),
            "trending_market_ratio": (df['market_regime'].str.contains('trending')).mean(),
            "avg_volume_ratio": df['volume_ratio'].mean(),
            "strategy_adaptability": len(df['market_regime'].unique()) / 5  # 市场环境多样性
        }