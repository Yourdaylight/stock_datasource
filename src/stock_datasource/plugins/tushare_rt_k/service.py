"""TuShare rt_k (realtime K-line) query service."""

from typing import Any, Dict, List, Optional
from datetime import datetime

from stock_datasource.core.base_service import BaseService, query_method, QueryParam


class RtKService(BaseService):
    """Query service for realtime K-line data."""
    
    table_name = "ods_rt_k"
    
    @query_method(
        name="get_latest_quote",
        description="获取指定股票的最新实时行情",
        params=[
            QueryParam(name="ts_code", type="str", required=True, description="股票代码")
        ]
    )
    def get_latest_quote(self, ts_code: str) -> Optional[Dict[str, Any]]:
        """Get latest realtime quote for a stock.
        
        Args:
            ts_code: Stock code (e.g., 600000.SH)
            
        Returns:
            Latest quote dict or None
        """
        sql = f"""
            SELECT * FROM {self.table_name}
            WHERE ts_code = %(ts_code)s
            ORDER BY trade_time DESC
            LIMIT 1
        """
        result = self.client.execute(sql, {"ts_code": ts_code})
        
        if result:
            columns = [
                "ts_code", "name", "pre_close", "high", "open", "low", "close",
                "vol", "amount", "num", "ask_price1", "ask_volume1",
                "bid_price1", "bid_volume1", "trade_time", "version", "_ingested_at"
            ]
            return dict(zip(columns, result[0]))
        return None
    
    @query_method(
        name="get_market_quotes",
        description="获取市场实时行情（按涨跌幅排序）",
        params=[
            QueryParam(name="market", type="str", required=False, description="市场(SH/SZ/BJ)"),
            QueryParam(name="limit", type="int", required=False, description="返回记录数限制")
        ]
    )
    def get_market_quotes(
        self, 
        market: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get market realtime quotes sorted by change percentage.
        
        Args:
            market: Market code (SH/SZ/BJ), None for all
            limit: Max results to return
            
        Returns:
            List of quote dicts with change percentage
        """
        market_filter = ""
        params = {"limit": int(limit)}
        
        if market:
            if market == "SH":
                market_filter = "AND ts_code LIKE '%.SH'"
            elif market == "SZ":
                market_filter = "AND ts_code LIKE '%.SZ'"
            elif market == "BJ":
                market_filter = "AND ts_code LIKE '%.BJ'"
        
        sql = f"""
            SELECT 
                ts_code, name, pre_close, open, high, low, close,
                vol, amount,
                if(pre_close > 0, round((close - pre_close) / pre_close * 100, 2), 0) as pct_change,
                trade_time
            FROM {self.table_name}
            WHERE trade_time = (SELECT max(trade_time) FROM {self.table_name})
            {market_filter}
            ORDER BY pct_change DESC
            LIMIT %(limit)s
        """
        result = self.client.execute(sql, params)
        
        columns = ["ts_code", "name", "pre_close", "open", "high", "low", "close",
                  "vol", "amount", "pct_change", "trade_time"]
        return [dict(zip(columns, row)) for row in result]
    
    @query_method(
        name="get_top_gainers",
        description="获取涨幅榜",
        params=[
            QueryParam(name="market", type="str", required=False, description="市场(SH/SZ/BJ)"),
            QueryParam(name="limit", type="int", required=False, description="返回记录数限制")
        ]
    )
    def get_top_gainers(
        self, 
        market: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get top gainers.
        
        Args:
            market: Market code (SH/SZ/BJ), None for all
            limit: Max results to return
            
        Returns:
            List of top gainer stocks
        """
        return self.get_market_quotes(market=market, limit=limit)
    
    @query_method(
        name="get_top_losers",
        description="获取跌幅榜",
        params=[
            QueryParam(name="market", type="str", required=False, description="市场(SH/SZ/BJ)"),
            QueryParam(name="limit", type="int", required=False, description="返回记录数限制")
        ]
    )
    def get_top_losers(
        self, 
        market: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get top losers.
        
        Args:
            market: Market code (SH/SZ/BJ), None for all
            limit: Max results to return
            
        Returns:
            List of top loser stocks
        """
        market_filter = ""
        params = {"limit": int(limit)}
        
        if market:
            if market == "SH":
                market_filter = "AND ts_code LIKE '%.SH'"
            elif market == "SZ":
                market_filter = "AND ts_code LIKE '%.SZ'"
            elif market == "BJ":
                market_filter = "AND ts_code LIKE '%.BJ'"
        
        sql = f"""
            SELECT 
                ts_code, name, pre_close, open, high, low, close,
                vol, amount,
                if(pre_close > 0, round((close - pre_close) / pre_close * 100, 2), 0) as pct_change,
                trade_time
            FROM {self.table_name}
            WHERE trade_time = (SELECT max(trade_time) FROM {self.table_name})
            {market_filter}
            ORDER BY pct_change ASC
            LIMIT %(limit)s
        """
        result = self.client.execute(sql, params)
        
        columns = ["ts_code", "name", "pre_close", "open", "high", "low", "close",
                  "vol", "amount", "pct_change", "trade_time"]
        return [dict(zip(columns, row)) for row in result]
    
    @query_method(
        name="get_top_volume",
        description="获取成交量排行榜",
        params=[
            QueryParam(name="market", type="str", required=False, description="市场(SH/SZ/BJ)"),
            QueryParam(name="limit", type="int", required=False, description="返回记录数限制")
        ]
    )
    def get_top_volume(
        self, 
        market: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get stocks with highest trading volume.
        
        Args:
            market: Market code (SH/SZ/BJ), None for all
            limit: Max results to return
            
        Returns:
            List of stocks sorted by volume
        """
        market_filter = ""
        params = {"limit": int(limit)}
        
        if market:
            if market == "SH":
                market_filter = "AND ts_code LIKE '%.SH'"
            elif market == "SZ":
                market_filter = "AND ts_code LIKE '%.SZ'"
            elif market == "BJ":
                market_filter = "AND ts_code LIKE '%.BJ'"
        
        sql = f"""
            SELECT 
                ts_code, name, pre_close, close, vol, amount,
                if(pre_close > 0, round((close - pre_close) / pre_close * 100, 2), 0) as pct_change,
                trade_time
            FROM {self.table_name}
            WHERE trade_time = (SELECT max(trade_time) FROM {self.table_name})
            {market_filter}
            ORDER BY vol DESC
            LIMIT %(limit)s
        """
        result = self.client.execute(sql, params)
        
        columns = ["ts_code", "name", "pre_close", "close", "vol", "amount", 
                  "pct_change", "trade_time"]
        return [dict(zip(columns, row)) for row in result]
    
    @query_method(
        name="get_market_overview",
        description="获取市场整体概览",
        params=[]
    )
    def get_market_overview(self) -> Dict[str, Any]:
        """Get market overview statistics.
        
        Returns:
            Market overview with counts and averages
        """
        sql = f"""
            SELECT 
                count() as total,
                countIf(close > pre_close) as up_count,
                countIf(close < pre_close) as down_count,
                countIf(close = pre_close) as flat_count,
                sum(vol) as total_vol,
                sum(amount) as total_amount,
                avg(if(pre_close > 0, (close - pre_close) / pre_close * 100, 0)) as avg_change,
                max(trade_time) as last_update
            FROM {self.table_name}
            WHERE trade_time = (SELECT max(trade_time) FROM {self.table_name})
        """
        result = self.client.execute(sql)
        
        if result:
            row = result[0]
            return {
                "total": row[0],
                "up_count": row[1],
                "down_count": row[2],
                "flat_count": row[3],
                "total_volume": row[4],
                "total_amount": row[5],
                "avg_change": round(row[6], 2) if row[6] else 0,
                "last_update": row[7]
            }
        return {}
