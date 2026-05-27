"""
市场状态检测策略 (Market Regime Strategy)

基于 CSI300 等宽基指数判断市场环境（牛市/熊市/震荡），
输出建议仓位水平供个股择时策略使用。

指标体系:
- MA50/MA200 交叉: 趋势方向
- RSI(14): 超买超卖
- ADX(14): 趋势强度
- 综合打分 → regime 分类 + position_level
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from ..base import (
    BaseStrategy,
    ParameterSchema,
    RiskLevel,
    StrategyCategory,
    StrategyMetadata,
    TradingSignal,
)


@dataclass
class RegimeState:
    """市场状态"""

    regime: str  # "strong_bull" / "bull" / "consolidation" / "bear" / "strong_bear"
    position_level: float  # 0.0 ~ 1.0 建议总仓位水平
    confidence: float  # 0.0 ~ 1.0 判断置信度
    indicators: dict = field(default_factory=dict)  # 当前指标值
    reason: str = ""  # 判断依据说明
    signal_date: str = ""  # 信号日期


class MarketRegimeStrategy(BaseStrategy):
    """
    市场状态检测策略

    根据宽基指数的技术指标综合判断市场所处阶段，
    输出 regime 分类和建议仓位水平。

    既可以作为 BaseStrategy 在回测中运行（在 regime 切换点产生信号），
    也可以通过 detect_regime() 方法被其他服务直接调用。
    """

    def _create_metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            id="market_regime",
            name="市场状态检测",
            description="基于MA/RSI/ADX等指标判断大盘牛熊状态，输出仓位建议",
            category=StrategyCategory.TREND,
            author="system",
            version="1.0.0",
            tags=["择时", "大盘", "regime", "仓位管理"],
            risk_level=RiskLevel.MEDIUM,
        )

    def get_parameter_schema(self) -> list[ParameterSchema]:
        return [
            ParameterSchema(
                name="ma_short",
                type="int",
                default=50,
                min_value=20,
                max_value=100,
                description="短期均线周期（趋势快线）",
            ),
            ParameterSchema(
                name="ma_long",
                type="int",
                default=200,
                min_value=100,
                max_value=300,
                description="长期均线周期（趋势慢线）",
            ),
            ParameterSchema(
                name="rsi_period",
                type="int",
                default=14,
                min_value=7,
                max_value=28,
                description="RSI 周期",
            ),
            ParameterSchema(
                name="rsi_overbought",
                type="int",
                default=70,
                min_value=60,
                max_value=85,
                description="RSI 超买阈值",
            ),
            ParameterSchema(
                name="rsi_oversold",
                type="int",
                default=30,
                min_value=15,
                max_value=40,
                description="RSI 超卖阈值",
            ),
            ParameterSchema(
                name="adx_period",
                type="int",
                default=14,
                min_value=7,
                max_value=28,
                description="ADX 周期",
            ),
            ParameterSchema(
                name="adx_threshold",
                type="int",
                default=25,
                min_value=15,
                max_value=40,
                description="ADX 趋势强度阈值",
            ),
            ParameterSchema(
                name="ma_proximity_pct",
                type="float",
                default=0.02,
                min_value=0.005,
                max_value=0.05,
                description="MA 接近阈值（判断震荡）",
            ),
        ]

    # ------------------------------------------------------------------
    # 技术指标计算 (纯 pandas/numpy)
    # ------------------------------------------------------------------

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """计算所有技术指标"""
        df = data.copy()

        ma_short = self.params.get("ma_short", 50)
        ma_long = self.params.get("ma_long", 200)
        rsi_period = self.params.get("rsi_period", 14)
        adx_period = self.params.get("adx_period", 14)

        # 1. 均线
        df["ma_short"] = df["close"].rolling(ma_short).mean()
        df["ma_long"] = df["close"].rolling(ma_long).mean()
        df["ma_diff_pct"] = (df["ma_short"] - df["ma_long"]) / df["ma_long"]

        # 2. RSI
        df["rsi"] = self._calc_rsi(df["close"], rsi_period)

        # 3. ADX
        df["adx"] = self._calc_adx(df, adx_period)

        # 4. Regime 分类
        df["regime"] = df.apply(self._classify_regime_row, axis=1)
        df["position_level"] = df["regime"].map(self._regime_to_position_level)

        return df

    def _calc_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """计算 RSI

        边界处理:
        - warmup期(不足period天): NaN (数据不足)
        - avg_loss==0 且 avg_gain>0: RSI=100 (全涨)
        - avg_gain==0 且 avg_loss>0: RSI=0 (全跌)
        - 两者都为0: NaN
        """
        delta = prices.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)

        avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()

        # pandas: positive/0 → inf, 0/0 → NaN, NaN/NaN → NaN
        # inf → rsi=100 (全涨), NaN → rsi=NaN (无数据), 0 → rsi=0 (全跌)
        with np.errstate(divide="ignore", invalid="ignore"):
            rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calc_adx(self, df: pd.DataFrame, period: int) -> pd.Series:
        """计算 ADX (Average Directional Index)"""
        high = df["high"]
        low = df["low"]
        close = df["close"]

        # True Range
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # Directional Movement
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low

        plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
        minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

        # Smoothed averages (Wilder's smoothing)
        atr = tr.ewm(alpha=1 / period, min_periods=period).mean()
        plus_di = 100 * (plus_dm.ewm(alpha=1 / period, min_periods=period).mean() / atr)
        minus_di = 100 * (
            minus_dm.ewm(alpha=1 / period, min_periods=period).mean() / atr
        )

        # DX and ADX
        dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1))
        adx = dx.ewm(alpha=1 / period, min_periods=period).mean()

        return adx

    # ------------------------------------------------------------------
    # Regime 分类
    # ------------------------------------------------------------------

    def _classify_regime_row(self, row: pd.Series) -> str:
        """对单行数据分类 regime"""
        ma_diff_pct = row.get("ma_diff_pct", 0)
        rsi = row.get("rsi", 50)
        adx = row.get("adx", 0)

        if pd.isna(ma_diff_pct) or pd.isna(rsi) or pd.isna(adx):
            return "unknown"

        proximity = self.params.get("ma_proximity_pct", 0.02)
        rsi_overbought = self.params.get("rsi_overbought", 70)
        rsi_oversold = self.params.get("rsi_oversold", 30)
        adx_threshold = self.params.get("adx_threshold", 25)

        # MA50 > MA200 区域
        if ma_diff_pct > proximity:
            if rsi < rsi_overbought and adx > adx_threshold:
                return "strong_bull"
            return "bull"

        # MA50 ≈ MA200 区域（震荡）
        if abs(ma_diff_pct) <= proximity:
            return "consolidation"

        # MA50 < MA200 区域
        if ma_diff_pct < -proximity:
            if rsi > rsi_overbought:
                # 熊市反弹超买 → 更危险
                return "strong_bear"
            if rsi < rsi_oversold and adx > adx_threshold:
                # 熊市超卖但趋势强 → 继续跌
                return "bear"
            return "bear"

        return "consolidation"

    def _regime_to_position_level(self, regime: str) -> float:
        """regime → 建议仓位水平"""
        mapping = {
            "strong_bull": 0.8,
            "bull": 0.6,
            "consolidation": 0.3,
            "bear": 0.1,
            "strong_bear": 0.05,
            "unknown": 0.0,
        }
        return mapping.get(regime, 0.3)

    # ------------------------------------------------------------------
    # 公共接口: detect_regime
    # ------------------------------------------------------------------

    def detect_regime(self, data: pd.DataFrame) -> RegimeState:
        """
        检测当前市场状态（供外部服务直接调用）

        Args:
            data: 指数的历史日线数据 (需包含至少 ma_long 天的数据)

        Returns:
            RegimeState 包含当前 regime 和建议仓位
        """
        df = self.calculate_indicators(data)

        # 取最后一行
        if df.empty:
            return RegimeState(
                regime="unknown",
                position_level=0.0,
                confidence=0.0,
                reason="数据不足",
            )

        last = df.iloc[-1]
        regime = last.get("regime", "unknown")
        position_level = last.get("position_level", 0.3)

        # 计算置信度：基于多个指标的一致性
        confidence = self._calc_confidence(last)

        # 生成原因说明
        reason = self._build_reason(last)

        # 信号日期
        signal_date = ""
        if "timestamp" in df.columns:
            signal_date = str(last["timestamp"].date())
        elif "trade_date" in df.columns:
            signal_date = str(last["trade_date"])

        return RegimeState(
            regime=regime,
            position_level=position_level,
            confidence=confidence,
            indicators={
                "ma_short": round(float(last.get("ma_short", 0)), 2),
                "ma_long": round(float(last.get("ma_long", 0)), 2),
                "ma_diff_pct": round(float(last.get("ma_diff_pct", 0)), 4),
                "rsi": round(float(last.get("rsi", 0)), 1),
                "adx": round(float(last.get("adx", 0)), 1),
                "close": round(float(last.get("close", 0)), 2),
            },
            reason=reason,
            signal_date=signal_date,
        )

    def _calc_confidence(self, row: pd.Series) -> float:
        """基于指标一致性计算置信度"""
        scores = []

        ma_diff_pct = row.get("ma_diff_pct", 0)
        rsi = row.get("rsi", 50)
        adx = row.get("adx", 0)
        adx_threshold = self.params.get("adx_threshold", 25)

        if pd.isna(ma_diff_pct) or pd.isna(rsi) or pd.isna(adx):
            return 0.3

        # MA 分离度越大，信号越确定
        ma_confidence = min(abs(ma_diff_pct) / 0.05, 1.0)
        scores.append(ma_confidence)

        # ADX 越高，趋势越明确
        adx_confidence = min(adx / (adx_threshold * 2), 1.0)
        scores.append(adx_confidence)

        # RSI 极端值增加信号确定性
        rsi_extremity = abs(rsi - 50) / 50
        scores.append(rsi_extremity)

        return round(max(0.3, min(1.0, sum(scores) / len(scores))), 2)

    def _build_reason(self, row: pd.Series) -> str:
        """构建 regime 判断的原因说明"""
        parts = []

        ma_diff_pct = row.get("ma_diff_pct", 0)
        if not pd.isna(ma_diff_pct):
            if ma_diff_pct > 0:
                parts.append(f"MA50 > MA200 ({ma_diff_pct:+.2%})")
            else:
                parts.append(f"MA50 < MA200 ({ma_diff_pct:+.2%})")

        rsi = row.get("rsi", 50)
        if not pd.isna(rsi):
            if rsi > 70:
                parts.append(f"RSI超买({rsi:.0f})")
            elif rsi < 30:
                parts.append(f"RSI超卖({rsi:.0f})")
            else:
                parts.append(f"RSI中性({rsi:.0f})")

        adx = row.get("adx", 0)
        adx_threshold = self.params.get("adx_threshold", 25)
        if not pd.isna(adx):
            if adx > adx_threshold:
                parts.append(f"趋势明确(ADX={adx:.0f})")
            else:
                parts.append(f"趋势弱(ADX={adx:.0f})")

        return " | ".join(parts)

    # ------------------------------------------------------------------
    # BaseStrategy 接口: generate_signals
    # ------------------------------------------------------------------

    def generate_signals(self, data: pd.DataFrame) -> list[TradingSignal]:
        """
        在 regime 切换点生成交易信号（用于回测）

        买入信号: regime 从 bear/consolidation 转为 bull/strong_bull
        卖出信号: regime 从 bull/strong_bull 转为 bear/strong_bear
        """
        df = self.calculate_indicators(data)
        signals = []

        if len(df) < 2:
            return signals

        # 确保有时间列
        if "timestamp" not in df.columns:
            if df.index.name == "timestamp" or "date" in str(df.index.dtype):
                df = df.reset_index()
                df.rename(columns={df.columns[0]: "timestamp"}, inplace=True)
            elif "trade_date" in df.columns:
                df["timestamp"] = pd.to_datetime(df["trade_date"])
            else:
                df["timestamp"] = pd.date_range(
                    start="2020-01-01", periods=len(df), freq="D"
                )

        symbol = df["symbol"].iloc[0] if "symbol" in df.columns else "INDEX"

        bullish_regimes = {"strong_bull", "bull"}
        bearish_regimes = {"bear", "strong_bear"}

        prev_regime = None
        for idx in range(len(df)):
            row = df.iloc[idx]
            current_regime = row.get("regime", "unknown")

            if current_regime == "unknown" or pd.isna(row.get("ma_short")):
                prev_regime = current_regime
                continue

            if prev_regime is not None and prev_regime != current_regime:
                # 从非牛转牛 → 买入
                if (
                    prev_regime not in bullish_regimes
                    and current_regime in bullish_regimes
                ):
                    signals.append(
                        TradingSignal(
                            timestamp=pd.to_datetime(row["timestamp"]),
                            symbol=symbol,
                            action="buy",
                            price=float(row["close"]),
                            confidence=self._calc_confidence(row),
                            reason=f"Regime → {current_regime}: {self._build_reason(row)}",
                        )
                    )
                # 从非熊转熊 → 卖出
                elif (
                    prev_regime not in bearish_regimes
                    and current_regime in bearish_regimes
                ):
                    signals.append(
                        TradingSignal(
                            timestamp=pd.to_datetime(row["timestamp"]),
                            symbol=symbol,
                            action="sell",
                            price=float(row["close"]),
                            confidence=self._calc_confidence(row),
                            reason=f"Regime → {current_regime}: {self._build_reason(row)}",
                        )
                    )

            prev_regime = current_regime

        return signals

    def _explain_strategy_logic(self) -> str:
        return f"""
市场状态检测策略通过综合分析大盘指数的技术指标来判断当前市场环境：

**核心逻辑**:
1. MA{self.params.get('ma_short', 50)}/MA{self.params.get('ma_long', 200)} 金叉死叉确定趋势方向
2. RSI({self.params.get('rsi_period', 14)}) 判断超买超卖
3. ADX({self.params.get('adx_period', 14)}) 衡量趋势强度
4. 综合以上指标将市场分为5种状态

**状态分类**:
- Strong Bull (强牛): MA金叉 + RSI适中 + ADX强趋势 → 仓位 80%
- Bull (牛市): MA金叉 → 仓位 60%
- Consolidation (震荡): MA接近 → 仓位 30%
- Bear (熊市): MA死叉 → 仓位 10%
- Strong Bear (强熊): MA死叉 + RSI反弹超买 → 仓位 5%

**使用方式**:
- 作为策略回测: 在 regime 切换点产生买卖信号
- 作为服务调用: detect_regime() 返回当前状态供其他策略参考
        """.strip()
