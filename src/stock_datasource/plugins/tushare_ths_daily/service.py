"""TuShare THS daily data query service."""

from datetime import datetime
from typing import Any, Dict, List

import pandas as pd

from stock_datasource.core.base_service import BaseService, QueryParam, query_method


def _convert_to_json_serializable(obj: Any) -> Any:
    """Convert non-JSON-serializable objects to JSON-compatible types."""
    if isinstance(obj, pd.Timestamp):
        return obj.strftime("%Y%m%d")
    if isinstance(obj, dict):
        return {k: _convert_to_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_to_json_serializable(item) for item in obj]
    if pd.isna(obj):
        return None
    return obj


class TuShareTHSDailyService(BaseService):
    """Query service for TuShare THS sector index daily data."""

    def __init__(self):
        super().__init__("tushare_ths_daily")

    @query_method(
        description="Query THS sector index daily data by code and date range",
        params=[
            QueryParam(
                name="ts_code",
                type="str",
                description="THS index code, e.g., 865001.TI",
                required=True,
            ),
            QueryParam(
                name="start_date",
                type="str",
                description="Start date in YYYYMMDD format",
                required=True,
            ),
            QueryParam(
                name="end_date",
                type="str",
                description="End date in YYYYMMDD format",
                required=True,
            ),
        ],
    )
    def get_ths_daily_data(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        """Query THS daily data."""
        start_dt = datetime.strptime(start_date, "%Y%m%d").date()
        end_dt = datetime.strptime(end_date, "%Y%m%d").date()

        query = """
        SELECT
            ts_code,
            trade_date,
            open,
            high,
            low,
            close,
            pre_close,
            avg_price,
            change,
            pct_change,
            vol,
            turnover_rate,
            total_mv,
            float_mv
        FROM ods_ths_daily
        WHERE ts_code = %(ts_code)s
        AND trade_date >= %(start_date)s
        AND trade_date <= %(end_date)s
        ORDER BY trade_date ASC
        """

        df = self.db.execute_query(
            query,
            {
                "ts_code": ts_code,
                "start_date": start_dt,
                "end_date": end_dt,
            },
        )
        records = df.to_dict("records")
        return [_convert_to_json_serializable(record) for record in records]

    @query_method(
        description="Query latest THS daily data for multiple indices",
        params=[
            QueryParam(
                name="ts_codes",
                type="list",
                description="List of THS index codes",
                required=True,
            ),
            QueryParam(
                name="limit",
                type="int",
                description="Number of latest records per index",
                required=False,
                default=1,
            ),
        ],
    )
    def get_latest_ths_daily(
        self,
        ts_codes: List[str],
        limit: int = 1,
    ) -> List[Dict[str, Any]]:
        """Query latest THS daily data for multiple indices."""
        query = """
        SELECT
            ts_code,
            trade_date,
            open,
            high,
            low,
            close,
            pct_change,
            vol,
            turnover_rate
        FROM (
            SELECT
                *,
                ROW_NUMBER() OVER (PARTITION BY ts_code ORDER BY trade_date DESC) as rn
            FROM ods_ths_daily
            WHERE ts_code IN %(ts_codes)s
        )
        WHERE rn <= %(limit)s
        ORDER BY ts_code, trade_date DESC
        """

        df = self.db.execute_query(
            query,
            {
                "ts_codes": tuple(ts_codes),
                "limit": limit,
            },
        )
        records = df.to_dict("records")
        return [_convert_to_json_serializable(record) for record in records]

    @query_method(
        description="Get THS daily data statistics for an index",
        params=[
            QueryParam(
                name="ts_code",
                type="str",
                description="THS index code",
                required=True,
            ),
            QueryParam(
                name="start_date",
                type="str",
                description="Start date in YYYYMMDD format",
                required=True,
            ),
            QueryParam(
                name="end_date",
                type="str",
                description="End date in YYYYMMDD format",
                required=True,
            ),
        ],
    )
    def get_ths_daily_stats(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
    ) -> Dict[str, Any]:
        """Get THS daily data statistics."""
        start_dt = datetime.strptime(start_date, "%Y%m%d").date()
        end_dt = datetime.strptime(end_date, "%Y%m%d").date()

        query = """
        SELECT
            COUNT(*) as trading_days,
            MIN(close) as min_close,
            MAX(close) as max_close,
            AVG(close) as avg_close,
            SUM(vol) as total_vol,
            AVG(pct_change) as avg_pct_change
        FROM ods_ths_daily
        WHERE ts_code = %(ts_code)s
        AND trade_date >= %(start_date)s
        AND trade_date <= %(end_date)s
        """

        df = self.db.execute_query(
            query,
            {
                "ts_code": ts_code,
                "start_date": start_dt,
                "end_date": end_dt,
            },
        )
        if df.empty:
            return {}
        return _convert_to_json_serializable(df.iloc[0].to_dict())
