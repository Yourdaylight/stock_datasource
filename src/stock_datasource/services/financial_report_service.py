"""Financial Report Service for comprehensive financial analysis."""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from stock_datasource.plugins.tushare_finace_indicator.service import TuShareFinaceIndicatorService

logger = logging.getLogger(__name__)


class FinancialReportService:
    """Unified service for financial report analysis and insights."""
    
    def __init__(self):
        """Initialize the financial report service."""
        self.finace_service = TuShareFinaceIndicatorService()
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
            
            # Get growth analysis
            growth_analysis = self.finace_service.calculate_growth_rates(code, periods * 2)
            
            # Get financial health analysis
            health_analysis = self.finace_service.analyze_financial_health(code, periods)
            
            return {
                "code": code,
                "analysis_date": datetime.now().isoformat(),
                "summary": summary,
                "growth_analysis": growth_analysis,
                "health_analysis": health_analysis,
                "status": "success"
            }
            
        except Exception as e:
            self.logger.error(f"Error in comprehensive analysis for {code}: {e}")
            return {
                "code": code,
                "status": "error",
                "error": str(e)
            }
    
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
            values = [d.get(metric) for d in sorted_data if d.get(metric) is not None]
            
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
                    "recent_avg": recent_avg,
                    "earlier_avg": earlier_avg,
                    "change_pct": ((recent_avg - earlier_avg) / earlier_avg * 100) if earlier_avg != 0 else 0
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