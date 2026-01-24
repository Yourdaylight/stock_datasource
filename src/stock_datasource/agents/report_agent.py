"""Report Agent for financial report analysis using LangGraph/DeepAgents."""

from typing import Dict, Any, List, Callable, Optional, Tuple
import logging
import json
import re

from .base_agent import LangGraphAgent, AgentConfig
from .tools import get_stock_info, get_stock_valuation
from ..services.financial_report_service import FinancialReportService

logger = logging.getLogger(__name__)


def _validate_and_normalize_stock_code(ts_code: str) -> Tuple[bool, str, Optional[str]]:
    """Validate and normalize stock code.
    
    Args:
        ts_code: Raw stock code input
        
    Returns:
        Tuple of (is_valid, normalized_code, error_message)
    """
    if not ts_code:
        return False, "", "股票代码不能为空"
    
    # Strip whitespace
    ts_code = ts_code.strip().upper()
    
    # Check if already in valid format (e.g., 600519.SH)
    if re.match(r'^\d{6}\.(SH|SZ|BJ)$', ts_code):
        return True, ts_code, None
    
    # Check if it's a 6-digit code without suffix
    if len(ts_code) == 6 and ts_code.isdigit():
        if ts_code.startswith('6'):
            return True, f"{ts_code}.SH", None
        elif ts_code.startswith(('0', '3')):
            return True, f"{ts_code}.SZ", None
        elif ts_code.startswith(('4', '8')):
            return True, f"{ts_code}.BJ", None
        else:
            return False, ts_code, f"无法识别的股票代码前缀: {ts_code}"
    
    # Invalid format
    return False, ts_code, f"无效的股票代码格式: {ts_code}。请使用6位数字代码(如600519)或完整代码(如600519.SH)"


def get_comprehensive_financial_analysis(ts_code: str, periods: int = 4) -> str:
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
        return f"❌ {error_msg}"
    
    try:
        service = FinancialReportService()
        analysis = service.get_comprehensive_analysis(ts_code, periods)
        
        if analysis.get("status") == "error":
            return f"❌ 获取 {ts_code} 财务数据失败: {analysis.get('error', '未知错误')}"
        
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
- ROE (净资产收益率): {prof.get('roe', 'N/A')}%
- ROA (总资产收益率): {prof.get('roa', 'N/A')}%
- 毛利率: {prof.get('gross_profit_margin', 'N/A')}%
- 净利率: {prof.get('net_profit_margin', 'N/A')}%
"""
        
        # Solvency metrics
        solv = summary.get("solvency", {})
        report += f"""
### 🛡️ 偿债能力指标
- 资产负债率: {solv.get('debt_to_assets', 'N/A')}%
- 流动比率: {solv.get('current_ratio', 'N/A')}
- 速动比率: {solv.get('quick_ratio', 'N/A')}
"""
        
        # Growth analysis
        growth_data = summary.get("growth", {})
        if growth_data:
            report += f"""
### 🚀 成长性分析
- 营收增长率: {growth_data.get('revenue_growth', 'N/A')}%
- 净利润增长率: {growth_data.get('profit_growth', 'N/A')}%
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
        
        return report
        
    except Exception as e:
        logger.error(f"Error in comprehensive financial analysis for {ts_code}: {e}")
        return f"❌ 分析 {ts_code} 时发生错误: {str(e)}"


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

## 分析框架 (基于真实财务数据)
1. **盈利能力**: ROE、ROA、毛利率、净利率、EPS
2. **偿债能力**: 资产负债率、流动比率、速动比率
3. **运营效率**: 资产周转率、存货周转率、应收账款周转率
4. **成长性**: 营收增长率、利润增长率、趋势分析
5. **估值水平**: PE、PB、PS与行业对比
6. **行业地位**: 同业对比、行业排名、竞争优势

## 分析流程
1. 获取股票基本信息和行情数据
2. 进行全面财务分析，评估财务健康度
3. 执行同业对比，确定行业地位
4. 生成AI投资洞察和风险评估
5. 提供综合性投资建议和关注点

## 专业标准
- 基于真实财务数据，确保分析准确性
- 多维度横向对比，提供行业视角
- 历史趋势分析，识别发展轨迹
- 风险因素识别，平衡收益与风险
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
- 投资导向：提供实用投资建议
- 专业表达：使用专业术语和标准

## 免责声明
所有财务分析和投资建议仅供参考，不构成投资决策依据。投资有风险，入市需谨慎。
"""
