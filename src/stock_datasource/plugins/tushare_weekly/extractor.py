"""周线行情数据提取器"""

import json
from pathlib import Path
from typing import Any

import pandas as pd
import tushare as ts


class WeeklyExtractor:
    """周线行情数据提取器"""

    def __init__(self, token: str | None = None):
        """初始化提取器"""
        if token:
            ts.set_token(token)
        self.pro = ts.pro_api()

        config_path = Path(__file__).parent / "config.json"
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

    def extract(
        self,
        ts_code: str | None = None,
        trade_date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """
        提取周线行情数据

        Args:
            ts_code: 股票代码
            trade_date: 交易日期（每周最后一个交易日）
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            周线行情DataFrame
        """
        params: dict[str, Any] = {}
        if ts_code:
            params["ts_code"] = ts_code
        if trade_date:
            params["trade_date"] = trade_date
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        df = self.pro.weekly(
            **params,
            fields=",".join(self.config["fields"]),
        )

        return df

    def extract_by_date_range(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """按日期范围提取单只股票周线数据"""
        return self.extract(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
        )

    def extract_by_trade_date(self, trade_date: str) -> pd.DataFrame:
        """提取指定交易日所有股票周线数据"""
        return self.extract(trade_date=trade_date)
