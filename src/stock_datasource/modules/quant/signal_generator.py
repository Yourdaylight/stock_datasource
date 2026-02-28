"""Trading signal generator - MA crossover + position management + risk control.

Core constraint: ONLY reads from ClickHouse local data. NEVER calls remote plugins.
Each signal includes full context (signal_context) for frontend display.
"""

import json
import logging
import time
from datetime import datetime
from typing import Optional

import pandas as pd

from stock_datasource.models.database import db_client

from .data_readiness import get_data_readiness_checker
from .schemas import (
    MarketRiskStatus,
    SignalConfig,
    SignalResult,
    TradingSignal,
)

logger = logging.getLogger(__name__)


class SignalGenerator:
    """Trading signal generator.

    Entry: MA25 crosses above MA120 (golden cross)
    Add position: Staged building (1/3 + 1/3 + 1/3)
    Stop loss: Below MA120 or -15%
    Stop profit: 10% pullback from high or RPS < 75
    Market risk: CSI300 below MA250 -> reduce position
    """

    def __init__(self, config: Optional[SignalConfig] = None):
        self.config = config or SignalConfig()
        self.readiness_checker = get_data_readiness_checker()

    async def generate_signals(
        self,
        pool_stocks: list[str],
        signal_date: Optional[str] = None,
    ) -> SignalResult:
        """Generate signals for pool stocks.

        1. Check data readiness
        2. Check market risk
        3. For each stock, check entry/exit signals
        """
        start_time = time.time()
        signal_date = signal_date or datetime.now().strftime("%Y%m%d")

        # Check data readiness
        readiness = await self.readiness_checker.check_signal_readiness()
        if not readiness.is_ready:
            return SignalResult(signal_date=signal_date, data_readiness=readiness)

        # Market risk
        market_risk = await self.check_market_risk()

        # Generate signals for each stock
        signals: list[TradingSignal] = []
        stock_names = self._load_stock_names()

        for ts_code in pool_stocks:
            try:
                stock_signals = await self._check_stock_signals(
                    ts_code, signal_date, stock_names.get(ts_code, ""), market_risk
                )
                signals.extend(stock_signals)
            except Exception as e:
                logger.error(f"Signal generation failed for {ts_code}: {e}")

        # Save signals
        self._save_signals(signals)

        elapsed = int((time.time() - start_time) * 1000)

        return SignalResult(
            signal_date=signal_date,
            signals=signals,
            market_risk=market_risk,
            data_readiness=readiness,
            execution_time_ms=elapsed,
        )

    async def _check_stock_signals(
        self,
        ts_code: str,
        signal_date: str,
        stock_name: str,
        market_risk: MarketRiskStatus,
    ) -> list[TradingSignal]:
        """Check all signal types for a single stock."""
        signals = []

        # Load daily data
        df = self._load_stock_daily(ts_code)
        if df.empty or len(df) < self.config.ma_long + 5:
            return signals

        close = pd.to_numeric(df["close"], errors="coerce")
        ma_short = close.rolling(self.config.ma_short).mean()
        ma_long = close.rolling(self.config.ma_long).mean()

        latest_close = float(close.iloc[-1])
        latest_ma_short = float(ma_short.iloc[-1]) if not pd.isna(ma_short.iloc[-1]) else 0
        latest_ma_long = float(ma_long.iloc[-1]) if not pd.isna(ma_long.iloc[-1]) else 0
        prev_ma_short = float(ma_short.iloc[-2]) if not pd.isna(ma_short.iloc[-2]) else 0
        prev_ma_long = float(ma_long.iloc[-2]) if not pd.isna(ma_long.iloc[-2]) else 0

        # Base context for all signals
        base_context = {
            "close": latest_close,
            f"ma{self.config.ma_short}": round(latest_ma_short, 2),
            f"ma{self.config.ma_long}": round(latest_ma_long, 2),
            f"prev_ma{self.config.ma_short}": round(prev_ma_short, 2),
            f"prev_ma{self.config.ma_long}": round(prev_ma_long, 2),
            "market_risk_level": market_risk.risk_level,
        }

        # 1. Golden cross entry signal
        if prev_ma_short <= prev_ma_long and latest_ma_short > latest_ma_long:
            # MA short crossed above MA long
            position = self.config.max_position_pct
            if market_risk.risk_level == "warning":
                position *= market_risk.suggested_position
            elif market_risk.risk_level == "danger":
                position *= 0.3

            signals.append(TradingSignal(
                signal_date=signal_date,
                ts_code=ts_code,
                stock_name=stock_name,
                signal_type="buy",
                signal_source="ma_crossover",
                price=latest_close,
                target_position=round(position / 3, 4),  # First 1/3
                confidence=min(0.8, 0.5 + (latest_ma_short - latest_ma_long) / latest_ma_long * 10),
                reason=f"MA{self.config.ma_short}上穿MA{self.config.ma_long}金叉，建仓1/3",
                ma25=latest_ma_short,
                ma120=latest_ma_long,
                signal_context={**base_context, "crossover_type": "golden_cross", "batch": "1/3"},
            ))

        # 2. Death cross / Stop loss
        if prev_ma_short >= prev_ma_long and latest_ma_short < latest_ma_long:
            signals.append(TradingSignal(
                signal_date=signal_date,
                ts_code=ts_code,
                stock_name=stock_name,
                signal_type="sell",
                signal_source="ma_crossover",
                price=latest_close,
                target_position=0,
                confidence=0.7,
                reason=f"MA{self.config.ma_short}下穿MA{self.config.ma_long}死叉，清仓",
                ma25=latest_ma_short,
                ma120=latest_ma_long,
                signal_context={**base_context, "crossover_type": "death_cross"},
            ))

        # 3. Stop loss: price below MA120 by > 5%
        if latest_ma_long > 0 and latest_close < latest_ma_long * 0.95:
            signals.append(TradingSignal(
                signal_date=signal_date,
                ts_code=ts_code,
                stock_name=stock_name,
                signal_type="sell",
                signal_source="stop_loss",
                price=latest_close,
                target_position=0,
                confidence=0.9,
                reason=f"价格{latest_close:.2f}跌破MA{self.config.ma_long}({latest_ma_long:.2f})的95%，止损",
                ma25=latest_ma_short,
                ma120=latest_ma_long,
                signal_context={
                    **base_context,
                    "stop_type": "ma_break",
                    "ma_gap_pct": round((latest_close / latest_ma_long - 1) * 100, 2),
                },
            ))

        # 4. Trailing stop: check if pulled back > threshold from recent high
        if len(close) >= 20:
            recent_high = close.iloc[-20:].max()
            pullback = (recent_high - latest_close) / recent_high * 100
            if pullback > self.config.trailing_stop_pct * 100:
                signals.append(TradingSignal(
                    signal_date=signal_date,
                    ts_code=ts_code,
                    stock_name=stock_name,
                    signal_type="reduce",
                    signal_source="stop_profit",
                    price=latest_close,
                    target_position=0,
                    confidence=0.75,
                    reason=f"从近期高点{recent_high:.2f}回撤{pullback:.1f}%，移动止盈",
                    ma25=latest_ma_short,
                    ma120=latest_ma_long,
                    signal_context={
                        **base_context,
                        "recent_high": round(float(recent_high), 2),
                        "pullback_pct": round(pullback, 2),
                    },
                ))

        return signals

    async def check_market_risk(self) -> MarketRiskStatus:
        """Check market risk level: CSI300 vs MA250."""
        try:
            df = db_client.execute_query(
                """SELECT trade_date, close
                FROM fact_index_daily
                WHERE ts_code = '000300.SH'
                AND trade_date >= toString(subtractDays(today(), 400))
                ORDER BY trade_date ASC"""
            )

            if df.empty or len(df) < 250:
                return MarketRiskStatus(description="数据不足，无法判断市场风险")

            close = pd.to_numeric(df["close"], errors="coerce")
            ma250 = close.rolling(250).mean()

            latest_close = float(close.iloc[-1])
            latest_ma250 = float(ma250.iloc[-1]) if not pd.isna(ma250.iloc[-1]) else 0

            is_above = latest_close > latest_ma250
            if is_above:
                risk_level = "normal"
                position = 1.0
                desc = f"沪深300({latest_close:.0f})在年线({latest_ma250:.0f})上方，市场正常"
            elif latest_close > latest_ma250 * 0.95:
                risk_level = "warning"
                position = 0.5
                desc = f"沪深300({latest_close:.0f})接近年线({latest_ma250:.0f})，降低仓位至50%"
            else:
                risk_level = "danger"
                position = 0.3
                desc = f"沪深300({latest_close:.0f})跌破年线({latest_ma250:.0f})，仓位降至30%"

            return MarketRiskStatus(
                index_close=latest_close,
                index_ma250=round(latest_ma250, 2),
                is_above_ma250=is_above,
                risk_level=risk_level,
                suggested_position=position,
                description=desc,
            )

        except Exception as e:
            logger.error(f"Market risk check failed: {e}")
            return MarketRiskStatus(description=f"检查失败: {e}")

    def _load_stock_daily(self, ts_code: str) -> pd.DataFrame:
        try:
            return db_client.execute_query(
                f"""SELECT trade_date, close, pct_chg
                FROM fact_daily_bar
                WHERE ts_code = '{ts_code}'
                AND trade_date >= toString(subtractDays(today(), 400))
                ORDER BY trade_date ASC"""
            )
        except Exception as e:
            logger.error(f"Failed to load daily for {ts_code}: {e}")
            return pd.DataFrame()

    def _load_stock_names(self) -> dict[str, str]:
        try:
            df = db_client.execute_query("SELECT ts_code, name FROM dim_stock_basic")
            return dict(zip(df["ts_code"], df["name"]))
        except Exception:
            return {}

    def _save_signals(self, signals: list[TradingSignal]) -> None:
        if not signals:
            return
        try:
            rows = []
            for s in signals:
                rows.append({
                    "signal_date": s.signal_date,
                    "ts_code": s.ts_code,
                    "stock_name": s.stock_name,
                    "signal_type": s.signal_type,
                    "signal_source": s.signal_source,
                    "price": s.price,
                    "target_position": s.target_position,
                    "confidence": s.confidence,
                    "reason": s.reason,
                    "pool_type": s.pool_type,
                    "ma25": s.ma25,
                    "ma120": s.ma120,
                    "signal_context": json.dumps(s.signal_context, ensure_ascii=False),
                })
            df = pd.DataFrame(rows)
            db_client.insert_dataframe("quant_trading_signal", df)
            logger.info(f"Saved {len(signals)} trading signals")
        except Exception as e:
            logger.error(f"Failed to save signals: {e}")


# Singleton
_generator: Optional[SignalGenerator] = None


def get_signal_generator(config: Optional[SignalConfig] = None) -> SignalGenerator:
    global _generator
    if _generator is None:
        _generator = SignalGenerator(config)
    return _generator
