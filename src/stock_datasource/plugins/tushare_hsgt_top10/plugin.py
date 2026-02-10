"""沪深股通十大成交股插件实现"""

import json
from pathlib import Path

from stock_datasource.core.base_plugin import BasePlugin, PluginCategory, PluginRole


class HsgtTop10Plugin(BasePlugin):
    """沪深股通十大成交股插件"""

    def __init__(self, **kwargs):
        config_path = Path(__file__).parent / "config.json"
        with open(config_path, "r", encoding="utf-8") as f:
            self._plugin_config = json.load(f)

        super().__init__(**kwargs)

    @property
    def name(self) -> str:
        """Plugin name."""
        return self._plugin_config.get("plugin_name", "tushare_hsgt_top10")

    @property
    def description(self) -> str:
        return self._plugin_config.get("description", "沪深股通十大成交股插件")

    def extract_data(self, **kwargs) -> dict:
        """Extract HSGT top10 data from TuShare API."""
        from .extractor import HsgtTop10Extractor

        extractor = HsgtTop10Extractor()
        return extractor.extract(**kwargs)

    def load_data(self, data: dict) -> dict:
        """Load HSGT top10 data into database.

        Args:
            data: DataFrame with HSGT top10 data

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
        """运行插件获取十大成交股数据"""
        df = self.extract_data(**kwargs)

        return {
            "status": "success",
            "data": df.to_dict(orient="records"),
            "count": len(df),
        }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="沪深股通十大成交股数据提取")
    parser.add_argument("--ts-code", type=str, help="股票代码")
    parser.add_argument("--trade-date", type=str, help="交易日期")
    parser.add_argument("--start-date", type=str, help="开始日期")
    parser.add_argument("--end-date", type=str, help="结束日期")
    parser.add_argument("--market-type", type=str, choices=["1", "3"], help="市场类型：1-沪市，3-深市")

    args = parser.parse_args()

    plugin = HsgtTop10Plugin()
    result = plugin.run(
        ts_code=args.ts_code,
        trade_date=args.trade_date,
        start_date=args.start_date,
        end_date=args.end_date,
        market_type=args.market_type,
    )

    print(f"获取到 {result['count']} 条记录")
    if result["data"]:
        for item in result["data"][:5]:
            print(item)
