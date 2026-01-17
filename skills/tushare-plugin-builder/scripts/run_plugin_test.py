#!/usr/bin/env python3
"""
运行插件数据拉取测试脚本。
用于 tushare-plugin-builder skill 生成插件后的端到端测试。

用法:
  python run_plugin_test.py PLUGIN_NAME --date 20250110
  python run_plugin_test.py tushare_ths_daily --date 20250110 --verify
"""

import argparse
import importlib
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 将项目根目录加入 sys.path
project_root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(project_root / "src"))


def get_latest_trade_date() -> str:
    """获取最近的交易日期（简单估算，跳过周末）。"""
    today = datetime.now()
    # 如果是周末，回退到周五
    if today.weekday() == 5:  # 周六
        today -= timedelta(days=1)
    elif today.weekday() == 6:  # 周日
        today -= timedelta(days=2)
    return today.strftime("%Y%m%d")


def run_plugin(plugin_name: str, trade_date: str) -> bool:
    """运行插件拉取数据。"""
    try:
        # 动态导入插件模块
        module_path = f"stock_datasource.plugins.{plugin_name}.plugin"
        print(f"正在导入插件: {module_path}")
        
        plugin_module = importlib.import_module(module_path)
        
        # 查找插件类
        plugin_class = None
        for name in dir(plugin_module):
            obj = getattr(plugin_module, name)
            if isinstance(obj, type) and name.endswith("Plugin") and name != "BasePlugin":
                plugin_class = obj
                break
        
        if not plugin_class:
            print(f"❌ 未找到插件类")
            return False
        
        print(f"找到插件类: {plugin_class.__name__}")
        
        # 实例化并运行
        plugin = plugin_class()
        
        print(f"\n正在运行插件，交易日期: {trade_date}")
        print("-" * 50)
        
        # 运行 ETL 流程
        result = plugin.run(trade_date=trade_date)
        
        if result:
            print("-" * 50)
            print(f"✅ 插件运行成功")
            return True
        else:
            print(f"❌ 插件运行失败")
            return False
            
    except ImportError as e:
        print(f"❌ 无法导入插件: {e}")
        return False
    except Exception as e:
        print(f"❌ 运行失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_data(plugin_name: str, trade_date: str) -> bool:
    """验证数据是否已入库。"""
    try:
        # 加载 schema 获取表名
        schema_path = project_root / "src" / "stock_datasource" / "plugins" / plugin_name / "schema.json"
        if not schema_path.exists():
            print(f"⚠️  未找到 schema.json: {schema_path}")
            return False
        
        import json
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        
        table_name = schema["table_name"]
        
        # 查询数据
        from stock_datasource.models.database import ClickHouseClient
        client = ClickHouseClient()
        
        # 格式化日期
        if len(trade_date) == 8:
            formatted_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}"
        else:
            formatted_date = trade_date
        
        query = """
        SELECT count() as cnt
        FROM {table}
        WHERE trade_date = %(date)s
        """.format(table=table_name)
        
        result = client.execute_query(query, {"date": formatted_date})
        
        if result.empty:
            print(f"❌ 查询失败")
            return False
        
        count = result.iloc[0]["cnt"]
        
        if count > 0:
            print(f"✅ 数据验证成功: {table_name} 中有 {count} 条 {trade_date} 的数据")
            return True
        else:
            print(f"❌ 数据验证失败: {table_name} 中没有 {trade_date} 的数据")
            return False
            
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="运行插件数据拉取测试")
    parser.add_argument("plugin_name", help="插件名称 (如: tushare_ths_daily)")
    parser.add_argument("--date", "-d", help="交易日期 (YYYYMMDD)，默认最近交易日")
    parser.add_argument("--verify", "-v", action="store_true", help="验证数据是否入库")
    parser.add_argument("--skip-run", action="store_true", help="跳过运行，仅验证")
    
    args = parser.parse_args()
    
    # 确定交易日期
    trade_date = args.date or get_latest_trade_date()
    print(f"交易日期: {trade_date}")
    
    # 运行插件
    if not args.skip_run:
        if not run_plugin(args.plugin_name, trade_date):
            sys.exit(1)
    
    # 验证数据
    if args.verify or args.skip_run:
        print()
        if not verify_data(args.plugin_name, trade_date):
            sys.exit(1)
    
    print("\n✅ 测试完成")


if __name__ == "__main__":
    main()
