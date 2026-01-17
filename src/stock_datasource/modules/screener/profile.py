"""股票十维画像计算服务

优先使用 Plugin Services 获取数据。
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import numpy as np

from stock_datasource.models.database import db_client
from stock_datasource.plugins.tushare_daily_basic.service import TuShareDailyBasicService
from stock_datasource.plugins.tushare_stock_basic.service import TuShareStockBasicService
from stock_datasource.plugins.tushare_daily.service import TuShareDailyService

from .schemas import StockProfile, ProfileDimension

logger = logging.getLogger(__name__)


# 十维画像权重配置
DIMENSION_WEIGHTS = {
    "valuation": 0.15,      # 估值维度
    "growth": 0.15,         # 成长维度
    "profitability": 0.10,  # 盈利维度
    "momentum": 0.15,       # 动量维度
    "trend": 0.10,          # 趋势维度
    "volume": 0.10,         # 量能维度
    "volatility": 0.05,     # 波动维度
    "capital_flow": 0.10,   # 资金维度
    "sentiment": 0.05,      # 情绪维度
    "risk": 0.05,           # 风险维度
}


def _format_date(date_val) -> Optional[str]:
    """Format date value to YYYY-MM-DD string."""
    if date_val is None:
        return None
    if isinstance(date_val, str):
        return date_val.split()[0].split('T')[0]
    if hasattr(date_val, 'strftime'):
        return date_val.strftime('%Y-%m-%d')
    return str(date_val).split()[0]


def _score_to_level(score: float) -> str:
    """将评分转换为等级"""
    if score >= 80:
        return "优秀"
    elif score >= 60:
        return "良好"
    elif score >= 40:
        return "中等"
    else:
        return "较差"


def _calculate_percentile(value: float, values: List[float], reverse: bool = False) -> float:
    """计算百分位排名 (0-100)"""
    if not values or value is None:
        return 50.0
    
    values_sorted = sorted(values)
    rank = sum(1 for v in values_sorted if v < value) / len(values_sorted) * 100
    
    if reverse:
        rank = 100 - rank
    
    return min(100, max(0, rank))


class ProfileService:
    """股票十维画像服务"""
    
    def __init__(self):
        self.db = db_client
        self.daily_basic_service = TuShareDailyBasicService()
        self.stock_basic_service = TuShareStockBasicService()
        self.daily_service = TuShareDailyService()
    
    def get_latest_trade_date(self) -> Optional[str]:
        """获取最新交易日期"""
        try:
            query = "SELECT max(trade_date) as max_date FROM ods_daily"
            df = self.db.execute_query(query)
            if df.empty or df.iloc[0]['max_date'] is None:
                return None
            return _format_date(df.iloc[0]['max_date'])
        except Exception as e:
            logger.error(f"Failed to get latest trade date: {e}")
            return None
    
    def _get_stock_info(self, ts_code: str) -> Dict[str, Any]:
        """获取股票基本信息"""
        try:
            result = self.stock_basic_service.get_stock_basic(ts_code)
            if result:
                return result[0]
        except Exception as e:
            logger.warning(f"Failed to get stock info for {ts_code}: {e}")
        return {"ts_code": ts_code, "name": ts_code}
    
    def _get_daily_data(self, ts_code: str, days: int = 60) -> List[Dict[str, Any]]:
        """获取最近N天的日线数据"""
        try:
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")
            result = self.daily_service.get_daily_data(ts_code, start_date, end_date)
            return result[:days] if result else []
        except Exception as e:
            logger.warning(f"Failed to get daily data for {ts_code}: {e}")
            return []
    
    def _get_valuation_data(self, ts_code: str, days: int = 60) -> List[Dict[str, Any]]:
        """获取估值数据"""
        try:
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")
            result = self.daily_basic_service.get_daily_basic(ts_code, start_date, end_date)
            return result if result else []
        except Exception as e:
            logger.warning(f"Failed to get valuation data for {ts_code}: {e}")
            return []
    
    def _get_market_pe_distribution(self) -> List[float]:
        """获取市场PE分布（用于百分位计算）"""
        try:
            latest_date = self.get_latest_trade_date()
            if not latest_date:
                return []
            
            query = f"""
                SELECT pe_ttm 
                FROM ods_daily_basic 
                WHERE trade_date = '{latest_date}' 
                AND pe_ttm > 0 AND pe_ttm < 1000
            """
            df = self.db.execute_query(query)
            return df['pe_ttm'].tolist() if not df.empty else []
        except Exception as e:
            logger.warning(f"Failed to get market PE distribution: {e}")
            return []
    
    def _get_market_pb_distribution(self) -> List[float]:
        """获取市场PB分布"""
        try:
            latest_date = self.get_latest_trade_date()
            if not latest_date:
                return []
            
            query = f"""
                SELECT pb 
                FROM ods_daily_basic 
                WHERE trade_date = '{latest_date}' 
                AND pb > 0 AND pb < 100
            """
            df = self.db.execute_query(query)
            return df['pb'].tolist() if not df.empty else []
        except Exception as e:
            logger.warning(f"Failed to get market PB distribution: {e}")
            return []
    
    def calculate_valuation_score(
        self, 
        pe_ttm: Optional[float], 
        pb: Optional[float],
        pe_distribution: List[float],
        pb_distribution: List[float]
    ) -> ProfileDimension:
        """计算估值维度评分 - 低估值得高分"""
        indicators = {"pe_ttm": pe_ttm, "pb": pb}
        
        scores = []
        if pe_ttm and pe_ttm > 0 and pe_distribution:
            # PE越低越好，使用 reverse=True
            pe_score = _calculate_percentile(pe_ttm, pe_distribution, reverse=True)
            scores.append(pe_score)
            indicators["pe_percentile"] = 100 - pe_score  # 显示原始百分位
        
        if pb and pb > 0 and pb_distribution:
            pb_score = _calculate_percentile(pb, pb_distribution, reverse=True)
            scores.append(pb_score)
            indicators["pb_percentile"] = 100 - pb_score
        
        score = np.mean(scores) if scores else 50.0
        
        return ProfileDimension(
            name="估值",
            score=round(score, 1),
            level=_score_to_level(score),
            weight=DIMENSION_WEIGHTS["valuation"],
            indicators=indicators
        )
    
    def calculate_momentum_score(self, daily_data: List[Dict[str, Any]]) -> ProfileDimension:
        """计算动量维度评分 - 基于近期涨幅"""
        indicators = {}
        scores = []
        
        if len(daily_data) >= 5:
            # 5日涨幅
            pct_5d = sum(d.get('pct_chg', 0) or 0 for d in daily_data[:5])
            indicators["pct_chg_5d"] = round(pct_5d, 2)
            # 涨幅转换为分数：+10% -> 80分，0% -> 50分，-10% -> 20分
            score_5d = min(100, max(0, 50 + pct_5d * 3))
            scores.append(score_5d)
        
        if len(daily_data) >= 20:
            # 20日涨幅
            pct_20d = sum(d.get('pct_chg', 0) or 0 for d in daily_data[:20])
            indicators["pct_chg_20d"] = round(pct_20d, 2)
            score_20d = min(100, max(0, 50 + pct_20d * 2))
            scores.append(score_20d)
        
        score = np.mean(scores) if scores else 50.0
        
        return ProfileDimension(
            name="动量",
            score=round(score, 1),
            level=_score_to_level(score),
            weight=DIMENSION_WEIGHTS["momentum"],
            indicators=indicators
        )
    
    def calculate_trend_score(self, daily_data: List[Dict[str, Any]]) -> ProfileDimension:
        """计算趋势维度评分 - 基于均线排列"""
        indicators = {}
        
        if len(daily_data) < 20:
            return ProfileDimension(
                name="趋势",
                score=50.0,
                level="中等",
                weight=DIMENSION_WEIGHTS["trend"],
                indicators={"status": "数据不足"}
            )
        
        closes = [d.get('close', 0) or 0 for d in daily_data]
        current = closes[0]
        ma5 = np.mean(closes[:5])
        ma10 = np.mean(closes[:10])
        ma20 = np.mean(closes[:20])
        
        indicators["current"] = round(current, 2)
        indicators["ma5"] = round(ma5, 2)
        indicators["ma10"] = round(ma10, 2)
        indicators["ma20"] = round(ma20, 2)
        
        # 评分逻辑
        score = 50.0
        
        # 均线多头排列加分
        if ma5 > ma10 > ma20:
            score += 30
            indicators["trend"] = "多头排列"
        elif ma5 < ma10 < ma20:
            score -= 20
            indicators["trend"] = "空头排列"
        else:
            indicators["trend"] = "震荡整理"
        
        # 价格位置加分
        if current > ma5:
            score += 10
        if current > ma10:
            score += 5
        if current > ma20:
            score += 5
        
        score = min(100, max(0, score))
        
        return ProfileDimension(
            name="趋势",
            score=round(score, 1),
            level=_score_to_level(score),
            weight=DIMENSION_WEIGHTS["trend"],
            indicators=indicators
        )
    
    def calculate_volume_score(self, daily_data: List[Dict[str, Any]], valuation_data: List[Dict[str, Any]]) -> ProfileDimension:
        """计算量能维度评分"""
        indicators = {}
        scores = []
        
        if len(daily_data) >= 10:
            volumes = [d.get('vol', 0) or 0 for d in daily_data]
            vol_ma5 = np.mean(volumes[:5])
            vol_ma10 = np.mean(volumes[:10])
            
            indicators["vol_ma5"] = round(vol_ma5, 0)
            indicators["vol_ma10"] = round(vol_ma10, 0)
            
            # 量比
            if vol_ma10 > 0:
                volume_ratio = vol_ma5 / vol_ma10
                indicators["volume_ratio"] = round(volume_ratio, 2)
                # 适度放量得高分
                if 1.0 <= volume_ratio <= 2.0:
                    scores.append(70)
                elif 0.8 <= volume_ratio < 1.0:
                    scores.append(50)
                elif volume_ratio > 2.0:
                    scores.append(60)  # 放量过大需警惕
                else:
                    scores.append(40)
        
        if valuation_data:
            latest = valuation_data[0]
            turnover = latest.get('turnover_rate')
            if turnover:
                indicators["turnover_rate"] = round(turnover, 2)
                # 换手率适中得高分
                if 1 <= turnover <= 5:
                    scores.append(70)
                elif 5 < turnover <= 10:
                    scores.append(60)
                elif turnover > 10:
                    scores.append(50)
                else:
                    scores.append(40)
        
        score = np.mean(scores) if scores else 50.0
        
        return ProfileDimension(
            name="量能",
            score=round(score, 1),
            level=_score_to_level(score),
            weight=DIMENSION_WEIGHTS["volume"],
            indicators=indicators
        )
    
    def calculate_volatility_score(self, daily_data: List[Dict[str, Any]]) -> ProfileDimension:
        """计算波动维度评分 - 低波动得高分（适合稳健投资）"""
        indicators = {}
        
        if len(daily_data) < 20:
            return ProfileDimension(
                name="波动",
                score=50.0,
                level="中等",
                weight=DIMENSION_WEIGHTS["volatility"],
                indicators={"status": "数据不足"}
            )
        
        pct_changes = [d.get('pct_chg', 0) or 0 for d in daily_data[:20]]
        volatility = np.std(pct_changes)
        indicators["volatility_20d"] = round(volatility, 2)
        
        # 波动率越低越好
        if volatility < 2:
            score = 80
        elif volatility < 3:
            score = 70
        elif volatility < 5:
            score = 50
        else:
            score = 30
        
        return ProfileDimension(
            name="波动",
            score=round(score, 1),
            level=_score_to_level(score),
            weight=DIMENSION_WEIGHTS["volatility"],
            indicators=indicators
        )
    
    def calculate_risk_score(self, ts_code: str, stock_info: Dict[str, Any]) -> ProfileDimension:
        """计算风险维度评分 - 低风险得高分"""
        indicators = {}
        score = 80.0  # 默认分数
        
        name = stock_info.get('name', '')
        
        # ST股票扣分
        if 'ST' in name or 'st' in name.lower():
            score -= 40
            indicators["st_status"] = True
        else:
            indicators["st_status"] = False
        
        # 退市风险
        if '*ST' in name:
            score -= 20
            indicators["delist_risk"] = True
        else:
            indicators["delist_risk"] = False
        
        score = min(100, max(0, score))
        
        return ProfileDimension(
            name="风险",
            score=round(score, 1),
            level=_score_to_level(score),
            weight=DIMENSION_WEIGHTS["risk"],
            indicators=indicators
        )
    
    def calculate_profile(self, ts_code: str) -> Optional[StockProfile]:
        """计算股票十维画像"""
        try:
            # 获取股票基本信息
            stock_info = self._get_stock_info(ts_code)
            stock_name = stock_info.get('name', ts_code)
            
            # 获取日线数据
            daily_data = self._get_daily_data(ts_code, 60)
            
            # 获取估值数据
            valuation_data = self._get_valuation_data(ts_code, 60)
            
            # 获取市场分布数据（用于百分位计算）
            pe_distribution = self._get_market_pe_distribution()
            pb_distribution = self._get_market_pb_distribution()
            
            # 当前估值数据
            latest_valuation = valuation_data[0] if valuation_data else {}
            pe_ttm = latest_valuation.get('pe_ttm')
            pb = latest_valuation.get('pb')
            
            # 计算各维度评分
            dimensions = []
            
            # 1. 估值维度
            dimensions.append(self.calculate_valuation_score(
                pe_ttm, pb, pe_distribution, pb_distribution
            ))
            
            # 2. 成长维度 (暂用动量代替，需要财务数据)
            growth_dim = ProfileDimension(
                name="成长",
                score=50.0,
                level="中等",
                weight=DIMENSION_WEIGHTS["growth"],
                indicators={"status": "需要财务数据"}
            )
            dimensions.append(growth_dim)
            
            # 3. 盈利维度 (暂用默认值，需要财务数据)
            profit_dim = ProfileDimension(
                name="盈利",
                score=50.0,
                level="中等",
                weight=DIMENSION_WEIGHTS["profitability"],
                indicators={"status": "需要财务数据"}
            )
            dimensions.append(profit_dim)
            
            # 4. 动量维度
            dimensions.append(self.calculate_momentum_score(daily_data))
            
            # 5. 趋势维度
            dimensions.append(self.calculate_trend_score(daily_data))
            
            # 6. 量能维度
            dimensions.append(self.calculate_volume_score(daily_data, valuation_data))
            
            # 7. 波动维度
            dimensions.append(self.calculate_volatility_score(daily_data))
            
            # 8. 资金维度 (需要资金流向数据)
            capital_dim = ProfileDimension(
                name="资金",
                score=50.0,
                level="中等",
                weight=DIMENSION_WEIGHTS["capital_flow"],
                indicators={"status": "需要资金流向数据"}
            )
            dimensions.append(capital_dim)
            
            # 9. 情绪维度 (需要龙虎榜等数据)
            sentiment_dim = ProfileDimension(
                name="情绪",
                score=50.0,
                level="中等",
                weight=DIMENSION_WEIGHTS["sentiment"],
                indicators={"status": "需要情绪数据"}
            )
            dimensions.append(sentiment_dim)
            
            # 10. 风险维度
            dimensions.append(self.calculate_risk_score(ts_code, stock_info))
            
            # 计算加权总分
            total_score = sum(d.score * d.weight for d in dimensions)
            
            # 生成投资建议
            recommendation = self._generate_recommendation(total_score, dimensions)
            
            return StockProfile(
                ts_code=ts_code,
                stock_name=stock_name,
                trade_date=self.get_latest_trade_date() or "",
                total_score=round(total_score, 1),
                dimensions=dimensions,
                recommendation=recommendation,
                raw_data={
                    "daily_data_count": len(daily_data),
                    "valuation_data_count": len(valuation_data),
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to calculate profile for {ts_code}: {e}")
            return None
    
    def _generate_recommendation(self, total_score: float, dimensions: List[ProfileDimension]) -> str:
        """生成投资建议"""
        strengths = [d.name for d in dimensions if d.score >= 70]
        weaknesses = [d.name for d in dimensions if d.score < 40]
        
        if total_score >= 70:
            base = "该股整体表现优秀"
        elif total_score >= 55:
            base = "该股整体表现良好"
        elif total_score >= 40:
            base = "该股整体表现中等"
        else:
            base = "该股整体表现较弱"
        
        parts = [base]
        
        if strengths:
            parts.append(f"，在{'/'.join(strengths[:3])}方面表现突出")
        
        if weaknesses:
            parts.append(f"，需关注{'/'.join(weaknesses[:2])}风险")
        
        parts.append("。投资需谨慎，建议结合基本面深入分析。")
        
        return "".join(parts)
    
    def batch_calculate_profiles(self, ts_codes: List[str]) -> List[StockProfile]:
        """批量计算股票画像"""
        profiles = []
        for ts_code in ts_codes:
            profile = self.calculate_profile(ts_code)
            if profile:
                profiles.append(profile)
        return profiles


# 创建单例
_profile_service = None


def get_profile_service() -> ProfileService:
    """获取 ProfileService 单例"""
    global _profile_service
    if _profile_service is None:
        _profile_service = ProfileService()
    return _profile_service
