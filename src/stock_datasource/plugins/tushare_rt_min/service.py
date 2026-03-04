"""TuShare rt_min (A股实时分钟K线) query service."""

from typing import Any, Dict, List, Optional
from datetime import datetime

from stock_datasource.core.base_service import BaseService, query_method, QueryParam


class RtMinService(BaseService):
    """Query service for A-share realtime minute K-line data."""
    
    table_name = "ods_rt_min"
    
    @query_method(
        name="get_latest_minute_kline",
        description="获取指定股票的最新分钟K线数据",
        params=[
            QueryParam(name="ts_code", type="str", required=True, description="股票代码"),
            QueryParam(name="freq", type="str", required=False, description="K线频率(1MIN/5MIN/15MIN/30MIN/60MIN)"),
            QueryParam(name="limit", type="int", required=False, description="返回记录数限制")
        ]
    )
    def get_latest_minute_kline(
        self, 
        ts_code: str, 
        freq: str = "1MIN",
        limit: int = 60
    ) -> List[Dict[str, Any]]:
        """Get latest minute K-line data for a stock.
        
        Args:
            ts_code: Stock code (e.g., 600000.SH)
            freq: K-line frequency
            limit: Max records to return
            
        Returns:
            List of minute K-line records
        """
        sql = f"""
            SELECT ts_code, freq, trade_time, open, close, high, low, vol, amount
            FROM {self.table_name}
            WHERE ts_code = %(ts_code)s AND freq = %(freq)s
            ORDER BY trade_time DESC
            LIMIT %(limit)s
        """
        result = self.client.execute(sql, {
            "ts_code": ts_code, 
            "freq": freq.upper(),
            "limit": int(limit)
        })
        
        columns = ["ts_code", "freq", "trade_time", "open", "close", "high", "low", "vol", "amount"]
        return [dict(zip(columns, row)) for row in result]
    
    @query_method(
        name="get_minute_kline_by_date",
        description="获取指定股票某日的分钟K线数据",
        params=[
            QueryParam(name="ts_code", type="str", required=True, description="股票代码"),
            QueryParam(name="trade_date", type="str", required=True, description="交易日期(YYYYMMDD)"),
            QueryParam(name="freq", type="str", required=False, description="K线频率")
        ]
    )
    def get_minute_kline_by_date(
        self, 
        ts_code: str, 
        trade_date: str,
        freq: str = "1MIN"
    ) -> List[Dict[str, Any]]:
        """Get minute K-line data for a stock on a specific date.
        
        Args:
            ts_code: Stock code
            trade_date: Trade date in YYYYMMDD format
            freq: K-line frequency
            
        Returns:
            List of minute K-line records for the date
        """
        sql = f"""
            SELECT ts_code, freq, trade_time, open, close, high, low, vol, amount
            FROM {self.table_name}
            WHERE ts_code = %(ts_code)s 
              AND freq = %(freq)s
              AND toYYYYMMDD(trade_time) = %(trade_date)s
            ORDER BY trade_time ASC
        """
        result = self.client.execute(sql, {
            "ts_code": ts_code,
            "freq": freq.upper(),
            "trade_date": int(trade_date)
        })
        
        columns = ["ts_code", "freq", "trade_time", "open", "close", "high", "low", "vol", "amount"]
        return [dict(zip(columns, row)) for row in result]
    
    @query_method(
        name="get_minute_snapshot",
        description="获取多只股票最新一根分钟K线快照",
        params=[
            QueryParam(name="ts_codes", type="str", required=True, description="股票代码列表(逗号分隔)"),
            QueryParam(name="freq", type="str", required=False, description="K线频率")
        ]
    )
    def get_minute_snapshot(
        self, 
        ts_codes: str,
        freq: str = "1MIN"
    ) -> List[Dict[str, Any]]:
        """Get latest minute snapshot for multiple stocks.
        
        Args:
            ts_codes: Comma-separated stock codes
            freq: K-line frequency
            
        Returns:
            List of latest minute records per stock
        """
        code_list = [c.strip() for c in ts_codes.split(",") if c.strip()]
        
        sql = f"""
            SELECT ts_code, freq, trade_time, open, close, high, low, vol, amount
            FROM {self.table_name}
            WHERE ts_code IN %(ts_codes)s
              AND freq = %(freq)s
              AND trade_time = (
                  SELECT max(trade_time) FROM {self.table_name}
                  WHERE freq = %(freq)s
              )
            ORDER BY ts_code
        """
        result = self.client.execute(sql, {
            "ts_codes": code_list,
            "freq": freq.upper()
        })
        
        columns = ["ts_code", "freq", "trade_time", "open", "close", "high", "low", "vol", "amount"]
        return [dict(zip(columns, row)) for row in result]
    
    @query_method(
        name="get_minute_stats",
        description="获取分钟K线数据的统计信息",
        params=[
            QueryParam(name="freq", type="str", required=False, description="K线频率")
        ]
    )
    def get_minute_stats(self, freq: str = "1MIN") -> Dict[str, Any]:
        """Get statistics about stored minute K-line data.
        
        Args:
            freq: K-line frequency
            
        Returns:
            Statistics dict
        """
        sql = f"""
            SELECT 
                count() as total_records,
                uniq(ts_code) as unique_stocks,
                min(trade_time) as earliest_time,
                max(trade_time) as latest_time
            FROM {self.table_name}
            WHERE freq = %(freq)s
        """
        result = self.client.execute(sql, {"freq": freq.upper()})
        
        if result:
            row = result[0]
            return {
                "total_records": row[0],
                "unique_stocks": row[1],
                "earliest_time": row[2],
                "latest_time": row[3],
                "freq": freq.upper()
            }
        return {}
