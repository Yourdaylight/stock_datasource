"""TuShare THS daily data plugin implementation."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

import pandas as pd

from stock_datasource.plugins import BasePlugin
from stock_datasource.core.base_plugin import PluginCategory, PluginRole
from .extractor import extractor


class TuShareTHSDailyPlugin(BasePlugin):
    """TuShare THS sector index daily data plugin."""

    @property
    def name(self) -> str:
        return "tushare_ths_daily"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "TuShare THS sector index daily data"

    @property
    def api_rate_limit(self) -> int:
        config_file = Path(__file__).parent / "config.json"
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config.get("rate_limit", 120)

    def get_schema(self) -> Dict[str, Any]:
        """Get table schema from separate JSON file."""
        schema_file = Path(__file__).parent / "schema.json"
        with open(schema_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_category(self) -> PluginCategory:
        """Get plugin category."""
        return PluginCategory.INDEX

    def get_role(self) -> PluginRole:
        """Get plugin role."""
        return PluginRole.PRIMARY

    def get_dependencies(self) -> List[str]:
        """Get plugin dependencies."""
        return []

    def extract_data(self, **kwargs) -> pd.DataFrame:
        """Extract THS daily data from TuShare."""
        trade_date = kwargs.get("trade_date")
        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")
        ts_code = kwargs.get("ts_code")
        fields = kwargs.get("fields")

        if not trade_date and not (start_date and end_date):
            raise ValueError("Either trade_date or (start_date and end_date) is required")

        self.logger.info(
            "Extracting THS daily data with params: "
            f"trade_date={trade_date}, start_date={start_date}, end_date={end_date}, ts_code={ts_code}"
        )

        data = extractor.extract(
            trade_date=trade_date,
            start_date=start_date,
            end_date=end_date,
            ts_code=ts_code,
            fields=fields,
        )

        if data.empty:
            self.logger.warning("No THS daily data found for the given parameters")
            return pd.DataFrame()

        self.logger.info(f"Extracted {len(data)} THS daily records")
        return data

    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate THS daily data."""
        if data.empty:
            self.logger.warning("Empty THS daily data")
            return False

        required_columns = ["ts_code", "trade_date", "close"]
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            return False

        for col in required_columns:
            if data[col].isnull().any():
                self.logger.error(f"Found null values in required column: {col}")
                return False

        self.logger.info(f"THS daily data validation passed for {len(data)} records")
        return True

    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data for database insertion."""
        if data.empty:
            return data

        # 确保所有预期列都存在（API 可能不返回某些字段）
        numeric_columns = [
            "open",
            "high",
            "low",
            "close",
            "pre_close",
            "avg_price",
            "change",
            "pct_change",
            "vol",
            "turnover_rate",
            "total_mv",
            "float_mv",
        ]
        
        # 为缺失的列添加 None 值
        for col in numeric_columns:
            if col not in data.columns:
                data[col] = None
            else:
                data[col] = pd.to_numeric(data[col], errors="coerce")

        if "trade_date" in data.columns:
            data["trade_date"] = pd.to_datetime(data["trade_date"], format="%Y%m%d").dt.date

        return data

    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load THS daily data into database."""
        if not self.db:
            self.logger.error("Database not initialized")
            return {"status": "failed", "error": "Database not initialized"}

        if data.empty:
            self.logger.warning("No data to load")
            return {"status": "no_data", "loaded_records": 0}

        try:
            schema = self.get_schema()
            table_name = schema.get("table_name")
            if not table_name:
                raise ValueError("table_name not found in schema.json")

            self.logger.info(f"Loading {len(data)} records into {table_name}")
            ods_data = data.copy()
            ods_data["version"] = int(datetime.now().timestamp())
            ods_data["_ingested_at"] = datetime.now()

            ods_data = self._prepare_data_for_insert(table_name, ods_data)
            self.db.insert_dataframe(table_name, ods_data)

            self.logger.info(f"Loaded {len(ods_data)} records into {table_name}")
            return {
                "status": "success",
                "loaded_records": len(ods_data),
                "table": table_name,
            }

        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            return {"status": "failed", "error": str(e)}
