"""
个股择时策略 (Stock Timing Strategy)

Regime-aware 的个股买卖点判断策略。
接收市场状态 (RegimeState) 作为上下文，根据大盘环境调节信号置信度和仓位权重。

买入条件: MA金叉 + RSI非超买 + 放量确认 + regime允许
卖出条件: MA死叉 OR 止损 OR 止盈 OR regime转熊
"""

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
from .market_regime_strategy import RegimeState


class StockTimingStrategy(BaseStrategy):
    """
    个股择时策略

    在大盘 regime 约束下对个股进行买卖时机判断。
    信号 confidence 会乘以 regime.position_level，
    使得熊市中即使个股出现技术买点，也会大幅降低建议仓位。
    """

    def __init__(
        self,
        params: dict[str, Any] = None,
        regime_state: RegimeState | None = None,
        held_positions: dict[str, float] | None = None,
    ):
        """
        Args:
            params: 策略参数
            regime_state: 当前市场状态
            held_positions: 已有持仓 {ts_code: avg_cost}，用于止损/止盈判断
        """
        self.regime_state = regime_state
        self.held_positions = held_positions or {}
        super().__init__(params)

    def _create_metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            id="stock_timing",
            name="个股择时策略",
            description="Regime-aware 的个股买卖点判断，结合均线、RSI、成交量和大盘状态",
            category=StrategyCategory.TREND,
            author="system",
            version="1.0.0",
            tags=["择时", "个股", "regime-aware", "止损止盈"],
            risk_level=RiskLevel.MEDIUM,
        )

    def get_parameter_schema(self) -> list[ParameterSchema]:
        return [
            ParameterSchema(
                name="ma_short",
                type="int",
                default=10,
                min_value=5,
                max_value=30,
                description="快速均线周期",
            ),
            ParameterSchema(
                name="ma_long",
                type="int",
                default=30,
                min_value=15,
                max_value=60,
                description="慢速均线周期",
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
                name="rsi_buy_threshold",
                type="int",
                default=70,
                min_value=55,
                max_value=80,
                description="RSI 买入上限（非超买才买）",
            ),
            ParameterSchema(
                name="rsi_sell_threshold",
                type="int",
                default=80,
                min_value=70,
                max_value=90,
                description="RSI 超买卖出阈值",
            ),
            ParameterSchema(
                name="volume_ratio_threshold",
                type="float",
                default=1.5,
                min_value=1.0,
                max_value=3.0,
                description="放量确认倍数（当日量/5日均量）",
            ),
            ParameterSchema(
                name="stop_loss_pct",
                type="float",
                default=0.08,
                min_value=0.03,
                max_value=0.15,
                description="止损比例",
            ),
            ParameterSchema(
                name="take_profit_pct",
                type="float",
                default=0.20,
                min_value=0.08,
                max_value=0.50,
                description="止盈比例",
            ),
            ParameterSchema(
                name="min_regime_level",
                type="float",
                default=0.2,
                min_value=0.0,
                max_value=0.5,
                description="允许开仓的最低 regime position_level",
            ),
        ]

    # ------------------------------------------------------------------
    # 技术指标
    # ------------------------------------------------------------------

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """计算个股技术指标"""
        df = data.copy()

        ma_short = self.params.get("ma_short", 10)
        ma_long = self.params.get("ma_long", 30)
        rsi_period = self.params.get("rsi_period", 14)

        # 均线
        df["ma_short"] = df["close"].rolling(ma_short).mean()
        df["ma_long"] = df["close"].rolling(ma_long).mean()

        # RSI
        df["rsi"] = self._calc_rsi(df["close"], rsi_period)

        # 成交量比率
        df["vol_ma5"] = df["volume"].rolling(5).mean()
        df["volume_ratio"] = df["volume"] / df["vol_ma5"].replace(0, np.nan)

        # ATR (用于动态止损参考)
        df["atr"] = self._calc_atr(df, period=14)

        # MA 交叉信号
        df["ma_cross"] = 0
        golden = (df["ma_short"] > df["ma_long"]) & (
            df["ma_short"].shift(1) <= df["ma_long"].shift(1)
        )
        death = (df["ma_short"] < df["ma_long"]) & (
            df["ma_short"].shift(1) >= df["ma_long"].shift(1)
        )
        df.loc[golden, "ma_cross"] = 1
        df.loc[death, "ma_cross"] = -1

        return df

    def _calc_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """计算 RSI

        边界处理:
        - warmup期(不足period天): NaN
        - avg_loss==0 且 avg_gain>0: RSI=100 (全涨)
        - avg_gain==0 且 avg_loss>0: RSI=0 (全跌)
        """
        delta = prices.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)
        avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
        # pandas: positive/0 → inf, 0/0 → NaN; inf → rsi=100, NaN → NaN
        with np.errstate(divide="ignore", invalid="ignore"):
            rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _calc_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """计算 ATR"""
        high = df["high"]
        low = df["low"]
        close = df["close"]
        tr = pd.concat(
            [
                high - low,
                (high - close.shift(1)).abs(),
                (low - close.shift(1)).abs(),
            ],
            axis=1,
        ).max(axis=1)
        return tr.ewm(alpha=1 / period, min_periods=period).mean()

    # ------------------------------------------------------------------
    # 信号生成
    # ------------------------------------------------------------------

    def generate_signals(self, data: pd.DataFrame) -> list[TradingSignal]:
        """生成买卖信号"""
        df = self.calculate_indicators(data)
        signals = []

        if len(df) < 2:
            return signals

        # 确保有时间列
        if "timestamp" not in df.columns:
            if "trade_date" in df.columns:
                df["timestamp"] = pd.to_datetime(df["trade_date"])
            elif df.index.name == "timestamp":
                df = df.reset_index()
            else:
                df["timestamp"] = pd.date_range(
                    start="2020-01-01", periods=len(df), freq="D"
                )

        symbol = df["symbol"].iloc[0] if "symbol" in df.columns else "UNKNOWN"

        # 参数
        rsi_buy = self.params.get("rsi_buy_threshold", 70)
        rsi_sell = self.params.get("rsi_sell_threshold", 80)
        vol_threshold = self.params.get("volume_ratio_threshold", 1.5)
        stop_loss = self.params.get("stop_loss_pct", 0.08)
        take_profit = self.params.get("take_profit_pct", 0.20)
        min_regime = self.params.get("min_regime_level", 0.2)

        # Regime 仓位乘数
        regime_level = (
            self.regime_state.position_level if self.regime_state else 0.6
        )

        # 从已有持仓初始化（解决 pipeline 每日重建策略丢失状态的问题）
        in_position = symbol in self.held_positions
        entry_price = self.held_positions.get(symbol, 0.0)

        for idx in range(len(df)):
            row = df.iloc[idx]

            # 跳过指标未就绪的行
            if pd.isna(row.get("ma_short")) or pd.isna(row.get("rsi")):
                continue

            timestamp = pd.to_datetime(row["timestamp"])
            price = float(row["close"])
            rsi = float(row["rsi"])
            volume_ratio = float(row.get("volume_ratio", 1.0))
            ma_cross = int(row.get("ma_cross", 0))

            if in_position:
                # --- 卖出逻辑 ---
                sell_reason = None

                # 止损
                if price <= entry_price * (1 - stop_loss):
                    sell_reason = f"止损触发 (跌幅 {(price/entry_price - 1)*100:.1f}%)"

                # 止盈
                elif price >= entry_price * (1 + take_profit):
                    sell_reason = f"止盈触发 (涨幅 {(price/entry_price - 1)*100:.1f}%)"

                # MA 死叉
                elif ma_cross == -1:
                    sell_reason = "MA死叉"

                # RSI 超买
                elif rsi > rsi_sell:
                    sell_reason = f"RSI超买({rsi:.0f})"

                # Regime 转熊 (如果有实时 regime 数据)
                elif self.regime_state and self.regime_state.position_level < 0.15:
                    sell_reason = f"Regime转熊(level={self.regime_state.position_level})"

                if sell_reason:
                    confidence = self._calc_sell_confidence(row, entry_price)
                    signals.append(
                        TradingSignal(
                            timestamp=timestamp,
                            symbol=symbol,
                            action="sell",
                            price=price,
                            confidence=confidence,
                            reason=sell_reason,
                        )
                    )
                    in_position = False
                    entry_price = 0.0

            else:
                # --- 买入逻辑 ---
                # Regime 不允许开仓
                if regime_level < min_regime:
                    continue

                # MA 金叉
                if ma_cross != 1:
                    continue

                # RSI 非超买
                if rsi >= rsi_buy:
                    continue

                # 放量确认（允许 NaN 通过）
                if not pd.isna(volume_ratio) and volume_ratio < vol_threshold:
                    continue

                # 所有条件满足 → 买入
                base_confidence = self._calc_buy_confidence(row)
                adjusted_confidence = base_confidence * regime_level

                reason_parts = [
                    f"MA金叉",
                    f"RSI={rsi:.0f}",
                    f"量比={volume_ratio:.1f}x",
                    f"regime={regime_level:.0%}",
                ]

                signals.append(
                    TradingSignal(
                        timestamp=timestamp,
                        symbol=symbol,
                        action="buy",
                        price=price,
                        confidence=round(adjusted_confidence, 2),
                        reason=" | ".join(reason_parts),
                    )
                )
                in_position = True
                entry_price = price

        return signals

    # ------------------------------------------------------------------
    # 置信度计算
    # ------------------------------------------------------------------

    def _calc_buy_confidence(self, row: pd.Series) -> float:
        """计算买入信号的基础置信度"""
        scores = []

        # RSI 越低（非超买区间内），买入信号越可靠
        rsi = row.get("rsi", 50)
        if not pd.isna(rsi):
            rsi_score = max(0, (70 - rsi) / 40)  # RSI=30 → 1.0, RSI=70 → 0.0
            scores.append(rsi_score)

        # 放量程度
        vol_ratio = row.get("volume_ratio", 1.0)
        if not pd.isna(vol_ratio):
            vol_score = min(vol_ratio / 3.0, 1.0)  # 量比3x → 满分
            scores.append(vol_score)

        # MA 分离度（金叉后拉开距离越大越确定）
        ma_short = row.get("ma_short", 0)
        ma_long = row.get("ma_long", 0)
        if ma_long and not pd.isna(ma_short) and not pd.isna(ma_long):
            separation = (ma_short - ma_long) / ma_long
            sep_score = min(max(separation, 0) / 0.03, 1.0)
            scores.append(sep_score)

        if not scores:
            return 0.5

        base = sum(scores) / len(scores)
        return max(0.3, min(0.9, base + 0.2))  # 基础置信度 0.3 ~ 0.9

    def _calc_sell_confidence(self, row: pd.Series, entry_price: float) -> float:
        """计算卖出信号的置信度"""
        price = float(row.get("close", 0))
        if entry_price <= 0:
            return 0.5

        pnl_pct = (price - entry_price) / entry_price

        # 止损越深、止盈越高 → 卖出越果断
        if pnl_pct < -0.05:
            return 0.9  # 深度止损 → 高置信度卖出
        elif pnl_pct > 0.15:
            return 0.8  # 大幅盈利 → 锁定利润
        else:
            return 0.6

    # ------------------------------------------------------------------
    # 说明
    # ------------------------------------------------------------------

    def _explain_strategy_logic(self) -> str:
        ma_short = self.params.get("ma_short", 10)
        ma_long = self.params.get("ma_long", 30)
        stop_loss = self.params.get("stop_loss_pct", 0.08)
        take_profit = self.params.get("take_profit_pct", 0.20)

        return f"""
个股择时策略 — Regime-Aware 买卖点判断:

**买入条件** (全部满足):
1. MA{ma_short} 上穿 MA{ma_long} (金叉)
2. RSI < {self.params.get('rsi_buy_threshold', 70)} (非超买)
3. 当日成交量 > 5日均量 × {self.params.get('volume_ratio_threshold', 1.5)} (放量)
4. 大盘 regime position_level > {self.params.get('min_regime_level', 0.2)}

**卖出条件** (任一触发):
1. MA{ma_short} 下穿 MA{ma_long} (死叉)
2. 跌幅达 {stop_loss:.0%} (止损)
3. 涨幅达 {take_profit:.0%} (止盈)
4. RSI > {self.params.get('rsi_sell_threshold', 80)} (超买)
5. 大盘 regime 转熊

**仓位控制**:
- 信号置信度 = 个股信号强度 × 大盘regime仓位水平
- 熊市(regime_level=0.1)时即使有金叉, 置信度也仅 0.1x
- 牛市(regime_level=0.8)时正常信号, 置信度接近原始值

**风险管理**:
- 硬性止损 {stop_loss:.0%}, 不可商量
- 止盈 {take_profit:.0%} 锁定利润
- 持仓期间 RSI 超买也触发卖出
        """.strip()
