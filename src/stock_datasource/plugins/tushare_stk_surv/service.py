"""Query service for institutional survey data."""

from typing import List, Dict, Any, Optional
from stock_datasource.core.base_service import BaseService, query_method, QueryParam


class StkSurvService(BaseService):
    """Service for querying institutional survey (机构调研) data."""
    
    def __init__(self):
        super().__init__("tushare_stk_surv")
    
    @query_method(
        description="查询指定日期的机构调研数据",
        params=[
            QueryParam(name="surv_date", type="str", required=True, 
                      description="调研日期，格式 YYYY-MM-DD"),
            QueryParam(name="limit", type="int", required=False, default=100,
                      description="返回记录数限制")
        ]
    )
    def get_surveys_by_date(self, surv_date: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get institutional surveys for a specific date."""
        query = f"""
            SELECT 
                ts_code,
                name,
                surv_date,
                fund_visitors,
                rece_place,
                rece_mode,
                rece_org,
                org_type,
                comp_rece,
                content
            FROM ods_stk_surv
            WHERE surv_date = '{surv_date}'
            ORDER BY ts_code
            LIMIT {limit}
        """
        return self.db.execute_query(query).to_dict('records')
    
    @query_method(
        description="查询指定股票的机构调研历史",
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
    def get_surveys_by_stock(self, ts_code: str, start_date: Optional[str] = None,
                             end_date: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get institutional survey history for a specific stock."""
        conditions = [f"ts_code = '{ts_code}'"]
        
        if start_date:
            conditions.append(f"surv_date >= '{start_date}'")
        if end_date:
            conditions.append(f"surv_date <= '{end_date}'")
        
        where_clause = " AND ".join(conditions)
        
        query = f"""
            SELECT 
                ts_code,
                name,
                surv_date,
                fund_visitors,
                rece_place,
                rece_mode,
                rece_org,
                org_type,
                comp_rece,
                content
            FROM ods_stk_surv
            WHERE {where_clause}
            ORDER BY surv_date DESC
            LIMIT {limit}
        """
        return self.db.execute_query(query).to_dict('records')
    
    @query_method(
        description="获取近期被调研次数最多的股票排名",
        params=[
            QueryParam(name="days", type="int", required=False, default=30,
                      description="统计天数"),
            QueryParam(name="limit", type="int", required=False, default=20,
                      description="返回记录数限制")
        ]
    )
    def get_hot_surveyed_stocks(self, days: int = 30, limit: int = 20) -> List[Dict[str, Any]]:
        """Get stocks with most institutional surveys in recent days."""
        query = f"""
            SELECT 
                ts_code,
                any(name) as name,
                count(*) as survey_count,
                count(DISTINCT surv_date) as survey_days,
                min(surv_date) as first_survey_date,
                max(surv_date) as last_survey_date
            FROM ods_stk_surv
            WHERE surv_date >= today() - {days}
            GROUP BY ts_code
            ORDER BY survey_count DESC
            LIMIT {limit}
        """
        return self.db.execute_query(query).to_dict('records')
    
    @query_method(
        description="获取调研机构类型统计",
        params=[
            QueryParam(name="ts_code", type="str", required=False,
                      description="股票代码，不填则统计全部"),
            QueryParam(name="days", type="int", required=False, default=30,
                      description="统计天数")
        ]
    )
    def get_org_type_stats(self, ts_code: Optional[str] = None, 
                           days: int = 30) -> List[Dict[str, Any]]:
        """Get statistics by organization type."""
        conditions = [f"surv_date >= today() - {days}"]
        if ts_code:
            conditions.append(f"ts_code = '{ts_code}'")
        
        where_clause = " AND ".join(conditions)
        
        query = f"""
            SELECT 
                org_type,
                count(*) as survey_count,
                count(DISTINCT ts_code) as stock_count
            FROM ods_stk_surv
            WHERE {where_clause} AND org_type != ''
            GROUP BY org_type
            ORDER BY survey_count DESC
        """
        return self.db.execute_query(query).to_dict('records')
    
    @query_method(
        description="搜索调研内容关键词",
        params=[
            QueryParam(name="keyword", type="str", required=True,
                      description="搜索关键词"),
            QueryParam(name="days", type="int", required=False, default=90,
                      description="搜索天数范围"),
            QueryParam(name="limit", type="int", required=False, default=50,
                      description="返回记录数限制")
        ]
    )
    def search_survey_content(self, keyword: str, days: int = 90, 
                              limit: int = 50) -> List[Dict[str, Any]]:
        """Search survey content by keyword."""
        query = f"""
            SELECT 
                ts_code,
                name,
                surv_date,
                rece_org,
                org_type,
                content
            FROM ods_stk_surv
            WHERE surv_date >= today() - {days}
              AND content LIKE '%{keyword}%'
            ORDER BY surv_date DESC
            LIMIT {limit}
        """
        return self.db.execute_query(query).to_dict('records')


# Service instance
service = StkSurvService()
