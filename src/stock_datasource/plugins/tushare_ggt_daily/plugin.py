"""港股通每日成交统计插件实现"""

import json
from pathlib import Path

from stock_datasource.core.base_plugin import BasePlugin, PluginCategory, PluginRole


class GgtDailyPlugin(BasePlugin):
    """港股通每日成交统计插件"""

    def __init__(self, **kwargs):
        config_path = Path(__file__).parent / "config.json"
        with open(config_path) as f:
            self.plugin_config = json.load(f)

        super().__init__(
            name=self.plugin_config["plugin_name"],
            category=PluginCategory.HK_STOCK,
            role=PluginRole.PRIMARY,
            **kwargs,
        )

    @property
    def description(self) -> str:
        return self.plugin_config["description"]

    def run(self, **kwargs) -> dict:
        """运行插件获取港股通每日成交统计数据"""
        from .extractor import GgtDailyExtractor

        extractor = GgtDailyExtractor()
        df = extractor.extract(**kwargs)

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
