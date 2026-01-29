"""Agent shared cache for cross-agent data sharing.

This module provides a specialized cache layer for agents to share data
such as stock information, market data, and analysis results.
"""

import logging
import hashlib
from typing import Any, Dict, List, Optional
from datetime import datetime

from .cache_service import get_cache_service, CacheService

logger = logging.getLogger(__name__)


class AgentSharedCache:
    """Shared cache layer for cross-agent data sharing.
    
    This class provides:
    - Session-scoped data sharing between agents
    - Stock data caching to avoid redundant API calls
    - Analysis results sharing
    - Execution context sharing
    
    Key prefixes:
    - agent:session:{session_id}:* - Session-scoped data
    - agent:stock:{ts_code}:* - Stock-related data
    - agent:shared:{key} - Global shared data
    """
    
    # TTL configurations (in seconds)
    TTL_SESSION_DATA = 30 * 60  # 30 minutes for session data
    TTL_STOCK_INFO = 24 * 60 * 60  # 24 hours for stock basic info
    TTL_STOCK_DAILY = 60 * 60  # 1 hour for daily data
    TTL_STOCK_REALTIME = 60  # 1 minute for real-time data
    TTL_ANALYSIS_RESULT = 5 * 60  # 5 minutes for analysis results
    
    def __init__(self, cache: CacheService = None):
        self._cache = cache or get_cache_service()
    
    @property
    def available(self) -> bool:
        """Check if cache is available."""
        return self._cache.available
    
    def _session_key(self, session_id: str, key: str) -> str:
        """Generate session-scoped key."""
        return f"agent:session:{session_id}:{key}"
    
    def _stock_key(self, ts_code: str, data_type: str) -> str:
        """Generate stock data key."""
        return f"agent:stock:{ts_code}:{data_type}"
    
    def _shared_key(self, key: str) -> str:
        """Generate global shared key."""
        return f"agent:shared:{key}"
    
    # ==================== Session-scoped Data ====================
    
    def set_session_data(self, session_id: str, key: str, value: Any, ttl: int = None) -> bool:
        """Store session-scoped data.
        
        Args:
            session_id: Session ID
            key: Data key
            value: Data value
            ttl: Optional TTL override
            
        Returns:
            True if successful
        """
        return self._cache.set(
            self._session_key(session_id, key),
            value,
            ttl or self.TTL_SESSION_DATA
        )
    
    def get_session_data(self, session_id: str, key: str) -> Optional[Any]:
        """Retrieve session-scoped data.
        
        Args:
            session_id: Session ID
            key: Data key
            
        Returns:
            Cached value or None
        """
        return self._cache.get(self._session_key(session_id, key))
    
    def delete_session_data(self, session_id: str, key: str = None) -> bool:
        """Delete session-scoped data.
        
        Args:
            session_id: Session ID
            key: Optional specific key, if None deletes all session data
            
        Returns:
            True if successful
        """
        if key:
            return self._cache.delete(self._session_key(session_id, key))
        else:
            count = self._cache.delete_pattern(f"agent:session:{session_id}:*")
            return count >= 0
    
    # ==================== Stock Data Cache ====================
    
    def cache_stock_info(self, ts_code: str, info: Dict[str, Any]) -> bool:
        """Cache stock basic information.
        
        Args:
            ts_code: Stock code (e.g., 600519.SH)
            info: Stock basic info dict
            
        Returns:
            True if successful
        """
        return self._cache.set(
            self._stock_key(ts_code, "info"),
            info,
            self.TTL_STOCK_INFO
        )
    
    def get_stock_info(self, ts_code: str) -> Optional[Dict[str, Any]]:
        """Get cached stock basic information.
        
        Args:
            ts_code: Stock code
            
        Returns:
            Stock info dict or None
        """
        return self._cache.get(self._stock_key(ts_code, "info"))
    
    def cache_stock_daily(self, ts_code: str, start_date: str, end_date: str, data: List[Dict]) -> bool:
        """Cache stock daily K-line data.
        
        Args:
            ts_code: Stock code
            start_date: Start date (YYYYMMDD)
            end_date: End date (YYYYMMDD)
            data: List of daily data dicts
            
        Returns:
            True if successful
        """
        key = f"daily:{start_date}_{end_date}"
        return self._cache.set(
            self._stock_key(ts_code, key),
            data,
            self.TTL_STOCK_DAILY
        )
    
    def get_stock_daily(self, ts_code: str, start_date: str, end_date: str) -> Optional[List[Dict]]:
        """Get cached stock daily K-line data.
        
        Args:
            ts_code: Stock code
            start_date: Start date (YYYYMMDD)
            end_date: End date (YYYYMMDD)
            
        Returns:
            List of daily data dicts or None
        """
        key = f"daily:{start_date}_{end_date}"
        return self._cache.get(self._stock_key(ts_code, key))
    
    def cache_stock_realtime(self, ts_code: str, data: Dict[str, Any]) -> bool:
        """Cache real-time stock data.
        
        Args:
            ts_code: Stock code
            data: Real-time data dict
            
        Returns:
            True if successful
        """
        return self._cache.set(
            self._stock_key(ts_code, "realtime"),
            data,
            self.TTL_STOCK_REALTIME
        )
    
    def get_stock_realtime(self, ts_code: str) -> Optional[Dict[str, Any]]:
        """Get cached real-time stock data.
        
        Args:
            ts_code: Stock code
            
        Returns:
            Real-time data dict or None
        """
        return self._cache.get(self._stock_key(ts_code, "realtime"))
    
    def cache_stock_financial(self, ts_code: str, period: str, data: Dict[str, Any]) -> bool:
        """Cache stock financial data.
        
        Args:
            ts_code: Stock code
            period: Financial period (e.g., '2024Q3')
            data: Financial data dict
            
        Returns:
            True if successful
        """
        return self._cache.set(
            self._stock_key(ts_code, f"financial:{period}"),
            data,
            self.TTL_STOCK_INFO  # Financial data doesn't change often
        )
    
    def get_stock_financial(self, ts_code: str, period: str) -> Optional[Dict[str, Any]]:
        """Get cached stock financial data.
        
        Args:
            ts_code: Stock code
            period: Financial period
            
        Returns:
            Financial data dict or None
        """
        return self._cache.get(self._stock_key(ts_code, f"financial:{period}"))
    
    # ==================== Analysis Results Cache ====================
    
    def cache_analysis_result(
        self, 
        agent_name: str, 
        query_hash: str, 
        result: Any,
        ttl: int = None
    ) -> bool:
        """Cache agent analysis result.
        
        Args:
            agent_name: Name of the agent
            query_hash: Hash of the query
            result: Analysis result
            ttl: Optional TTL override
            
        Returns:
            True if successful
        """
        key = f"analysis:{agent_name}:{query_hash}"
        return self._cache.set(
            self._shared_key(key),
            result,
            ttl or self.TTL_ANALYSIS_RESULT
        )
    
    def get_analysis_result(self, agent_name: str, query_hash: str) -> Optional[Any]:
        """Get cached analysis result.
        
        Args:
            agent_name: Name of the agent
            query_hash: Hash of the query
            
        Returns:
            Cached result or None
        """
        key = f"analysis:{agent_name}:{query_hash}"
        return self._cache.get(self._shared_key(key))
    
    @staticmethod
    def hash_query(query: str, **kwargs) -> str:
        """Generate hash for a query and parameters.
        
        Args:
            query: Query string
            **kwargs: Additional parameters
            
        Returns:
            MD5 hash string
        """
        content = f"{query}:{sorted(kwargs.items())}"
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    # ==================== Agent Execution Context ====================
    
    def set_execution_context(
        self, 
        session_id: str, 
        agent_name: str, 
        context: Dict[str, Any]
    ) -> bool:
        """Store agent execution context for handoff.
        
        Args:
            session_id: Session ID
            agent_name: Name of the agent
            context: Execution context
            
        Returns:
            True if successful
        """
        key = f"context:{agent_name}"
        # Add timestamp
        context["_cached_at"] = datetime.now().isoformat()
        return self.set_session_data(session_id, key, context)
    
    def get_execution_context(self, session_id: str, agent_name: str) -> Optional[Dict[str, Any]]:
        """Get agent execution context.
        
        Args:
            session_id: Session ID
            agent_name: Name of the agent
            
        Returns:
            Execution context or None
        """
        return self.get_session_data(session_id, f"context:{agent_name}")
    
    def share_data_between_agents(
        self,
        session_id: str,
        from_agent: str,
        to_agent: str,
        data: Dict[str, Any]
    ) -> bool:
        """Share data from one agent to another.
        
        Args:
            session_id: Session ID
            from_agent: Source agent name
            to_agent: Target agent name  
            data: Data to share
            
        Returns:
            True if successful
        """
        key = f"handoff:{from_agent}:{to_agent}"
        data["_from_agent"] = from_agent
        data["_to_agent"] = to_agent
        data["_shared_at"] = datetime.now().isoformat()
        return self.set_session_data(session_id, key, data)
    
    def receive_shared_data(
        self,
        session_id: str,
        from_agent: str,
        to_agent: str
    ) -> Optional[Dict[str, Any]]:
        """Receive data shared from another agent.
        
        Args:
            session_id: Session ID
            from_agent: Source agent name
            to_agent: Target agent name
            
        Returns:
            Shared data or None
        """
        key = f"handoff:{from_agent}:{to_agent}"
        return self.get_session_data(session_id, key)
    
    # ==================== Batch Stock Data ====================
    
    def cache_stock_batch(self, stocks: List[Dict[str, Any]], data_type: str = "info") -> int:
        """Cache batch stock data.
        
        Args:
            stocks: List of stock data dicts with 'ts_code' key
            data_type: Type of data (info, realtime, etc.)
            
        Returns:
            Number of successfully cached items
        """
        success_count = 0
        for stock in stocks:
            ts_code = stock.get("ts_code")
            if ts_code:
                ttl = self.TTL_STOCK_INFO if data_type == "info" else self.TTL_STOCK_REALTIME
                if self._cache.set(self._stock_key(ts_code, data_type), stock, ttl):
                    success_count += 1
        return success_count
    
    def get_stock_batch(self, ts_codes: List[str], data_type: str = "info") -> Dict[str, Any]:
        """Get batch stock data.
        
        Args:
            ts_codes: List of stock codes
            data_type: Type of data
            
        Returns:
            Dict mapping ts_code to data
        """
        result = {}
        for ts_code in ts_codes:
            data = self._cache.get(self._stock_key(ts_code, data_type))
            if data:
                result[ts_code] = data
        return result
    
    # ==================== Market Data Cache ====================
    
    def cache_market_overview(self, data: Dict[str, Any]) -> bool:
        """Cache market overview data.
        
        Args:
            data: Market overview data
            
        Returns:
            True if successful
        """
        today = datetime.now().strftime("%Y%m%d")
        return self._cache.set(
            self._shared_key(f"market:overview:{today}"),
            data,
            self.TTL_STOCK_REALTIME * 5  # 5 minutes
        )
    
    def get_market_overview(self) -> Optional[Dict[str, Any]]:
        """Get cached market overview data.
        
        Returns:
            Market overview data or None
        """
        today = datetime.now().strftime("%Y%m%d")
        return self._cache.get(self._shared_key(f"market:overview:{today}"))
    
    def cache_index_data(self, index_code: str, data: Dict[str, Any]) -> bool:
        """Cache index data.
        
        Args:
            index_code: Index code (e.g., 000001.SH)
            data: Index data
            
        Returns:
            True if successful
        """
        return self._cache.set(
            self._shared_key(f"index:{index_code}"),
            data,
            self.TTL_STOCK_REALTIME * 5
        )
    
    def get_index_data(self, index_code: str) -> Optional[Dict[str, Any]]:
        """Get cached index data.
        
        Args:
            index_code: Index code
            
        Returns:
            Index data or None
        """
        return self._cache.get(self._shared_key(f"index:{index_code}"))


# Singleton instance
_agent_cache: Optional[AgentSharedCache] = None


def get_agent_cache() -> AgentSharedCache:
    """Get global agent shared cache instance."""
    global _agent_cache
    if _agent_cache is None:
        _agent_cache = AgentSharedCache()
    return _agent_cache


# Convenience function
agent_cache = get_agent_cache
