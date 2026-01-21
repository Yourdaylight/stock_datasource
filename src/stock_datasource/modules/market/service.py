"""Market service implementation.

This service provides market data and technical analysis capabilities:
- K-line data retrieval (via Plugin Services)
- Technical indicator calculation
- Market overview
- AI trend analysis
"""

from typing import List, Dict, Any, Optional
import logging
import pandas as pd
from datetime import datetime, timedelta

from .indicators import (
    calculate_indicators,
    detect_signals,
    calculate_support_resistance,
    determine_trend,
)

logger = logging.getLogger(__name__)


class MarketService:
    """Market service for stock data and analysis.
    
    Uses Plugin Services for data access following the Plugin-first principle.
    """
    
    def __init__(self):
        self._daily_service = None
        self._adj_factor_service = None
        self._stock_basic_service = None
        self._daily_basic_service = None
        self._db = None
    
    @property
    def daily_service(self):
        """Lazy load TuShareDailyService."""
        if self._daily_service is None:
            try:
                from stock_datasource.plugins.tushare_daily.service import TuShareDailyService
                self._daily_service = TuShareDailyService()
                logger.info("TuShareDailyService initialized")
            except Exception as e:
                logger.warning(f"Failed to load TuShareDailyService: {e}")
        return self._daily_service
    
    @property
    def adj_factor_service(self):
        """Lazy load TuShareAdjFactorService."""
        if self._adj_factor_service is None:
            try:
                from stock_datasource.plugins.tushare_adj_factor.service import TuShareAdjFactorService
                self._adj_factor_service = TuShareAdjFactorService()
                logger.info("TuShareAdjFactorService initialized")
            except Exception as e:
                logger.warning(f"Failed to load TuShareAdjFactorService: {e}")
        return self._adj_factor_service
    
    @property
    def stock_basic_service(self):
        """Lazy load TuShareStockBasicService."""
        if self._stock_basic_service is None:
            try:
                from stock_datasource.plugins.tushare_stock_basic.service import TuShareStockBasicService
                self._stock_basic_service = TuShareStockBasicService()
                logger.info("TuShareStockBasicService initialized")
            except Exception as e:
                logger.warning(f"Failed to load TuShareStockBasicService: {e}")
        return self._stock_basic_service
    
    @property
    def daily_basic_service(self):
        """Lazy load TuShareDailyBasicService."""
        if self._daily_basic_service is None:
            try:
                from stock_datasource.plugins.tushare_daily_basic.service import TuShareDailyBasicService
                self._daily_basic_service = TuShareDailyBasicService()
                logger.info("TuShareDailyBasicService initialized")
            except Exception as e:
                logger.warning(f"Failed to load TuShareDailyBasicService: {e}")
        return self._daily_basic_service
    
    @property
    def db(self):
        """Lazy load database client for direct queries when needed."""
        if self._db is None:
            try:
                from stock_datasource.models.database import db_client
                self._db = db_client
            except Exception as e:
                logger.warning(f"Failed to get DB client: {e}")
        return self._db
    
    def _normalize_date(self, date_str: str) -> str:
        """Normalize date string to YYYYMMDD format."""
        if '-' in date_str:
            return date_str.replace('-', '')
        return date_str
    
    def _format_date(self, date_str: str) -> str:
        """Format date string to YYYY-MM-DD format."""
        if '-' not in date_str and len(date_str) == 8:
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        return date_str
    
    async def get_kline(
        self,
        code: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq"
    ) -> Dict[str, Any]:
        """Get K-line data for a stock using Plugin Services.
        
        Args:
            code: Stock code (e.g., 000001.SZ)
            start_date: Start date
            end_date: End date
            adjust: Adjustment type (qfq/hfq/none)
            
        Returns:
            K-line data with stock info
        """
        start_date = self._normalize_date(start_date)
        end_date = self._normalize_date(end_date)
        
        # Try using Plugin Service first
        if self.daily_service:
            try:
                records = self.daily_service.get_daily_data(
                    code=code,
                    start_date=start_date,
                    end_date=end_date
                )
                
                if records:
                    # Apply adjustment if needed
                    if adjust in ("qfq", "hfq") and self.adj_factor_service:
                        adj_factors = self.adj_factor_service.get_adj_factor(
                            code=code,
                            start_date=start_date,
                            end_date=end_date
                        )
                        records = self._apply_adjustment(records, adj_factors, adjust)
                    
                    data = []
                    for record in records:
                        trade_date = record.get('trade_date', '')
                        if isinstance(trade_date, str):
                            trade_date = self._format_date(trade_date)
                        
                        data.append({
                            "date": str(trade_date),
                            "open": float(record.get('open', 0) or 0),
                            "high": float(record.get('high', 0) or 0),
                            "low": float(record.get('low', 0) or 0),
                            "close": float(record.get('close', 0) or 0),
                            "volume": float(record.get('vol', 0) or 0),
                            "amount": float(record.get('amount', 0) or 0)
                        })
                    
                    return {
                        "code": code,
                        "name": self._get_stock_name(code),
                        "data": data
                    }
            except Exception as e:
                logger.error(f"Plugin service failed, falling back: {e}")
        
        # Fallback to direct DB query
        return await self._get_kline_from_db(code, start_date, end_date)
    
    def _apply_adjustment(
        self,
        records: List[Dict],
        adj_factors: List[Dict],
        adjust: str
    ) -> List[Dict]:
        """Apply price adjustment to K-line data."""
        if not adj_factors:
            return records
        
        # Create adj_factor lookup by date
        adj_dict = {r['trade_date']: float(r['adj_factor']) for r in adj_factors}
        
        # Get latest adj_factor for forward adjustment
        # Sort adj factors by date to get the most recent one
        sorted_dates = sorted(adj_dict.keys())
        latest_adj = adj_dict[sorted_dates[-1]] if sorted_dates else 1.0
        
        # For missing dates, use the nearest available adj_factor
        # by looking up the closest earlier date
        def get_adj_factor(trade_date: str) -> float:
            if trade_date in adj_dict:
                return adj_dict[trade_date]
            # Find the closest earlier date with adj_factor
            for d in reversed(sorted_dates):
                if d <= trade_date:
                    return adj_dict[d]
            # If no earlier date found, use the latest
            return latest_adj
        
        for record in records:
            trade_date = record.get('trade_date', '')
            adj_factor = get_adj_factor(trade_date)
            
            if adjust == "qfq":
                # Forward adjustment: divide by latest to normalize
                ratio = adj_factor / latest_adj
            else:
                # Backward adjustment
                ratio = adj_factor
            
            for field in ['open', 'high', 'low', 'close']:
                if record.get(field):
                    record[field] = round(float(record[field]) * ratio, 2)
        
        return records
    
    async def _get_kline_from_db(
        self,
        code: str,
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        """Fallback: get K-line data directly from database."""
        if self.db is None:
            return self._get_mock_kline(code, start_date, end_date)
        
        try:
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
                "start": start_date,
                "end": end_date
            })
            
            data = []
            for _, row in df.iterrows():
                trade_date = row["trade_date"]
                if hasattr(trade_date, 'strftime'):
                    trade_date = trade_date.strftime('%Y-%m-%d')
                else:
                    trade_date = self._format_date(str(trade_date))
                
                data.append({
                    "date": trade_date,
                    "open": float(row["open"] or 0),
                    "high": float(row["high"] or 0),
                    "low": float(row["low"] or 0),
                    "close": float(row["close"] or 0),
                    "volume": float(row["volume"] or 0),
                    "amount": float(row["amount"] or 0)
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
        period: int = 60,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Calculate technical indicators for a stock.
        
        Args:
            code: Stock code
            indicators: List of indicators to calculate
            period: Calculation period (days of data to use)
            params: Optional parameters for each indicator
            
        Returns:
            Indicator data
        """
        # Get price data
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=period + 50)).strftime("%Y%m%d")
        
        kline_result = await self.get_kline(code, start_date, end_date, adjust="qfq")
        kline_data = kline_result.get("data", [])
        
        if not kline_data:
            return {
                "code": code,
                "name": self._get_stock_name(code),
                "dates": [],
                "indicators": {},
                "signals": []
            }
        
        # Convert to DataFrame
        df = pd.DataFrame(kline_data)
        df['volume'] = df['volume'].astype(float)
        
        # Calculate indicators
        indicator_params = {}
        if params:
            # Convert IndicatorParams model to dict if needed
            if hasattr(params, 'dict'):
                params = params.dict(exclude_none=True)
            indicator_params = {k.upper(): v for k, v in params.items() if v}
        
        indicators_data = calculate_indicators(df, indicators, indicator_params)
        
        # Detect signals
        signals = detect_signals(df, indicators_data)
        
        # Get dates
        dates = df['date'].tolist()
        
        return {
            "code": code,
            "name": kline_result.get("name", code),
            "dates": dates,
            "indicators": indicators_data,
            "signals": [{"type": s["type"], "indicator": s["indicator"], 
                        "signal": s["signal"], "description": s["description"]} for s in signals]
        }
    
    async def get_indicators_legacy(
        self,
        code: str,
        indicators: List[str],
        period: int = 60
    ) -> Dict[str, Any]:
        """Get indicators in legacy format (for backward compatibility)."""
        result = await self.get_indicators(code, indicators, period)
        
        # Convert to legacy format
        dates = result.get("dates", [])
        indicators_data = result.get("indicators", {})
        
        legacy_data = []
        for i, date in enumerate(dates):
            values = {}
            for key, vals in indicators_data.items():
                if i < len(vals) and vals[i] is not None:
                    values[key] = vals[i]
            if values:
                legacy_data.append({
                    "date": date,
                    "values": values
                })
        
        return {
            "code": code,
            "indicators": legacy_data
        }
    
    async def get_market_overview(self) -> Dict[str, Any]:
        """Get market overview with index data and statistics."""
        try:
            # Get latest trade date
            latest_date = None
            if self.daily_service:
                latest_date = self.daily_service.get_latest_trade_date()
            
            if not latest_date:
                latest_date = datetime.now().strftime("%Y-%m-%d")
            
            # Get index data
            indices = await self._get_index_data()
            
            # Get market statistics
            stats = await self._get_market_stats(latest_date)
            
            return {
                "date": latest_date,
                "indices": indices,
                "stats": stats
            }
        except Exception as e:
            logger.error(f"Failed to get market overview: {e}")
            return {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "indices": [],
                "stats": {
                    "up_count": 0,
                    "down_count": 0,
                    "flat_count": 0,
                    "limit_up_count": 0,
                    "limit_down_count": 0,
                    "total_amount": 0
                }
            }
    
    async def _get_index_data(self) -> List[Dict[str, Any]]:
        """Get major index data."""
        indices = []
        index_codes = [
            ("000001.SH", "上证指数"),
            ("399001.SZ", "深证成指"),
            ("399006.SZ", "创业板指"),
            ("000016.SH", "上证50"),
            ("000300.SH", "沪深300"),
            ("000905.SH", "中证500"),
        ]
        
        if self.db is None:
            # Return mock data
            return [
                {"code": "000001.SH", "name": "上证指数", "close": 3050.0, "pct_chg": 0.5},
                {"code": "399001.SZ", "name": "深证成指", "close": 10200.0, "pct_chg": 0.8},
                {"code": "399006.SZ", "name": "创业板指", "close": 2100.0, "pct_chg": 1.2},
            ]
        
        try:
            for code, name in index_codes:
                query = """
                    SELECT close, pct_chg, vol, amount
                    FROM ods_index_daily
                    WHERE ts_code = %(code)s
                    ORDER BY trade_date DESC
                    LIMIT 1
                """
                df = self.db.execute_query(query, {"code": code})
                
                if not df.empty:
                    row = df.iloc[0]
                    indices.append({
                        "code": code,
                        "name": name,
                        "close": float(row.get("close", 0) or 0),
                        "pct_chg": float(row.get("pct_chg", 0) or 0),
                        "volume": float(row.get("vol", 0) or 0),
                        "amount": float(row.get("amount", 0) or 0)
                    })
        except Exception as e:
            logger.error(f"Failed to get index data: {e}")
        
        return indices
    
    async def _get_market_stats(self, date: str) -> Dict[str, Any]:
        """Get market statistics for a given date."""
        stats = {
            "up_count": 0,
            "down_count": 0,
            "flat_count": 0,
            "limit_up_count": 0,
            "limit_down_count": 0,
            "total_amount": 0
        }
        
        if self.db is None:
            return stats
        
        try:
            date_str = self._normalize_date(date)
            
            # Get all stocks' daily data for the date
            if self.daily_service:
                df = self.daily_service.get_all_daily_by_date(date_str)
            else:
                query = """
                    SELECT pct_chg, amount
                    FROM ods_daily
                    WHERE trade_date = %(date)s
                """
                df = self.db.execute_query(query, {"date": date_str})
            
            if not df.empty:
                pct_chg = df['pct_chg'].fillna(0)
                stats["up_count"] = int((pct_chg > 0).sum())
                stats["down_count"] = int((pct_chg < 0).sum())
                stats["flat_count"] = int((pct_chg == 0).sum())
                stats["limit_up_count"] = int((pct_chg >= 9.9).sum())
                stats["limit_down_count"] = int((pct_chg <= -9.9).sum())
                stats["total_amount"] = round(df['amount'].sum() / 100000000, 2)  # Convert to 亿
        except Exception as e:
            logger.error(f"Failed to get market stats: {e}")
        
        return stats
    
    async def get_hot_stocks(
        self, 
        sort_by: str = "amount", 
        limit: int = 10,
        date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get hot stocks by amount or pct_chg.
        
        Args:
            sort_by: 'amount' for trading volume, 'pct_chg' for price change
            limit: Number of stocks to return
            date: Trade date (optional, defaults to latest)
            
        Returns:
            Hot stocks data
        """
        try:
            if self.db is None:
                return {"trade_date": None, "data": [], "sort_by": sort_by}
            
            # Get latest trade date if not specified
            if not date:
                result = self.db.execute_query(
                    "SELECT max(trade_date) as latest FROM fact_daily_bar"
                )
                if result is not None and not result.empty:
                    latest = result['latest'].iloc[0]
                    if hasattr(latest, 'strftime'):
                        date = latest.strftime('%Y-%m-%d')
                    else:
                        date = str(latest)
            
            if not date or date in ['1970-01-01', '19700101']:
                return {"trade_date": None, "data": [], "sort_by": sort_by}
            
            # Determine sort order
            order_field = "amount" if sort_by == "amount" else "pct_chg"
            order_dir = "DESC"
            
            # Query hot stocks - use argMax to deduplicate and nested subquery to filter
            query = f"""
            SELECT 
                d.ts_code AS ts_code,
                s.name AS name,
                d.close AS close,
                d.pct_chg AS pct_chg,
                d.amount AS amount,
                d.vol AS vol,
                b.turnover_rate AS turnover_rate,
                b.circ_mv AS circ_mv
            FROM (
                SELECT ts_code, close, pct_chg, amount, vol
                FROM (
                    SELECT 
                        ts_code, 
                        argMax(close, _ingested_at) as close, 
                        argMax(pct_chg, _ingested_at) as pct_chg, 
                        argMax(amount, _ingested_at) as amount,
                        argMax(vol, _ingested_at) as vol
                    FROM fact_daily_bar
                    WHERE trade_date = %(trade_date)s
                    AND ts_code NOT LIKE '%%.BJ'
                    GROUP BY ts_code
                )
                WHERE amount > 0
                ORDER BY {order_field} {order_dir}
                LIMIT %(limit)s
            ) d
            LEFT JOIN (
                SELECT ts_code, any(name) as name 
                FROM dim_security 
                GROUP BY ts_code
            ) s ON d.ts_code = s.ts_code
            LEFT JOIN (
                SELECT ts_code, argMax(turnover_rate, _ingested_at) as turnover_rate, argMax(circ_mv, _ingested_at) as circ_mv
                FROM ods_daily_basic
                WHERE trade_date = %(trade_date)s
                GROUP BY ts_code
            ) b ON d.ts_code = b.ts_code
            ORDER BY d.{order_field} {order_dir}
            """
            
            result = self.db.execute_query(query, {
                "trade_date": date,
                "limit": limit
            })
            
            if result is None or result.empty:
                return {"trade_date": date, "data": [], "sort_by": sort_by}
            
            data = []
            for _, row in result.iterrows():
                data.append({
                    "ts_code": row.get("ts_code"),
                    "name": row.get("name") or row.get("ts_code", "").split(".")[0],
                    "close": float(row.get("close") or 0),
                    "pct_chg": float(row.get("pct_chg") or 0),
                    "amount": float(row.get("amount") or 0),
                    "turnover_rate": float(row.get("turnover_rate") or 0) if row.get("turnover_rate") else None,
                    "circ_mv": float(row.get("circ_mv") or 0) if row.get("circ_mv") else None,
                })
            
            return {
                "trade_date": date,
                "data": data,
                "sort_by": sort_by
            }
            
        except Exception as e:
            logger.error(f"Failed to get hot stocks: {e}")
            return {"trade_date": None, "data": [], "sort_by": sort_by}
    
    async def get_hot_sectors(self) -> Dict[str, Any]:
        """Get hot sectors data."""
        # This would typically use industry index data
        # For now, return mock data
        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "sectors": [
                {"name": "新能源", "pct_chg": 3.5, "leading_stock": "宁德时代", "leading_stock_code": "300750.SZ"},
                {"name": "半导体", "pct_chg": 2.8, "leading_stock": "北方华创", "leading_stock_code": "002371.SZ"},
                {"name": "白酒", "pct_chg": 1.5, "leading_stock": "贵州茅台", "leading_stock_code": "600519.SH"},
                {"name": "银行", "pct_chg": 0.8, "leading_stock": "招商银行", "leading_stock_code": "600036.SH"},
            ]
        }
    
    async def analyze_trend(self, code: str, period: int = 60) -> Dict[str, Any]:
        """Analyze stock trend.
        
        Args:
            code: Stock code
            period: Analysis period
            
        Returns:
            Trend analysis result
        """
        # Get K-line and indicators
        kline_result = await self.get_kline(
            code,
            (datetime.now() - timedelta(days=period + 30)).strftime("%Y-%m-%d"),
            datetime.now().strftime("%Y-%m-%d")
        )
        
        kline_data = kline_result.get("data", [])
        stock_name = kline_result.get("name", code)
        
        if not kline_data:
            return {
                "code": code,
                "name": stock_name,
                "trend": "无数据",
                "support": 0,
                "resistance": 0,
                "signals": [],
                "summary": "无法获取股票数据",
                "disclaimer": "以上分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。"
            }
        
        df = pd.DataFrame(kline_data)
        df['volume'] = df['volume'].astype(float)
        
        # Calculate indicators
        indicators_data = calculate_indicators(df, ["MACD", "RSI", "KDJ", "BOLL", "MA"])
        
        # Detect signals
        signals = detect_signals(df, indicators_data)
        
        # Calculate support/resistance
        levels = calculate_support_resistance(df)
        
        # Determine trend
        trend = determine_trend(df)
        
        # Generate summary
        summary = self._generate_analysis_summary(
            code, stock_name, trend, levels, signals, df
        )
        
        return {
            "code": code,
            "name": stock_name,
            "trend": trend,
            "support": levels["support"],
            "resistance": levels["resistance"],
            "signals": [
                {
                    "type": s["type"],
                    "indicator": s["indicator"],
                    "signal": s["signal"],
                    "description": s["description"]
                }
                for s in signals
            ],
            "summary": summary,
            "disclaimer": "以上分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。"
        }
    
    def _generate_analysis_summary(
        self,
        code: str,
        name: str,
        trend: str,
        levels: Dict[str, float],
        signals: List[Dict],
        df: pd.DataFrame
    ) -> str:
        """Generate analysis summary text."""
        if df.empty:
            return f"无法获取{name}({code})的行情数据"
        
        last = df.iloc[-1]
        current_price = last['close']
        
        # Calculate change
        if len(df) > 1:
            prev_close = df.iloc[-2]['close']
            change = current_price - prev_close
            change_pct = (change / prev_close) * 100 if prev_close else 0
        else:
            change = 0
            change_pct = 0
        
        parts = []
        
        # Basic info
        parts.append(f"{name}({code})当前价格{current_price:.2f}元，")
        if change >= 0:
            parts.append(f"涨{change_pct:.2f}%。")
        else:
            parts.append(f"跌{abs(change_pct):.2f}%。")
        
        # Trend
        parts.append(f"当前处于{trend}。")
        
        # Support/Resistance
        parts.append(f"支撑位{levels['support']:.2f}，压力位{levels['resistance']:.2f}。")
        
        # Signals
        bullish_signals = [s for s in signals if s["type"] == "bullish"]
        bearish_signals = [s for s in signals if s["type"] == "bearish"]
        
        if bullish_signals:
            signal_names = [s["signal"] for s in bullish_signals[:3]]
            parts.append(f"看多信号：{'、'.join(signal_names)}。")
        
        if bearish_signals:
            signal_names = [s["signal"] for s in bearish_signals[:3]]
            parts.append(f"看空信号：{'、'.join(signal_names)}。")
        
        if not bullish_signals and not bearish_signals:
            parts.append("暂无明显技术信号。")
        
        return "".join(parts)
    
    async def search_stock(self, keyword: str) -> List[Dict[str, str]]:
        """Search stocks by keyword.
        
        Args:
            keyword: Search keyword
            
        Returns:
            List of matching stocks
        """
        # Try using Plugin Service
        if self.stock_basic_service:
            try:
                results = self.stock_basic_service.search_stocks(keyword, limit=20)
                if results:
                    return [{"code": r["ts_code"], "name": r["name"]} for r in results]
            except Exception as e:
                logger.warning(f"Stock search via plugin failed: {e}")
        
        # Fallback to direct DB query
        if self.db is None:
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
        # Try using Plugin Service
        if self.stock_basic_service:
            try:
                info = self.stock_basic_service.get_stock_info(code)
                if info and "name" in info:
                    return info["name"]
            except Exception:
                pass
        
        # Fallback to DB query
        if self.db:
            try:
                query = "SELECT name FROM ods_stock_basic WHERE ts_code = %(code)s LIMIT 1"
                df = self.db.execute_query(query, {"code": code})
                if not df.empty:
                    return df.iloc[0]["name"]
            except Exception:
                pass
        
        # Default mock names
        names = {
            "600519.SH": "贵州茅台",
            "000001.SZ": "平安银行",
            "000858.SZ": "五粮液",
            "300750.SZ": "宁德时代",
            "601318.SH": "中国平安",
        }
        return names.get(code, code)
    
    def _get_mock_kline(self, code: str, start_date: str, end_date: str) -> Dict[str, Any]:
        """Generate mock K-line data."""
        import random
        
        data = []
        current_date = datetime.strptime(self._format_date(start_date), "%Y-%m-%d")
        end = datetime.strptime(self._format_date(end_date), "%Y-%m-%d")
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
