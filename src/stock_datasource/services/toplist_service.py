"""Top list (龙虎榜) data service."""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, date, timedelta
import pandas as pd

from stock_datasource.models.database import db_client
from stock_datasource.utils.logger import logger

class TopListService:
    """龙虎榜数据核心服务"""
    
    def __init__(self):
        self.db = db_client
        self.logger = logger.bind(component="TopListService")
    
    async def get_top_list_by_date(self, trade_date: str) -> List[Dict[str, Any]]:
        """获取指定日期龙虎榜数据
        
        Args:
            trade_date: 交易日期 (YYYY-MM-DD 或 YYYYMMDD 格式)
        
        Returns:
            龙虎榜数据列表
        """
        try:
            # 标准化日期格式
            if len(trade_date) == 8:  # YYYYMMDD
                formatted_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
            else:
                formatted_date = trade_date
            
            query = """
            SELECT 
                trade_date,
                ts_code,
                name,
                close,
                pct_chg,
                turnover_rate,
                amount,
                l_sell,
                l_buy,
                l_amount,
                net_amount,
                net_rate,
                amount_rate,
                float_values,
                reason
            FROM ods_top_list
            WHERE trade_date = %(trade_date)s
            ORDER BY net_amount DESC
            """
            
            result = self.db.query(query, {"trade_date": formatted_date})
            
            # 转换DataFrame为字典列表
            if result.empty:
                self.logger.info(f"No top list records found for {trade_date}")
                return []
            
            # 将DataFrame转换为字典列表，并处理数据类型
            data_list = result.to_dict('records')
            
            # 转换日期和数值类型
            for item in data_list:
                # 转换日期为字符串
                if 'trade_date' in item and item['trade_date'] is not None:
                    if hasattr(item['trade_date'], 'strftime'):
                        item['trade_date'] = item['trade_date'].strftime('%Y-%m-%d')
                    else:
                        item['trade_date'] = str(item['trade_date'])
                
                # 确保数值字段为float或None，处理NaN
                numeric_fields = ['close', 'pct_chg', 'turnover_rate', 'amount', 
                                'l_sell', 'l_buy', 'l_amount', 'net_amount', 
                                'net_rate', 'amount_rate', 'float_values']
                for field in numeric_fields:
                    if field in item:
                        val = item[field]
                        if val is None or (isinstance(val, float) and pd.isna(val)):
                            item[field] = None
                        else:
                            try:
                                item[field] = float(val)
                            except (ValueError, TypeError):
                                item[field] = None
            
            self.logger.info(f"Retrieved {len(data_list)} top list records for {trade_date}")
            return data_list
            
        except Exception as e:
            self.logger.error(f"Failed to get top list data for {trade_date}: {e}")
            raise
    
    async def get_top_inst_by_date(self, trade_date: str) -> List[Dict[str, Any]]:
        """获取指定日期机构席位数据
        
        Args:
            trade_date: 交易日期 (YYYY-MM-DD 或 YYYYMMDD 格式)
        
        Returns:
            机构席位数据列表
        """
        try:
            # 标准化日期格式
            if len(trade_date) == 8:  # YYYYMMDD
                formatted_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
            else:
                formatted_date = trade_date
            
            query = """
            SELECT 
                trade_date,
                ts_code,
                exalter,
                buy,
                buy_rate,
                sell,
                sell_rate,
                net_buy,
                seat_type
            FROM ods_top_inst
            WHERE trade_date = %(trade_date)s
            ORDER BY net_buy DESC
            """
            
            result = self.db.query(query, {"trade_date": formatted_date})
            
            # 转换DataFrame为字典列表
            if hasattr(result, 'empty') and result.empty:
                self.logger.info(f"No institutional seats records found for {trade_date}")
                return []
            
            # 转换为字典列表并处理数据类型
            if hasattr(result, 'to_dict'):
                data_list = result.to_dict('records')
            else:
                data_list = result if isinstance(result, list) else []
            
            for item in data_list:
                # 转换日期为字符串
                if 'trade_date' in item and item['trade_date'] is not None:
                    if hasattr(item['trade_date'], 'strftime'):
                        item['trade_date'] = item['trade_date'].strftime('%Y-%m-%d')
                    else:
                        item['trade_date'] = str(item['trade_date'])
                
                # 确保数值字段为float或None
                numeric_fields = ['buy', 'buy_rate', 'sell', 'sell_rate', 'net_buy']
                for field in numeric_fields:
                    if field in item and item[field] is not None:
                        try:
                            item[field] = float(item[field])
                        except (ValueError, TypeError):
                            item[field] = None
            
            self.logger.info(f"Retrieved {len(data_list)} institutional seats records for {trade_date}")
            return data_list
            
        except Exception as e:
            self.logger.error(f"Failed to get institutional seats data for {trade_date}: {e}")
            raise
    
    async def get_stock_top_list_history(self, ts_code: str, days: int = 30) -> List[Dict[str, Any]]:
        """获取股票龙虎榜历史
        
        Args:
            ts_code: 股票代码
            days: 查询天数
        
        Returns:
            股票龙虎榜历史数据
        """
        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            
            query = """
            SELECT 
                trade_date,
                ts_code,
                name,
                close,
                pct_chg,
                turnover_rate,
                amount,
                l_sell,
                l_buy,
                l_amount,
                net_amount,
                net_rate,
                amount_rate,
                reason
            FROM ods_top_list
            WHERE ts_code = %(ts_code)s
              AND trade_date >= %(start_date)s
              AND trade_date <= %(end_date)s
            ORDER BY trade_date DESC
            """
            
            result = self.db.query(query, {
                "ts_code": ts_code,
                "start_date": start_date,
                "end_date": end_date
            })
            
            # 转换DataFrame为字典列表
            if hasattr(result, 'empty') and result.empty:
                self.logger.info(f"No historical top list records found for {ts_code}")
                return []
            
            if hasattr(result, 'to_dict'):
                data_list = result.to_dict('records')
            else:
                data_list = result if isinstance(result, list) else []
            
            for item in data_list:
                # 转换日期为字符串
                if 'trade_date' in item and item['trade_date'] is not None:
                    if hasattr(item['trade_date'], 'strftime'):
                        item['trade_date'] = item['trade_date'].strftime('%Y-%m-%d')
                    else:
                        item['trade_date'] = str(item['trade_date'])
                
                # 确保数值字段为float或None
                numeric_fields = ['close', 'pct_chg', 'turnover_rate', 'amount', 
                                'l_sell', 'l_buy', 'l_amount', 'net_amount', 
                                'net_rate', 'amount_rate']
                for field in numeric_fields:
                    if field in item and item[field] is not None:
                        try:
                            item[field] = float(item[field])
                        except (ValueError, TypeError):
                            item[field] = None
            
            self.logger.info(f"Retrieved {len(data_list)} historical top list records for {ts_code}")
            return data_list
            
        except Exception as e:
            self.logger.error(f"Failed to get top list history for {ts_code}: {e}")
            raise
    
    async def get_top_list_summary(self, trade_date: str) -> Dict[str, Any]:
        """获取龙虎榜摘要统计
        
        Args:
            trade_date: 交易日期
        
        Returns:
            龙虎榜摘要统计数据
        """
        try:
            # 标准化日期格式
            if len(trade_date) == 8:  # YYYYMMDD
                formatted_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
            else:
                formatted_date = trade_date
            
            # 基础统计
            basic_stats_query = """
            SELECT 
                COUNT(*) as total_stocks,
                SUM(amount) as total_amount,
                AVG(pct_chg) as avg_pct_chg,
                AVG(turnover_rate) as avg_turnover_rate,
                SUM(net_amount) as total_net_amount
            FROM ods_top_list
            WHERE trade_date = %(trade_date)s
            """
            
            basic_stats = self.db.query(basic_stats_query, {"trade_date": formatted_date})
            
            # 机构席位统计
            inst_stats_query = """
            SELECT 
                seat_type,
                COUNT(*) as count,
                SUM(net_buy) as total_net_buy
            FROM ods_top_inst
            WHERE trade_date = %(trade_date)s
            GROUP BY seat_type
            """
            
            inst_stats = self.db.query(inst_stats_query, {"trade_date": formatted_date})
            
            # 辅助函数：安全转换为float，处理NaN
            def safe_float(val, default=0.0):
                if val is None or (isinstance(val, float) and pd.isna(val)):
                    return default
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return default
            
            # 构建摘要
            summary = {
                "trade_date": formatted_date,
                "total_stocks": int(basic_stats.iloc[0]["total_stocks"]) if not basic_stats.empty else 0,
                "total_amount": safe_float(basic_stats.iloc[0]["total_amount"]) if not basic_stats.empty else 0.0,
                "avg_pct_chg": safe_float(basic_stats.iloc[0]["avg_pct_chg"]) if not basic_stats.empty else 0.0,
                "avg_turnover_rate": safe_float(basic_stats.iloc[0]["avg_turnover_rate"]) if not basic_stats.empty else 0.0,
                "total_net_amount": safe_float(basic_stats.iloc[0]["total_net_amount"]) if not basic_stats.empty else 0.0,
                "institution_count": 0,
                "hot_money_count": 0,
                "unknown_count": 0,
                "net_institution_flow": 0.0,
                "net_hot_money_flow": 0.0
            }
            
            # 处理机构统计
            if not inst_stats.empty:
                for _, stat in inst_stats.iterrows():
                    seat_type = stat["seat_type"]
                    count = stat["count"]
                    net_buy = safe_float(stat["total_net_buy"])
                    
                    if seat_type == "institution":
                        summary["institution_count"] = int(count)
                        summary["net_institution_flow"] = net_buy
                    elif seat_type == "hot_money":
                        summary["hot_money_count"] = int(count)
                        summary["net_hot_money_flow"] = net_buy
                    else:
                        summary["unknown_count"] = int(count)
            
            self.logger.info(f"Generated summary for {trade_date}: {summary['total_stocks']} stocks")
            return summary
            
        except Exception as e:
            self.logger.error(f"Failed to get top list summary for {trade_date}: {e}")
            raise
    
    async def get_active_stocks(self, days: int = 7) -> List[Dict[str, Any]]:
        """获取活跃股票（频繁上榜）
        
        Args:
            days: 查询天数
        
        Returns:
            活跃股票列表
        """
        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            
            query = """
            SELECT 
                ts_code,
                name,
                COUNT(*) as appearance_count,
                AVG(pct_chg) as avg_pct_chg,
                SUM(net_amount) as total_net_amount,
                MAX(trade_date) as last_appearance
            FROM ods_top_list
            WHERE trade_date >= %(start_date)s
              AND trade_date <= %(end_date)s
            GROUP BY ts_code, name
            HAVING appearance_count >= 2
            ORDER BY appearance_count DESC, total_net_amount DESC
            LIMIT 50
            """
            
            result = self.db.query(query, {
                "start_date": start_date,
                "end_date": end_date
            })
            
            # 转换DataFrame为字典列表
            if hasattr(result, 'empty') and result.empty:
                self.logger.info(f"No active stocks found in last {days} days")
                return []
            
            if hasattr(result, 'to_dict'):
                data_list = result.to_dict('records')
            else:
                data_list = result if isinstance(result, list) else []
            
            for item in data_list:
                # 转换日期为字符串
                if 'last_appearance' in item and item['last_appearance'] is not None:
                    if hasattr(item['last_appearance'], 'strftime'):
                        item['last_appearance'] = item['last_appearance'].strftime('%Y-%m-%d')
                    else:
                        item['last_appearance'] = str(item['last_appearance'])
                
                # 确保数值字段为正确的Python类型
                if 'appearance_count' in item and item['appearance_count'] is not None:
                    item['appearance_count'] = int(item['appearance_count'])
                if 'avg_pct_chg' in item and item['avg_pct_chg'] is not None:
                    item['avg_pct_chg'] = float(item['avg_pct_chg'])
                if 'total_net_amount' in item and item['total_net_amount'] is not None:
                    item['total_net_amount'] = float(item['total_net_amount'])
            
            self.logger.info(f"Found {len(data_list)} active stocks in last {days} days")
            return data_list
            
        except Exception as e:
            self.logger.error(f"Failed to get active stocks: {e}")
            raise
    
    async def get_reason_statistics(self, trade_date: str) -> List[Dict[str, Any]]:
        """获取上榜原因统计
        
        Args:
            trade_date: 交易日期
        
        Returns:
            上榜原因统计
        """
        try:
            # 标准化日期格式
            if len(trade_date) == 8:  # YYYYMMDD
                formatted_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
            else:
                formatted_date = trade_date
            
            query = """
            SELECT 
                reason,
                COUNT(*) as count,
                AVG(pct_chg) as avg_pct_chg,
                SUM(amount) as total_amount
            FROM ods_top_list
            WHERE trade_date = %(trade_date)s
              AND reason != ''
            GROUP BY reason
            ORDER BY count DESC
            """
            
            result = self.db.query(query, {"trade_date": formatted_date})
            
            # 转换DataFrame为字典列表
            if hasattr(result, 'empty') and result.empty:
                self.logger.info(f"No reason statistics found for {trade_date}")
                return []
            
            # 转换为字典列表并处理数据类型
            if hasattr(result, 'to_dict'):
                data_list = result.to_dict('records')
            else:
                data_list = result if isinstance(result, list) else []
            
            for item in data_list:
                # 确保数值字段为正确的Python类型
                if 'count' in item and item['count'] is not None:
                    item['count'] = int(item['count'])
                if 'avg_pct_chg' in item and item['avg_pct_chg'] is not None:
                    item['avg_pct_chg'] = float(item['avg_pct_chg'])
                if 'total_amount' in item and item['total_amount'] is not None:
                    item['total_amount'] = float(item['total_amount'])
            
            self.logger.info(f"Retrieved reason statistics for {trade_date}")
            return data_list
            
        except Exception as e:
            self.logger.error(f"Failed to get reason statistics for {trade_date}: {e}")
            raise