"""TuShare cyq_chips (筹码分布) query service."""

from typing import Any, Dict, List, Optional
import pandas as pd
from stock_datasource.core.base_service import BaseService, query_method, QueryParam


def _convert_to_json_serializable(obj: Any) -> Any:
    """Convert non-JSON-serializable objects to JSON-compatible types."""
    if isinstance(obj, pd.Timestamp):
        return obj.strftime('%Y%m%d')
    elif isinstance(obj, (pd.Series, dict)):
        return {k: _convert_to_json_serializable(v) for k, v in (obj.items() if isinstance(obj, dict) else obj.items())}
    elif isinstance(obj, list):
        return [_convert_to_json_serializable(item) for item in obj]
    elif pd.isna(obj):
        return None
    return obj


class TuShareCyqChipsService(BaseService):
    """Query service for TuShare cyq_chips (筹码分布) data."""
    
    def __init__(self):
        super().__init__("tushare_cyq_chips")
    
    @query_method(
        description="查询指定股票在日期范围内的筹码分布数据",
        params=[
            QueryParam(
                name="ts_code",
                type="str",
                description="股票代码，如 600000.SH",
                required=True,
            ),
            QueryParam(
                name="start_date",
                type="str",
                description="开始日期 YYYYMMDD 格式",
                required=True,
            ),
            QueryParam(
                name="end_date",
                type="str",
                description="结束日期 YYYYMMDD 格式",
                required=True,
            ),
        ]
    )
    def get_by_date_range(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        """
        Query cyq_chips data by stock code and date range.
        
        Args:
            ts_code: Stock code (e.g., 600000.SH)
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
        
        Returns:
            List of cyq_chips data records
        """
        query = """
        SELECT 
            ts_code,
            trade_date,
            price,
            percent
        FROM ods_cyq_chips
        WHERE ts_code = %(ts_code)s
        AND trade_date >= %(start_date)s
        AND trade_date <= %(end_date)s
        ORDER BY trade_date ASC, price ASC
        """
        
        df = self.db.execute_query(query, {
            'ts_code': ts_code,
            'start_date': start_date,
            'end_date': end_date
        })
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="查询指定股票某一天的筹码分布",
        params=[
            QueryParam(
                name="ts_code",
                type="str",
                description="股票代码，如 600000.SH",
                required=True,
            ),
            QueryParam(
                name="trade_date",
                type="str",
                description="交易日期 YYYYMMDD 格式",
                required=True,
            ),
        ]
    )
    def get_by_date(
        self,
        ts_code: str,
        trade_date: str,
    ) -> List[Dict[str, Any]]:
        """
        Query cyq_chips data for a specific date.
        
        Args:
            ts_code: Stock code (e.g., 600000.SH)
            trade_date: Trade date in YYYYMMDD format
        
        Returns:
            List of cyq_chips data records for that day
        """
        query = """
        SELECT 
            ts_code,
            trade_date,
            price,
            percent
        FROM ods_cyq_chips
        WHERE ts_code = %(ts_code)s
        AND trade_date = %(trade_date)s
        ORDER BY price ASC
        """
        
        df = self.db.execute_query(query, {
            'ts_code': ts_code,
            'trade_date': trade_date
        })
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="查询指定股票最新的筹码分布数据",
        params=[
            QueryParam(
                name="ts_code",
                type="str",
                description="股票代码，如 600000.SH",
                required=True,
            ),
        ]
    )
    def get_latest(
        self,
        ts_code: str,
    ) -> List[Dict[str, Any]]:
        """
        Query latest cyq_chips data for a stock.
        
        Args:
            ts_code: Stock code (e.g., 600000.SH)
        
        Returns:
            List of cyq_chips data records for the latest date
        """
        query = """
        SELECT 
            ts_code,
            trade_date,
            price,
            percent
        FROM ods_cyq_chips
        WHERE ts_code = %(ts_code)s
        AND trade_date = (
            SELECT max(trade_date) FROM ods_cyq_chips WHERE ts_code = %(ts_code)s
        )
        ORDER BY price ASC
        """
        
        df = self.db.execute_query(query, {'ts_code': ts_code})
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="获取筹码集中度分析（获利盘和套牢盘比例）",
        params=[
            QueryParam(
                name="ts_code",
                type="str",
                description="股票代码，如 600000.SH",
                required=True,
            ),
            QueryParam(
                name="trade_date",
                type="str",
                description="交易日期 YYYYMMDD 格式",
                required=True,
            ),
            QueryParam(
                name="current_price",
                type="float",
                description="当前股价，用于计算获利盘比例",
                required=True,
            ),
        ]
    )
    def get_profit_ratio(
        self,
        ts_code: str,
        trade_date: str,
        current_price: float,
    ) -> Dict[str, Any]:
        """
        Calculate profit/loss ratio based on current price.
        
        Args:
            ts_code: Stock code (e.g., 600000.SH)
            trade_date: Trade date in YYYYMMDD format
            current_price: Current stock price for comparison
        
        Returns:
            Dict with profit/loss statistics
        """
        query = """
        SELECT 
            sum(CASE WHEN price <= %(current_price)s THEN percent ELSE 0 END) as profit_ratio,
            sum(CASE WHEN price > %(current_price)s THEN percent ELSE 0 END) as loss_ratio,
            count(*) as price_levels,
            min(price) as min_price,
            max(price) as max_price
        FROM ods_cyq_chips
        WHERE ts_code = %(ts_code)s
        AND trade_date = %(trade_date)s
        """
        
        df = self.db.execute_query(query, {
            'ts_code': ts_code,
            'trade_date': trade_date,
            'current_price': current_price
        })
        
        if df.empty:
            return {}
        
        result = df.iloc[0].to_dict()
        result['ts_code'] = ts_code
        result['trade_date'] = trade_date
        result['current_price'] = current_price
        return _convert_to_json_serializable(result)
    
    @query_method(
        description="获取筹码分布统计信息",
        params=[
            QueryParam(
                name="ts_code",
                type="str",
                description="股票代码，如 600000.SH",
                required=True,
            ),
            QueryParam(
                name="trade_date",
                type="str",
                description="交易日期 YYYYMMDD 格式",
                required=True,
            ),
        ]
    )
    def get_distribution_stats(
        self,
        ts_code: str,
        trade_date: str,
    ) -> Dict[str, Any]:
        """
        Get distribution statistics for cyq_chips.
        
        Args:
            ts_code: Stock code (e.g., 600000.SH)
            trade_date: Trade date in YYYYMMDD format
        
        Returns:
            Statistics dictionary including concentration metrics
        """
        query = """
        SELECT 
            count(*) as price_levels,
            min(price) as min_price,
            max(price) as max_price,
            sum(price * percent) / sum(percent) as weighted_avg_price,
            max(percent) as max_percent
        FROM ods_cyq_chips
        WHERE ts_code = %(ts_code)s
        AND trade_date = %(trade_date)s
        """
        
        df = self.db.execute_query(query, {
            'ts_code': ts_code,
            'trade_date': trade_date
        })
        
        if df.empty:
            return {}
        
        result = df.iloc[0].to_dict()
        result['ts_code'] = ts_code
        result['trade_date'] = trade_date
        return _convert_to_json_serializable(result)
    
    @query_method(
        description="获取筹码最集中的价格区间",
        params=[
            QueryParam(
                name="ts_code",
                type="str",
                description="股票代码，如 600000.SH",
                required=True,
            ),
            QueryParam(
                name="trade_date",
                type="str",
                description="交易日期 YYYYMMDD 格式",
                required=True,
            ),
            QueryParam(
                name="top_n",
                type="int",
                description="返回占比最高的前N个价格点",
                required=False,
                default=10,
            ),
        ]
    )
    def get_top_concentration(
        self,
        ts_code: str,
        trade_date: str,
        top_n: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get top N price levels with highest chip concentration.
        
        Args:
            ts_code: Stock code (e.g., 600000.SH)
            trade_date: Trade date in YYYYMMDD format
            top_n: Number of top price levels to return
        
        Returns:
            List of top price levels by concentration
        """
        query = """
        SELECT 
            ts_code,
            trade_date,
            price,
            percent
        FROM ods_cyq_chips
        WHERE ts_code = %(ts_code)s
        AND trade_date = %(trade_date)s
        ORDER BY percent DESC
        LIMIT %(top_n)s
        """
        
        df = self.db.execute_query(query, {
            'ts_code': ts_code,
            'trade_date': trade_date,
            'top_n': top_n
        })
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
