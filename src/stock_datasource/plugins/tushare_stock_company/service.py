"""TuShare stock company query service."""

from typing import Any, Dict, List, Optional

from stock_datasource.core.base_service import BaseService, query_method, QueryParam


class StockCompanyService(BaseService):
    """Query service for stock company data."""
    
    table_name = "ods_stock_company"
    
    @query_method(
        name="get_company_by_code",
        description="获取指定股票的公司基础信息",
        params=[
            QueryParam(name="ts_code", type="str", required=True, description="股票代码")
        ]
    )
    def get_company_by_code(self, ts_code: str) -> Optional[Dict[str, Any]]:
        """Get company info by stock code.
        
        Args:
            ts_code: Stock code (e.g., 000001.SZ)
            
        Returns:
            Company info dict or None
        """
        sql = f"""
            SELECT * FROM {self.table_name}
            WHERE ts_code = %(ts_code)s
            ORDER BY version DESC
            LIMIT 1
        """
        result = self.client.execute(sql, {"ts_code": ts_code})
        
        if result:
            columns = [
                "ts_code", "com_name", "com_id", "exchange", "chairman",
                "manager", "secretary", "reg_capital", "setup_date",
                "province", "city", "introduction", "website", "email",
                "office", "employees", "main_business", "business_scope",
                "version", "_ingested_at"
            ]
            return dict(zip(columns, result[0]))
        return None
    
    @query_method(
        name="get_companies_by_exchange",
        description="获取指定交易所的所有上市公司",
        params=[
            QueryParam(name="exchange", type="str", required=True, description="交易所代码(SSE/SZSE/BSE)"),
            QueryParam(name="limit", type="int", required=False, description="返回记录数限制")
        ]
    )
    def get_companies_by_exchange(
        self, 
        exchange: str, 
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get all companies by exchange.
        
        Args:
            exchange: Exchange code (SSE/SZSE/BSE)
            limit: Optional limit on results
            
        Returns:
            List of company info dicts
        """
        sql = f"""
            SELECT ts_code, com_name, chairman, reg_capital, province, city, employees
            FROM {self.table_name}
            WHERE exchange = %(exchange)s
            ORDER BY ts_code
        """
        if limit:
            sql += f" LIMIT {int(limit)}"
            
        result = self.client.execute(sql, {"exchange": exchange})
        
        columns = ["ts_code", "com_name", "chairman", "reg_capital", "province", "city", "employees"]
        return [dict(zip(columns, row)) for row in result]
    
    @query_method(
        name="get_companies_by_province",
        description="获取指定省份的所有上市公司",
        params=[
            QueryParam(name="province", type="str", required=True, description="省份名称"),
            QueryParam(name="limit", type="int", required=False, description="返回记录数限制")
        ]
    )
    def get_companies_by_province(
        self, 
        province: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get all companies by province.
        
        Args:
            province: Province name (e.g., 广东)
            limit: Optional limit on results
            
        Returns:
            List of company info dicts
        """
        sql = f"""
            SELECT ts_code, com_name, city, chairman, reg_capital, employees
            FROM {self.table_name}
            WHERE province = %(province)s
            ORDER BY reg_capital DESC
        """
        if limit:
            sql += f" LIMIT {int(limit)}"
            
        result = self.client.execute(sql, {"province": province})
        
        columns = ["ts_code", "com_name", "city", "chairman", "reg_capital", "employees"]
        return [dict(zip(columns, row)) for row in result]
    
    @query_method(
        name="search_companies",
        description="搜索公司（支持公司名称模糊匹配）",
        params=[
            QueryParam(name="keyword", type="str", required=True, description="搜索关键词"),
            QueryParam(name="limit", type="int", required=False, description="返回记录数限制")
        ]
    )
    def search_companies(
        self, 
        keyword: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search companies by name.
        
        Args:
            keyword: Search keyword for company name
            limit: Max results to return
            
        Returns:
            List of matching company info dicts
        """
        sql = f"""
            SELECT ts_code, com_name, exchange, province, city, chairman, employees
            FROM {self.table_name}
            WHERE com_name LIKE %(pattern)s
            ORDER BY ts_code
            LIMIT %(limit)s
        """
        result = self.client.execute(sql, {"pattern": f"%{keyword}%", "limit": int(limit)})
        
        columns = ["ts_code", "com_name", "exchange", "province", "city", "chairman", "employees"]
        return [dict(zip(columns, row)) for row in result]
    
    @query_method(
        name="get_company_statistics",
        description="获取上市公司统计信息（按交易所、省份分组）",
        params=[]
    )
    def get_company_statistics(self) -> Dict[str, Any]:
        """Get company statistics.
        
        Returns:
            Statistics dict with counts by exchange and province
        """
        # By exchange
        exchange_sql = f"""
            SELECT exchange, count() as cnt
            FROM {self.table_name}
            GROUP BY exchange
            ORDER BY cnt DESC
        """
        exchange_result = self.client.execute(exchange_sql)
        
        # By province (top 10)
        province_sql = f"""
            SELECT province, count() as cnt
            FROM {self.table_name}
            WHERE province != ''
            GROUP BY province
            ORDER BY cnt DESC
            LIMIT 10
        """
        province_result = self.client.execute(province_sql)
        
        # Total count
        total_sql = f"SELECT count() FROM {self.table_name}"
        total_result = self.client.execute(total_sql)
        
        return {
            "total": total_result[0][0] if total_result else 0,
            "by_exchange": {row[0]: row[1] for row in exchange_result},
            "top_provinces": {row[0]: row[1] for row in province_result}
        }
