"""Market overview analysis tool functions for Overview Agent.

Provides tools for:
- Major indices status
- Market breadth (up/down counts)
- Sector performance
- Hot ETFs analysis
- Market sentiment
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def _get_db():
    """Get database connection."""
    from stock_datasource.models.database import db_client
    return db_client


def _execute_query(query: str) -> List[Dict[str, Any]]:
    """Execute query and return results as list of dicts."""
    db = _get_db()
    df = db.execute_query(query)
    if df is None or df.empty:
        return []
    return df.to_dict('records')


def _get_latest_trade_date(table: str = "ods_idx_factor_pro") -> Optional[str]:
    """Get latest trade date from table."""
    query = f"""
    SELECT max(trade_date) as latest_date
    FROM {table}
    """
    result = _execute_query(query)
    if result and result[0].get('latest_date'):
        latest = result[0]['latest_date']
        if hasattr(latest, 'strftime'):
            return latest.strftime('%Y%m%d')
        return str(latest).replace('-', '')
    return None


# Major indices
MAJOR_INDICES = [
    ("000001.SH", "上证指数"),
    ("399001.SZ", "深证成指"),
    ("000300.SH", "沪深300"),
    ("000905.SH", "中证500"),
    ("000016.SH", "上证50"),
    ("399006.SZ", "创业板指"),
    ("000852.SH", "中证1000"),
    ("000688.SH", "科创50"),
]


def get_major_indices_status(date: Optional[str] = None) -> Dict[str, Any]:
    """获取主要指数状态。

    Args:
        date: 交易日期（YYYYMMDD格式），默认使用最新日期

    Returns:
        包含主要指数涨跌信息的字典
    """
    if not date:
        date = _get_latest_trade_date()
    
    if not date:
        return {"error": "无法获取交易日期"}
    
    indices_codes = [f"'{code}'" for code, _ in MAJOR_INDICES]
    indices_str = ", ".join(indices_codes)
    
    query = f"""
    SELECT 
        f.ts_code,
        b.name,
        f.close,
        f.pre_close,
        ROUND((f.close - f.pre_close) / f.pre_close * 100, 2) as pct_chg,
        f.vol,
        f.amount
    FROM ods_idx_factor_pro f
    LEFT JOIN dim_index_basic b ON f.ts_code = b.ts_code
    WHERE f.ts_code IN ({indices_str})
    AND f.trade_date = '{date}'
    """
    
    result = _execute_query(query)
    
    # Sort by predefined order
    code_order = {code: i for i, (code, _) in enumerate(MAJOR_INDICES)}
    result.sort(key=lambda x: code_order.get(x.get('ts_code', ''), 999))
    
    # Generate summary
    up_count = sum(1 for r in result if (r.get('pct_chg') or 0) > 0)
    down_count = sum(1 for r in result if (r.get('pct_chg') or 0) < 0)
    
    summary = f"主要指数{up_count}涨{down_count}跌"
    
    # Find best and worst
    if result:
        sorted_by_chg = sorted(result, key=lambda x: x.get('pct_chg') or 0, reverse=True)
        best = sorted_by_chg[0]
        worst = sorted_by_chg[-1]
        summary += f"，{best.get('name')}表现最好({best.get('pct_chg')}%)，{worst.get('name')}表现最弱({worst.get('pct_chg')}%)"
    
    return {
        "trade_date": date,
        "indices": result,
        "up_count": up_count,
        "down_count": down_count,
        "summary": summary
    }


def get_market_breadth(date: Optional[str] = None) -> Dict[str, Any]:
    """获取市场广度（涨跌家数、涨跌停数量）。

    Args:
        date: 交易日期（YYYYMMDD格式），默认使用最新日期

    Returns:
        包含涨跌家数统计的字典
    """
    if not date:
        date = _get_latest_trade_date("fact_daily_bar")
    
    if not date:
        return {"error": "无法获取交易日期"}
    
    query = f"""
    SELECT 
        SUM(CASE WHEN pct_chg > 0 THEN 1 ELSE 0 END) as up_count,
        SUM(CASE WHEN pct_chg < 0 THEN 1 ELSE 0 END) as down_count,
        SUM(CASE WHEN pct_chg = 0 OR pct_chg IS NULL THEN 1 ELSE 0 END) as flat_count,
        SUM(CASE WHEN pct_chg >= 9.9 THEN 1 ELSE 0 END) as limit_up_count,
        SUM(CASE WHEN pct_chg <= -9.9 THEN 1 ELSE 0 END) as limit_down_count,
        SUM(CASE WHEN pct_chg >= 19.9 THEN 1 ELSE 0 END) as limit_up_20_count,
        SUM(CASE WHEN pct_chg <= -19.9 THEN 1 ELSE 0 END) as limit_down_20_count,
        COUNT(*) as total_count,
        ROUND(SUM(amount) / 100000000, 2) as total_amount_yi
    FROM fact_daily_bar
    WHERE trade_date = '{date}'
    """
    
    result = _execute_query(query)
    
    if not result:
        return {"error": f"未找到{date}的市场数据"}
    
    stats = result[0]
    up = int(stats.get('up_count', 0) or 0)
    down = int(stats.get('down_count', 0) or 0)
    total = int(stats.get('total_count', 0) or 0)
    
    # Calculate up/down ratio (use None instead of inf for JSON compatibility)
    ratio = round(up / down, 2) if down > 0 else None
    
    # Generate summary
    if ratio is None:
        sentiment = "市场无下跌个股数据"
    elif ratio > 2:
        sentiment = "市场情绪偏多，上涨家数明显多于下跌"
    elif ratio > 1:
        sentiment = "市场情绪偏暖，上涨家数略多于下跌"
    elif ratio > 0.5:
        sentiment = "市场情绪偏弱，下跌家数多于上涨"
    else:
        sentiment = "市场情绪偏空，下跌家数明显多于上涨"
    
    return {
        "trade_date": date,
        "up_count": up,
        "down_count": down,
        "flat_count": int(stats.get('flat_count', 0) or 0),
        "limit_up_count": int(stats.get('limit_up_count', 0) or 0),
        "limit_down_count": int(stats.get('limit_down_count', 0) or 0),
        "limit_up_20_count": int(stats.get('limit_up_20_count', 0) or 0),
        "limit_down_20_count": int(stats.get('limit_down_20_count', 0) or 0),
        "total_count": total,
        "up_down_ratio": ratio,
        "total_amount_yi": stats.get('total_amount_yi'),
        "summary": sentiment
    }


def get_sector_performance(date: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
    """获取板块表现排名。

    Args:
        date: 交易日期（YYYYMMDD格式），默认使用最新日期
        limit: 返回数量

    Returns:
        包含板块涨跌排名的字典
    """
    if not date:
        date = _get_latest_trade_date()
    
    if not date:
        return {"error": "无法获取交易日期"}
    
    # Query sector indices (category contains '行业' or index_type is 'sector')
    query = f"""
    SELECT 
        f.ts_code,
        b.name,
        f.close,
        ROUND((f.close - f.pre_close) / f.pre_close * 100, 2) as pct_chg,
        f.amount
    FROM ods_idx_factor_pro f
    JOIN dim_index_basic b ON f.ts_code = b.ts_code
    WHERE f.trade_date = '{date}'
    AND (b.category LIKE '%行业%' OR b.index_type = '行业指数')
    AND f.close IS NOT NULL
    AND f.pre_close IS NOT NULL
    ORDER BY pct_chg DESC
    LIMIT {limit * 2}
    """
    
    result = _execute_query(query)
    
    if not result:
        # Fallback: try theme indices
        query = f"""
        SELECT 
            f.ts_code,
            b.name,
            f.close,
            ROUND((f.close - f.pre_close) / f.pre_close * 100, 2) as pct_chg,
            f.amount
        FROM ods_idx_factor_pro f
        JOIN dim_index_basic b ON f.ts_code = b.ts_code
        WHERE f.trade_date = '{date}'
        AND b.category LIKE '%主题%'
        AND f.close IS NOT NULL
        AND f.pre_close IS NOT NULL
        ORDER BY pct_chg DESC
        LIMIT {limit * 2}
        """
        result = _execute_query(query)
    
    # Get top gainers and losers
    top_gainers = result[:limit] if result else []
    top_losers = sorted(result, key=lambda x: x.get('pct_chg') or 0)[:limit] if result else []
    
    return {
        "trade_date": date,
        "top_gainers": top_gainers,
        "top_losers": top_losers,
    }


def get_hot_etfs_analysis(date: Optional[str] = None, sort_by: str = "amount", limit: int = 10) -> Dict[str, Any]:
    """获取热门ETF分析。

    Args:
        date: 交易日期（YYYYMMDD格式），默认使用最新日期
        sort_by: 排序字段（amount=成交额, pct_chg=涨跌幅）
        limit: 返回数量

    Returns:
        包含热门ETF列表和分析的字典
    """
    if not date:
        date = _get_latest_trade_date("ods_etf_fund_daily")
    
    if not date:
        return {"error": "无法获取交易日期"}
    
    order_field = "amount" if sort_by == "amount" else "pct_chg"
    order_dir = "DESC"
    
    query = f"""
    SELECT 
        d.ts_code,
        b.csname as name,
        b.index_name as benchmark,
        d.close,
        d.pct_chg,
        d.amount,
        d.vol
    FROM ods_etf_fund_daily d
    LEFT JOIN ods_etf_basic b ON d.ts_code = b.ts_code
    WHERE d.trade_date = '{date}'
    AND d.{order_field} IS NOT NULL
    ORDER BY d.{order_field} {order_dir}
    LIMIT {limit}
    """
    
    result = _execute_query(query)
    
    # Generate analysis
    analysis = []
    if result:
        if sort_by == "amount":
            top_etf = result[0]
            analysis.append(f"成交额最高的ETF是{top_etf.get('name')}({top_etf.get('ts_code')})，成交额{round(top_etf.get('amount', 0) / 10000, 2)}亿元")
        else:
            top_etf = result[0]
            analysis.append(f"涨幅最大的ETF是{top_etf.get('name')}({top_etf.get('ts_code')})，涨幅{top_etf.get('pct_chg')}%")
        
        # Check for theme concentration
        benchmarks = [r.get('benchmark', '') for r in result if r.get('benchmark')]
        if benchmarks:
            # Simple theme detection
            themes = {}
            for bm in benchmarks:
                for theme in ['科技', '新能源', '医药', '消费', '金融', '半导体', '军工']:
                    if theme in str(bm):
                        themes[theme] = themes.get(theme, 0) + 1
            
            if themes:
                top_theme = max(themes.items(), key=lambda x: x[1])
                if top_theme[1] >= 2:
                    analysis.append(f"热门ETF中{top_theme[0]}主题较为集中（{top_theme[1]}只）")
    
    return {
        "trade_date": date,
        "sort_by": sort_by,
        "etfs": result,
        "analysis": analysis
    }


def get_market_sentiment(date: Optional[str] = None) -> Dict[str, Any]:
    """获取市场情绪指标。

    Args:
        date: 交易日期（YYYYMMDD格式），默认使用最新日期

    Returns:
        包含市场情绪指标的字典
    """
    if not date:
        date = _get_latest_trade_date()
    
    if not date:
        return {"error": "无法获取交易日期"}
    
    # Get market breadth
    breadth = get_market_breadth(date)
    
    # Get index status
    indices = get_major_indices_status(date)
    
    # Calculate sentiment score (0-100)
    score = 50  # Neutral baseline
    
    # Adjust by up/down ratio
    if "up_down_ratio" in breadth:
        ratio = breadth["up_down_ratio"]
        if ratio is not None:
            if ratio > 2:
                score += 20
            elif ratio > 1.5:
                score += 15
            elif ratio > 1:
                score += 5
            elif ratio < 0.5:
                score -= 20
            elif ratio < 0.7:
                score -= 15
            elif ratio < 1:
                score -= 5
    
    # Adjust by limit up/down
    limit_up = breadth.get("limit_up_count", 0)
    limit_down = breadth.get("limit_down_count", 0)
    if limit_up > limit_down * 2:
        score += 10
    elif limit_down > limit_up * 2:
        score -= 10
    
    # Adjust by major indices
    if "indices" in indices:
        idx_up = sum(1 for i in indices["indices"] if (i.get("pct_chg") or 0) > 0)
        idx_down = len(indices["indices"]) - idx_up
        if idx_up > idx_down:
            score += 5
        elif idx_down > idx_up:
            score -= 5
    
    # Clamp score
    score = max(0, min(100, score))
    
    # Generate sentiment label
    if score >= 70:
        label = "乐观"
        description = "市场情绪积极，多头占优"
    elif score >= 55:
        label = "偏多"
        description = "市场情绪偏暖，略偏多头"
    elif score >= 45:
        label = "中性"
        description = "市场情绪中性，多空平衡"
    elif score >= 30:
        label = "偏空"
        description = "市场情绪偏弱，略偏空头"
    else:
        label = "悲观"
        description = "市场情绪低迷，空头占优"
    
    return {
        "trade_date": date,
        "sentiment_score": score,
        "sentiment_label": label,
        "sentiment_description": description,
        "factors": {
            "up_down_ratio": breadth.get("up_down_ratio"),
            "limit_up_count": breadth.get("limit_up_count"),
            "limit_down_count": breadth.get("limit_down_count"),
            "indices_up": indices.get("up_count"),
            "indices_down": indices.get("down_count"),
        }
    }


def get_market_daily_summary(date: Optional[str] = None) -> Dict[str, Any]:
    """获取市场每日综合摘要（快速分析用）。

    Args:
        date: 交易日期（YYYYMMDD格式），默认使用最新日期

    Returns:
        包含完整市场摘要的字典
    """
    if not date:
        date = _get_latest_trade_date()
    
    # Empty-data defaults (stable structure for frontend)
    empty_sentiment = {"score": 50, "label": "中性", "description": "暂无数据"}
    empty_breadth = {
        "up_count": 0,
        "down_count": 0,
        "limit_up_count": 0,
        "limit_down_count": 0,
        "total_amount_yi": 0,
        "up_down_ratio": None,
    }

    if not date:
        return {
            "trade_date": None,
            "market_summary": "暂无数据",
            "indices_summary": {},
            "market_breadth": empty_breadth,
            "sentiment": empty_sentiment,
            "hot_etfs": [],
            "signals": [],
        }
    
    # Collect all data (resilient: if error dict, treat as empty)
    indices = get_major_indices_status(date)
    if "error" in indices:
        indices = {"indices": [], "summary": "", "up_count": 0, "down_count": 0}

    breadth = get_market_breadth(date)
    if "error" in breadth:
        breadth = empty_breadth.copy()

    sentiment = get_market_sentiment(date)
    if "error" in sentiment:
        sentiment = {"sentiment_score": 50, "sentiment_label": "中性", "sentiment_description": "暂无情绪数据"}

    hot_etfs = get_hot_etfs_analysis(date, sort_by="amount", limit=5)
    if "error" in hot_etfs:
        hot_etfs = {"etfs": []}
    
    # Generate signals
    signals = []
    
    # Index signals
    if "indices" in indices:
        for idx in indices["indices"][:3]:  # Top 3 indices
            pct = idx.get("pct_chg", 0)
            name = idx.get("name", "")
            if pct and abs(pct) >= 1:
                direction = "上涨" if pct > 0 else "下跌"
                signals.append(f"{name}{direction}{abs(pct)}%")
    
    # Breadth signals
    if breadth.get("limit_up_count", 0) > 50:
        signals.append(f"涨停家数{breadth['limit_up_count']}家，市场活跃")
    if breadth.get("limit_down_count", 0) > 50:
        signals.append(f"⚠️ 跌停家数{breadth['limit_down_count']}家，注意风险")
    
    # Volume signals
    if breadth.get("total_amount_yi"):
        amount = breadth["total_amount_yi"]
        if amount > 10000:
            signals.append(f"两市成交额{amount}亿元，交投活跃")
        elif amount < 5000:
            signals.append(f"两市成交额{amount}亿元，交投清淡")
    
    # Generate summary text
    summary_parts = []
    
    # Index summary
    if indices.get("summary"):
        summary_parts.append(indices["summary"])
    
    # Breadth summary
    if breadth.get("summary"):
        summary_parts.append(breadth["summary"])
    
    # Sentiment
    if sentiment.get("sentiment_description"):
        summary_parts.append(sentiment["sentiment_description"])
    
    market_summary = "。".join(summary_parts) + "。" if summary_parts else "暂无数据"
    
    return {
        "trade_date": date,
        "market_summary": market_summary,
        "indices_summary": {
            "data": indices.get("indices", [])[:5],
            "up_count": indices.get("up_count"),
            "down_count": indices.get("down_count"),
        },
        "market_breadth": {
            "up_count": breadth.get("up_count", 0),
            "down_count": breadth.get("down_count", 0),
            "limit_up_count": breadth.get("limit_up_count", 0),
            "limit_down_count": breadth.get("limit_down_count", 0),
            "total_amount_yi": breadth.get("total_amount_yi", 0),
            "up_down_ratio": breadth.get("up_down_ratio"),
        },
        "sentiment": {
            "score": sentiment.get("sentiment_score", 50),
            "label": sentiment.get("sentiment_label", "中性"),
            "description": sentiment.get("sentiment_description", "暂无数据"),
        },
        "hot_etfs": hot_etfs.get("etfs", [])[:5],
        "signals": signals,
    }
