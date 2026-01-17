"""TuShare THS index metadata plugin implementation."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

import pandas as pd

from stock_datasource.plugins import BasePlugin
from stock_datasource.core.base_plugin import PluginCategory, PluginRole
from .extractor import extractor


class TuShareTHSIndexPlugin(BasePlugin):
    """TuShare THS sector index metadata plugin."""

    @property
    def name(self) -> str:
        return "tushare_ths_index"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "TuShare THS sector index metadata (index list)"

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
        """Extract THS index metadata from TuShare."""
        ts_code = kwargs.get("ts_code")
        exchange = kwargs.get("exchange")
        index_type = kwargs.get("type") or kwargs.get("index_type")

        self.logger.info(
            "Extracting THS index metadata with params: "
            f"ts_code={ts_code}, exchange={exchange}, type={index_type}"
        )

        data = extractor.extract(
            ts_code=ts_code,
            exchange=exchange,
            index_type=index_type,
        )

        if data.empty:
            self.logger.warning("No THS index metadata found for the given parameters")
            return pd.DataFrame()

        self.logger.info(f"Extracted {len(data)} THS index records")
        return data

    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate THS index metadata."""
        if data.empty:
            self.logger.warning("Empty THS index data")
            return False

        required_columns = ["ts_code", "name"]
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            return False

        for col in required_columns:
            if data[col].isnull().any():
                self.logger.error(f"Found null values in required column: {col}")
                return False

        self.logger.info(f"THS index data validation passed for {len(data)} records")
        return True

    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data for database insertion."""
        if data.empty:
            return data

        # Handle count field - convert to int, fill NA with None for Nullable(Int32)
        if "count" in data.columns:
            data["count"] = pd.to_numeric(data["count"], errors="coerce")
            # Convert to object type to allow None values
            data["count"] = data["count"].where(pd.notna(data["count"]), None)

        # Handle list_date field
        if "list_date" in data.columns:
            data["list_date"] = pd.to_datetime(
                data["list_date"], format="%Y%m%d", errors="coerce"
            ).dt.date

        # Ensure optional columns exist
        optional_columns = ["exchange", "type", "count", "list_date"]
        for col in optional_columns:
            if col not in data.columns:
                data[col] = None

        return data

    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load THS index metadata into database."""
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
