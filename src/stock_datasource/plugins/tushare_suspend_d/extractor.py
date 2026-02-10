"""每日停复牌信息数据提取器"""

import json
from pathlib import Path
from typing import Any

import pandas as pd
import tushare as ts


class SuspendDExtractor:
    """每日停复牌信息数据提取器"""

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
        suspend_type: str | None = None,
    ) -> pd.DataFrame:
        """
        提取每日停复牌信息

        Args:
            ts_code: 股票代码（支持多个）
            trade_date: 交易日日期
            start_date: 开始日期
            end_date: 结束日期
            suspend_type: 停复牌类型：S-停牌，R-复牌

        Returns:
            停复牌信息DataFrame
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
        if suspend_type:
            params["suspend_type"] = suspend_type

        df = self.pro.suspend_d(
            **params,
            fields=",".join(self.config["fields"]),
        )

        return df

    def extract_suspended_stocks(self, trade_date: str) -> pd.DataFrame:
        """提取指定日期停牌股票"""
        return self.extract(trade_date=trade_date, suspend_type="S")

    def extract_resumed_stocks(self, trade_date: str) -> pd.DataFrame:
        """提取指定日期复牌股票"""
        return self.extract(trade_date=trade_date, suspend_type="R")
