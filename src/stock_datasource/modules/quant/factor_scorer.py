"""Multi-factor scoring model for stock ranking.

Factors: Quality (30%), Growth (30%), Value (20%), Momentum (20%)
Core constraint: ONLY reads from ClickHouse local data.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from stock_datasource.models.database import db_client

from .schemas import FactorScoreDetail, FactorWeight

logger = logging.getLogger(__name__)


def _percentile_score(value: float, values: pd.Series) -> float:
    """Convert a value to percentile score (0-100) within distribution."""
    if values.empty or pd.isna(value):
        return 50.0
    rank = (values < value).sum() / len(values) * 100
    return round(rank, 2)


def _inverse_percentile_score(value: float, values: pd.Series) -> float:
    """Inverse percentile (lower is better, e.g., PE, debt ratio)."""
    if values.empty or pd.isna(value):
        return 50.0
    rank = (values > value).sum() / len(values) * 100
    return round(rank, 2)


class FactorScorer:
    """Multi-factor scoring model.

    Reads from ClickHouse only. Returns per-stock factor breakdown for frontend.
    """

    def __init__(self, weights: Optional[FactorWeight] = None):
        self.weights = weights or FactorWeight()

    async def score_stocks(
        self, ts_codes: list[str]
    ) -> list[FactorScoreDetail]:
        """Score a list of stocks on all factors.

        Returns list sorted by total_score descending.
        """
        if not ts_codes:
            return []

        # Load all needed data
        fina_df = self._load_fina_data(ts_codes)
        daily_basic_df = self._load_daily_basic(ts_codes)
        daily_df = self._load_daily_data(ts_codes)
        stock_names = self._load_stock_names()

        results = []
        for code in ts_codes:
            detail = FactorScoreDetail(
                ts_code=code,
                stock_name=stock_names.get(code, ""),
            )

            # Quality factor
            q_score, q_breakdown = self._calc_quality(code, fina_df)
            detail.quality_score = q_score
            detail.quality_breakdown = q_breakdown

            # Growth factor
            g_score, g_breakdown = self._calc_growth(code, fina_df)
            detail.growth_score = g_score
            detail.growth_breakdown = g_breakdown

            # Value factor
            v_score, v_breakdown = self._calc_value(code, daily_basic_df)
            detail.value_score = v_score
            detail.value_breakdown = v_breakdown

            # Momentum factor
            m_score, m_breakdown = self._calc_momentum(code, daily_df)
            detail.momentum_score = m_score
            detail.momentum_breakdown = m_breakdown

            # Total score
            detail.total_score = round(
                detail.quality_score * self.weights.quality
                + detail.growth_score * self.weights.growth
                + detail.value_score * self.weights.value
                + detail.momentum_score * self.weights.momentum,
                2,
            )
            results.append(detail)

        # Sort by total score
        results.sort(key=lambda x: x.total_score, reverse=True)

        # Assign ranks
        for i, r in enumerate(results):
            r.rank = i + 1

        return results

    # =========================================================================
    # Individual Factor Calculations
    # =========================================================================

    def _calc_quality(self, ts_code: str, fina_df: pd.DataFrame) -> tuple[float, dict]:
        """Quality factor: ROE, gross margin, debt ratio."""
        breakdown = {"roe": 0, "gross_margin": 0, "debt_ratio": 0}
        stock_data = fina_df[fina_df["ts_code"] == ts_code]
        if stock_data.empty:
            return 50.0, breakdown

        all_data = fina_df

        # ROE
        roe = pd.to_numeric(stock_data["roe"].iloc[0], errors="coerce") if "roe" in stock_data else 0
        all_roe = pd.to_numeric(all_data["roe"], errors="coerce").dropna()
        breakdown["roe"] = _percentile_score(roe, all_roe)

        # Gross margin
        if "grossprofit_margin" in stock_data.columns:
            gm = pd.to_numeric(stock_data["grossprofit_margin"].iloc[0], errors="coerce")
            all_gm = pd.to_numeric(all_data["grossprofit_margin"], errors="coerce").dropna()
            breakdown["gross_margin"] = _percentile_score(gm, all_gm)
        else:
            breakdown["gross_margin"] = 50.0

        # Debt ratio (lower is better)
        if "debt_to_assets" in stock_data.columns:
            dr = pd.to_numeric(stock_data["debt_to_assets"].iloc[0], errors="coerce")
            all_dr = pd.to_numeric(all_data["debt_to_assets"], errors="coerce").dropna()
            breakdown["debt_ratio"] = _inverse_percentile_score(dr, all_dr)
        else:
            breakdown["debt_ratio"] = 50.0

        score = (breakdown["roe"] * 0.5 + breakdown["gross_margin"] * 0.3 + breakdown["debt_ratio"] * 0.2)
        return round(score, 2), breakdown

    def _calc_growth(self, ts_code: str, fina_df: pd.DataFrame) -> tuple[float, dict]:
        """Growth factor: revenue growth, profit growth."""
        breakdown = {"revenue_growth": 0, "profit_growth": 0}
        stock_data = fina_df[fina_df["ts_code"] == ts_code]
        if stock_data.empty:
            return 50.0, breakdown

        all_data = fina_df

        # Revenue growth
        rg = pd.to_numeric(stock_data["revenue_yoy"].iloc[0], errors="coerce") if "revenue_yoy" in stock_data else 0
        all_rg = pd.to_numeric(all_data["revenue_yoy"], errors="coerce").dropna()
        breakdown["revenue_growth"] = _percentile_score(rg, all_rg)

        # Profit growth
        pg = pd.to_numeric(stock_data["netprofit_yoy"].iloc[0], errors="coerce") if "netprofit_yoy" in stock_data else 0
        all_pg = pd.to_numeric(all_data["netprofit_yoy"], errors="coerce").dropna()
        breakdown["profit_growth"] = _percentile_score(pg, all_pg)

        score = breakdown["revenue_growth"] * 0.5 + breakdown["profit_growth"] * 0.5
        return round(score, 2), breakdown

    def _calc_value(self, ts_code: str, daily_basic_df: pd.DataFrame) -> tuple[float, dict]:
        """Value factor: PE percentile, PB percentile (lower is better)."""
        breakdown = {"pe_percentile": 0, "pb_percentile": 0}
        stock_data = daily_basic_df[daily_basic_df["ts_code"] == ts_code]
        if stock_data.empty:
            return 50.0, breakdown

        all_data = daily_basic_df

        # PE (lower is better)
        pe = pd.to_numeric(stock_data["pe"].iloc[0], errors="coerce") if "pe" in stock_data else 0
        all_pe = pd.to_numeric(all_data["pe"], errors="coerce").dropna()
        all_pe = all_pe[(all_pe > 0) & (all_pe < 500)]
        breakdown["pe_percentile"] = _inverse_percentile_score(pe, all_pe) if pe > 0 else 0

        # PB (lower is better)
        pb = pd.to_numeric(stock_data["pb"].iloc[0], errors="coerce") if "pb" in stock_data else 0
        all_pb = pd.to_numeric(all_data["pb"], errors="coerce").dropna()
        all_pb = all_pb[(all_pb > 0) & (all_pb < 50)]
        breakdown["pb_percentile"] = _inverse_percentile_score(pb, all_pb) if pb > 0 else 0

        score = breakdown["pe_percentile"] * 0.5 + breakdown["pb_percentile"] * 0.5
        return round(score, 2), breakdown

    def _calc_momentum(self, ts_code: str, daily_df: pd.DataFrame) -> tuple[float, dict]:
        """Momentum factor: half-year return."""
        breakdown = {"half_year_return": 0}
        stock_data = daily_df[daily_df["ts_code"] == ts_code].sort_values("trade_date")
        if len(stock_data) < 120:
            return 50.0, breakdown

        close = pd.to_numeric(stock_data["close"], errors="coerce")
        latest = close.iloc[-1]
        half_year_ago = close.iloc[-120] if len(close) >= 120 else close.iloc[0]

        if half_year_ago > 0:
            ret = ((latest - half_year_ago) / half_year_ago) * 100
        else:
            ret = 0

        # Calculate percentile across all stocks
        all_returns = []
        for code in daily_df["ts_code"].unique():
            s = daily_df[daily_df["ts_code"] == code].sort_values("trade_date")
            c = pd.to_numeric(s["close"], errors="coerce")
            if len(c) >= 120 and c.iloc[-120] > 0:
                all_returns.append(((c.iloc[-1] - c.iloc[-120]) / c.iloc[-120]) * 100)

        breakdown["half_year_return"] = _percentile_score(ret, pd.Series(all_returns))
        return round(breakdown["half_year_return"], 2), breakdown

    # =========================================================================
    # Data Loading
    # =========================================================================

    def _load_fina_data(self, ts_codes: list[str]) -> pd.DataFrame:
        try:
            codes_str = "','".join(ts_codes)
            return db_client.execute_query(
                f"""SELECT ts_code, end_date,
                       argMax(roe, _ingested_at) as roe,
                       argMax(revenue_yoy, _ingested_at) as revenue_yoy,
                       argMax(netprofit_yoy, _ingested_at) as netprofit_yoy,
                       argMax(grossprofit_margin, _ingested_at) as grossprofit_margin,
                       argMax(debt_to_assets, _ingested_at) as debt_to_assets
                FROM fact_fina_indicator
                WHERE ts_code IN ('{codes_str}')
                AND end_date >= '20220101'
                GROUP BY ts_code, end_date
                ORDER BY ts_code, end_date DESC"""
            )
        except Exception as e:
            logger.error(f"Failed to load fina data for scoring: {e}")
            return pd.DataFrame()

    def _load_daily_basic(self, ts_codes: list[str]) -> pd.DataFrame:
        try:
            codes_str = "','".join(ts_codes)
            return db_client.execute_query(
                f"""SELECT ts_code, trade_date, pe, pb, total_mv
                FROM fact_daily_basic
                WHERE ts_code IN ('{codes_str}')
                AND trade_date = (SELECT max(trade_date) FROM fact_daily_basic)"""
            )
        except Exception as e:
            logger.error(f"Failed to load daily basic for scoring: {e}")
            return pd.DataFrame()

    def _load_daily_data(self, ts_codes: list[str]) -> pd.DataFrame:
        try:
            codes_str = "','".join(ts_codes)
            return db_client.execute_query(
                f"""SELECT ts_code, trade_date, close, pct_chg
                FROM fact_daily_bar
                WHERE ts_code IN ('{codes_str}')
                AND trade_date >= toString(subtractDays(today(), 200))
                ORDER BY ts_code, trade_date"""
            )
        except Exception as e:
            logger.error(f"Failed to load daily data for scoring: {e}")
            return pd.DataFrame()

    def _load_stock_names(self) -> dict[str, str]:
        try:
            df = db_client.execute_query("SELECT ts_code, name FROM dim_stock_basic")
            return dict(zip(df["ts_code"], df["name"]))
        except Exception:
            return {}


# Singleton
_scorer: Optional[FactorScorer] = None


def get_factor_scorer(weights: Optional[FactorWeight] = None) -> FactorScorer:
    global _scorer
    if _scorer is None:
        _scorer = FactorScorer(weights)
    return _scorer
