"""ETF/Index analysis tool functions for ETF Agent.

Provides tools for:
- Index basic information query
- Constituent stock and weight analysis
- Technical factor analysis (80+ indicators)
- Trend, momentum, volatility, volume, sentiment analysis
- Concentration risk analysis
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
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


def _get_latest_trade_date() -> str:
    """Get the latest trade date from ods_idx_factor_pro."""
    query = """
    SELECT max(trade_date) as latest_date
    FROM ods_idx_factor_pro
    """
    result = _execute_query(query)
    if result and result[0].get('latest_date'):
        return result[0]['latest_date']
    return datetime.now().strftime('%Y%m%d')


def _get_date_n_days_ago(n: int) -> str:
    """Get date string N days ago."""
    return (datetime.now() - timedelta(days=n)).strftime('%Y%m%d')


def get_index_info(ts_code: str) -> Dict[str, Any]:
    """获取指数基础信息。

    Args:
        ts_code: 指数代码，如 000300.SH（沪深300）

    Returns:
        包含指数名称、市场、发布方、加权方式等信息的字典
    """
    query = f"""
    SELECT 
        ts_code,
        name,
        fullname,
        market,
        publisher,
        index_type,
        category,
        base_date,
        base_point,
        list_date,
        weight_rule,
        desc,
        exp_date
    FROM dim_index_basic
    WHERE ts_code = '{ts_code}'
    """
    result = _execute_query(query)
    if not result:
        return {"error": f"未找到指数 {ts_code} 的信息"}
    return result[0]


def get_index_constituents(ts_code: str, trade_date: Optional[str] = None) -> Dict[str, Any]:
    """获取指数成分股及权重。

    Args:
        ts_code: 指数代码，如 000300.SH
        trade_date: 交易日期（YYYYMMDD格式），默认使用最新日期

    Returns:
        包含成分股列表和权重的字典
    """
    if not trade_date:
        # 获取最新权重日期
        date_query = f"""
        SELECT max(trade_date) as latest_date
        FROM ods_index_weight
        WHERE index_code = '{ts_code}'
        """
        date_result = _execute_query(date_query)
        if date_result and date_result[0].get('latest_date'):
            latest = date_result[0]['latest_date']
            # Handle both string and datetime types
            if hasattr(latest, 'strftime'):
                trade_date = latest.strftime('%Y%m%d')
            elif isinstance(latest, str) and latest not in ('', '1970-01-01', '1970-01-01 00:00:00'):
                trade_date = latest.replace('-', '')
            else:
                trade_date = None
        else:
            trade_date = None
        if not trade_date:
            return {"error": f"未找到指数 {ts_code} 的成分股数据"}

    query = f"""
    SELECT 
        index_code,
        con_code,
        trade_date,
        weight
    FROM ods_index_weight
    WHERE index_code = '{ts_code}'
    AND trade_date = '{trade_date}'
    ORDER BY weight DESC
    """
    result = _execute_query(query)
    if not result:
        return {"error": f"未找到指数 {ts_code} 在 {trade_date} 的成分股数据"}
    
    return {
        "index_code": ts_code,
        "trade_date": trade_date,
        "constituent_count": len(result),
        "constituents": result[:20],  # 返回前20个
        "total_weight": sum(r.get('weight', 0) or 0 for r in result)
    }


def get_index_factors(ts_code: str, days: int = 5) -> Dict[str, Any]:
    """获取指数最近N日的技术因子数据。

    Args:
        ts_code: 指数代码，如 000300.SH
        days: 获取最近多少天的数据，默认5天

    Returns:
        包含技术指标数据的字典
    """
    query = f"""
    SELECT *
    FROM ods_idx_factor_pro
    WHERE ts_code = '{ts_code}'
    ORDER BY trade_date DESC
    LIMIT {days}
    """
    result = _execute_query(query)
    if not result:
        return {"error": f"未找到指数 {ts_code} 的技术因子数据"}
    
    # 按日期正序返回
    result.reverse()
    return {
        "ts_code": ts_code,
        "days": len(result),
        "data": result
    }


def analyze_trend(ts_code: str) -> Dict[str, Any]:
    """分析指数趋势（均线系统 + MACD + DMI）。

    Args:
        ts_code: 指数代码

    Returns:
        趋势分析结果，包含趋势方向、强度、具体指标状态
    """
    query = f"""
    SELECT 
        ts_code, trade_date, close,
        ma_bfq_5, ma_bfq_10, ma_bfq_20, ma_bfq_60, ma_bfq_250,
        macd_dif_bfq, macd_dea_bfq, macd_bfq,
        dmi_pdi_bfq, dmi_mdi_bfq, dmi_adx_bfq
    FROM ods_idx_factor_pro
    WHERE ts_code = '{ts_code}'
    ORDER BY trade_date DESC
    LIMIT 5
    """
    result = _execute_query(query)
    if not result:
        return {"error": f"未找到指数 {ts_code} 的趋势数据"}
    
    latest = result[0]
    prev = result[1] if len(result) > 1 else latest
    
    # 均线分析
    ma5 = latest.get('ma_bfq_5') or 0
    ma10 = latest.get('ma_bfq_10') or 0
    ma20 = latest.get('ma_bfq_20') or 0
    ma60 = latest.get('ma_bfq_60') or 0
    ma250 = latest.get('ma_bfq_250') or 0
    close = latest.get('close') or 0
    
    # 判断均线排列
    if ma5 > ma10 > ma20 > ma60:
        ma_status = "多头排列"
        ma_score = 80
    elif ma5 < ma10 < ma20 < ma60:
        ma_status = "空头排列"
        ma_score = 20
    else:
        ma_status = "均线交织"
        ma_score = 50
    
    # 年线位置
    above_ma250 = close > ma250 if ma250 else None
    
    # MACD分析
    dif = latest.get('macd_dif_bfq') or 0
    dea = latest.get('macd_dea_bfq') or 0
    macd = latest.get('macd_bfq') or 0
    prev_dif = prev.get('macd_dif_bfq') or 0
    prev_dea = prev.get('macd_dea_bfq') or 0
    
    # 金叉死叉判断
    if dif > dea and prev_dif <= prev_dea:
        macd_cross = "金叉"
    elif dif < dea and prev_dif >= prev_dea:
        macd_cross = "死叉"
    else:
        macd_cross = "无交叉"
    
    if dif > 0 and dea > 0:
        macd_zone = "零轴上方"
        macd_score = 70 if dif > dea else 55
    elif dif < 0 and dea < 0:
        macd_zone = "零轴下方"
        macd_score = 30 if dif < dea else 45
    else:
        macd_zone = "零轴附近"
        macd_score = 50
    
    # DMI分析
    pdi = latest.get('dmi_pdi_bfq') or 0
    mdi = latest.get('dmi_mdi_bfq') or 0
    adx = latest.get('dmi_adx_bfq') or 0
    
    if adx > 25:
        trend_strength = "趋势明确"
        if pdi > mdi:
            dmi_status = "多头趋势"
            dmi_score = 75
        else:
            dmi_status = "空头趋势"
            dmi_score = 25
    else:
        trend_strength = "震荡市"
        dmi_status = "方向不明"
        dmi_score = 50
    
    # 综合评分
    trend_score = int(ma_score * 0.4 + macd_score * 0.35 + dmi_score * 0.25)
    
    if trend_score >= 65:
        trend_direction = "上涨趋势"
    elif trend_score <= 35:
        trend_direction = "下跌趋势"
    else:
        trend_direction = "震荡整理"
    
    return {
        "ts_code": ts_code,
        "trade_date": latest.get('trade_date'),
        "trend_direction": trend_direction,
        "trend_score": trend_score,
        "ma_analysis": {
            "status": ma_status,
            "score": ma_score,
            "ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60,
            "above_ma250": above_ma250
        },
        "macd_analysis": {
            "dif": dif, "dea": dea, "macd": macd,
            "cross": macd_cross,
            "zone": macd_zone,
            "score": macd_score
        },
        "dmi_analysis": {
            "pdi": pdi, "mdi": mdi, "adx": adx,
            "status": dmi_status,
            "strength": trend_strength,
            "score": dmi_score
        }
    }


def analyze_momentum(ts_code: str) -> Dict[str, Any]:
    """分析指数动量（KDJ + RSI + MTM + ROC）。

    Args:
        ts_code: 指数代码

    Returns:
        动量分析结果，包含超买超卖状态、动量方向
    """
    query = f"""
    SELECT 
        ts_code, trade_date,
        kdj_k_bfq, kdj_d_bfq, kdj_bfq,
        rsi_bfq_6, rsi_bfq_12, rsi_bfq_24,
        mtm_bfq, mtmma_bfq, roc_bfq, maroc_bfq
    FROM ods_idx_factor_pro
    WHERE ts_code = '{ts_code}'
    ORDER BY trade_date DESC
    LIMIT 3
    """
    result = _execute_query(query)
    if not result:
        return {"error": f"未找到指数 {ts_code} 的动量数据"}
    
    latest = result[0]
    prev = result[1] if len(result) > 1 else latest
    
    # KDJ分析
    k = latest.get('kdj_k_bfq') or 50
    d = latest.get('kdj_d_bfq') or 50
    j = latest.get('kdj_bfq') or 50
    prev_k = prev.get('kdj_k_bfq') or 50
    prev_d = prev.get('kdj_d_bfq') or 50
    
    if k > 80 and j > 100:
        kdj_status = "超买"
        kdj_score = 25
    elif k < 20 and j < 0:
        kdj_status = "超卖"
        kdj_score = 75
    else:
        kdj_status = "中性"
        kdj_score = 50
    
    # KDJ金叉死叉
    if k > d and prev_k <= prev_d:
        kdj_cross = "金叉"
    elif k < d and prev_k >= prev_d:
        kdj_cross = "死叉"
    else:
        kdj_cross = "无交叉"
    
    # RSI分析
    rsi6 = latest.get('rsi_bfq_6') or 50
    rsi12 = latest.get('rsi_bfq_12') or 50
    rsi24 = latest.get('rsi_bfq_24') or 50
    
    if rsi6 > 70:
        rsi_status = "超买"
        rsi_score = 30
    elif rsi6 < 30:
        rsi_status = "超卖"
        rsi_score = 70
    else:
        rsi_status = "中性"
        rsi_score = 50
    
    # MTM/ROC分析
    mtm = latest.get('mtm_bfq') or 0
    roc = latest.get('roc_bfq') or 0
    
    if mtm > 0 and roc > 0:
        momentum_direction = "动量向上"
        momentum_score = 65
    elif mtm < 0 and roc < 0:
        momentum_direction = "动量向下"
        momentum_score = 35
    else:
        momentum_direction = "动量中性"
        momentum_score = 50
    
    # 综合评分
    overall_score = int(kdj_score * 0.35 + rsi_score * 0.35 + momentum_score * 0.3)
    
    if kdj_status == "超买" and rsi_status == "超买":
        overall_status = "严重超买"
    elif kdj_status == "超卖" and rsi_status == "超卖":
        overall_status = "严重超卖"
    elif kdj_status == "超买" or rsi_status == "超买":
        overall_status = "偏超买"
    elif kdj_status == "超卖" or rsi_status == "超卖":
        overall_status = "偏超卖"
    else:
        overall_status = "中性"
    
    return {
        "ts_code": ts_code,
        "trade_date": latest.get('trade_date'),
        "overall_status": overall_status,
        "overall_score": overall_score,
        "momentum_direction": momentum_direction,
        "kdj_analysis": {
            "k": k, "d": d, "j": j,
            "status": kdj_status,
            "cross": kdj_cross,
            "score": kdj_score
        },
        "rsi_analysis": {
            "rsi6": rsi6, "rsi12": rsi12, "rsi24": rsi24,
            "status": rsi_status,
            "score": rsi_score
        },
        "mtm_roc_analysis": {
            "mtm": mtm, "roc": roc,
            "direction": momentum_direction,
            "score": momentum_score
        }
    }


def analyze_volatility(ts_code: str) -> Dict[str, Any]:
    """分析指数波动率（ATR + 布林带 + 通道）。

    Args:
        ts_code: 指数代码

    Returns:
        波动分析结果，包含波动水平、支撑压力位
    """
    query = f"""
    SELECT 
        ts_code, trade_date, close,
        atr_bfq,
        boll_upper_bfq, boll_mid_bfq, boll_lower_bfq,
        ktn_upper_bfq, ktn_mid_bfq, ktn_down_bfq,
        taq_up_bfq, taq_mid_bfq, taq_down_bfq
    FROM ods_idx_factor_pro
    WHERE ts_code = '{ts_code}'
    ORDER BY trade_date DESC
    LIMIT 20
    """
    result = _execute_query(query)
    if not result:
        return {"error": f"未找到指数 {ts_code} 的波动数据"}
    
    latest = result[0]
    close = latest.get('close') or 0
    
    # ATR分析
    atr = latest.get('atr_bfq') or 0
    atr_values = [r.get('atr_bfq') or 0 for r in result]
    atr_avg = sum(atr_values) / len(atr_values) if atr_values else 0
    
    if atr > atr_avg * 1.2:
        atr_status = "高波动"
        volatility_score = 30  # 高波动风险高
    elif atr < atr_avg * 0.8:
        atr_status = "低波动"
        volatility_score = 70  # 低波动可能变盘
    else:
        atr_status = "正常波动"
        volatility_score = 50
    
    # 布林带分析
    boll_upper = latest.get('boll_upper_bfq') or 0
    boll_mid = latest.get('boll_mid_bfq') or 0
    boll_lower = latest.get('boll_lower_bfq') or 0
    
    if boll_upper and boll_lower:
        boll_width = (boll_upper - boll_lower) / boll_mid * 100 if boll_mid else 0
        
        if close >= boll_upper:
            boll_position = "触及上轨"
            boll_signal = "短期压力"
        elif close <= boll_lower:
            boll_position = "触及下轨"
            boll_signal = "短期支撑"
        elif close > boll_mid:
            boll_position = "中轨上方"
            boll_signal = "偏强"
        else:
            boll_position = "中轨下方"
            boll_signal = "偏弱"
    else:
        boll_width = 0
        boll_position = "数据不足"
        boll_signal = "无法判断"
    
    # 通道突破分析
    taq_up = latest.get('taq_up_bfq') or 0
    taq_down = latest.get('taq_down_bfq') or 0
    
    if close >= taq_up and taq_up > 0:
        channel_status = "突破上轨"
        channel_signal = "趋势突破买入信号"
    elif close <= taq_down and taq_down > 0:
        channel_status = "跌破下轨"
        channel_signal = "趋势突破卖出信号"
    else:
        channel_status = "通道内运行"
        channel_signal = "无明显突破"
    
    return {
        "ts_code": ts_code,
        "trade_date": latest.get('trade_date'),
        "close": close,
        "volatility_score": volatility_score,
        "atr_analysis": {
            "atr": atr,
            "atr_avg_20d": round(atr_avg, 2),
            "status": atr_status
        },
        "boll_analysis": {
            "upper": boll_upper,
            "mid": boll_mid,
            "lower": boll_lower,
            "width_pct": round(boll_width, 2),
            "position": boll_position,
            "signal": boll_signal
        },
        "channel_analysis": {
            "taq_upper": taq_up,
            "taq_lower": taq_down,
            "status": channel_status,
            "signal": channel_signal
        }
    }


def analyze_volume(ts_code: str) -> Dict[str, Any]:
    """分析指数量能（OBV + VR + MFI）。

    Args:
        ts_code: 指数代码

    Returns:
        量能分析结果，包含量价配合、资金流向
    """
    query = f"""
    SELECT 
        ts_code, trade_date, close, vol,
        obv_bfq, vr_bfq, mfi_bfq
    FROM ods_idx_factor_pro
    WHERE ts_code = '{ts_code}'
    ORDER BY trade_date DESC
    LIMIT 10
    """
    result = _execute_query(query)
    if not result:
        return {"error": f"未找到指数 {ts_code} 的量能数据"}
    
    latest = result[0]
    prev = result[1] if len(result) > 1 else latest
    
    # OBV分析
    obv = latest.get('obv_bfq') or 0
    prev_obv = prev.get('obv_bfq') or 0
    close = latest.get('close') or 0
    prev_close = prev.get('close') or 0
    
    obv_change = obv - prev_obv
    price_change = close - prev_close
    
    if obv_change > 0 and price_change > 0:
        obv_status = "量价齐升"
        obv_signal = "趋势健康"
        obv_score = 70
    elif obv_change < 0 and price_change > 0:
        obv_status = "价升量缩"
        obv_signal = "警惕背离"
        obv_score = 40
    elif obv_change > 0 and price_change < 0:
        obv_status = "价跌量升"
        obv_signal = "可能筑底"
        obv_score = 55
    else:
        obv_status = "量价齐跌"
        obv_signal = "趋势延续"
        obv_score = 30
    
    # VR分析
    vr = latest.get('vr_bfq') or 100
    
    if vr > 450:
        vr_status = "成交过热"
        vr_signal = "注意风险"
        vr_score = 25
    elif vr < 70:
        vr_status = "成交低迷"
        vr_signal = "关注机会"
        vr_score = 60
    elif vr > 150:
        vr_status = "成交活跃"
        vr_signal = "市场活跃"
        vr_score = 55
    else:
        vr_status = "成交正常"
        vr_signal = "正常水平"
        vr_score = 50
    
    # MFI分析
    mfi = latest.get('mfi_bfq') or 50
    
    if mfi > 80:
        mfi_status = "资金超买"
        mfi_signal = "资金流入过度"
        mfi_score = 30
    elif mfi < 20:
        mfi_status = "资金超卖"
        mfi_signal = "资金流出过度"
        mfi_score = 70
    elif mfi > 50:
        mfi_status = "资金流入"
        mfi_signal = "资金净流入"
        mfi_score = 60
    else:
        mfi_status = "资金流出"
        mfi_signal = "资金净流出"
        mfi_score = 40
    
    # 综合评分
    volume_score = int(obv_score * 0.4 + vr_score * 0.3 + mfi_score * 0.3)
    
    return {
        "ts_code": ts_code,
        "trade_date": latest.get('trade_date'),
        "volume_score": volume_score,
        "obv_analysis": {
            "obv": obv,
            "change": obv_change,
            "status": obv_status,
            "signal": obv_signal,
            "score": obv_score
        },
        "vr_analysis": {
            "vr": vr,
            "status": vr_status,
            "signal": vr_signal,
            "score": vr_score
        },
        "mfi_analysis": {
            "mfi": mfi,
            "status": mfi_status,
            "signal": mfi_signal,
            "score": mfi_score
        }
    }


def analyze_sentiment(ts_code: str) -> Dict[str, Any]:
    """分析市场情绪（PSY + BRAR + CCI + WR）。

    Args:
        ts_code: 指数代码

    Returns:
        情绪分析结果，包含市场情绪状态
    """
    query = f"""
    SELECT 
        ts_code, trade_date,
        psy_bfq, brar_ar_bfq, brar_br_bfq,
        cci_bfq, wr_bfq, wr1_bfq
    FROM ods_idx_factor_pro
    WHERE ts_code = '{ts_code}'
    ORDER BY trade_date DESC
    LIMIT 3
    """
    result = _execute_query(query)
    if not result:
        return {"error": f"未找到指数 {ts_code} 的情绪数据"}
    
    latest = result[0]
    
    # PSY分析
    psy = latest.get('psy_bfq') or 50
    
    if psy > 75:
        psy_status = "市场过热"
        psy_score = 25
    elif psy < 25:
        psy_status = "市场过冷"
        psy_score = 75
    else:
        psy_status = "情绪中性"
        psy_score = 50
    
    # BRAR分析
    ar = latest.get('brar_ar_bfq') or 100
    br = latest.get('brar_br_bfq') or 100
    
    if ar > 180:
        ar_status = "人气过热"
        ar_score = 30
    elif ar < 50:
        ar_status = "人气低迷"
        ar_score = 70
    else:
        ar_status = "人气正常"
        ar_score = 50
    
    if br > 400:
        br_status = "意愿过强"
        br_score = 25
    elif br < 40:
        br_status = "意愿低迷"
        br_score = 75
    else:
        br_status = "意愿正常"
        br_score = 50
    
    # CCI分析
    cci = latest.get('cci_bfq') or 0
    
    if cci > 100:
        cci_status = "超买"
        cci_score = 30
    elif cci < -100:
        cci_status = "超卖"
        cci_score = 70
    else:
        cci_status = "正常区间"
        cci_score = 50
    
    # WR分析（注意WR是反向指标）
    wr = latest.get('wr_bfq') or 50
    
    if wr < 20:
        wr_status = "超买"
        wr_score = 30
    elif wr > 80:
        wr_status = "超卖"
        wr_score = 70
    else:
        wr_status = "正常"
        wr_score = 50
    
    # 综合评分
    sentiment_score = int(psy_score * 0.3 + ar_score * 0.2 + br_score * 0.2 + cci_score * 0.15 + wr_score * 0.15)
    
    if sentiment_score >= 65:
        overall_sentiment = "偏悲观（反向机会）"
    elif sentiment_score <= 35:
        overall_sentiment = "偏乐观（注意风险）"
    else:
        overall_sentiment = "情绪中性"
    
    return {
        "ts_code": ts_code,
        "trade_date": latest.get('trade_date'),
        "overall_sentiment": overall_sentiment,
        "sentiment_score": sentiment_score,
        "psy_analysis": {
            "psy": psy,
            "status": psy_status,
            "score": psy_score
        },
        "brar_analysis": {
            "ar": ar,
            "br": br,
            "ar_status": ar_status,
            "br_status": br_status
        },
        "cci_analysis": {
            "cci": cci,
            "status": cci_status,
            "score": cci_score
        },
        "wr_analysis": {
            "wr": wr,
            "status": wr_status,
            "score": wr_score
        }
    }


def analyze_concentration(ts_code: str) -> Dict[str, Any]:
    """分析指数集中度风险（CR10 + HHI）。

    Args:
        ts_code: 指数代码

    Returns:
        集中度分析结果，包含CR10、HHI指数、风险等级
    """
    # 获取最新权重日期
    date_query = f"""
    SELECT max(trade_date) as latest_date
    FROM ods_index_weight
    WHERE index_code = '{ts_code}'
    """
    date_result = _execute_query(date_query)
    trade_date = None
    if date_result and date_result[0].get('latest_date'):
        latest = date_result[0]['latest_date']
        if hasattr(latest, 'strftime'):
            trade_date = latest.strftime('%Y%m%d')
        elif isinstance(latest, str) and latest not in ('', '1970-01-01', '1970-01-01 00:00:00'):
            trade_date = latest.replace('-', '')
    
    if not trade_date:
        return {"error": f"未找到指数 {ts_code} 的成分股数据"}
    
    query = f"""
    SELECT 
        index_code,
        con_code,
        weight
    FROM ods_index_weight
    WHERE index_code = '{ts_code}'
    AND trade_date = '{trade_date}'
    ORDER BY weight DESC
    """
    result = _execute_query(query)
    if not result:
        return {"error": f"未找到指数 {ts_code} 的成分股权重数据"}
    
    # 计算CR10（前10大成分股权重占比）
    top10_weight = sum(r.get('weight', 0) or 0 for r in result[:10])
    
    # 计算HHI指数（赫芬达尔指数）
    weights = [r.get('weight', 0) or 0 for r in result]
    hhi = sum(w * w for w in weights) * 100  # 乘以100转换为常用单位
    
    # 风险等级判断
    if top10_weight < 30 and hhi < 500:
        risk_level = "低"
        risk_description = "分散度好，集中度风险低"
        concentration_score = 80
    elif top10_weight > 50 or hhi > 1000:
        risk_level = "高"
        risk_description = "高度集中，需关注头部成分股波动"
        concentration_score = 30
    else:
        risk_level = "中"
        risk_description = "适度集中，风险可控"
        concentration_score = 55
    
    return {
        "ts_code": ts_code,
        "trade_date": trade_date,
        "constituent_count": len(result),
        "cr10": round(top10_weight, 2),
        "hhi": round(hhi, 2),
        "risk_level": risk_level,
        "risk_description": risk_description,
        "concentration_score": concentration_score,
        "top10_constituents": result[:10]
    }


def get_comprehensive_analysis(ts_code: str) -> Dict[str, Any]:
    """生成指数综合量化分析报告。

    Args:
        ts_code: 指数代码，如 000300.SH

    Returns:
        综合分析报告，包含多空评分(0-100)和操作建议
    """
    # 获取基础信息
    index_info = get_index_info(ts_code)
    if "error" in index_info:
        return index_info
    
    # 获取各维度分析
    trend = analyze_trend(ts_code)
    momentum = analyze_momentum(ts_code)
    volatility = analyze_volatility(ts_code)
    volume = analyze_volume(ts_code)
    sentiment = analyze_sentiment(ts_code)
    concentration = analyze_concentration(ts_code)
    
    # 检查错误
    for analysis in [trend, momentum, volatility, volume, sentiment]:
        if "error" in analysis:
            return {"error": f"分析数据不完整: {analysis.get('error')}"}
    
    # 计算综合评分（加权平均）
    # 趋势30% + 动量25% + 波动20% + 量能15% + 情绪10%
    trend_score = trend.get('trend_score', 50)
    momentum_score = momentum.get('overall_score', 50)
    volatility_score = volatility.get('volatility_score', 50)
    volume_score = volume.get('volume_score', 50)
    sentiment_score = sentiment.get('sentiment_score', 50)
    
    overall_score = int(
        trend_score * 0.30 +
        momentum_score * 0.25 +
        volatility_score * 0.20 +
        volume_score * 0.15 +
        sentiment_score * 0.10
    )
    
    # 生成操作建议
    if overall_score >= 70:
        suggestion = "积极"
        suggestion_detail = "多项指标看多，可考虑适当增加仓位"
    elif overall_score >= 55:
        suggestion = "谨慎乐观"
        suggestion_detail = "整体偏多，但需关注风险指标变化"
    elif overall_score >= 45:
        suggestion = "观望"
        suggestion_detail = "多空信号交织，建议观望等待明确方向"
    elif overall_score >= 30:
        suggestion = "谨慎"
        suggestion_detail = "整体偏空，建议控制仓位"
    else:
        suggestion = "减仓"
        suggestion_detail = "多项指标看空，建议降低风险敞口"
    
    # 识别主要风险
    risks = []
    if momentum.get('overall_status') in ['严重超买', '偏超买']:
        risks.append("短期超买，注意回调风险")
    if volatility.get('atr_analysis', {}).get('status') == '高波动':
        risks.append("波动率偏高，注意仓位控制")
    if volume.get('obv_analysis', {}).get('status') == '价升量缩':
        risks.append("量价背离，趋势可能不持续")
    if sentiment.get('psy_analysis', {}).get('status') == '市场过热':
        risks.append("市场情绪过热，警惕回调")
    if concentration.get('risk_level') == '高':
        risks.append(f"集中度风险高，CR10={concentration.get('cr10')}%")
    
    return {
        "ts_code": ts_code,
        "index_name": index_info.get('name'),
        "trade_date": trend.get('trade_date'),
        "overall_score": overall_score,
        "suggestion": suggestion,
        "suggestion_detail": suggestion_detail,
        "risks": risks if risks else ["暂无明显风险信号"],
        "dimension_scores": {
            "trend": {"score": trend_score, "weight": "30%", "direction": trend.get('trend_direction')},
            "momentum": {"score": momentum_score, "weight": "25%", "status": momentum.get('overall_status')},
            "volatility": {"score": volatility_score, "weight": "20%", "status": volatility.get('atr_analysis', {}).get('status')},
            "volume": {"score": volume_score, "weight": "15%", "status": volume.get('obv_analysis', {}).get('status')},
            "sentiment": {"score": sentiment_score, "weight": "10%", "status": sentiment.get('overall_sentiment')}
        },
        "concentration": {
            "cr10": concentration.get('cr10'),
            "hhi": concentration.get('hhi'),
            "risk_level": concentration.get('risk_level')
        },
        "disclaimer": "以上分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。"
    }
