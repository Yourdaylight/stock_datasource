"""TuShare THS index metadata query service."""

from typing import Any, Dict, List, Optional

import pandas as pd

from stock_datasource.core.base_service import BaseService, QueryParam, query_method


def _convert_to_json_serializable(obj: Any) -> Any:
    """Convert non-JSON-serializable objects to JSON-compatible types."""
    if isinstance(obj, pd.Timestamp):
        return obj.strftime("%Y%m%d")
    if hasattr(obj, "isoformat"):  # date/datetime
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _convert_to_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_to_json_serializable(item) for item in obj]
    if pd.isna(obj):
        return None
    return obj


class TuShareTHSIndexService(BaseService):
    """Query service for TuShare THS sector index metadata."""

    def __init__(self):
        super().__init__("tushare_ths_index")

    @query_method(
        description="Query THS sector index list with optional filters",
        params=[
            QueryParam(
                name="exchange",
                type="str",
                description="Market type: A-股票, HK-港股, US-美股",
                required=False,
            ),
            QueryParam(
                name="index_type",
                type="str",
                description="Index type: N-概念, I-行业, R-地域, S-特色, ST-风格, TH-主题, BB-宽基",
                required=False,
            ),
            QueryParam(
                name="limit",
                type="int",
                description="Maximum number of records to return",
                required=False,
                default=1000,
            ),
        ],
    )
    def get_ths_index_list(
        self,
        exchange: Optional[str] = None,
        index_type: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Query THS index list with optional filters."""
        conditions = ["1=1"]
        params: Dict[str, Any] = {"limit": limit}

        if exchange:
            conditions.append("exchange = %(exchange)s")
            params["exchange"] = exchange

        if index_type:
            conditions.append("type = %(index_type)s")
            params["index_type"] = index_type

        where_clause = " AND ".join(conditions)

        query = f"""
        SELECT
            ts_code,
            name,
            count,
            exchange,
            list_date,
            type
        FROM ods_ths_index
        WHERE {where_clause}
        ORDER BY ts_code ASC
        LIMIT %(limit)s
        """

        df = self.db.execute_query(query, params)
        records = df.to_dict("records")
        return [_convert_to_json_serializable(record) for record in records]

    @query_method(
        description="Get THS index by code",
        params=[
            QueryParam(
                name="ts_code",
                type="str",
                description="THS index code, e.g., 885001.TI",
                required=True,
            ),
        ],
    )
    def get_ths_index_by_code(
        self,
        ts_code: str,
    ) -> Optional[Dict[str, Any]]:
        """Get THS index details by code."""
        query = """
        SELECT
            ts_code,
            name,
            count,
            exchange,
            list_date,
            type
        FROM ods_ths_index
        WHERE ts_code = %(ts_code)s
        LIMIT 1
        """

        df = self.db.execute_query(query, {"ts_code": ts_code})
        if df.empty:
            return None
        return _convert_to_json_serializable(df.iloc[0].to_dict())

    @query_method(
        description="Search THS index by name keyword",
        params=[
            QueryParam(
                name="keyword",
                type="str",
                description="Keyword to search in index name",
                required=True,
            ),
            QueryParam(
                name="limit",
                type="int",
                description="Maximum number of records to return",
                required=False,
                default=50,
            ),
        ],
    )
    def search_ths_index_by_name(
        self,
        keyword: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Search THS index by name keyword."""
        query = """
        SELECT
            ts_code,
            name,
            count,
            exchange,
            list_date,
            type
        FROM ods_ths_index
        WHERE name LIKE %(pattern)s
        ORDER BY count DESC NULLS LAST
        LIMIT %(limit)s
        """

        df = self.db.execute_query(
            query,
            {
                "pattern": f"%{keyword}%",
                "limit": limit,
            },
        )
        records = df.to_dict("records")
        return [_convert_to_json_serializable(record) for record in records]

    @query_method(
        description="Get THS index statistics by type",
        params=[],
    )
    def get_ths_index_stats(self) -> List[Dict[str, Any]]:
        """Get THS index statistics grouped by type."""
        query = """
        SELECT
            type,
            exchange,
            COUNT(*) as index_count,
            SUM(count) as total_constituents,
            AVG(count) as avg_constituents
        FROM ods_ths_index
        GROUP BY type, exchange
        ORDER BY index_count DESC
        """

        df = self.db.execute_query(query, {})
        records = df.to_dict("records")
        return [_convert_to_json_serializable(record) for record in records]
