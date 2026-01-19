"""Overview module service layer.

Provides daily market overview and AI analysis services.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def _get_db():
    """Get database connection."""
    from stock_datasource.models.database import db_client
    return db_client


def _execute_query(query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Execute query and return results as list of dicts.

    This helper should be resilient: if ClickHouse is initializing or a table is missing,
    return an empty list instead of raising and breaking the frontend.

    IMPORTANT: Use parameterized queries for user-controlled inputs.
    """
    db = _get_db()
    try:
        df = db.execute_query(query, params or {})
    except Exception as e:
        logger.warning(f"ClickHouse query failed: {e}")
        return []

    if df is None or df.empty:
        return []
    return df.to_dict('records')


# Major indices to track
MAJOR_INDICES = [
    ("000001.SH", "上证指数"),
    ("399001.SZ", "深证成指"),
    ("000300.SH", "沪深300"),
    ("000905.SH", "中证500"),
    ("000016.SH", "上证50"),
    ("399006.SZ", "创业板指"),
    ("000852.SH", "中证1000"),
    ("000688.SH", "科创50"),
]


class OverviewService:
    """Service for market overview operations."""
    
    def __init__(self):
        self.db = _get_db()
    
    def _get_latest_trade_date(self, table: str = "ods_idx_factor_pro") -> Optional[str]:
        """Get latest trade date from table."""
        query = f"""
        SELECT max(trade_date) as latest_date
        FROM {table}
        """
        result = _execute_query(query)
        if result and result[0].get('latest_date'):
            latest = result[0]['latest_date']
            if hasattr(latest, 'strftime'):
                date_str = latest.strftime('%Y%m%d')
            else:
                date_str = str(latest).replace('-', '')

            # ClickHouse max(Date) on empty table returns 1970-01-01
            if date_str in {"19700101", "1970-01-01"}:
                return None

            return date_str
        return None
    
    def get_daily_overview(self, date: Optional[str] = None) -> Dict[str, Any]:
        """Get daily market overview.
        
        Args:
            date: Trade date (YYYYMMDD), defaults to latest
            
        Returns:
            Dict with major indices, market stats, hot ETFs
        """
        # Get latest date if not specified
        if not date:
            date = self._get_latest_trade_date()
        
        if not date:
            return {
                "trade_date": None,
                "major_indices": [],
                "market_stats": None,
                "hot_etfs_by_amount": [],
                "hot_etfs_by_change": [],
            }
        
        trade_date = datetime.strptime(date, "%Y%m%d").date()

        # Get major indices
        major_indices = self._get_major_indices(trade_date)

        # Get market stats
        market_stats = self._get_market_stats(trade_date, date_str=date)

        # Get hot ETFs
        hot_etfs_by_amount = self._get_hot_etfs(trade_date, sort_by="amount", limit=10)
        hot_etfs_by_change = self._get_hot_etfs(trade_date, sort_by="pct_chg", limit=10)
        
        return {
            "trade_date": date,
            "major_indices": major_indices,
            "market_stats": market_stats,
            "hot_etfs_by_amount": hot_etfs_by_amount,
            "hot_etfs_by_change": hot_etfs_by_change,
        }
    
    def _get_major_indices(self, trade_date) -> List[Dict[str, Any]]:
        """Get major indices status for a date."""
        indices_codes = [f"'{code}'" for code, _ in MAJOR_INDICES]
        indices_str = ", ".join(indices_codes)

        query = f"""
        SELECT
            f.ts_code,
            b.name,
            f.close,
            ROUND((f.close - f.pre_close) / f.pre_close * 100, 2) as pct_chg,
            f.vol,
            f.amount
        FROM ods_idx_factor_pro f
        LEFT JOIN dim_index_basic b ON f.ts_code = b.ts_code
        WHERE f.ts_code IN ({indices_str})
        AND f.trade_date = %(trade_date)s
        """

        result = _execute_query(query, {"trade_date": trade_date})
        
        # Sort by predefined order
        code_order = {code: i for i, (code, _) in enumerate(MAJOR_INDICES)}
        result.sort(key=lambda x: code_order.get(x.get('ts_code', ''), 999))
        
        return result
    
    def _get_market_stats(self, trade_date, date_str: str) -> Optional[Dict[str, Any]]:
        """Get market statistics for a date."""
        # Use fact_daily_bar which has pct_chg field
        query = """
        SELECT
            trade_date,
            SUM(CASE WHEN pct_chg > 0 THEN 1 ELSE 0 END) as up_count,
            SUM(CASE WHEN pct_chg < 0 THEN 1 ELSE 0 END) as down_count,
            SUM(CASE WHEN pct_chg = 0 OR pct_chg IS NULL THEN 1 ELSE 0 END) as flat_count,
            SUM(CASE WHEN pct_chg >= 9.9 THEN 1 ELSE 0 END) as limit_up_count,
            SUM(CASE WHEN pct_chg <= -9.9 THEN 1 ELSE 0 END) as limit_down_count,
            SUM(amount) as total_amount,
            SUM(vol) as total_vol
        FROM fact_daily_bar
        WHERE trade_date = %(trade_date)s
        GROUP BY trade_date
        """

        result = _execute_query(query, {"trade_date": trade_date})
        if result:
            stats = result[0]
            return {
                "trade_date": date_str,
                "up_count": int(stats.get('up_count', 0) or 0),
                "down_count": int(stats.get('down_count', 0) or 0),
                "flat_count": int(stats.get('flat_count', 0) or 0),
                "limit_up_count": int(stats.get('limit_up_count', 0) or 0),
                "limit_down_count": int(stats.get('limit_down_count', 0) or 0),
                "total_amount": stats.get('total_amount'),
                "total_vol": stats.get('total_vol'),
            }

        return None
    
    def _get_hot_etfs(
        self,
        trade_date,
        sort_by: str = "amount",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get hot ETFs for a date."""
        order_field = "amount" if sort_by == "amount" else "pct_chg"
        order_dir = "DESC"
        limit = int(limit)

        query = f"""
        SELECT
            d.ts_code,
            b.csname as name,
            d.close,
            d.pct_chg,
            d.amount,
            d.vol
        FROM ods_etf_fund_daily d
        LEFT JOIN ods_etf_basic b ON d.ts_code = b.ts_code
        WHERE d.trade_date = %(trade_date)s
        AND d.{order_field} IS NOT NULL
        ORDER BY d.{order_field} {order_dir}
        LIMIT {limit}
        """

        return _execute_query(query, {"trade_date": trade_date})
    
    def get_hot_etfs(
        self,
        date: Optional[str] = None,
        sort_by: str = "amount",
        limit: int = 10,
    ) -> Dict[str, Any]:
        """Get hot ETFs.
        
        Args:
            date: Trade date (YYYYMMDD), defaults to latest
            sort_by: Sort field (amount or pct_chg)
            limit: Number of ETFs to return
            
        Returns:
            Dict with trade_date, sort_by, data
        """
        if not date:
            date = self._get_latest_trade_date("ods_etf_fund_daily")
        
        if not date:
            return {
                "trade_date": None,
                "sort_by": sort_by,
                "data": [],
            }
        
        trade_date = datetime.strptime(date, "%Y%m%d").date()
        data = self._get_hot_etfs(trade_date, sort_by, limit)
        
        return {
            "trade_date": date,
            "sort_by": sort_by,
            "data": data
        }
    
    def get_indices(self, date: Optional[str] = None) -> Dict[str, Any]:
        """Get major indices status.
        
        Args:
            date: Trade date (YYYYMMDD), defaults to latest
            
        Returns:
            Dict with trade_date and indices data
        """
        if not date:
            date = self._get_latest_trade_date()
        
        if not date:
            return {
                "trade_date": None,
                "data": [],
            }
        
        trade_date = datetime.strptime(date, "%Y%m%d").date()
        indices = self._get_major_indices(trade_date)

        return {
            "trade_date": date,
            "data": indices
        }
    
    async def analyze_market(
        self,
        question: str,
        user_id: str = "default",
        date: Optional[str] = None,
        clear_history: bool = False,
    ) -> Dict[str, Any]:
        """Analyze market using Overview Agent with conversation memory.
        
        Args:
            question: User question
            user_id: User identifier for session tracking
            date: Analysis date (defaults to latest)
            clear_history: Whether to clear conversation history
            
        Returns:
            Analysis result with session info
        """
        from stock_datasource.agents import get_overview_agent
        
        if not date:
            date = self._get_latest_trade_date()
        
        agent = get_overview_agent()
        
        # Build task
        task = f"请基于{date}的市场数据回答：{question}"
        
        # Execute agent with context
        context = {
            "user_id": user_id,
            "context_key": f"overview_{date}",
            "clear_history": clear_history,
        }
        
        result = await agent.execute(task, context)
        
        return {
            "date": date,
            "question": question,
            "response": result.response,
            "success": result.success,
            "metadata": result.metadata,
            "session_id": result.metadata.get("session_id", ""),
            "history_length": result.metadata.get("history_length", 0),
        }
    
    def get_quick_analysis(self, date: Optional[str] = None) -> Dict[str, Any]:
        """Get quick market analysis without AI.
        
        Args:
            date: Analysis date (defaults to latest)
            
        Returns:
            Quick analysis result
        """
        from stock_datasource.agents.overview_tools import get_market_daily_summary
        
        if not date:
            date = self._get_latest_trade_date()

        # Delegate entirely to the helper which already has stable empty defaults
        return get_market_daily_summary(date)



# Singleton instance
_overview_service: Optional[OverviewService] = None


def get_overview_service() -> OverviewService:
    """Get Overview service singleton."""
    global _overview_service
    if _overview_service is None:
        _overview_service = OverviewService()
    return _overview_service
