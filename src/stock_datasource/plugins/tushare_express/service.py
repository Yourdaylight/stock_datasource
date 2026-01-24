"""Tushare 业绩快报查询服务"""

from typing import Optional, List, Dict, Any
from datetime import date

from stock_datasource.core.base_service import BaseService


class TuShareExpressService(BaseService):
    """业绩快报数据查询服务"""

    def __init__(self):
        super().__init__("tushare_express")
        self.table_name = "ods_express"

    def get_express(
        self,
        ts_code: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        period: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        获取业绩快报数据

        Args:
            ts_code: 股票代码
            start_date: 公告开始日期
            end_date: 公告结束日期
            period: 报告期（如 20241231）
            limit: 返回记录数限制

        Returns:
            业绩快报数据列表
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

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
            SELECT
                ts_code,
                ann_date,
                end_date,
                revenue,
                operate_profit,
                total_profit,
                n_income,
                total_assets,
                diluted_eps,
                diluted_roe,
                yoy_net_profit,
                bps,
                yoy_sales,
                yoy_op,
                yoy_tp,
                perf_summary
            FROM {self.table_name}
            WHERE {where_clause}
            ORDER BY ann_date DESC, ts_code
            LIMIT %(limit)s
        """
        params["limit"] = limit

        return self._execute_query(query, params)

    def get_latest_express(
        self,
        ts_code: str,
    ) -> Optional[Dict[str, Any]]:
        """
        获取股票最新业绩快报

        Args:
            ts_code: 股票代码

        Returns:
            最新业绩快报数据
        """
        query = f"""
            SELECT
                ts_code,
                ann_date,
                end_date,
                revenue,
                operate_profit,
                total_profit,
                n_income,
                total_assets,
                total_hldr_eqy_exc_min_int,
                diluted_eps,
                diluted_roe,
                yoy_net_profit,
                bps,
                yoy_sales,
                yoy_op,
                yoy_tp,
                yoy_dedu_np,
                perf_summary,
                is_audit
            FROM {self.table_name}
            WHERE ts_code = %(ts_code)s
            ORDER BY ann_date DESC
            LIMIT 1
        """
        params = {"ts_code": ts_code}

        results = self._execute_query(query, params)
        return results[0] if results else None

    def get_express_growth_ranking(
        self,
        period: str,
        metric: str = "yoy_net_profit",
        order: str = "DESC",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        获取业绩快报增长排行

        Args:
            period: 报告期（如 20241231）
            metric: 排序指标（yoy_net_profit/yoy_sales/yoy_eps）
            order: 排序方向（DESC/ASC）
            limit: 返回记录数限制

        Returns:
            业绩快报增长排行数据
        """
        # 验证 metric 参数
        allowed_metrics = {"yoy_net_profit", "yoy_sales", "yoy_eps", "yoy_op", "yoy_tp", "yoy_roe"}
        if metric not in allowed_metrics:
            raise ValueError(f"Invalid metric: {metric}. Allowed: {allowed_metrics}")
        
        # 验证 order 参数
        order = order.upper()
        if order not in {"ASC", "DESC"}:
            raise ValueError(f"Invalid order: {order}. Allowed: ASC, DESC")
        
        period_date = f"{period[:4]}-{period[4:6]}-{period[6:]}"

        query = f"""
            SELECT
                ts_code,
                ann_date,
                end_date,
                revenue,
                n_income,
                diluted_eps,
                diluted_roe,
                yoy_net_profit,
                yoy_sales,
                yoy_eps,
                yoy_roe,
                perf_summary
            FROM {self.table_name}
            WHERE end_date = %(period_date)s
                AND {metric} IS NOT NULL
            ORDER BY {metric} {order}
            LIMIT %(limit)s
        """
        params = {"period_date": period_date, "limit": limit}

        return self._execute_query(query, params)

    def get_express_comparison(
        self,
        ts_code: str,
        periods: int = 4,
    ) -> List[Dict[str, Any]]:
        """
        获取股票多期业绩快报对比

        Args:
            ts_code: 股票代码
            periods: 对比期数

        Returns:
            多期业绩快报数据
        """
        query = f"""
            SELECT
                ts_code,
                ann_date,
                end_date,
                revenue,
                operate_profit,
                total_profit,
                n_income,
                diluted_eps,
                diluted_roe,
                yoy_net_profit,
                yoy_sales,
                bps
            FROM {self.table_name}
            WHERE ts_code = %(ts_code)s
            ORDER BY end_date DESC
            LIMIT %(periods)s
        """
        params = {"ts_code": ts_code, "periods": periods}

        return self._execute_query(query, params)
