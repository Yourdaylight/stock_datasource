"""港股通每日成交统计数据提取器"""

import json
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import tushare as ts


class GgtDailyExtractor:
    """港股通每日成交统计数据提取器"""

    def __init__(self, token: str | None = None):
        """初始化提取器"""
        if token:
            ts.set_token(token)
        self.pro = ts.pro_api()

        config_path = Path(__file__).parent / "config.json"
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.api_name = self.config["api_name"]
        self.fields = [
            "trade_date",
            "buy_amount",
            "buy_volume",
            "sell_amount",
            "sell_volume",
        ]

    def extract(
        self,
        trade_date: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        提取港股通每日成交统计数据

        Args:
            trade_date: 交易日期（支持单日或多日，逗号分隔）
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            pd.DataFrame: 港股通每日成交统计数据
        """
        params: dict[str, Any] = {}
        if trade_date:
            params["trade_date"] = trade_date
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        df = self.pro.query(self.api_name, **params, fields=",".join(self.fields))
        return df
