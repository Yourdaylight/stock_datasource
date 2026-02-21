"""沪深股通十大成交股数据提取器"""

import json
from pathlib import Path
from typing import Any

import pandas as pd
import tushare as ts


class HsgtTop10Extractor:
    """沪深股通十大成交股数据提取器"""

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
        market_type: str | None = None,
    ) -> pd.DataFrame:
        """
        提取沪深股通十大成交股数据

        Args:
            ts_code: 股票代码
            trade_date: 交易日期
            start_date: 开始日期
            end_date: 结束日期
            market_type: 市场类型（1：沪市，3：深市）

        Returns:
            十大成交股DataFrame
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
        if market_type:
            params["market_type"] = market_type

        df = self.pro.hsgt_top10(
            **params,
            fields=",".join(self.config["fields"]),
        )

        return df

    def extract_sh_top10(self, trade_date: str) -> pd.DataFrame:
        """提取沪股通前十大成交股"""
        return self.extract(trade_date=trade_date, market_type="1")

    def extract_sz_top10(self, trade_date: str) -> pd.DataFrame:
        """提取深股通前十大成交股"""
        return self.extract(trade_date=trade_date, market_type="3")

    def extract_all_top10(self, trade_date: str) -> pd.DataFrame:
        """提取沪深股通前十大成交股"""
        return self.extract(trade_date=trade_date)
