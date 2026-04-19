"""Index module service layer.

Memory is now handled by base_agent.LangGraphAgent, which provides:
- A: LangGraph MemorySaver for automatic checkpoint
- B: Tool result compression
- D: Session-based shared state storage
"""

import logging
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd

from stock_datasource.models.database import _to_clickhouse_literal

logger = logging.getLogger(__name__)


def _get_db():
    """Get database connection."""
    from stock_datasource.models.database import db_client

    return db_client


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize dataframe values for JSON serialization and Pydantic validation."""
    if df is None or df.empty:
        return df
    # Replace NaN/NaT with None
    df = df.replace({np.nan: None})

    # Convert datetime-like objects to strings (YYYY-MM-DD format)
    def convert_value(x):
        if isinstance(x, (datetime, pd.Timestamp)) or isinstance(x, date):
            return x.strftime("%Y-%m-%d")
        return x

    df = df.map(convert_value)
    return df


def _execute_query(query: str) -> list[dict[str, Any]]:
    """Execute query and return results as list of dicts."""
    db = _get_db()
    df = db.execute_query(query)
    if df is None or df.empty:
        return []
    df = _normalize_df(df)
    return df.to_dict("records")


class IndexService:
    """Service for Index operations."""

    def get_indices(
        self,
        market: str | None = None,
        category: str | None = None,
        keyword: str | None = None,
        trade_date: str | None = None,
        publisher: str | None = None,
        pct_chg_min: float | None = None,
        pct_chg_max: float | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """Get index list with pagination and filters.

        Args:
            market: Filter by market (SSE/SZSE/CSI)
            category: Filter by category
            keyword: Search keyword in name
            trade_date: Trade date for daily data (YYYYMMDD), defaults to latest
            publisher: Filter by publisher
            pct_chg_min: Minimum price change percentage
            pct_chg_max: Maximum price change percentage
            page: Page number
            page_size: Page size

        Returns:
            Dict with total, page, page_size, data, trade_date
        """
        # Determine target date
        if trade_date:
            target_date = trade_date
        else:
            date_query = "SELECT max(trade_date) as max_date FROM ods_idx_factor_pro"
            date_result = _execute_query(date_query)
            if date_result and date_result[0].get("max_date"):
                td = date_result[0]["max_date"]
                if hasattr(td, "strftime"):
                    target_date = td.strftime("%Y%m%d")
                elif isinstance(td, str):
                    target_date = td.replace("-", "")
                else:
                    target_date = None
            else:
                target_date = None

        if not target_date:
            return {
                "total": 0,
                "page": page,
                "page_size": page_size,
                "data": [],
                "trade_date": None,
            }

        # Build WHERE clauses
        where_clauses = [f"d.trade_date = {_to_clickhouse_literal(target_date)}"]

        if market:
            where_clauses.append(f"b.market = {_to_clickhouse_literal(market)}")
        if category:
            where_clauses.append(f"b.category = {_to_clickhouse_literal(category)}")
        if keyword:
            kw_literal = _to_clickhouse_literal(f"%{keyword}%")
            where_clauses.append(
                f"(b.name ILIKE {kw_literal} OR b.fullname ILIKE {kw_literal} OR b.ts_code LIKE {kw_literal})"
            )
        if publisher:
            where_clauses.append(f"b.publisher = {_to_clickhouse_literal(publisher)}")
        if pct_chg_min is not None:
            where_clauses.append(
                f"ROUND((d.close - d.pre_close) / d.pre_close * 100, 2) >= {float(pct_chg_min)}"
            )
        if pct_chg_max is not None:
            where_clauses.append(
                f"ROUND((d.close - d.pre_close) / d.pre_close * 100, 2) <= {float(pct_chg_max)}"
            )

        where_sql = " AND ".join(where_clauses)

        # Count total
        count_query = f"""
        SELECT count() as total
        FROM ods_idx_factor_pro d
        INNER JOIN (SELECT * FROM dim_index_basic FINAL) b ON d.ts_code = b.ts_code
        WHERE {where_sql}
        """
        count_result = _execute_query(count_query)
        total = count_result[0].get("total", 0) if count_result else 0

        if total == 0:
            return {
                "total": 0,
                "page": page,
                "page_size": page_size,
                "data": [],
                "trade_date": target_date,
            }

        # Get data with pagination
        offset = (page - 1) * page_size
        query = f"""
        SELECT 
            b.ts_code AS ts_code,
            b.name AS name,
            b.fullname AS fullname,
            b.market AS market,
            b.publisher AS publisher,
            b.index_type AS index_type,
            b.category AS category,
            b.base_date AS base_date,
            b.base_point AS base_point,
            b.list_date AS list_date,
            b.weight_rule AS weight_rule,
            b.desc AS desc,
            d.trade_date AS trade_date,
            d.open AS open,
            d.high AS high,
            d.low AS low,
            d.close AS close,
            d.pre_close AS pre_close,
            ROUND((d.close - d.pre_close) / d.pre_close * 100, 2) AS pct_chg,
            d.vol AS vol,
            d.amount AS amount
        FROM ods_idx_factor_pro d
        INNER JOIN (SELECT * FROM dim_index_basic FINAL) b ON d.ts_code = b.ts_code
        WHERE {where_sql}
        ORDER BY d.amount DESC NULLS LAST, b.ts_code ASC
        LIMIT {page_size}
        OFFSET {offset}
        """

        data = _execute_query(query)

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "data": data,
            "trade_date": target_date,
        }

    def get_index_detail(self, ts_code: str) -> dict[str, Any] | None:
        """Get index detail by code.

        Args:
            ts_code: Index code

        Returns:
            Index detail dict or None
        """
        query = f"""
        SELECT 
            ts_code,
            name,
            fullname,
            market,
            publisher,
            index_type,
            category,
            base_date,
            base_point,
            list_date,
            weight_rule,
            desc,
            exp_date
        FROM dim_index_basic FINAL
        WHERE ts_code = {_to_clickhouse_literal(ts_code)}
        """
        result = _execute_query(query)
        return result[0] if result else None

    def get_constituents(
        self,
        ts_code: str,
        trade_date: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Get index constituents.

        Args:
            ts_code: Index code
            trade_date: Trade date (YYYYMMDD), defaults to latest
            limit: Max number of constituents to return

        Returns:
            Dict with constituents data
        """
        # Get latest date if not specified
        if not trade_date:
            date_query = f"""
            SELECT max(trade_date) as latest_date
            FROM ods_index_weight
            WHERE index_code = {_to_clickhouse_literal(ts_code)}
            """
            date_result = _execute_query(date_query)
            if date_result and date_result[0].get("latest_date"):
                latest = date_result[0]["latest_date"]
                # Handle both string and datetime types
                if hasattr(latest, "strftime"):
                    trade_date = latest.strftime("%Y%m%d")
                elif isinstance(latest, str) and latest not in (
                    "",
                    "1970-01-01",
                    "1970-01-01 00:00:00",
                ):
                    trade_date = latest.replace("-", "")
                else:
                    trade_date = None
            else:
                trade_date = None

        if not trade_date:
            return {
                "index_code": ts_code,
                "trade_date": None,
                "constituent_count": 0,
                "total_weight": 0,
                "constituents": [],
            }

        query = f"""
        SELECT 
            index_code,
            con_code,
            trade_date,
            weight
        FROM ods_index_weight
        WHERE index_code = {_to_clickhouse_literal(ts_code)}
        AND trade_date = {_to_clickhouse_literal(trade_date)}
        ORDER BY weight DESC
        LIMIT {limit}
        """

        constituents = _execute_query(query)

        # Get total count
        count_query = f"""
        SELECT count() as cnt
        FROM ods_index_weight
        WHERE index_code = {_to_clickhouse_literal(ts_code)}
        AND trade_date = {_to_clickhouse_literal(trade_date)}
        """
        count_result = _execute_query(count_query)
        total_count = (
            count_result[0].get("cnt", 0) if count_result else len(constituents)
        )

        total_weight = sum(c.get("weight", 0) or 0 for c in constituents)

        return {
            "index_code": ts_code,
            "trade_date": trade_date,
            "constituent_count": total_count,
            "total_weight": round(total_weight, 2),
            "constituents": constituents,
        }

    def get_factors(
        self,
        ts_code: str,
        days: int = 30,
        indicators: list[str] | None = None,
    ) -> dict[str, Any]:
        """Get technical factor data.

        Args:
            ts_code: Index code
            days: Number of days
            indicators: Specific indicators to return

        Returns:
            Dict with factor data
        """
        # Whitelist of allowed indicator columns to prevent column name injection
        _ALLOWED_INDICATORS = {
            "ts_code",
            "trade_date",
            "open",
            "high",
            "low",
            "close",
            "vol",
            "amount",
            "ma_5",
            "ma_10",
            "ma_20",
            "ma_60",
            "ma_120",
            "ma_250",
            "ema_5",
            "ema_10",
            "ema_20",
            "ema_60",
            "macd",
            "macd_dif",
            "macd_dea",
            "rsi_6",
            "rsi_12",
            "rsi_24",
            "kdj_k",
            "kdj_d",
            "kdj_j",
            "boll_upper",
            "boll_mid",
            "boll_lower",
            "atr",
            "cci",
            "wr",
            "bias",
            "turnover_rate",
            "volume_ratio",
            "pe",
            "pb",
            "ps",
            "pcf",
            "pre_close",
            "pct_chg",
            "change",
        }
        if indicators:
            base_cols = [
                "ts_code",
                "trade_date",
                "open",
                "high",
                "low",
                "close",
                "vol",
                "amount",
            ]
            safe_indicators = [
                i for i in indicators if i in _ALLOWED_INDICATORS and i not in base_cols
            ]
            cols = base_cols + safe_indicators
            columns_str = ", ".join(cols)
        else:
            columns_str = "*"

        query = f"""
        SELECT {columns_str}
        FROM ods_idx_factor_pro
        WHERE ts_code = {_to_clickhouse_literal(ts_code)}
        ORDER BY trade_date DESC
        LIMIT {days}
        """

        data = _execute_query(query)
        data.reverse()  # Return in chronological order

        return {"ts_code": ts_code, "days": len(data), "data": data}

    def get_markets(self) -> list[dict[str, Any]]:
        """Get all available markets."""
        query = """
        SELECT DISTINCT market, count() as count
        FROM dim_index_basic FINAL
        WHERE market IS NOT NULL AND market != ''
        GROUP BY market
        ORDER BY count DESC
        """
        return _execute_query(query)

    def get_categories(self) -> list[dict[str, Any]]:
        """Get all available categories."""
        query = """
        SELECT DISTINCT category, count() as count
        FROM dim_index_basic FINAL
        WHERE category IS NOT NULL AND category != ''
        GROUP BY category
        ORDER BY count DESC
        """
        return _execute_query(query)

    def get_publishers(self) -> list[dict[str, Any]]:
        """Get all available publishers."""
        query = """
        SELECT 
            publisher as value,
            publisher as label,
            count() as count
        FROM dim_index_basic FINAL
        WHERE publisher IS NOT NULL AND publisher != ''
        GROUP BY publisher
        ORDER BY count DESC
        """
        return _execute_query(query)

    def get_trade_dates(self, limit: int = 30) -> list[str]:
        """Get available trade dates from index daily data.

        Args:
            limit: Maximum number of dates to return

        Returns:
            List of trade dates in YYYYMMDD format, descending order
        """
        query = f"""
        SELECT DISTINCT trade_date
        FROM ods_idx_factor_pro
        ORDER BY trade_date DESC
        LIMIT {int(limit)}
        """
        result = _execute_query(query)
        dates = []
        for r in result:
            td = r.get("trade_date")
            if td:
                # Handle different date formats
                if hasattr(td, "strftime"):
                    dates.append(td.strftime("%Y%m%d"))
                elif isinstance(td, str):
                    dates.append(td.replace("-", ""))
        return dates

    def get_daily(
        self,
        ts_code: str,
        days: int = 30,
    ) -> dict[str, Any]:
        """Get index daily data.

        Args:
            ts_code: Index code
            days: Number of days

        Returns:
            Dict with ts_code, days, data
        """
        ts_code_literal = _to_clickhouse_literal(ts_code)
        query = f"""
        SELECT 
            ts_code,
            trade_date,
            open,
            high,
            low,
            close,
            pre_close,
            ROUND((close - pre_close) / pre_close * 100, 2) as pct_chg,
            vol,
            amount
        FROM ods_idx_factor_pro
        WHERE ts_code = {ts_code_literal}
        ORDER BY trade_date DESC
        LIMIT {days}
        """

        data = _execute_query(query)
        data.reverse()  # Chronological order

        return {"ts_code": ts_code, "days": len(data), "data": data}

    def get_kline(
        self,
        ts_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
        freq: str = "daily",
    ) -> dict[str, Any]:
        """Get index K-line data.

        Args:
            ts_code: Index code
            start_date: Start date (YYYYMMDD)
            end_date: End date (YYYYMMDD)
            freq: Data frequency ('daily', 'weekly', 'monthly')

        Returns:
            Dict with ts_code, name, freq, data
        """
        # Get index name
        name_query = f"SELECT name FROM dim_index_basic FINAL WHERE ts_code = {_to_clickhouse_literal(ts_code)}"
        name_result = _execute_query(name_query)
        name = name_result[0].get("name") if name_result else None

        # Determine table based on frequency
        freq_table_map = {
            "daily": "ods_idx_factor_pro",
            "weekly": "ods_index_weekly",
            "monthly": "ods_index_monthly",
        }
        table = freq_table_map.get(freq, "ods_idx_factor_pro")

        # Build date filter
        date_conditions = []
        if start_date:
            date_conditions.append(
                f"trade_date >= {_to_clickhouse_literal(start_date)}"
            )
        if end_date:
            date_conditions.append(f"trade_date <= {_to_clickhouse_literal(end_date)}")

        date_filter = " AND ".join(date_conditions) if date_conditions else "1=1"

        # Different columns for different tables
        if freq == "daily":
            pct_chg_col = "ROUND((close - pre_close) / pre_close * 100, 2) as pct_chg"
        else:
            pct_chg_col = "pct_chg"

        query = f"""
        SELECT 
            ts_code,
            trade_date,
            open,
            high,
            low,
            close,
            vol,
            amount,
            {pct_chg_col}
        FROM {table}
        WHERE ts_code = {_to_clickhouse_literal(ts_code)}
        AND {date_filter}
        ORDER BY trade_date ASC
        """

        data = _execute_query(query)

        return {"ts_code": ts_code, "name": name, "freq": freq, "data": data}

    async def analyze_index(
        self,
        ts_code: str,
        question: str | None = None,
        user_id: str = "default",
        clear_history: bool = False,
    ) -> dict[str, Any]:
        """Analyze index using Index Agent with conversation memory.

        Memory is handled by base_agent.LangGraphAgent which provides:
        - LangGraph MemorySaver for checkpoint-based memory
        - Automatic conversation history management
        - Tool result caching
        - Automatic summarization for long conversations

        Args:
            ts_code: Index code
            question: Optional specific question
            user_id: User identifier for session tracking
            clear_history: Whether to clear conversation history before this request

        Returns:
            Analysis result with session info
        """
        from stock_datasource.agents import get_index_agent

        agent = get_index_agent()

        # Build task
        if question:
            task = f"请分析指数 {ts_code}，重点回答：{question}"
        else:
            task = f"请对指数 {ts_code} 进行全面的量化分析"

        # Execute agent with context - memory is managed by base_agent
        context = {
            "user_id": user_id,
            "context_key": ts_code,  # Use ts_code as context key for session isolation
            "clear_history": clear_history,
        }

        result = await agent.execute(task, context)

        return {
            "ts_code": ts_code,
            "question": question,
            "response": result.response,
            "success": result.success,
            "metadata": result.metadata,
            "session_id": result.metadata.get("session_id", ""),
            "history_length": result.metadata.get("history_length", 0),
        }

    def get_quick_analysis(self, ts_code: str) -> dict[str, Any]:
        """Get quick analysis without AI (direct data analysis).

        Args:
            ts_code: Index code

        Returns:
            Quick analysis result
        """
        from stock_datasource.agents.index_tools import get_comprehensive_analysis

        return get_comprehensive_analysis(ts_code)


# Singleton instance
_index_service: IndexService | None = None


def get_index_service() -> IndexService:
    """Get Index service singleton."""
    global _index_service
    if _index_service is None:
        _index_service = IndexService()
    return _index_service
