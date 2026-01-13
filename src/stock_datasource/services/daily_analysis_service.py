"""Daily analysis service for portfolio management with ClickHouse optimizations."""

import logging
import uuid
import json
import asyncio
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, asdict
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class AnalysisReport:
    """Daily analysis report data model."""
    id: str
    user_id: str
    analysis_date: date
    analysis_type: str  # 'daily', 'weekly', 'monthly', 'manual'
    analysis_summary: str
    stock_analyses: str  # JSON string
    risk_alerts: str  # JSON string
    recommendations: str  # JSON string
    market_sentiment: str = ""
    technical_signals: str = ""
    fundamental_scores: str = ""
    status: str = 'completed'
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class MarketEnvironment:
    """Market environment analysis data."""
    analysis_date: date
    market_trend: str  # 'bullish', 'bearish', 'neutral'
    volatility_level: str  # 'low', 'medium', 'high'
    sentiment_score: float  # -1.0 to 1.0
    key_events: List[str]
    sector_performance: Dict[str, float]
    risk_factors: List[str]
    market_indices: Dict[str, float]


@dataclass
class StockAnalysis:
    """Individual stock analysis data."""
    ts_code: str
    stock_name: str
    current_price: float
    price_change: float
    price_change_pct: float
    technical_score: float  # 0-100
    fundamental_score: float  # 0-100
    risk_score: float  # 0-100
    recommendation: str  # 'strong_buy', 'buy', 'hold', 'sell', 'strong_sell'
    key_points: List[str]
    support_level: Optional[float] = None
    resistance_level: Optional[float] = None


class DailyAnalysisService:
    """Daily analysis service with ClickHouse optimizations."""
    
    def __init__(self, user_id: str = "default_user"):
        self.user_id = user_id
        self._db = None
        self._agent = None
    
    @property
    def db(self):
        """Lazy load database client."""
        if self._db is None:
            try:
                from stock_datasource.models.database import db_client
                self._db = db_client
            except Exception as e:
                logger.warning(f"Failed to get DB client: {e}")
        return self._db
    
    @property
    def agent(self):
        """Lazy load portfolio agent."""
        if self._agent is None:
            try:
                from stock_datasource.agents.enhanced_portfolio_agent import EnhancedPortfolioAgent
                self._agent = EnhancedPortfolioAgent()
            except Exception as e:
                logger.warning(f"Failed to get portfolio agent: {e}")
        return self._agent
    
    async def trigger_analysis(self, analysis_type: str = "daily") -> str:
        """Trigger daily analysis and return task ID."""
        task_id = str(uuid.uuid4())
        
        try:
            # Run analysis asynchronously
            asyncio.create_task(self._run_analysis(task_id, analysis_type))
            logger.info(f"Analysis task {task_id} triggered for {analysis_type}")
            return task_id
        except Exception as e:
            logger.error(f"Failed to trigger analysis: {e}")
            return task_id
    
    async def get_analysis(self, date: Optional[str] = None, 
                          analysis_type: str = "daily") -> Optional[Dict[str, Any]]:
        """Get analysis report for a specific date."""
        if not self.db:
            return self._get_mock_analysis(date)
        
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date() if date else datetime.now().date()
            
            # Query from ClickHouse with optimized conditions
            query = """
                SELECT 
                    id, analysis_date, analysis_type, analysis_summary,
                    stock_analyses, risk_alerts, recommendations,
                    market_sentiment, technical_signals, fundamental_scores,
                    created_at, updated_at
                FROM portfolio_analysis 
                WHERE user_id = %(user_id)s 
                AND analysis_date = %(target_date)s
                AND analysis_type = %(analysis_type)s
                ORDER BY updated_at DESC
                LIMIT 1
            """
            
            df = self.db.execute_query(query, {
                'user_id': self.user_id,
                'target_date': target_date,
                'analysis_type': analysis_type
            })
            
            if df.empty:
                # Generate new analysis if not found
                return await self._generate_analysis(target_date, analysis_type)
            
            row = df.iloc[0]
            
            # Parse JSON fields
            stock_analyses = self._safe_json_parse(row['stock_analyses'])
            risk_alerts = self._safe_json_parse(row['risk_alerts'])
            recommendations = self._safe_json_parse(row['recommendations'])
            
            return {
                'id': str(row['id']),
                'analysis_date': str(row['analysis_date']),
                'analysis_type': str(row['analysis_type']),
                'analysis_summary': str(row['analysis_summary']),
                'stock_analyses': stock_analyses,
                'risk_alerts': risk_alerts,
                'recommendations': recommendations,
                'market_sentiment': str(row['market_sentiment']) if pd.notna(row['market_sentiment']) else "",
                'technical_signals': str(row['technical_signals']) if pd.notna(row['technical_signals']) else "",
                'fundamental_scores': str(row['fundamental_scores']) if pd.notna(row['fundamental_scores']) else "",
                'created_at': str(row['created_at']) if pd.notna(row['created_at']) else None,
                'updated_at': str(row['updated_at']) if pd.notna(row['updated_at']) else None
            }
            
        except Exception as e:
            logger.error(f"Failed to get analysis: {e}")
            return self._get_mock_analysis(date)
    
    async def get_analysis_history(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get analysis history for the last N days."""
        if not self.db:
            return []
        
        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            
            query = """
                SELECT 
                    analysis_date, analysis_type, analysis_summary,
                    market_sentiment, created_at
                FROM portfolio_analysis 
                WHERE user_id = %(user_id)s
                AND analysis_date >= %(start_date)s
                AND analysis_date <= %(end_date)s
                ORDER BY analysis_date DESC, created_at DESC
            """
            
            df = self.db.execute_query(query, {
                'user_id': self.user_id,
                'start_date': start_date,
                'end_date': end_date
            })
            
            history = []
            for _, row in df.iterrows():
                history.append({
                    'analysis_date': str(row['analysis_date']),
                    'analysis_type': str(row['analysis_type']),
                    'analysis_summary': str(row['analysis_summary']),
                    'market_sentiment': str(row['market_sentiment']) if pd.notna(row['market_sentiment']) else "",
                    'created_at': str(row['created_at']) if pd.notna(row['created_at']) else None
                })
            
            return history
            
        except Exception as e:
            logger.error(f"Failed to get analysis history: {e}")
            return []
    
    async def _run_analysis(self, task_id: str, analysis_type: str):
        """Run the actual analysis process."""
        try:
            analysis_date = datetime.now().date()
            
            # Generate comprehensive analysis
            analysis_data = await self._generate_analysis(analysis_date, analysis_type)
            
            if analysis_data:
                # Save to database
                await self._save_analysis(analysis_data)
                logger.info(f"Analysis task {task_id} completed successfully")
            else:
                logger.error(f"Analysis task {task_id} failed to generate data")
                
        except Exception as e:
            logger.error(f"Analysis task {task_id} failed: {e}")
    
    async def _generate_analysis(self, analysis_date: date, 
                               analysis_type: str) -> Optional[Dict[str, Any]]:
        """Generate comprehensive analysis using ClickHouse data and AI."""
        try:
            # Get user positions
            positions = await self._get_user_positions()
            if not positions:
                return self._get_mock_analysis(str(analysis_date))
            
            # Analyze market environment
            market_env = await self._analyze_market_environment(analysis_date)
            
            # Analyze individual stocks
            stock_analyses = await self._analyze_stocks(positions, analysis_date)
            
            # Calculate portfolio metrics
            portfolio_metrics = await self._calculate_portfolio_metrics(positions)
            
            # Generate risk alerts
            risk_alerts = await self._generate_risk_alerts(positions, portfolio_metrics)
            
            # Generate AI recommendations
            recommendations = await self._generate_recommendations(
                positions, stock_analyses, market_env, portfolio_metrics
            )
            
            # Create analysis summary
            analysis_summary = await self._create_analysis_summary(
                portfolio_metrics, market_env, len(risk_alerts), len(recommendations)
            )
            
            analysis_id = str(uuid.uuid4())
            
            return {
                'id': analysis_id,
                'user_id': self.user_id,
                'analysis_date': str(analysis_date),
                'analysis_type': analysis_type,
                'analysis_summary': analysis_summary,
                'stock_analyses': stock_analyses,
                'risk_alerts': risk_alerts,
                'recommendations': recommendations,
                'market_sentiment': market_env.get('sentiment', 'neutral'),
                'technical_signals': json.dumps(market_env.get('technical_signals', {})),
                'fundamental_scores': json.dumps(market_env.get('fundamental_scores', {})),
                'created_at': str(datetime.now()),
                'updated_at': str(datetime.now())
            }
            
        except Exception as e:
            logger.error(f"Failed to generate analysis: {e}")
            return None
    
    async def _get_user_positions(self) -> List[Dict[str, Any]]:
        """Get user positions from ClickHouse."""
        if not self.db:
            return []
        
        try:
            query = """
                SELECT 
                    ts_code, stock_name, quantity, cost_price, 
                    current_price, market_value, profit_loss, profit_rate,
                    sector, industry, buy_date
                FROM user_positions 
                WHERE user_id = %(user_id)s AND is_active = 1
                ORDER BY market_value DESC
            """
            
            df = self.db.execute_query(query, {'user_id': self.user_id})
            return df.to_dict('records') if not df.empty else []
            
        except Exception as e:
            logger.error(f"Failed to get user positions: {e}")
            return []
    
    async def _analyze_market_environment(self, analysis_date: date) -> Dict[str, Any]:
        """Analyze market environment using ClickHouse aggregations."""
        try:
            if not self.db:
                return self._get_mock_market_environment()
            
            # Get market indices performance
            indices_query = """
                SELECT 
                    ts_code,
                    close as current_price,
                    close - lag(close, 1) OVER (PARTITION BY ts_code ORDER BY trade_date) as price_change,
                    (close - lag(close, 1) OVER (PARTITION BY ts_code ORDER BY trade_date)) / lag(close, 1) OVER (PARTITION BY ts_code ORDER BY trade_date) * 100 as change_pct
                FROM ods_daily 
                WHERE ts_code IN ('000001.SH', '399001.SZ', '399006.SZ')  -- 上证指数, 深证成指, 创业板指
                AND trade_date = (SELECT max(trade_date) FROM ods_daily)
            """
            
            indices_df = self.db.execute_query(indices_query)
            
            # Calculate market sentiment
            sentiment_score = 0.0
            if not indices_df.empty:
                avg_change = indices_df['change_pct'].mean()
                sentiment_score = max(-1.0, min(1.0, avg_change / 5.0))  # Normalize to -1 to 1
            
            # Determine market trend
            if sentiment_score > 0.2:
                market_trend = 'bullish'
            elif sentiment_score < -0.2:
                market_trend = 'bearish'
            else:
                market_trend = 'neutral'
            
            # Calculate volatility (simplified)
            volatility_level = 'medium'  # Would need more historical data for accurate calculation
            
            return {
                'analysis_date': str(analysis_date),
                'market_trend': market_trend,
                'volatility_level': volatility_level,
                'sentiment_score': sentiment_score,
                'sentiment': market_trend,
                'key_events': ['市场整体表现平稳', '关注政策变化'],
                'sector_performance': {},
                'risk_factors': ['市场波动风险', '政策风险'],
                'technical_signals': {'trend': market_trend, 'strength': abs(sentiment_score)},
                'fundamental_scores': {'market_health': 75.0}
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze market environment: {e}")
            return self._get_mock_market_environment()
    
    async def _analyze_stocks(self, positions: List[Dict[str, Any]], 
                            analysis_date: date) -> Dict[str, Any]:
        """Analyze individual stocks using technical and fundamental data."""
        stock_analyses = {}
        
        for position in positions:
            ts_code = position['ts_code']
            
            try:
                # Get technical indicators
                technical_score = await self._calculate_technical_score(ts_code)
                
                # Get fundamental score (simplified)
                fundamental_score = await self._calculate_fundamental_score(ts_code)
                
                # Calculate risk score
                risk_score = await self._calculate_risk_score(position)
                
                # Generate recommendation
                recommendation = self._generate_stock_recommendation(
                    technical_score, fundamental_score, risk_score
                )
                
                stock_analyses[ts_code] = {
                    'stock_name': position['stock_name'],
                    'current_price': position.get('current_price', 0),
                    'profit_rate': position.get('profit_rate', 0),
                    'technical_score': technical_score,
                    'fundamental_score': fundamental_score,
                    'risk_score': risk_score,
                    'recommendation': recommendation,
                    'key_points': self._generate_key_points(position, technical_score, fundamental_score)
                }
                
            except Exception as e:
                logger.warning(f"Failed to analyze stock {ts_code}: {e}")
                continue
        
        return stock_analyses
    
    async def _calculate_technical_score(self, ts_code: str) -> float:
        """Calculate technical analysis score using ClickHouse."""
        try:
            if not self.db:
                return 65.0  # Mock score
            
            # Get latest technical indicators
            query = """
                SELECT ma5, ma10, ma20, rsi, macd, macd_signal
                FROM technical_indicators 
                WHERE ts_code = %(ts_code)s
                ORDER BY indicator_date DESC
                LIMIT 1
            """
            
            df = self.db.execute_query(query, {'ts_code': ts_code})
            
            if df.empty:
                return 65.0  # Default score
            
            row = df.iloc[0]
            score = 50.0  # Base score
            
            # MA trend analysis
            if pd.notna(row['ma5']) and pd.notna(row['ma10']) and pd.notna(row['ma20']):
                if row['ma5'] > row['ma10'] > row['ma20']:
                    score += 15  # Uptrend
                elif row['ma5'] < row['ma10'] < row['ma20']:
                    score -= 15  # Downtrend
            
            # RSI analysis
            if pd.notna(row['rsi']):
                rsi = float(row['rsi'])
                if 30 <= rsi <= 70:
                    score += 10  # Neutral zone
                elif rsi < 30:
                    score += 5   # Oversold (potential buy)
                elif rsi > 70:
                    score -= 5   # Overbought (potential sell)
            
            # MACD analysis
            if pd.notna(row['macd']) and pd.notna(row['macd_signal']):
                if row['macd'] > row['macd_signal']:
                    score += 10  # Bullish signal
                else:
                    score -= 10  # Bearish signal
            
            return max(0, min(100, score))
            
        except Exception as e:
            logger.warning(f"Failed to calculate technical score for {ts_code}: {e}")
            return 65.0
    
    async def _calculate_fundamental_score(self, ts_code: str) -> float:
        """Calculate fundamental analysis score."""
        try:
            # This would typically use financial data from ClickHouse
            # For now, return a mock score based on some basic logic
            return 70.0  # Mock fundamental score
            
        except Exception as e:
            logger.warning(f"Failed to calculate fundamental score for {ts_code}: {e}")
            return 70.0
    
    async def _calculate_risk_score(self, position: Dict[str, Any]) -> float:
        """Calculate risk score for a position."""
        try:
            risk_score = 50.0  # Base risk
            
            # Position size risk
            profit_rate = position.get('profit_rate', 0)
            if abs(profit_rate) > 20:
                risk_score += 20  # High volatility
            elif abs(profit_rate) > 10:
                risk_score += 10  # Medium volatility
            
            # Sector concentration risk (would need portfolio context)
            # For now, use a simple calculation
            
            return max(0, min(100, risk_score))
            
        except Exception as e:
            logger.warning(f"Failed to calculate risk score: {e}")
            return 50.0
    
    def _generate_stock_recommendation(self, technical_score: float, 
                                     fundamental_score: float, risk_score: float) -> str:
        """Generate stock recommendation based on scores."""
        combined_score = (technical_score + fundamental_score) / 2 - (risk_score - 50)
        
        if combined_score >= 80:
            return 'strong_buy'
        elif combined_score >= 65:
            return 'buy'
        elif combined_score >= 35:
            return 'hold'
        elif combined_score >= 20:
            return 'sell'
        else:
            return 'strong_sell'
    
    def _generate_key_points(self, position: Dict[str, Any], 
                           technical_score: float, fundamental_score: float) -> List[str]:
        """Generate key analysis points for a stock."""
        points = []
        
        profit_rate = position.get('profit_rate', 0)
        if profit_rate > 10:
            points.append(f"当前盈利{profit_rate:.1f}%，表现良好")
        elif profit_rate < -10:
            points.append(f"当前亏损{abs(profit_rate):.1f}%，需要关注")
        
        if technical_score > 70:
            points.append("技术面表现强势")
        elif technical_score < 40:
            points.append("技术面偏弱，谨慎操作")
        
        if fundamental_score > 70:
            points.append("基本面健康")
        elif fundamental_score < 40:
            points.append("基本面存在风险")
        
        return points
    
    async def _calculate_portfolio_metrics(self, positions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate portfolio-level metrics."""
        if not positions:
            return {}
        
        total_value = sum(pos.get('market_value', 0) for pos in positions)
        total_cost = sum(pos.get('quantity', 0) * pos.get('cost_price', 0) for pos in positions)
        total_profit = total_value - total_cost
        profit_rate = (total_profit / total_cost * 100) if total_cost > 0 else 0
        
        # Calculate sector distribution
        sector_distribution = {}
        for pos in positions:
            sector = pos.get('sector', '未知')
            value = pos.get('market_value', 0)
            sector_distribution[sector] = sector_distribution.get(sector, 0) + value
        
        # Normalize to percentages
        if total_value > 0:
            sector_distribution = {k: v/total_value*100 for k, v in sector_distribution.items()}
        
        return {
            'total_value': total_value,
            'total_cost': total_cost,
            'total_profit': total_profit,
            'profit_rate': profit_rate,
            'position_count': len(positions),
            'sector_distribution': sector_distribution
        }
    
    async def _generate_risk_alerts(self, positions: List[Dict[str, Any]], 
                                  portfolio_metrics: Dict[str, Any]) -> List[str]:
        """Generate risk alerts based on analysis."""
        alerts = []
        
        # Portfolio level alerts
        profit_rate = portfolio_metrics.get('profit_rate', 0)
        if profit_rate < -15:
            alerts.append(f"投资组合整体亏损{abs(profit_rate):.1f}%，建议重新评估投资策略")
        
        # Position level alerts
        for pos in positions:
            pos_profit_rate = pos.get('profit_rate', 0)
            if pos_profit_rate < -20:
                alerts.append(f"{pos['stock_name']}亏损{abs(pos_profit_rate):.1f}%，建议考虑止损")
            elif pos_profit_rate > 30:
                alerts.append(f"{pos['stock_name']}盈利{pos_profit_rate:.1f}%，建议考虑止盈")
        
        # Concentration risk
        sector_dist = portfolio_metrics.get('sector_distribution', {})
        for sector, percentage in sector_dist.items():
            if percentage > 50:
                alerts.append(f"{sector}板块占比{percentage:.1f}%，存在集中度风险")
        
        return alerts
    
    async def _generate_recommendations(self, positions: List[Dict[str, Any]], 
                                     stock_analyses: Dict[str, Any],
                                     market_env: Dict[str, Any],
                                     portfolio_metrics: Dict[str, Any]) -> List[str]:
        """Generate investment recommendations."""
        recommendations = []
        
        # Market-based recommendations
        market_trend = market_env.get('market_trend', 'neutral')
        if market_trend == 'bullish':
            recommendations.append("市场趋势向好，可适当增加仓位")
        elif market_trend == 'bearish':
            recommendations.append("市场趋势偏弱，建议降低仓位或加强防御")
        
        # Stock-specific recommendations
        for ts_code, analysis in stock_analyses.items():
            recommendation = analysis.get('recommendation', 'hold')
            stock_name = analysis.get('stock_name', ts_code)
            
            if recommendation == 'strong_buy':
                recommendations.append(f"强烈推荐增持{stock_name}")
            elif recommendation == 'strong_sell':
                recommendations.append(f"建议减持{stock_name}")
        
        # Portfolio optimization recommendations
        profit_rate = portfolio_metrics.get('profit_rate', 0)
        if profit_rate > 15:
            recommendations.append("投资组合表现优秀，建议保持当前策略")
        elif profit_rate < -10:
            recommendations.append("投资组合表现不佳，建议调整投资策略")
        
        return recommendations
    
    async def _create_analysis_summary(self, portfolio_metrics: Dict[str, Any],
                                     market_env: Dict[str, Any], 
                                     risk_count: int, rec_count: int) -> str:
        """Create analysis summary text."""
        profit_rate = portfolio_metrics.get('profit_rate', 0)
        position_count = portfolio_metrics.get('position_count', 0)
        market_trend = market_env.get('market_trend', 'neutral')
        
        summary_parts = []
        
        # Portfolio performance
        if profit_rate > 5:
            summary_parts.append(f"您的投资组合表现良好，整体盈利{profit_rate:.1f}%")
        elif profit_rate > 0:
            summary_parts.append(f"您的投资组合小幅盈利{profit_rate:.1f}%")
        elif profit_rate > -5:
            summary_parts.append(f"您的投资组合小幅亏损{abs(profit_rate):.1f}%")
        else:
            summary_parts.append(f"您的投资组合亏损{abs(profit_rate):.1f}%，需要关注")
        
        # Market condition
        market_desc = {
            'bullish': '市场整体向好',
            'bearish': '市场整体偏弱', 
            'neutral': '市场震荡整理'
        }
        summary_parts.append(market_desc.get(market_trend, '市场表现平稳'))
        
        # Risk and recommendations
        if risk_count > 0:
            summary_parts.append(f"发现{risk_count}个风险提示")
        if rec_count > 0:
            summary_parts.append(f"提供{rec_count}条投资建议")
        
        return "，".join(summary_parts) + "。"
    
    async def _save_analysis(self, analysis_data: Dict[str, Any]):
        """Save analysis to ClickHouse."""
        if not self.db:
            return
        
        try:
            query = """
                INSERT INTO portfolio_analysis 
                (id, user_id, analysis_date, analysis_type, analysis_summary,
                 stock_analyses, risk_alerts, recommendations, market_sentiment,
                 technical_signals, fundamental_scores, created_at, updated_at)
                VALUES (%(id)s, %(user_id)s, %(analysis_date)s, %(analysis_type)s,
                        %(analysis_summary)s, %(stock_analyses)s, %(risk_alerts)s,
                        %(recommendations)s, %(market_sentiment)s, %(technical_signals)s,
                        %(fundamental_scores)s, %(created_at)s, %(updated_at)s)
            """
            
            params = {
                'id': analysis_data['id'],
                'user_id': analysis_data['user_id'],
                'analysis_date': analysis_data['analysis_date'],
                'analysis_type': analysis_data['analysis_type'],
                'analysis_summary': analysis_data['analysis_summary'],
                'stock_analyses': json.dumps(analysis_data['stock_analyses'], ensure_ascii=False),
                'risk_alerts': json.dumps(analysis_data['risk_alerts'], ensure_ascii=False),
                'recommendations': json.dumps(analysis_data['recommendations'], ensure_ascii=False),
                'market_sentiment': analysis_data['market_sentiment'],
                'technical_signals': analysis_data['technical_signals'],
                'fundamental_scores': analysis_data['fundamental_scores'],
                'created_at': analysis_data['created_at'],
                'updated_at': analysis_data['updated_at']
            }
            
            self.db.execute(query, params)
            logger.info(f"Analysis {analysis_data['id']} saved successfully")
            
        except Exception as e:
            logger.error(f"Failed to save analysis: {e}")
    
    def _safe_json_parse(self, json_str: str) -> Any:
        """Safely parse JSON string."""
        try:
            if pd.isna(json_str) or not json_str:
                return {}
            return json.loads(json_str)
        except:
            return {}
    
    def _get_mock_analysis(self, date: Optional[str] = None) -> Dict[str, Any]:
        """Get mock analysis data."""
        analysis_date = date or str(datetime.now().date())
        
        return {
            'id': str(uuid.uuid4()),
            'analysis_date': analysis_date,
            'analysis_type': 'daily',
            'analysis_summary': '您的投资组合表现良好，整体盈利5.8%，市场整体向好，发现1个风险提示，提供3条投资建议。',
            'stock_analyses': {
                '600519.SH': {
                    'stock_name': '贵州茅台',
                    'current_price': 1800.0,
                    'profit_rate': 5.88,
                    'technical_score': 75.0,
                    'fundamental_score': 80.0,
                    'risk_score': 45.0,
                    'recommendation': 'hold',
                    'key_points': ['当前盈利5.9%，表现良好', '技术面表现强势', '基本面健康']
                }
            },
            'risk_alerts': ['市场波动加大，注意风险控制'],
            'recommendations': ['建议继续持有贵州茅台', '可考虑适当分散投资', '关注市场政策变化'],
            'market_sentiment': 'bullish',
            'technical_signals': '{"trend": "bullish", "strength": 0.6}',
            'fundamental_scores': '{"market_health": 75.0}',
            'created_at': str(datetime.now()),
            'updated_at': str(datetime.now())
        }
    
    def _get_mock_market_environment(self) -> Dict[str, Any]:
        """Get mock market environment data."""
        return {
            'analysis_date': str(datetime.now().date()),
            'market_trend': 'bullish',
            'volatility_level': 'medium',
            'sentiment_score': 0.3,
            'sentiment': 'bullish',
            'key_events': ['市场整体表现良好', '政策环境稳定'],
            'sector_performance': {'科技': 2.5, '消费': 1.8, '金融': -0.5},
            'risk_factors': ['市场波动风险', '政策变化风险'],
            'technical_signals': {'trend': 'bullish', 'strength': 0.6},
            'fundamental_scores': {'market_health': 75.0}
        }
    target_price: Optional[float]
    stop_loss: Optional[float]
    key_points: List[str]
    technical_indicators: Dict[str, Any]
    fundamental_metrics: Dict[str, Any]


class DailyAnalysisService:
    """Service for generating daily portfolio analysis reports."""
    
    def __init__(self):
        self._db = None
        self._portfolio_service = None
        self._market_agent = None
        self._portfolio_agent = None
    
    @property
    def db(self):
        """Lazy load database client."""
        if self._db is None:
            try:
                from stock_datasource.models.database import db_client
                self._db = db_client
            except Exception as e:
                logger.warning(f"Failed to get DB client: {e}")
        return self._db
    
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
    def market_agent(self):
        """Lazy load market agent."""
        if self._market_agent is None:
            try:
                from stock_datasource.agents.market_agent import MarketAgent
                from stock_datasource.agents.base_agent import AgentConfig
                config = AgentConfig(
                    name="market_agent",
                    description="Market analysis agent",
                    model_name="deepseek-chat",
                    temperature=0.3
                )
                self._market_agent = MarketAgent(config)
            except Exception as e:
                logger.warning(f"Failed to get market agent: {e}")
        return self._market_agent
    
    @property
    def portfolio_agent(self):
        """Lazy load portfolio agent."""
        if self._portfolio_agent is None:
            try:
                from stock_datasource.agents.portfolio_agent import PortfolioAgent
                from stock_datasource.agents.base_agent import AgentConfig
                config = AgentConfig(
                    name="portfolio_agent",
                    description="Portfolio analysis agent",
                    model_name="deepseek-chat",
                    temperature=0.3
                )
                self._portfolio_agent = PortfolioAgent(config)
            except Exception as e:
                logger.warning(f"Failed to get portfolio agent: {e}")
        return self._portfolio_agent
    
    async def run_daily_analysis(self, user_id: str = "default_user", 
                                analysis_date: Optional[date] = None) -> AnalysisReport:
        """Run comprehensive daily analysis for user portfolio."""
        if analysis_date is None:
            analysis_date = date.today()
        
        logger.info(f"Starting daily analysis for user {user_id} on {analysis_date}")
        
        # Create analysis report record
        report = AnalysisReport(
            id=str(uuid.uuid4()),
            user_id=user_id,
            report_date=analysis_date,
            report_type='daily',
            market_analysis="",
            portfolio_summary="",
            individual_analysis="",
            risk_assessment="",
            recommendations="",
            ai_insights="",
            status='pending',
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        try:
            # Save initial report
            await self._save_report(report)
            
            # Step 1: Analyze market environment
            logger.info("Analyzing market environment...")
            market_env = await self._analyze_market_environment(analysis_date)
            report.market_analysis = self._format_market_analysis(market_env)
            
            # Step 2: Get portfolio summary
            logger.info("Analyzing portfolio summary...")
            if self.portfolio_service:
                portfolio_summary = await self.portfolio_service.get_summary(user_id)
                report.portfolio_summary = self._format_portfolio_summary(portfolio_summary)
            
            # Step 3: Analyze individual positions
            logger.info("Analyzing individual positions...")
            if self.portfolio_service:
                positions = await self.portfolio_service.get_positions(user_id)
                stock_analyses = []
                for position in positions:
                    analysis = await self._analyze_individual_stock(position, market_env)
                    stock_analyses.append(analysis)
                report.individual_analysis = self._format_individual_analysis(stock_analyses)
            
            # Step 4: Risk assessment
            logger.info("Performing risk assessment...")
            risk_assessment = await self._assess_portfolio_risk(user_id, market_env)
            report.risk_assessment = self._format_risk_assessment(risk_assessment)
            
            # Step 5: Generate recommendations
            logger.info("Generating recommendations...")
            recommendations = await self._generate_recommendations(user_id, market_env, stock_analyses)
            report.recommendations = self._format_recommendations(recommendations)
            
            # Step 6: AI insights
            logger.info("Generating AI insights...")
            ai_insights = await self._generate_ai_insights(report, market_env)
            report.ai_insights = ai_insights
            
            # Mark as completed
            report.status = 'completed'
            report.updated_at = datetime.now()
            
            # Save final report
            await self._save_report(report)
            
            logger.info(f"Daily analysis completed for user {user_id}")
            return report
            
        except Exception as e:
            logger.error(f"Daily analysis failed: {e}")
            report.status = 'failed'
            report.updated_at = datetime.now()
            await self._save_report(report)
            raise
    
    async def get_analysis_report(self, user_id: str, report_date: date) -> Optional[AnalysisReport]:
        """Get analysis report for specific date."""
        try:
            if self.db is not None:
                query = """
                    SELECT * FROM daily_analysis_reports
                    WHERE user_id = %(user_id)s AND report_date = %(report_date)s
                    AND report_type = 'daily'
                    ORDER BY created_at DESC
                    LIMIT 1
                """
                df = self.db.execute_query(query, {
                    'user_id': user_id,
                    'report_date': report_date
                })
                
                if not df.empty:
                    row = df.iloc[0]
                    return AnalysisReport(
                        id=str(row['id']),
                        user_id=str(row['user_id']),
                        report_date=row['report_date'],
                        report_type=row['report_type'],
                        market_analysis=row['market_analysis'],
                        portfolio_summary=row['portfolio_summary'],
                        individual_analysis=row['individual_analysis'],
                        risk_assessment=row['risk_assessment'],
                        recommendations=row['recommendations'],
                        ai_insights=row['ai_insights'],
                        status=row['status'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at']
                    )
        except Exception as e:
            logger.error(f"Failed to get analysis report: {e}")
        
        return None
    
    async def get_analysis(self, date: Optional[str] = None, 
                          analysis_type: str = "daily") -> Optional[Dict[str, Any]]:
        """Get analysis report for a specific date (compatible with router)."""
        try:
            from datetime import datetime as dt
            target_date = dt.strptime(date, "%Y-%m-%d").date() if date else dt.now().date()
            
            # Try to get existing report
            report = await self.get_analysis_report("default_user", target_date)
            
            if report:
                return {
                    'id': report.id,
                    'analysis_date': str(report.report_date),
                    'analysis_type': report.report_type,
                    'analysis_summary': report.ai_insights or "投资组合表现良好",
                    'stock_analyses': json.loads(report.individual_analysis) if report.individual_analysis else {},
                    'risk_alerts': [report.risk_assessment] if report.risk_assessment else [],
                    'recommendations': json.loads(report.recommendations) if report.recommendations else []
                }
            
            # Return mock data if no report found
            return self._get_mock_analysis(date)
            
        except Exception as e:
            logger.error(f"Failed to get analysis: {e}")
            return self._get_mock_analysis(date)
    
    def _get_mock_analysis(self, date: Optional[str] = None) -> Dict[str, Any]:
        """Get mock analysis data for fallback."""
        from datetime import datetime as dt
        analysis_date = date or str(dt.now().date())
        
        return {
            'id': str(uuid.uuid4()),
            'analysis_date': analysis_date,
            'analysis_type': 'daily',
            'analysis_summary': '您的投资组合表现良好，整体盈利5.8%，市场整体向好，发现1个风险提示，提供3条投资建议。',
            'stock_analyses': {
                '600519.SH': {
                    'stock_name': '贵州茅台',
                    'current_price': 1800.0,
                    'profit_rate': 5.88,
                    'technical_score': 75.0,
                    'fundamental_score': 80.0,
                    'risk_score': 45.0,
                    'recommendation': 'hold',
                    'key_points': ['当前盈利5.9%，表现良好', '技术面表现强势', '基本面健康']
                }
            },
            'risk_alerts': ['市场波动加大，注意风险控制'],
            'recommendations': ['建议继续持有贵州茅台', '可考虑适当分散投资', '关注市场政策变化']
        }

    async def get_analysis_history(self, user_id: str, days: int = 30) -> List[AnalysisReport]:
        """Get analysis report history."""
        try:
            if self.db is not None:
                query = """
                    SELECT * FROM daily_analysis_reports
                    WHERE user_id = %(user_id)s 
                    AND report_date >= %(start_date)s
                    ORDER BY report_date DESC
                """
                start_date = date.today() - timedelta(days=days)
                df = self.db.execute_query(query, {
                    'user_id': user_id,
                    'start_date': start_date
                })
                
                if not df.empty:
                    reports = []
                    for _, row in df.iterrows():
                        report = AnalysisReport(
                            id=str(row['id']),
                            user_id=str(row['user_id']),
                            report_date=row['report_date'],
                            report_type=row['report_type'],
                            market_analysis=row['market_analysis'],
                            portfolio_summary=row['portfolio_summary'],
                            individual_analysis=row['individual_analysis'],
                            risk_assessment=row['risk_assessment'],
                            recommendations=row['recommendations'],
                            ai_insights=row['ai_insights'],
                            status=row['status'],
                            created_at=row['created_at'],
                            updated_at=row['updated_at']
                        )
                        reports.append(report)
                    return reports
        except Exception as e:
            logger.error(f"Failed to get analysis history: {e}")
        
        return []
    
    # Private analysis methods
    async def _analyze_market_environment(self, analysis_date: date) -> MarketEnvironment:
        """Analyze current market environment."""
        # Mock market environment analysis
        return MarketEnvironment(
            market_trend='neutral',
            volatility_level='medium',
            sentiment_score=0.1,
            key_events=['央行政策会议', '经济数据发布'],
            sector_performance={
                '金融': 1.2,
                '科技': -0.8,
                '消费': 0.5,
                '医药': 2.1
            },
            risk_factors=['地缘政治风险', '通胀压力']
        )
    
    async def _analyze_individual_stock(self, position, market_env: MarketEnvironment) -> StockAnalysis:
        """Analyze individual stock."""
        # Mock individual stock analysis
        return StockAnalysis(
            ts_code=position.ts_code,
            stock_name=position.stock_name,
            technical_score=75.0,
            fundamental_score=80.0,
            risk_score=30.0,
            recommendation='hold',
            target_price=position.current_price * 1.1 if position.current_price else None,
            stop_loss=position.current_price * 0.9 if position.current_price else None,
            key_points=['技术指标良好', '基本面稳健', '估值合理'],
            technical_indicators={
                'ma20': position.current_price * 0.98 if position.current_price else 0,
                'rsi': 55.0,
                'macd': 0.1
            },
            fundamental_metrics={
                'pe_ratio': 25.0,
                'pb_ratio': 3.2,
                'roe': 15.5
            }
        )
    
    async def _assess_portfolio_risk(self, user_id: str, market_env: MarketEnvironment) -> Dict[str, Any]:
        """Assess portfolio risk."""
        return {
            'overall_risk': 'medium',
            'concentration_risk': 'low',
            'market_risk': 'medium',
            'liquidity_risk': 'low',
            'risk_score': 45.0,
            'recommendations': [
                '适当分散投资',
                '关注市场波动',
                '保持流动性'
            ]
        }
    
    async def _generate_recommendations(self, user_id: str, market_env: MarketEnvironment, 
                                      stock_analyses: List[StockAnalysis]) -> List[Dict[str, Any]]:
        """Generate investment recommendations."""
        return [
            {
                'type': 'portfolio',
                'action': 'rebalance',
                'description': '建议适当调整仓位配置',
                'priority': 'medium'
            },
            {
                'type': 'risk',
                'action': 'monitor',
                'description': '密切关注市场风险变化',
                'priority': 'high'
            }
        ]
    
    async def _generate_ai_insights(self, report: AnalysisReport, 
                                   market_env: MarketEnvironment) -> str:
        """Generate AI-powered insights."""
        # This would use the portfolio agent to generate insights
        insights = f"""
        基于当前市场环境和投资组合分析，以下是AI生成的投资洞察：

        1. 市场环境：当前市场呈现{market_env.market_trend}趋势，波动性{market_env.volatility_level}
        
        2. 投资组合表现：整体表现符合预期，建议保持当前配置
        
        3. 风险提示：注意{', '.join(market_env.risk_factors)}
        
        4. 操作建议：建议在当前市场环境下保持谨慎乐观的态度
        """
        
        return insights.strip()
    
    # Formatting methods
    def _format_market_analysis(self, market_env: MarketEnvironment) -> str:
        """Format market analysis."""
        return json.dumps({
            'trend': market_env.market_trend,
            'volatility': market_env.volatility_level,
            'sentiment': market_env.sentiment_score,
            'events': market_env.key_events,
            'sector_performance': market_env.sector_performance,
            'risk_factors': market_env.risk_factors
        }, ensure_ascii=False, indent=2)
    
    def _format_portfolio_summary(self, summary) -> str:
        """Format portfolio summary."""
        return json.dumps({
            'total_value': summary.total_value,
            'total_cost': summary.total_cost,
            'total_profit': summary.total_profit,
            'profit_rate': summary.profit_rate,
            'position_count': summary.position_count,
            'top_performer': summary.top_performer,
            'worst_performer': summary.worst_performer,
            'sector_distribution': summary.sector_distribution
        }, ensure_ascii=False, indent=2)
    
    def _format_individual_analysis(self, analyses: List[StockAnalysis]) -> str:
        """Format individual stock analyses."""
        formatted_analyses = []
        for analysis in analyses:
            formatted_analyses.append({
                'ts_code': analysis.ts_code,
                'stock_name': analysis.stock_name,
                'technical_score': analysis.technical_score,
                'fundamental_score': analysis.fundamental_score,
                'risk_score': analysis.risk_score,
                'recommendation': analysis.recommendation,
                'target_price': analysis.target_price,
                'stop_loss': analysis.stop_loss,
                'key_points': analysis.key_points
            })
        
        return json.dumps(formatted_analyses, ensure_ascii=False, indent=2)
    
    def _format_risk_assessment(self, risk_data: Dict[str, Any]) -> str:
        """Format risk assessment."""
        return json.dumps(risk_data, ensure_ascii=False, indent=2)
    
    def _format_recommendations(self, recommendations: List[Dict[str, Any]]) -> str:
        """Format recommendations."""
        return json.dumps(recommendations, ensure_ascii=False, indent=2)
    
    async def _save_report(self, report: AnalysisReport):
        """Save analysis report to database."""
        try:
            if self.db is not None:
                query = """
                    INSERT INTO daily_analysis_reports
                    (id, user_id, report_date, report_type, market_analysis, portfolio_summary,
                     individual_analysis, risk_assessment, recommendations, ai_insights, 
                     status, created_at, updated_at)
                    VALUES (%(id)s, %(user_id)s, %(report_date)s, %(report_type)s, 
                            %(market_analysis)s, %(portfolio_summary)s, %(individual_analysis)s,
                            %(risk_assessment)s, %(recommendations)s, %(ai_insights)s,
                            %(status)s, %(created_at)s, %(updated_at)s)
                """
                params = asdict(report)
                self.db.execute(query, params)
                logger.info(f"Analysis report {report.id} saved")
        except Exception as e:
            logger.error(f"Failed to save analysis report: {e}")


# Global service instance
_daily_analysis_service = None


def get_daily_analysis_service() -> DailyAnalysisService:
    """Get daily analysis service instance."""
    global _daily_analysis_service
    if _daily_analysis_service is None:
        _daily_analysis_service = DailyAnalysisService()
    return _daily_analysis_service