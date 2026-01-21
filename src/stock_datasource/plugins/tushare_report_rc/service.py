"""Query service for research report earnings forecast data."""

from typing import List, Dict, Any, Optional
from stock_datasource.core.base_service import BaseService, query_method, QueryParam


class ReportRcService(BaseService):
    """Service for querying research report earnings forecast (研报盈利预测) data."""
    
    def __init__(self):
        super().__init__("tushare_report_rc")
    
    @query_method(
        description="查询指定日期的研报数据",
        params=[
            QueryParam(name="report_date", type="str", required=True,
                      description="研报日期，格式 YYYY-MM-DD"),
            QueryParam(name="limit", type="int", required=False, default=100,
                      description="返回记录数限制")
        ]
    )
    def get_reports_by_date(self, report_date: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get research reports for a specific date."""
        query = f"""
            SELECT 
                ts_code,
                name,
                report_date,
                report_title,
                report_type,
                classify,
                org_name,
                author_name,
                quarter,
                eps,
                np,
                pe,
                rating,
                max_price,
                min_price
            FROM ods_report_rc
            WHERE report_date = '{report_date}'
            ORDER BY ts_code, org_name
            LIMIT {limit}
        """
        return self.db.execute_query(query).to_dict('records')
    
    @query_method(
        description="查询指定股票的研报历史",
        params=[
            QueryParam(name="ts_code", type="str", required=True,
                      description="股票代码，如 000001.SZ"),
            QueryParam(name="start_date", type="str", required=False,
                      description="开始日期，格式 YYYY-MM-DD"),
            QueryParam(name="end_date", type="str", required=False,
                      description="结束日期，格式 YYYY-MM-DD"),
            QueryParam(name="limit", type="int", required=False, default=100,
                      description="返回记录数限制")
        ]
    )
    def get_reports_by_stock(self, ts_code: str, start_date: Optional[str] = None,
                             end_date: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get research report history for a specific stock."""
        conditions = [f"ts_code = '{ts_code}'"]
        
        if start_date:
            conditions.append(f"report_date >= '{start_date}'")
        if end_date:
            conditions.append(f"report_date <= '{end_date}'")
        
        where_clause = " AND ".join(conditions)
        
        query = f"""
            SELECT 
                ts_code,
                name,
                report_date,
                report_title,
                report_type,
                classify,
                org_name,
                author_name,
                quarter,
                eps,
                np,
                pe,
                rating,
                max_price,
                min_price
            FROM ods_report_rc
            WHERE {where_clause}
            ORDER BY report_date DESC
            LIMIT {limit}
        """
        return self.db.execute_query(query).to_dict('records')
    
    @query_method(
        description="获取近期被研报覆盖次数最多的股票排名",
        params=[
            QueryParam(name="days", type="int", required=False, default=30,
                      description="统计天数"),
            QueryParam(name="limit", type="int", required=False, default=20,
                      description="返回记录数限制")
        ]
    )
    def get_hot_covered_stocks(self, days: int = 30, limit: int = 20) -> List[Dict[str, Any]]:
        """Get stocks with most research report coverage in recent days."""
        query = f"""
            SELECT 
                ts_code,
                any(name) as name,
                count(*) as report_count,
                count(DISTINCT org_name) as org_count,
                count(DISTINCT report_date) as report_days,
                min(report_date) as first_report_date,
                max(report_date) as last_report_date,
                avg(eps) as avg_eps_forecast,
                avg(pe) as avg_pe_forecast
            FROM ods_report_rc
            WHERE report_date >= today() - {days}
            GROUP BY ts_code
            ORDER BY report_count DESC
            LIMIT {limit}
        """
        return self.db.execute_query(query).to_dict('records')
    
    @query_method(
        description="获取券商机构研报统计",
        params=[
            QueryParam(name="days", type="int", required=False, default=30,
                      description="统计天数"),
            QueryParam(name="limit", type="int", required=False, default=20,
                      description="返回记录数限制")
        ]
    )
    def get_org_stats(self, days: int = 30, limit: int = 20) -> List[Dict[str, Any]]:
        """Get statistics by research organization."""
        query = f"""
            SELECT 
                org_name,
                count(*) as report_count,
                count(DISTINCT ts_code) as stock_count,
                count(DISTINCT author_name) as analyst_count
            FROM ods_report_rc
            WHERE report_date >= today() - {days} AND org_name != ''
            GROUP BY org_name
            ORDER BY report_count DESC
            LIMIT {limit}
        """
        return self.db.execute_query(query).to_dict('records')
    
    @query_method(
        description="获取股票的盈利预测一致性预期",
        params=[
            QueryParam(name="ts_code", type="str", required=True,
                      description="股票代码，如 000001.SZ"),
            QueryParam(name="quarter", type="str", required=False,
                      description="预测报告期，如 2024Q4")
        ]
    )
    def get_consensus_forecast(self, ts_code: str, 
                               quarter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get consensus earnings forecast for a stock."""
        conditions = [f"ts_code = '{ts_code}'"]
        if quarter:
            conditions.append(f"quarter = '{quarter}'")
        
        where_clause = " AND ".join(conditions)
        
        query = f"""
            SELECT 
                ts_code,
                any(name) as name,
                quarter,
                count(*) as forecast_count,
                count(DISTINCT org_name) as org_count,
                avg(eps) as avg_eps,
                min(eps) as min_eps,
                max(eps) as max_eps,
                avg(np) as avg_np,
                avg(pe) as avg_pe,
                avg(max_price) as avg_target_high,
                avg(min_price) as avg_target_low
            FROM ods_report_rc
            WHERE {where_clause} AND quarter != ''
            GROUP BY ts_code, quarter
            ORDER BY quarter DESC
        """
        return self.db.execute_query(query).to_dict('records')
    
    @query_method(
        description="获取投资评级分布",
        params=[
            QueryParam(name="ts_code", type="str", required=False,
                      description="股票代码，不填则统计全部"),
            QueryParam(name="days", type="int", required=False, default=30,
                      description="统计天数")
        ]
    )
    def get_rating_distribution(self, ts_code: Optional[str] = None,
                                days: int = 30) -> List[Dict[str, Any]]:
        """Get rating distribution for a stock or all stocks."""
        conditions = [f"report_date >= today() - {days}", "rating != ''"]
        if ts_code:
            conditions.append(f"ts_code = '{ts_code}'")
        
        where_clause = " AND ".join(conditions)
        
        query = f"""
            SELECT 
                rating,
                count(*) as count,
                count(DISTINCT ts_code) as stock_count,
                count(DISTINCT org_name) as org_count
            FROM ods_report_rc
            WHERE {where_clause}
            GROUP BY rating
            ORDER BY count DESC
        """
        return self.db.execute_query(query).to_dict('records')
    
    @query_method(
        description="搜索研报标题关键词",
        params=[
            QueryParam(name="keyword", type="str", required=True,
                      description="搜索关键词"),
            QueryParam(name="days", type="int", required=False, default=90,
                      description="搜索天数范围"),
            QueryParam(name="limit", type="int", required=False, default=50,
                      description="返回记录数限制")
        ]
    )
    def search_report_title(self, keyword: str, days: int = 90,
                            limit: int = 50) -> List[Dict[str, Any]]:
        """Search research reports by title keyword."""
        query = f"""
            SELECT 
                ts_code,
                name,
                report_date,
                report_title,
                org_name,
                author_name,
                rating,
                eps,
                max_price,
                min_price
            FROM ods_report_rc
            WHERE report_date >= today() - {days}
              AND report_title LIKE '%{keyword}%'
            ORDER BY report_date DESC
            LIMIT {limit}
        """
        return self.db.execute_query(query).to_dict('records')


# Service instance
service = ReportRcService()
