"""Report Agent for financial report analysis using LangGraph/DeepAgents."""

from typing import Dict, Any, List, Callable, Optional, Tuple
import logging
import json
import re

from .base_agent import LangGraphAgent, AgentConfig
from .tools import get_stock_info, get_stock_valuation
from ..services.financial_report_service import FinancialReportService
from ..utils.stock_code import validate_cn_stock_code as _validate_and_normalize_stock_code

logger = logging.getLogger(__name__)


def _fmt_pct(val, fallback='N/A') -> str:
    """Format a percentage value, handling \\N and None."""
    if val is None or val == '\\N' or val == 'None' or val == '':
        return fallback
    try:
        return f"{float(val):.2f}%"
    except (ValueError, TypeError):
        return fallback


def _fmt_num(val, fallback='N/A') -> str:
    """Format a numeric value, handling \\N and None."""
    if val is None or val == '\\N' or val == 'None' or val == '':
        return fallback
    try:
        return f"{float(val):.2f}"
    except (ValueError, TypeError):
        return fallback


def get_comprehensive_financial_analysis(ts_code: str, periods: int = 4) -> Dict[str, Any]:
    """获取全面的财务分析报告。
    
    Args:
        ts_code: 股票代码，如 600519 或 600519.SH
        periods: 分析时间范围，4期=近1年，8期=近2年，默认4期
        
    Returns:
        全面的财务分析报告，包括财务健康度、同业对比、增长分析等。
    """
    # Validate and normalize stock code
    is_valid, ts_code, error_msg = _validate_and_normalize_stock_code(ts_code)
    if not is_valid:
        return {"report": f"❌ {error_msg}"}
    
    try:
        service = FinancialReportService()
        analysis = service.get_comprehensive_analysis(ts_code, periods)
        
        if analysis.get("status") == "error":
            return {"report": f"❌ 获取 {ts_code} 财务数据失败: {analysis.get('error', '未知错误')}"}
        
        summary = analysis.get("summary", {})
        health = analysis.get("health_analysis", {})
        growth = analysis.get("growth_analysis", {})
        
        # Format the analysis report (remove main title, will be shown in UI)
        report = f"""### 📊 财务健康度评分: {health.get('health_score', 0)}/100

### 💪 主要优势
"""
        
        strengths = health.get("strengths", [])
        if strengths:
            for strength in strengths:
                report += f"- {strength}\n"
        else:
            report += "- 暂无明显优势\n"
        
        report += "\n### ⚠️ 关注点\n"
        weaknesses = health.get("weaknesses", [])
        if weaknesses:
            for weakness in weaknesses:
                report += f"- {weakness}\n"
        else:
            report += "- 财务状况良好，无明显风险点\n"
        
        # Profitability metrics
        prof = summary.get("profitability", {})
        report += f"""
### 📈 盈利能力指标
- ROE (净资产收益率): {_fmt_pct(prof.get('roe'))}
- ROA (总资产收益率): {_fmt_pct(prof.get('roa'))}
- 毛利率: {_fmt_pct(prof.get('gross_profit_margin'))}
- 净利率: {_fmt_pct(prof.get('net_profit_margin'))}
"""
        
        # Solvency metrics
        solv = summary.get("solvency", {})
        report += f"""
### 🛡️ 偿债能力指标
- 资产负债率: {_fmt_pct(solv.get('debt_to_assets'))}
- 流动比率: {_fmt_num(solv.get('current_ratio'))}
- 速动比率: {_fmt_num(solv.get('quick_ratio'))}
"""
        
        # Growth analysis
        growth_data = summary.get("growth", {})
        if growth_data:
            report += f"""
### 🚀 成长性分析
- 营收增长率: {_fmt_pct(growth_data.get('revenue_growth'))}
- 净利润增长率: {_fmt_pct(growth_data.get('profit_growth'))}
"""
        
        # Recommendations
        recommendations = health.get("recommendations", [])
        if recommendations:
            report += "\n### 💡 投资建议\n"
            for rec in recommendations:
                report += f"- {rec}\n"
        
        # Format latest period
        latest_period = summary.get('latest_period', 'N/A')
        if hasattr(latest_period, 'strftime'):
            latest_period = latest_period.strftime('%Y-%m-%d')
        elif latest_period and latest_period != 'N/A' and not isinstance(latest_period, str):
            latest_period = str(latest_period)
        
        report += f"\n### 📅 数据说明\n- 分析时间范围: 近{summary.get('periods', 0)//4}年({summary.get('periods', 0)}个季度)\n- 最新财报: {latest_period}"
        
        # Build visualization data for TrendChart component
        financial_periods = analysis.get("financial_data", [])
        viz = None
        if financial_periods and isinstance(financial_periods, list) and len(financial_periods) > 0:
            viz_data = []
            for fp in financial_periods:
                period_str = fp.get("end_date") or fp.get("period", "")
                if hasattr(period_str, 'strftime'):
                    period_str = period_str.strftime('%Y-%m-%d')
                viz_data.append({
                    "period": str(period_str),
                    "revenue": fp.get("revenue"),
                    "net_profit": fp.get("n_income") or fp.get("net_profit"),
                    "net_profit_attr_p": fp.get("n_income_attr_p"),
                    "total_assets": fp.get("total_assets"),
                    "total_liab": fp.get("total_liab"),
                    "roe": fp.get("roe"),
                    "roa": fp.get("roa"),
                    "gross_margin": fp.get("grossprofit_margin"),
                    "net_margin": fp.get("netprofit_margin"),
                })
            if viz_data:
                viz = {
                    "type": "financial_trend",
                    "title": f"{ts_code} 财务趋势分析",
                    "props": {
                        "data": viz_data,
                    }
                }
        
        result = {"report": report}
        if viz:
            result["_visualization"] = viz
        return result
        
    except Exception as e:
        logger.error(f"Error in comprehensive financial analysis for {ts_code}: {e}")
        return {"report": f"❌ 分析 {ts_code} 时发生错误: {str(e)}"}


def get_peer_comparison_analysis(ts_code: str, end_date: str = None) -> str:
    """获取同业对比分析。
    
    Args:
        ts_code: 股票代码
        end_date: 报告期，格式YYYYMMDD，不提供则使用最新季度
        
    Returns:
        同业对比分析报告。
    """
    # Validate and normalize stock code
    is_valid, ts_code, error_msg = _validate_and_normalize_stock_code(ts_code)
    if not is_valid:
        return f"❌ {error_msg}"
    
    try:
        service = FinancialReportService()
        analysis = service.get_peer_comparison_analysis(ts_code, end_date)
        
        if analysis.get("status") == "error":
            return f"❌ 获取 {ts_code} 同业对比数据失败: {analysis.get('error', '未知错误')}"
        
        comparison = analysis.get("comparison", {})
        interpretation = analysis.get("interpretation", {})
        
        if not comparison.get("comparison"):
            return f"📊 {ts_code} 暂无同业对比数据"
        
        report = f"""## {ts_code} 同业对比分析

### 📊 行业地位 (报告期: {analysis.get('end_date', 'N/A')})
对比样本: {comparison.get('peer_count', 0)}家公司

"""
        
        # Key metrics comparison
        metrics_map = {
            "roe": "ROE (净资产收益率)",
            "roa": "ROA (总资产收益率)", 
            "gross_profit_margin": "毛利率",
            "net_profit_margin": "净利率",
            "debt_to_assets": "资产负债率",
            "current_ratio": "流动比率"
        }
        
        for metric, data in comparison.get("comparison", {}).items():
            metric_name = metrics_map.get(metric, metric)
            target_value = data.get("target_value")
            percentile = data.get("percentile_rank", 0)
            industry_median = data.get("industry_median")
            
            interp = interpretation.get(metric, {})
            level = interp.get("level", "未知")
            
            report += f"""### {metric_name}
- 公司数值: {target_value}
- 行业中位数: {industry_median}
- 行业排名: 前{100-percentile:.0f}% ({level})

"""
        
        # Top peers
        peers = comparison.get("peer_companies", [])[:5]
        if peers:
            report += "### 🏆 行业标杆 (ROE排名前5)\n"
            for i, peer in enumerate(peers, 1):
                report += f"{i}. {peer.get('ts_code', 'N/A')} - ROE: {peer.get('roe', 'N/A')}%\n"
        
        return report
        
    except Exception as e:
        logger.error(f"Error in peer comparison for {ts_code}: {e}")
        return f"❌ 同业对比分析 {ts_code} 时发生错误: {str(e)}"


def get_investment_insights(ts_code: str) -> str:
    """获取AI投资洞察和建议。
    
    Args:
        ts_code: 股票代码
        
    Returns:
        结构化的投资洞察报告。
    """
    # Validate and normalize stock code
    is_valid, ts_code, error_msg = _validate_and_normalize_stock_code(ts_code)
    if not is_valid:
        return f"❌ {error_msg}"
    
    try:
        service = FinancialReportService()
        insights = service.get_investment_insights(ts_code)
        
        if insights.get("status") == "error":
            return f"❌ 获取 {ts_code} 投资洞察失败: {insights.get('error', '未知错误')}"
        
        insight_data = insights.get("insights", {})
        
        report = f"""## {ts_code} 投资洞察报告

### 🎯 投资要点
"""
        
        thesis = insight_data.get("investment_thesis", [])
        for point in thesis:
            report += f"- {point}\n"
        
        report += "\n### ⚠️ 风险因素\n"
        risks = insight_data.get("risk_factors", [])
        if risks:
            for risk in risks:
                report += f"- {risk}\n"
        else:
            report += "- 暂无明显风险因素\n"
        
        # Competitive position
        competitive = insight_data.get("competitive_position", {})
        report += f"""
### 🏆 竞争地位
- 行业地位: {competitive.get('position', '未知')}
- 优秀指标数: {competitive.get('excellent_metrics', 0)}/{competitive.get('total_metrics', 0)}
"""
        
        # Financial strength
        strength = insight_data.get("financial_strength", {})
        report += f"""
### 💪 财务实力
- 财务实力等级: {strength.get('level', '未知')}
- 健康度评分: {strength.get('score', 0)}/100
"""
        
        key_strengths = strength.get("key_strengths", [])
        if key_strengths:
            report += "- 核心优势: " + "、".join(key_strengths) + "\n"
        
        # Growth prospects
        growth = insight_data.get("growth_prospects", {})
        report += f"""
### 🚀 成长前景
- 成长性评级: {growth.get('prospects', '未知')}
- 营收增长率: {growth.get('revenue_growth', 'N/A')}%
- 利润增长率: {growth.get('profit_growth', 'N/A')}%
"""
        
        report += "\n### 📋 免责声明\n以上分析基于历史财务数据，仅供参考，不构成投资建议。投资有风险，决策需谨慎。"
        
        return report
        
    except Exception as e:
        logger.error(f"Error generating insights for {ts_code}: {e}")
        return f"❌ 生成投资洞察 {ts_code} 时发生错误: {str(e)}"


def get_income_statement(ts_code: str, periods: int = 4) -> str:
    """获取利润表数据。

    Args:
        ts_code: 股票代码
        periods: 期数，默认4期

    Returns:
        利润表数据。
    """
    is_valid, ts_code, error_msg = _validate_and_normalize_stock_code(ts_code)
    if not is_valid:
        return f"❌ {error_msg}"

    try:
        service = FinancialReportService()
        result = service.get_income_statement(ts_code, periods)

        if result.get("status") == "error":
            return f"❌ 获取利润表失败: {result.get('error', '未知错误')}"

        data = result.get("data", [])
        if not data:
            return f"❌ 未找到 {ts_code} 的利润表数据"

        report = f"## {ts_code} 利润表 (近{len(data)}期)\n\n"
        report += "| 报告期 | 营业收入 | 营业利润 | 净利润 | 每股收益 |\n"
        report += "|---------|----------|----------|--------|----------|\n"

        for row in data[:periods]:
            report += f"| {row.get('end_date', '')} | {row.get('revenue', 0):.2f} | {row.get('operate_profit', 0):.2f} | {row.get('n_income', 0):.2f} | {row.get('basic_eps', 0):.2f} |\n"

        return report
    except Exception as e:
        logger.error(f"Error getting income statement for {ts_code}: {e}")
        return f"❌ 获取利润表 {ts_code} 时发生错误: {str(e)}"


def get_balance_sheet(ts_code: str, periods: int = 4) -> str:
    """获取资产负债表数据。

    Args:
        ts_code: 股票代码
        periods: 期数，默认4期

    Returns:
        资产负债表数据。
    """
    is_valid, ts_code, error_msg = _validate_and_normalize_stock_code(ts_code)
    if not is_valid:
        return f"❌ {error_msg}"

    try:
        service = FinancialReportService()
        result = service.get_balance_sheet(ts_code, periods)

        if result.get("status") == "error":
            return f"❌ 获取资产负债表失败: {result.get('error', '未知错误')}"

        data = result.get("data", [])
        if not data:
            return f"❌ 未找到 {ts_code} 的资产负债表数据"

        report = f"## {ts_code} 资产负债表 (近{len(data)}期)\n\n"
        report += "| 报告期 | 总资产 | 负债合计 | 股东权益 | 资产负债率 |\n"
        report += "|---------|--------|--------|----------|------------|\n"

        for row in data[:periods]:
            total_assets = row.get('total_assets', 0)
            total_liab = row.get('total_liab', 0)
            equity = row.get('equity', 0)
            debt_ratio = (total_liab / total_assets * 100) if total_assets else 0

            report += f"| {row.get('end_date', '')} | {total_assets:.2f} | {total_liab:.2f} | {equity:.2f} | {debt_ratio:.2f}% |\n"

        return report
    except Exception as e:
        logger.error(f"Error getting balance sheet for {ts_code}: {e}")
        return f"❌ 获取资产负债表 {ts_code} 时发生错误: {str(e)}"


def get_cash_flow(ts_code: str, periods: int = 4) -> str:
    """获取现金流量表数据。

    Args:
        ts_code: 股票代码
        periods: 期数，默认4期

    Returns:
        现金流量表数据。
    """
    is_valid, ts_code, error_msg = _validate_and_normalize_stock_code(ts_code)
    if not is_valid:
        return f"❌ {error_msg}"

    try:
        service = FinancialReportService()
        result = service.get_cash_flow(ts_code, periods)

        if result.get("status") == "error":
            return f"❌ 获取现金流量表失败: {result.get('error', '未知错误')}"

        data = result.get("data", [])
        if not data:
            return f"❌ 未找到 {ts_code} 的现金流量表数据"

        report = f"## {ts_code} 现金流量表 (近{len(data)}期)\n\n"
        report += "| 报告期 | 经营现金流 | 投资现金流 | 筹资现金流 | 净现金流 |\n"
        report += "|---------|-----------|-----------|-----------|---------|\n"

        for row in data[:periods]:
            report += f"| {row.get('end_date', '')} | {row.get('n_cashflow_act', 0):.2f} | {row.get('n_cashflow_inv_act', 0):.2f} | {row.get('n_cashflow_fin_act', 0):.2f} | {row.get('n_cash_flows_fnc_act', 0):.2f} |\n"

        return report
    except Exception as e:
        logger.error(f"Error getting cash flow for {ts_code}: {e}")
        return f"❌ 获取现金流量表 {ts_code} 时发生错误: {str(e)}"


def get_forecast(ts_code: str, limit: int = 10) -> str:
    """获取业绩预告数据。

    Args:
        ts_code: 股票代码
        limit: 返回记录数，默认10条

    Returns:
        业绩预告数据。
    """
    is_valid, ts_code, error_msg = _validate_and_normalize_stock_code(ts_code)
    if not is_valid:
        return f"❌ {error_msg}"

    try:
        service = FinancialReportService()
        result = service.get_forecast(ts_code, limit)

        if result.get("status") == "error":
            return f"❌ 获取业绩预告失败: {result.get('error', '未知错误')}"

        data = result.get("data", [])
        if not data:
            return f"ℹ️ 未找到 {ts_code} 的业绩预告数据"

        report = f"## {ts_code} 业绩预告 (共{len(data)}条)\n\n"
        report += "| 报告期 | 预告类型 | 预测净利润 | 同比增长 | 公告日期 |\n"
        report += "|---------|---------|-----------|---------|---------|\n"

        for row in data[:limit]:
            p_change_min = row.get('p_change_min', 0)
            p_change_max = row.get('p_change_max', 0)
            change_range = f"{p_change_min:.1f}% ~ {p_change_max:.1f}%" if p_change_min != p_change_max else f"{p_change_min:.1f}%"

            report += f"| {row.get('end_date', '')} | {row.get('type', '')} | {row.get('p_profit_min', 0):.2f} ~ {row.get('p_profit_max', 0):.2f} | {change_range} | {row.get('ann_date', '')} |\n"

        return report
    except Exception as e:
        logger.error(f"Error getting forecast for {ts_code}: {e}")
        return f"❌ 获取业绩预告 {ts_code} 时发生错误: {str(e)}"


def get_express(ts_code: str, limit: int = 10) -> str:
    """获取业绩快报数据。

    Args:
        ts_code: 股票代码
        limit: 返回记录数，默认10条

    Returns:
        业绩快报数据。
    """
    is_valid, ts_code, error_msg = _validate_and_normalize_stock_code(ts_code)
    if not is_valid:
        return f"❌ {error_msg}"

    try:
        service = FinancialReportService()
        result = service.get_express(ts_code, limit)

        if result.get("status") == "error":
            return f"❌ 获取业绩快报失败: {result.get('error', '未知错误')}"

        data = result.get("data", [])
        if not data:
            return f"ℹ️ 未找到 {ts_code} 的业绩快报数据"

        report = f"## {ts_code} 业绩快报 (共{len(data)}条)\n\n"
        report += "| 报告期 | 营业收入 | 净利润 | 净利润增长率 | 公告日期 |\n"
        report += "|---------|----------|--------|-------------|---------|\n"

        for row in data[:limit]:
            report += f"| {row.get('end_date', '')} | {row.get('revenue', 0):.2f} | {row.get('n_income', 0):.2f} | {row.get('yoy_net_profit', 0):.2f}% | {row.get('ann_date', '')} |\n"

        return report
    except Exception as e:
        logger.error(f"Error getting express for {ts_code}: {e}")
        return f"❌ 获取业绩快报 {ts_code} 时发生错误: {str(e)}"


def get_full_financial_statements(ts_code: str, periods: int = 4) -> str:
    """获取完整的三大财务报表。

    Args:
        ts_code: 股票代码
        periods: 期数，默认4期

    Returns:
        包含利润表、资产负债表、现金流量表的完整数据。
    """
    is_valid, ts_code, error_msg = _validate_and_normalize_stock_code(ts_code)
    if not is_valid:
        return f"❌ {error_msg}"

    try:
        service = FinancialReportService()
        result = service.get_full_financial_statements(ts_code, periods)

        if result.get("status") == "error":
            return f"❌ 获取财务报表失败: {result.get('error', '未知错误')}"

        income_data = result.get("income_statement", {}).get("data", [])[:periods]
        balance_data = result.get("balance_sheet", {}).get("data", [])[:periods]
        cashflow_data = result.get("cash_flow", {}).get("data", [])[:periods]

        report = f"# {ts_code} 财务报表 (近{periods}期)\n\n"

        if income_data:
            report += "## 利润表\n"
            report += "| 报告期 | 营业收入 | 净利润 | EPS |\n"
            report += "|---------|----------|--------|-----|\n"
            for row in income_data:
                report += f"| {row.get('end_date', '')} | {row.get('revenue', 0):.2f} | {row.get('n_income', 0):.2f} | {row.get('basic_eps', 0):.2f} |\n"
            report += "\n"

        if balance_data:
            report += "## 资产负债表\n"
            report += "| 报告期 | 总资产 | 股东权益 | 资产负债率 |\n"
            report += "|---------|--------|----------|------------|\n"
            for row in balance_data:
                total_assets = row.get('total_assets', 0)
                total_liab = row.get('total_liab', 0)
                debt_ratio = (total_liab / total_assets * 100) if total_assets else 0
                report += f"| {row.get('end_date', '')} | {total_assets:.2f} | {row.get('equity', 0):.2f} | {debt_ratio:.2f}% |\n"
            report += "\n"

        if cashflow_data:
            report += "## 现金流量表\n"
            report += "| 报告期 | 经营现金流 | 净现金流 |\n"
            report += "|---------|-----------|---------|\n"
            for row in cashflow_data:
                report += f"| {row.get('end_date', '')} | {row.get('n_cashflow_act', 0):.2f} | {row.get('n_cash_flows_fnc_act', 0):.2f} |\n"

        return report
    except Exception as e:
        logger.error(f"Error getting full statements for {ts_code}: {e}")
        return f"❌ 获取财务报表 {ts_code} 时发生错误: {str(e)}"


def get_audit_opinion(ts_code: str, periods: int = 5) -> str:
    """获取财务审计意见数据。

    Args:
        ts_code: 股票代码
        periods: 期数，默认5期

    Returns:
        审计意见数据，包括审计结果、审计费用、会计师事务所等。
    """
    is_valid, ts_code, error_msg = _validate_and_normalize_stock_code(ts_code)
    if not is_valid:
        return f"❌ {error_msg}"

    try:
        from ..plugins.tushare_fina_audit.service import TuShareFinaAuditService
        service = TuShareFinaAuditService()
        data = service.get_audit_opinion(ts_code, periods)

        if not data:
            return f"ℹ️ 未找到 {ts_code} 的审计意见数据"

        report = f"## {ts_code} 财务审计意见 (近{len(data)}期)\n\n"
        report += "| 报告期 | 审计结果 | 审计费用(万元) | 会计师事务所 | 签字会计师 |\n"
        report += "|---------|----------|--------------|-------------|------------|\n"

        for row in data[:periods]:
            audit_fees = row.get('audit_fees', 0)
            audit_fees_wan = audit_fees / 10000 if audit_fees else 0
            report += f"| {row.get('end_date', '')} | {row.get('audit_result', 'N/A')} | {audit_fees_wan:.2f} | {row.get('audit_agency', 'N/A')} | {row.get('audit_sign', 'N/A')} |\n"

        # 审计风险提示
        non_standard = [r for r in data if r.get('audit_result') and r.get('audit_result') != '标准无保留意见']
        if non_standard:
            report += "\n### ⚠️ 审计风险提示\n"
            report += f"发现 {len(non_standard)} 期非标准审计意见:\n"
            for row in non_standard:
                report += f"- {row.get('end_date', '')}: {row.get('audit_result', '')}\n"

        return report
    except Exception as e:
        logger.error(f"Error getting audit opinion for {ts_code}: {e}")
        return f"❌ 获取审计意见 {ts_code} 时发生错误: {str(e)}"


def get_non_standard_opinions(start_date: str = None, end_date: str = None, limit: int = 50) -> str:
    """获取非标准审计意见列表。

    Args:
        start_date: 开始日期，格式 YYYY-MM-DD
        end_date: 结束日期，格式 YYYY-MM-DD
        limit: 返回记录数，默认50条

    Returns:
        非标准审计意见列表，用于风险监控。
    """
    try:
        from datetime import datetime, timedelta
        from ..plugins.tushare_fina_audit.service import TuShareFinaAuditService
        
        # 默认查询最近一年
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        
        service = TuShareFinaAuditService()
        data = service.get_non_standard_opinions(start_date, end_date, limit)

        if not data:
            return f"ℹ️ 在 {start_date} 至 {end_date} 期间未发现非标准审计意见"

        report = f"## 非标准审计意见列表 ({start_date} 至 {end_date})\n\n"
        report += f"共发现 {len(data)} 条非标准审计意见:\n\n"
        report += "| 股票代码 | 报告期 | 审计结果 | 会计师事务所 | 公告日期 |\n"
        report += "|----------|--------|----------|-------------|----------|\n"

        for row in data[:limit]:
            report += f"| {row.get('ts_code', '')} | {row.get('end_date', '')} | {row.get('audit_result', '')} | {row.get('audit_agency', '')} | {row.get('ann_date', '')} |\n"

        report += "\n### 📝 说明\n"
        report += "非标准审计意见可能表明公司存在财务风险，建议进一步研究具体原因。\n"
        report += "常见类型包括：保留意见、否定意见、无法表示意见、带强调事项段的无保留意见等。"

        return report
    except Exception as e:
        logger.error(f"Error getting non-standard opinions: {e}")
        return f"❌ 获取非标准审计意见时发生错误: {str(e)}"


class ReportAgent(LangGraphAgent):
    """Report Agent for financial report analysis using DeepAgents.
    
    Handles:
    - Comprehensive financial analysis
    - Peer comparison and industry benchmarking
    - AI-powered investment insights
    - Financial health assessment
    """
    
    def __init__(self):
        config = AgentConfig(
            name="ReportAgent",
            description="专业财报分析师，提供全面的财务分析、同业对比、投资洞察等服务"
        )
        super().__init__(config)
    
    def get_tools(self) -> List[Callable]:
        """Return enhanced report analysis tools."""
        return [
            get_stock_info,
            get_stock_valuation,
            get_comprehensive_financial_analysis,
            get_peer_comparison_analysis,
            get_investment_insights,
            get_income_statement,
            get_balance_sheet,
            get_cash_flow,
            get_forecast,
            get_express,
            get_full_financial_statements,
            get_audit_opinion,
            get_non_standard_opinions,
        ]
    
    def get_system_prompt(self) -> str:
        """Return enhanced system prompt for comprehensive financial analysis."""
        return """你是一个专业的财务分析师和投资顾问，专注于A股上市公司的深度财报分析。

## 核心能力
- 全面财务健康度评估
- 专业同业对比分析  
- AI驱动的投资洞察
- 多维度风险识别
- 基于数据的投资建议
- 审计意见风险评估

## 可用工具
- get_stock_info: 获取股票基本信息和最新行情
- get_stock_valuation: 获取PE、PB等估值指标
- get_comprehensive_financial_analysis: 获取全面财务分析(健康度、盈利能力、偿债能力、成长性)
- get_peer_comparison_analysis: 获取同业对比分析和行业排名
- get_investment_insights: 获取AI投资洞察和结构化建议
- get_income_statement: 获取利润表数据（营业收入、净利润、EPS等）
- get_balance_sheet: 获取资产负债表数据（总资产、负债、股东权益等）
- get_cash_flow: 获取现金流量表数据（经营现金流、投资现金流、筹资现金流等）
- get_forecast: 获取业绩预告数据
- get_express: 获取业绩快报数据
- get_full_financial_statements: 获取完整的三大财务报表（利润表、资产负债表、现金流量表）
- get_audit_opinion: 获取财务审计意见数据（审计结果、审计费用、会计师事务所、签字会计师）
- get_non_standard_opinions: 获取非标准审计意见列表（用于风险监控和筛选）

## 分析框架 (基于真实财务数据)
1. **盈利能力**: ROE、ROA、毛利率、净利率、EPS
2. **偿债能力**: 资产负债率、流动比率、速动比率
3. **运营效率**: 资产周转率、存货周转率、应收账款周转率
4. **成长性**: 营收增长率、利润增长率、趋势分析
5. **估值水平**: PE、PB、PS与行业对比
6. **行业地位**: 同业对比、行业排名、竞争优势
7. **审计风险**: 审计意见类型、历史审计记录、会计师事务所变更

## 审计意见类型说明
- 标准无保留意见: 财务报表公允反映公司财务状况（最佳）
- 带强调事项段的无保留意见: 存在需要关注的事项但不影响整体公允性
- 保留意见: 部分事项无法核实或存在异议
- 否定意见: 财务报表整体不公允（高风险警示）
- 无法表示意见: 审计范围受限，无法发表意见（高风险警示）

## 分析流程
1. 获取股票基本信息和行情数据
2. 进行全面财务分析，评估财务健康度
3. 查看审计意见，评估财务报表可靠性
4. 执行同业对比，确定行业地位
5. 生成AI投资洞察和风险评估
6. 提供综合性投资建议和关注点

## 专业标准
- 基于真实财务数据，确保分析准确性
- 多维度横向对比，提供行业视角
- 历史趋势分析，识别发展轨迹
- 风险因素识别，平衡收益与风险
- 审计意见分析，评估报表可信度
- 结构化输出，便于理解和决策

## 常用股票代码示例
- 贵州茅台: 600519 → 600519.SH
- 平安银行: 000001 → 000001.SZ  
- 比亚迪: 002594 → 002594.SZ
- 宁德时代: 300750 → 300750.SZ

## 分析原则
- 数据驱动：基于真实财务指标
- 对比分析：横向同业、纵向历史
- 风险意识：明确指出潜在风险
- 审计关注：非标准意见需重点提示
- 投资导向：提供实用投资建议
- 专业表达：使用专业术语和标准

## 免责声明
所有财务分析和投资建议仅供参考，不构成投资决策依据。投资有风险，入市需谨慎。
"""
