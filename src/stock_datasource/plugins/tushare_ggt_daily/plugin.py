"""港股通每日成交统计插件实现"""

import json
from pathlib import Path

from stock_datasource.core.base_plugin import BasePlugin, PluginCategory, PluginRole


class GgtDailyPlugin(BasePlugin):
    """港股通每日成交统计插件"""

    def __init__(self, **kwargs):
        config_path = Path(__file__).parent / "config.json"
        with open(config_path) as f:
            self._plugin_config = json.load(f)

        super().__init__(**kwargs)

    @property
    def name(self) -> str:
        """Plugin name."""
        return self._plugin_config.get("plugin_name", "tushare_ggt_daily")

    @property
    def description(self) -> str:
        return self._plugin_config.get("description", "港股通每日成交统计插件")

    def extract_data(self, **kwargs) -> dict:
        """Extract GGT daily data from TuShare API."""
        from .extractor import GgtDailyExtractor

        extractor = GgtDailyExtractor()
        return extractor.extract(**kwargs)

    def load_data(self, data: dict) -> dict:
        """Load GGT daily data into database.

        Args:
            data: DataFrame with GGT daily data

        Returns:
            Dict with loading statistics
        """
        import pandas as pd

        # Convert dict back to DataFrame if needed
        if isinstance(data, dict) and "data" in data:
            df = pd.DataFrame(data["data"])
        else:
            df = data

        if not self.db:
            raise ValueError("Database connection not available")

        # Use the BasePlugin's _ensure_table_exists method
        schema = self.get_schema()
        self._ensure_table_exists(schema)

        # Insert data using ClickHouse client
        table_name = schema.get('table_name')
        if not table_name:
            raise ValueError("Table name not found in schema")

        # Convert DataFrame to ClickHouse format
        self.db.insert_dataframe(table_name, df)

        return {
            "status": "success",
            "count": len(df),
            "table": table_name
        }

    def run(self, **kwargs) -> dict:
        """运行插件获取港股通每日成交统计数据"""
        df = self.extract_data(**kwargs)

        return {
            "status": "success",
            "data": df,
            "count": len(df),
        }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="港股通每日成交统计数据拉取")
    parser.add_argument("--trade-date", type=str, help="交易日期")
    parser.add_argument("--start-date", type=str, help="开始日期")
    parser.add_argument("--end-date", type=str, help="结束日期")
    args = parser.parse_args()

    plugin = GgtDailyPlugin()
    result = plugin.run(
        trade_date=args.trade_date,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    print(f"提取到 {result['count']} 条记录")
    if result["count"] > 0:
        print(result["data"].head())
