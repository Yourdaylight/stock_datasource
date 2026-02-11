"""HK Financial Report Service for comprehensive Hong Kong stock financial analysis."""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from stock_datasource.plugins.tushare_hk_fina_indicator.service import TuShareHKFinaIndicatorService
from stock_datasource.plugins.tushare_hk_income.service import TuShareHKIncomeService
from stock_datasource.plugins.tushare_hk_balancesheet.service import TuShareHKBalancesheetService
from stock_datasource.plugins.tushare_hk_cashflow.service import TuShareHKCashflowService

logger = logging.getLogger(__name__)


class HKFinancialReportService:
    """Unified service for Hong Kong stock financial report analysis."""

    def __init__(self):
        self.fina_service = TuShareHKFinaIndicatorService()
        self.income_service = TuShareHKIncomeService()
        self.balancesheet_service = TuShareHKBalancesheetService()
        self.cashflow_service = TuShareHKCashflowService()
        self.logger = logger

    # ========== 综合分析 ==========

    def get_comprehensive_analysis(self, code: str, periods: Optional[int] = 8) -> Dict[str, Any]:
        """Get comprehensive financial analysis for an HK stock.

        Args:
            code: HK stock code (e.g., 00700.HK)
            periods: Number of periods to analyze

        Returns:
            Comprehensive financial analysis including profitability, solvency, growth
        """
        try:
            # Get financial indicators (wide table)
            indicators = self.fina_service.get_financial_indicators(code, periods)
            profitability = self.fina_service.get_profitability_metrics(code, periods)

            # Get three statements (pivot format)
            income_data = self.income_service.get_income_pivot(code, periods_count=periods)
            balance_data = self.balancesheet_service.get_balancesheet_pivot(code, periods_count=periods)
            cashflow_data = self.cashflow_service.get_cashflow_pivot(code, periods_count=periods)

            # Build summary
            summary = self._build_summary(indicators, profitability)
            health = self._analyze_health(indicators, balance_data)
            growth = self._analyze_growth(indicators)

            return {
                "code": code,
                "analysis_date": datetime.now().isoformat(),
                "summary": summary,
                "health_analysis": health,
                "growth_analysis": growth,
                "raw_data": {
                    "indicators": indicators,
                    "income": income_data,
                    "balance": balance_data,
                    "cashflow": cashflow_data,
                },
                "status": "success",
            }

        except Exception as e:
            self.logger.error(f"Error in HK comprehensive analysis for {code}: {e}")
            return {"code": code, "status": "error", "error": str(e)}

    # ========== 财务指标查询 ==========

    def get_financial_indicators(self, code: str, periods: int = 8) -> Dict[str, Any]:
        """获取港股财务指标数据（宽表）"""
        try:
            data = self.fina_service.get_financial_indicators(code, periods)
            return {
                "code": code,
                "periods": len(data),
                "data": data,
                "status": "success",
            }
        except Exception as e:
            self.logger.error(f"Error getting HK fina indicators for {code}: {e}")
            return {"code": code, "status": "error", "error": str(e)}

    # ========== 三大报表查询 ==========

    def get_income_statement(self, code: str, periods: int = 8, period: Optional[str] = None) -> Dict[str, Any]:
        """获取港股利润表数据（PIVOT 宽表格式）"""
        try:
            data = self.income_service.get_income_pivot(code, period=period, periods_count=periods)
            return {
                "code": code,
                "periods": data.get("periods", 0),
                "indicators": data.get("indicators", []),
                "data": data.get("data", []),
                "status": "success",
            }
        except Exception as e:
            self.logger.error(f"Error getting HK income for {code}: {e}")
            return {"code": code, "status": "error", "error": str(e)}

    def get_balance_sheet(self, code: str, periods: int = 8, period: Optional[str] = None) -> Dict[str, Any]:
        """获取港股资产负债表数据（PIVOT 宽表格式）"""
        try:
            data = self.balancesheet_service.get_balancesheet_pivot(code, period=period, periods_count=periods)
            return {
                "code": code,
                "periods": data.get("periods", 0),
                "indicators": data.get("indicators", []),
                "data": data.get("data", []),
                "status": "success",
            }
        except Exception as e:
            self.logger.error(f"Error getting HK balance sheet for {code}: {e}")
            return {"code": code, "status": "error", "error": str(e)}

    def get_cash_flow(self, code: str, periods: int = 8, period: Optional[str] = None) -> Dict[str, Any]:
        """获取港股现金流量表数据（PIVOT 宽表格式）"""
        try:
            data = self.cashflow_service.get_cashflow_pivot(code, period=period, periods_count=periods)
            return {
                "code": code,
                "periods": data.get("periods", 0),
                "indicators": data.get("indicators", []),
                "data": data.get("data", []),
                "status": "success",
            }
        except Exception as e:
            self.logger.error(f"Error getting HK cash flow for {code}: {e}")
            return {"code": code, "status": "error", "error": str(e)}

    def get_full_financial_statements(self, code: str, periods: int = 8) -> Dict[str, Any]:
        """获取港股完整的三大财务报表"""
        try:
            income = self.get_income_statement(code, periods)
            balance = self.get_balance_sheet(code, periods)
            cashflow = self.get_cash_flow(code, periods)

            return {
                "code": code,
                "income_statement": income,
                "balance_sheet": balance,
                "cash_flow": cashflow,
                "status": "success",
            }
        except Exception as e:
            self.logger.error(f"Error getting HK full statements for {code}: {e}")
            return {"code": code, "status": "error", "error": str(e)}

    # ========== 原始 EAV 查询 ==========

    def get_income_raw(self, code: str, period: Optional[str] = None,
                       indicators: Optional[str] = None, limit: int = 500) -> Dict[str, Any]:
        """获取港股利润表原始 EAV 数据"""
        try:
            data = self.income_service.get_income(code, period=period, indicators=indicators, limit=limit)
            return {"code": code, "count": len(data), "data": data, "status": "success"}
        except Exception as e:
            self.logger.error(f"Error getting HK income raw for {code}: {e}")
            return {"code": code, "status": "error", "error": str(e)}

    def get_balancesheet_raw(self, code: str, period: Optional[str] = None,
                             indicators: Optional[str] = None, limit: int = 500) -> Dict[str, Any]:
        """获取港股资产负债表原始 EAV 数据"""
        try:
            data = self.balancesheet_service.get_balancesheet(code, period=period, indicators=indicators, limit=limit)
            return {"code": code, "count": len(data), "data": data, "status": "success"}
        except Exception as e:
            self.logger.error(f"Error getting HK balancesheet raw for {code}: {e}")
            return {"code": code, "status": "error", "error": str(e)}

    def get_cashflow_raw(self, code: str, period: Optional[str] = None,
                         indicators: Optional[str] = None, limit: int = 500) -> Dict[str, Any]:
        """获取港股现金流量表原始 EAV 数据"""
        try:
            data = self.cashflow_service.get_cashflow(code, period=period, indicators=indicators, limit=limit)
            return {"code": code, "count": len(data), "data": data, "status": "success"}
        except Exception as e:
            self.logger.error(f"Error getting HK cashflow raw for {code}: {e}")
            return {"code": code, "status": "error", "error": str(e)}

    # ========== 指标列表 ==========

    def list_income_indicators(self, code: Optional[str] = None) -> List[str]:
        """列出港股利润表所有指标名称"""
        return self.income_service.list_indicators(code)

    def list_balancesheet_indicators(self, code: Optional[str] = None) -> List[str]:
        """列出港股资产负债表所有指标名称"""
        return self.balancesheet_service.list_indicators(code)

    def list_cashflow_indicators(self, code: Optional[str] = None) -> List[str]:
        """列出港股现金流量表所有指标名称"""
        return self.cashflow_service.list_indicators(code)

    # ========== 内部分析方法 ==========

    def _build_summary(self, indicators: List[Dict], profitability: Dict) -> Dict[str, Any]:
        """Build financial summary from indicators."""
        if not indicators:
            return {"message": "No indicator data available"}

        latest = indicators[0] if indicators else {}
        metrics = profitability.get("metrics", [])
        latest_metric = metrics[0] if metrics else {}

        return {
            "latest_period": latest.get("end_date"),
            "name": latest.get("name"),
            "periods": len(indicators),
            "profitability": {
                "roe_avg": latest_metric.get("roe_avg"),
                "roa": latest_metric.get("roa"),
                "gross_profit_ratio": latest_metric.get("gross_profit_ratio"),
                "net_profit_ratio": latest_metric.get("net_profit_ratio"),
                "basic_eps": latest_metric.get("basic_eps"),
            },
            "valuation": {
                "pe_ttm": latest_metric.get("pe_ttm"),
                "pb_ttm": latest_metric.get("pb_ttm"),
                "total_market_cap": latest_metric.get("total_market_cap"),
            },
        }

    def _analyze_health(self, indicators: List[Dict], balance_data: Dict) -> Dict[str, Any]:
        """Analyze financial health with comprehensive metrics and personalized recommendations."""
        if not indicators:
            return {"health_score": 0, "strengths": [], "weaknesses": [], "recommendations": []}

        latest = indicators[0]
        score = 50
        strengths = []
        weaknesses = []
        recommendations = []

        def _safe_float(val):
            if val is None or val == '\\N' or val == 'None' or val == '':
                return None
            try:
                return float(val)
            except (ValueError, TypeError):
                return None

        # ROE assessment
        roe_val = _safe_float(latest.get("roe_avg"))
        if roe_val is not None:
            if roe_val > 20:
                score += 15
                strengths.append(f"ROE 非常优秀({roe_val:.1f}%)，资本回报率行业领先")
            elif roe_val > 15:
                score += 12
                strengths.append(f"ROE 表现优秀({roe_val:.1f}%)，股东回报良好")
            elif roe_val > 8:
                score += 5
                strengths.append(f"ROE 处于合理水平({roe_val:.1f}%)")
            elif roe_val > 0:
                score -= 5
                weaknesses.append(f"ROE 偏低({roe_val:.1f}%)，资本使用效率有待提升")
                recommendations.append("关注管理层提升资本回报率的具体措施")
            else:
                score -= 15
                weaknesses.append(f"ROE 为负({roe_val:.1f}%)，公司处于亏损状态")
                recommendations.append("重点关注公司扭亏为盈的战略规划和时间表")

        # ROA assessment
        roa_val = _safe_float(latest.get("roa"))
        if roa_val is not None:
            if roa_val > 10:
                score += 5
                strengths.append(f"总资产收益率优秀({roa_val:.1f}%)，资产利用效率高")
            elif roa_val < 2:
                score -= 5
                weaknesses.append(f"总资产收益率偏低({roa_val:.1f}%)，资产利用效率不足")

        # Gross profit ratio
        gpr_val = _safe_float(latest.get("gross_profit_ratio"))
        if gpr_val is not None:
            if gpr_val > 60:
                score += 10
                strengths.append(f"毛利率极高({gpr_val:.1f}%)，具有强定价权和护城河")
            elif gpr_val > 40:
                score += 8
                strengths.append(f"毛利率较高({gpr_val:.1f}%)，盈利模式良好")
            elif gpr_val > 20:
                score += 3
            elif gpr_val < 15:
                score -= 5
                weaknesses.append(f"毛利率偏低({gpr_val:.1f}%)，行业竞争压力较大")
                recommendations.append("关注公司产品差异化战略和成本控制能力")

        # Net profit ratio
        npr_val = _safe_float(latest.get("net_profit_ratio"))
        if npr_val is not None:
            if npr_val > 25:
                score += 5
                strengths.append(f"净利率优秀({npr_val:.1f}%)，费用管控和盈利转化能力强")
            elif npr_val < 5 and npr_val > 0:
                weaknesses.append(f"净利率偏低({npr_val:.1f}%)，盈利空间有限")
                recommendations.append("建议关注公司费用优化和利润率提升计划")

        # Net profit YoY growth
        np_yoy_val = _safe_float(latest.get("holder_profit_yoy"))
        if np_yoy_val is not None:
            if np_yoy_val > 50:
                score += 10
                strengths.append(f"净利润同比大幅增长({np_yoy_val:.1f}%)，业绩爆发力强")
                recommendations.append("高增长可能不可持续，关注增长的可持续性和质量")
            elif np_yoy_val > 20:
                score += 8
                strengths.append(f"净利润同比增长强劲({np_yoy_val:.1f}%)")
            elif np_yoy_val > 0:
                score += 3
            elif np_yoy_val > -20:
                score -= 5
                weaknesses.append(f"净利润同比小幅下滑({np_yoy_val:.1f}%)")
                recommendations.append("关注利润下滑是短期波动还是趋势性变化")
            else:
                score -= 10
                weaknesses.append(f"净利润同比大幅下滑({np_yoy_val:.1f}%)，盈利能力明显恶化")
                recommendations.append("重点关注利润下滑的核心原因及管理层的应对策略")

        # Revenue YoY growth
        rev_yoy_val = _safe_float(latest.get("operate_income_yoy"))
        if rev_yoy_val is not None:
            if rev_yoy_val > 30:
                score += 5
                strengths.append(f"营收同比高速增长({rev_yoy_val:.1f}%)，市场扩张势头强劲")
            elif rev_yoy_val > 10:
                score += 3
                strengths.append(f"营收保持稳健增长({rev_yoy_val:.1f}%)")
            elif rev_yoy_val < -10:
                score -= 8
                weaknesses.append(f"营收同比下滑({rev_yoy_val:.1f}%)，市场竞争力或需求减弱")
                recommendations.append("关注公司新业务布局和市场份额变化趋势")

        # PE valuation
        pe_val = _safe_float(latest.get("pe_ttm"))
        if pe_val is not None and pe_val > 0:
            if pe_val < 10:
                strengths.append(f"估值较低(PE {pe_val:.1f}倍)，可能存在低估机会")
                recommendations.append("低PE需排除业绩下滑预期，关注未来盈利趋势")
            elif pe_val > 50:
                weaknesses.append(f"估值偏高(PE {pe_val:.1f}倍)，需要高增长支撑")
                recommendations.append("高估值股票波动较大，建议关注业绩是否能匹配市场预期")
            elif pe_val > 30:
                recommendations.append(f"当前PE为{pe_val:.1f}倍，估值处于中等偏高水平")

        # EPS
        eps_val = _safe_float(latest.get("basic_eps"))
        if eps_val is not None:
            if eps_val > 5:
                strengths.append(f"每股收益较高({eps_val:.2f}元)，单股盈利能力强")
            elif eps_val < 0:
                weaknesses.append(f"每股收益为负({eps_val:.2f}元)，公司处于亏损")

        # Growth trend analysis (compare multiple periods)
        if len(indicators) >= 3:
            roe_trend = []
            for ind in indicators[:4]:
                v = _safe_float(ind.get("roe_avg"))
                if v is not None:
                    roe_trend.append(v)
            if len(roe_trend) >= 3:
                if all(roe_trend[i] >= roe_trend[i+1] for i in range(len(roe_trend)-1)):
                    strengths.append("ROE 连续多期改善，盈利能力持续提升")
                    score += 3
                elif all(roe_trend[i] <= roe_trend[i+1] for i in range(len(roe_trend)-1)):
                    weaknesses.append("ROE 连续多期下降，盈利能力呈恶化趋势")
                    score -= 3
                    recommendations.append("ROE持续下滑需警惕，建议深入分析杜邦拆解找出核心原因")

        # Generate summary recommendations if none yet
        if not recommendations:
            if score >= 75:
                recommendations.append("财务基本面优秀，可重点关注估值是否合理以及行业景气度")
            elif score >= 60:
                recommendations.append("财务状况总体良好，建议结合行业趋势和公司战略综合判断")
            else:
                recommendations.append("财务面存在一定风险，建议持续跟踪后续财报改善情况")

        score = max(0, min(100, score))

        return {
            "health_score": score,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "recommendations": recommendations,
        }

    def _analyze_growth(self, indicators: List[Dict]) -> Dict[str, Any]:
        """Analyze growth trends."""
        if len(indicators) < 2:
            return {"message": "Insufficient data for growth analysis"}

        growth = {}

        # Revenue growth between periods
        for i in range(len(indicators) - 1):
            cur = indicators[i]
            prev = indicators[i + 1]
            try:
                cur_rev = float(cur.get("operate_income", 0) or 0)
                prev_rev = float(prev.get("operate_income", 0) or 0)
                if prev_rev > 0:
                    growth[cur.get("end_date", f"period_{i}")] = {
                        "revenue_growth": round((cur_rev - prev_rev) / prev_rev * 100, 2),
                    }
            except (TypeError, ValueError):
                continue

        return {"period_growth": growth}
