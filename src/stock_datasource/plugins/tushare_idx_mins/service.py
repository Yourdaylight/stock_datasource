"""TuShare idx_mins (指数历史分钟行情) query service."""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from stock_datasource.core.base_service import BaseService, query_method, QueryParam


class IdxMinsService(BaseService):
    """Query service for 指数历史分钟行情 data."""
    
    table_name = "ods_min_kline_index"
    
    @query_method(
        name="get_idx_mins_by_code",
        description="获取指定指数的分钟K线数据",
        params=[
            QueryParam(name="ts_code", type="str", required=True, description="指数代码"),
            QueryParam(name="freq", type="str", required=False, description="频度(1min/5min/15min/30min/60min)"),
            QueryParam(name="start_time", type="str", required=False, description="开始时间"),
            QueryParam(name="end_time", type="str", required=False, description="结束时间"),
            QueryParam(name="limit", type="int", required=False, description="返回记录数限制")
        ]
    )
    def get_idx_mins_by_code(
        self, 
        ts_code: str,
        freq: str = "1min",
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Get index minute K-line data."""
        params = {
            "ts_code": ts_code,
            "freq": freq,
            "limit": int(limit)
        }
        
        time_filter = ""
        if start_time:
            time_filter += " AND trade_time >= %(start_time)s"
            params["start_time"] = start_time
        if end_time:
            time_filter += " AND trade_time <= %(end_time)s"
            params["end_time"] = end_time
        
        sql = f"""
            SELECT ts_code, freq, trade_time, open, close, high, low, vol, amount
            FROM {self.table_name}
            WHERE ts_code = %(ts_code)s AND freq = %(freq)s
            {time_filter}
            ORDER BY trade_time DESC
            LIMIT %(limit)s
        """
        result = self.client.execute(sql, params)
        
        columns = ["ts_code", "freq", "trade_time", "open", "close", "high", "low", "vol", "amount"]
        return [dict(zip(columns, row)) for row in result]
    
    @query_method(
        name="get_latest_idx_mins",
        description="获取指定指数最新的N条分钟数据",
        params=[
            QueryParam(name="ts_code", type="str", required=True, description="指数代码"),
            QueryParam(name="freq", type="str", required=False, description="频度"),
            QueryParam(name="count", type="int", required=False, description="返回条数")
        ]
    )
    def get_latest_idx_mins(
        self, 
        ts_code: str,
        freq: str = "1min",
        count: int = 100
    ) -> List[Dict[str, Any]]:
        """Get latest N index minute records."""
        sql = f"""
            SELECT ts_code, freq, trade_time, open, close, high, low, vol, amount
            FROM {self.table_name}
            WHERE ts_code = %(ts_code)s AND freq = %(freq)s
            ORDER BY trade_time DESC
            LIMIT %(count)s
        """
        result = self.client.execute(sql, {
            "ts_code": ts_code, 
            "freq": freq, 
            "count": int(count)
        })
        
        columns = ["ts_code", "freq", "trade_time", "open", "close", "high", "low", "vol", "amount"]
        return [dict(zip(columns, row)) for row in result]
    
    @query_method(
        name="get_idx_mins_by_date",
        description="获取指定日期的指数分钟数据",
        params=[
            QueryParam(name="ts_code", type="str", required=True, description="指数代码"),
            QueryParam(name="trade_date", type="str", required=True, description="交易日期(YYYYMMDD)"),
            QueryParam(name="freq", type="str", required=False, description="频度")
        ]
    )
    def get_idx_mins_by_date(
        self, 
        ts_code: str,
        trade_date: str,
        freq: str = "1min"
    ) -> List[Dict[str, Any]]:
        """Get index minute data for a specific date."""
        date_str = trade_date[:4] + "-" + trade_date[4:6] + "-" + trade_date[6:8]
        
        sql = f"""
            SELECT ts_code, freq, trade_time, open, close, high, low, vol, amount
            FROM {self.table_name}
            WHERE ts_code = %(ts_code)s 
            AND freq = %(freq)s
            AND toDate(trade_time) = %(trade_date)s
            ORDER BY trade_time ASC
        """
        result = self.client.execute(sql, {
            "ts_code": ts_code, 
            "freq": freq,
            "trade_date": date_str
        })
        
        columns = ["ts_code", "freq", "trade_time", "open", "close", "high", "low", "vol", "amount"]
        return [dict(zip(columns, row)) for row in result]
    
    @query_method(
        name="get_idx_data_summary",
        description="获取指数分钟数据统计摘要",
        params=[
            QueryParam(name="ts_code", type="str", required=False, description="指数代码(可选)")
        ]
    )
    def get_idx_data_summary(self, ts_code: Optional[str] = None) -> Dict[str, Any]:
        """Get index data summary statistics."""
        ts_filter = ""
        params = {}
        
        if ts_code:
            ts_filter = "WHERE ts_code = %(ts_code)s"
            params["ts_code"] = ts_code
        
        sql = f"""
            SELECT 
                count() as total_records,
                count(DISTINCT ts_code) as index_count,
                min(trade_time) as earliest_time,
                max(trade_time) as latest_time,
                countIf(freq = '1min') as mins_1,
                countIf(freq = '5min') as mins_5,
                countIf(freq = '15min') as mins_15,
                countIf(freq = '30min') as mins_30,
                countIf(freq = '60min') as mins_60
            FROM {self.table_name}
            {ts_filter}
        """
        result = self.client.execute(sql, params)
        
        if result:
            row = result[0]
            return {
                "total_records": row[0],
                "index_count": row[1],
                "earliest_time": row[2],
                "latest_time": row[3],
                "by_freq": {
                    "1min": row[4],
                    "5min": row[5],
                    "15min": row[6],
                    "30min": row[7],
                    "60min": row[8]
                }
            }
        return {}
