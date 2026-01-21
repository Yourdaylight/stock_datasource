"""Enhanced Portfolio Agent for comprehensive portfolio analysis using LangGraph/DeepAgents."""

from typing import Dict, Any, List, Optional, Tuple, AsyncGenerator
import logging
from datetime import datetime, date
import json
import pandas as pd
import numpy as np

from .base_agent import LangGraphAgent, AgentConfig, AgentResult
from .tools import get_stock_info

logger = logging.getLogger(__name__)


class EnhancedPortfolioAgent(LangGraphAgent):
    """Enhanced Portfolio Agent with comprehensive analysis capabilities."""
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self._portfolio_service = None
        self._market_service = None
        self._toplist_service = None
        self._toplist_analysis_service = None
        # Current user context (set during execute)
        self._current_user_id: str = "default_user"
        
        # Add portfolio-specific tools
        self.tools.extend([
            {
                "name": "analyze_portfolio_performance",
                "description": "分析投资组合整体表现",
                "function": self.analyze_portfolio_performance
            },
            {
                "name": "analyze_individual_stock",
                "description": "分析单个股票的技术面和基本面",
                "function": self.analyze_individual_stock
            },
            {
                "name": "assess_portfolio_risk",
                "description": "评估投资组合风险",
                "function": self.assess_portfolio_risk
            },
            {
                "name": "generate_investment_recommendations",
                "description": "生成投资建议",
                "function": self.generate_investment_recommendations
            },
            {
                "name": "calculate_technical_indicators",
                "description": "计算技术指标",
                "function": self.calculate_technical_indicators
            },
            {
                "name": "analyze_fundamental_metrics",
                "description": "分析基本面指标",
                "function": self.analyze_fundamental_metrics
            },
            {
                "name": "detect_market_signals",
                "description": "检测市场信号",
                "function": self.detect_market_signals
            },
            {
                "name": "optimize_portfolio_allocation",
                "description": "优化投资组合配置",
                "function": self.optimize_portfolio_allocation
            },
            {
                "name": "analyze_portfolio_toplist",
                "description": "分析投资组合相关龙虎榜情况",
                "function": self.analyze_portfolio_toplist
            },
            {
                "name": "check_position_toplist_status",
                "description": "检查持仓股票的龙虎榜状态",
                "function": self.check_position_toplist_status
            },
            {
                "name": "analyze_position_capital_flow",
                "description": "分析持仓股票的资金流向",
                "function": self.analyze_position_capital_flow
            }
        ])
    
    @property
    def portfolio_service(self):
        """Lazy load portfolio service."""
        if self._portfolio_service is None:
            try:
                from stock_datasource.modules.portfolio.enhanced_service import get_enhanced_portfolio_service
                self._portfolio_service = get_enhanced_portfolio_service()
            except Exception as e:
                logger.warning(f"Failed to get portfolio service: {e}")
        return self._portfolio_service
    
    @property
    def market_service(self):
        """Lazy load market service."""
        if self._market_service is None:
            try:
                from stock_datasource.modules.market.service import get_market_service
                self._market_service = get_market_service()
            except Exception as e:
                logger.warning(f"Failed to get market service: {e}")
        return self._market_service
    
    @property
    def toplist_service(self):
        """Lazy load toplist service."""
        if self._toplist_service is None:
            try:
                from stock_datasource.services.toplist_service import TopListService
                self._toplist_service = TopListService()
            except Exception as e:
                logger.warning(f"Failed to get toplist service: {e}")
        return self._toplist_service
    
    @property
    def toplist_analysis_service(self):
        """Lazy load toplist analysis service."""
        if self._toplist_analysis_service is None:
            try:
                from stock_datasource.services.toplist_analysis_service import TopListAnalysisService
                self._toplist_analysis_service = TopListAnalysisService()
            except Exception as e:
                logger.warning(f"Failed to get toplist analysis service: {e}")
        return self._toplist_analysis_service
    
    async def analyze_portfolio_performance(self, analysis_period: int = 30) -> Dict[str, Any]:
        """分析投资组合整体表现."""
        try:
            if not self.portfolio_service:
                return {"error": "Portfolio service not available"}
            
            # Use current user_id from context
            user_id = self._current_user_id
            
            # Get portfolio summary
            summary = await self.portfolio_service.get_summary(user_id)
            
            # Get profit history
            profit_history = await self.portfolio_service.get_profit_history(user_id, analysis_period)
            
            # Calculate performance metrics
            performance_metrics = self._calculate_performance_metrics(profit_history)
            
            # Analyze sector allocation
            sector_analysis = self._analyze_sector_allocation(summary.sector_distribution or {})
            
            return {
                "summary": {
                    "total_value": summary.total_value,
                    "total_cost": summary.total_cost,
                    "total_profit": summary.total_profit,
                    "profit_rate": summary.profit_rate,
                    "position_count": summary.position_count
                },
                "performance_metrics": performance_metrics,
                "sector_analysis": sector_analysis,
                "top_performer": summary.top_performer,
                "worst_performer": summary.worst_performer,
                "risk_score": summary.risk_score or 50.0
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze portfolio performance: {e}")
            return {"error": str(e)}
    
    async def analyze_individual_stock(self, ts_code: str, analysis_type: str = "comprehensive") -> Dict[str, Any]:
        """分析单个股票的技术面和基本面."""
        try:
            analysis_result = {
                "ts_code": ts_code,
                "analysis_type": analysis_type,
                "timestamp": datetime.now().isoformat()
            }
            
            # Get basic stock info
            stock_info = await self._get_stock_basic_info(ts_code)
            analysis_result["basic_info"] = stock_info
            
            if analysis_type in ["technical", "comprehensive"]:
                # Technical analysis
                technical_analysis = await self._perform_technical_analysis(ts_code)
                analysis_result["technical_analysis"] = technical_analysis
            
            if analysis_type in ["fundamental", "comprehensive"]:
                # Fundamental analysis
                fundamental_analysis = await self._perform_fundamental_analysis(ts_code)
                analysis_result["fundamental_analysis"] = fundamental_analysis
            
            # Generate overall recommendation
            recommendation = self._generate_stock_recommendation(analysis_result)
            analysis_result["recommendation"] = recommendation
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"Failed to analyze individual stock {ts_code}: {e}")
            return {"error": str(e), "ts_code": ts_code}
    
    async def assess_portfolio_risk(self) -> Dict[str, Any]:
        """评估投资组合风险."""
        try:
            if not self.portfolio_service:
                return {"error": "Portfolio service not available"}
            
            # Use current user_id from context
            user_id = self._current_user_id
            
            # Get positions
            positions = await self.portfolio_service.get_positions(user_id)
            
            if not positions:
                return {"risk_level": "无风险", "message": "无持仓"}
            
            # Calculate various risk metrics
            risk_assessment = {
                "overall_risk_score": 0.0,
                "concentration_risk": self._assess_concentration_risk(positions),
                "sector_risk": self._assess_sector_risk(positions),
                "volatility_risk": await self._assess_volatility_risk(positions),
                "liquidity_risk": self._assess_liquidity_risk(positions),
                "correlation_risk": await self._assess_correlation_risk(positions),
                "recommendations": []
            }
            
            # Calculate overall risk score
            risk_assessment["overall_risk_score"] = self._calculate_overall_risk_score(risk_assessment)
            
            # Generate risk recommendations
            risk_assessment["recommendations"] = self._generate_risk_recommendations(risk_assessment)
            
            return risk_assessment
            
        except Exception as e:
            logger.error(f"Failed to assess portfolio risk: {e}")
            return {"error": str(e)}
    
    async def generate_investment_recommendations(self, market_condition: str = "neutral") -> Dict[str, Any]:
        """生成投资建议."""
        try:
            recommendations = {
                "timestamp": datetime.now().isoformat(),
                "market_condition": market_condition,
                "portfolio_recommendations": [],
                "individual_stock_recommendations": [],
                "risk_management_recommendations": [],
                "allocation_recommendations": []
            }
            
            if not self.portfolio_service:
                return {"error": "Portfolio service not available"}
            
            # Use current user_id from context
            user_id = self._current_user_id
            
            # Get portfolio data
            positions = await self.portfolio_service.get_positions(user_id)
            summary = await self.portfolio_service.get_summary(user_id)
            
            # Portfolio-level recommendations
            portfolio_recs = await self._generate_portfolio_recommendations(summary, market_condition)
            recommendations["portfolio_recommendations"] = portfolio_recs
            
            # Individual stock recommendations
            for position in positions[:5]:  # Limit to top 5 positions
                stock_rec = await self._generate_individual_stock_recommendation(position, market_condition)
                recommendations["individual_stock_recommendations"].append(stock_rec)
            
            # Risk management recommendations
            risk_recs = await self._generate_risk_management_recommendations(positions, summary)
            recommendations["risk_management_recommendations"] = risk_recs
            
            # Allocation recommendations
            allocation_recs = self._generate_allocation_recommendations(summary, market_condition)
            recommendations["allocation_recommendations"] = allocation_recs
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Failed to generate investment recommendations: {e}")
            return {"error": str(e)}
    
    async def calculate_technical_indicators(self, ts_code: str, period: int = 60) -> Dict[str, Any]:
        """计算技术指标."""
        try:
            # Get historical price data
            price_data = await self._get_price_data(ts_code, period)
            
            if price_data is None or len(price_data) < 20:
                return {"error": "Insufficient price data"}
            
            indicators = {}
            
            # Moving averages
            indicators["ma5"] = price_data['close'].rolling(5).mean().iloc[-1]
            indicators["ma10"] = price_data['close'].rolling(10).mean().iloc[-1]
            indicators["ma20"] = price_data['close'].rolling(20).mean().iloc[-1]
            indicators["ma60"] = price_data['close'].rolling(60).mean().iloc[-1] if len(price_data) >= 60 else None
            
            # RSI
            indicators["rsi"] = self._calculate_rsi(price_data['close'])
            
            # MACD
            macd_data = self._calculate_macd(price_data['close'])
            indicators.update(macd_data)
            
            # Bollinger Bands
            bb_data = self._calculate_bollinger_bands(price_data['close'])
            indicators.update(bb_data)
            
            # Volume indicators
            if 'volume' in price_data.columns:
                indicators["volume_ma5"] = price_data['volume'].rolling(5).mean().iloc[-1]
                indicators["volume_ratio"] = price_data['volume'].iloc[-1] / indicators["volume_ma5"]
            
            # Current price and change
            indicators["current_price"] = price_data['close'].iloc[-1]
            indicators["price_change"] = price_data['close'].iloc[-1] - price_data['close'].iloc[-2]
            indicators["price_change_pct"] = (indicators["price_change"] / price_data['close'].iloc[-2]) * 100
            
            return {
                "ts_code": ts_code,
                "calculation_date": datetime.now().date().isoformat(),
                "indicators": indicators,
                "data_points": len(price_data)
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate technical indicators for {ts_code}: {e}")
            return {"error": str(e), "ts_code": ts_code}
    
    async def analyze_fundamental_metrics(self, ts_code: str) -> Dict[str, Any]:
        """分析基本面指标."""
        try:
            # Get fundamental data (mock implementation)
            fundamental_data = await self._get_fundamental_data(ts_code)
            
            if not fundamental_data:
                return {"error": "No fundamental data available"}
            
            analysis = {
                "ts_code": ts_code,
                "analysis_date": datetime.now().date().isoformat(),
                "valuation_metrics": {},
                "profitability_metrics": {},
                "growth_metrics": {},
                "financial_health": {},
                "overall_score": 0.0
            }
            
            # Valuation metrics
            analysis["valuation_metrics"] = {
                "pe_ratio": fundamental_data.get("pe_ratio", 0),
                "pb_ratio": fundamental_data.get("pb_ratio", 0),
                "ps_ratio": fundamental_data.get("ps_ratio", 0),
                "peg_ratio": fundamental_data.get("peg_ratio", 0)
            }
            
            # Profitability metrics
            analysis["profitability_metrics"] = {
                "roe": fundamental_data.get("roe", 0),
                "roa": fundamental_data.get("roa", 0),
                "gross_margin": fundamental_data.get("gross_margin", 0),
                "net_margin": fundamental_data.get("net_margin", 0)
            }
            
            # Growth metrics
            analysis["growth_metrics"] = {
                "revenue_growth": fundamental_data.get("revenue_growth", 0),
                "earnings_growth": fundamental_data.get("earnings_growth", 0),
                "book_value_growth": fundamental_data.get("book_value_growth", 0)
            }
            
            # Financial health
            analysis["financial_health"] = {
                "debt_to_equity": fundamental_data.get("debt_to_equity", 0),
                "current_ratio": fundamental_data.get("current_ratio", 0),
                "quick_ratio": fundamental_data.get("quick_ratio", 0)
            }
            
            # Calculate overall score
            analysis["overall_score"] = self._calculate_fundamental_score(analysis)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze fundamental metrics for {ts_code}: {e}")
            return {"error": str(e), "ts_code": ts_code}
    
    async def detect_market_signals(self, ts_code: str) -> Dict[str, Any]:
        """检测市场信号."""
        try:
            signals = {
                "ts_code": ts_code,
                "detection_time": datetime.now().isoformat(),
                "technical_signals": [],
                "volume_signals": [],
                "momentum_signals": [],
                "overall_signal": "neutral"
            }
            
            # Get technical indicators
            tech_indicators = await self.calculate_technical_indicators(ts_code)
            
            if "error" in tech_indicators:
                return tech_indicators
            
            indicators = tech_indicators["indicators"]
            
            # Technical signals
            if indicators.get("current_price", 0) > indicators.get("ma20", 0):
                signals["technical_signals"].append("价格突破20日均线")
            
            if indicators.get("rsi", 50) > 70:
                signals["technical_signals"].append("RSI超买信号")
            elif indicators.get("rsi", 50) < 30:
                signals["technical_signals"].append("RSI超卖信号")
            
            # MACD signals
            if indicators.get("macd", 0) > indicators.get("macd_signal", 0):
                signals["technical_signals"].append("MACD金叉信号")
            
            # Volume signals
            if indicators.get("volume_ratio", 1) > 2:
                signals["volume_signals"].append("成交量放大")
            
            # Momentum signals
            if indicators.get("price_change_pct", 0) > 5:
                signals["momentum_signals"].append("强势上涨")
            elif indicators.get("price_change_pct", 0) < -5:
                signals["momentum_signals"].append("快速下跌")
            
            # Determine overall signal
            signals["overall_signal"] = self._determine_overall_signal(signals)
            
            return signals
            
        except Exception as e:
            logger.error(f"Failed to detect market signals for {ts_code}: {e}")
            return {"error": str(e), "ts_code": ts_code}
    
    async def optimize_portfolio_allocation(self, target_risk: str = "moderate") -> Dict[str, Any]:
        """优化投资组合配置."""
        try:
            if not self.portfolio_service:
                return {"error": "Portfolio service not available"}
            
            # Use current user_id from context
            user_id = self._current_user_id
            
            # Get current portfolio
            positions = await self.portfolio_service.get_positions(user_id)
            summary = await self.portfolio_service.get_summary(user_id)
            
            optimization = {
                "user_id": user_id,
                "target_risk": target_risk,
                "current_allocation": {},
                "recommended_allocation": {},
                "rebalancing_actions": [],
                "expected_improvement": {}
            }
            
            # Analyze current allocation
            current_allocation = self._analyze_current_allocation(positions, summary)
            optimization["current_allocation"] = current_allocation
            
            # Generate recommended allocation
            recommended_allocation = self._generate_recommended_allocation(
                current_allocation, target_risk
            )
            optimization["recommended_allocation"] = recommended_allocation
            
            # Generate rebalancing actions
            rebalancing_actions = self._generate_rebalancing_actions(
                current_allocation, recommended_allocation
            )
            optimization["rebalancing_actions"] = rebalancing_actions
            
            # Calculate expected improvement
            expected_improvement = self._calculate_expected_improvement(
                current_allocation, recommended_allocation
            )
            optimization["expected_improvement"] = expected_improvement
            
            return optimization
            
        except Exception as e:
            logger.error(f"Failed to optimize portfolio allocation: {e}")
            return {"error": str(e)}
    
    # Private helper methods
    def _calculate_performance_metrics(self, profit_history: List[Dict]) -> Dict[str, float]:
        """Calculate portfolio performance metrics."""
        if not profit_history:
            return {}
        
        # Convert to DataFrame for easier calculation
        df = pd.DataFrame(profit_history)
        
        if 'total_profit' not in df.columns:
            return {}
        
        returns = df['total_profit'].pct_change().dropna()
        
        return {
            "total_return": df['total_profit'].iloc[-1] if len(df) > 0 else 0,
            "volatility": returns.std() * np.sqrt(252) if len(returns) > 1 else 0,
            "sharpe_ratio": (returns.mean() / returns.std()) * np.sqrt(252) if len(returns) > 1 and returns.std() > 0 else 0,
            "max_drawdown": self._calculate_max_drawdown(df['total_profit']) if len(df) > 1 else 0,
            "win_rate": (returns > 0).mean() if len(returns) > 0 else 0
        }
    
    def _calculate_max_drawdown(self, values: pd.Series) -> float:
        """Calculate maximum drawdown."""
        peak = values.expanding().max()
        drawdown = (values - peak) / peak
        return drawdown.min()
    
    def _analyze_sector_allocation(self, sector_distribution: Dict[str, float]) -> Dict[str, Any]:
        """Analyze sector allocation."""
        if not sector_distribution:
            return {"message": "No sector data available"}
        
        total_allocation = sum(sector_distribution.values())
        
        analysis = {
            "sector_weights": sector_distribution,
            "concentration_level": "low",
            "diversification_score": 0.0,
            "recommendations": []
        }
        
        # Check concentration
        max_weight = max(sector_distribution.values()) if sector_distribution else 0
        if max_weight > 50:
            analysis["concentration_level"] = "high"
            analysis["recommendations"].append("考虑降低单一行业集中度")
        elif max_weight > 30:
            analysis["concentration_level"] = "medium"
        
        # Calculate diversification score (inverse of Herfindahl index)
        if total_allocation > 0:
            normalized_weights = [w/total_allocation for w in sector_distribution.values()]
            herfindahl_index = sum(w**2 for w in normalized_weights)
            analysis["diversification_score"] = 1 - herfindahl_index
        
        return analysis
    
    def _assess_concentration_risk(self, positions: List) -> Dict[str, Any]:
        """Assess concentration risk."""
        if not positions:
            return {"risk_level": "无", "message": "无持仓"}
        
        total_value = sum(p.market_value or 0 for p in positions)
        
        if total_value == 0:
            return {"risk_level": "无法评估", "message": "无市值数据"}
        
        # Calculate position weights
        weights = [(p.market_value or 0) / total_value for p in positions]
        max_weight = max(weights)
        
        risk_assessment = {
            "max_position_weight": max_weight,
            "position_count": len(positions),
            "risk_level": "低",
            "recommendations": []
        }
        
        if max_weight > 0.4:
            risk_assessment["risk_level"] = "高"
            risk_assessment["recommendations"].append("单一持仓占比过高，建议分散投资")
        elif max_weight > 0.25:
            risk_assessment["risk_level"] = "中"
            risk_assessment["recommendations"].append("注意单一持仓集中度")
        
        if len(positions) < 5:
            risk_assessment["recommendations"].append("持仓数量较少，建议增加分散度")
        
        return risk_assessment
    
    def _assess_sector_risk(self, positions: List) -> Dict[str, Any]:
        """Assess sector risk."""
        sector_exposure = {}
        total_value = sum(p.market_value or 0 for p in positions)
        
        for position in positions:
            sector = position.sector or "未知"
            value = position.market_value or 0
            sector_exposure[sector] = sector_exposure.get(sector, 0) + value
        
        if total_value == 0:
            return {"risk_level": "无法评估", "message": "无市值数据"}
        
        # Normalize to percentages
        sector_weights = {k: v/total_value for k, v in sector_exposure.items()}
        max_sector_weight = max(sector_weights.values()) if sector_weights else 0
        
        risk_assessment = {
            "sector_weights": sector_weights,
            "max_sector_weight": max_sector_weight,
            "risk_level": "低",
            "recommendations": []
        }
        
        if max_sector_weight > 0.6:
            risk_assessment["risk_level"] = "高"
            risk_assessment["recommendations"].append("行业集中度过高，建议跨行业分散")
        elif max_sector_weight > 0.4:
            risk_assessment["risk_level"] = "中"
            risk_assessment["recommendations"].append("注意行业集中风险")
        
        return risk_assessment
    
    async def _assess_volatility_risk(self, positions: List) -> Dict[str, Any]:
        """Assess volatility risk."""
        # Mock implementation - in reality would calculate based on historical volatility
        return {
            "portfolio_volatility": 0.25,
            "risk_level": "中",
            "recommendations": ["监控市场波动"]
        }
    
    def _assess_liquidity_risk(self, positions: List) -> Dict[str, Any]:
        """Assess liquidity risk."""
        # Mock implementation - in reality would check trading volume and market cap
        return {
            "liquidity_score": 0.8,
            "risk_level": "低",
            "recommendations": []
        }
    
    async def _assess_correlation_risk(self, positions: List) -> Dict[str, Any]:
        """Assess correlation risk."""
        # Mock implementation - in reality would calculate correlation matrix
        return {
            "average_correlation": 0.3,
            "risk_level": "低",
            "recommendations": []
        }
    
    def _calculate_overall_risk_score(self, risk_assessment: Dict) -> float:
        """Calculate overall risk score."""
        # Simple weighted average of different risk components
        weights = {
            "concentration_risk": 0.3,
            "sector_risk": 0.25,
            "volatility_risk": 0.25,
            "liquidity_risk": 0.1,
            "correlation_risk": 0.1
        }
        
        risk_scores = {
            "低": 20,
            "中": 50,
            "高": 80
        }
        
        total_score = 0
        for risk_type, weight in weights.items():
            if risk_type in risk_assessment:
                risk_level = risk_assessment[risk_type].get("risk_level", "中")
                score = risk_scores.get(risk_level, 50)
                total_score += score * weight
        
        return total_score
    
    def _generate_risk_recommendations(self, risk_assessment: Dict) -> List[str]:
        """Generate risk management recommendations."""
        recommendations = []
        
        overall_score = risk_assessment.get("overall_risk_score", 50)
        
        if overall_score > 70:
            recommendations.append("整体风险较高，建议降低仓位或增加分散度")
        elif overall_score > 50:
            recommendations.append("风险水平适中，建议定期监控")
        else:
            recommendations.append("风险水平较低，可考虑适当增加收益型投资")
        
        # Add specific recommendations from each risk component
        for risk_type, risk_data in risk_assessment.items():
            if isinstance(risk_data, dict) and "recommendations" in risk_data:
                recommendations.extend(risk_data["recommendations"])
        
        return list(set(recommendations))  # Remove duplicates
    
    # Technical indicator calculation methods
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """Calculate RSI."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50.0
    
    def _calculate_macd(self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, float]:
        """Calculate MACD."""
        ema_fast = prices.ewm(span=fast).mean()
        ema_slow = prices.ewm(span=slow).mean()
        macd = ema_fast - ema_slow
        macd_signal = macd.ewm(span=signal).mean()
        macd_hist = macd - macd_signal
        
        return {
            "macd": macd.iloc[-1] if not pd.isna(macd.iloc[-1]) else 0.0,
            "macd_signal": macd_signal.iloc[-1] if not pd.isna(macd_signal.iloc[-1]) else 0.0,
            "macd_hist": macd_hist.iloc[-1] if not pd.isna(macd_hist.iloc[-1]) else 0.0
        }
    
    def _calculate_bollinger_bands(self, prices: pd.Series, period: int = 20, std_dev: int = 2) -> Dict[str, float]:
        """Calculate Bollinger Bands."""
        sma = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        
        return {
            "bb_upper": (sma + (std * std_dev)).iloc[-1] if not pd.isna(sma.iloc[-1]) else 0.0,
            "bb_middle": sma.iloc[-1] if not pd.isna(sma.iloc[-1]) else 0.0,
            "bb_lower": (sma - (std * std_dev)).iloc[-1] if not pd.isna(sma.iloc[-1]) else 0.0
        }
    
    # Mock data methods (to be replaced with real data sources)
    async def _get_stock_basic_info(self, ts_code: str) -> Dict[str, Any]:
        """Get basic stock information."""
        # Mock implementation
        return {
            "ts_code": ts_code,
            "name": f"股票{ts_code}",
            "industry": "未知",
            "market_cap": 1000000000,
            "pe_ratio": 25.0
        }
    
    async def _get_price_data(self, ts_code: str, period: int) -> Optional[pd.DataFrame]:
        """Get historical price data."""
        # Mock implementation - generate sample data
        dates = pd.date_range(end=datetime.now(), periods=period, freq='D')
        base_price = 100.0
        
        # Generate random walk price data
        returns = np.random.normal(0.001, 0.02, period)
        prices = [base_price]
        for ret in returns[1:]:
            prices.append(prices[-1] * (1 + ret))
        
        return pd.DataFrame({
            'date': dates,
            'close': prices,
            'volume': np.random.randint(1000000, 10000000, period)
        })
    
    async def _get_fundamental_data(self, ts_code: str) -> Dict[str, float]:
        """Get fundamental data."""
        # Mock implementation
        return {
            "pe_ratio": 25.0,
            "pb_ratio": 3.2,
            "ps_ratio": 5.1,
            "peg_ratio": 1.2,
            "roe": 15.5,
            "roa": 8.2,
            "gross_margin": 35.0,
            "net_margin": 12.0,
            "revenue_growth": 8.5,
            "earnings_growth": 12.0,
            "book_value_growth": 10.0,
            "debt_to_equity": 0.4,
            "current_ratio": 2.1,
            "quick_ratio": 1.5
        }
    
    def _calculate_fundamental_score(self, analysis: Dict) -> float:
        """Calculate overall fundamental score."""
        # Simple scoring based on key metrics
        score = 50.0  # Base score
        
        valuation = analysis.get("valuation_metrics", {})
        profitability = analysis.get("profitability_metrics", {})
        growth = analysis.get("growth_metrics", {})
        
        # Valuation scoring (lower is better for PE, PB)
        pe_ratio = valuation.get("pe_ratio", 25)
        if pe_ratio < 15:
            score += 10
        elif pe_ratio > 30:
            score -= 10
        
        # Profitability scoring
        roe = profitability.get("roe", 0)
        if roe > 15:
            score += 15
        elif roe < 5:
            score -= 15
        
        # Growth scoring
        revenue_growth = growth.get("revenue_growth", 0)
        if revenue_growth > 10:
            score += 10
        elif revenue_growth < 0:
            score -= 10
        
        return max(0, min(100, score))
    
    def _determine_overall_signal(self, signals: Dict) -> str:
        """Determine overall market signal."""
        bullish_signals = 0
        bearish_signals = 0
        
        # Count signals
        for signal_list in [signals["technical_signals"], signals["volume_signals"], signals["momentum_signals"]]:
            for signal in signal_list:
                if any(word in signal for word in ["突破", "金叉", "放大", "上涨"]):
                    bullish_signals += 1
                elif any(word in signal for word in ["下跌", "超卖", "死叉"]):
                    bearish_signals += 1
        
        if bullish_signals > bearish_signals + 1:
            return "bullish"
        elif bearish_signals > bullish_signals + 1:
            return "bearish"
        else:
            return "neutral"
    
    # Recommendation generation methods
    async def _perform_technical_analysis(self, ts_code: str) -> Dict[str, Any]:
        """Perform technical analysis."""
        indicators = await self.calculate_technical_indicators(ts_code)
        signals = await self.detect_market_signals(ts_code)
        
        return {
            "indicators": indicators.get("indicators", {}),
            "signals": signals,
            "trend": self._determine_trend(indicators.get("indicators", {})),
            "support_resistance": self._calculate_support_resistance(indicators.get("indicators", {}))
        }
    
    async def _perform_fundamental_analysis(self, ts_code: str) -> Dict[str, Any]:
        """Perform fundamental analysis."""
        return await self.analyze_fundamental_metrics(ts_code)
    
    def _generate_stock_recommendation(self, analysis_result: Dict) -> Dict[str, Any]:
        """Generate stock recommendation based on analysis."""
        recommendation = {
            "action": "hold",
            "confidence": 0.5,
            "target_price": None,
            "stop_loss": None,
            "reasoning": []
        }
        
        # Technical analysis influence
        if "technical_analysis" in analysis_result:
            tech_signals = analysis_result["technical_analysis"].get("signals", {})
            overall_signal = tech_signals.get("overall_signal", "neutral")
            
            if overall_signal == "bullish":
                recommendation["action"] = "buy"
                recommendation["confidence"] += 0.2
                recommendation["reasoning"].append("技术面呈现多头信号")
            elif overall_signal == "bearish":
                recommendation["action"] = "sell"
                recommendation["confidence"] += 0.2
                recommendation["reasoning"].append("技术面呈现空头信号")
        
        # Fundamental analysis influence
        if "fundamental_analysis" in analysis_result:
            fund_score = analysis_result["fundamental_analysis"].get("overall_score", 50)
            
            if fund_score > 70:
                if recommendation["action"] != "sell":
                    recommendation["action"] = "buy"
                recommendation["confidence"] += 0.2
                recommendation["reasoning"].append("基本面评分良好")
            elif fund_score < 30:
                recommendation["action"] = "sell"
                recommendation["confidence"] += 0.2
                recommendation["reasoning"].append("基本面评分较差")
        
        # Ensure confidence is within bounds
        recommendation["confidence"] = max(0.1, min(0.9, recommendation["confidence"]))
        
        return recommendation
    
    def _determine_trend(self, indicators: Dict) -> str:
        """Determine price trend."""
        current_price = indicators.get("current_price", 0)
        ma20 = indicators.get("ma20", 0)
        ma60 = indicators.get("ma60", 0)
        
        if current_price > ma20 > ma60:
            return "uptrend"
        elif current_price < ma20 < ma60:
            return "downtrend"
        else:
            return "sideways"
    
    def _calculate_support_resistance(self, indicators: Dict) -> Dict[str, float]:
        """Calculate support and resistance levels."""
        current_price = indicators.get("current_price", 0)
        bb_upper = indicators.get("bb_upper", 0)
        bb_lower = indicators.get("bb_lower", 0)
        ma20 = indicators.get("ma20", 0)
        
        return {
            "resistance": max(bb_upper, current_price * 1.05),
            "support": min(bb_lower, current_price * 0.95),
            "key_level": ma20
        }
    
    async def _generate_portfolio_recommendations(self, summary, market_condition: str) -> List[Dict[str, Any]]:
        """Generate portfolio-level recommendations."""
        recommendations = []
        
        # Performance-based recommendations
        if summary.profit_rate > 10:
            recommendations.append({
                "type": "performance",
                "message": "投资组合表现良好，建议保持当前策略",
                "priority": "low"
            })
        elif summary.profit_rate < -10:
            recommendations.append({
                "type": "performance",
                "message": "投资组合亏损较大，建议重新评估投资策略",
                "priority": "high"
            })
        
        # Market condition based recommendations
        if market_condition == "bearish":
            recommendations.append({
                "type": "market",
                "message": "市场环境偏空，建议降低仓位或增加防御性资产",
                "priority": "medium"
            })
        elif market_condition == "bullish":
            recommendations.append({
                "type": "market",
                "message": "市场环境向好，可考虑适当增加仓位",
                "priority": "medium"
            })
        
        return recommendations
    
    async def _generate_individual_stock_recommendation(self, position, market_condition: str) -> Dict[str, Any]:
        """Generate recommendation for individual stock."""
        analysis = await self.analyze_individual_stock(position.ts_code)
        
        recommendation = {
            "ts_code": position.ts_code,
            "stock_name": position.stock_name,
            "current_position": {
                "quantity": position.quantity,
                "cost_price": position.cost_price,
                "current_price": position.current_price,
                "profit_rate": position.profit_rate
            }
        }
        
        if "recommendation" in analysis:
            recommendation.update(analysis["recommendation"])
        else:
            recommendation.update({
                "action": "hold",
                "confidence": 0.5,
                "reasoning": ["数据不足，建议保持观望"]
            })
        
        return recommendation
    
    async def _generate_risk_management_recommendations(self, positions: List, summary) -> List[Dict[str, Any]]:
        """Generate risk management recommendations."""
        recommendations = []
        
        # Position size recommendations
        total_value = summary.total_value
        for position in positions:
            if position.market_value and total_value > 0:
                weight = position.market_value / total_value
                if weight > 0.3:
                    recommendations.append({
                        "type": "position_size",
                        "ts_code": position.ts_code,
                        "message": f"{position.stock_name}仓位过重({weight:.1%})，建议减仓",
                        "priority": "medium"
                    })
        
        # Stop loss recommendations
        for position in positions:
            if position.profit_rate and position.profit_rate < -15:
                recommendations.append({
                    "type": "stop_loss",
                    "ts_code": position.ts_code,
                    "message": f"{position.stock_name}亏损较大({position.profit_rate:.1f}%)，建议考虑止损",
                    "priority": "high"
                })
        
        return recommendations
    
    def _generate_allocation_recommendations(self, summary, market_condition: str) -> List[Dict[str, Any]]:
        """Generate allocation recommendations."""
        recommendations = []
        
        sector_dist = summary.sector_distribution or {}
        
        # Sector diversification recommendations
        if len(sector_dist) < 3:
            recommendations.append({
                "type": "diversification",
                "message": "建议增加行业分散度，目前行业集中度较高",
                "priority": "medium"
            })
        
        # Sector-specific recommendations based on market condition
        if market_condition == "bullish":
            recommendations.append({
                "type": "sector_allocation",
                "message": "市场向好，可考虑增加成长型行业配置",
                "priority": "low"
            })
        elif market_condition == "bearish":
            recommendations.append({
                "type": "sector_allocation", 
                "message": "市场偏弱，建议增加防御性行业配置",
                "priority": "medium"
            })
        
        return recommendations
    
    def _analyze_current_allocation(self, positions: List, summary) -> Dict[str, Any]:
        """Analyze current portfolio allocation."""
        total_value = summary.total_value
        
        allocation = {
            "total_value": total_value,
            "position_weights": {},
            "sector_weights": summary.sector_distribution or {},
            "risk_metrics": {
                "concentration": 0.0,
                "diversification": 0.0
            }
        }
        
        # Calculate position weights
        for position in positions:
            if position.market_value and total_value > 0:
                weight = position.market_value / total_value
                allocation["position_weights"][position.ts_code] = {
                    "weight": weight,
                    "stock_name": position.stock_name,
                    "sector": position.sector
                }
        
        # Calculate concentration (max position weight)
        if allocation["position_weights"]:
            allocation["risk_metrics"]["concentration"] = max(
                pos["weight"] for pos in allocation["position_weights"].values()
            )
        
        return allocation
    
    def _generate_recommended_allocation(self, current_allocation: Dict, target_risk: str) -> Dict[str, Any]:
        """Generate recommended allocation based on target risk."""
        # Risk-based allocation targets
        risk_profiles = {
            "conservative": {"max_position": 0.15, "max_sector": 0.25, "min_positions": 8},
            "moderate": {"max_position": 0.20, "max_sector": 0.35, "min_positions": 6},
            "aggressive": {"max_position": 0.30, "max_sector": 0.50, "min_positions": 4}
        }
        
        profile = risk_profiles.get(target_risk, risk_profiles["moderate"])
        
        recommended = {
            "target_risk": target_risk,
            "allocation_targets": profile,
            "sector_targets": {
                "金融": 0.20,
                "科技": 0.25,
                "消费": 0.20,
                "医药": 0.15,
                "其他": 0.20
            },
            "rebalancing_needed": False
        }
        
        # Check if rebalancing is needed
        current_concentration = current_allocation["risk_metrics"]["concentration"]
        if current_concentration > profile["max_position"]:
            recommended["rebalancing_needed"] = True
        
        return recommended
    
    def _generate_rebalancing_actions(self, current: Dict, recommended: Dict) -> List[Dict[str, Any]]:
        """Generate specific rebalancing actions."""
        actions = []
        
        if not recommended["rebalancing_needed"]:
            return actions
        
        max_position = recommended["allocation_targets"]["max_position"]
        
        # Find overweight positions
        for ts_code, position_data in current["position_weights"].items():
            if position_data["weight"] > max_position:
                reduce_amount = position_data["weight"] - max_position
                actions.append({
                    "action": "reduce",
                    "ts_code": ts_code,
                    "stock_name": position_data["stock_name"],
                    "current_weight": position_data["weight"],
                    "target_weight": max_position,
                    "reduce_percentage": reduce_amount,
                    "reason": f"仓位超过{max_position:.1%}限制"
                })
        
        return actions
    
    def _calculate_expected_improvement(self, current: Dict, recommended: Dict) -> Dict[str, Any]:
        """Calculate expected improvement from rebalancing."""
        return {
            "risk_reduction": "预期降低10-15%的组合风险",
            "diversification_improvement": "提高投资组合分散度",
            "expected_return": "在控制风险的前提下优化收益",
            "implementation_cost": "预计交易成本0.2-0.5%"
        }
    
    async def analyze_portfolio_toplist(self) -> Dict[str, Any]:
        """分析投资组合相关的龙虎榜情况"""
        try:
            if not self.portfolio_service or not self.toplist_service:
                return {"error": "Required services not available"}
            
            # Use current user_id from context
            user_id = self._current_user_id
            
            # 获取持仓股票
            positions = await self.portfolio_service.get_positions(user_id)
            if not positions:
                return {"message": "当前无持仓股票"}
            
            # 分析持仓股票的龙虎榜情况
            toplist_analysis = {
                "on_list_positions": [],
                "capital_flow_analysis": {},
                "risk_alerts": [],
                "investment_suggestions": []
            }
            
            # 获取最近5天的数据
            from datetime import datetime, timedelta
            end_date = datetime.now().date()
            
            for position in positions:
                ts_code = position.get("ts_code")
                if not ts_code:
                    continue
                
                # 获取该股票的龙虎榜历史
                history = await self.toplist_service.get_stock_top_list_history(ts_code, 5)
                
                if history:
                    # 计算席位集中度
                    concentration = await self.toplist_analysis_service.calculate_seat_concentration(ts_code, 5)
                    
                    position_analysis = {
                        "ts_code": ts_code,
                        "stock_name": position.get("stock_name", ""),
                        "position_weight": position.get("weight", 0),
                        "toplist_appearances": len(history),
                        "latest_appearance": history[0]["trade_date"] if history else None,
                        "concentration_index": concentration.get("concentration_index", 0),
                        "institution_dominance": concentration.get("institution_dominance", 0),
                        "recent_net_flow": sum(item.get("net_amount", 0) for item in history),
                        "risk_level": self._assess_toplist_risk(history, concentration)
                    }
                    
                    toplist_analysis["on_list_positions"].append(position_analysis)
                    
                    # 生成风险预警
                    if concentration.get("concentration_index", 0) > 0.7:
                        toplist_analysis["risk_alerts"].append({
                            "ts_code": ts_code,
                            "type": "high_concentration",
                            "message": f"{position.get('stock_name', ts_code)}席位高度集中，需关注流动性风险"
                        })
                    
                    if position_analysis["recent_net_flow"] < -100000:  # 净流出超过10万
                        toplist_analysis["risk_alerts"].append({
                            "ts_code": ts_code,
                            "type": "capital_outflow",
                            "message": f"{position.get('stock_name', ts_code)}近期资金净流出明显，建议关注"
                        })
            
            # 生成投资建议
            toplist_analysis["investment_suggestions"] = self._generate_toplist_suggestions(
                toplist_analysis["on_list_positions"]
            )
            
            # 整体资金流向分析
            total_net_flow = sum(pos["recent_net_flow"] for pos in toplist_analysis["on_list_positions"])
            avg_concentration = np.mean([pos["concentration_index"] for pos in toplist_analysis["on_list_positions"]]) if toplist_analysis["on_list_positions"] else 0
            
            toplist_analysis["capital_flow_analysis"] = {
                "total_net_flow": total_net_flow,
                "average_concentration": avg_concentration,
                "positions_on_toplist": len(toplist_analysis["on_list_positions"]),
                "high_risk_positions": len([pos for pos in toplist_analysis["on_list_positions"] if pos["risk_level"] == "high"])
            }
            
            return {
                "success": True,
                "data": toplist_analysis,
                "message": f"成功分析投资组合龙虎榜情况，{len(toplist_analysis['on_list_positions'])}只股票有龙虎榜记录"
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze portfolio toplist: {e}")
            return {"success": False, "error": str(e)}
    
    async def check_position_toplist_status(self) -> Dict[str, Any]:
        """检查持仓股票的龙虎榜状态"""
        try:
            if not self.portfolio_service or not self.toplist_service:
                return {"error": "Required services not available"}
            
            # Use current user_id from context
            user_id = self._current_user_id
            
            positions = await self.portfolio_service.get_positions(user_id)
            if not positions:
                return {"message": "当前无持仓股票"}
            
            # 获取今日龙虎榜数据
            from datetime import datetime
            today = datetime.now().strftime("%Y-%m-%d")
            today_toplist = await self.toplist_service.get_top_list_by_date(today)
            
            # 检查持仓股票是否在今日龙虎榜中
            toplist_codes = {item["ts_code"] for item in today_toplist}
            
            status_results = []
            for position in positions:
                ts_code = position.get("ts_code")
                if ts_code in toplist_codes:
                    # 找到对应的龙虎榜数据
                    toplist_data = next((item for item in today_toplist if item["ts_code"] == ts_code), None)
                    if toplist_data:
                        status_results.append({
                            "ts_code": ts_code,
                            "stock_name": position.get("stock_name", ""),
                            "on_toplist": True,
                            "pct_chg": toplist_data.get("pct_chg", 0),
                            "net_amount": toplist_data.get("net_amount", 0),
                            "reason": toplist_data.get("reason", ""),
                            "position_weight": position.get("weight", 0)
                        })
                else:
                    status_results.append({
                        "ts_code": ts_code,
                        "stock_name": position.get("stock_name", ""),
                        "on_toplist": False,
                        "position_weight": position.get("weight", 0)
                    })
            
            on_toplist_count = len([r for r in status_results if r["on_toplist"]])
            
            return {
                "success": True,
                "data": {
                    "positions_status": status_results,
                    "total_positions": len(status_results),
                    "on_toplist_count": on_toplist_count,
                    "toplist_ratio": on_toplist_count / len(status_results) if status_results else 0
                },
                "message": f"持仓中有{on_toplist_count}只股票今日上榜龙虎榜"
            }
            
        except Exception as e:
            logger.error(f"Failed to check toplist status: {e}")
            return {"success": False, "error": str(e)}
    
    async def analyze_position_capital_flow(self, days: int = 5) -> Dict[str, Any]:
        """分析持仓股票的资金流向"""
        try:
            if not self.portfolio_service or not self.toplist_analysis_service:
                return {"error": "Required services not available"}
            
            # Use current user_id from context
            user_id = self._current_user_id
            
            positions = await self.portfolio_service.get_positions(user_id)
            if not positions:
                return {"message": "当前无持仓股票"}
            
            flow_analysis = {
                "position_flows": [],
                "summary": {
                    "total_positions": len(positions),
                    "analyzed_positions": 0,
                    "net_inflow_positions": 0,
                    "net_outflow_positions": 0,
                    "total_net_flow": 0
                }
            }
            
            for position in positions:
                ts_code = position.get("ts_code")
                if not ts_code:
                    continue
                
                try:
                    # 获取席位集中度分析
                    concentration = await self.toplist_analysis_service.calculate_seat_concentration(ts_code, days)
                    
                    # 获取龙虎榜历史
                    history = await self.toplist_service.get_stock_top_list_history(ts_code, days)
                    
                    if history:
                        net_flow = sum(item.get("net_amount", 0) for item in history)
                        avg_pct_chg = np.mean([item.get("pct_chg", 0) for item in history])
                        
                        position_flow = {
                            "ts_code": ts_code,
                            "stock_name": position.get("stock_name", ""),
                            "position_weight": position.get("weight", 0),
                            "net_flow": net_flow,
                            "avg_pct_chg": avg_pct_chg,
                            "concentration_index": concentration.get("concentration_index", 0),
                            "institution_dominance": concentration.get("institution_dominance", 0),
                            "appearance_count": len(history),
                            "flow_direction": "流入" if net_flow > 0 else "流出",
                            "risk_assessment": self._assess_flow_risk(net_flow, concentration, avg_pct_chg)
                        }
                        
                        flow_analysis["position_flows"].append(position_flow)
                        flow_analysis["summary"]["analyzed_positions"] += 1
                        flow_analysis["summary"]["total_net_flow"] += net_flow
                        
                        if net_flow > 0:
                            flow_analysis["summary"]["net_inflow_positions"] += 1
                        else:
                            flow_analysis["summary"]["net_outflow_positions"] += 1
                
                except Exception as e:
                    logger.warning(f"Failed to analyze flow for {ts_code}: {e}")
                    continue
            
            # 按净流入排序
            flow_analysis["position_flows"].sort(key=lambda x: x["net_flow"], reverse=True)
            
            return {
                "success": True,
                "data": flow_analysis,
                "message": f"成功分析{flow_analysis['summary']['analyzed_positions']}只持仓股票的资金流向"
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze capital flow: {e}")
            return {"success": False, "error": str(e)}
    
    def _assess_toplist_risk(self, history: List[Dict], concentration: Dict) -> str:
        """评估龙虎榜风险等级"""
        risk_score = 0
        
        # 基于出现频率
        if len(history) >= 3:
            risk_score += 2
        elif len(history) >= 2:
            risk_score += 1
        
        # 基于席位集中度
        hhi = concentration.get("concentration_index", 0)
        if hhi > 0.7:
            risk_score += 3
        elif hhi > 0.5:
            risk_score += 2
        elif hhi > 0.3:
            risk_score += 1
        
        # 基于资金流向
        net_flow = sum(item.get("net_amount", 0) for item in history)
        if net_flow < -200000:  # 大额流出
            risk_score += 2
        elif net_flow < -50000:
            risk_score += 1
        
        if risk_score >= 5:
            return "high"
        elif risk_score >= 3:
            return "medium"
        else:
            return "low"
    
    def _assess_flow_risk(self, net_flow: float, concentration: Dict, avg_pct_chg: float) -> str:
        """评估资金流向风险"""
        risk_factors = []
        
        if net_flow < -100000:
            risk_factors.append("大额资金流出")
        
        if concentration.get("concentration_index", 0) > 0.6:
            risk_factors.append("席位高度集中")
        
        if abs(avg_pct_chg) > 8:
            risk_factors.append("价格波动剧烈")
        
        if len(risk_factors) >= 2:
            return f"高风险: {', '.join(risk_factors)}"
        elif len(risk_factors) == 1:
            return f"中等风险: {risk_factors[0]}"
        else:
            return "低风险"
    
    def _generate_toplist_suggestions(self, positions: List[Dict]) -> List[str]:
        """生成基于龙虎榜的投资建议"""
        suggestions = []
        
        if not positions:
            return ["当前持仓股票无龙虎榜记录，建议关注市场热点"]
        
        # 高风险持仓建议
        high_risk_positions = [pos for pos in positions if pos["risk_level"] == "high"]
        if high_risk_positions:
            suggestions.append(f"建议关注{len(high_risk_positions)}只高风险股票，考虑适当减仓")
        
        # 资金流出建议
        outflow_positions = [pos for pos in positions if pos["recent_net_flow"] < -50000]
        if outflow_positions:
            suggestions.append(f"{len(outflow_positions)}只股票存在明显资金流出，建议密切关注")
        
        # 席位集中度建议
        high_concentration = [pos for pos in positions if pos["concentration_index"] > 0.6]
        if high_concentration:
            suggestions.append(f"{len(high_concentration)}只股票席位集中度较高，注意流动性风险")
        
        # 机构主导建议
        institution_dominated = [pos for pos in positions if pos["institution_dominance"] > 0.7]
        if institution_dominated:
            suggestions.append(f"{len(institution_dominated)}只股票机构主导明显，可关注后续动向")
        
        if not suggestions:
            suggestions.append("持仓股票龙虎榜表现相对稳定，建议继续观察")
        
        return suggestions
    
    async def execute(self, task: str, context: Dict[str, Any] = None) -> AgentResult:
        """Execute with user context injection."""
        context = context or {}
        # Set current user_id from context
        self._current_user_id = context.get("user_id", "default_user")
        return await super().execute(task, context)
    
    async def execute_stream(self, task: str, context: Dict[str, Any] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute stream with user context injection."""
        context = context or {}
        # Set current user_id from context
        self._current_user_id = context.get("user_id", "default_user")
        async for event in super().execute_stream(task, context):
            yield event


# Global agent instance
_enhanced_portfolio_agent = None


def get_enhanced_portfolio_agent() -> EnhancedPortfolioAgent:
    """Get enhanced portfolio agent instance."""
    global _enhanced_portfolio_agent
    if _enhanced_portfolio_agent is None:
        config = AgentConfig(
            name="enhanced_portfolio_agent",
            description="Enhanced portfolio analysis and management agent",
            model_name="deepseek-chat",
            temperature=0.3
        )
        _enhanced_portfolio_agent = EnhancedPortfolioAgent(config)
    return _enhanced_portfolio_agent