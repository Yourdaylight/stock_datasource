"""周线行情插件实现"""

import json
from pathlib import Path

from stock_datasource.core.base_plugin import BasePlugin, PluginCategory, PluginRole


class WeeklyPlugin(BasePlugin):
    """周线行情插件"""

    def __init__(self, **kwargs):
        config_path = Path(__file__).parent / "config.json"
        with open(config_path) as f:
            self.plugin_config = json.load(f)

        super().__init__(
            name=self.plugin_config["plugin_name"],
            category=PluginCategory.CN_STOCK,
            role=PluginRole.PRIMARY,
            **kwargs,
        )

    @property
    def description(self) -> str:
        return self.plugin_config["description"]

    def run(self, **kwargs) -> dict:
        """运行插件获取周线行情数据"""
        from .extractor import WeeklyExtractor

        extractor = WeeklyExtractor()
        df = extractor.extract(**kwargs)

        return {
            "status": "success",
            "data": df.to_dict(orient="records"),
            "count": len(df),
        }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="周线行情数据提取")
    parser.add_argument("--ts-code", type=str, help="股票代码")
    parser.add_argument("--trade-date", type=str, help="交易日期")
    parser.add_argument("--start-date", type=str, help="开始日期")
    parser.add_argument("--end-date", type=str, help="结束日期")

    args = parser.parse_args()

    plugin = WeeklyPlugin()
    result = plugin.run(
        ts_code=args.ts_code,
        trade_date=args.trade_date,
        start_date=args.start_date,
        end_date=args.end_date,
    )

    print(f"获取到 {result['count']} 条记录")
    if result["data"]:
        print(f"示例数据: {result['data'][0]}")
