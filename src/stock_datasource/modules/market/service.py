"""Market service implementation."""

from typing import List, Dict, Any, Optional
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class MarketService:
    """Market service for stock data and analysis."""
    
    def __init__(self):
        self._db = None
    
    @property
    def db(self):
        """Lazy load database client."""
        if self._db is None:
            try:
                from stock_datasource.models.database import get_db_client
                self._db = get_db_client()
            except Exception as e:
                logger.warning(f"Failed to get DB client: {e}")
        return self._db
    
    async def get_kline(
        self,
        code: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq"
    ) -> Dict[str, Any]:
        """Get K-line data for a stock.
        
        Args:
            code: Stock code
            start_date: Start date
            end_date: End date
            adjust: Adjustment type
            
        Returns:
            K-line data with stock info
        """
        if self.db is None:
            # Return mock data
            return self._get_mock_kline(code, start_date, end_date)
        
        try:
            # Query from ClickHouse
            query = """
                SELECT 
                    trade_date,
                    open, high, low, close,
                    vol as volume,
                    amount
                FROM ods_daily
                WHERE ts_code = %(code)s
                  AND trade_date BETWEEN %(start)s AND %(end)s
                ORDER BY trade_date
            """
            df = self.db.execute_query(query, {
                "code": code,
                "start": start_date.replace("-", ""),
                "end": end_date.replace("-", "")
            })
            
            data = []
            for _, row in df.iterrows():
                data.append({
                    "date": str(row["trade_date"]),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]),
                    "amount": float(row["amount"])
                })
            
            return {
                "code": code,
                "name": self._get_stock_name(code),
                "data": data
            }
        except Exception as e:
            logger.error(f"Failed to get K-line data: {e}")
            return self._get_mock_kline(code, start_date, end_date)
    
    async def get_indicators(
        self,
        code: str,
        indicators: List[str],
        period: int = 60
    ) -> Dict[str, Any]:
        """Calculate technical indicators.
        
        Args:
            code: Stock code
            indicators: List of indicators to calculate
            period: Calculation period
            
        Returns:
            Indicator data
        """
        # For now, return mock data
        # In production, calculate from actual price data
        return {
            "code": code,
            "indicators": []
        }
    
    async def search_stock(self, keyword: str) -> List[Dict[str, str]]:
        """Search stocks by keyword.
        
        Args:
            keyword: Search keyword
            
        Returns:
            List of matching stocks
        """
        if self.db is None:
            # Return mock data
            return [
                {"code": "600519.SH", "name": "贵州茅台"},
                {"code": "000001.SZ", "name": "平安银行"},
                {"code": "000858.SZ", "name": "五粮液"}
            ]
        
        try:
            query = """
                SELECT ts_code as code, name
                FROM ods_stock_basic
                WHERE ts_code LIKE %(keyword)s OR name LIKE %(keyword)s
                LIMIT 20
            """
            df = self.db.execute_query(query, {"keyword": f"%{keyword}%"})
            return df.to_dict("records")
        except Exception as e:
            logger.error(f"Stock search failed: {e}")
            return []
    
    def _get_stock_name(self, code: str) -> str:
        """Get stock name by code."""
        # Mock implementation
        names = {
            "600519.SH": "贵州茅台",
            "000001.SZ": "平安银行",
            "000858.SZ": "五粮液"
        }
        return names.get(code, code)
    
    def _get_mock_kline(self, code: str, start_date: str, end_date: str) -> Dict[str, Any]:
        """Generate mock K-line data."""
        import random
        
        data = []
        current_date = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        price = 100.0
        
        while current_date <= end:
            if current_date.weekday() < 5:  # Skip weekends
                change = random.uniform(-0.03, 0.03)
                open_price = price
                close_price = price * (1 + change)
                high_price = max(open_price, close_price) * (1 + random.uniform(0, 0.02))
                low_price = min(open_price, close_price) * (1 - random.uniform(0, 0.02))
                
                data.append({
                    "date": current_date.strftime("%Y-%m-%d"),
                    "open": round(open_price, 2),
                    "high": round(high_price, 2),
                    "low": round(low_price, 2),
                    "close": round(close_price, 2),
                    "volume": random.randint(1000000, 10000000),
                    "amount": random.randint(100000000, 1000000000)
                })
                price = close_price
            
            current_date += timedelta(days=1)
        
        return {
            "code": code,
            "name": self._get_stock_name(code),
            "data": data
        }


# Global service instance
_market_service: Optional[MarketService] = None


def get_market_service() -> MarketService:
    """Get or create market service instance."""
    global _market_service
    if _market_service is None:
        _market_service = MarketService()
    return _market_service
