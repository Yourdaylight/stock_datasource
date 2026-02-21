"""Financial Report Service for comprehensive financial analysis."""

import logging
import math
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from stock_datasource.plugins.tushare_finace_indicator.service import TuShareFinaceIndicatorService
from stock_datasource.plugins.tushare_income.service import TuShareIncomeService
from stock_datasource.plugins.tushare_balancesheet.service import TuShareBalancesheetService
from stock_datasource.plugins.tushare_cashflow.service import TuShareCashflowService
from stock_datasource.plugins.tushare_forecast.service import TuShareForecastService
from stock_datasource.plugins.tushare_express.service import TuShareExpressService

logger = logging.getLogger(__name__)


def _sanitize_json_data(data):
    """Recursively replace NaN/inf float values with None for JSON compatibility."""
    if isinstance(data, dict):
        return {k: _sanitize_json_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_sanitize_json_data(v) for v in data]
    elif isinstance(data, float):
        if math.isnan(data) or math.isinf(data):
            return None
    return data


class FinancialReportService:
    """Unified service for financial report analysis and insights."""
    
    def __init__(self):
        """Initialize the financial report service."""
        self.finace_service = TuShareFinaceIndicatorService()
        self.income_service = TuShareIncomeService()
        self.balancesheet_service = TuShareBalancesheetService()
        self.cashflow_service = TuShareCashflowService()
        self.forecast_service = TuShareForecastService()
        self.express_service = TuShareExpressService()
        self.logger = logger
    
    def get_comprehensive_analysis(self, code: str, periods: Optional[int] = 4) -> Dict[str, Any]:
        """Get comprehensive financial analysis for a stock.
        
        Args:
            code: Stock code (e.g., 002579.SZ)
            periods: Number of periods to analyze
            
        Returns:
            Comprehensive financial analysis including summary, growth, and health metrics
        """
        try:
            # Get financial summary
            summary = self.finace_service.get_financial_summary(code, periods)
            
            # Supplement revenue/net_profit from income statement into raw_data & growth
            self._supplement_income_data(summary, code, periods)
            
            # Get growth analysis
            growth_analysis = self.finace_service.calculate_growth_rates(code, periods * 2)
            
            # Get financial health analysis
            health_analysis = self.finace_service.analyze_financial_health(code, periods)
            
            return _sanitize_json_data({
                "code": code,
                "analysis_date": datetime.now().isoformat(),
                "summary": summary,
                "growth_analysis": growth_analysis,
                "health_analysis": health_analysis,
                "status": "success"
            })
            
        except Exception as e:
            self.logger.error(f"Error in comprehensive analysis for {code}: {e}")
            return {
                "code": code,
                "status": "error",
                "error": str(e)
            }
    
    @staticmethod
    def _is_valid_value(v) -> bool:
        """Check if a value is valid (not None, not ClickHouse NULL '\\N', not empty)."""
        return v is not None and v != '\\N' and v != 'None' and v != ''

    def _supplement_income_data(self, summary: Dict[str, Any], code: str, periods: int) -> None:
        """Supplement fina_indicator data with revenue/net_profit from income statement.
        
        TuShare fina_indicator API only provides ratio-type metrics (ROE, ROA, margins, etc.)
        but does NOT provide absolute amounts (total_revenue, net_profit).
        We fetch these from the income statement and merge them in.
        """
        try:
            # Fetch more income periods to ensure date coverage with fina_indicator
            income_result = self.income_service.get_profitability_metrics(code, periods * 3)
            if not income_result or income_result.get("periods", 0) == 0:
                return
            
            # Build lookup by end_date
            income_map = {}
            for m in income_result.get("metrics", []):
                ed = m.get("end_date", "")
                if ed:
                    income_map[ed] = m
            
            if not income_map:
                return
            
            # Patch raw_data entries
            raw_data = summary.get("raw_data", [])
            for item in raw_data:
                ed = item.get("end_date", "")
                if hasattr(ed, 'strftime'):
                    ed = ed.strftime('%Y-%m-%d')
                elif ed and not isinstance(ed, str):
                    ed = str(ed)
                
                inc = income_map.get(ed, {})
                if not self._is_valid_value(item.get("total_revenue")) and inc.get("total_revenue"):
                    item["total_revenue"] = inc["total_revenue"]
                if not self._is_valid_value(item.get("net_profit")) and inc.get("net_income"):
                    item["net_profit"] = inc["net_income"]
            
            # Also supplement gross_margin and net_margin from income if missing
            for item in raw_data:
                ed = item.get("end_date", "")
                if hasattr(ed, 'strftime'):
                    ed = ed.strftime('%Y-%m-%d')
                elif ed and not isinstance(ed, str):
                    ed = str(ed)
                
                inc = income_map.get(ed, {})
                if not self._is_valid_value(item.get("gross_profit_margin")) and inc.get("gross_margin"):
                    item["gross_profit_margin"] = inc["gross_margin"]
                if not self._is_valid_value(item.get("net_profit_margin")) and inc.get("net_margin"):
                    item["net_profit_margin"] = inc["net_margin"]
            
            # Recalculate growth if missing
            growth = summary.get("growth", {})
            if not growth.get("revenue_growth") and len(raw_data) >= 2:
                try:
                    curr_rev = float(raw_data[0].get("total_revenue")) if self._is_valid_value(raw_data[0].get("total_revenue")) else None
                    prev_rev = float(raw_data[1].get("total_revenue")) if self._is_valid_value(raw_data[1].get("total_revenue")) else None
                    if curr_rev is not None and prev_rev is not None and prev_rev != 0:
                        growth["revenue_growth"] = (curr_rev - prev_rev) / prev_rev * 100
                except (ValueError, TypeError):
                    pass
            
            if not growth.get("profit_growth") and len(raw_data) >= 2:
                try:
                    curr_np = float(raw_data[0].get("net_profit")) if self._is_valid_value(raw_data[0].get("net_profit")) else None
                    prev_np = float(raw_data[1].get("net_profit")) if self._is_valid_value(raw_data[1].get("net_profit")) else None
                    if curr_np is not None and prev_np is not None and prev_np != 0:
                        growth["profit_growth"] = (curr_np - prev_np) / prev_np * 100
                except (ValueError, TypeError):
                    pass
            
            summary["growth"] = growth
            
        except Exception as e:
            self.logger.warning(f"Failed to supplement income data for {code}: {e}")
    
    def get_peer_comparison_analysis(self, code: str, end_date: Optional[str] = None) -> Dict[str, Any]:
        """Get peer comparison analysis for industry benchmarking.
        
        Args:
            code: Stock code
            end_date: Report date in YYYYMMDD format (defaults to latest quarter)
            
        Returns:
            Peer comparison analysis with industry benchmarks
        """
        try:
            # Use latest quarter if no date specified
            if not end_date:
                # Get the most recent quarter end date
                # This is a simplified approach - in production, you'd want more sophisticated date logic
                now = datetime.now()
                if now.month <= 3:
                    end_date = f"{now.year - 1}1231"
                elif now.month <= 6:
                    end_date = f"{now.year}0331"
                elif now.month <= 9:
                    end_date = f"{now.year}0630"
                else:
                    end_date = f"{now.year}0930"
            
            # Get peer comparison
            comparison = self.finace_service.get_peer_comparison(code, end_date)
            
            # Add interpretation
            interpretation = self._interpret_peer_comparison(comparison)
            
            return {
                "code": code,
                "end_date": end_date,
                "comparison": comparison,
                "interpretation": interpretation,
                "status": "success"
            }
            
        except Exception as e:
            self.logger.error(f"Error in peer comparison for {code}: {e}")
            return {
                "code": code,
                "status": "error",
                "error": str(e)
            }
    
    def get_financial_trends(self, code: str, periods: Optional[int] = 8) -> Dict[str, Any]:
        """Get financial trends and time series analysis.
        
        Args:
            code: Stock code
            periods: Number of periods for trend analysis
            
        Returns:
            Financial trends and time series data
        """
        try:
            # Get historical data
            historical_data = self.finace_service.get_latest_indicators(code, periods)
            
            # Get growth rates
            growth_rates = self.finace_service.calculate_growth_rates(code, periods)
            
            # Calculate trend indicators
            trends = self._calculate_trends(historical_data)
            
            return {
                "code": code,
                "periods": len(historical_data),
                "historical_data": historical_data,
                "growth_rates": growth_rates,
                "trends": trends,
                "status": "success"
            }
            
        except Exception as e:
            self.logger.error(f"Error in financial trends for {code}: {e}")
            return {
                "code": code,
                "status": "error",
                "error": str(e)
            }
    
    def get_investment_insights(self, code: str) -> Dict[str, Any]:
        """Generate AI-ready investment insights and analysis points.
        
        Args:
            code: Stock code
            
        Returns:
            Structured investment insights for AI analysis
        """
        try:
            # Get comprehensive data
            comprehensive = self.get_comprehensive_analysis(code)
            peer_comparison = self.get_peer_comparison_analysis(code)
            trends = self.get_financial_trends(code)
            
            # Check if any data retrieval failed
            if comprehensive.get("status") == "error":
                return {
                    "code": code,
                    "status": "error",
                    "error": f"获取综合分析失败: {comprehensive.get('error', '未知错误')}"
                }
            
            if peer_comparison.get("status") == "error":
                return {
                    "code": code,
                    "status": "error",
                    "error": f"获取同业对比失败: {peer_comparison.get('error', '未知错误')}"
                }
            
            if trends.get("status") == "error":
                return {
                    "code": code,
                    "status": "error",
                    "error": f"获取趋势分析失败: {trends.get('error', '未知错误')}"
                }
            
            # Generate structured insights
            insights = {
                "investment_thesis": self._generate_investment_thesis(comprehensive, peer_comparison, trends),
                "risk_factors": self._identify_risk_factors(comprehensive, trends),
                "competitive_position": self._assess_competitive_position(peer_comparison),
                "financial_strength": self._assess_financial_strength(comprehensive),
                "growth_prospects": self._assess_growth_prospects(trends)
            }
            
            return {
                "code": code,
                "insights": insights,
                "data_sources": {
                    "comprehensive": comprehensive,
                    "peer_comparison": peer_comparison,
                    "trends": trends
                },
                "status": "success"
            }
            
        except Exception as e:
            self.logger.error(f"Error generating insights for {code}: {e}")
            return {
                "code": code,
                "status": "error",
                "error": str(e)
            }
    
    def _interpret_peer_comparison(self, comparison: Dict[str, Any]) -> Dict[str, Any]:
        """Interpret peer comparison results."""
        if not comparison.get("comparison"):
            return {"message": "No comparison data available"}
        
        interpretations = {}
        
        for metric, data in comparison["comparison"].items():
            percentile = data.get("percentile_rank", 0)
            target_value = data.get("target_value")
            industry_median = data.get("industry_median")
            
            if percentile >= 75:
                level = "优秀"
            elif percentile >= 50:
                level = "良好"
            elif percentile >= 25:
                level = "一般"
            else:
                level = "较差"
            
            interpretations[metric] = {
                "level": level,
                "percentile": percentile,
                "vs_industry": "高于行业中位数" if target_value and industry_median and target_value > industry_median else "低于行业中位数"
            }
        
        return interpretations
    
    def _calculate_trends(self, historical_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate trend indicators from historical data."""
        if len(historical_data) < 3:
            return {"message": "Insufficient data for trend analysis"}
        
        # Sort by date
        sorted_data = sorted(historical_data, key=lambda x: x.get("end_date", ""))
        
        trends = {}
        metrics = ["roe", "roa", "net_profit_margin", "debt_to_assets", "total_revenue", "net_profit"]
        
        for metric in metrics:
            # Convert values to float and filter out None values
            values = []
            for d in sorted_data:
                val = d.get(metric)
                if val is not None:
                    try:
                        values.append(float(val))
                    except (ValueError, TypeError):
                        continue
            
            if len(values) >= 3:
                # Simple trend analysis
                recent_avg = sum(values[-2:]) / 2 if len(values) >= 2 else values[-1]
                earlier_avg = sum(values[:2]) / 2 if len(values) >= 2 else values[0]
                
                if recent_avg > earlier_avg * 1.1:
                    trend = "上升"
                elif recent_avg < earlier_avg * 0.9:
                    trend = "下降"
                else:
                    trend = "稳定"
                
                trends[metric] = {
                    "trend": trend,
                    "recent_avg": round(recent_avg, 2),
                    "earlier_avg": round(earlier_avg, 2),
                    "change_pct": round(((recent_avg - earlier_avg) / earlier_avg * 100), 2) if earlier_avg != 0 else 0
                }
        
        return trends
    
    def _generate_investment_thesis(self, comprehensive: Dict[str, Any], 
                                  peer_comparison: Dict[str, Any], 
                                  trends: Dict[str, Any]) -> List[str]:
        """Generate investment thesis points."""
        thesis_points = []
        
        # Health score analysis
        health_score = comprehensive.get("health_analysis", {}).get("health_score", 0)
        if health_score >= 70:
            thesis_points.append("公司财务健康状况良好，基本面稳健")
        elif health_score >= 50:
            thesis_points.append("公司财务状况一般，需关注改善趋势")
        else:
            thesis_points.append("公司财务状况存在风险，需谨慎评估")
        
        # Growth analysis
        growth_data = comprehensive.get("summary", {}).get("growth", {})
        if growth_data.get("revenue_growth", 0) > 10:
            thesis_points.append("营收增长强劲，显示良好的业务扩张能力")
        
        # Profitability analysis
        prof_data = comprehensive.get("summary", {}).get("profitability", {})
        if prof_data.get("roe", 0) > 15:
            thesis_points.append("ROE表现优秀，股东回报率较高")
        
        return thesis_points
    
    def _identify_risk_factors(self, comprehensive: Dict[str, Any], 
                             trends: Dict[str, Any]) -> List[str]:
        """Identify key risk factors."""
        risks = []
        
        # From health analysis
        weaknesses = comprehensive.get("health_analysis", {}).get("weaknesses", [])
        risks.extend(weaknesses)
        
        # From trend analysis
        trend_data = trends.get("trends", {})
        for metric, trend_info in trend_data.items():
            if trend_info.get("trend") == "下降" and metric in ["roe", "net_profit_margin", "total_revenue"]:
                risks.append(f"{metric}呈下降趋势")
        
        return risks
    
    def _assess_competitive_position(self, peer_comparison: Dict[str, Any]) -> Dict[str, Any]:
        """Assess competitive position based on peer comparison."""
        interpretation = peer_comparison.get("interpretation", {})
        
        excellent_metrics = sum(1 for m in interpretation.values() if m.get("level") == "优秀")
        good_metrics = sum(1 for m in interpretation.values() if m.get("level") == "良好")
        total_metrics = len(interpretation)
        
        if total_metrics == 0:
            return {"position": "无法评估", "reason": "缺乏对比数据"}
        
        excellent_ratio = excellent_metrics / total_metrics
        good_ratio = (excellent_metrics + good_metrics) / total_metrics
        
        if excellent_ratio >= 0.6:
            position = "行业领先"
        elif good_ratio >= 0.6:
            position = "行业中上游"
        elif good_ratio >= 0.4:
            position = "行业中游"
        else:
            position = "行业下游"
        
        return {
            "position": position,
            "excellent_metrics": excellent_metrics,
            "total_metrics": total_metrics,
            "details": interpretation
        }
    
    def _assess_financial_strength(self, comprehensive: Dict[str, Any]) -> Dict[str, Any]:
        """Assess overall financial strength."""
        health_score = comprehensive.get("health_analysis", {}).get("health_score", 0)
        strengths = comprehensive.get("health_analysis", {}).get("strengths", [])
        
        if health_score >= 80:
            strength_level = "强"
        elif health_score >= 60:
            strength_level = "中等偏强"
        elif health_score >= 40:
            strength_level = "中等"
        else:
            strength_level = "弱"
        
        return {
            "level": strength_level,
            "score": health_score,
            "key_strengths": strengths[:3]  # Top 3 strengths
        }
    
    def _assess_growth_prospects(self, trends: Dict[str, Any]) -> Dict[str, Any]:
        """Assess growth prospects based on trends."""
        trend_data = trends.get("trends", {})
        growth_rates = trends.get("growth_rates", {})
        
        # Count positive trends
        positive_trends = sum(1 for t in trend_data.values() if t.get("trend") == "上升")
        total_trends = len(trend_data)
        
        # Check revenue and profit growth
        revenue_growth = growth_rates.get("total_revenue", {}).get("average_growth", 0)
        profit_growth = growth_rates.get("net_profit", {}).get("average_growth", 0)
        
        if revenue_growth > 15 and profit_growth > 15:
            prospects = "优秀"
        elif revenue_growth > 5 and profit_growth > 5:
            prospects = "良好"
        elif revenue_growth > 0 and profit_growth > 0:
            prospects = "一般"
        else:
            prospects = "较差"
        
        return {
            "prospects": prospects,
            "revenue_growth": revenue_growth,
            "profit_growth": profit_growth,
            "positive_trend_ratio": positive_trends / total_trends if total_trends > 0 else 0
        }
    
    # ========== 新增：三大财务报表查询方法 ==========
    
    def get_income_statement(self, code: str, periods: int = 4, report_type: int = 1) -> Dict[str, Any]:
        """获取利润表数据
        
        Args:
            code: 股票代码
            periods: 期数
            report_type: 报表类型 (1=合并报表, 2=单季合并, 4=调整合并, 6=母公司)
            
        Returns:
            利润表数据
        """
        try:
            data = self.income_service.get_income_statement(
                code=code, periods=periods, report_type=str(report_type)
            )
            return _sanitize_json_data({
                "code": code,
                "report_type": report_type,
                "periods": len(data),
                "data": data,
                "status": "success"
            })
        except Exception as e:
            self.logger.error(f"Error getting income statement for {code}: {e}")
            return {"code": code, "status": "error", "error": str(e)}
    
    def get_balance_sheet(self, code: str, periods: int = 4, report_type: int = 1) -> Dict[str, Any]:
        """获取资产负债表数据
        
        Args:
            code: 股票代码
            periods: 期数
            report_type: 报表类型
            
        Returns:
            资产负债表数据
        """
        try:
            data = self.balancesheet_service.get_balance_sheet(
                code=code, periods=periods, report_type=str(report_type)
            )
            return _sanitize_json_data({
                "code": code,
                "report_type": report_type,
                "periods": len(data),
                "data": data,
                "status": "success"
            })
        except Exception as e:
            self.logger.error(f"Error getting balance sheet for {code}: {e}")
            return {"code": code, "status": "error", "error": str(e)}
    
    def get_cash_flow(self, code: str, periods: int = 4, report_type: int = 1) -> Dict[str, Any]:
        """获取现金流量表数据
        
        Args:
            code: 股票代码
            periods: 期数
            report_type: 报表类型
            
        Returns:
            现金流量表数据
        """
        try:
            data = self.cashflow_service.get_cashflow(
                code=code, periods=periods, report_type=str(report_type)
            )
            return _sanitize_json_data({
                "code": code,
                "report_type": report_type,
                "periods": len(data),
                "data": data,
                "status": "success"
            })
        except Exception as e:
            self.logger.error(f"Error getting cash flow for {code}: {e}")
            return {"code": code, "status": "error", "error": str(e)}
    
    def get_forecast(self, code: str, limit: int = 10) -> Dict[str, Any]:
        """获取业绩预告数据
        
        Args:
            code: 股票代码
            limit: 返回记录数
            
        Returns:
            业绩预告数据
        """
        try:
            data = self.forecast_service.get_forecast(ts_code=code, limit=limit)
            return {
                "code": code,
                "count": len(data),
                "data": data,
                "status": "success"
            }
        except Exception as e:
            self.logger.error(f"Error getting forecast for {code}: {e}")
            return {"code": code, "status": "error", "error": str(e)}
    
    def get_express(self, code: str, limit: int = 10) -> Dict[str, Any]:
        """获取业绩快报数据
        
        Args:
            code: 股票代码
            limit: 返回记录数
            
        Returns:
            业绩快报数据
        """
        try:
            data = self.express_service.get_express(ts_code=code, limit=limit)
            return {
                "code": code,
                "count": len(data),
                "data": data,
                "status": "success"
            }
        except Exception as e:
            self.logger.error(f"Error getting express for {code}: {e}")
            return {"code": code, "status": "error", "error": str(e)}
    
    def get_full_financial_statements(self, code: str, periods: int = 4, report_type: int = 1) -> Dict[str, Any]:
        """获取完整的三大财务报表
        
        Args:
            code: 股票代码
            periods: 期数
            report_type: 报表类型
            
        Returns:
            包含利润表、资产负债表、现金流量表的完整数据
        """
        try:
            income = self.get_income_statement(code, periods, report_type)
            balance = self.get_balance_sheet(code, periods, report_type)
            cashflow = self.get_cash_flow(code, periods, report_type)
            
            return {
                "code": code,
                "report_type": report_type,
                "income_statement": income,
                "balance_sheet": balance,
                "cash_flow": cashflow,
                "status": "success"
            }
        except Exception as e:
            self.logger.error(f"Error getting full statements for {code}: {e}")
            return {"code": code, "status": "error", "error": str(e)}