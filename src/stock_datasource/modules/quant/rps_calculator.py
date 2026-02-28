"""RPS (Relative Price Strength) calculator.

Core constraint: ONLY reads from ClickHouse local data. NEVER calls remote plugins.
"""

import logging
import time
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from stock_datasource.models.database import db_client

from .data_readiness import get_data_readiness_checker
from .schemas import DataReadinessResult, RPSRankItem, RPSResult

logger = logging.getLogger(__name__)


class RPSCalculator:
    """RPS calculator - computes relative price strength across the full market.

    Reads only from ClickHouse. Uses adj_factor for forward-adjusted prices.
    """

    def __init__(self):
        self.readiness_checker = get_data_readiness_checker()

    async def calculate_rps(
        self, calc_date: Optional[str] = None, periods: list[int] = None
    ) -> RPSResult:
        """Calculate RPS for the full market.

        Args:
            calc_date: Calculation date (YYYYMMDD)
            periods: RPS periods [250, 120, 60]
        """
        start_time = time.time()
        calc_date = calc_date or datetime.now().strftime("%Y%m%d")
        periods = periods or [250, 120, 60]

        # Check data readiness
        readiness = await self.readiness_checker.check_core_pool_readiness()
        if not readiness.is_ready:
            return RPSResult(calc_date=calc_date, data_readiness=readiness)

        try:
            # Load daily data with adj factor
            daily_df = self._load_daily_data()
            if daily_df.empty:
                return RPSResult(calc_date=calc_date, data_readiness=readiness)

            # Calculate price changes for each period
            results: dict[str, dict] = {}
            stock_names = self._load_stock_names()

            for ts_code in daily_df["ts_code"].unique():
                stock_data = daily_df[daily_df["ts_code"] == ts_code].sort_values(
                    "trade_date", ascending=True
                )
                if len(stock_data) < max(periods):
                    continue

                close_prices = pd.to_numeric(stock_data["close"], errors="coerce")
                adj_factors = pd.to_numeric(
                    stock_data["adj_factor"], errors="coerce"
                ) if "adj_factor" in stock_data.columns else pd.Series(
                    [1.0] * len(stock_data)
                )

                # Adjusted close
                adj_close = close_prices * adj_factors / adj_factors.iloc[-1]

                latest_price = adj_close.iloc[-1]
                changes = {}
                for period in periods:
                    if len(adj_close) >= period:
                        old_price = adj_close.iloc[-period]
                        if old_price > 0:
                            changes[period] = ((latest_price - old_price) / old_price) * 100
                        else:
                            changes[period] = 0.0
                    else:
                        changes[period] = 0.0

                results[ts_code] = {
                    "stock_name": stock_names.get(ts_code, ""),
                    "changes": changes,
                }

            # Calculate percentile ranks (RPS)
            for period in periods:
                all_changes = [
                    r["changes"].get(period, 0.0)
                    for r in results.values()
                    if period in r["changes"]
                ]
                if not all_changes:
                    continue

                sorted_changes = sorted(all_changes)
                total = len(sorted_changes)

                for ts_code, data in results.items():
                    chg = data["changes"].get(period, 0.0)
                    # Percentile rank
                    rank = np.searchsorted(sorted_changes, chg) / total * 100
                    data[f"rps_{period}"] = round(rank, 2)
                    data[f"price_chg_{period}"] = round(chg, 2)

            # Build items
            items = []
            for ts_code, data in results.items():
                items.append(
                    RPSRankItem(
                        ts_code=ts_code,
                        stock_name=data.get("stock_name", ""),
                        rps_250=data.get("rps_250", 0),
                        rps_120=data.get("rps_120", 0),
                        rps_60=data.get("rps_60", 0),
                        price_chg_250=data.get("price_chg_250", 0),
                        price_chg_120=data.get("price_chg_120", 0),
                        price_chg_60=data.get("price_chg_60", 0),
                        calc_date=calc_date,
                    )
                )

            # Sort by rps_250 descending
            items.sort(key=lambda x: x.rps_250, reverse=True)

            # Save to ClickHouse
            self._save_rps(items, calc_date)

            return RPSResult(
                calc_date=calc_date,
                total_stocks=len(items),
                items=items,
                data_readiness=readiness,
            )

        except Exception as e:
            logger.error(f"RPS calculation failed: {e}")
            return RPSResult(calc_date=calc_date, data_readiness=readiness)

    async def get_strong_stocks(
        self, threshold: float = 80, period: int = 250
    ) -> list[str]:
        """Get stocks with RPS > threshold."""
        try:
            col = f"rps_{period}"
            df = db_client.execute_query(
                f"""SELECT ts_code FROM quant_rps_rank
                WHERE calc_date = (SELECT max(calc_date) FROM quant_rps_rank)
                AND {col} >= {threshold}
                ORDER BY {col} DESC"""
            )
            return df["ts_code"].tolist() if len(df) > 0 else []
        except Exception as e:
            logger.error(f"Failed to get strong stocks: {e}")
            return []

    def _load_daily_data(self) -> pd.DataFrame:
        """Load daily bar + adj factor from ClickHouse."""
        try:
            return db_client.execute_query(
                """SELECT d.ts_code, d.trade_date, d.close, d.pct_chg,
                      a.adj_factor
                FROM fact_daily_bar d
                LEFT JOIN fact_adj_factor a ON d.ts_code = a.ts_code AND d.trade_date = a.trade_date
                WHERE d.trade_date >= toString(subtractDays(today(), 400))
                ORDER BY d.ts_code, d.trade_date"""
            )
        except Exception:
            # Fallback without join
            try:
                return db_client.execute_query(
                    """SELECT ts_code, trade_date, close, pct_chg
                    FROM fact_daily_bar
                    WHERE trade_date >= toString(subtractDays(today(), 400))
                    ORDER BY ts_code, trade_date"""
                )
            except Exception as e:
                logger.error(f"Failed to load daily data: {e}")
                return pd.DataFrame()

    def _load_stock_names(self) -> dict[str, str]:
        try:
            df = db_client.execute_query("SELECT ts_code, name FROM dim_stock_basic")
            return dict(zip(df["ts_code"], df["name"]))
        except Exception:
            return {}

    def _save_rps(self, items: list[RPSRankItem], calc_date: str) -> None:
        """Persist RPS results to ClickHouse."""
        try:
            if not items:
                return
            rows = [item.model_dump() for item in items]
            df = pd.DataFrame(rows)
            db_client.insert_dataframe("quant_rps_rank", df)
            logger.info(f"Saved {len(items)} RPS records for {calc_date}")
        except Exception as e:
            logger.error(f"Failed to save RPS: {e}")


# Singleton
_rps_calculator: Optional[RPSCalculator] = None


def get_rps_calculator() -> RPSCalculator:
    global _rps_calculator
    if _rps_calculator is None:
        _rps_calculator = RPSCalculator()
    return _rps_calculator
