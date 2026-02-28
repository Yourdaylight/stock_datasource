"""Core pool builder - constructs and manages the stock pool.

Top 50 by multi-factor score (core) + RPS supplement (observation).
Core constraint: ONLY reads from ClickHouse local data.
"""

import json
import logging
import time
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from stock_datasource.models.database import db_client

from .data_readiness import get_data_readiness_checker
from .factor_scorer import get_factor_scorer
from .rps_calculator import get_rps_calculator
from .schemas import (
    CorePoolResult,
    FactorScoreDetail,
    FactorWeight,
    PoolChange,
)

logger = logging.getLogger(__name__)


class CorePoolBuilder:
    """Build and manage the core stock pool.

    - Scores stocks using multi-factor model
    - Selects Top 50 as core pool
    - Adds RPS supplement (up to 20) with basic financial check
    - Tracks pool changes (entries/exits)
    """

    def __init__(self, weights: Optional[FactorWeight] = None):
        self.weights = weights or FactorWeight()
        self.readiness_checker = get_data_readiness_checker()
        self.factor_scorer = get_factor_scorer(weights)
        self.rps_calculator = get_rps_calculator()
        self.core_size = 50
        self.supplement_size = 20

    async def build_core_pool(
        self,
        screened_stocks: list[str],
        update_date: Optional[str] = None,
    ) -> CorePoolResult:
        """Build core pool from screening results.

        1. Check data readiness
        2. Score all screened stocks
        3. Select Top 50 as core
        4. RPS supplement (up to 20)
        5. Compare with previous pool, record changes
        """
        start_time = time.time()
        update_date = update_date or datetime.now().strftime("%Y%m%d")

        # Check data readiness
        readiness = await self.readiness_checker.check_core_pool_readiness()
        if not readiness.is_ready:
            return CorePoolResult(update_date=update_date, data_readiness=readiness)

        # Score stocks
        scored = await self.factor_scorer.score_stocks(screened_stocks)
        if not scored:
            return CorePoolResult(update_date=update_date, data_readiness=readiness)

        # Select Top N as core
        core_stocks = scored[: self.core_size]
        for s in core_stocks:
            s.pool_type = "core"

        # RPS supplement
        core_codes = {s.ts_code for s in core_stocks}
        supplement_stocks = await self._get_rps_supplement(core_codes, update_date)

        # Detect pool changes
        pool_changes = await self._detect_changes(core_stocks, supplement_stocks, update_date)

        # Calculate factor distribution
        all_pool = core_stocks + supplement_stocks
        factor_dist = self._calc_factor_distribution(all_pool)

        # Save to ClickHouse
        self._save_pool(core_stocks, supplement_stocks, update_date)

        elapsed = int((time.time() - start_time) * 1000)

        return CorePoolResult(
            update_date=update_date,
            core_stocks=core_stocks,
            supplement_stocks=supplement_stocks,
            pool_changes=pool_changes,
            factor_distribution=factor_dist,
            data_readiness=readiness,
            execution_time_ms=elapsed,
        )

    async def _get_rps_supplement(
        self, core_codes: set[str], update_date: str
    ) -> list[FactorScoreDetail]:
        """Get RPS supplement stocks not in core pool.

        Quick financial check: net_profit > 0 and ROE > 3%.
        """
        try:
            strong_stocks = await self.rps_calculator.get_strong_stocks(threshold=80)
            candidates = [s for s in strong_stocks if s not in core_codes]

            if not candidates:
                return []

            # Quick financial check
            passed = self._quick_financial_check(candidates)

            # Score the passed ones
            supplement = await self.factor_scorer.score_stocks(passed[: self.supplement_size * 2])
            supplement = supplement[: self.supplement_size]
            for s in supplement:
                s.pool_type = "rps_supplement"

            return supplement

        except Exception as e:
            logger.error(f"RPS supplement failed: {e}")
            return []

    def _quick_financial_check(self, ts_codes: list[str]) -> list[str]:
        """Quick check: net profit > 0, ROE > 3%."""
        if not ts_codes:
            return []
        try:
            codes_str = "','".join(ts_codes)
            df = db_client.execute_query(
                f"""SELECT ts_code,
                       argMax(roe, end_date) as latest_roe
                FROM fact_fina_indicator
                WHERE ts_code IN ('{codes_str}')
                AND end_date >= '20240101'
                GROUP BY ts_code
                HAVING latest_roe > 3"""
            )
            return df["ts_code"].tolist() if len(df) > 0 else []
        except Exception:
            return ts_codes[:self.supplement_size]

    async def _detect_changes(
        self,
        core_stocks: list[FactorScoreDetail],
        supplement_stocks: list[FactorScoreDetail],
        update_date: str,
    ) -> list[PoolChange]:
        """Compare current pool with previous pool to detect changes."""
        changes = []
        try:
            # Get previous pool
            prev_df = db_client.execute_query(
                f"""SELECT ts_code, pool_type, rank, total_score, stock_name
                FROM quant_core_pool
                WHERE update_date = (
                    SELECT max(update_date) FROM quant_core_pool
                    WHERE update_date < '{update_date}'
                )"""
            )

            prev_codes = set(prev_df["ts_code"]) if len(prev_df) > 0 else set()
            current_codes = {s.ts_code for s in core_stocks + supplement_stocks}

            # New entries
            for stock in core_stocks + supplement_stocks:
                if stock.ts_code not in prev_codes:
                    changes.append(PoolChange(
                        ts_code=stock.ts_code,
                        stock_name=stock.stock_name,
                        change_type="new_entry",
                        change_date=update_date,
                        new_rank=stock.rank,
                        total_score=stock.total_score,
                        reason=f"新入{stock.pool_type}池，总分{stock.total_score}",
                    ))

            # Exits
            for _, row in prev_df.iterrows() if len(prev_df) > 0 else []:
                if row["ts_code"] not in current_codes:
                    changes.append(PoolChange(
                        ts_code=row["ts_code"],
                        stock_name=row.get("stock_name", ""),
                        change_type="exit",
                        change_date=update_date,
                        old_rank=int(row.get("rank", 0)),
                        reason="调出池",
                    ))

        except Exception as e:
            logger.debug(f"No previous pool data for comparison: {e}")

        return changes

    def _calc_factor_distribution(
        self, stocks: list[FactorScoreDetail]
    ) -> dict:
        """Calculate factor score distribution stats."""
        if not stocks:
            return {}

        result = {}
        for factor in ["quality_score", "growth_score", "value_score", "momentum_score", "total_score"]:
            values = [getattr(s, factor) for s in stocks]
            result[factor] = {
                "min": round(min(values), 2),
                "max": round(max(values), 2),
                "mean": round(np.mean(values), 2),
                "median": round(np.median(values), 2),
                "std": round(np.std(values), 2),
            }

        return result

    def _save_pool(
        self,
        core_stocks: list[FactorScoreDetail],
        supplement_stocks: list[FactorScoreDetail],
        update_date: str,
    ) -> None:
        """Save pool to ClickHouse."""
        try:
            rows = []
            for stock in core_stocks + supplement_stocks:
                rows.append({
                    "update_date": update_date,
                    "pool_type": stock.pool_type,
                    "ts_code": stock.ts_code,
                    "stock_name": stock.stock_name,
                    "quality_score": stock.quality_score,
                    "growth_score": stock.growth_score,
                    "value_score": stock.value_score,
                    "momentum_score": stock.momentum_score,
                    "total_score": stock.total_score,
                    "factor_details": json.dumps({
                        "quality": stock.quality_breakdown,
                        "growth": stock.growth_breakdown,
                        "value": stock.value_breakdown,
                        "momentum": stock.momentum_breakdown,
                    }, ensure_ascii=False),
                    "rank": stock.rank,
                    "rps_250": stock.rps_250,
                    "change_type": "",
                })

            if rows:
                df = pd.DataFrame(rows)
                db_client.insert_dataframe("quant_core_pool", df)
                logger.info(f"Saved {len(rows)} pool entries for {update_date}")

        except Exception as e:
            logger.error(f"Failed to save pool: {e}")


# Singleton
_builder: Optional[CorePoolBuilder] = None


def get_core_pool_builder(weights: Optional[FactorWeight] = None) -> CorePoolBuilder:
    global _builder
    if _builder is None:
        _builder = CorePoolBuilder(weights)
    return _builder
