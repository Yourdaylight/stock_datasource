"""港股通十大成交股数据提取器"""

import json
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import tushare as ts


class GgtTop10Extractor:
    """港股通十大成交股数据提取器"""

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
            "ts_code",
            "name",
            "close",
            "p_change",
            "rank",
            "market_type",
            "amount",
            "net_amount",
            "sh_amount",
            "sh_net_amount",
            "sh_buy",
            "sh_sell",
            "sz_amount",
            "sz_net_amount",
            "sz_buy",
            "sz_sell",
        ]

    def extract(
        self,
        ts_code: Optional[str] = None,
        trade_date: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        market_type: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        提取港股通十大成交股数据

        Args:
            ts_code: 股票代码（与trade_date二选一）
            trade_date: 交易日期（与ts_code二选一）
            start_date: 开始日期
            end_date: 结束日期
            market_type: 市场类型，2-港股通(沪)，4-港股通(深)

        Returns:
            pd.DataFrame: 港股通十大成交股数据
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

        df = self.pro.query(self.api_name, **params, fields=",".join(self.fields))
        return df
