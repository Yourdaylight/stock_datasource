"""Technical indicators calculation module.

This module provides calculation functions for common technical indicators:
- MA (Moving Average)
- EMA (Exponential Moving Average)
- MACD (Moving Average Convergence Divergence)
- RSI (Relative Strength Index)
- KDJ (Stochastic Indicator)
- BOLL (Bollinger Bands)
- ATR (Average True Range)
- OBV (On Balance Volume)
- DMI (Directional Movement Index)
- CCI (Commodity Channel Index)

All functions accept pandas DataFrame with OHLCV data and return indicator values.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Union
import logging

logger = logging.getLogger(__name__)


def _clean_nan(values: Union[List, pd.Series]) -> List[Optional[float]]:
    """Convert NaN values to None for JSON serialization."""
    if isinstance(values, pd.Series):
        values = values.tolist()
    return [None if (isinstance(v, float) and (np.isnan(v) or np.isinf(v))) else v for v in values]


def calculate_ma(df: pd.DataFrame, periods: List[int] = None) -> Dict[str, List[Optional[float]]]:
    """Calculate Moving Average (MA).
    
    Args:
        df: DataFrame with 'close' column
        periods: List of periods, default [5, 10, 20, 60, 120, 250]
        
    Returns:
        Dict with MA values for each period, e.g., {"MA5": [...], "MA10": [...]}
    """
    if periods is None:
        periods = [5, 10, 20, 60]
    
    result = {}
    for period in periods:
        key = f"MA{period}"
        ma = df['close'].rolling(window=period).mean()
        result[key] = _clean_nan(ma.round(2))
    
    return result


def calculate_ema(df: pd.DataFrame, periods: List[int] = None) -> Dict[str, List[Optional[float]]]:
    """Calculate Exponential Moving Average (EMA).
    
    Args:
        df: DataFrame with 'close' column
        periods: List of periods, default [12, 26]
        
    Returns:
        Dict with EMA values for each period
    """
    if periods is None:
        periods = [12, 26]
    
    result = {}
    for period in periods:
        key = f"EMA{period}"
        ema = df['close'].ewm(span=period, adjust=False).mean()
        result[key] = _clean_nan(ema.round(2))
    
    return result


def calculate_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9
) -> Dict[str, List[Optional[float]]]:
    """Calculate MACD (Moving Average Convergence Divergence).
    
    Args:
        df: DataFrame with 'close' column
        fast: Fast EMA period (default 12)
        slow: Slow EMA period (default 26)
        signal: Signal line period (default 9)
        
    Returns:
        Dict with DIF, DEA, and MACD histogram values
    """
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    macd = (dif - dea) * 2  # Histogram
    
    return {
        "DIF": _clean_nan(dif.round(2)),
        "DEA": _clean_nan(dea.round(2)),
        "MACD": _clean_nan(macd.round(2))
    }


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> Dict[str, List[Optional[float]]]:
    """Calculate RSI (Relative Strength Index).
    
    Args:
        df: DataFrame with 'close' column
        period: RSI period (default 14)
        
    Returns:
        Dict with RSI values
    """
    delta = df['close'].diff()
    
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    
    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    # Handle division by zero
    rsi = rsi.fillna(50)
    
    return {
        f"RSI{period}": _clean_nan(rsi.round(2))
    }


def calculate_kdj(
    df: pd.DataFrame,
    n: int = 9,
    m1: int = 3,
    m2: int = 3
) -> Dict[str, List[Optional[float]]]:
    """Calculate KDJ (Stochastic Indicator).
    
    Args:
        df: DataFrame with 'high', 'low', 'close' columns
        n: RSV period (default 9)
        m1: K smoothing factor (default 3)
        m2: D smoothing factor (default 3)
        
    Returns:
        Dict with K, D, J values
    """
    df = df.copy()
    
    low_min = df['low'].rolling(window=n).min()
    high_max = df['high'].rolling(window=n).max()
    
    rsv = ((df['close'] - low_min) / (high_max - low_min) * 100).fillna(50)
    
    k_values = []
    d_values = []
    j_values = []
    
    k = 50.0
    d = 50.0
    
    for r in rsv:
        k = (m1 - 1) / m1 * k + 1 / m1 * r
        d = (m2 - 1) / m2 * d + 1 / m2 * k
        j = 3 * k - 2 * d
        
        k_values.append(round(k, 2))
        d_values.append(round(d, 2))
        j_values.append(round(j, 2))
    
    return {
        "K": _clean_nan(k_values),
        "D": _clean_nan(d_values),
        "J": _clean_nan(j_values)
    }


def calculate_boll(
    df: pd.DataFrame,
    period: int = 20,
    std_dev: int = 2
) -> Dict[str, List[Optional[float]]]:
    """Calculate Bollinger Bands (BOLL).
    
    Args:
        df: DataFrame with 'close' column
        period: MA period (default 20)
        std_dev: Standard deviation multiplier (default 2)
        
    Returns:
        Dict with Upper, Middle, Lower band values
    """
    middle = df['close'].rolling(window=period).mean()
    std = df['close'].rolling(window=period).std()
    
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    
    return {
        "BOLL_UPPER": _clean_nan(upper.round(2)),
        "BOLL_MIDDLE": _clean_nan(middle.round(2)),
        "BOLL_LOWER": _clean_nan(lower.round(2))
    }


def calculate_atr(df: pd.DataFrame, period: int = 14) -> Dict[str, List[Optional[float]]]:
    """Calculate ATR (Average True Range).
    
    Args:
        df: DataFrame with 'high', 'low', 'close' columns
        period: ATR period (default 14)
        
    Returns:
        Dict with ATR values
    """
    df = df.copy()
    
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = true_range.ewm(span=period, adjust=False).mean()
    
    return {
        f"ATR{period}": _clean_nan(atr.round(2))
    }


def calculate_obv(df: pd.DataFrame) -> Dict[str, List[Optional[float]]]:
    """Calculate OBV (On Balance Volume).
    
    Args:
        df: DataFrame with 'close' and 'volume' columns
        
    Returns:
        Dict with OBV values
    """
    df = df.copy()
    
    direction = np.sign(df['close'].diff())
    direction.iloc[0] = 0
    
    obv = (direction * df['volume']).cumsum()
    
    return {
        "OBV": _clean_nan(obv.round(0))
    }


def calculate_dmi(df: pd.DataFrame, period: int = 14) -> Dict[str, List[Optional[float]]]:
    """Calculate DMI (Directional Movement Index).
    
    Args:
        df: DataFrame with 'high', 'low', 'close' columns
        period: DMI period (default 14)
        
    Returns:
        Dict with +DI, -DI, ADX values
    """
    df = df.copy()
    
    # Calculate True Range
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    
    # Calculate Directional Movement
    up_move = df['high'] - df['high'].shift()
    down_move = df['low'].shift() - df['low']
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    
    plus_dm = pd.Series(plus_dm, index=df.index)
    minus_dm = pd.Series(minus_dm, index=df.index)
    
    # Smoothed values
    tr_smooth = tr.ewm(span=period, adjust=False).mean()
    plus_dm_smooth = plus_dm.ewm(span=period, adjust=False).mean()
    minus_dm_smooth = minus_dm.ewm(span=period, adjust=False).mean()
    
    # +DI and -DI
    plus_di = (plus_dm_smooth / tr_smooth) * 100
    minus_di = (minus_dm_smooth / tr_smooth) * 100
    
    # ADX
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = dx.ewm(span=period, adjust=False).mean()
    
    return {
        "PDI": _clean_nan(plus_di.round(2).fillna(0)),
        "MDI": _clean_nan(minus_di.round(2).fillna(0)),
        "ADX": _clean_nan(adx.round(2).fillna(0))
    }


def calculate_cci(df: pd.DataFrame, period: int = 14) -> Dict[str, List[Optional[float]]]:
    """Calculate CCI (Commodity Channel Index).
    
    Args:
        df: DataFrame with 'high', 'low', 'close' columns
        period: CCI period (default 14)
        
    Returns:
        Dict with CCI values
    """
    df = df.copy()
    
    tp = (df['high'] + df['low'] + df['close']) / 3  # Typical Price
    ma_tp = tp.rolling(window=period).mean()
    mad = tp.rolling(window=period).apply(lambda x: np.abs(x - x.mean()).mean())
    
    cci = (tp - ma_tp) / (0.015 * mad)
    
    return {
        f"CCI{period}": _clean_nan(cci.round(2).fillna(0))
    }


# Indicator calculation registry
INDICATOR_CALCULATORS = {
    "MA": calculate_ma,
    "EMA": calculate_ema,
    "MACD": calculate_macd,
    "RSI": calculate_rsi,
    "KDJ": calculate_kdj,
    "BOLL": calculate_boll,
    "ATR": calculate_atr,
    "OBV": calculate_obv,
    "DMI": calculate_dmi,
    "CCI": calculate_cci,
}


def calculate_indicators(
    df: pd.DataFrame,
    indicators: List[str],
    params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Calculate multiple technical indicators.
    
    Args:
        df: DataFrame with OHLCV data (columns: open, high, low, close, volume)
        indicators: List of indicator names to calculate
        params: Optional dict of parameters for each indicator
            e.g., {"MA": {"periods": [5, 10, 20]}, "RSI": {"period": 14}}
        
    Returns:
        Dict with all calculated indicator values
    """
    params = params or {}
    result = {}
    
    for indicator in indicators:
        indicator_upper = indicator.upper()
        calculator = INDICATOR_CALCULATORS.get(indicator_upper)
        
        if calculator is None:
            logger.warning(f"Unknown indicator: {indicator}")
            continue
        
        try:
            indicator_params = params.get(indicator_upper, {})
            indicator_data = calculator(df, **indicator_params) if indicator_params else calculator(df)
            result.update(indicator_data)
        except Exception as e:
            logger.error(f"Failed to calculate {indicator}: {e}")
            continue
    
    return result


def _safe_compare(val1, val2, op: str) -> bool:
    """Safely compare two values, returning False if either is None or NaN."""
    if val1 is None or val2 is None:
        return False
    if isinstance(val1, float) and (np.isnan(val1) or np.isinf(val1)):
        return False
    if isinstance(val2, float) and (np.isnan(val2) or np.isinf(val2)):
        return False
    
    if op == '>':
        return val1 > val2
    elif op == '<':
        return val1 < val2
    elif op == '>=':
        return val1 >= val2
    elif op == '<=':
        return val1 <= val2
    return False


def detect_signals(
    df: pd.DataFrame,
    indicators_data: Dict[str, List[float]]
) -> List[Dict[str, Any]]:
    """Detect trading signals based on technical indicators.
    
    Args:
        df: DataFrame with OHLCV data
        indicators_data: Calculated indicator data
        
    Returns:
        List of detected signals
    """
    signals = []
    n = len(df)
    
    if n < 3:
        return signals
    
    # MACD signals
    if "DIF" in indicators_data and "DEA" in indicators_data:
        dif = indicators_data["DIF"]
        dea = indicators_data["DEA"]
        
        if len(dif) >= 2 and len(dea) >= 2:
            # Golden cross (DIF crosses above DEA)
            if _safe_compare(dif[-1], dea[-1], '>') and _safe_compare(dif[-2], dea[-2], '<='):
                signals.append({
                    "type": "bullish",
                    "indicator": "MACD",
                    "signal": "MACD金叉",
                    "description": "DIF上穿DEA，买入信号"
                })
            
            # Death cross (DIF crosses below DEA)
            if _safe_compare(dif[-1], dea[-1], '<') and _safe_compare(dif[-2], dea[-2], '>='):
                signals.append({
                    "type": "bearish",
                    "indicator": "MACD",
                    "signal": "MACD死叉",
                    "description": "DIF下穿DEA，卖出信号"
                })
    
    # RSI signals
    rsi_keys = [k for k in indicators_data.keys() if k.startswith("RSI")]
    for rsi_key in rsi_keys:
        rsi = indicators_data[rsi_key]
        
        if rsi and len(rsi) > 0 and rsi[-1] is not None:
            if _safe_compare(rsi[-1], 80, '>'):
                signals.append({
                    "type": "bearish",
                    "indicator": "RSI",
                    "signal": "RSI超买",
                    "description": f"{rsi_key}={rsi[-1]:.1f}，处于超买区间"
                })
            elif _safe_compare(rsi[-1], 20, '<'):
                signals.append({
                    "type": "bullish",
                    "indicator": "RSI",
                    "signal": "RSI超卖",
                    "description": f"{rsi_key}={rsi[-1]:.1f}，处于超卖区间"
                })
    
    # KDJ signals
    if "K" in indicators_data and "D" in indicators_data:
        k = indicators_data["K"]
        d = indicators_data["D"]
        j = indicators_data.get("J", [])
        
        if len(k) >= 2 and len(d) >= 2:
            # Golden cross
            if _safe_compare(k[-1], d[-1], '>') and _safe_compare(k[-2], d[-2], '<='):
                signals.append({
                    "type": "bullish",
                    "indicator": "KDJ",
                    "signal": "KDJ金叉",
                    "description": "K线上穿D线，买入信号"
                })
            
            # Death cross
            if _safe_compare(k[-1], d[-1], '<') and _safe_compare(k[-2], d[-2], '>='):
                signals.append({
                    "type": "bearish",
                    "indicator": "KDJ",
                    "signal": "KDJ死叉",
                    "description": "K线下穿D线，卖出信号"
                })
        
        # J overbought/oversold
        if j and len(j) > 0 and j[-1] is not None:
            if _safe_compare(j[-1], 100, '>'):
                signals.append({
                    "type": "bearish",
                    "indicator": "KDJ",
                    "signal": "J线超买",
                    "description": f"J={j[-1]:.1f}，处于超买区间"
                })
            elif _safe_compare(j[-1], 0, '<'):
                signals.append({
                    "type": "bullish",
                    "indicator": "KDJ",
                    "signal": "J线超卖",
                    "description": f"J={j[-1]:.1f}，处于超卖区间"
                })
    
    # BOLL signals
    if "BOLL_UPPER" in indicators_data and "BOLL_LOWER" in indicators_data:
        upper = indicators_data["BOLL_UPPER"]
        lower = indicators_data["BOLL_LOWER"]
        close = df['close'].tolist()
        
        if close and upper and lower and len(close) > 0 and len(upper) > 0 and len(lower) > 0:
            if _safe_compare(close[-1], upper[-1], '>'):
                signals.append({
                    "type": "bearish",
                    "indicator": "BOLL",
                    "signal": "突破上轨",
                    "description": "股价突破布林带上轨，可能回调"
                })
            elif _safe_compare(close[-1], lower[-1], '<'):
                signals.append({
                    "type": "bullish",
                    "indicator": "BOLL",
                    "signal": "突破下轨",
                    "description": "股价突破布林带下轨，可能反弹"
                })
    
    return signals


def calculate_support_resistance(df: pd.DataFrame, window: int = 20) -> Dict[str, float]:
    """Calculate support and resistance levels.
    
    Args:
        df: DataFrame with OHLCV data
        window: Window for calculating levels
        
    Returns:
        Dict with support and resistance levels
    """
    if len(df) < 1:
        return {
            "resistance": 0.0,
            "support": 0.0,
            "fib_382": 0.0,
            "fib_618": 0.0,
            "mean": 0.0
        }
    
    if len(df) < window:
        window = len(df)
    
    recent = df.tail(window)
    
    high_max = recent['high'].max()
    low_min = recent['low'].min()
    close_mean = recent['close'].mean()
    
    # Handle NaN values
    if pd.isna(high_max):
        high_max = recent['close'].max() if not recent['close'].empty else 0.0
    if pd.isna(low_min):
        low_min = recent['close'].min() if not recent['close'].empty else 0.0
    if pd.isna(close_mean):
        close_mean = (high_max + low_min) / 2 if (high_max + low_min) > 0 else 0.0
    
    # Simple support/resistance calculation
    resistance = round(float(high_max), 2)
    support = round(float(low_min), 2)
    
    # Calculate fibonacci levels
    diff = high_max - low_min
    fib_382 = round(float(high_max - diff * 0.382), 2) if diff > 0 else resistance
    fib_618 = round(float(high_max - diff * 0.618), 2) if diff > 0 else support
    
    return {
        "resistance": resistance,
        "support": support,
        "fib_382": fib_382,
        "fib_618": fib_618,
        "mean": round(float(close_mean), 2)
    }


def determine_trend(df: pd.DataFrame, short_period: int = 5, long_period: int = 20) -> str:
    """Determine price trend based on moving averages.
    
    Args:
        df: DataFrame with close price
        short_period: Short MA period
        long_period: Long MA period
        
    Returns:
        Trend string: "上涨趋势", "下跌趋势", or "震荡"
    """
    if len(df) < long_period:
        return "震荡"
    
    ma_short = df['close'].rolling(window=short_period).mean()
    ma_long = df['close'].rolling(window=long_period).mean()
    
    # Check last 5 days
    recent_short = ma_short.tail(5)
    recent_long = ma_long.tail(5)
    
    # Check if short MA is consistently above/below long MA
    above_count = (recent_short > recent_long).sum()
    
    if above_count >= 4:
        return "上涨趋势"
    elif above_count <= 1:
        return "下跌趋势"
    else:
        return "震荡"
