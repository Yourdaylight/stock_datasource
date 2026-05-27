"""Timing Service — 择时编排核心逻辑

每日择时流水线:
1. 获取 CSI300 数据 → 检测 regime
2. 获取观察池/持仓股票数据
3. 对每只股票运行 StockTimingStrategy
4. 将信号发送给 PaperTradingService 执行
5. 记录日净值快照
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import pandas as pd

from stock_datasource.backtest.engine import DataService
from stock_datasource.models.database import db_client
from stock_datasource.strategies.builtin.market_regime_strategy import (
    MarketRegimeStrategy,
    RegimeState,
)
from stock_datasource.strategies.builtin.stock_timing_strategy import (
    StockTimingStrategy,
)

from ..paper_trading.service import PaperTradingService
from .schemas import (
    PipelineResult,
    RegimeResponse,
    SignalItem,
    TimingHistoryItem,
)

logger = logging.getLogger(__name__)

# 默认使用 CSI300 作为大盘参考指数
DEFAULT_INDEX = "000300.SH"

# regime 检测需要的历史天数（至少覆盖 MA200）
REGIME_LOOKBACK_DAYS = 300


class TimingService:
    """择时编排服务"""

    def __init__(self):
        self._data_service = DataService()
        self._paper_trading = PaperTradingService()
        self._regime_strategy = MarketRegimeStrategy()
        self._db = db_client

    # ------------------------------------------------------------------
    # 核心 Pipeline
    # ------------------------------------------------------------------

    async def run_daily_pipeline(
        self,
        user_id: str,
        account_id: str,
        watchlist: list[str] | None = None,
    ) -> PipelineResult:
        """
        运行每日择时全流程

        Args:
            user_id: 用户ID
            account_id: 模拟盘账户ID
            watchlist: 观察池股票列表（为空则使用持仓 + 默认池）

        Returns:
            PipelineResult 包含 regime、信号、执行结果
        """
        errors: list[str] = []
        signals_items: list[SignalItem] = []
        trades_executed = 0

        # Step 1: 检测市场状态
        regime = await self.get_current_regime()
        regime_response = RegimeResponse(
            regime=regime.regime,
            position_level=regime.position_level,
            confidence=regime.confidence,
            reason=regime.reason,
            signal_date=regime.signal_date,
            indicators=regime.indicators,
        )

        logger.info(
            f"[Timing Pipeline] Regime: {regime.regime} "
            f"(level={regime.position_level}, confidence={regime.confidence})"
        )

        # Step 2: 构建观察池
        if not watchlist:
            watchlist = await self._build_watchlist(user_id, account_id)

        if not watchlist:
            return PipelineResult(
                regime=regime_response,
                message="观察池为空，无法生成信号",
            )

        # Step 3: 获取个股数据并生成信号
        today = date.today()
        start_date = today - timedelta(days=90)  # 需要至少 MA30 的数据

        stock_data = await self._data_service.get_historical_data(
            watchlist, start_date, today
        )

        # 获取当前持仓用于注入策略（使策略知道已有仓位，正确触发卖出信号）
        positions = await self._paper_trading.get_positions(user_id, account_id)
        held_positions = {p.ts_code: p.avg_cost for p in positions if p.quantity > 0}

        for ts_code in watchlist:
            if ts_code not in stock_data or stock_data[ts_code].empty:
                errors.append(f"{ts_code}: 无数据")
                continue

            try:
                # 每只股票单独实例化策略，注入 regime 和持仓状态
                stock_strategy = StockTimingStrategy(
                    regime_state=regime,
                    held_positions=held_positions,
                )
                signals = stock_strategy.generate_signals(stock_data[ts_code])

                # 只取最后一天的信号
                today_signals = [
                    s for s in signals if s.timestamp.date() == today
                ]

                for signal in today_signals:
                    signals_items.append(
                        SignalItem(
                            ts_code=signal.symbol,
                            action=signal.action,
                            price=signal.price,
                            confidence=signal.confidence,
                            reason=signal.reason,
                        )
                    )

                    # Step 4: 执行信号
                    result = await self._paper_trading.execute_signal(
                        user_id, account_id, signal, regime
                    )
                    if result.success:
                        trades_executed += 1
                    else:
                        logger.debug(
                            f"Signal not executed for {ts_code}: {result.message}"
                        )

            except Exception as e:
                errors.append(f"{ts_code}: {str(e)}")
                logger.warning(f"Signal generation failed for {ts_code}: {e}")

        # Step 5: 记录每日快照
        try:
            await self._paper_trading.take_daily_snapshot(
                user_id, account_id, regime
            )
        except Exception as e:
            errors.append(f"快照记录失败: {e}")

        message = (
            f"Pipeline 完成: regime={regime.regime}, "
            f"观察池={len(watchlist)}只, "
            f"信号={len(signals_items)}条, "
            f"成交={trades_executed}笔"
        )
        logger.info(f"[Timing Pipeline] {message}")

        return PipelineResult(
            regime=regime_response,
            signals_generated=len(signals_items),
            trades_executed=trades_executed,
            signals=signals_items,
            errors=errors,
            message=message,
        )

    # ------------------------------------------------------------------
    # Regime 检测
    # ------------------------------------------------------------------

    async def get_current_regime(self) -> RegimeState:
        """获取当前市场状态"""
        today = date.today()
        start_date = today - timedelta(days=REGIME_LOOKBACK_DAYS)

        # 获取指数数据
        index_data = await self._data_service.get_index_data(
            DEFAULT_INDEX, start_date, today
        )

        if index_data.empty:
            logger.warning(f"No index data for {DEFAULT_INDEX}")
            return RegimeState(
                regime="unknown",
                position_level=0.3,
                confidence=0.0,
                reason=f"无法获取{DEFAULT_INDEX}数据",
                signal_date=str(today),
            )

        return self._regime_strategy.detect_regime(index_data)

    # ------------------------------------------------------------------
    # 信号查询（不执行）
    # ------------------------------------------------------------------

    async def get_latest_signals(
        self,
        user_id: str,
        account_id: str,
        watchlist: list[str] | None = None,
    ) -> list[SignalItem]:
        """获取最新择时信号（只生成不执行）"""
        regime = await self.get_current_regime()

        if not watchlist:
            watchlist = await self._build_watchlist(user_id, account_id)

        if not watchlist:
            return []

        today = date.today()
        start_date = today - timedelta(days=90)
        stock_data = await self._data_service.get_historical_data(
            watchlist, start_date, today
        )

        stock_strategy = StockTimingStrategy(regime_state=regime)
        signals_items = []

        for ts_code in watchlist:
            if ts_code not in stock_data or stock_data[ts_code].empty:
                continue
            try:
                signals = stock_strategy.generate_signals(stock_data[ts_code])
                # 取最后一条信号
                if signals:
                    last_signal = signals[-1]
                    signals_items.append(
                        SignalItem(
                            ts_code=last_signal.symbol,
                            action=last_signal.action,
                            price=last_signal.price,
                            confidence=last_signal.confidence,
                            reason=last_signal.reason,
                        )
                    )
            except Exception as e:
                logger.warning(f"Signal generation failed for {ts_code}: {e}")

        return signals_items

    # ------------------------------------------------------------------
    # 历史 Regime
    # ------------------------------------------------------------------

    async def get_regime_history(self, days: int = 30) -> list[TimingHistoryItem]:
        """获取历史 regime 变化记录"""
        today = date.today()
        start_date = today - timedelta(days=days + REGIME_LOOKBACK_DAYS)

        index_data = await self._data_service.get_index_data(
            DEFAULT_INDEX, start_date, today
        )

        if index_data.empty:
            return []

        df = self._regime_strategy.calculate_indicators(index_data)

        # 取最近 days 天
        result_df = df.tail(days)
        history = []
        for _, row in result_df.iterrows():
            if pd.isna(row.get("regime")):
                continue
            ts = row.get("timestamp", row.get("trade_date", ""))
            history.append(
                TimingHistoryItem(
                    date=str(ts.date()) if hasattr(ts, "date") else str(ts),
                    regime=row["regime"],
                    position_level=float(row.get("position_level", 0.3)),
                    close_price=float(row.get("close", 0)),
                )
            )

        return history

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------

    async def _build_watchlist(
        self, user_id: str, account_id: str
    ) -> list[str]:
        """构建观察池：当前持仓 + 默认蓝筹列表"""
        watchlist = set()

        # 从当前持仓获取
        positions = await self._paper_trading.get_positions(user_id, account_id)
        for pos in positions:
            watchlist.add(pos.ts_code)

        # 默认蓝筹池（如果持仓为空）
        if not watchlist:
            default_pool = [
                "600519.SH",  # 贵州茅台
                "000858.SZ",  # 五粮液
                "601318.SH",  # 中国平安
                "000001.SZ",  # 平安银行
                "600036.SH",  # 招商银行
                "000333.SZ",  # 美的集团
                "600900.SH",  # 长江电力
                "601012.SH",  # 隆基绿能
            ]
            watchlist.update(default_pool)

        return list(watchlist)
