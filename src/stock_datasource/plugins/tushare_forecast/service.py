"""Tushare 业绩预告查询服务"""

from typing import Optional, List, Dict, Any
from datetime import date

from stock_datasource.core.base_service import BaseService


class TuShareForecastService(BaseService):
    """业绩预告数据查询服务"""

    def __init__(self):
        super().__init__("tushare_forecast")
        self.table_name = "ods_forecast"

    def get_forecast(
        self,
        ts_code: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        period: Optional[str] = None,
        type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        获取业绩预告数据

        Args:
            ts_code: 股票代码
            start_date: 公告开始日期
            end_date: 公告结束日期
            period: 报告期（如 20241231）
            type: 预告类型
            limit: 返回记录数限制

        Returns:
            业绩预告数据列表
        """
        conditions = []
        params = {}

        if ts_code:
            conditions.append("ts_code = %(ts_code)s")
            params["ts_code"] = ts_code

        if start_date:
            conditions.append("ann_date >= %(start_date)s")
            params["start_date"] = start_date

        if end_date:
            conditions.append("ann_date <= %(end_date)s")
            params["end_date"] = end_date

        if period:
            conditions.append("toString(end_date) LIKE %(period)s")
            params["period"] = f"{period[:4]}-{period[4:6]}-{period[6:]}%"

        if type:
            conditions.append("type = %(type)s")
            params["type"] = type

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
            SELECT
                ts_code,
                ann_date,
                end_date,
                type,
                p_change_min,
                p_change_max,
                net_profit_min,
                net_profit_max,
                last_parent_net,
                first_ann_date,
                summary,
                change_reason
            FROM {self.table_name}
            WHERE {where_clause}
            ORDER BY ann_date DESC, ts_code
            LIMIT %(limit)s
        """
        params["limit"] = limit

        return self._execute_query(query, params)

    def get_latest_forecast(
        self,
        ts_code: str,
    ) -> Optional[Dict[str, Any]]:
        """
        获取股票最新业绩预告

        Args:
            ts_code: 股票代码

        Returns:
            最新业绩预告数据
        """
        query = f"""
            SELECT
                ts_code,
                ann_date,
                end_date,
                type,
                p_change_min,
                p_change_max,
                net_profit_min,
                net_profit_max,
                last_parent_net,
                first_ann_date,
                summary,
                change_reason
            FROM {self.table_name}
            WHERE ts_code = %(ts_code)s
            ORDER BY ann_date DESC
            LIMIT 1
        """
        params = {"ts_code": ts_code}

        results = self._execute_query(query, params)
        return results[0] if results else None

    def get_forecast_by_type(
        self,
        type: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        按预告类型获取业绩预告

        Args:
            type: 预告类型（预增/预减/扭亏/首亏/续亏/续盈/略增/略减）
            start_date: 公告开始日期
            end_date: 公告结束日期
            limit: 返回记录数限制

        Returns:
            业绩预告数据列表
        """
        conditions = ["type = %(type)s"]
        params = {"type": type}

        if start_date:
            conditions.append("ann_date >= %(start_date)s")
            params["start_date"] = start_date

        if end_date:
            conditions.append("ann_date <= %(end_date)s")
            params["end_date"] = end_date

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT
                ts_code,
                ann_date,
                end_date,
                type,
                p_change_min,
                p_change_max,
                net_profit_min,
                net_profit_max,
                last_parent_net,
                summary
            FROM {self.table_name}
            WHERE {where_clause}
            ORDER BY ann_date DESC, p_change_max DESC
            LIMIT %(limit)s
        """
        params["limit"] = limit

        return self._execute_query(query, params)

    def get_forecast_statistics(
        self,
        period: str,
    ) -> Dict[str, Any]:
        """
        获取报告期业绩预告统计

        Args:
            period: 报告期（如 20241231）

        Returns:
            统计数据
        """
        period_date = f"{period[:4]}-{period[4:6]}-{period[6:]}"
        
        query = f"""
            SELECT
                type,
                count(*) as count,
                avg(p_change_min) as avg_change_min,
                avg(p_change_max) as avg_change_max
            FROM {self.table_name}
            WHERE end_date = %(period_date)s
            GROUP BY type
            ORDER BY count DESC
        """
        params = {"period_date": period_date}

        results = self._execute_query(query, params)
        
        return {
            "period": period,
            "statistics": results,
            "total": sum(r.get("count", 0) for r in results),
        }
