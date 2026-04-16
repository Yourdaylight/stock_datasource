"""TuShare stk_rewards (管理层薪酬和持股) query service."""

from typing import Any

import pandas as pd

from stock_datasource.core.base_service import BaseService, QueryParam, query_method


def _convert_to_json_serializable(obj: Any) -> Any:
    if pd.isna(obj):
        return None
    return obj


class TuShareStkRewardsService(BaseService):
    """Query service for TuShare stk_rewards data."""

    def __init__(self):
        super().__init__("tushare_stk_rewards")

    @query_method(
        description="Query management rewards by stock code",
        params=[
            QueryParam(
                name="ts_code", type="str", description="Stock code", required=True
            ),
            QueryParam(
                name="end_date",
                type="str",
                description="Report period YYYYMMDD (optional)",
                required=False,
            ),
        ],
    )
    def get_stk_rewards(
        self, ts_code: str, end_date: str | None = None
    ) -> list[dict[str, Any]]:
        where = f"ts_code = '{ts_code}'"
        if end_date:
            where += f" AND end_date = '{end_date}'"
        query = f"""
        SELECT ts_code, ann_date, end_date, name, title, reward, hold_vol
        FROM ods_stk_rewards WHERE {where} ORDER BY end_date DESC, name
        """
        df = self.db.execute_query(query)
        return [
            {k: _convert_to_json_serializable(v) for k, v in r.items()}
            for r in df.to_dict("records")
        ]

    @query_method(
        description="Query top rewarded managers",
        params=[
            QueryParam(
                name="end_date",
                type="str",
                description="Report period YYYYMMDD",
                required=True,
            ),
            QueryParam(
                name="limit",
                type="int",
                description="Number of records to return",
                required=False,
            ),
        ],
    )
    def get_top_rewards(self, end_date: str, limit: int = 100) -> list[dict[str, Any]]:
        query = f"""
        SELECT ts_code, ann_date, end_date, name, title, reward, hold_vol
        FROM ods_stk_rewards 
        WHERE end_date = '{end_date}' AND reward IS NOT NULL
        ORDER BY reward DESC
        LIMIT {limit}
        """
        df = self.db.execute_query(query)
        return [
            {k: _convert_to_json_serializable(v) for k, v in r.items()}
            for r in df.to_dict("records")
        ]
