"""Index analysis tool functions for Index Agent.

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


def _get_simple_analysis(ts_code: str, index_info: Dict[str, Any]) -> Dict[str, Any]:
    """返回简化版分析（当技术指标数据不可用时）。"""
    # 获取最近行情
    query = f"""
    SELECT ts_code, trade_date, close, pct_chg, vol, amount
    FROM ods_idx_factor_pro
    WHERE ts_code = '{ts_code}'
    ORDER BY trade_date DESC
    LIMIT 20
    """
    result = _execute_query(query)
    if not result:
        return {"error": f"未找到指数 {ts_code} 的行情数据"}
    
    latest = result[0]
    
    # 计算简单统计
    closes = [r.get('close', 0) for r in result if r.get('close')]
    pct_chgs = [r.get('pct_chg', 0) for r in result if r.get('pct_chg') is not None]
    
    avg_return = sum(pct_chgs) / len(pct_chgs) if pct_chgs else 0
    period_return = ((closes[0] / closes[-1]) - 1) * 100 if closes and closes[-1] else 0
    
    # 简单评分：基于近期涨跌
    if avg_return > 0.5:
        score = 70
        suggestion = "偏多"
    elif avg_return > 0:
        score = 55
        suggestion = "中性偏多"
    elif avg_return > -0.5:
        score = 45
        suggestion = "中性偏空"
    else:
        score = 30
        suggestion = "偏空"
    
    return {
        "ts_code": ts_code,
        "index_name": index_info.get('name'),
        "trade_date": latest.get('trade_date'),
        "overall_score": score,
        "suggestion": suggestion,
        "suggestion_detail": f"基于近20日行情分析，平均日涨跌{avg_return:.2f}%，期间收益{period_return:.2f}%",
        "latest_close": latest.get('close'),
        "latest_pct_chg": latest.get('pct_chg'),
        "period_return": round(period_return, 2),
        "avg_daily_return": round(avg_return, 3),
        "data_note": "技术指标数据暂不可用，仅基于基础行情分析",
        "risks": []
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
    
    # 安全调用分析函数
    def safe_call(func, ts_code):
        try:
            return func(ts_code)
        except Exception as e:
            logger.warning(f"{func.__name__} failed for {ts_code}: {e}")
            return {"error": str(e)}
    
    # 获取各维度分析（允许部分失败）
    trend = safe_call(analyze_trend, ts_code)
    momentum = safe_call(analyze_momentum, ts_code)
    volatility = safe_call(analyze_volatility, ts_code)
    volume = safe_call(analyze_volume, ts_code)
    sentiment = safe_call(analyze_sentiment, ts_code)
    concentration = safe_call(analyze_concentration, ts_code)
    
    # 如果所有技术指标分析都失败，返回简化版分析
    all_failed = all("error" in a for a in [trend, momentum, volatility, volume, sentiment])
    if all_failed:
        # 使用基础行情数据返回简化分析
        return _get_simple_analysis(ts_code, index_info)
    
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

# ============================================================
# 扩展指数数据工具 - 周线/月线/行业/概念/国际指数
# ============================================================

def get_index_weekly_data(ts_code: str, days: int = 52) -> Dict[str, Any]:
    """获取指数周线数据（默认最近52周）。

    Args:
        ts_code: 指数代码，如 000300.SH
        days: 获取最近多少周的数据，默认52周（约1年）

    Returns:
        包含周线行情数据的字典
    """
    query = f"""
    SELECT 
        ts_code, trade_date, open, high, low, close,
        pre_close, change, pct_chg, vol, amount
    FROM ods_index_weekly
    WHERE ts_code = '{ts_code}'
    ORDER BY trade_date DESC
    LIMIT {days}
    """
    result = _execute_query(query)
    if not result:
        return {"error": f"未找到指数 {ts_code} 的周线数据"}
    
    result.reverse()
    
    # 计算周线统计
    closes = [r.get('close', 0) for r in result if r.get('close')]
    pct_chgs = [r.get('pct_chg', 0) for r in result if r.get('pct_chg') is not None]
    
    return {
        "ts_code": ts_code,
        "weeks": len(result),
        "data": result[-10:],  # 返回最近10周
        "stats": {
            "latest_close": closes[-1] if closes else None,
            "max_close": max(closes) if closes else None,
            "min_close": min(closes) if closes else None,
            "avg_weekly_return": round(sum(pct_chgs) / len(pct_chgs), 3) if pct_chgs else None,
            "total_weeks": len(result)
        }
    }


def get_index_monthly_data(ts_code: str, months: int = 24) -> Dict[str, Any]:
    """获取指数月线数据（默认最近24个月）。

    Args:
        ts_code: 指数代码，如 000300.SH
        months: 获取最近多少月的数据，默认24个月（2年）

    Returns:
        包含月线行情数据的字典
    """
    query = f"""
    SELECT 
        ts_code, trade_date, open, high, low, close,
        pre_close, change, pct_chg, vol, amount
    FROM ods_index_monthly
    WHERE ts_code = '{ts_code}'
    ORDER BY trade_date DESC
    LIMIT {months}
    """
    result = _execute_query(query)
    if not result:
        return {"error": f"未找到指数 {ts_code} 的月线数据"}
    
    result.reverse()
    
    closes = [r.get('close', 0) for r in result if r.get('close')]
    pct_chgs = [r.get('pct_chg', 0) for r in result if r.get('pct_chg') is not None]
    
    return {
        "ts_code": ts_code,
        "months": len(result),
        "data": result[-12:],  # 返回最近12个月
        "stats": {
            "latest_close": closes[-1] if closes else None,
            "max_close": max(closes) if closes else None,
            "min_close": min(closes) if closes else None,
            "avg_monthly_return": round(sum(pct_chgs) / len(pct_chgs), 3) if pct_chgs else None,
            "ytd_return": round(sum(pct_chgs[-12:]), 2) if len(pct_chgs) >= 12 else None,
            "total_months": len(result)
        }
    }


def get_sw_industry_daily(trade_date: str = None, ts_code: str = None) -> Dict[str, Any]:
    """获取申万行业指数日线数据。

    Args:
        trade_date: 交易日期（YYYYMMDD），不传则获取最新日期
        ts_code: 行业指数代码（可选），不传则返回所有行业

    Returns:
        包含申万行业指数数据的字典
    """
    if not trade_date:
        date_query = "SELECT max(trade_date) as latest FROM ods_sw_daily"
        date_result = _execute_query(date_query)
        if date_result and date_result[0].get('latest'):
            latest = date_result[0]['latest']
            if hasattr(latest, 'strftime'):
                trade_date = latest.strftime('%Y%m%d')
            else:
                trade_date = str(latest).replace('-', '')
        else:
            return {"error": "未找到申万行业指数数据"}
    
    where_clause = f"trade_date = '{trade_date}'"
    if ts_code:
        where_clause += f" AND ts_code = '{ts_code}'"
    
    query = f"""
    SELECT 
        ts_code, trade_date, name, open, high, low, close,
        change, pct_change, vol, amount, pe, pb, float_mv, total_mv
    FROM ods_sw_daily
    WHERE {where_clause}
    ORDER BY pct_change DESC
    """
    result = _execute_query(query)
    if not result:
        return {"error": f"未找到申万行业指数数据"}
    
    # 计算涨跌统计
    up_count = sum(1 for r in result if (r.get('pct_change') or 0) > 0)
    down_count = sum(1 for r in result if (r.get('pct_change') or 0) < 0)
    
    return {
        "trade_date": trade_date,
        "total_count": len(result),
        "up_count": up_count,
        "down_count": down_count,
        "flat_count": len(result) - up_count - down_count,
        "top5_gainers": result[:5],
        "top5_losers": result[-5:][::-1] if len(result) >= 5 else result[::-1],
        "all_industries": result if ts_code else None
    }


def get_ci_industry_daily(trade_date: str = None, ts_code: str = None) -> Dict[str, Any]:
    """获取中信行业指数日线数据。

    Args:
        trade_date: 交易日期（YYYYMMDD），不传则获取最新日期
        ts_code: 行业指数代码（可选），不传则返回所有行业

    Returns:
        包含中信行业指数数据的字典
    """
    if not trade_date:
        date_query = "SELECT max(trade_date) as latest FROM ods_ci_daily"
        date_result = _execute_query(date_query)
        if date_result and date_result[0].get('latest'):
            latest = date_result[0]['latest']
            if hasattr(latest, 'strftime'):
                trade_date = latest.strftime('%Y%m%d')
            else:
                trade_date = str(latest).replace('-', '')
        else:
            return {"error": "未找到中信行业指数数据"}
    
    where_clause = f"trade_date = '{trade_date}'"
    if ts_code:
        where_clause += f" AND ts_code = '{ts_code}'"
    
    query = f"""
    SELECT 
        ts_code, trade_date, name, open, high, low, close,
        change, pct_change, vol, amount
    FROM ods_ci_daily
    WHERE {where_clause}
    ORDER BY pct_change DESC
    """
    result = _execute_query(query)
    if not result:
        return {"error": f"未找到中信行业指数数据"}
    
    up_count = sum(1 for r in result if (r.get('pct_change') or 0) > 0)
    down_count = sum(1 for r in result if (r.get('pct_change') or 0) < 0)
    
    return {
        "trade_date": trade_date,
        "total_count": len(result),
        "up_count": up_count,
        "down_count": down_count,
        "flat_count": len(result) - up_count - down_count,
        "top5_gainers": result[:5],
        "top5_losers": result[-5:][::-1] if len(result) >= 5 else result[::-1]
    }


def search_ths_index(keyword: str = None, index_type: str = None) -> Dict[str, Any]:
    """搜索同花顺概念/行业指数。

    Args:
        keyword: 搜索关键词（模糊匹配名称）
        index_type: 指数类型：N-概念, I-行业, R-地域, S-特色, ST-风格, TH-主题, BB-宽基

    Returns:
        匹配的同花顺指数列表
    """
    conditions = ["1=1"]
    if keyword:
        conditions.append(f"name LIKE '%{keyword}%'")
    if index_type:
        conditions.append(f"type = '{index_type}'")
    
    where_clause = " AND ".join(conditions)
    
    query = f"""
    SELECT ts_code, name, count, exchange, list_date, type
    FROM ods_ths_index
    WHERE {where_clause}
    ORDER BY count DESC NULLS LAST
    LIMIT 50
    """
    result = _execute_query(query)
    if not result:
        return {"error": "未找到匹配的同花顺指数"}
    
    # 按类型分组统计
    type_stats = {}
    for r in result:
        t = r.get('type', 'unknown')
        type_stats[t] = type_stats.get(t, 0) + 1
    
    return {
        "total_count": len(result),
        "type_stats": type_stats,
        "indices": result
    }


def get_ths_daily(ts_code: str, days: int = 20) -> Dict[str, Any]:
    """获取同花顺指数日线数据。

    Args:
        ts_code: 同花顺指数代码，如 885001.TI
        days: 获取最近多少天数据，默认20天

    Returns:
        包含同花顺指数日线数据的字典
    """
    query = f"""
    SELECT 
        ts_code, trade_date, open, high, low, close,
        pre_close, avg_price, change, pct_change,
        vol, turnover_rate, total_mv, float_mv
    FROM ods_ths_daily
    WHERE ts_code = '{ts_code}'
    ORDER BY trade_date DESC
    LIMIT {days}
    """
    result = _execute_query(query)
    if not result:
        return {"error": f"未找到同花顺指数 {ts_code} 的日线数据"}
    
    result.reverse()
    
    # 获取指数基本信息
    info_query = f"""
    SELECT ts_code, name, count, exchange, type
    FROM ods_ths_index
    WHERE ts_code = '{ts_code}'
    """
    info_result = _execute_query(info_query)
    index_info = info_result[0] if info_result else {}
    
    closes = [r.get('close', 0) for r in result if r.get('close')]
    pct_chgs = [r.get('pct_change', 0) for r in result if r.get('pct_change') is not None]
    
    return {
        "ts_code": ts_code,
        "index_name": index_info.get('name'),
        "index_type": index_info.get('type'),
        "constituent_count": index_info.get('count'),
        "days": len(result),
        "data": result[-10:],
        "stats": {
            "latest_close": closes[-1] if closes else None,
            "period_return": round(((closes[-1] / closes[0]) - 1) * 100, 2) if closes and closes[0] else None,
            "avg_daily_return": round(sum(pct_chgs) / len(pct_chgs), 3) if pct_chgs else None,
            "max_close": max(closes) if closes else None,
            "min_close": min(closes) if closes else None
        }
    }


def get_ths_members(ts_code: str) -> Dict[str, Any]:
    """获取同花顺概念/行业成分股。

    Args:
        ts_code: 同花顺指数代码

    Returns:
        包含成分股列表的字典
    """
    # 获取指数信息
    info_query = f"""
    SELECT ts_code, name, count, type
    FROM ods_ths_index
    WHERE ts_code = '{ts_code}'
    """
    info_result = _execute_query(info_query)
    index_info = info_result[0] if info_result else {}
    
    # 获取成分股
    query = f"""
    SELECT ts_code, code, name, weight, in_date, out_date, is_new
    FROM ods_ths_member
    WHERE ts_code = '{ts_code}'
    ORDER BY weight DESC NULLS LAST
    """
    result = _execute_query(query)
    if not result:
        return {"error": f"未找到同花顺指数 {ts_code} 的成分股数据"}
    
    return {
        "ts_code": ts_code,
        "index_name": index_info.get('name'),
        "index_type": index_info.get('type'),
        "constituent_count": len(result),
        "constituents": result[:30],  # 返回前30个
        "new_additions": [r for r in result if r.get('is_new') == 'Y'][:10]
    }


def get_global_index(ts_code: str = None, trade_date: str = None, days: int = 20) -> Dict[str, Any]:
    """获取国际指数数据。

    Args:
        ts_code: 国际指数代码（可选），如 SPX（标普500）、DJI（道琼斯）、IXIC（纳斯达克）
        trade_date: 交易日期（可选）
        days: 获取最近多少天数据，默认20天

    Returns:
        国际指数数据
    """
    if ts_code:
        query = f"""
        SELECT ts_code, trade_date, open, high, low, close,
               pre_close, change, pct_chg, swing, vol, amount
        FROM ods_index_global
        WHERE ts_code = '{ts_code}'
        ORDER BY trade_date DESC
        LIMIT {days}
        """
        result = _execute_query(query)
        if not result:
            return {"error": f"未找到国际指数 {ts_code} 的数据"}
        
        result.reverse()
        closes = [r.get('close', 0) for r in result if r.get('close')]
        
        return {
            "ts_code": ts_code,
            "days": len(result),
            "data": result[-10:],
            "stats": {
                "latest_close": closes[-1] if closes else None,
                "period_return": round(((closes[-1] / closes[0]) - 1) * 100, 2) if closes and closes[0] else None,
            }
        }
    
    elif trade_date:
        query = f"""
        SELECT ts_code, trade_date, open, high, low, close,
               pre_close, change, pct_chg, swing
        FROM ods_index_global
        WHERE trade_date = '{trade_date}'
        ORDER BY ts_code
        """
        result = _execute_query(query)
        if not result:
            return {"error": f"未找到 {trade_date} 的国际指数数据"}
        
        return {
            "trade_date": trade_date,
            "indices": result
        }
    
    else:
        # 获取最新日期的所有国际指数
        date_query = "SELECT max(trade_date) as latest FROM ods_index_global"
        date_result = _execute_query(date_query)
        if date_result and date_result[0].get('latest'):
            latest = date_result[0]['latest']
            if hasattr(latest, 'strftime'):
                trade_date = latest.strftime('%Y%m%d')
            else:
                trade_date = str(latest).replace('-', '')
            return get_global_index(trade_date=trade_date)
        return {"error": "未找到国际指数数据"}


def get_market_daily_stats(trade_date: str = None) -> Dict[str, Any]:
    """获取每日全市场统计数据。

    Args:
        trade_date: 交易日期（YYYYMMDD），不传则获取最新日期

    Returns:
        全市场统计数据（上市公司数、总市值、成交额等）
    """
    if not trade_date:
        date_query = "SELECT max(trade_date) as latest FROM ods_daily_info"
        date_result = _execute_query(date_query)
        if date_result and date_result[0].get('latest'):
            latest = date_result[0]['latest']
            if hasattr(latest, 'strftime'):
                trade_date = latest.strftime('%Y%m%d')
            else:
                trade_date = str(latest).replace('-', '')
        else:
            return {"error": "未找到每日市场统计数据"}
    
    query = f"""
    SELECT 
        trade_date, ts_code, ts_name, com_count, 
        total_share, float_share, total_mv, float_mv,
        amount, vol, trans_count, pe, tr, exchange
    FROM ods_daily_info
    WHERE trade_date = '{trade_date}'
    ORDER BY ts_code
    """
    result = _execute_query(query)
    if not result:
        return {"error": f"未找到 {trade_date} 的市场统计数据"}
    
    # 汇总统计
    total_companies = sum(r.get('com_count', 0) or 0 for r in result)
    total_mv = sum(r.get('total_mv', 0) or 0 for r in result)
    total_amount = sum(r.get('amount', 0) or 0 for r in result)
    
    return {
        "trade_date": trade_date,
        "summary": {
            "total_companies": total_companies,
            "total_mv_billion": round(total_mv / 100000000, 2) if total_mv else None,
            "total_amount_billion": round(total_amount / 100000000, 2) if total_amount else None
        },
        "by_market": result
    }


def get_industry_classification(level: str = "L1", src: str = "SW2021") -> Dict[str, Any]:
    """获取行业分类信息。

    Args:
        level: 分类级别 L1(一级)/L2(二级)/L3(三级)
        src: 分类来源 SW2021(申万2021)/SW(申万)/MSCI

    Returns:
        行业分类信息
    """
    query = f"""
    SELECT 
        index_code, industry_name, level, industry_code,
        is_pub, parent_code, src
    FROM dim_index_classify
    WHERE level = '{level}' AND src = '{src}'
    ORDER BY index_code
    """
    result = _execute_query(query)
    if not result:
        return {"error": f"未找到 {src} {level} 级行业分类数据"}
    
    return {
        "source": src,
        "level": level,
        "total_count": len(result),
        "classifications": result
    }


def compare_index_performance(ts_codes: List[str], days: int = 20) -> Dict[str, Any]:
    """比较多个指数的表现。

    Args:
        ts_codes: 指数代码列表，如 ['000300.SH', '000905.SH', '399006.SZ']
        days: 比较最近多少天，默认20天

    Returns:
        指数表现对比
    """
    if not ts_codes:
        return {"error": "请提供至少一个指数代码"}
    
    codes_str = "','".join(ts_codes)
    query = f"""
    SELECT ts_code, trade_date, close, pct_chg
    FROM ods_idx_factor_pro
    WHERE ts_code IN ('{codes_str}')
    ORDER BY trade_date DESC
    """
    result = _execute_query(query)
    if not result:
        return {"error": "未找到指定指数的数据"}
    
    # 按指数分组处理
    index_data = {}
    for r in result:
        code = r.get('ts_code')
        if code not in index_data:
            index_data[code] = []
        if len(index_data[code]) < days:
            index_data[code].append(r)
    
    # 计算各指数统计
    performance = []
    for code in ts_codes:
        data = index_data.get(code, [])
        if not data:
            performance.append({"ts_code": code, "error": "无数据"})
            continue
        
        data.reverse()
        closes = [d.get('close', 0) for d in data if d.get('close')]
        pct_chgs = [d.get('pct_chg', 0) for d in data if d.get('pct_chg') is not None]
        
        performance.append({
            "ts_code": code,
            "latest_close": closes[-1] if closes else None,
            "period_return": round(((closes[-1] / closes[0]) - 1) * 100, 2) if closes and closes[0] else None,
            "avg_daily_return": round(sum(pct_chgs) / len(pct_chgs), 3) if pct_chgs else None,
            "max_drawdown": _calc_max_drawdown(closes) if closes else None,
            "volatility": round(_calc_std(pct_chgs), 3) if pct_chgs else None,
            "trading_days": len(data)
        })
    
    # 排序
    performance.sort(key=lambda x: x.get('period_return') or -999, reverse=True)
    
    return {
        "comparison_days": days,
        "performance": performance,
        "best_performer": performance[0] if performance else None,
        "worst_performer": performance[-1] if performance else None
    }


def _calc_max_drawdown(prices: List[float]) -> float:
    """计算最大回撤"""
    if not prices:
        return 0
    max_price = prices[0]
    max_drawdown = 0
    for price in prices:
        if price > max_price:
            max_price = price
        drawdown = (max_price - price) / max_price * 100
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    return round(max_drawdown, 2)


def _calc_std(values: List[float]) -> float:
    """计算标准差"""
    if not values or len(values) < 2:
        return 0
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return variance ** 0.5


def get_industry_ranking(trade_date: str = None, source: str = "sw") -> Dict[str, Any]:
    """获取行业涨跌幅排行。

    Args:
        trade_date: 交易日期（YYYYMMDD），不传则获取最新
        source: 数据来源 sw(申万)/ci(中信)

    Returns:
        行业涨跌幅排行
    """
    if source.lower() == "sw":
        return get_sw_industry_daily(trade_date)
    elif source.lower() == "ci":
        return get_ci_industry_daily(trade_date)
    else:
        return {"error": f"不支持的数据来源: {source}，请使用 sw 或 ci"}