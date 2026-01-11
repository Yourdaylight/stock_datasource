"""ETF module service layer.

Memory is now handled by base_agent.LangGraphAgent, which provides:
- A: LangGraph MemorySaver for automatic checkpoint
- B: Tool result compression
- D: Session-based shared state storage
"""

from typing import List, Dict, Any, Optional
import logging

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


class ETFService:
    """Service for ETF/Index operations."""
    
    def get_indices(
        self,
        market: Optional[str] = None,
        category: Optional[str] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """Get index list with pagination and filters.
        
        Args:
            market: Filter by market (SSE/SZSE/CSI)
            category: Filter by category
            keyword: Search keyword in name
            page: Page number
            page_size: Page size
            
        Returns:
            Dict with total, page, page_size, data
        """
        where_clauses = ["1=1"]
        
        if market:
            where_clauses.append(f"market = '{market}'")
        if category:
            where_clauses.append(f"category = '{category}'")
        if keyword:
            where_clauses.append(f"(name ILIKE '%{keyword}%' OR fullname ILIKE '%{keyword}%')")
        
        where_sql = " AND ".join(where_clauses)
        
        # Count total
        count_query = f"""
        SELECT count() as total
        FROM dim_index_basic
        WHERE {where_sql}
        """
        count_result = _execute_query(count_query)
        total = count_result[0].get('total', 0) if count_result else 0
        
        # Get data with pagination
        offset = (page - 1) * page_size
        query = f"""
        SELECT 
            ts_code,
            name,
            fullname,
            market,
            publisher,
            index_type,
            category,
            base_date,
            base_point,
            list_date,
            weight_rule,
            desc
        FROM dim_index_basic
        WHERE {where_sql}
        ORDER BY ts_code ASC
        LIMIT {page_size}
        OFFSET {offset}
        """
        
        data = _execute_query(query)
        
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "data": data
        }
    
    def get_index_detail(self, ts_code: str) -> Optional[Dict[str, Any]]:
        """Get index detail by code.
        
        Args:
            ts_code: Index code
            
        Returns:
            Index detail dict or None
        """
        query = f"""
        SELECT 
            ts_code,
            name,
            fullname,
            market,
            publisher,
            index_type,
            category,
            base_date,
            base_point,
            list_date,
            weight_rule,
            desc,
            exp_date
        FROM dim_index_basic
        WHERE ts_code = '{ts_code}'
        """
        result = _execute_query(query)
        return result[0] if result else None
    
    def get_constituents(
        self,
        ts_code: str,
        trade_date: Optional[str] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """Get index constituents.
        
        Args:
            ts_code: Index code
            trade_date: Trade date (YYYYMMDD), defaults to latest
            limit: Max number of constituents to return
            
        Returns:
            Dict with constituents data
        """
        # Get latest date if not specified
        if not trade_date:
            date_query = f"""
            SELECT max(trade_date) as latest_date
            FROM ods_index_weight
            WHERE index_code = '{ts_code}'
            """
            date_result = _execute_query(date_query)
            if date_result and date_result[0].get('latest_date'):
                latest = date_result[0]['latest_date']
                # Handle both string and datetime types
                if hasattr(latest, 'strftime'):
                    trade_date = latest.strftime('%Y%m%d')
                elif isinstance(latest, str) and latest not in ('', '1970-01-01', '1970-01-01 00:00:00'):
                    trade_date = latest.replace('-', '')
                else:
                    trade_date = None
            else:
                trade_date = None
        
        if not trade_date:
            return {
                "index_code": ts_code,
                "trade_date": None,
                "constituent_count": 0,
                "total_weight": 0,
                "constituents": []
            }
        
        query = f"""
        SELECT 
            index_code,
            con_code,
            trade_date,
            weight
        FROM ods_index_weight
        WHERE index_code = '{ts_code}'
        AND trade_date = '{trade_date}'
        ORDER BY weight DESC
        LIMIT {limit}
        """
        
        constituents = _execute_query(query)
        
        # Get total count
        count_query = f"""
        SELECT count() as cnt
        FROM ods_index_weight
        WHERE index_code = '{ts_code}'
        AND trade_date = '{trade_date}'
        """
        count_result = _execute_query(count_query)
        total_count = count_result[0].get('cnt', 0) if count_result else len(constituents)
        
        total_weight = sum(c.get('weight', 0) or 0 for c in constituents)
        
        return {
            "index_code": ts_code,
            "trade_date": trade_date,
            "constituent_count": total_count,
            "total_weight": round(total_weight, 2),
            "constituents": constituents
        }
    
    def get_factors(
        self,
        ts_code: str,
        days: int = 30,
        indicators: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get technical factor data.
        
        Args:
            ts_code: Index code
            days: Number of days
            indicators: Specific indicators to return
            
        Returns:
            Dict with factor data
        """
        if indicators:
            base_cols = ["ts_code", "trade_date", "open", "high", "low", "close", "vol", "amount"]
            cols = base_cols + [i for i in indicators if i not in base_cols]
            columns_str = ", ".join(cols)
        else:
            columns_str = "*"
        
        query = f"""
        SELECT {columns_str}
        FROM ods_idx_factor_pro
        WHERE ts_code = '{ts_code}'
        ORDER BY trade_date DESC
        LIMIT {days}
        """
        
        data = _execute_query(query)
        data.reverse()  # Return in chronological order
        
        return {
            "ts_code": ts_code,
            "days": len(data),
            "data": data
        }
    
    def get_markets(self) -> List[Dict[str, Any]]:
        """Get all available markets."""
        query = """
        SELECT DISTINCT market, count() as count
        FROM dim_index_basic
        WHERE market IS NOT NULL AND market != ''
        GROUP BY market
        ORDER BY count DESC
        """
        return _execute_query(query)
    
    def get_categories(self) -> List[Dict[str, Any]]:
        """Get all available categories."""
        query = """
        SELECT DISTINCT category, count() as count
        FROM dim_index_basic
        WHERE category IS NOT NULL AND category != ''
        GROUP BY category
        ORDER BY count DESC
        """
        return _execute_query(query)
    
    async def analyze_index(
        self,
        ts_code: str,
        question: Optional[str] = None,
        user_id: str = "default",
        clear_history: bool = False,
    ) -> Dict[str, Any]:
        """Analyze index using ETF Agent with conversation memory.
        
        Memory is handled by base_agent.LangGraphAgent which provides:
        - LangGraph MemorySaver for checkpoint-based memory
        - Automatic conversation history management
        - Tool result caching
        - Automatic summarization for long conversations
        
        Args:
            ts_code: Index code
            question: Optional specific question
            user_id: User identifier for session tracking
            clear_history: Whether to clear conversation history before this request
            
        Returns:
            Analysis result with session info
        """
        from stock_datasource.agents import get_etf_agent
        
        agent = get_etf_agent()
        
        # Build task
        if question:
            task = f"请分析指数 {ts_code}，重点回答：{question}"
        else:
            task = f"请对指数 {ts_code} 进行全面的量化分析"
        
        # Execute agent with context - memory is managed by base_agent
        context = {
            "user_id": user_id,
            "context_key": ts_code,  # Use ts_code as context key for session isolation
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
        """Get quick analysis without AI (direct data analysis).
        
        Args:
            ts_code: Index code
            
        Returns:
            Quick analysis result
        """
        from stock_datasource.agents.etf_tools import get_comprehensive_analysis
        return get_comprehensive_analysis(ts_code)


# Singleton instance
_etf_service: Optional[ETFService] = None


def get_etf_service() -> ETFService:
    """Get ETF service singleton."""
    global _etf_service
    if _etf_service is None:
        _etf_service = ETFService()
    return _etf_service
