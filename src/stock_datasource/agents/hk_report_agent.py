"""HK Report Agent for Hong Kong stock financial report analysis using LangGraph/DeepAgents."""

from typing import Dict, Any, List, Callable, Optional, Tuple
import logging
import re

from .base_agent import LangGraphAgent, AgentConfig
from ..services.hk_financial_report_service import HKFinancialReportService
from ..utils.stock_code import validate_hk_stock_code as _validate_and_normalize_hk_stock_code

logger = logging.getLogger(__name__)


# ========== Formatting Helpers ==========

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


# ========== Agent Tool Functions ==========

def get_hk_comprehensive_financial_analysis(ts_code: str, periods: int = 8) -> str:
    """获取港股全面财务分析报告。

    Args:
        ts_code: 港股代码，如 00700 或 00700.HK
        periods: 分析期数，默认8期

    Returns:
        全面的港股财务分析报告，包括财务健康度、盈利能力、成长性等。
    """
    is_valid, ts_code, error_msg = _validate_and_normalize_hk_stock_code(ts_code)
    if not is_valid:
        return f"❌ {error_msg}"

    try:
        service = HKFinancialReportService()
        analysis = service.get_comprehensive_analysis(ts_code, periods)

        if analysis.get("status") == "error":
            return f"❌ 获取 {ts_code} 财务数据失败: {analysis.get('error', '未知错误')}"

        summary = analysis.get("summary", {})
        health = analysis.get("health_analysis", {})

        report = f"### 📊 财务健康度评分: {health.get('health_score', 0)}/100\n\n"

        # Profitability
        prof = summary.get("profitability", {})
        report += f"""### 📈 盈利能力指标
- ROE (加权平均): {_fmt_pct(prof.get('roe_avg'))}
- ROA (总资产收益率): {_fmt_pct(prof.get('roa'))}
- 毛利率: {_fmt_pct(prof.get('gross_profit_ratio'))}
- 净利率: {_fmt_pct(prof.get('net_profit_ratio'))}
- 基本每股收益: {_fmt_num(prof.get('basic_eps'))}

"""

        # Valuation
        val = summary.get("valuation", {})
        report += f"""### 💰 估值指标
- PE (TTM): {_fmt_num(val.get('pe_ttm'))}
- PB (TTM): {_fmt_num(val.get('pb_ttm'))}
- 总市值: {val.get('total_market_cap', 'N/A')}

"""

        # Strengths
        report += "### 💪 主要优势\n"
        strengths = health.get("strengths", [])
        if strengths:
            for s in strengths:
                report += f"- {s}\n"
        else:
            report += "- 暂无明显优势\n"

        # Weaknesses
        report += "\n### ⚠️ 关注点\n"
        weaknesses = health.get("weaknesses", [])
        if weaknesses:
            for w in weaknesses:
                report += f"- {w}\n"
        else:
            report += "- 财务状况良好，无明显风险点\n"

        # Investment recommendations
        recommendations = health.get("recommendations", [])
        if recommendations:
            report += "\n### 💡 投资建议\n"
            for rec in recommendations:
                report += f"- {rec}\n"

        report += f"\n### 📅 数据说明\n- 公司名称: {summary.get('name', 'N/A')}\n- 最新财报: {summary.get('latest_period', 'N/A')}\n- 分析期数: {summary.get('periods', 0)}期"

        return report

    except Exception as e:
        logger.error(f"Error in HK comprehensive analysis for {ts_code}: {e}")
        return f"❌ 分析 {ts_code} 时发生错误: {str(e)}"


def get_hk_financial_indicators(ts_code: str, periods: int = 8) -> str:
    """获取港股财务指标数据。

    Args:
        ts_code: 港股代码
        periods: 期数，默认8期

    Returns:
        港股财务指标数据表格。
    """
    is_valid, ts_code, error_msg = _validate_and_normalize_hk_stock_code(ts_code)
    if not is_valid:
        return f"❌ {error_msg}"

    try:
        service = HKFinancialReportService()
        result = service.get_financial_indicators(ts_code, periods)

        if result.get("status") == "error":
            return f"❌ 获取财务指标失败: {result.get('error', '未知错误')}"

        data = result.get("data", [])
        if not data:
            return f"❌ 未找到 {ts_code} 的财务指标数据"

        report = f"## {ts_code} 港股财务指标 (近{len(data)}期)\n\n"
        report += "| 报告期 | ROE(%) | ROA(%) | 毛利率(%) | 净利率(%) | EPS | PE(TTM) |\n"
        report += "|---------|--------|--------|-----------|-----------|-----|--------|\n"

        for row in data[:periods]:
            report += (
                f"| {row.get('end_date', '')} "
                f"| {row.get('roe_avg', 'N/A')} "
                f"| {row.get('roa', 'N/A')} "
                f"| {row.get('gross_profit_ratio', 'N/A')} "
                f"| {row.get('net_profit_ratio', 'N/A')} "
                f"| {row.get('basic_eps', 'N/A')} "
                f"| {row.get('pe_ttm', 'N/A')} |\n"
            )

        return report
    except Exception as e:
        logger.error(f"Error getting HK indicators for {ts_code}: {e}")
        return f"❌ 获取财务指标 {ts_code} 时发生错误: {str(e)}"


def get_hk_income_statement(ts_code: str, periods: int = 8) -> str:
    """获取港股利润表数据。

    Args:
        ts_code: 港股代码
        periods: 期数，默认8期

    Returns:
        港股利润表数据（PIVOT 宽表格式）。
    """
    is_valid, ts_code, error_msg = _validate_and_normalize_hk_stock_code(ts_code)
    if not is_valid:
        return f"❌ {error_msg}"

    try:
        service = HKFinancialReportService()
        result = service.get_income_statement(ts_code, periods)

        if result.get("status") == "error":
            return f"❌ 获取利润表失败: {result.get('error', '未知错误')}"

        data = result.get("data", [])
        if not data:
            return f"❌ 未找到 {ts_code} 的利润表数据"

        report = f"## {ts_code} 港股利润表 (近{len(data)}期)\n\n"
        report += "| 报告期 | 营业收入 | 毛利 | 营业利润 | 净利润 |\n"
        report += "|---------|----------|------|----------|--------|\n"

        for row in data:
            report += (
                f"| {row.get('end_date', '')} "
                f"| {row.get('营业收入', 'N/A')} "
                f"| {row.get('毛利', 'N/A')} "
                f"| {row.get('营业利润', 'N/A')} "
                f"| {row.get('净利润', 'N/A')} |\n"
            )

        return report
    except Exception as e:
        logger.error(f"Error getting HK income for {ts_code}: {e}")
        return f"❌ 获取利润表 {ts_code} 时发生错误: {str(e)}"


def get_hk_balance_sheet(ts_code: str, periods: int = 8) -> str:
    """获取港股资产负债表数据。

    Args:
        ts_code: 港股代码
        periods: 期数，默认8期

    Returns:
        港股资产负债表数据（PIVOT 宽表格式）。
    """
    is_valid, ts_code, error_msg = _validate_and_normalize_hk_stock_code(ts_code)
    if not is_valid:
        return f"❌ {error_msg}"

    try:
        service = HKFinancialReportService()
        result = service.get_balance_sheet(ts_code, periods)

        if result.get("status") == "error":
            return f"❌ 获取资产负债表失败: {result.get('error', '未知错误')}"

        data = result.get("data", [])
        if not data:
            return f"❌ 未找到 {ts_code} 的资产负债表数据"

        report = f"## {ts_code} 港股资产负债表 (近{len(data)}期)\n\n"
        report += "| 报告期 | 资产总额 | 负债总额 | 股东权益 | 流动资产 |\n"
        report += "|---------|----------|----------|----------|----------|\n"

        for row in data:
            report += (
                f"| {row.get('end_date', '')} "
                f"| {row.get('资产总额', 'N/A')} "
                f"| {row.get('负债总额', 'N/A')} "
                f"| {row.get('股东权益', 'N/A')} "
                f"| {row.get('流动资产', 'N/A')} |\n"
            )

        return report
    except Exception as e:
        logger.error(f"Error getting HK balance sheet for {ts_code}: {e}")
        return f"❌ 获取资产负债表 {ts_code} 时发生错误: {str(e)}"


def get_hk_cash_flow(ts_code: str, periods: int = 8) -> str:
    """获取港股现金流量表数据。

    Args:
        ts_code: 港股代码
        periods: 期数，默认8期

    Returns:
        港股现金流量表数据（PIVOT 宽表格式）。
    """
    is_valid, ts_code, error_msg = _validate_and_normalize_hk_stock_code(ts_code)
    if not is_valid:
        return f"❌ {error_msg}"

    try:
        service = HKFinancialReportService()
        result = service.get_cash_flow(ts_code, periods)

        if result.get("status") == "error":
            return f"❌ 获取现金流量表失败: {result.get('error', '未知错误')}"

        data = result.get("data", [])
        if not data:
            return f"❌ 未找到 {ts_code} 的现金流量表数据"

        report = f"## {ts_code} 港股现金流量表 (近{len(data)}期)\n\n"
        report += "| 报告期 | 经营活动净额 | 投资活动净额 | 筹资活动净额 | 期末余额 |\n"
        report += "|---------|-------------|-------------|-------------|----------|\n"

        for row in data:
            report += (
                f"| {row.get('end_date', '')} "
                f"| {row.get('经营活动现金流量净额', 'N/A')} "
                f"| {row.get('投资活动现金流量净额', 'N/A')} "
                f"| {row.get('筹资活动现金流量净额', 'N/A')} "
                f"| {row.get('期末现金及等价物余额', 'N/A')} |\n"
            )

        return report
    except Exception as e:
        logger.error(f"Error getting HK cash flow for {ts_code}: {e}")
        return f"❌ 获取现金流量表 {ts_code} 时发生错误: {str(e)}"


def get_hk_full_financial_statements(ts_code: str, periods: int = 8) -> str:
    """获取港股完整的三大财务报表。

    Args:
        ts_code: 港股代码
        periods: 期数，默认8期

    Returns:
        包含利润表、资产负债表、现金流量表的完整数据。
    """
    is_valid, ts_code, error_msg = _validate_and_normalize_hk_stock_code(ts_code)
    if not is_valid:
        return f"❌ {error_msg}"

    try:
        service = HKFinancialReportService()
        result = service.get_full_financial_statements(ts_code, periods)

        if result.get("status") == "error":
            return f"❌ 获取财务报表失败: {result.get('error', '未知错误')}"

        report = f"# {ts_code} 港股财务报表 (近{periods}期)\n\n"

        # Income
        income_data = result.get("income_statement", {}).get("data", [])
        if income_data:
            report += "## 利润表\n"
            report += "| 报告期 | 营业收入 | 净利润 |\n"
            report += "|---------|----------|--------|\n"
            for row in income_data:
                report += f"| {row.get('end_date', '')} | {row.get('营业收入', 'N/A')} | {row.get('净利润', 'N/A')} |\n"
            report += "\n"

        # Balance
        balance_data = result.get("balance_sheet", {}).get("data", [])
        if balance_data:
            report += "## 资产负债表\n"
            report += "| 报告期 | 资产总额 | 负债总额 | 股东权益 |\n"
            report += "|---------|----------|----------|----------|\n"
            for row in balance_data:
                report += f"| {row.get('end_date', '')} | {row.get('资产总额', 'N/A')} | {row.get('负债总额', 'N/A')} | {row.get('股东权益', 'N/A')} |\n"
            report += "\n"

        # Cashflow
        cashflow_data = result.get("cash_flow", {}).get("data", [])
        if cashflow_data:
            report += "## 现金流量表\n"
            report += "| 报告期 | 经营活动净额 | 投资活动净额 | 筹资活动净额 |\n"
            report += "|---------|-------------|-------------|-------------|\n"
            for row in cashflow_data:
                report += (
                    f"| {row.get('end_date', '')} "
                    f"| {row.get('经营活动现金流量净额', 'N/A')} "
                    f"| {row.get('投资活动现金流量净额', 'N/A')} "
                    f"| {row.get('筹资活动现金流量净额', 'N/A')} |\n"
                )

        return report
    except Exception as e:
        logger.error(f"Error getting HK full statements for {ts_code}: {e}")
        return f"❌ 获取财务报表 {ts_code} 时发生错误: {str(e)}"


# ========== Agent Class ==========

class HKReportAgent(LangGraphAgent):
    """HK Report Agent for Hong Kong stock financial report analysis.

    Handles:
    - Comprehensive HK financial analysis
    - HK financial indicators (wide table)
    - HK income statement / balance sheet / cash flow (EAV pivot)
    - Financial health assessment
    """

    def __init__(self):
        config = AgentConfig(
            name="HKReportAgent",
            description="港股财报分析师，提供港股全面财务分析、三大报表查询、财务指标分析等服务"
        )
        super().__init__(config)

    def get_tools(self) -> List[Callable]:
        """Return HK report analysis tools."""
        return [
            get_hk_comprehensive_financial_analysis,
            get_hk_financial_indicators,
            get_hk_income_statement,
            get_hk_balance_sheet,
            get_hk_cash_flow,
            get_hk_full_financial_statements,
        ]

    def get_system_prompt(self) -> str:
        """Return system prompt for HK financial analysis."""
        return """你是一个专业的港股财务分析师，专注于港交所上市公司的深度财报分析。

## 核心能力
- 港股全面财务健康度评估
- 港股三大财务报表分析（利润表、资产负债表、现金流量表）
- 港股财务指标分析（ROE、ROA、毛利率、净利率等）
- 估值指标分析（PE、PB等）

## 可用工具
- get_hk_comprehensive_financial_analysis: 获取港股全面财务分析（健康度、盈利能力、成长性）
- get_hk_financial_indicators: 获取港股财务指标数据（宽表，含ROE/ROA/EPS/PE/PB等）
- get_hk_income_statement: 获取港股利润表（营业收入、毛利、净利润等）
- get_hk_balance_sheet: 获取港股资产负债表（总资产、总负债、股东权益等）
- get_hk_cash_flow: 获取港股现金流量表（经营/投资/筹资活动现金流）
- get_hk_full_financial_statements: 获取港股完整三大财务报表

## 分析框架
1. **盈利能力**: ROE、ROA、毛利率、净利率、EPS
2. **资产质量**: 资产负债率、流动资产/非流动资产结构
3. **现金流**: 经营现金流、自由现金流、现金流质量
4. **成长性**: 营收增长率、利润增长率、趋势分析
5. **估值水平**: PE(TTM)、PB(TTM)与同业对比

## 港股代码格式
- 腾讯控股: 00700 → 00700.HK
- 阿里巴巴: 09988 → 09988.HK
- 美团: 03690 → 03690.HK
- 小米集团: 01810 → 01810.HK
- 比亚迪股份: 01211 → 01211.HK

## 分析原则
- 数据驱动：基于真实财务指标
- 港股特点：注意港股报表为中文指标名（纵表 EAV 格式）
- 货币单位：港股报表通常以港币（HKD）或人民币（CNY）计价，注意区分
- 风险意识：明确指出潜在风险
- 专业表达：使用专业术语和标准

## 免责声明
所有财务分析和投资建议仅供参考，不构成投资决策依据。投资有风险，入市需谨慎。
"""
