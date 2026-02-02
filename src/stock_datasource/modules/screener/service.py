"""Screener service - 选股服务层

优先使用 Plugin Services 获取数据，避免直接写 SQL 查询。
"""

import logging
import math
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd

from stock_datasource.plugins.tushare_daily_basic.service import TuShareDailyBasicService
from stock_datasource.plugins.tushare_stock_basic.service import TuShareStockBasicService
from stock_datasource.plugins.tushare_daily.service import TuShareDailyService

from .schemas import (
    ScreenerCondition, StockItem, SectorInfo
)

logger = logging.getLogger(__name__)


def _format_date(date_val) -> Optional[str]:
    """Format date value to YYYY-MM-DD string."""
    if date_val is None:
        return None
    if isinstance(date_val, str):
        return date_val.split()[0].split('T')[0]
    if hasattr(date_val, 'strftime'):
        return date_val.strftime('%Y-%m-%d')
    return str(date_val).split()[0]


def _safe_float(val) -> Optional[float]:
    """Safely convert to float, handling NaN and None."""
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


# 操作符映射
OPERATORS = {
    "gt": lambda x, v: x > v,
    "gte": lambda x, v: x >= v,
    "lt": lambda x, v: x < v,
    "lte": lambda x, v: x <= v,
    "eq": lambda x, v: x == v,
    "neq": lambda x, v: x != v,
    ">": lambda x, v: x > v,
    ">=": lambda x, v: x >= v,
    "<": lambda x, v: x < v,
    "<=": lambda x, v: x <= v,
    "=": lambda x, v: x == v,
    "!=": lambda x, v: x != v,
}

# 字段名映射 (前端字段 -> 数据源字段)
FIELD_MAPPING = {
    # 估值指标 (来自 daily_basic)
    "pe": "pe_ttm",
    "pe_ttm": "pe_ttm",
    "pb": "pb",
    "ps": "ps_ttm",
    "ps_ttm": "ps_ttm",
    "dv_ratio": "dv_ratio",
    "total_mv": "total_mv",
    "circ_mv": "circ_mv",
    "turnover_rate": "turnover_rate",
    "volume_ratio": "volume_ratio",
    # 行情指标 (来自 daily)
    "pct_chg": "pct_chg",
    "close": "close",
    "open": "open",
    "high": "high",
    "low": "low",
    "vol": "vol",
    "amount": "amount",
    # 基本信息 (来自 stock_basic)
    "industry": "industry",
}

# 数据源分类
DAILY_BASIC_FIELDS = {"pe_ttm", "pb", "ps_ttm", "dv_ratio", "total_mv", "circ_mv", 
                       "turnover_rate", "volume_ratio", "close"}
DAILY_FIELDS = {"pct_chg", "open", "high", "low", "vol", "amount"}
STOCK_BASIC_FIELDS = {"industry", "name", "area", "market"}


class ScreenerService:
    """选股服务 - 使用 Plugin Services 获取数据"""
    
    def __init__(self):
        self.daily_basic_service = TuShareDailyBasicService()
        self.stock_basic_service = TuShareStockBasicService()
        self.daily_service = TuShareDailyService()
        
        # 缓存
        self._stock_names: Dict[str, str] = {}
        self._stock_industries: Dict[str, str] = {}
        self._latest_date: Optional[str] = None
    
    def _load_stock_basic_cache(self):
        """加载股票基本信息缓存"""
        if self._stock_names:
            return
        try:
            df = self.stock_basic_service.get_all_stock_basic_df()
            self._stock_names = dict(zip(df['ts_code'], df['name']))
            self._stock_industries = dict(zip(df['ts_code'], df['industry']))
        except Exception as e:
            logger.error(f"Failed to load stock basic cache: {e}")
    
    def get_latest_trade_date(self) -> Optional[str]:
        """获取最新交易日期 - 使用 daily_service"""
        if self._latest_date:
            return self._latest_date
        try:
            self._latest_date = self.daily_service.get_latest_trade_date()
            return self._latest_date
        except Exception as e:
            logger.error(f"Failed to get latest trade date: {e}")
            return None
    
    def get_stock_names(self, ts_codes: List[str]) -> Dict[str, str]:
        """获取股票名称映射 - 使用 stock_basic_service"""
        self._load_stock_basic_cache()
        return {code: self._stock_names.get(code, code) for code in ts_codes}
    
    def _get_merged_data(self, trade_date: str) -> pd.DataFrame:
        """
        获取合并后的股票数据 - 使用 Plugin Services
        
        合并 daily + daily_basic + stock_basic 数据
        """
        # 1. 获取日行情数据 - 使用 daily_service
        daily_df = self.daily_service.get_all_daily_by_date(trade_date)
        if daily_df.empty:
            return pd.DataFrame()
        
        # 2. 获取日基本指标数据 - 使用 daily_basic_service
        daily_basic_df = self.daily_basic_service.get_all_daily_basic_by_date(trade_date)
        
        # 3. 获取股票基本信息 - 使用 stock_basic_service
        self._load_stock_basic_cache()
        
        # 4. 合并数据
        # 合并 daily 和 daily_basic
        if not daily_basic_df.empty:
            # 避免重复列
            merge_cols = ['ts_code', 'trade_date']
            basic_cols = [c for c in daily_basic_df.columns if c not in daily_df.columns or c in merge_cols]
            merged_df = daily_df.merge(
                daily_basic_df[basic_cols], 
                on=merge_cols, 
                how='left'
            )
        else:
            merged_df = daily_df
        
        # 添加股票名称和行业
        merged_df['stock_name'] = merged_df['ts_code'].map(
            lambda x: self._stock_names.get(x, x)
        )
        merged_df['industry'] = merged_df['ts_code'].map(
            lambda x: self._stock_industries.get(x)
        )
        
        return merged_df
    
    def _apply_conditions(
        self, 
        df: pd.DataFrame, 
        conditions: List[ScreenerCondition]
    ) -> pd.DataFrame:
        """应用筛选条件到 DataFrame"""
        if df.empty or not conditions:
            return df
        
        mask = pd.Series([True] * len(df), index=df.index)
        
        for cond in conditions:
            # 映射字段名
            field = FIELD_MAPPING.get(cond.field, cond.field)
            
            if field not in df.columns:
                logger.warning(f"Field not found in data: {field}")
                continue
            
            op_func = OPERATORS.get(cond.operator)
            if not op_func:
                logger.warning(f"Unknown operator: {cond.operator}")
                continue
            
            try:
                # 处理不同类型的值
                if cond.operator in ("in", "IN"):
                    if isinstance(cond.value, list):
                        mask &= df[field].isin(cond.value)
                elif isinstance(cond.value, str) and field == "industry":
                    mask &= df[field] == cond.value
                else:
                    # 数值比较
                    col = pd.to_numeric(df[field], errors='coerce')
                    mask &= op_func(col, float(cond.value))
            except Exception as e:
                logger.warning(f"Failed to apply condition {cond}: {e}")
                continue
        
        return df[mask]
    
    def filter_by_conditions(
        self,
        conditions: List[ScreenerCondition],
        sort_by: str = "pct_chg",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 20,
        include_name: bool = True,
        trade_date: Optional[str] = None
    ) -> Tuple[List[StockItem], int]:
        """
        多条件筛选股票 - 使用 Plugin Services
        
        Args:
            conditions: 筛选条件列表
            sort_by: 排序字段
            sort_order: 排序方向 asc/desc
            page: 页码
            page_size: 每页数量
            include_name: 是否包含股票名称
            trade_date: 交易日期，默认使用最新日期
            
        Returns:
            (股票列表, 总数量)
        """
        target_date = trade_date or self.get_latest_trade_date()
        if not target_date:
            return [], 0
        
        # 获取合并后的数据
        merged_df = self._get_merged_data(target_date)
        if merged_df.empty:
            return [], 0
        
        # 应用筛选条件
        filtered_df = self._apply_conditions(merged_df, conditions)
        
        # 总数
        total = len(filtered_df)
        if total == 0:
            return [], 0
        
        # 排序
        sort_field = FIELD_MAPPING.get(sort_by, sort_by)
        if sort_field in filtered_df.columns:
            ascending = sort_order.lower() == "asc"
            filtered_df = filtered_df.sort_values(
                by=sort_field, 
                ascending=ascending, 
                na_position='last'
            )
        
        # 分页
        offset = (page - 1) * page_size
        page_df = filtered_df.iloc[offset:offset + page_size]
        
        # 转换为 StockItem
        items = self._df_to_stock_items(page_df)
        
        return items, total
    
    def get_stocks(
        self,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "pct_chg",
        sort_order: str = "desc",
        search: Optional[str] = None,
        trade_date: Optional[str] = None
    ) -> Tuple[List[StockItem], int]:
        """获取股票列表（带分页）- 使用 Plugin Services
        
        Args:
            trade_date: 交易日期，默认使用最新日期
        """
        target_date = trade_date or self.get_latest_trade_date()
        if not target_date:
            return [], 0
        
        # 获取合并后的数据
        merged_df = self._get_merged_data(target_date)
        if merged_df.empty:
            return [], 0
        
        # 搜索过滤
        if search:
            search_upper = search.strip().upper()
            mask = (
                merged_df['ts_code'].str.upper().str.contains(search_upper, na=False) |
                merged_df['stock_name'].str.contains(search, na=False)
            )
            merged_df = merged_df[mask]
        
        total = len(merged_df)
        if total == 0:
            return [], 0
        
        # 排序
        sort_field = FIELD_MAPPING.get(sort_by, sort_by)
        if sort_field in merged_df.columns:
            ascending = sort_order.lower() == "asc"
            merged_df = merged_df.sort_values(
                by=sort_field, 
                ascending=ascending, 
                na_position='last'
            )
        
        # 分页
        offset = (page - 1) * page_size
        page_df = merged_df.iloc[offset:offset + page_size]
        
        # 转换为 StockItem
        items = self._df_to_stock_items(page_df)
        
        return items, total
    
    def _df_to_stock_items(self, df: pd.DataFrame) -> List[StockItem]:
        """将 DataFrame 转换为 StockItem 列表"""
        items = []
        for _, row in df.iterrows():
            item = StockItem(
                ts_code=row.get('ts_code', ''),
                stock_name=row.get('stock_name') or row.get('ts_code', ''),
                trade_date=_format_date(row.get('trade_date')),
                open=_safe_float(row.get('open')),
                high=_safe_float(row.get('high')),
                low=_safe_float(row.get('low')),
                close=_safe_float(row.get('close')),
                pct_chg=_safe_float(row.get('pct_chg')),
                vol=_safe_float(row.get('vol')),
                amount=_safe_float(row.get('amount')),
                pe_ttm=_safe_float(row.get('pe_ttm')),
                pb=_safe_float(row.get('pb')),
                ps_ttm=_safe_float(row.get('ps_ttm')),
                dv_ratio=_safe_float(row.get('dv_ratio')),
                total_mv=_safe_float(row.get('total_mv')),
                circ_mv=_safe_float(row.get('circ_mv')),
                turnover_rate=_safe_float(row.get('turnover_rate')),
                industry=row.get('industry'),
            )
            items.append(item)
        return items
    
    def get_sectors(self) -> List[SectorInfo]:
        """获取行业列表 - 使用 stock_basic_service"""
        try:
            industries = self.stock_basic_service.get_all_industries()
            return [
                SectorInfo(
                    name=item['industry'],
                    stock_count=int(item['stock_count'])
                )
                for item in industries
                if item.get('industry')
            ]
        except Exception as e:
            logger.error(f"Failed to get sectors: {e}")
            return []
    
    def get_stocks_by_sector(
        self,
        sector: str,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "pct_chg",
        sort_order: str = "desc"
    ) -> Tuple[List[StockItem], int]:
        """按行业获取股票列表"""
        conditions = [ScreenerCondition(field="industry", operator="eq", value=sector)]
        return self.filter_by_conditions(
            conditions=conditions,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size
        )
    
    def get_available_fields(self) -> List[Dict[str, Any]]:
        """获取可用筛选字段"""
        return [
            {"field": "pe", "label": "PE (市盈率)", "type": "number"},
            {"field": "pb", "label": "PB (市净率)", "type": "number"},
            {"field": "ps", "label": "PS (市销率)", "type": "number"},
            {"field": "dv_ratio", "label": "股息率 (%)", "type": "number"},
            {"field": "turnover_rate", "label": "换手率 (%)", "type": "number"},
            {"field": "volume_ratio", "label": "量比", "type": "number"},
            {"field": "pct_chg", "label": "涨跌幅 (%)", "type": "number"},
            {"field": "close", "label": "收盘价", "type": "number"},
            {"field": "total_mv", "label": "总市值 (万元)", "type": "number"},
            {"field": "circ_mv", "label": "流通市值 (万元)", "type": "number"},
            {"field": "vol", "label": "成交量 (手)", "type": "number"},
            {"field": "amount", "label": "成交额 (千元)", "type": "number"},
            {"field": "industry", "label": "行业", "type": "select"},
        ]


# 创建单例
_screener_service = None


def get_screener_service() -> ScreenerService:
    """获取 ScreenerService 单例"""
    global _screener_service
    if _screener_service is None:
        _screener_service = ScreenerService()
    return _screener_service
