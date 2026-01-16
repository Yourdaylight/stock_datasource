"""Screener module router."""

from fastapi import APIRouter, Query
from typing import List, Any, Optional
from pydantic import BaseModel, Field
import logging
import pandas as pd

from stock_datasource.models.database import db_client
from stock_datasource.agents.tools import _format_date

logger = logging.getLogger(__name__)


def _safe_float(value) -> Optional[float]:
    """Convert value to float, return None if NaN or invalid."""
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None

router = APIRouter()


class ScreenerCondition(BaseModel):
    field: str
    operator: str
    value: Any


class ScreenerRequest(BaseModel):
    conditions: List[ScreenerCondition] = Field(default_factory=list)
    sort_by: str = None
    sort_order: str = "desc"
    limit: int = 100


class NLScreenerRequest(BaseModel):
    query: str


class StockItem(BaseModel):
    """Stock item with basic info and latest quote."""
    ts_code: str
    trade_date: Optional[str] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    pct_chg: Optional[float] = None
    vol: Optional[float] = None
    amount: Optional[float] = None
    pe_ttm: Optional[float] = None
    pb: Optional[float] = None
    total_mv: Optional[float] = None
    turnover_rate: Optional[float] = None


class StockListResponse(BaseModel):
    """Paginated stock list response."""
    items: List[StockItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class PresetStrategy(BaseModel):
    id: str
    name: str
    description: str
    conditions: List[ScreenerCondition]


@router.get("/stocks", response_model=StockListResponse)
async def get_stocks(
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "pct_chg",
    sort_order: str = "desc",
    search: Optional[str] = None
):
    """Get paginated stock list with latest quotes.
    
    This is the default API for the screener page, showing all stocks
    with their latest market data.
    """
    try:
        db = db_client
        
        # Get latest trade date
        date_query = "SELECT max(trade_date) as max_date FROM ods_daily"
        date_df = db.execute_query(date_query)
        if date_df.empty or date_df.iloc[0]['max_date'] is None:
            return StockListResponse(items=[], total=0, page=page, page_size=page_size, total_pages=0)
        
        latest_date = _format_date(date_df.iloc[0]['max_date'])
        
        # Build WHERE clause
        where_parts = [f"d.trade_date = '{latest_date}'"]
        if search:
            # Search by stock code (support partial match)
            search_clean = search.strip().upper()
            where_parts.append(f"d.ts_code LIKE '%{search_clean}%'")
        
        where_clause = " AND ".join(where_parts)
        
        # Validate sort field to prevent SQL injection
        allowed_sort_fields = {
            "ts_code", "close", "pct_chg", "vol", "amount", 
            "pe_ttm", "pb", "total_mv", "turnover_rate"
        }
        if sort_by not in allowed_sort_fields:
            sort_by = "pct_chg"
        
        sort_direction = "DESC" if sort_order.lower() == "desc" else "ASC"
        
        # Get total count
        count_query = f"""
            SELECT count(*) as cnt
            FROM ods_daily d
            WHERE {where_clause}
        """
        count_df = db.execute_query(count_query)
        total = int(count_df.iloc[0]['cnt']) if not count_df.empty else 0
        
        if total == 0:
            return StockListResponse(items=[], total=0, page=page, page_size=page_size, total_pages=0)
        
        # Calculate pagination
        total_pages = (total + page_size - 1) // page_size
        offset = (page - 1) * page_size
        
        # Get paginated data with valuation info
        data_query = f"""
            SELECT 
                d.ts_code,
                d.trade_date,
                d.open,
                d.high,
                d.low,
                d.close,
                d.pct_chg,
                d.vol,
                d.amount,
                b.pe_ttm,
                b.pb,
                b.total_mv,
                b.turnover_rate
            FROM ods_daily d
            LEFT JOIN ods_daily_basic b 
                ON d.ts_code = b.ts_code AND d.trade_date = b.trade_date
            WHERE {where_clause}
            ORDER BY {sort_by} {sort_direction}
            LIMIT {page_size} OFFSET {offset}
        """
        
        df = db.execute_query(data_query)
        
        items = []
        for _, row in df.iterrows():
            item = StockItem(
                ts_code=row['ts_code'],
                trade_date=_format_date(row['trade_date']),
                open=_safe_float(row.get('open')),
                high=_safe_float(row.get('high')),
                low=_safe_float(row.get('low')),
                close=_safe_float(row.get('close')),
                pct_chg=_safe_float(row.get('pct_chg')),
                vol=_safe_float(row.get('vol')),
                amount=_safe_float(row.get('amount')),
                pe_ttm=_safe_float(row.get('pe_ttm')),
                pb=_safe_float(row.get('pb')),
                total_mv=_safe_float(row.get('total_mv')),
                turnover_rate=_safe_float(row.get('turnover_rate')),
            )
            items.append(item)
        
        return StockListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
        
    except Exception as e:
        logger.error(f"Failed to get stocks: {e}")
        return StockListResponse(items=[], total=0, page=page, page_size=page_size, total_pages=0)


@router.post("/filter", response_model=StockListResponse)
async def filter_stocks(
    request: ScreenerRequest,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Filter stocks by conditions."""
    try:
        db = db_client
        
        # Get latest trade date
        date_query = "SELECT max(trade_date) as max_date FROM ods_daily"
        date_df = db.execute_query(date_query)
        if date_df.empty or date_df.iloc[0]['max_date'] is None:
            return StockListResponse(items=[], total=0, page=page, page_size=page_size, total_pages=0)
        
        latest_date = _format_date(date_df.iloc[0]['max_date'])
        
        # Build WHERE clause from conditions
        where_parts = [f"d.trade_date = '{latest_date}'"]
        
        # Map operators
        op_map = {
            "gt": ">", "gte": ">=", "lt": "<", "lte": "<=",
            "eq": "=", "neq": "!=", ">": ">", ">=": ">=",
            "<": "<", "<=": "<=", "=": "=", "!=": "!="
        }
        
        # Map fields to table aliases
        field_map = {
            "pe": "b.pe_ttm", "pe_ttm": "b.pe_ttm",
            "pb": "b.pb",
            "turnover_rate": "b.turnover_rate",
            "total_mv": "b.total_mv",
            "circ_mv": "b.circ_mv",
            "pct_chg": "d.pct_chg",
            "close": "d.close",
            "vol": "d.vol",
            "amount": "d.amount",
        }
        
        for cond in request.conditions:
            field = field_map.get(cond.field, f"d.{cond.field}")
            op = op_map.get(cond.operator, cond.operator)
            value = cond.value
            
            # Validate numeric value
            if isinstance(value, (int, float)):
                where_parts.append(f"{field} {op} {value}")
        
        where_clause = " AND ".join(where_parts)
        
        # Get total count
        count_query = f"""
            SELECT count(*) as cnt
            FROM ods_daily d
            LEFT JOIN ods_daily_basic b ON d.ts_code = b.ts_code AND d.trade_date = b.trade_date
            WHERE {where_clause}
        """
        count_df = db.execute_query(count_query)
        total = int(count_df.iloc[0]['cnt']) if not count_df.empty else 0
        
        if total == 0:
            return StockListResponse(items=[], total=0, page=page, page_size=page_size, total_pages=0)
        
        # Calculate pagination
        total_pages = (total + page_size - 1) // page_size
        offset = (page - 1) * page_size
        
        # Determine sort
        sort_by = request.sort_by or "pct_chg"
        sort_field = field_map.get(sort_by, f"d.{sort_by}")
        sort_direction = "DESC" if request.sort_order.lower() == "desc" else "ASC"
        
        # Get data
        data_query = f"""
            SELECT 
                d.ts_code,
                d.trade_date,
                d.open, d.high, d.low, d.close,
                d.pct_chg, d.vol, d.amount,
                b.pe_ttm, b.pb, b.total_mv, b.turnover_rate
            FROM ods_daily d
            LEFT JOIN ods_daily_basic b ON d.ts_code = b.ts_code AND d.trade_date = b.trade_date
            WHERE {where_clause}
            ORDER BY {sort_field} {sort_direction}
            LIMIT {page_size} OFFSET {offset}
        """
        
        df = db.execute_query(data_query)
        
        items = []
        for _, row in df.iterrows():
            item = StockItem(
                ts_code=row['ts_code'],
                trade_date=_format_date(row['trade_date']),
                open=_safe_float(row.get('open')),
                high=_safe_float(row.get('high')),
                low=_safe_float(row.get('low')),
                close=_safe_float(row.get('close')),
                pct_chg=_safe_float(row.get('pct_chg')),
                vol=_safe_float(row.get('vol')),
                amount=_safe_float(row.get('amount')),
                pe_ttm=_safe_float(row.get('pe_ttm')),
                pb=_safe_float(row.get('pb')),
                total_mv=_safe_float(row.get('total_mv')),
                turnover_rate=_safe_float(row.get('turnover_rate')),
            )
            items.append(item)
        
        return StockListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
        
    except Exception as e:
        logger.error(f"Failed to filter stocks: {e}")
        return StockListResponse(items=[], total=0, page=page, page_size=page_size, total_pages=0)


@router.post("/nl", response_model=StockListResponse)
async def nl_screener(
    request: NLScreenerRequest,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Natural language stock screening using AI agent."""
    try:
        from stock_datasource.agents import get_screener_agent
        
        agent = get_screener_agent()
        result = await agent.execute(request.query, {"session_id": "screener"})
        
        # For now, return the AI response as a message
        # In a full implementation, the agent would return structured data
        if result.success:
            # Try to parse structured results from agent
            # For now, just return empty with a note
            return StockListResponse(
                items=[],
                total=0,
                page=page,
                page_size=page_size,
                total_pages=0,
            )
        else:
            return StockListResponse(items=[], total=0, page=page, page_size=page_size, total_pages=0)
            
    except Exception as e:
        logger.error(f"NL screener failed: {e}")
        return StockListResponse(items=[], total=0, page=page, page_size=page_size, total_pages=0)


@router.get("/presets", response_model=List[PresetStrategy])
async def get_presets():
    """Get preset screening strategies."""
    return [
        PresetStrategy(
            id="low_pe",
            name="低估值策略",
            description="PE < 15, PB < 2",
            conditions=[
                ScreenerCondition(field="pe", operator="lt", value=15),
                ScreenerCondition(field="pb", operator="lt", value=2)
            ]
        ),
        PresetStrategy(
            id="high_turnover",
            name="活跃股策略",
            description="换手率 > 5%",
            conditions=[
                ScreenerCondition(field="turnover_rate", operator="gt", value=5)
            ]
        ),
        PresetStrategy(
            id="large_cap",
            name="大盘股策略",
            description="总市值 > 1000亿",
            conditions=[
                ScreenerCondition(field="total_mv", operator="gt", value=10000000)
            ]
        ),
        PresetStrategy(
            id="strong_momentum",
            name="强势股策略",
            description="涨幅 > 5%",
            conditions=[
                ScreenerCondition(field="pct_chg", operator="gt", value=5)
            ]
        )
    ]


@router.get("/fields")
async def get_fields():
    """Get available screening fields."""
    return [
        {"field": "pe", "label": "PE (市盈率)", "type": "number"},
        {"field": "pb", "label": "PB (市净率)", "type": "number"},
        {"field": "turnover_rate", "label": "换手率 (%)", "type": "number"},
        {"field": "pct_chg", "label": "涨跌幅 (%)", "type": "number"},
        {"field": "close", "label": "收盘价", "type": "number"},
        {"field": "total_mv", "label": "总市值 (万元)", "type": "number"},
        {"field": "vol", "label": "成交量 (手)", "type": "number"},
        {"field": "amount", "label": "成交额 (千元)", "type": "number"},
    ]


@router.get("/summary")
async def get_market_summary():
    """Get market summary statistics."""
    try:
        db = db_client
        
        # Get latest trade date
        date_query = "SELECT max(trade_date) as max_date FROM ods_daily"
        date_df = db.execute_query(date_query)
        if date_df.empty or date_df.iloc[0]['max_date'] is None:
            return {"error": "No data available"}
        
        latest_date = _format_date(date_df.iloc[0]['max_date'])
        
        # Get summary statistics
        summary_query = f"""
            SELECT 
                count(*) as total_stocks,
                sum(CASE WHEN pct_chg > 0 THEN 1 ELSE 0 END) as up_count,
                sum(CASE WHEN pct_chg < 0 THEN 1 ELSE 0 END) as down_count,
                sum(CASE WHEN pct_chg = 0 THEN 1 ELSE 0 END) as flat_count,
                sum(CASE WHEN pct_chg >= 9.9 THEN 1 ELSE 0 END) as limit_up,
                sum(CASE WHEN pct_chg <= -9.9 THEN 1 ELSE 0 END) as limit_down,
                avg(pct_chg) as avg_change
            FROM ods_daily
            WHERE trade_date = '{latest_date}'
        """
        
        df = db.execute_query(summary_query)
        
        if df.empty:
            return {"error": "No data available"}
        
        row = df.iloc[0]
        return {
            "trade_date": latest_date,
            "total_stocks": int(row['total_stocks']) if pd.notna(row['total_stocks']) else 0,
            "up_count": int(row['up_count']) if pd.notna(row['up_count']) else 0,
            "down_count": int(row['down_count']) if pd.notna(row['down_count']) else 0,
            "flat_count": int(row['flat_count']) if pd.notna(row['flat_count']) else 0,
            "limit_up": int(row['limit_up']) if pd.notna(row['limit_up']) else 0,
            "limit_down": int(row['limit_down']) if pd.notna(row['limit_down']) else 0,
            "avg_change": _safe_float(row['avg_change']) or 0,
        }
        
    except Exception as e:
        logger.error(f"Failed to get market summary: {e}")
        return {"error": str(e)}
