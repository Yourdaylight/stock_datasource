"""TuShare rt_idx_k plugin implementation."""

import json
from pathlib import Path
from typing import Any

import pandas as pd

from stock_datasource.plugins import BasePlugin

from .extractor import RtIdxKExtractor


class TuShareRtIdxKPlugin(BasePlugin):
    @property
    def name(self) -> str:
        return "tushare_rt_idx_k"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "TuShare realtime index daily K-line from rt_idx_k API"

    @property
    def api_rate_limit(self) -> int:
        config_file = Path(__file__).parent / "config.json"
        with open(config_file, encoding="utf-8") as f:
            config = json.load(f)
        return config.get("rate_limit", 120)

    def get_schema(self) -> dict[str, Any]:
        schema_file = Path(__file__).parent / "schema.json"
        with open(schema_file, encoding="utf-8") as f:
            return json.load(f)

    def extract_data(self, **kwargs) -> pd.DataFrame:
        ts_code = kwargs.get("ts_code")
        extractor = RtIdxKExtractor()
        if not ts_code:
            return pd.DataFrame()
        return extractor.extract(ts_code=ts_code)

    def load_data(self, data: pd.DataFrame) -> dict[str, Any]:
        """Load realtime index K-line into ODS table."""
        if not self.db:
            self.logger.error("Database not initialized")
            return {"status": "failed", "error": "Database not initialized"}

        if data.empty:
            self.logger.warning("No data to load")
            return {"status": "no_data", "loaded_records": 0}

        try:
            table_name = "ods_rt_kline_daily_index"
            self.logger.info(f"Loading {len(data)} records into {table_name}")
            ods_data = self._prepare_data_for_insert(table_name, data)
            self.db.insert_dataframe(table_name, ods_data)
            self.logger.info(f"Loaded {len(ods_data)} records into {table_name}")
            return {
                "status": "success",
                "table": table_name,
                "loaded_records": len(ods_data),
            }
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            return {"status": "failed", "error": str(e)}
