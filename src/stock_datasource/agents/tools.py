"""Stock analysis tools for DeepAgents.

These tools are used by the DeepAgent to query stock data from ClickHouse.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Lazy database client
_db_client = None


def _get_db():
    """Get database client lazily."""
    global _db_client
    if _db_client is None:
        try:
            from stock_datasource.models.database import db_client
            _db_client = db_client
        except Exception as e:
            logger.warning(f"Failed to get DB client: {e}")
    return _db_client


def _is_hk_stock(ts_code: str) -> bool:
    """Check if a stock code is a Hong Kong stock.
    
    Args:
        ts_code: Stock code, e.g. 00700.HK
        
    Returns:
        True if the code is a HK stock
    """
    return ts_code.upper().endswith('.HK')


def _normalize_ts_code(ts_code: str) -> str:
    """Normalize stock code by auto-completing suffix.
    
    Handles:
    - 5-digit codes -> HK stock (e.g. 00700 -> 00700.HK)
    - 6-digit codes starting with 6 -> SH (e.g. 600519 -> 600519.SH)
    - 6-digit codes starting with 0/3 -> SZ (e.g. 000001 -> 000001.SZ)
    - Already suffixed codes -> uppercase (e.g. 00700.hk -> 00700.HK)
    """
    ts_code = ts_code.strip()
    # 5-digit pure number -> HK stock
    if len(ts_code) == 5 and ts_code.isdigit():
        ts_code = f"{ts_code}.HK"
    # 6-digit pure number -> A-share
    elif len(ts_code) == 6 and ts_code.isdigit():
        if ts_code.startswith('6'):
            ts_code = f"{ts_code}.SH"
        elif ts_code.startswith(('0', '3')):
            ts_code = f"{ts_code}.SZ"
    return ts_code.upper()


def get_stock_info(ts_code: str) -> str:
    """获取股票基本信息（支持A股和港股）。
    
    Args:
        ts_code: 股票代码，如 600519.SH、000001.SZ 或 00700.HK。如果只有6位数字，会自动补全后缀。
        
    Returns:
        股票的基本信息，包括最新行情和估值数据。
    """
    ts_code = _normalize_ts_code(ts_code)
    
    # Route to HK handler if it's a HK stock
    if _is_hk_stock(ts_code):
        return _get_hk_stock_info(ts_code)
    
    db = _get_db()
    
    if db is None:
        return f"数据库连接失败，无法查询股票 {ts_code} 信息"
    
    try:
        # Get latest daily data with valuation
        query = """
            SELECT 
                d.ts_code,
                d.trade_date,
                d.open, d.high, d.low, d.close,
                d.pct_chg,
                d.vol as volume,
                d.amount,
                b.pe_ttm, b.pb, b.total_mv, b.circ_mv, b.turnover_rate
            FROM ods_daily d
            LEFT JOIN ods_daily_basic b ON d.ts_code = b.ts_code AND d.trade_date = b.trade_date
            WHERE d.ts_code = %(code)s
            ORDER BY d.trade_date DESC
            LIMIT 1
        """
        df = db.execute_query(query, {"code": ts_code})
        
        if df.empty:
            return f"未找到股票 {ts_code} 的数据，请确认股票代码是否正确"
        
        row = df.iloc[0]
        trade_date = _format_date(row['trade_date'])
        
        lines = [f"## 股票信息: {ts_code}"]
        lines.append(f"### 最新行情 ({trade_date})")
        lines.append(f"- 收盘价: {row['close']:.2f}")
        lines.append(f"- 涨跌幅: {row['pct_chg']:+.2f}%")
        lines.append(f"- 开盘: {row['open']:.2f} | 最高: {row['high']:.2f} | 最低: {row['low']:.2f}")
        lines.append(f"- 成交量: {row['volume']/10000:.2f}万手")
        lines.append(f"- 成交额: {row['amount']/100000000:.2f}亿元")
        
        if row.get('pe_ttm'):
            lines.append(f"\n### 估值指标")
            lines.append(f"- PE(TTM): {row['pe_ttm']:.2f}")
        if row.get('pb'):
            lines.append(f"- PB: {row['pb']:.2f}")
        if row.get('total_mv'):
            lines.append(f"- 总市值: {row['total_mv']/10000:.2f}亿元")
        if row.get('turnover_rate'):
            lines.append(f"- 换手率: {row['turnover_rate']:.2f}%")
        
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Query stock info failed: {e}")
        return f"查询股票 {ts_code} 信息失败: {str(e)}"


def get_stock_kline(ts_code: str, days: int = 30) -> str:
    """获取股票K线数据（日线），支持A股和港股。
    
    Args:
        ts_code: 股票代码，如 600519.SH 或 00700.HK
        days: 获取最近多少天的数据，默认30天
        
    Returns:
        K线数据，包括日期、开盘价、最高价、最低价、收盘价、成交量、涨跌幅等。
    """
    ts_code = _normalize_ts_code(ts_code)
    
    # Route to HK handler if it's a HK stock
    if _is_hk_stock(ts_code):
        return _get_hk_stock_kline(ts_code, days)
    
    db = _get_db()
    
    if db is None:
        return f"数据库连接失败，无法查询 {ts_code} K线数据"
    
    try:
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")
        
        query = """
            SELECT 
                trade_date,
                open, high, low, close,
                vol as volume,
                amount,
                pct_chg as change_pct
            FROM ods_daily
            WHERE ts_code = %(code)s
              AND trade_date BETWEEN %(start)s AND %(end)s
            ORDER BY trade_date DESC
            LIMIT %(limit)s
        """
        df = db.execute_query(query, {
            "code": ts_code,
            "start": start_date,
            "end": end_date,
            "limit": days
        })
        
        if df.empty:
            return f"未找到股票 {ts_code} 的K线数据"
        
        # Format output
        lines = [f"## {ts_code} 最近 {len(df)} 个交易日K线数据\n"]
        lines.append("| 日期 | 开盘 | 最高 | 最低 | 收盘 | 涨跌幅 | 成交量(万手) | 成交额(亿) |")
        lines.append("|------|------|------|------|------|--------|-------------|-----------|")
        
        for _, row in df.iterrows():
            lines.append(
                f"| {row['trade_date']} | {row['open']:.2f} | {row['high']:.2f} | "
                f"{row['low']:.2f} | {row['close']:.2f} | {row['change_pct']:+.2f}% | "
                f"{row['volume']/10000:.2f} | {row['amount']/100000000:.2f} |"
            )
        
        # Add summary
        latest = df.iloc[0]
        total_change = df['change_pct'].sum()
        avg_volume = df['volume'].mean() / 10000
        
        lines.append(f"\n### 统计摘要")
        lines.append(f"- 最新收盘价: {latest['close']:.2f}")
        lines.append(f"- 最新涨跌幅: {latest['change_pct']:+.2f}%")
        lines.append(f"- 期间累计涨跌: {total_change:.2f}%")
        lines.append(f"- 日均成交量: {avg_volume:.2f}万手")
        
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Query K-line failed: {e}")
        return f"查询 {ts_code} K线数据失败: {str(e)}"


def get_stock_valuation(ts_code: str) -> str:
    """获取股票估值指标（PE、PB、市值等），支持A股和港股。
    
    Args:
        ts_code: 股票代码，如 600519.SH 或 00700.HK
        
    Returns:
        估值指标，包括PE、PB、市值、换手率等。港股将返回财务指标信息。
    """
    ts_code = _normalize_ts_code(ts_code)
    
    # Route to HK handler if it's a HK stock
    if _is_hk_stock(ts_code):
        return _get_hk_stock_valuation(ts_code)
    
    db = _get_db()
    
    if db is None:
        return f"数据库连接失败，无法查询 {ts_code} 估值数据"
    
    try:
        query = """
            SELECT 
                trade_date,
                pe, pe_ttm, pb, ps, ps_ttm,
                total_mv, circ_mv,
                turnover_rate, turnover_rate_f
            FROM ods_daily_basic
            WHERE ts_code = %(code)s
            ORDER BY trade_date DESC
            LIMIT 1
        """
        df = db.execute_query(query, {"code": ts_code})
        
        if df.empty:
            return f"未找到股票 {ts_code} 的估值数据"
        
        row = df.iloc[0]
        lines = [f"## {ts_code} 估值指标 ({row['trade_date']})\n"]
        
        if row.get('pe_ttm'):
            lines.append(f"- PE(TTM): {row['pe_ttm']:.2f}")
        if row.get('pe'):
            lines.append(f"- PE(静态): {row['pe']:.2f}")
        if row.get('pb'):
            lines.append(f"- PB: {row['pb']:.2f}")
        if row.get('ps_ttm'):
            lines.append(f"- PS(TTM): {row['ps_ttm']:.2f}")
        if row.get('total_mv'):
            lines.append(f"- 总市值: {row['total_mv']/10000:.2f}亿元")
        if row.get('circ_mv'):
            lines.append(f"- 流通市值: {row['circ_mv']/10000:.2f}亿元")
        if row.get('turnover_rate'):
            lines.append(f"- 换手率: {row['turnover_rate']:.2f}%")
        if row.get('turnover_rate_f'):
            lines.append(f"- 换手率(自由流通): {row['turnover_rate_f']:.2f}%")
        
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Query valuation failed: {e}")
        return f"查询 {ts_code} 估值数据失败: {str(e)}"


def calculate_technical_indicators(ts_code: str) -> str:
    """计算股票技术指标（均线、MACD等），支持A股和港股。
    
    Args:
        ts_code: 股票代码，如 600519.SH 或 00700.HK
        
    Returns:
        技术指标分析结果，包括均线、趋势判断等。
    """
    ts_code = _normalize_ts_code(ts_code)
    
    # Route to HK handler if it's a HK stock
    if _is_hk_stock(ts_code):
        return _calculate_hk_technical_indicators(ts_code)
    
    db = _get_db()
    
    if db is None:
        return f"数据库连接失败，无法计算 {ts_code} 技术指标"
    
    try:
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=120)).strftime("%Y%m%d")
        
        query = """
            SELECT trade_date, close, vol as volume
            FROM ods_daily
            WHERE ts_code = %(code)s
              AND trade_date BETWEEN %(start)s AND %(end)s
            ORDER BY trade_date DESC
            LIMIT 60
        """
        df = db.execute_query(query, {
            "code": ts_code,
            "start": start_date,
            "end": end_date
        })
        
        if len(df) < 20:
            return f"股票 {ts_code} 数据不足，无法计算技术指标"
        
        closes = df['close'].tolist()
        volumes = df['volume'].tolist()
        
        # Calculate moving averages
        ma5 = sum(closes[:5]) / 5
        ma10 = sum(closes[:10]) / 10
        ma20 = sum(closes[:20]) / 20
        
        current_price = closes[0]
        
        # Calculate volume MA
        vol_ma5 = sum(volumes[:5]) / 5
        vol_ma10 = sum(volumes[:10]) / 10
        
        lines = [f"## {ts_code} 技术指标分析\n"]
        lines.append(f"### 当前价格: {current_price:.2f}\n")
        
        lines.append("### 均线系统")
        lines.append(f"- MA5: {ma5:.2f} ({'↑' if current_price > ma5 else '↓'})")
        lines.append(f"- MA10: {ma10:.2f} ({'↑' if current_price > ma10 else '↓'})")
        lines.append(f"- MA20: {ma20:.2f} ({'↑' if current_price > ma20 else '↓'})")
        
        # Trend analysis
        if ma5 > ma10 > ma20:
            trend = "多头排列（看涨）"
        elif ma5 < ma10 < ma20:
            trend = "空头排列（看跌）"
        else:
            trend = "震荡整理"
        lines.append(f"- 均线趋势: {trend}")
        
        # Support/Resistance
        lines.append(f"\n### 支撑/压力位")
        lines.append(f"- 短期支撑: {ma5:.2f}")
        lines.append(f"- 中期支撑: {ma10:.2f}")
        lines.append(f"- 强支撑: {ma20:.2f}")
        
        # Volume analysis
        lines.append(f"\n### 成交量分析")
        lines.append(f"- 5日均量: {vol_ma5/10000:.2f}万手")
        lines.append(f"- 10日均量: {vol_ma10/10000:.2f}万手")
        if vol_ma5 > vol_ma10 * 1.2:
            lines.append("- 量能状态: 放量")
        elif vol_ma5 < vol_ma10 * 0.8:
            lines.append("- 量能状态: 缩量")
        else:
            lines.append("- 量能状态: 平稳")
        
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Calculate indicators failed: {e}")
        return f"计算 {ts_code} 技术指标失败: {str(e)}"


# ==================== HK Stock Helper Functions ====================

def _get_hk_stock_info(ts_code: str) -> str:
    """获取港股基本信息。
    
    Args:
        ts_code: 港股代码，如 00700.HK
        
    Returns:
        港股的基本信息，包括最新行情。
    """
    db = _get_db()
    if db is None:
        return f"数据库连接失败，无法查询港股 {ts_code} 信息"
    
    try:
        query = """
            SELECT 
                d.ts_code,
                d.trade_date,
                d.open, d.high, d.low, d.close,
                d.pre_close,
                d.pct_chg,
                d.vol as volume,
                d.amount,
                b.name
            FROM ods_hk_daily d
            LEFT JOIN ods_hk_basic b ON d.ts_code = b.ts_code
            WHERE d.ts_code = %(code)s
            ORDER BY d.trade_date DESC
            LIMIT 1
        """
        df = db.execute_query(query, {"code": ts_code})
        
        if df.empty:
            return f"未找到港股 {ts_code} 的数据，请确认股票代码是否正确（港股代码格式如 00700.HK）"
        
        row = df.iloc[0]
        trade_date = _format_date(row['trade_date'])
        name = row.get('name', '') or ''
        
        lines = [f"## 港股信息: {ts_code} {name}"]
        lines.append(f"### 最新行情 ({trade_date})")
        lines.append(f"- 收盘价: {row['close']:.3f} HKD")
        
        if row.get('pct_chg') is not None:
            lines.append(f"- 涨跌幅: {row['pct_chg']:+.2f}%")
        if row.get('pre_close') is not None:
            lines.append(f"- 昨收价: {row['pre_close']:.3f}")
        if row.get('open') is not None:
            lines.append(f"- 开盘: {row['open']:.3f} | 最高: {row['high']:.3f} | 最低: {row['low']:.3f}")
        if row.get('volume') is not None:
            lines.append(f"- 成交量: {row['volume']/10000:.2f}万股")
        if row.get('amount') is not None and row['amount']:
            lines.append(f"- 成交额: {row['amount']/100000000:.2f}亿港元")
        
        lines.append(f"\n> 注：港股无涨跌幅限制，支持T+0交易，以港币计价")
        
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Query HK stock info failed: {e}")
        return f"查询港股 {ts_code} 信息失败: {str(e)}"


def _get_hk_stock_kline(ts_code: str, days: int = 30) -> str:
    """获取港股K线数据。
    
    Args:
        ts_code: 港股代码，如 00700.HK
        days: 获取最近多少天的数据
        
    Returns:
        K线数据表格。
    """
    db = _get_db()
    if db is None:
        return f"数据库连接失败，无法查询港股 {ts_code} K线数据"
    
    try:
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")
        
        query = """
            SELECT 
                trade_date,
                open, high, low, close,
                vol as volume,
                amount,
                pct_chg as change_pct
            FROM ods_hk_daily
            WHERE ts_code = %(code)s
              AND trade_date BETWEEN %(start)s AND %(end)s
            ORDER BY trade_date DESC
            LIMIT %(limit)s
        """
        df = db.execute_query(query, {
            "code": ts_code,
            "start": start_date,
            "end": end_date,
            "limit": days
        })
        
        if df.empty:
            return f"未找到港股 {ts_code} 的K线数据"
        
        lines = [f"## {ts_code} 最近 {len(df)} 个交易日K线数据（港股）\n"]
        lines.append("| 日期 | 开盘 | 最高 | 最低 | 收盘 | 涨跌幅 | 成交量(万股) |")
        lines.append("|------|------|------|------|------|--------|-------------|")
        
        for _, row in df.iterrows():
            open_p = f"{row['open']:.3f}" if row.get('open') is not None else "-"
            high_p = f"{row['high']:.3f}" if row.get('high') is not None else "-"
            low_p = f"{row['low']:.3f}" if row.get('low') is not None else "-"
            close_p = f"{row['close']:.3f}" if row.get('close') is not None else "-"
            chg = f"{row['change_pct']:+.2f}%" if row.get('change_pct') is not None else "-"
            vol = f"{row['volume']/10000:.2f}" if row.get('volume') is not None else "-"
            lines.append(f"| {row['trade_date']} | {open_p} | {high_p} | {low_p} | {close_p} | {chg} | {vol} |")
        
        # Summary
        latest = df.iloc[0]
        valid_chg = df['change_pct'].dropna()
        total_change = valid_chg.sum() if not valid_chg.empty else 0
        valid_vol = df['volume'].dropna()
        avg_volume = valid_vol.mean() / 10000 if not valid_vol.empty else 0
        
        lines.append(f"\n### 统计摘要")
        lines.append(f"- 最新收盘价: {latest['close']:.3f} HKD")
        if latest.get('change_pct') is not None:
            lines.append(f"- 最新涨跌幅: {latest['change_pct']:+.2f}%")
        lines.append(f"- 期间累计涨跌: {total_change:.2f}%")
        lines.append(f"- 日均成交量: {avg_volume:.2f}万股")
        
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Query HK K-line failed: {e}")
        return f"查询港股 {ts_code} K线数据失败: {str(e)}"


def _calculate_hk_technical_indicators(ts_code: str) -> str:
    """计算港股技术指标。
    
    Args:
        ts_code: 港股代码，如 00700.HK
        
    Returns:
        技术指标分析结果。
    """
    db = _get_db()
    if db is None:
        return f"数据库连接失败，无法计算港股 {ts_code} 技术指标"
    
    try:
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=120)).strftime("%Y%m%d")
        
        query = """
            SELECT trade_date, close, vol as volume
            FROM ods_hk_daily
            WHERE ts_code = %(code)s
              AND trade_date BETWEEN %(start)s AND %(end)s
              AND close IS NOT NULL
            ORDER BY trade_date DESC
            LIMIT 60
        """
        df = db.execute_query(query, {
            "code": ts_code,
            "start": start_date,
            "end": end_date
        })
        
        if len(df) < 20:
            return f"港股 {ts_code} 数据不足（仅 {len(df)} 条），无法计算技术指标。港股数据可能覆盖时间较短。"
        
        closes = df['close'].tolist()
        volumes = df['volume'].dropna().tolist()
        
        # Calculate moving averages
        ma5 = sum(closes[:5]) / 5
        ma10 = sum(closes[:10]) / 10
        ma20 = sum(closes[:20]) / 20
        
        current_price = closes[0]
        
        lines = [f"## {ts_code} 港股技术指标分析\n"]
        lines.append(f"### 当前价格: {current_price:.3f} HKD\n")
        
        lines.append("### 均线系统")
        lines.append(f"- MA5: {ma5:.3f} ({'↑' if current_price > ma5 else '↓'})")
        lines.append(f"- MA10: {ma10:.3f} ({'↑' if current_price > ma10 else '↓'})")
        lines.append(f"- MA20: {ma20:.3f} ({'↑' if current_price > ma20 else '↓'})")
        
        # Trend analysis
        if ma5 > ma10 > ma20:
            trend = "多头排列（看涨）"
        elif ma5 < ma10 < ma20:
            trend = "空头排列（看跌）"
        else:
            trend = "震荡整理"
        lines.append(f"- 均线趋势: {trend}")
        
        # Support/Resistance
        lines.append(f"\n### 支撑/压力位")
        lines.append(f"- 短期支撑: {ma5:.3f}")
        lines.append(f"- 中期支撑: {ma10:.3f}")
        lines.append(f"- 强支撑: {ma20:.3f}")
        
        # Volume analysis
        if len(volumes) >= 10:
            vol_ma5 = sum(volumes[:5]) / 5
            vol_ma10 = sum(volumes[:10]) / 10
            
            lines.append(f"\n### 成交量分析")
            lines.append(f"- 5日均量: {vol_ma5/10000:.2f}万股")
            lines.append(f"- 10日均量: {vol_ma10/10000:.2f}万股")
            if vol_ma5 > vol_ma10 * 1.2:
                lines.append("- 量能状态: 放量")
            elif vol_ma5 < vol_ma10 * 0.8:
                lines.append("- 量能状态: 缩量")
            else:
                lines.append("- 量能状态: 平稳")
        
        lines.append(f"\n> 注：港股无涨跌幅限制，技术指标信号需结合港股市场特点判断")
        
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Calculate HK indicators failed: {e}")
        return f"计算港股 {ts_code} 技术指标失败: {str(e)}"


def _get_hk_stock_valuation(ts_code: str) -> str:
    """获取港股估值信息（通过HK财务报告服务）。
    
    Args:
        ts_code: 港股代码，如 00700.HK
        
    Returns:
        港股估值/财务指标信息。
    """
    try:
        from stock_datasource.services.hk_financial_report_service import HKFinancialReportService
        
        service = HKFinancialReportService()
        result = service.get_financial_indicators(ts_code)
        
        if not result or result.get("error"):
            # Fallback: return basic price info from ods_hk_daily
            db = _get_db()
            if db is None:
                return f"港股 {ts_code} 暂无独立估值数据表（如PE/PB），建议通过财报分析获取相关指标"
            
            query = """
                SELECT 
                    d.ts_code, d.trade_date, d.close, d.pct_chg,
                    b.name
                FROM ods_hk_daily d
                LEFT JOIN ods_hk_basic b ON d.ts_code = b.ts_code
                WHERE d.ts_code = %(code)s
                ORDER BY d.trade_date DESC
                LIMIT 1
            """
            df = db.execute_query(query, {"code": ts_code})
            if df.empty:
                return f"港股 {ts_code} 暂无估值数据，建议使用财报分析功能获取财务指标"
            
            row = df.iloc[0]
            name = row.get('name', '') or ''
            lines = [f"## {ts_code} {name} 估值参考"]
            lines.append(f"- 最新收盘价: {row['close']:.3f} HKD")
            if row.get('pct_chg') is not None:
                lines.append(f"- 涨跌幅: {row['pct_chg']:+.2f}%")
            lines.append(f"\n> 港股暂无独立估值数据表（PE/PB/市值），详细财务指标请使用\"XX.HK 财报分析\"获取")
            return "\n".join(lines)
        
        # Format financial indicators
        lines = [f"## {ts_code} 港股财务指标\n"]
        for key, value in result.items():
            if key not in ("error", "ts_code"):
                lines.append(f"- {key}: {value}")
        
        return "\n".join(lines)
    except ImportError:
        return f"港股 {ts_code} 暂无独立估值数据表，建议使用\"XX.HK 财报分析\"获取财务指标"
    except Exception as e:
        logger.error(f"Get HK valuation failed: {e}")
        return f"港股 {ts_code} 暂无独立估值数据表，建议使用\"XX.HK 财报分析\"获取财务指标"


def screen_stocks(
    min_pe: Optional[float] = None,
    max_pe: Optional[float] = None,
    min_pb: Optional[float] = None,
    max_pb: Optional[float] = None,
    min_market_cap: Optional[float] = None,
    max_market_cap: Optional[float] = None,
    industry: Optional[str] = None,
    limit: int = 20
) -> str:
    """根据条件筛选股票。
    
    Args:
        min_pe: 最小PE值
        max_pe: 最大PE值
        min_pb: 最小PB值
        max_pb: 最大PB值
        min_market_cap: 最小市值（亿元）
        max_market_cap: 最大市值（亿元）
        industry: 行业名称（模糊匹配）
        limit: 返回结果数量，默认20
        
    Returns:
        符合条件的股票列表。
    """
    db = _get_db()
    
    if db is None:
        return "数据库连接失败，无法进行股票筛选"
    
    try:
        # Build query conditions
        conditions = ["1=1"]
        params = {"limit": limit}
        
        if min_pe is not None:
            conditions.append("b.pe_ttm >= %(min_pe)s")
            params["min_pe"] = min_pe
        if max_pe is not None:
            conditions.append("b.pe_ttm <= %(max_pe)s")
            params["max_pe"] = max_pe
        if min_pb is not None:
            conditions.append("b.pb >= %(min_pb)s")
            params["min_pb"] = min_pb
        if max_pb is not None:
            conditions.append("b.pb <= %(max_pb)s")
            params["max_pb"] = max_pb
        if min_market_cap is not None:
            conditions.append("b.total_mv >= %(min_mv)s")
            params["min_mv"] = min_market_cap * 10000  # Convert to 万元
        if max_market_cap is not None:
            conditions.append("b.total_mv <= %(max_mv)s")
            params["max_mv"] = max_market_cap * 10000
        
        where_clause = " AND ".join(conditions)
        
        # Get latest trade date
        date_query = "SELECT max(trade_date) as max_date FROM ods_daily_basic"
        date_df = db.execute_query(date_query)
        latest_date_raw = date_df.iloc[0]['max_date'] if not date_df.empty else None
        
        if latest_date_raw:
            latest_date = _format_date(latest_date_raw)
            where_clause += f" AND b.trade_date = '{latest_date}'"
        
        query = f"""
            SELECT 
                s.ts_code, s.name, s.industry,
                b.pe_ttm, b.pb, b.total_mv, b.turnover_rate
            FROM ods_stock_basic s
            JOIN ods_daily_basic b ON s.ts_code = b.ts_code
            WHERE {where_clause}
        """
        
        if industry:
            query += " AND s.industry LIKE %(industry)s"
            params["industry"] = f"%{industry}%"
        
        query += " ORDER BY b.total_mv DESC LIMIT %(limit)s"
        
        df = db.execute_query(query, params)
        
        if df.empty:
            return "未找到符合条件的股票"
        
        # Format output
        lines = [f"## 股票筛选结果 (共 {len(df)} 只)\n"]
        lines.append("| 代码 | 名称 | 行业 | PE(TTM) | PB | 市值(亿) | 换手率 |")
        lines.append("|------|------|------|---------|-----|----------|--------|")
        
        for _, row in df.iterrows():
            pe = f"{row['pe_ttm']:.1f}" if row.get('pe_ttm') else "-"
            pb = f"{row['pb']:.2f}" if row.get('pb') else "-"
            mv = f"{row['total_mv']/10000:.1f}" if row.get('total_mv') else "-"
            tr = f"{row['turnover_rate']:.2f}%" if row.get('turnover_rate') else "-"
            lines.append(f"| {row['ts_code']} | {row['name']} | {row.get('industry', '-')} | {pe} | {pb} | {mv} | {tr} |")
        
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Screen stocks failed: {e}")
        return f"股票筛选失败: {str(e)}"


def _format_date(date_val) -> str:
    """Format date value to YYYY-MM-DD string for ClickHouse Date type."""
    if date_val is None:
        return None
    if isinstance(date_val, str):
        # Already a string, extract date part if it contains time
        return date_val.split()[0].split('T')[0]
    if hasattr(date_val, 'strftime'):
        return date_val.strftime('%Y-%m-%d')
    return str(date_val).split()[0]


def get_market_overview() -> str:
    """获取市场整体概况（大盘指数、涨跌统计等）。
    
    Returns:
        市场概况信息。
    """
    db = _get_db()
    
    if db is None:
        return "数据库连接失败，无法获取市场概况"
    
    try:
        # Get latest trade date
        date_query = "SELECT max(trade_date) as max_date FROM ods_daily"
        date_df = db.execute_query(date_query)
        latest_date_raw = date_df.iloc[0]['max_date'] if not date_df.empty else None
        
        if not latest_date_raw:
            return "无法获取最新交易日期"
        
        # Format date to YYYY-MM-DD for ClickHouse Date type
        latest_date = _format_date(latest_date_raw)
        
        # Get market statistics
        stats_query = """
            SELECT 
                count(*) as total,
                sum(CASE WHEN pct_chg > 0 THEN 1 ELSE 0 END) as up_count,
                sum(CASE WHEN pct_chg < 0 THEN 1 ELSE 0 END) as down_count,
                sum(CASE WHEN pct_chg = 0 THEN 1 ELSE 0 END) as flat_count,
                sum(CASE WHEN pct_chg >= 9.9 THEN 1 ELSE 0 END) as limit_up,
                sum(CASE WHEN pct_chg <= -9.9 THEN 1 ELSE 0 END) as limit_down,
                avg(pct_chg) as avg_change,
                sum(amount) as total_amount
            FROM ods_daily
            WHERE trade_date = %(date)s
        """
        stats_df = db.execute_query(stats_query, {"date": latest_date})
        
        if stats_df.empty:
            return f"未找到 {latest_date} 的市场数据"
        
        stats = stats_df.iloc[0]
        
        lines = [f"## A股市场概况 ({latest_date})\n"]
        lines.append("### 涨跌统计")
        lines.append(f"- 上涨家数: {int(stats['up_count'])}")
        lines.append(f"- 下跌家数: {int(stats['down_count'])}")
        lines.append(f"- 平盘家数: {int(stats['flat_count'])}")
        lines.append(f"- 涨停家数: {int(stats['limit_up'])}")
        lines.append(f"- 跌停家数: {int(stats['limit_down'])}")
        lines.append(f"- 平均涨跌: {stats['avg_change']:.2f}%")
        lines.append(f"- 总成交额: {stats['total_amount']/100000000:.2f}亿元")
        
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Get market overview failed: {e}")
        return f"获取市场概况失败: {str(e)}"


def get_stock_profile(ts_code: str) -> str:
    """获取股票十维画像评分。
    
    Args:
        ts_code: 股票代码，如 600519.SH
        
    Returns:
        股票的十维画像评分和投资建议。
    """
    ts_code = _normalize_ts_code(ts_code)
    
    try:
        from stock_datasource.modules.screener.profile import get_profile_service
        
        service = get_profile_service()
        profile = service.calculate_profile(ts_code)
        
        if not profile:
            return f"未找到股票 {ts_code} 的画像数据"
        
        header = f"## {ts_code} {profile.stock_name} 十维画像"
        score_line = f"### 综合评分: {profile.total_score:.1f} 分"
        
        lines = [header, "", score_line, ""]
        lines.append("### 各维度评分")
        lines.append("| 维度 | 评分 | 等级 | 权重 |")
        lines.append("|------|------|------|------|")
        
        for dim in profile.dimensions:
            lines.append(f"| {dim.name} | {dim.score:.1f} | {dim.level} | {dim.weight*100:.0f}% |")
        
        lines.append("")
        lines.append("### 投资建议")
        lines.append(profile.recommendation)
        
        newline = chr(10)
        return newline.join(lines)
    except Exception as e:
        logger.error(f"Get stock profile failed: {e}")
        return f"获取 {ts_code} 画像失败: {str(e)}"


def get_sector_stocks(sector: str, limit: int = 20) -> str:
    """获取特定行业的股票列表。
    
    Args:
        sector: 行业名称，如 "白酒"、"电子"、"银行"
        limit: 返回数量，默认20
        
    Returns:
        该行业的股票列表。
    """
    db = _get_db()
    
    if db is None:
        return f"数据库连接失败，无法查询 {sector} 行业股票"
    
    try:
        # Get latest trade date
        date_query = "SELECT max(trade_date) as max_date FROM ods_daily"
        date_df = db.execute_query(date_query)
        latest_date_raw = date_df.iloc[0]['max_date'] if not date_df.empty else None
        
        if not latest_date_raw:
            return "无法获取最新交易日期"
        
        latest_date = _format_date(latest_date_raw)
        
        query = f"""
            SELECT 
                s.ts_code, s.name, s.industry,
                d.close, d.pct_chg,
                b.pe_ttm, b.pb, b.total_mv
            FROM ods_stock_basic s
            JOIN ods_daily d ON s.ts_code = d.ts_code
            LEFT JOIN ods_daily_basic b ON s.ts_code = b.ts_code AND d.trade_date = b.trade_date
            WHERE s.industry = %(sector)s
            AND s.list_status = 'L'
            AND d.trade_date = '{latest_date}'
            ORDER BY b.total_mv DESC
            LIMIT %(limit)s
        """
        
        df = db.execute_query(query, {"sector": sector, "limit": limit})
        
        if df.empty:
            return f"未找到 {sector} 行业的股票，请确认行业名称是否正确"
        
        header = f"## {sector} 行业股票列表 (共 {len(df)} 只)"
        lines = [header, ""]
        lines.append("| 代码 | 名称 | 收盘价 | 涨跌幅 | PE | PB | 市值(亿) |")
        lines.append("|------|------|--------|--------|-----|-----|----------|")
        
        for _, row in df.iterrows():
            close = f"{row['close']:.2f}" if row.get('close') else "-"
            pct = f"{row['pct_chg']:+.2f}%" if row.get('pct_chg') else "-"
            pe = f"{row['pe_ttm']:.1f}" if row.get('pe_ttm') else "-"
            pb = f"{row['pb']:.2f}" if row.get('pb') else "-"
            mv = f"{row['total_mv']/10000:.1f}" if row.get('total_mv') else "-"
            lines.append(f"| {row['ts_code']} | {row['name']} | {close} | {pct} | {pe} | {pb} | {mv} |")
        
        newline = chr(10)
        return newline.join(lines)
    except Exception as e:
        logger.error(f"Get sector stocks failed: {e}")
        return f"获取 {sector} 行业股票失败: {str(e)}"


def get_available_sectors() -> str:
    """获取所有可用的行业列表。
    
    Returns:
        行业列表及每个行业的股票数量。
    """
    db = _get_db()
    
    if db is None:
        return "数据库连接失败，无法获取行业列表"
    
    try:
        query = """
            SELECT industry, count(*) as stock_count
            FROM ods_stock_basic
            WHERE list_status = 'L' AND industry IS NOT NULL AND industry != ''
            GROUP BY industry
            ORDER BY stock_count DESC
        """
        
        df = db.execute_query(query)
        
        if df.empty:
            return "未找到行业数据"
        
        lines = ["## A股行业列表", ""]
        lines.append("| 行业 | 股票数量 |")
        lines.append("|------|----------|")
        
        for _, row in df.iterrows():
            lines.append(f"| {row['industry']} | {row['stock_count']} |")
        
        lines.append("")
        lines.append(f"共 {len(df)} 个行业")
        
        newline = chr(10)
        return newline.join(lines)
    except Exception as e:
        logger.error(f"Get available sectors failed: {e}")
        return f"获取行业列表失败: {str(e)}"


# Export all tools
STOCK_TOOLS = [
    get_stock_info,
    get_stock_kline,
    get_stock_valuation,
    calculate_technical_indicators,
    screen_stocks,
    get_market_overview,
    get_stock_profile,
    get_sector_stocks,
    get_available_sectors,
]
