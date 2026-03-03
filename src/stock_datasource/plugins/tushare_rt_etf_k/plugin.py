"""TuShare rt_etf_k plugin implementation."""

from pathlib import Path
import json
from typing import Any, Dict

import pandas as pd

from stock_datasource.plugins import BasePlugin
from .extractor import RtEtfKExtractor


class TuShareRtEtfKPlugin(BasePlugin):
    @property
    def name(self) -> str:
        return "tushare_rt_etf_k"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "TuShare realtime ETF daily K-line from rt_etf_k API"

    @property
    def api_rate_limit(self) -> int:
        config_file = Path(__file__).parent / "config.json"
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config.get("rate_limit", 120)

    def get_schema(self) -> Dict[str, Any]:
        schema_file = Path(__file__).parent / "schema.json"
        with open(schema_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def extract_data(self, **kwargs) -> pd.DataFrame:
        ts_code = kwargs.get("ts_code")
        extractor = RtEtfKExtractor()
        if not ts_code:
            return pd.DataFrame()
        return extractor.extract(ts_code=ts_code)
