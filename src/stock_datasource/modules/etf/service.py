"""ETF module service layer.

Provides ETF data query and analysis services.
"""

from typing import List, Dict, Any, Optional
import logging

from stock_datasource.core.base_list_service import (
    BaseListService, FilterConfig, ListQueryParams, ListResponse, SortConfig
)
from stock_datasource.agents.tools import _format_date

logger = logging.getLogger(__name__)


def _get_db():
    """Get database connection."""
    from stock_datasource.models.database import db_client
    return db_client


def _execute_query(query: str) -> List[Dict[str, Any]]:
    """Execute query and return results as list of dicts."""
    db = _get_db()
    df = db.execute_query(query)
    if df is None or df.empty:
        return []
    return df.to_dict('records')


def _safe_float(value) -> Optional[float]:
    """Convert value to float, return None if NaN or invalid."""
    if value is None:
        return None
    try:
        if value != value:  # NaN check
            return None
        return float(value)
    except (ValueError, TypeError):
        return None


class EtfService(BaseListService):
    """Service for ETF operations."""
    
    @property
    def table_name(self) -> str:
        return "ods_etf_basic"
    
    def get_list_columns(self) -> List[str]:
        return [
            "ts_code",
            "csname",
            "cname",
            "mgr_name",
            "custod_name",
            "etf_type",
            "setup_date",
            "list_date",
            "mgt_fee",
            "index_code",
            "index_name",
            "list_status",
            "exchange"
        ]
    
    def get_search_fields(self) -> List[str]:
        return ["csname", "cname", "ts_code", "mgr_name", "index_name"]
    
    def get_filter_configs(self) -> List[FilterConfig]:
        return [
            FilterConfig(
                field="exchange",
                label="交易所",
                type="select",
                options=[
                    {"value": "SH", "label": "上交所"},
                    {"value": "SZ", "label": "深交所"},
                ]
            ),
            FilterConfig(
                field="etf_type",
                label="基金类型",
                type="select",
            ),
            FilterConfig(
                field="list_status",
                label="状态",
                type="select",
                options=[
                    {"value": "L", "label": "上市"},
                    {"value": "D", "label": "退市"},
                    {"value": "P", "label": "待上市"},
                ]
            ),
        ]
    
    def get_default_sort(self) -> SortConfig:
        return SortConfig(field="ts_code", direction="ASC")
    
    def get_etfs(
        self,
        exchange: Optional[str] = None,
        etf_type: Optional[str] = None,
        list_status: Optional[str] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: Optional[str] = None,
        sort_order: str = "desc",
    ) -> Dict[str, Any]:
        """Get ETF list with latest daily quotes and basic info.
        
        Returns paginated items similar to screener data structure.
        """
        db = _get_db()
        
        # Get latest trade date from ETF daily table
        date_query = "SELECT max(trade_date) as max_date FROM ods_etf_fund_daily"
        date_df = db.execute_query(date_query)
        if date_df.empty or date_df.iloc[0]["max_date"] is None:
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}
        
        latest_date = _format_date(date_df.iloc[0]["max_date"])
        
        # Build WHERE clause
        where_parts = [f"d.trade_date = '{latest_date}'"]
        if exchange:
            exchange_escaped = exchange.replace("'", "''")
            where_parts.append(f"b.exchange = '{exchange_escaped}'")
        if etf_type:
            etf_type_escaped = etf_type.replace("'", "''")
            where_parts.append(f"b.etf_type = '{etf_type_escaped}'")
        if list_status:
            list_status_escaped = list_status.replace("'", "''")
            where_parts.append(f"b.list_status = '{list_status_escaped}'")
        if keyword:
            keyword_clean = keyword.strip()
            if keyword_clean:
                keyword_escaped = keyword_clean.replace("'", "''")
                where_parts.append(
                    "(" +
                    f"d.ts_code LIKE '%{keyword_escaped}%' OR "
                    f"b.csname LIKE '%{keyword_escaped}%' OR "
                    f"b.cname LIKE '%{keyword_escaped}%' OR "
                    f"b.index_name LIKE '%{keyword_escaped}%'" +
                    ")"
                )
        
        where_clause = " AND ".join(where_parts)
        
        # Validate sort field to prevent SQL injection
        allowed_sort_fields = {
            "ts_code": "d.ts_code",
            "trade_date": "d.trade_date",
            "close": "d.close",
            "pct_chg": "d.pct_chg",
            "vol": "d.vol",
            "amount": "d.amount",
            "list_date": "b.list_date",
        }
        sort_field = allowed_sort_fields.get(sort_by or "pct_chg", "d.pct_chg")
        sort_direction = "DESC" if (sort_order or "desc").lower() == "desc" else "ASC"
        
        # Get total count
        count_query = f"""
            SELECT count(*) as cnt
            FROM ods_etf_fund_daily d
            LEFT JOIN ods_etf_basic b ON d.ts_code = b.ts_code
            WHERE {where_clause}
        """
        count_df = db.execute_query(count_query)
        total = int(count_df.iloc[0]["cnt"]) if not count_df.empty else 0
        if total == 0:
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}
        
        # Pagination
        total_pages = (total + page_size - 1) // page_size
        offset = (page - 1) * page_size
        
        data_query = f"""
            SELECT
                d.ts_code,
                d.trade_date,
                d.open,
                d.high,
                d.low,
                d.close,
                d.pct_chg,
                d.vol,
                d.amount,
                b.csname,
                b.cname,
                b.index_code,
                b.index_name,
                b.exchange,
                b.mgr_name,
                b.custod_name,
                b.list_date,
                b.list_status,
                b.etf_type,
                b.mgt_fee
            FROM ods_etf_fund_daily d
            LEFT JOIN ods_etf_basic b ON d.ts_code = b.ts_code
            WHERE {where_clause}
            ORDER BY {sort_field} {sort_direction}
            LIMIT {page_size} OFFSET {offset}
        """
        
        df = db.execute_query(data_query)
        items = []
        for _, row in df.iterrows():
            items.append({
                "ts_code": row.get("ts_code"),
                "trade_date": _format_date(row.get("trade_date")),
                "open": _safe_float(row.get("open")),
                "high": _safe_float(row.get("high")),
                "low": _safe_float(row.get("low")),
                "close": _safe_float(row.get("close")),
                "pct_chg": _safe_float(row.get("pct_chg")),
                "vol": _safe_float(row.get("vol")),
                "amount": _safe_float(row.get("amount")),
                "csname": row.get("csname"),
                "cname": row.get("cname"),
                "index_code": row.get("index_code"),
                "index_name": row.get("index_name"),
                "exchange": row.get("exchange"),
                "mgr_name": row.get("mgr_name"),
                "custod_name": row.get("custod_name"),
                "list_date": row.get("list_date"),
                "list_status": row.get("list_status"),
                "etf_type": row.get("etf_type"),
                "mgt_fee": _safe_float(row.get("mgt_fee")),
            })
        
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }
    
    def get_etf_detail(self, ts_code: str) -> Optional[Dict[str, Any]]:
        """Get ETF detail by code.
        
        Args:
            ts_code: ETF code
            
        Returns:
            ETF detail dict or None
        """
        return self.get_detail("ts_code", ts_code)
    
    def get_daily(
        self,
        ts_code: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get ETF daily data.
        
        Args:
            ts_code: ETF code
            days: Number of days
            
        Returns:
            Dict with ts_code, days, data
        """
        ts_code_escaped = ts_code.replace("'", "''")
        query = f"""
        SELECT 
            ts_code,
            trade_date,
            open,
            high,
            low,
            close,
            pre_close,
            change,
            pct_chg,
            vol,
            amount
        FROM ods_etf_fund_daily
        WHERE ts_code = '{ts_code_escaped}'
        ORDER BY trade_date DESC
        LIMIT {days}
        """
        
        data = _execute_query(query)
        data.reverse()  # Chronological order
        
        return {
            "ts_code": ts_code,
            "days": len(data),
            "data": data
        }
    
    def get_kline(
        self,
        ts_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        adjust: str = "qfq",
    ) -> Dict[str, Any]:
        """Get ETF K-line data with adjustment.
        
        Args:
            ts_code: ETF code
            start_date: Start date (YYYYMMDD)
            end_date: End date (YYYYMMDD)
            adjust: Adjustment type (qfq=forward, hfq=backward, none=no adjust)
            
        Returns:
            Dict with ts_code, name, adjust, data
        """
        ts_code_escaped = ts_code.replace("'", "''")
        
        # Get ETF name
        name_query = f"SELECT csname as name FROM ods_etf_basic WHERE ts_code = '{ts_code_escaped}'"
        name_result = _execute_query(name_query)
        name = name_result[0].get("name") if name_result else None
        
        # Build date filter
        date_conditions = []
        if start_date:
            date_conditions.append(f"d.trade_date >= '{start_date}'")
        if end_date:
            date_conditions.append(f"d.trade_date <= '{end_date}'")
        
        date_filter = " AND ".join(date_conditions) if date_conditions else "1=1"
        
        if adjust == "none":
            # No adjustment
            query = f"""
            SELECT 
                ts_code,
                trade_date,
                open,
                high,
                low,
                close,
                vol,
                amount,
                pct_chg
            FROM ods_etf_fund_daily d
            WHERE ts_code = '{ts_code_escaped}'
            AND {date_filter}
            ORDER BY trade_date ASC
            """
        else:
            # With adjustment factor
            # qfq (forward) uses latest adj_factor as base
            # hfq (backward) uses earliest adj_factor as base
            query = f"""
            WITH adj AS (
                SELECT 
                    ts_code,
                    trade_date,
                    adj_factor,
                    {
                        "LAST_VALUE(adj_factor) OVER (PARTITION BY ts_code ORDER BY trade_date ASC ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING)"
                        if adjust == "qfq" else
                        "FIRST_VALUE(adj_factor) OVER (PARTITION BY ts_code ORDER BY trade_date ASC)"
                    } as base_factor
                FROM ods_etf_fund_adj
                WHERE ts_code = '{ts_code_escaped}'
            )
            SELECT 
                d.ts_code,
                d.trade_date,
                ROUND(d.open * COALESCE(a.adj_factor, 1) / COALESCE(a.base_factor, 1), 4) as open,
                ROUND(d.high * COALESCE(a.adj_factor, 1) / COALESCE(a.base_factor, 1), 4) as high,
                ROUND(d.low * COALESCE(a.adj_factor, 1) / COALESCE(a.base_factor, 1), 4) as low,
                ROUND(d.close * COALESCE(a.adj_factor, 1) / COALESCE(a.base_factor, 1), 4) as close,
                d.vol,
                d.amount,
                d.pct_chg
            FROM ods_etf_fund_daily d
            LEFT JOIN adj a ON d.ts_code = a.ts_code AND d.trade_date = a.trade_date
            WHERE d.ts_code = '{ts_code_escaped}'
            AND {date_filter.replace('d.', '')}
            ORDER BY d.trade_date ASC
            """
        
        data = _execute_query(query)
        
        return {
            "ts_code": ts_code,
            "name": name,
            "adjust": adjust,
            "data": data
        }
    
    def get_exchanges(self) -> List[Dict[str, Any]]:
        """Get all available exchanges."""
        query = """
        SELECT 
            exchange as value,
            CASE exchange 
                WHEN 'SH' THEN '上交所'
                WHEN 'SZ' THEN '深交所'
                ELSE exchange
            END as label,
            count() as count
        FROM ods_etf_basic
        WHERE exchange IS NOT NULL AND exchange != ''
        GROUP BY exchange
        ORDER BY count DESC
        """
        return _execute_query(query)
    
    def get_types(self) -> List[Dict[str, Any]]:
        """Get all available ETF types."""
        query = """
        SELECT 
            etf_type as value,
            etf_type as label,
            count() as count
        FROM ods_etf_basic
        WHERE etf_type IS NOT NULL AND etf_type != ''
        GROUP BY etf_type
        ORDER BY count DESC
        """
        return _execute_query(query)
    
    def get_invest_types(self) -> List[Dict[str, Any]]:
        """Get all available investment types (same as etf_type for this schema)."""
        return self.get_types()
    
    async def analyze_etf(
        self,
        ts_code: str,
        question: Optional[str] = None,
        user_id: str = "default",
        clear_history: bool = False,
    ) -> Dict[str, Any]:
        """Analyze ETF using ETF Agent with conversation memory.
        
        Args:
            ts_code: ETF code
            question: Optional specific question
            user_id: User identifier for session tracking
            clear_history: Whether to clear conversation history
            
        Returns:
            Analysis result with session info
        """
        from stock_datasource.agents import get_etf_agent
        
        agent = get_etf_agent()
        
        # Build task
        if question:
            task = f"请分析ETF {ts_code}，重点回答：{question}"
        else:
            task = f"请对ETF {ts_code} 进行全面的量化分析"
        
        # Execute agent with context
        context = {
            "user_id": user_id,
            "context_key": ts_code,
            "clear_history": clear_history,
        }
        
        result = await agent.execute(task, context)
        
        return {
            "ts_code": ts_code,
            "question": question,
            "response": result.response,
            "success": result.success,
            "metadata": result.metadata,
            "session_id": result.metadata.get("session_id", ""),
            "history_length": result.metadata.get("history_length", 0),
        }
    
    def get_quick_analysis(self, ts_code: str) -> Dict[str, Any]:
        """Get quick analysis without AI.
        
        Args:
            ts_code: ETF code
            
        Returns:
            Quick analysis result
        """
        from stock_datasource.agents.etf_tools import get_etf_comprehensive_analysis
        return get_etf_comprehensive_analysis(ts_code)


# Singleton instance
_etf_service: Optional[EtfService] = None


def get_etf_service() -> EtfService:
    """Get ETF service singleton."""
    global _etf_service
    if _etf_service is None:
        _etf_service = EtfService()
    return _etf_service
