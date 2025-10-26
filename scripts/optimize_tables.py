#!/usr/bin/env python3
"""
表优化脚本 - 清理重复数据
用于定期优化 ClickHouse ReplacingMergeTree 表，去除重复数据
"""

import sys
import time
import argparse
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from stock_datasource.models.database import db_client
from stock_datasource.utils.logger import logger


class TableOptimizer:
    """表优化器"""
    
    def __init__(self):
        self.db = db_client
        self.ods_tables = [
            'ods_daily',
            'ods_adj_factor', 
            'ods_daily_basic',
            'ods_stk_limit',
            'ods_suspend_d',
            'ods_trade_calendar',
            'ods_stock_basic'
        ]
    
    def check_duplicates(self, table_name: str) -> dict:
        """检查表中的重复数据情况"""
        try:
            # 检查表是否存在
            if not self.db.table_exists(table_name):
                return {"exists": False}
            
            # 获取总记录数
            total_count = self.db.execute(f'SELECT COUNT(*) FROM {table_name}')[0][0]
            
            if total_count == 0:
                return {
                    "exists": True,
                    "total_records": 0,
                    "unique_records": 0,
                    "duplicate_records": 0,
                    "duplicate_rate": 0.0
                }
            
            # 根据表结构确定唯一性检查字段
            if table_name == 'ods_stock_basic':
                unique_fields = 'ts_code'
            elif table_name == 'ods_trade_calendar':
                unique_fields = 'exchange, cal_date'
            else:
                unique_fields = 'ts_code, trade_date'
            
            # 获取唯一记录数
            unique_count = self.db.execute(
                f'SELECT COUNT(DISTINCT ({unique_fields})) FROM {table_name}'
            )[0][0]
            
            duplicate_count = total_count - unique_count
            duplicate_rate = (duplicate_count / total_count * 100) if total_count > 0 else 0
            
            return {
                "exists": True,
                "total_records": total_count,
                "unique_records": unique_count,
                "duplicate_records": duplicate_count,
                "duplicate_rate": duplicate_rate
            }
            
        except Exception as e:
            logger.error(f"检查表 {table_name} 重复数据失败: {e}")
            return {"exists": True, "error": str(e)}
    
    def optimize_table(self, table_name: str, final: bool = True) -> dict:
        """优化单个表"""
        try:
            if not self.db.table_exists(table_name):
                return {"success": False, "error": f"表 {table_name} 不存在"}
            
            # 检查优化前的状态
            before_stats = self.check_duplicates(table_name)
            
            # 执行优化
            start_time = time.time()
            optimize_sql = f"OPTIMIZE TABLE {table_name}"
            if final:
                optimize_sql += " FINAL"
            
            logger.info(f"开始优化表 {table_name}...")
            self.db.execute(optimize_sql)
            
            end_time = time.time()
            duration = end_time - start_time
            
            # 检查优化后的状态
            after_stats = self.check_duplicates(table_name)
            
            cleaned_records = before_stats.get("duplicate_records", 0)
            
            logger.info(f"表 {table_name} 优化完成，耗时 {duration:.2f}秒，清理了 {cleaned_records:,} 条重复记录")
            
            return {
                "success": True,
                "duration": duration,
                "before": before_stats,
                "after": after_stats,
                "cleaned_records": cleaned_records
            }
            
        except Exception as e:
            logger.error(f"优化表 {table_name} 失败: {e}")
            return {"success": False, "error": str(e)}
    
    def optimize_all_tables(self, final: bool = True) -> dict:
        """优化所有 ODS 表"""
        results = {}
        total_cleaned = 0
        total_duration = 0
        
        logger.info(f"开始优化 {len(self.ods_tables)} 个 ODS 表...")
        
        for table in self.ods_tables:
            result = self.optimize_table(table, final)
            results[table] = result
            
            if result.get("success"):
                total_cleaned += result.get("cleaned_records", 0)
                total_duration += result.get("duration", 0)
        
        successful_tables = len([r for r in results.values() if r.get("success")])
        
        logger.info(f"优化完成！成功: {successful_tables}/{len(self.ods_tables)} 个表，"
                   f"总耗时: {total_duration:.2f}秒，清理: {total_cleaned:,} 条重复记录")
        
        return {
            "total_tables": len(self.ods_tables),
            "successful_tables": successful_tables,
            "total_duration": total_duration,
            "total_cleaned_records": total_cleaned,
            "results": results
        }
    
    def report_status(self) -> None:
        """报告所有表的重复数据状态"""
        print("\n" + "="*80)
        print("📊 数据表重复情况报告")
        print("="*80)
        
        total_records = 0
        total_duplicates = 0
        
        for table in self.ods_tables:
            stats = self.check_duplicates(table)
            
            if not stats.get("exists"):
                print(f"❌ {table:<20} - 表不存在")
                continue
            
            if "error" in stats:
                print(f"⚠️  {table:<20} - 检查失败: {stats['error']}")
                continue
            
            records = stats["total_records"]
            duplicates = stats["duplicate_records"]
            rate = stats["duplicate_rate"]
            
            total_records += records
            total_duplicates += duplicates
            
            if duplicates == 0:
                status = "✅"
            elif rate < 5:
                status = "⚠️ "
            else:
                status = "❌"
            
            print(f"{status} {table:<20} - 总记录: {records:>8,}, "
                  f"重复: {duplicates:>8,} ({rate:>5.1f}%)")
        
        print("-" * 80)
        overall_rate = (total_duplicates / total_records * 100) if total_records > 0 else 0
        print(f"📈 总计: 记录 {total_records:,}, 重复 {total_duplicates:,} ({overall_rate:.1f}%)")
        print("="*80)


def main():
    parser = argparse.ArgumentParser(description="ClickHouse 表优化工具")
    parser.add_argument("--table", "-t", help="指定要优化的表名")
    parser.add_argument("--all", "-a", action="store_true", help="优化所有 ODS 表")
    parser.add_argument("--check", "-c", action="store_true", help="仅检查重复数据状态")
    parser.add_argument("--no-final", action="store_true", help="不使用 FINAL 关键字")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    
    args = parser.parse_args()
    
    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.INFO)
    
    optimizer = TableOptimizer()
    
    try:
        if args.check:
            # 仅检查状态
            optimizer.report_status()
        elif args.table:
            # 优化指定表
            result = optimizer.optimize_table(args.table, final=not args.no_final)
            if result["success"]:
                print(f"✅ 表 {args.table} 优化成功")
                print(f"   清理重复记录: {result['cleaned_records']:,}")
                print(f"   耗时: {result['duration']:.2f}秒")
            else:
                print(f"❌ 表 {args.table} 优化失败: {result['error']}")
                sys.exit(1)
        elif args.all:
            # 优化所有表
            result = optimizer.optimize_all_tables(final=not args.no_final)
            print(f"\n✅ 批量优化完成")
            print(f"   成功表数: {result['successful_tables']}/{result['total_tables']}")
            print(f"   清理记录: {result['total_cleaned_records']:,}")
            print(f"   总耗时: {result['total_duration']:.2f}秒")
        else:
            # 默认显示帮助和状态
            parser.print_help()
            print("\n")
            optimizer.report_status()
    
    except KeyboardInterrupt:
        print("\n❌ 操作被用户中断")
        sys.exit(1)
    except Exception as e:
        logger.error(f"执行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()