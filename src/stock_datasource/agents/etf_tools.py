"""ETF analysis tool functions for ETF Agent.

Provides tools for:
- ETF basic information query
- ETF daily data analysis
- Tracking index comparison
- ETF metrics calculation (tracking error, premium/discount, etc.)
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging
import math

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


def _get_latest_trade_date(table: str = "ods_etf_fund_daily") -> str:
    """Get the latest trade date from table."""
    query = f"""
    SELECT max(trade_date) as latest_date
    FROM {table}
    """
    result = _execute_query(query)
    if result and result[0].get('latest_date'):
        return result[0]['latest_date']
    return datetime.now().strftime('%Y%m%d')


def get_etf_basic_info(ts_code: str) -> Dict[str, Any]:
    """获取ETF基础信息。

    Args:
        ts_code: ETF代码，如 510300.SH（沪深300ETF）

    Returns:
        包含ETF名称、管理人、托管人、跟踪指数等信息的字典
    """
    ts_code_escaped = ts_code.replace("'", "''")
    query = f"""
    SELECT 
        ts_code,
        csname as name,
        cname as full_name,
        mgr_name as management,
        custod_name as custodian,
        etf_type as fund_type,
        setup_date as found_date,
        list_date,
        mgt_fee as m_fee,
        index_code,
        index_name as benchmark,
        list_status as status,
        exchange as market
    FROM ods_etf_basic
    WHERE ts_code = '{ts_code_escaped}'
    """
    result = _execute_query(query)
    if not result:
        return {"error": f"未找到ETF {ts_code} 的信息"}
    return result[0]


def get_etf_daily_data(ts_code: str, days: int = 30) -> Dict[str, Any]:
    """获取ETF日线数据。

    Args:
        ts_code: ETF代码
        days: 获取天数，默认30天

    Returns:
        包含日线数据列表的字典
    """
    ts_code_escaped = ts_code.replace("'", "''")
    query = f"""
    SELECT 
        ts_code,
        trade_date,
        open,
        high,
        low,
        close,
        pre_close,
        change,
        pct_chg,
        vol,
        amount
    FROM ods_etf_fund_daily
    WHERE ts_code = '{ts_code_escaped}'
    ORDER BY trade_date DESC
    LIMIT {days}
    """
    
    data = _execute_query(query)
    data.reverse()  # Chronological order
    
    if not data:
        return {"error": f"未找到ETF {ts_code} 的日线数据"}
    
    # Calculate some basic metrics
    latest = data[-1] if data else {}
    first = data[0] if data else {}
    
    # Period return
    period_return = None
    if latest.get('close') and first.get('close') and first['close'] > 0:
        period_return = round((latest['close'] / first['close'] - 1) * 100, 2)
    
    # Average volume
    volumes = [d.get('vol', 0) or 0 for d in data]
    avg_vol = round(sum(volumes) / len(volumes), 2) if volumes else 0
    
    # Average amount
    amounts = [d.get('amount', 0) or 0 for d in data]
    avg_amount = round(sum(amounts) / len(amounts), 2) if amounts else 0
    
    return {
        "ts_code": ts_code,
        "days": len(data),
        "latest_date": latest.get('trade_date'),
        "latest_close": latest.get('close'),
        "latest_pct_chg": latest.get('pct_chg'),
        "period_return": period_return,
        "avg_volume": avg_vol,
        "avg_amount": avg_amount,
        "data": data[-10:]  # Return last 10 days for context
    }


def get_etf_tracking_index(ts_code: str) -> Dict[str, Any]:
    """获取ETF跟踪指数信息。

    Args:
        ts_code: ETF代码

    Returns:
        包含跟踪指数信息的字典
    """
    ts_code_escaped = ts_code.replace("'", "''")
    
    # Get ETF benchmark
    etf_query = f"""
    SELECT index_name as benchmark, csname as name, index_code
    FROM ods_etf_basic
    WHERE ts_code = '{ts_code_escaped}'
    """
    etf_result = _execute_query(etf_query)
    
    if not etf_result:
        return {"error": f"未找到ETF {ts_code} 的信息"}
    
    benchmark = etf_result[0].get('benchmark')
    index_code = etf_result[0].get('index_code')
    etf_name = etf_result[0].get('name')
    
    if not benchmark and not index_code:
        return {
            "ts_code": ts_code,
            "etf_name": etf_name,
            "benchmark": None,
            "message": "该ETF未设置跟踪指数"
        }
    
    # Try to find index info by index_code first
    index_info = None
    if index_code:
        index_query = f"""
        SELECT ts_code, name, fullname, market, publisher
        FROM dim_index_basic
        WHERE ts_code = '{index_code}'
        LIMIT 1
        """
        index_result = _execute_query(index_query)
        if index_result:
            index_info = index_result[0]
    
    # If not found by code, try by name
    if not index_info and benchmark:
        index_query = f"""
        SELECT ts_code, name, fullname, market, publisher
        FROM dim_index_basic
        WHERE name ILIKE '%{benchmark.split("*")[0].split("指数")[0]}%'
        OR fullname ILIKE '%{benchmark.split("*")[0].split("指数")[0]}%'
        LIMIT 1
        """
        index_result = _execute_query(index_query)
        if index_result:
            index_info = index_result[0]
    
    return {
        "ts_code": ts_code,
        "etf_name": etf_name,
        "benchmark": benchmark,
        "index_code": index_code,
        "tracking_index": index_info
    }


def calculate_etf_metrics(ts_code: str, days: int = 60) -> Dict[str, Any]:
    """计算ETF关键指标。

    Args:
        ts_code: ETF代码
        days: 计算周期天数

    Returns:
        包含跟踪误差、波动率、流动性等指标的字典
    """
    ts_code_escaped = ts_code.replace("'", "''")
    
    # Get ETF daily data
    query = f"""
    SELECT 
        trade_date,
        close,
        pct_chg,
        vol,
        amount
    FROM ods_etf_fund_daily
    WHERE ts_code = '{ts_code_escaped}'
    ORDER BY trade_date DESC
    LIMIT {days}
    """
    
    data = _execute_query(query)
    data.reverse()
    
    if len(data) < 5:
        return {"error": f"ETF {ts_code} 数据不足，无法计算指标"}
    
    # Calculate metrics
    returns = [d.get('pct_chg', 0) or 0 for d in data]
    volumes = [d.get('vol', 0) or 0 for d in data]
    amounts = [d.get('amount', 0) or 0 for d in data]
    
    # Volatility (annualized)
    if len(returns) > 1:
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
        daily_vol = math.sqrt(variance)
        annual_vol = round(daily_vol * math.sqrt(252), 2)
    else:
        annual_vol = 0
    
    # Average daily turnover
    avg_amount = round(sum(amounts) / len(amounts) / 10000, 2) if amounts else 0  # In 万元
    
    # Recent performance
    latest_close = data[-1].get('close', 0) if data else 0
    
    # 5-day return
    if len(data) >= 5:
        return_5d = round(sum(returns[-5:]), 2)
    else:
        return_5d = None
    
    # 20-day return
    if len(data) >= 20:
        return_20d = round(sum(returns[-20:]), 2)
    else:
        return_20d = None
    
    # Max drawdown
    max_drawdown = 0
    peak = data[0].get('close', 0) if data else 0
    for d in data:
        close = d.get('close', 0) or 0
        if close > peak:
            peak = close
        drawdown = (peak - close) / peak * 100 if peak > 0 else 0
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    
    return {
        "ts_code": ts_code,
        "period_days": len(data),
        "latest_close": latest_close,
        "annual_volatility": annual_vol,
        "avg_daily_amount_wan": avg_amount,
        "return_5d": return_5d,
        "return_20d": return_20d,
        "max_drawdown": round(max_drawdown, 2),
        "latest_date": data[-1].get('trade_date') if data else None
    }


def compare_etf_with_index(ts_code: str, days: int = 30) -> Dict[str, Any]:
    """ETF与跟踪指数对比分析。

    Args:
        ts_code: ETF代码
        days: 对比天数

    Returns:
        包含ETF与指数对比数据的字典
    """
    ts_code_escaped = ts_code.replace("'", "''")
    
    # Get ETF info and benchmark
    etf_info = get_etf_basic_info(ts_code)
    if "error" in etf_info:
        return etf_info
    
    benchmark = etf_info.get('benchmark')
    if not benchmark:
        return {
            "ts_code": ts_code,
            "message": "该ETF未设置跟踪指数，无法进行对比分析"
        }
    
    # Get ETF returns
    etf_query = f"""
    SELECT trade_date, pct_chg
    FROM ods_etf_fund_daily
    WHERE ts_code = '{ts_code_escaped}'
    ORDER BY trade_date DESC
    LIMIT {days}
    """
    etf_data = _execute_query(etf_query)
    
    if not etf_data:
        return {"error": f"未找到ETF {ts_code} 的日线数据"}
    
    # Calculate ETF cumulative return
    etf_returns = [d.get('pct_chg', 0) or 0 for d in reversed(etf_data)]
    etf_cum_return = sum(etf_returns)
    
    # Try to find matching index data
    # This is a simplified comparison - in reality you'd need to match the exact benchmark index
    index_data = None
    index_cum_return = None
    tracking_diff = None
    
    # Common index mappings for ETFs
    index_mappings = {
        "沪深300": "000300.SH",
        "中证500": "000905.SH",
        "上证50": "000016.SH",
        "创业板": "399006.SZ",
        "中证1000": "000852.SH",
    }
    
    matched_index = None
    for key, code in index_mappings.items():
        if key in benchmark:
            matched_index = code
            break
    
    if matched_index:
        index_query = f"""
        SELECT trade_date, 
               (close - pre_close) / pre_close * 100 as pct_chg
        FROM ods_idx_factor_pro
        WHERE ts_code = '{matched_index}'
        ORDER BY trade_date DESC
        LIMIT {days}
        """
        index_data = _execute_query(index_query)
        
        if index_data:
            index_returns = [d.get('pct_chg', 0) or 0 for d in reversed(index_data)]
            index_cum_return = sum(index_returns)
            tracking_diff = round(etf_cum_return - index_cum_return, 2)
    
    return {
        "ts_code": ts_code,
        "etf_name": etf_info.get('name'),
        "benchmark": benchmark,
        "matched_index": matched_index,
        "period_days": len(etf_data),
        "etf_cum_return": round(etf_cum_return, 2),
        "index_cum_return": round(index_cum_return, 2) if index_cum_return is not None else None,
        "tracking_diff": tracking_diff,
        "analysis": _generate_tracking_analysis(etf_cum_return, index_cum_return, tracking_diff)
    }


def _generate_tracking_analysis(etf_return: float, index_return: Optional[float], diff: Optional[float]) -> str:
    """Generate tracking analysis text."""
    if index_return is None or diff is None:
        return "无法获取跟踪指数数据进行对比"
    
    if abs(diff) < 0.5:
        return f"ETF跟踪效果良好，与指数收益差异仅{diff}%"
    elif diff > 0:
        return f"ETF表现优于跟踪指数{diff}%，可能存在正向跟踪偏离"
    else:
        return f"ETF表现弱于跟踪指数{abs(diff)}%，可能存在负向跟踪偏离"


def get_etf_comprehensive_analysis(ts_code: str) -> Dict[str, Any]:
    """ETF综合分析（快速分析用）。

    Args:
        ts_code: ETF代码

    Returns:
        包含完整分析结果的字典
    """
    # Get basic info
    basic_info = get_etf_basic_info(ts_code)
    if "error" in basic_info:
        return basic_info
    
    # Get daily data
    daily_data = get_etf_daily_data(ts_code, days=60)
    
    # Get metrics
    metrics = calculate_etf_metrics(ts_code, days=60)
    
    # Get tracking info
    tracking_info = get_etf_tracking_index(ts_code)
    
    # Get comparison
    comparison = compare_etf_with_index(ts_code, days=30)
    
    # Generate signals
    signals = []
    
    # Volume signal
    if daily_data.get('avg_amount', 0) > 10000:  # > 1亿
        signals.append("流动性良好，日均成交额超过1亿")
    elif daily_data.get('avg_amount', 0) < 1000:  # < 1000万
        signals.append("⚠️ 流动性较差，日均成交额不足1000万")
    
    # Volatility signal
    if metrics.get('annual_volatility', 0) > 30:
        signals.append("⚠️ 波动率较高，年化波动率超过30%")
    elif metrics.get('annual_volatility', 0) < 15:
        signals.append("波动率较低，适合稳健投资")
    
    # Return signals
    if metrics.get('return_5d') is not None:
        if metrics['return_5d'] > 5:
            signals.append(f"近5日上涨{metrics['return_5d']}%，短期表现强势")
        elif metrics['return_5d'] < -5:
            signals.append(f"⚠️ 近5日下跌{abs(metrics['return_5d'])}%，短期表现弱势")
    
    # Drawdown signal
    if metrics.get('max_drawdown', 0) > 10:
        signals.append(f"⚠️ 近期最大回撤{metrics['max_drawdown']}%，注意风险")
    
    # Tracking signal
    if comparison.get('tracking_diff') is not None:
        if abs(comparison['tracking_diff']) > 2:
            signals.append(f"⚠️ 跟踪偏离较大：{comparison['tracking_diff']}%")
    
    return {
        "ts_code": ts_code,
        "name": basic_info.get('name'),
        "trade_date": daily_data.get('latest_date'),
        "basic_info": {
            "management": basic_info.get('management'),
            "custodian": basic_info.get('custodian'),
            "fund_type": basic_info.get('fund_type'),
            "list_date": basic_info.get('list_date'),
            "m_fee": basic_info.get('m_fee'),
            "c_fee": basic_info.get('c_fee'),
            "benchmark": basic_info.get('benchmark'),
            "status": basic_info.get('status'),
        },
        "price_metrics": {
            "latest_close": daily_data.get('latest_close'),
            "latest_pct_chg": daily_data.get('latest_pct_chg'),
            "return_5d": metrics.get('return_5d'),
            "return_20d": metrics.get('return_20d'),
            "period_return": daily_data.get('period_return'),
        },
        "volume_metrics": {
            "avg_volume": daily_data.get('avg_volume'),
            "avg_amount_wan": metrics.get('avg_daily_amount_wan'),
        },
        "risk_metrics": {
            "annual_volatility": metrics.get('annual_volatility'),
            "max_drawdown": metrics.get('max_drawdown'),
        },
        "tracking_info": {
            "benchmark": tracking_info.get('benchmark'),
            "tracking_index": tracking_info.get('tracking_index'),
            "tracking_diff": comparison.get('tracking_diff'),
            "analysis": comparison.get('analysis'),
        },
        "signals": signals,
    }
