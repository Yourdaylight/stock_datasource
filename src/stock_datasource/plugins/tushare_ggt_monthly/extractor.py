"""港股通每月成交统计数据提取器"""

import json
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import tushare as ts


class GgtMonthlyExtractor:
    """港股通每月成交统计数据提取器"""

    def __init__(self, token: str | None = None):
        """初始化提取器"""
        if token:
            ts.set_token(token)
        self.pro = ts.pro_api()

        config_path = Path(__file__).parent / "config.json"
        with open(config_path) as f:
            self.config = json.load(f)

        self.api_name = self.config["api_name"]
        self.fields = [
            "month",
            "day_buy_amt",
            "day_buy_vol",
            "day_sell_amt",
            "day_sell_vol",
            "total_buy_amt",
            "total_buy_vol",
            "total_sell_amt",
            "total_sell_vol",
        ]

    def extract(
        self,
        month: Optional[str] = None,
        start_month: Optional[str] = None,
        end_month: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        提取港股通每月成交统计数据

        Args:
            month: 交易月份（支持单月或多月，逗号分隔）
            start_month: 开始月份
            end_month: 结束月份

        Returns:
            pd.DataFrame: 港股通每月成交统计数据
        """
        params: dict[str, Any] = {}
        if month:
            params["month"] = month
        if start_month:
            params["start_month"] = start_month
        if end_month:
            params["end_month"] = end_month

        df = self.pro.query(self.api_name, **params, fields=",".join(self.fields))
        return df
