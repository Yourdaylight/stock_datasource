"""TuShare rt_etf_min (ETF实时分钟K线) query service."""

from typing import Any, Dict, List, Optional
from datetime import datetime

from stock_datasource.core.base_service import BaseService, query_method, QueryParam


class RtEtfMinService(BaseService):
    """Query service for ETF realtime minute K-line data."""
    
    table_name = "ods_rt_etf_min"
    
    @query_method(
        name="get_latest_etf_minute_kline",
        description="获取指定ETF的最新分钟K线数据",
        params=[
            QueryParam(name="ts_code", type="str", required=True, description="ETF代码"),
            QueryParam(name="freq", type="str", required=False, description="K线频率(1MIN/5MIN/15MIN/30MIN/60MIN)"),
            QueryParam(name="limit", type="int", required=False, description="返回记录数限制")
        ]
    )
    def get_latest_etf_minute_kline(
        self, 
        ts_code: str, 
        freq: str = "1MIN",
        limit: int = 60
    ) -> List[Dict[str, Any]]:
        """Get latest minute K-line data for an ETF."""
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
        name="get_etf_minute_kline_by_date",
        description="获取指定ETF某日的分钟K线数据",
        params=[
            QueryParam(name="ts_code", type="str", required=True, description="ETF代码"),
            QueryParam(name="trade_date", type="str", required=True, description="交易日期(YYYYMMDD)"),
            QueryParam(name="freq", type="str", required=False, description="K线频率")
        ]
    )
    def get_etf_minute_kline_by_date(
        self, 
        ts_code: str, 
        trade_date: str,
        freq: str = "1MIN"
    ) -> List[Dict[str, Any]]:
        """Get minute K-line data for an ETF on a specific date."""
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
        name="get_etf_minute_snapshot",
        description="获取多只ETF最新一根分钟K线快照",
        params=[
            QueryParam(name="ts_codes", type="str", required=True, description="ETF代码列表(逗号分隔)"),
            QueryParam(name="freq", type="str", required=False, description="K线频率")
        ]
    )
    def get_etf_minute_snapshot(
        self, 
        ts_codes: str,
        freq: str = "1MIN"
    ) -> List[Dict[str, Any]]:
        """Get latest minute snapshot for multiple ETFs."""
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
        name="get_etf_minute_stats",
        description="获取ETF分钟K线数据统计",
        params=[
            QueryParam(name="freq", type="str", required=False, description="K线频率")
        ]
    )
    def get_etf_minute_stats(self, freq: str = "1MIN") -> Dict[str, Any]:
        """Get statistics about stored ETF minute K-line data."""
        sql = f"""
            SELECT 
                count() as total_records,
                uniq(ts_code) as unique_etfs,
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
                "unique_etfs": row[1],
                "earliest_time": row[2],
                "latest_time": row[3],
                "freq": freq.upper()
            }
        return {}
