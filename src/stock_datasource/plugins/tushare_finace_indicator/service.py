"""Query service for TuShare financial indicators data."""

import re
from typing import List, Dict, Any, Optional
from stock_datasource.core.base_service import BaseService, query_method, QueryParam


class TuShareFinaceIndicatorService(BaseService):
    """Query service for TuShare financial indicators data."""
    
    def __init__(self):
        super().__init__("tushare_finace_indicator")
    
    def _validate_stock_code(self, code: str) -> bool:
        """Validate stock code format to prevent SQL injection."""
        if not isinstance(code, str):
            return False
        # Allow only alphanumeric characters and dots (e.g., 000001.SZ, 600000.SH, 00700.HK)
        pattern = r'^[A-Za-z0-9]{4,6}\.[A-Za-z]{2,3}$'
        return bool(re.match(pattern, code))
    
    def _validate_date_format(self, date_str: str) -> bool:
        """Validate date format (YYYYMMDD)."""
        if not isinstance(date_str, str):
            return False
        return date_str.isdigit() and len(date_str) == 8
    
    def _sanitize_limit(self, limit: Optional[int], default: int = 1000, max_limit: int = 10000) -> int:
        """Sanitize and validate limit parameter."""
        try:
            limit_value = int(limit) if limit is not None else default
        except (TypeError, ValueError):
            limit_value = default
        
        if limit_value <= 0:
            limit_value = default
        elif limit_value > max_limit:
            limit_value = max_limit
            
        return limit_value
    
    @query_method(
        description="Query financial indicators by stock code and date range",
        params=[
            QueryParam(name="code", type="str", description="Stock code (e.g., 002579.SZ)", required=False),
            QueryParam(name="start_date", type="str", description="Start date YYYYMMDD", required=True),
            QueryParam(name="end_date", type="str", description="End date YYYYMMDD", required=True),
            QueryParam(name="limit", type="int", description="Maximum number of records to return", required=False)
        ]
    )
    def get_financial_indicators(self, code: Optional[str] = None, start_date: Optional[str] = None, 
                                end_date: Optional[str] = None, limit: Optional[int] = 1000) -> List[Dict[str, Any]]:
        """Query financial indicators from database using parameterized queries."""
        
        # Input validation
        if not start_date or not end_date:
            raise ValueError("start_date and end_date are required")
        
        if not self._validate_date_format(start_date):
            raise ValueError("start_date must be in YYYYMMDD format")
        
        if not self._validate_date_format(end_date):
            raise ValueError("end_date must be in YYYYMMDD format")
        
        if code and not self._validate_stock_code(code):
            raise ValueError(f"Invalid stock code format: {code}")
        
        # Sanitize limit
        limit_value = self._sanitize_limit(limit)
        
        # Build parameterized query
        query = "SELECT * FROM ods_fina_indicator WHERE 1=1"
        params = {}
        
        if code:
            query += " AND ts_code = %(code)s"
            params['code'] = code
        
        if start_date:
            query += " AND end_date >= %(start_date)s"
            params['start_date'] = start_date
        
        if end_date:
            query += " AND end_date <= %(end_date)s"
            params['end_date'] = end_date
        
        query += " ORDER BY ts_code, end_date DESC LIMIT %(limit)s"
        params['limit'] = str(limit_value)
        
        df = self.db.execute_query(query, params)
        
        # Convert datetime columns to string for JSON serialization
        for col in df.columns:
            if df[col].dtype == 'datetime64[ns]':
                df[col] = df[col].astype(str)
        
        return df.to_dict('records')
    
    @query_method(
        description="Get financial summary with key indicators",
        params=[
            QueryParam(name="code", type="str", description="Stock code (e.g., 002579.SZ)", required=True),
            QueryParam(name="periods", type="int", description="Number of latest periods to return", required=False)
        ]
    )
    def get_financial_summary(self, code: str, periods: Optional[int] = 4) -> Dict[str, Any]:
        """Get comprehensive financial summary for a stock."""
        
        # Input validation
        if not code:
            raise ValueError("code is required")
        
        if not self._validate_stock_code(code):
            raise ValueError(f"Invalid stock code format: {code}")
        
        # Sanitize periods
        periods_value = self._sanitize_limit(periods, default=4, max_limit=20)
        
        # Get latest financial data
        latest_data = self.get_latest_indicators(code, periods_value)
        
        if not latest_data:
            return {
                "code": code,
                "periods": 0,
                "latest_period": None,
                "profitability": {},
                "solvency": {},
                "efficiency": {},
                "growth": {}
            }
        
        # Calculate summary metrics
        latest = latest_data[0]  # Most recent period
        
        # Profitability metrics
        profitability = {
            "roe": latest.get("roe"),
            "roa": latest.get("roa"), 
            "gross_profit_margin": latest.get("gross_profit_margin"),
            "net_profit_margin": latest.get("net_profit_margin"),
            "eps": latest.get("eps")
        }
        
        # Solvency metrics
        solvency = {
            "debt_to_assets": latest.get("debt_to_assets"),
            "debt_to_equity": latest.get("debt_to_equity"),
            "current_ratio": latest.get("current_ratio"),
            "quick_ratio": latest.get("quick_ratio")
        }
        
        # Efficiency metrics
        efficiency = {
            "asset_turnover": latest.get("asset_turnover"),
            "inventory_turnover": latest.get("inventory_turnover"),
            "receivable_turnover": latest.get("receivable_turnover")
        }
        
        # Growth rates (if multiple periods available)
        growth = {}
        if len(latest_data) >= 2:
            current = latest_data[0]
            previous = latest_data[1]
            
            if current.get("total_revenue") and previous.get("total_revenue"):
                growth["revenue_growth"] = ((current["total_revenue"] - previous["total_revenue"]) / 
                                         previous["total_revenue"] * 100)
            
            if current.get("net_profit") and previous.get("net_profit"):
                growth["profit_growth"] = ((current["net_profit"] - previous["net_profit"]) / 
                                         previous["net_profit"] * 100)
        
        return {
            "code": code,
            "periods": len(latest_data),
            "latest_period": latest.get("end_date"),
            "profitability": profitability,
            "solvency": solvency,
            "efficiency": efficiency,
            "growth": growth,
            "raw_data": latest_data
        }
    
    @query_method(
        description="Calculate growth rates for financial indicators",
        params=[
            QueryParam(name="code", type="str", description="Stock code (e.g., 002579.SZ)", required=True),
            QueryParam(name="periods", type="int", description="Number of periods for trend analysis", required=False)
        ]
    )
    def calculate_growth_rates(self, code: str, periods: Optional[int] = 8) -> Dict[str, Any]:
        """Calculate growth rates for key financial indicators."""
        
        # Input validation
        if not code:
            raise ValueError("code is required")
        
        if not self._validate_stock_code(code):
            raise ValueError(f"Invalid stock code format: {code}")
        
        # Get historical data
        historical_data = self.get_latest_indicators(code, periods or 8)
        
        if len(historical_data) < 2:
            return {
                "code": code,
                "message": "Insufficient data for growth calculation",
                "growth_rates": {}
            }
        
        # Sort by date (newest first)
        historical_data.sort(key=lambda x: x.get("end_date", ""), reverse=True)
        
        growth_rates = {}
        metrics = ["total_revenue", "net_profit", "total_assets", "total_equity", "roe", "roa"]
        
        for metric in metrics:
            rates = []
            for i in range(len(historical_data) - 1):
                current = historical_data[i].get(metric)
                previous = historical_data[i + 1].get(metric)
                
                if current is not None and previous is not None and previous != 0:
                    growth_rate = ((current - previous) / abs(previous)) * 100
                    rates.append({
                        "period": historical_data[i].get("end_date"),
                        "rate": round(growth_rate, 2)
                    })
            
            if rates:
                # Calculate average growth rate
                avg_growth = sum(r["rate"] for r in rates) / len(rates)
                growth_rates[metric] = {
                    "average_growth": round(avg_growth, 2),
                    "periods": rates
                }
        
        return {
            "code": code,
            "periods_analyzed": len(historical_data),
            "growth_rates": growth_rates
        }
    
    @query_method(
        description="Get peer comparison data for industry analysis",
        params=[
            QueryParam(name="code", type="str", description="Target stock code", required=True),
            QueryParam(name="end_date", type="str", description="Report date YYYYMMDD", required=True),
            QueryParam(name="industry_limit", type="int", description="Number of peer companies to compare", required=False)
        ]
    )
    def get_peer_comparison(self, code: str, end_date: str, industry_limit: Optional[int] = 20) -> Dict[str, Any]:
        """Get peer comparison data for industry analysis."""
        
        # Input validation
        if not code or not end_date:
            raise ValueError("code and end_date are required")
        
        if not self._validate_stock_code(code):
            raise ValueError(f"Invalid stock code format: {code}")
        
        if not self._validate_date_format(end_date):
            raise ValueError("end_date must be in YYYYMMDD format")
        
        # Sanitize limit
        limit_value = self._sanitize_limit(industry_limit, default=20, max_limit=100)
        
        # Get target company data
        target_query = """
        SELECT * FROM ods_fina_indicator
        WHERE ts_code = %(code)s AND end_date = %(end_date)s
        """
        target_params = {'code': code, 'end_date': end_date}
        target_df = self.db.execute_query(target_query, target_params)
        
        if target_df.empty:
            return {
                "code": code,
                "end_date": end_date,
                "message": "No data found for target company",
                "comparison": {}
            }
        
        target_data = target_df.iloc[0].to_dict()
        
        # Get industry peers (companies with similar market cap or industry)
        # For now, get top performers by ROE as a proxy for industry peers
        peers_query = """
        SELECT ts_code, roe, roa, gross_profit_margin, net_profit_margin, 
               debt_to_assets, current_ratio, total_revenue, net_profit
        FROM ods_fina_indicator
        WHERE end_date = %(end_date)s 
        AND ts_code != %(code)s
        AND roe IS NOT NULL
        ORDER BY roe DESC
        LIMIT %(limit)s
        """
        peers_params = {
            'end_date': end_date,
            'code': code,
            'limit': str(limit_value)
        }
        peers_df = self.db.execute_query(peers_query, peers_params)
        
        if peers_df.empty:
            return {
                "code": code,
                "end_date": end_date,
                "message": "No peer data found",
                "comparison": {}
            }
        
        # Calculate industry statistics
        metrics = ["roe", "roa", "gross_profit_margin", "net_profit_margin", "debt_to_assets", "current_ratio"]
        comparison = {}
        
        for metric in metrics:
            if metric in peers_df.columns:
                peer_values = peers_df[metric].dropna()
                target_value = target_data.get(metric)
                
                if not peer_values.empty and target_value is not None:
                    comparison[metric] = {
                        "target_value": target_value,
                        "industry_median": float(peer_values.median()),
                        "industry_mean": float(peer_values.mean()),
                        "industry_p25": float(peer_values.quantile(0.25)),
                        "industry_p75": float(peer_values.quantile(0.75)),
                        "percentile_rank": float((peer_values < target_value).sum() / len(peer_values) * 100)
                    }
        
        return {
            "code": code,
            "end_date": end_date,
            "peer_count": len(peers_df),
            "comparison": comparison,
            "peer_companies": peers_df[["ts_code", "roe", "roa"]].to_dict('records')[:10]  # Top 10 peers
        }
    
    @query_method(
        description="Analyze financial health and provide insights",
        params=[
            QueryParam(name="code", type="str", description="Stock code (e.g., 002579.SZ)", required=True),
            QueryParam(name="periods", type="int", description="Number of periods to analyze", required=False)
        ]
    )
    def analyze_financial_health(self, code: str, periods: Optional[int] = 4) -> Dict[str, Any]:
        """Analyze financial health and provide structured insights."""
        
        # Input validation
        if not code:
            raise ValueError("code is required")
        
        if not self._validate_stock_code(code):
            raise ValueError(f"Invalid stock code format: {code}")
        
        # Get financial summary
        summary = self.get_financial_summary(code, periods)
        
        if summary["periods"] == 0:
            return {
                "code": code,
                "health_score": 0,
                "analysis": "No financial data available",
                "strengths": [],
                "weaknesses": [],
                "recommendations": []
            }
        
        # Analyze financial health
        strengths = []
        weaknesses = []
        recommendations = []
        health_score = 50  # Base score
        
        # Profitability analysis
        prof = summary["profitability"]
        if prof.get("roe") and prof["roe"] > 15:
            strengths.append(f"优秀的ROE ({prof['roe']:.1f}%)")
            health_score += 10
        elif prof.get("roe") and prof["roe"] < 5:
            weaknesses.append(f"较低的ROE ({prof['roe']:.1f}%)")
            health_score -= 10
        
        if prof.get("net_profit_margin") and prof["net_profit_margin"] > 10:
            strengths.append(f"良好的净利率 ({prof['net_profit_margin']:.1f}%)")
            health_score += 5
        elif prof.get("net_profit_margin") and prof["net_profit_margin"] < 3:
            weaknesses.append(f"净利率偏低 ({prof['net_profit_margin']:.1f}%)")
            health_score -= 5
        
        # Solvency analysis
        solv = summary["solvency"]
        if solv.get("debt_to_assets") and solv["debt_to_assets"] < 0.4:
            strengths.append(f"资产负债率健康 ({solv['debt_to_assets']:.1f}%)")
            health_score += 5
        elif solv.get("debt_to_assets") and solv["debt_to_assets"] > 0.7:
            weaknesses.append(f"资产负债率较高 ({solv['debt_to_assets']:.1f}%)")
            health_score -= 10
        
        if solv.get("current_ratio") and solv["current_ratio"] > 1.5:
            strengths.append(f"流动比率良好 ({solv['current_ratio']:.1f})")
            health_score += 5
        elif solv.get("current_ratio") and solv["current_ratio"] < 1.0:
            weaknesses.append(f"流动比率偏低 ({solv['current_ratio']:.1f})")
            health_score -= 10
        
        # Growth analysis
        growth = summary["growth"]
        if growth.get("revenue_growth") and growth["revenue_growth"] > 10:
            strengths.append(f"营收增长强劲 ({growth['revenue_growth']:.1f}%)")
            health_score += 10
        elif growth.get("revenue_growth") and growth["revenue_growth"] < -5:
            weaknesses.append(f"营收出现下滑 ({growth['revenue_growth']:.1f}%)")
            health_score -= 15
        
        # Generate recommendations
        if weaknesses:
            if any("ROE" in w for w in weaknesses):
                recommendations.append("关注公司盈利能力改善措施")
            if any("负债率" in w for w in weaknesses):
                recommendations.append("关注债务结构优化和偿债能力")
            if any("增长" in w or "下滑" in w for w in weaknesses):
                recommendations.append("关注业务增长策略和市场竞争力")
        
        if not strengths:
            recommendations.append("建议深入分析公司基本面和行业前景")
        
        # Ensure health score is within bounds
        health_score = max(0, min(100, health_score))
        
        return {
            "code": code,
            "health_score": health_score,
            "analysis": f"基于{summary['periods']}期财务数据的健康度分析",
            "strengths": strengths,
            "weaknesses": weaknesses,
            "recommendations": recommendations,
            "summary": summary
        }
    
    @query_method(
        description="Get latest financial indicators for a stock",
        params=[
            QueryParam(name="code", type="str", description="Stock code (e.g., 002579.SZ)", required=True),
            QueryParam(name="periods", type="int", description="Number of latest periods to return", required=False)
        ]
    )
    def get_latest_indicators(self, code: str, periods: Optional[int] = 4) -> List[Dict[str, Any]]:
        """Get latest financial indicators for a specific stock using parameterized queries."""
        
        # Input validation
        if not code:
            raise ValueError("code is required")
        
        if not self._validate_stock_code(code):
            raise ValueError(f"Invalid stock code format: {code}")
        
        # Sanitize periods
        periods_value = self._sanitize_limit(periods, default=4, max_limit=100)
        
        # Parameterized query - LIMIT needs to be hardcoded for ClickHouse
        query = f"""
        SELECT * FROM ods_fina_indicator
        WHERE ts_code = %(code)s
        ORDER BY end_date DESC
        LIMIT {periods_value}
        """
        params = {
            'code': code
        }
        
        df = self.db.execute_query(query, params)
        
        # Convert datetime columns to string for JSON serialization
        for col in df.columns:
            if df[col].dtype == 'datetime64[ns]':
                df[col] = df[col].astype(str)
        
        return df.to_dict('records')
    
    @query_method(
        description="Get financial summary with key indicators",
        params=[
            QueryParam(name="code", type="str", description="Stock code (e.g., 002579.SZ)", required=True),
            QueryParam(name="periods", type="int", description="Number of latest periods to return", required=False)
        ]
    )
    def get_financial_summary(self, code: str, periods: Optional[int] = 4) -> Dict[str, Any]:
        """Get comprehensive financial summary for a stock."""
        
        # Input validation
        if not code:
            raise ValueError("code is required")
        
        if not self._validate_stock_code(code):
            raise ValueError(f"Invalid stock code format: {code}")
        
        # Sanitize periods
        periods_value = self._sanitize_limit(periods, default=4, max_limit=20)
        
        # Get latest financial data
        latest_data = self.get_latest_indicators(code, periods_value)
        
        if not latest_data:
            return {
                "code": code,
                "periods": 0,
                "latest_period": None,
                "profitability": {},
                "solvency": {},
                "efficiency": {},
                "growth": {}
            }
        
        # Calculate summary metrics
        latest = latest_data[0]  # Most recent period
        
        # Profitability metrics
        profitability = {
            "roe": latest.get("roe"),
            "roa": latest.get("roa"), 
            "gross_profit_margin": latest.get("gross_profit_margin"),
            "net_profit_margin": latest.get("net_profit_margin"),
            "eps": latest.get("eps")
        }
        
        # Solvency metrics
        solvency = {
            "debt_to_assets": latest.get("debt_to_assets"),
            "debt_to_equity": latest.get("debt_to_equity"),
            "current_ratio": latest.get("current_ratio"),
            "quick_ratio": latest.get("quick_ratio")
        }
        
        # Efficiency metrics
        efficiency = {
            "asset_turnover": latest.get("asset_turnover"),
            "inventory_turnover": latest.get("inventory_turnover"),
            "receivable_turnover": latest.get("receivable_turnover")
        }
        
        # Growth rates (if multiple periods available)
        growth = {}
        if len(latest_data) >= 2:
            current = latest_data[0]
            previous = latest_data[1]
            
            if current.get("total_revenue") and previous.get("total_revenue"):
                growth["revenue_growth"] = ((current["total_revenue"] - previous["total_revenue"]) / 
                                         previous["total_revenue"] * 100)
            
            if current.get("net_profit") and previous.get("net_profit"):
                growth["profit_growth"] = ((current["net_profit"] - previous["net_profit"]) / 
                                         previous["net_profit"] * 100)
        
        return {
            "code": code,
            "periods": len(latest_data),
            "latest_period": latest.get("end_date"),
            "profitability": profitability,
            "solvency": solvency,
            "efficiency": efficiency,
            "growth": growth,
            "raw_data": latest_data
        }
    
    @query_method(
        description="Calculate growth rates for financial indicators",
        params=[
            QueryParam(name="code", type="str", description="Stock code (e.g., 002579.SZ)", required=True),
            QueryParam(name="periods", type="int", description="Number of periods for trend analysis", required=False)
        ]
    )
    def calculate_growth_rates(self, code: str, periods: Optional[int] = 8) -> Dict[str, Any]:
        """Calculate growth rates for key financial indicators."""
        
        # Input validation
        if not code:
            raise ValueError("code is required")
        
        if not self._validate_stock_code(code):
            raise ValueError(f"Invalid stock code format: {code}")
        
        # Get historical data
        historical_data = self.get_latest_indicators(code, periods or 8)
        
        if len(historical_data) < 2:
            return {
                "code": code,
                "message": "Insufficient data for growth calculation",
                "growth_rates": {}
            }
        
        # Sort by date (newest first)
        historical_data.sort(key=lambda x: x.get("end_date", ""), reverse=True)
        
        growth_rates = {}
        metrics = ["total_revenue", "net_profit", "total_assets", "total_equity", "roe", "roa"]
        
        for metric in metrics:
            rates = []
            for i in range(len(historical_data) - 1):
                current = historical_data[i].get(metric)
                previous = historical_data[i + 1].get(metric)
                
                if current is not None and previous is not None and previous != 0:
                    growth_rate = ((current - previous) / abs(previous)) * 100
                    rates.append({
                        "period": historical_data[i].get("end_date"),
                        "rate": round(growth_rate, 2)
                    })
            
            if rates:
                # Calculate average growth rate
                avg_growth = sum(r["rate"] for r in rates) / len(rates)
                growth_rates[metric] = {
                    "average_growth": round(avg_growth, 2),
                    "periods": rates
                }
        
        return {
            "code": code,
            "periods_analyzed": len(historical_data),
            "growth_rates": growth_rates
        }
    
    @query_method(
        description="Get peer comparison data for industry analysis",
        params=[
            QueryParam(name="code", type="str", description="Target stock code", required=True),
            QueryParam(name="end_date", type="str", description="Report date YYYYMMDD", required=True),
            QueryParam(name="industry_limit", type="int", description="Number of peer companies to compare", required=False)
        ]
    )
    def get_peer_comparison(self, code: str, end_date: str, industry_limit: Optional[int] = 20) -> Dict[str, Any]:
        """Get peer comparison data for industry analysis."""
        
        # Input validation
        if not code or not end_date:
            raise ValueError("code and end_date are required")
        
        if not self._validate_stock_code(code):
            raise ValueError(f"Invalid stock code format: {code}")
        
        if not self._validate_date_format(end_date):
            raise ValueError("end_date must be in YYYYMMDD format")
        
        # Sanitize limit
        limit_value = self._sanitize_limit(industry_limit, default=20, max_limit=100)
        
        # Get target company data
        target_query = """
        SELECT * FROM ods_fina_indicator
        WHERE ts_code = %(code)s AND end_date = %(end_date)s
        """
        target_params = {'code': code, 'end_date': end_date}
        target_df = self.db.execute_query(target_query, target_params)
        
        if target_df.empty:
            return {
                "code": code,
                "end_date": end_date,
                "message": "No data found for target company",
                "comparison": {}
            }
        
        target_data = target_df.iloc[0].to_dict()
        
        # Get industry peers (companies with similar market cap or industry)
        # For now, get top performers by ROE as a proxy for industry peers
        peers_query = """
        SELECT ts_code, roe, roa, gross_profit_margin, net_profit_margin, 
               debt_to_assets, current_ratio, total_revenue, net_profit
        FROM ods_fina_indicator
        WHERE end_date = %(end_date)s 
        AND ts_code != %(code)s
        AND roe IS NOT NULL
        ORDER BY roe DESC
        LIMIT %(limit)s
        """
        peers_params = {
            'end_date': end_date,
            'code': code,
            'limit': str(limit_value)
        }
        peers_df = self.db.execute_query(peers_query, peers_params)
        
        if peers_df.empty:
            return {
                "code": code,
                "end_date": end_date,
                "message": "No peer data found",
                "comparison": {}
            }
        
        # Calculate industry statistics
        metrics = ["roe", "roa", "gross_profit_margin", "net_profit_margin", "debt_to_assets", "current_ratio"]
        comparison = {}
        
        for metric in metrics:
            if metric in peers_df.columns:
                peer_values = peers_df[metric].dropna()
                target_value = target_data.get(metric)
                
                if not peer_values.empty and target_value is not None:
                    comparison[metric] = {
                        "target_value": target_value,
                        "industry_median": float(peer_values.median()),
                        "industry_mean": float(peer_values.mean()),
                        "industry_p25": float(peer_values.quantile(0.25)),
                        "industry_p75": float(peer_values.quantile(0.75)),
                        "percentile_rank": float((peer_values < target_value).sum() / len(peer_values) * 100)
                    }
        
        return {
            "code": code,
            "end_date": end_date,
            "peer_count": len(peers_df),
            "comparison": comparison,
            "peer_companies": peers_df[["ts_code", "roe", "roa"]].to_dict('records')[:10]  # Top 10 peers
        }
    
    @query_method(
        description="Analyze financial health and provide insights",
        params=[
            QueryParam(name="code", type="str", description="Stock code (e.g., 002579.SZ)", required=True),
            QueryParam(name="periods", type="int", description="Number of periods to analyze", required=False)
        ]
    )
    def analyze_financial_health(self, code: str, periods: Optional[int] = 4) -> Dict[str, Any]:
        """Analyze financial health and provide structured insights."""
        
        # Input validation
        if not code:
            raise ValueError("code is required")
        
        if not self._validate_stock_code(code):
            raise ValueError(f"Invalid stock code format: {code}")
        
        # Get financial summary
        summary = self.get_financial_summary(code, periods)
        
        if summary["periods"] == 0:
            return {
                "code": code,
                "health_score": 0,
                "analysis": "No financial data available",
                "strengths": [],
                "weaknesses": [],
                "recommendations": []
            }
        
        # Analyze financial health
        strengths = []
        weaknesses = []
        recommendations = []
        health_score = 50  # Base score
        
        # Profitability analysis
        prof = summary["profitability"]
        if prof.get("roe") and prof["roe"] > 15:
            strengths.append(f"优秀的ROE ({prof['roe']:.1f}%)")
            health_score += 10
        elif prof.get("roe") and prof["roe"] < 5:
            weaknesses.append(f"较低的ROE ({prof['roe']:.1f}%)")
            health_score -= 10
        
        if prof.get("net_profit_margin") and prof["net_profit_margin"] > 10:
            strengths.append(f"良好的净利率 ({prof['net_profit_margin']:.1f}%)")
            health_score += 5
        elif prof.get("net_profit_margin") and prof["net_profit_margin"] < 3:
            weaknesses.append(f"净利率偏低 ({prof['net_profit_margin']:.1f}%)")
            health_score -= 5
        
        # Solvency analysis
        solv = summary["solvency"]
        if solv.get("debt_to_assets") and solv["debt_to_assets"] < 0.4:
            strengths.append(f"资产负债率健康 ({solv['debt_to_assets']:.1f}%)")
            health_score += 5
        elif solv.get("debt_to_assets") and solv["debt_to_assets"] > 0.7:
            weaknesses.append(f"资产负债率较高 ({solv['debt_to_assets']:.1f}%)")
            health_score -= 10
        
        if solv.get("current_ratio") and solv["current_ratio"] > 1.5:
            strengths.append(f"流动比率良好 ({solv['current_ratio']:.1f})")
            health_score += 5
        elif solv.get("current_ratio") and solv["current_ratio"] < 1.0:
            weaknesses.append(f"流动比率偏低 ({solv['current_ratio']:.1f})")
            health_score -= 10
        
        # Growth analysis
        growth = summary["growth"]
        if growth.get("revenue_growth") and growth["revenue_growth"] > 10:
            strengths.append(f"营收增长强劲 ({growth['revenue_growth']:.1f}%)")
            health_score += 10
        elif growth.get("revenue_growth") and growth["revenue_growth"] < -5:
            weaknesses.append(f"营收出现下滑 ({growth['revenue_growth']:.1f}%)")
            health_score -= 15
        
        # Generate recommendations
        if weaknesses:
            if any("ROE" in w for w in weaknesses):
                recommendations.append("关注公司盈利能力改善措施")
            if any("负债率" in w for w in weaknesses):
                recommendations.append("关注债务结构优化和偿债能力")
            if any("增长" in w or "下滑" in w for w in weaknesses):
                recommendations.append("关注业务增长策略和市场竞争力")
        
        if not strengths:
            recommendations.append("建议深入分析公司基本面和行业前景")
        
        # Ensure health score is within bounds
        health_score = max(0, min(100, health_score))
        
        return {
            "code": code,
            "health_score": health_score,
            "analysis": f"基于{summary['periods']}期财务数据的健康度分析",
            "strengths": strengths,
            "weaknesses": weaknesses,
            "recommendations": recommendations,
            "summary": summary
        }
    
    @query_method(
        description="Get financial indicators summary by date",
        params=[
            QueryParam(name="end_date", type="str", description="Report date YYYYMMDD", required=True),
            QueryParam(name="min_roe", type="float", description="Minimum ROE filter", required=False),
            QueryParam(name="max_roe", type="float", description="Maximum ROE filter", required=False),
            QueryParam(name="limit", type="int", description="Maximum number of records", required=False)
        ]
    )
    def get_indicators_by_date(self, end_date: str, min_roe: Optional[float] = None, 
                             max_roe: Optional[float] = None, limit: Optional[int] = 1000) -> List[Dict[str, Any]]:
        """Get financial indicators for all stocks on a specific report date using parameterized queries."""
        
        # Input validation
        if not end_date:
            raise ValueError("end_date is required")
        
        if not self._validate_date_format(end_date):
            raise ValueError("end_date must be in YYYYMMDD format")
        
        # Validate ROE values
        if min_roe is not None and (not isinstance(min_roe, (int, float)) or min_roe < -100 or min_roe > 1000):
            raise ValueError("min_roe must be a number between -100 and 1000")
        
        if max_roe is not None and (not isinstance(max_roe, (int, float)) or max_roe < -100 or max_roe > 1000):
            raise ValueError("max_roe must be a number between -100 and 1000")
        
        if min_roe is not None and max_roe is not None and min_roe > max_roe:
            raise ValueError("min_roe cannot be greater than max_roe")
        
        # Sanitize limit
        limit_value = self._sanitize_limit(limit)
        
        # Build parameterized query
        query = "SELECT * FROM ods_fina_indicator WHERE end_date = %(end_date)s"
        params = {'end_date': end_date}
        
        if min_roe is not None:
            query += " AND roe >= %(min_roe)s"
            params['min_roe'] = str(min_roe)
        
        if max_roe is not None:
            query += " AND roe <= %(max_roe)s"
            params['max_roe'] = str(max_roe)
        
        query += " ORDER BY roe DESC NULLS LAST LIMIT %(limit)s"
        params['limit'] = str(limit_value)
        
        df = self.db.execute_query(query, params)
        
        # Convert datetime columns to string for JSON serialization
        for col in df.columns:
            if df[col].dtype == 'datetime64[ns]':
                df[col] = df[col].astype(str)
        
        return df.to_dict('records')
    
    @query_method(
        description="Get financial summary with key indicators",
        params=[
            QueryParam(name="code", type="str", description="Stock code (e.g., 002579.SZ)", required=True),
            QueryParam(name="periods", type="int", description="Number of latest periods to return", required=False)
        ]
    )
    def get_financial_summary(self, code: str, periods: Optional[int] = 4) -> Dict[str, Any]:
        """Get comprehensive financial summary for a stock."""
        
        # Input validation
        if not code:
            raise ValueError("code is required")
        
        if not self._validate_stock_code(code):
            raise ValueError(f"Invalid stock code format: {code}")
        
        # Sanitize periods
        periods_value = self._sanitize_limit(periods, default=4, max_limit=20)
        
        # Get latest financial data
        latest_data = self.get_latest_indicators(code, periods_value)
        
        if not latest_data:
            return {
                "code": code,
                "periods": 0,
                "latest_period": None,
                "profitability": {},
                "solvency": {},
                "efficiency": {},
                "growth": {}
            }
        
        # Calculate summary metrics
        latest = latest_data[0]  # Most recent period
        
        # Profitability metrics
        profitability = {
            "roe": latest.get("roe"),
            "roa": latest.get("roa"), 
            "gross_profit_margin": latest.get("gross_profit_margin"),
            "net_profit_margin": latest.get("net_profit_margin"),
            "eps": latest.get("eps")
        }
        
        # Solvency metrics
        solvency = {
            "debt_to_assets": latest.get("debt_to_assets"),
            "debt_to_equity": latest.get("debt_to_equity"),
            "current_ratio": latest.get("current_ratio"),
            "quick_ratio": latest.get("quick_ratio")
        }
        
        # Efficiency metrics
        efficiency = {
            "asset_turnover": latest.get("asset_turnover"),
            "inventory_turnover": latest.get("inventory_turnover"),
            "receivable_turnover": latest.get("receivable_turnover")
        }
        
        # Growth rates (if multiple periods available)
        growth = {}
        if len(latest_data) >= 2:
            current = latest_data[0]
            previous = latest_data[1]
            
            if current.get("total_revenue") and previous.get("total_revenue"):
                growth["revenue_growth"] = ((current["total_revenue"] - previous["total_revenue"]) / 
                                         previous["total_revenue"] * 100)
            
            if current.get("net_profit") and previous.get("net_profit"):
                growth["profit_growth"] = ((current["net_profit"] - previous["net_profit"]) / 
                                         previous["net_profit"] * 100)
        
        return {
            "code": code,
            "periods": len(latest_data),
            "latest_period": latest.get("end_date"),
            "profitability": profitability,
            "solvency": solvency,
            "efficiency": efficiency,
            "growth": growth,
            "raw_data": latest_data
        }
    
    @query_method(
        description="Calculate growth rates for financial indicators",
        params=[
            QueryParam(name="code", type="str", description="Stock code (e.g., 002579.SZ)", required=True),
            QueryParam(name="periods", type="int", description="Number of periods for trend analysis", required=False)
        ]
    )
    def calculate_growth_rates(self, code: str, periods: Optional[int] = 8) -> Dict[str, Any]:
        """Calculate growth rates for key financial indicators."""
        
        # Input validation
        if not code:
            raise ValueError("code is required")
        
        if not self._validate_stock_code(code):
            raise ValueError(f"Invalid stock code format: {code}")
        
        # Get historical data
        historical_data = self.get_latest_indicators(code, periods or 8)
        
        if len(historical_data) < 2:
            return {
                "code": code,
                "message": "Insufficient data for growth calculation",
                "growth_rates": {}
            }
        
        # Sort by date (newest first)
        historical_data.sort(key=lambda x: x.get("end_date", ""), reverse=True)
        
        growth_rates = {}
        metrics = ["total_revenue", "net_profit", "total_assets", "total_equity", "roe", "roa"]
        
        for metric in metrics:
            rates = []
            for i in range(len(historical_data) - 1):
                current = historical_data[i].get(metric)
                previous = historical_data[i + 1].get(metric)
                
                if current is not None and previous is not None and previous != 0:
                    growth_rate = ((current - previous) / abs(previous)) * 100
                    rates.append({
                        "period": historical_data[i].get("end_date"),
                        "rate": round(growth_rate, 2)
                    })
            
            if rates:
                # Calculate average growth rate
                avg_growth = sum(r["rate"] for r in rates) / len(rates)
                growth_rates[metric] = {
                    "average_growth": round(avg_growth, 2),
                    "periods": rates
                }
        
        return {
            "code": code,
            "periods_analyzed": len(historical_data),
            "growth_rates": growth_rates
        }
    
    @query_method(
        description="Get peer comparison data for industry analysis",
        params=[
            QueryParam(name="code", type="str", description="Target stock code", required=True),
            QueryParam(name="end_date", type="str", description="Report date YYYYMMDD", required=True),
            QueryParam(name="industry_limit", type="int", description="Number of peer companies to compare", required=False)
        ]
    )
    def get_peer_comparison(self, code: str, end_date: str, industry_limit: Optional[int] = 20) -> Dict[str, Any]:
        """Get peer comparison data for industry analysis."""
        
        # Input validation
        if not code or not end_date:
            raise ValueError("code and end_date are required")
        
        if not self._validate_stock_code(code):
            raise ValueError(f"Invalid stock code format: {code}")
        
        if not self._validate_date_format(end_date):
            raise ValueError("end_date must be in YYYYMMDD format")
        
        # Sanitize limit
        limit_value = self._sanitize_limit(industry_limit, default=20, max_limit=100)
        
        # Get target company data
        target_query = """
        SELECT * FROM ods_fina_indicator
        WHERE ts_code = %(code)s AND end_date = %(end_date)s
        """
        target_params = {'code': code, 'end_date': end_date}
        target_df = self.db.execute_query(target_query, target_params)
        
        if target_df.empty:
            return {
                "code": code,
                "end_date": end_date,
                "message": "No data found for target company",
                "comparison": {}
            }
        
        target_data = target_df.iloc[0].to_dict()
        
        # Get industry peers (companies with similar market cap or industry)
        # For now, get top performers by ROE as a proxy for industry peers
        peers_query = """
        SELECT ts_code, roe, roa, gross_profit_margin, net_profit_margin, 
               debt_to_assets, current_ratio, total_revenue, net_profit
        FROM ods_fina_indicator
        WHERE end_date = %(end_date)s 
        AND ts_code != %(code)s
        AND roe IS NOT NULL
        ORDER BY roe DESC
        LIMIT %(limit)s
        """
        peers_params = {
            'end_date': end_date,
            'code': code,
            'limit': str(limit_value)
        }
        peers_df = self.db.execute_query(peers_query, peers_params)
        
        if peers_df.empty:
            return {
                "code": code,
                "end_date": end_date,
                "message": "No peer data found",
                "comparison": {}
            }
        
        # Calculate industry statistics
        metrics = ["roe", "roa", "gross_profit_margin", "net_profit_margin", "debt_to_assets", "current_ratio"]
        comparison = {}
        
        for metric in metrics:
            if metric in peers_df.columns:
                peer_values = peers_df[metric].dropna()
                target_value = target_data.get(metric)
                
                if not peer_values.empty and target_value is not None:
                    comparison[metric] = {
                        "target_value": target_value,
                        "industry_median": float(peer_values.median()),
                        "industry_mean": float(peer_values.mean()),
                        "industry_p25": float(peer_values.quantile(0.25)),
                        "industry_p75": float(peer_values.quantile(0.75)),
                        "percentile_rank": float((peer_values < target_value).sum() / len(peer_values) * 100)
                    }
        
        return {
            "code": code,
            "end_date": end_date,
            "peer_count": len(peers_df),
            "comparison": comparison,
            "peer_companies": peers_df[["ts_code", "roe", "roa"]].to_dict('records')[:10]  # Top 10 peers
        }
    
    @query_method(
        description="Analyze financial health and provide insights",
        params=[
            QueryParam(name="code", type="str", description="Stock code (e.g., 002579.SZ)", required=True),
            QueryParam(name="periods", type="int", description="Number of periods to analyze", required=False)
        ]
    )
    def analyze_financial_health(self, code: str, periods: Optional[int] = 4) -> Dict[str, Any]:
        """Analyze financial health and provide structured insights."""
        
        # Input validation
        if not code:
            raise ValueError("code is required")
        
        if not self._validate_stock_code(code):
            raise ValueError(f"Invalid stock code format: {code}")
        
        # Get financial summary
        summary = self.get_financial_summary(code, periods)
        
        if summary["periods"] == 0:
            return {
                "code": code,
                "health_score": 0,
                "analysis": "No financial data available",
                "strengths": [],
                "weaknesses": [],
                "recommendations": []
            }
        
        # Analyze financial health
        strengths = []
        weaknesses = []
        recommendations = []
        health_score = 50  # Base score
        
        # Profitability analysis
        prof = summary["profitability"]
        if prof.get("roe") and prof["roe"] > 15:
            strengths.append(f"优秀的ROE ({prof['roe']:.1f}%)")
            health_score += 10
        elif prof.get("roe") and prof["roe"] < 5:
            weaknesses.append(f"较低的ROE ({prof['roe']:.1f}%)")
            health_score -= 10
        
        if prof.get("net_profit_margin") and prof["net_profit_margin"] > 10:
            strengths.append(f"良好的净利率 ({prof['net_profit_margin']:.1f}%)")
            health_score += 5
        elif prof.get("net_profit_margin") and prof["net_profit_margin"] < 3:
            weaknesses.append(f"净利率偏低 ({prof['net_profit_margin']:.1f}%)")
            health_score -= 5
        
        # Solvency analysis
        solv = summary["solvency"]
        if solv.get("debt_to_assets") and solv["debt_to_assets"] < 0.4:
            strengths.append(f"资产负债率健康 ({solv['debt_to_assets']:.1f}%)")
            health_score += 5
        elif solv.get("debt_to_assets") and solv["debt_to_assets"] > 0.7:
            weaknesses.append(f"资产负债率较高 ({solv['debt_to_assets']:.1f}%)")
            health_score -= 10
        
        if solv.get("current_ratio") and solv["current_ratio"] > 1.5:
            strengths.append(f"流动比率良好 ({solv['current_ratio']:.1f})")
            health_score += 5
        elif solv.get("current_ratio") and solv["current_ratio"] < 1.0:
            weaknesses.append(f"流动比率偏低 ({solv['current_ratio']:.1f})")
            health_score -= 10
        
        # Growth analysis
        growth = summary["growth"]
        if growth.get("revenue_growth") and growth["revenue_growth"] > 10:
            strengths.append(f"营收增长强劲 ({growth['revenue_growth']:.1f}%)")
            health_score += 10
        elif growth.get("revenue_growth") and growth["revenue_growth"] < -5:
            weaknesses.append(f"营收出现下滑 ({growth['revenue_growth']:.1f}%)")
            health_score -= 15
        
        # Generate recommendations
        if weaknesses:
            if any("ROE" in w for w in weaknesses):
                recommendations.append("关注公司盈利能力改善措施")
            if any("负债率" in w for w in weaknesses):
                recommendations.append("关注债务结构优化和偿债能力")
            if any("增长" in w or "下滑" in w for w in weaknesses):
                recommendations.append("关注业务增长策略和市场竞争力")
        
        if not strengths:
            recommendations.append("建议深入分析公司基本面和行业前景")
        
        # Ensure health score is within bounds
        health_score = max(0, min(100, health_score))
        
        return {
            "code": code,
            "health_score": health_score,
            "analysis": f"基于{summary['periods']}期财务数据的健康度分析",
            "strengths": strengths,
            "weaknesses": weaknesses,
            "recommendations": recommendations,
            "summary": summary
        }
    
    @query_method(
        description="Get ROE trend for a stock",
        params=[
            QueryParam(name="code", type="str", description="Stock code", required=True),
            QueryParam(name="periods", type="int", description="Number of periods", required=False)
        ]
    )
    def get_roe_trend(self, code: str, periods: Optional[int] = 8) -> List[Dict[str, Any]]:
        """Get ROE trend for a specific stock using parameterized queries."""
        
        # Input validation
        if not code:
            raise ValueError("code is required")
        
        if not self._validate_stock_code(code):
            raise ValueError(f"Invalid stock code format: {code}")
        
        # Sanitize periods
        periods_value = self._sanitize_limit(periods, default=8, max_limit=100)
        
        # Parameterized query - LIMIT needs to be hardcoded for ClickHouse
        query = f"""
        SELECT 
            end_date,
            roe,
            net_profit_margin,
            asset_turnover
        FROM ods_fina_indicator
        WHERE ts_code = %(code)s
        ORDER BY end_date DESC
        LIMIT {periods_value}
        """
        params = {
            'code': code
        }
        
        df = self.db.execute_query(query, params)
        
        # Convert datetime columns to string for JSON serialization
        for col in df.columns:
            if df[col].dtype == 'datetime64[ns]':
                df[col] = df[col].astype(str)
        
        return df.to_dict('records')
    
    @query_method(
        description="Get financial summary with key indicators",
        params=[
            QueryParam(name="code", type="str", description="Stock code (e.g., 002579.SZ)", required=True),
            QueryParam(name="periods", type="int", description="Number of latest periods to return", required=False)
        ]
    )
    def get_financial_summary(self, code: str, periods: Optional[int] = 4) -> Dict[str, Any]:
        """Get comprehensive financial summary for a stock."""
        
        # Input validation
        if not code:
            raise ValueError("code is required")
        
        if not self._validate_stock_code(code):
            raise ValueError(f"Invalid stock code format: {code}")
        
        # Sanitize periods
        periods_value = self._sanitize_limit(periods, default=4, max_limit=20)
        
        # Get latest financial data
        latest_data = self.get_latest_indicators(code, periods_value)
        
        if not latest_data:
            return {
                "code": code,
                "periods": 0,
                "latest_period": None,
                "profitability": {},
                "solvency": {},
                "efficiency": {},
                "growth": {}
            }
        
        # Calculate summary metrics
        latest = latest_data[0]  # Most recent period
        
        # Profitability metrics
        profitability = {
            "roe": latest.get("roe"),
            "roa": latest.get("roa"), 
            "gross_profit_margin": latest.get("gross_profit_margin"),
            "net_profit_margin": latest.get("net_profit_margin"),
            "eps": latest.get("eps")
        }
        
        # Solvency metrics
        solvency = {
            "debt_to_assets": latest.get("debt_to_assets"),
            "debt_to_equity": latest.get("debt_to_equity"),
            "current_ratio": latest.get("current_ratio"),
            "quick_ratio": latest.get("quick_ratio")
        }
        
        # Efficiency metrics
        efficiency = {
            "asset_turnover": latest.get("asset_turnover"),
            "inventory_turnover": latest.get("inventory_turnover"),
            "receivable_turnover": latest.get("receivable_turnover")
        }
        
        # Growth rates (if multiple periods available)
        growth = {}
        if len(latest_data) >= 2:
            current = latest_data[0]
            previous = latest_data[1]
            
            if current.get("total_revenue") and previous.get("total_revenue"):
                growth["revenue_growth"] = ((current["total_revenue"] - previous["total_revenue"]) / 
                                         previous["total_revenue"] * 100)
            
            if current.get("net_profit") and previous.get("net_profit"):
                growth["profit_growth"] = ((current["net_profit"] - previous["net_profit"]) / 
                                         previous["net_profit"] * 100)
        
        return {
            "code": code,
            "periods": len(latest_data),
            "latest_period": latest.get("end_date"),
            "profitability": profitability,
            "solvency": solvency,
            "efficiency": efficiency,
            "growth": growth,
            "raw_data": latest_data
        }
    
    @query_method(
        description="Calculate growth rates for financial indicators",
        params=[
            QueryParam(name="code", type="str", description="Stock code (e.g., 002579.SZ)", required=True),
            QueryParam(name="periods", type="int", description="Number of periods for trend analysis", required=False)
        ]
    )
    def calculate_growth_rates(self, code: str, periods: Optional[int] = 8) -> Dict[str, Any]:
        """Calculate growth rates for key financial indicators."""
        
        # Input validation
        if not code:
            raise ValueError("code is required")
        
        if not self._validate_stock_code(code):
            raise ValueError(f"Invalid stock code format: {code}")
        
        # Get historical data
        historical_data = self.get_latest_indicators(code, periods or 8)
        
        if len(historical_data) < 2:
            return {
                "code": code,
                "message": "Insufficient data for growth calculation",
                "growth_rates": {}
            }
        
        # Sort by date (newest first)
        historical_data.sort(key=lambda x: x.get("end_date", ""), reverse=True)
        
        growth_rates = {}
        metrics = ["total_revenue", "net_profit", "total_assets", "total_equity", "roe", "roa"]
        
        for metric in metrics:
            rates = []
            for i in range(len(historical_data) - 1):
                current = historical_data[i].get(metric)
                previous = historical_data[i + 1].get(metric)
                
                if current is not None and previous is not None and previous != 0:
                    growth_rate = ((current - previous) / abs(previous)) * 100
                    rates.append({
                        "period": historical_data[i].get("end_date"),
                        "rate": round(growth_rate, 2)
                    })
            
            if rates:
                # Calculate average growth rate
                avg_growth = sum(r["rate"] for r in rates) / len(rates)
                growth_rates[metric] = {
                    "average_growth": round(avg_growth, 2),
                    "periods": rates
                }
        
        return {
            "code": code,
            "periods_analyzed": len(historical_data),
            "growth_rates": growth_rates
        }
    
    @query_method(
        description="Get peer comparison data for industry analysis",
        params=[
            QueryParam(name="code", type="str", description="Target stock code", required=True),
            QueryParam(name="end_date", type="str", description="Report date YYYYMMDD", required=True),
            QueryParam(name="industry_limit", type="int", description="Number of peer companies to compare", required=False)
        ]
    )
    def get_peer_comparison(self, code: str, end_date: str, industry_limit: Optional[int] = 20) -> Dict[str, Any]:
        """Get peer comparison data for industry analysis."""
        
        # Input validation
        if not code or not end_date:
            raise ValueError("code and end_date are required")
        
        if not self._validate_stock_code(code):
            raise ValueError(f"Invalid stock code format: {code}")
        
        if not self._validate_date_format(end_date):
            raise ValueError("end_date must be in YYYYMMDD format")
        
        # Sanitize limit
        limit_value = self._sanitize_limit(industry_limit, default=20, max_limit=100)
        
        # Get target company data
        target_query = """
        SELECT * FROM ods_fina_indicator
        WHERE ts_code = %(code)s AND end_date = %(end_date)s
        """
        target_params = {'code': code, 'end_date': end_date}
        target_df = self.db.execute_query(target_query, target_params)
        
        if target_df.empty:
            return {
                "code": code,
                "end_date": end_date,
                "message": "No data found for target company",
                "comparison": {}
            }
        
        target_data = target_df.iloc[0].to_dict()
        
        # Get industry peers (companies with similar market cap or industry)
        # For now, get top performers by ROE as a proxy for industry peers
        peers_query = """
        SELECT ts_code, roe, roa, gross_profit_margin, net_profit_margin, 
               debt_to_assets, current_ratio, total_revenue, net_profit
        FROM ods_fina_indicator
        WHERE end_date = %(end_date)s 
        AND ts_code != %(code)s
        AND roe IS NOT NULL
        ORDER BY roe DESC
        LIMIT %(limit)s
        """
        peers_params = {
            'end_date': end_date,
            'code': code,
            'limit': str(limit_value)
        }
        peers_df = self.db.execute_query(peers_query, peers_params)
        
        if peers_df.empty:
            return {
                "code": code,
                "end_date": end_date,
                "message": "No peer data found",
                "comparison": {}
            }
        
        # Calculate industry statistics
        metrics = ["roe", "roa", "gross_profit_margin", "net_profit_margin", "debt_to_assets", "current_ratio"]
        comparison = {}
        
        for metric in metrics:
            if metric in peers_df.columns:
                peer_values = peers_df[metric].dropna()
                target_value = target_data.get(metric)
                
                if not peer_values.empty and target_value is not None:
                    comparison[metric] = {
                        "target_value": target_value,
                        "industry_median": float(peer_values.median()),
                        "industry_mean": float(peer_values.mean()),
                        "industry_p25": float(peer_values.quantile(0.25)),
                        "industry_p75": float(peer_values.quantile(0.75)),
                        "percentile_rank": float((peer_values < target_value).sum() / len(peer_values) * 100)
                    }
        
        return {
            "code": code,
            "end_date": end_date,
            "peer_count": len(peers_df),
            "comparison": comparison,
            "peer_companies": peers_df[["ts_code", "roe", "roa"]].to_dict('records')[:10]  # Top 10 peers
        }
    
    @query_method(
        description="Analyze financial health and provide insights",
        params=[
            QueryParam(name="code", type="str", description="Stock code (e.g., 002579.SZ)", required=True),
            QueryParam(name="periods", type="int", description="Number of periods to analyze", required=False)
        ]
    )
    def analyze_financial_health(self, code: str, periods: Optional[int] = 4) -> Dict[str, Any]:
        """Analyze financial health and provide structured insights."""
        
        # Input validation
        if not code:
            raise ValueError("code is required")
        
        if not self._validate_stock_code(code):
            raise ValueError(f"Invalid stock code format: {code}")
        
        # Get financial summary
        summary = self.get_financial_summary(code, periods)
        
        if summary["periods"] == 0:
            return {
                "code": code,
                "health_score": 0,
                "analysis": "No financial data available",
                "strengths": [],
                "weaknesses": [],
                "recommendations": []
            }
        
        # Analyze financial health
        strengths = []
        weaknesses = []
        recommendations = []
        health_score = 50  # Base score
        
        # Profitability analysis
        prof = summary["profitability"]
        if prof.get("roe") and prof["roe"] > 15:
            strengths.append(f"优秀的ROE ({prof['roe']:.1f}%)")
            health_score += 10
        elif prof.get("roe") and prof["roe"] < 5:
            weaknesses.append(f"较低的ROE ({prof['roe']:.1f}%)")
            health_score -= 10
        
        if prof.get("net_profit_margin") and prof["net_profit_margin"] > 10:
            strengths.append(f"良好的净利率 ({prof['net_profit_margin']:.1f}%)")
            health_score += 5
        elif prof.get("net_profit_margin") and prof["net_profit_margin"] < 3:
            weaknesses.append(f"净利率偏低 ({prof['net_profit_margin']:.1f}%)")
            health_score -= 5
        
        # Solvency analysis
        solv = summary["solvency"]
        if solv.get("debt_to_assets") and solv["debt_to_assets"] < 0.4:
            strengths.append(f"资产负债率健康 ({solv['debt_to_assets']:.1f}%)")
            health_score += 5
        elif solv.get("debt_to_assets") and solv["debt_to_assets"] > 0.7:
            weaknesses.append(f"资产负债率较高 ({solv['debt_to_assets']:.1f}%)")
            health_score -= 10
        
        if solv.get("current_ratio") and solv["current_ratio"] > 1.5:
            strengths.append(f"流动比率良好 ({solv['current_ratio']:.1f})")
            health_score += 5
        elif solv.get("current_ratio") and solv["current_ratio"] < 1.0:
            weaknesses.append(f"流动比率偏低 ({solv['current_ratio']:.1f})")
            health_score -= 10
        
        # Growth analysis
        growth = summary["growth"]
        if growth.get("revenue_growth") and growth["revenue_growth"] > 10:
            strengths.append(f"营收增长强劲 ({growth['revenue_growth']:.1f}%)")
            health_score += 10
        elif growth.get("revenue_growth") and growth["revenue_growth"] < -5:
            weaknesses.append(f"营收出现下滑 ({growth['revenue_growth']:.1f}%)")
            health_score -= 15
        
        # Generate recommendations
        if weaknesses:
            if any("ROE" in w for w in weaknesses):
                recommendations.append("关注公司盈利能力改善措施")
            if any("负债率" in w for w in weaknesses):
                recommendations.append("关注债务结构优化和偿债能力")
            if any("增长" in w or "下滑" in w for w in weaknesses):
                recommendations.append("关注业务增长策略和市场竞争力")
        
        if not strengths:
            recommendations.append("建议深入分析公司基本面和行业前景")
        
        # Ensure health score is within bounds
        health_score = max(0, min(100, health_score))
        
        return {
            "code": code,
            "health_score": health_score,
            "analysis": f"基于{summary['periods']}期财务数据的健康度分析",
            "strengths": strengths,
            "weaknesses": weaknesses,
            "recommendations": recommendations,
            "summary": summary
        }