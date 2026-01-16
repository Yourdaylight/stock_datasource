"""Top List (龙虎榜) intelligent agent."""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, date, timedelta

from .base_agent import LangGraphAgent, AgentConfig, ToolDefinition
from ..services.toplist_service import TopListService
from ..services.toplist_analysis_service import TopListAnalysisService
from ..services.anomaly_detection_service import AnomalyDetectionService

logger = logging.getLogger(__name__)


class TopListAgent(LangGraphAgent):
    """龙虎榜智能分析代理"""
    
    def __init__(self, config: Optional[AgentConfig] = None):
        if config is None:
            config = AgentConfig(
                name="toplist_agent",
                description="龙虎榜数据分析和异动检测专家",
                model="gpt-4",
                temperature=0.3,
                max_tokens=4000
            )
        
        # 定义工具集
        tools = [
            ToolDefinition(
                name="get_top_list_data",
                description="获取指定日期的龙虎榜数据",
                parameters={
                    "trade_date": {
                        "type": "string",
                        "description": "交易日期，格式：YYYY-MM-DD 或 YYYYMMDD"
                    }
                }
            ),
            ToolDefinition(
                name="get_institutional_analysis",
                description="分析机构资金流向和行为模式",
                parameters={
                    "trade_date": {
                        "type": "string", 
                        "description": "交易日期，格式：YYYY-MM-DD 或 YYYYMMDD"
                    }
                }
            ),
            ToolDefinition(
                name="identify_hot_money_targets",
                description="识别游资目标股票",
                parameters={
                    "days": {
                        "type": "integer",
                        "description": "分析天数，默认5天",
                        "default": 5
                    }
                }
            ),
            ToolDefinition(
                name="analyze_stock_concentration",
                description="分析股票的席位集中度",
                parameters={
                    "ts_code": {
                        "type": "string",
                        "description": "股票代码，如000001.SZ"
                    },
                    "days": {
                        "type": "integer", 
                        "description": "分析天数，默认10天",
                        "default": 10
                    }
                }
            ),
            ToolDefinition(
                name="detect_market_anomalies",
                description="检测市场异动和异常交易活动",
                parameters={}
            ),
            ToolDefinition(
                name="get_stock_toplist_history",
                description="获取股票的龙虎榜历史记录",
                parameters={
                    "ts_code": {
                        "type": "string",
                        "description": "股票代码，如000001.SZ"
                    },
                    "days": {
                        "type": "integer",
                        "description": "查询天数，默认30天",
                        "default": 30
                    }
                }
            ),
            ToolDefinition(
                name="analyze_sector_flows",
                description="分析板块资金流向",
                parameters={
                    "trade_date": {
                        "type": "string",
                        "description": "交易日期，格式：YYYY-MM-DD 或 YYYYMMDD"
                    }
                }
            ),
            ToolDefinition(
                name="generate_toplist_report",
                description="生成龙虎榜综合分析报告",
                parameters={
                    "trade_date": {
                        "type": "string",
                        "description": "交易日期，格式：YYYY-MM-DD 或 YYYYMMDD"
                    }
                }
            )
        ]
        
        super().__init__(config, tools)
        
        # 初始化服务
        self.toplist_service = TopListService()
        self.analysis_service = TopListAnalysisService()
        self.anomaly_service = AnomalyDetectionService()
        
        # 设置系统提示
        self.system_prompt = """你是一个专业的龙虎榜数据分析专家，擅长：

1. **龙虎榜数据解读**：
   - 分析上榜股票的基本情况和上榜原因
   - 解读龙虎榜买卖数据和净流入情况
   - 识别异常交易活动和市场信号

2. **机构行为分析**：
   - 追踪机构席位的资金流向
   - 分析机构投资偏好和操作模式
   - 识别机构抱团和分歧股票

3. **游资动向监控**：
   - 识别活跃游资席位和目标股票
   - 分析游资操作特征和炒作路径
   - 预测游资可能的下一步动作

4. **异动检测预警**：
   - 检测成交量、价格、席位集中度异常
   - 识别潜在的市场操纵行为
   - 提供及时的风险预警

5. **投资建议生成**：
   - 基于龙虎榜数据提供投资参考
   - 分析股票的资金面支撑情况
   - 评估短期和中期投资机会

请根据用户的问题，选择合适的工具进行分析，并提供专业、准确的解读和建议。
注意保持客观中立，强调风险提示。"""
    
    async def get_top_list_data(self, trade_date: str) -> Dict[str, Any]:
        """获取龙虎榜数据"""
        try:
            # 获取基础数据
            top_list_data = await self.toplist_service.get_top_list_by_date(trade_date)
            summary = await self.toplist_service.get_top_list_summary(trade_date)
            
            return {
                "success": True,
                "data": {
                    "top_list": top_list_data[:20],  # 返回前20只股票
                    "summary": summary,
                    "total_count": len(top_list_data)
                },
                "message": f"成功获取{trade_date}的龙虎榜数据，共{len(top_list_data)}只股票上榜"
            }
        except Exception as e:
            logger.error(f"Failed to get top list data: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_institutional_analysis(self, trade_date: str) -> Dict[str, Any]:
        """分析机构资金流向"""
        try:
            analysis = await self.analysis_service.analyze_institutional_flow(trade_date)
            
            return {
                "success": True,
                "data": analysis,
                "message": f"成功分析{trade_date}的机构资金流向"
            }
        except Exception as e:
            logger.error(f"Failed to analyze institutional flow: {e}")
            return {"success": False, "error": str(e)}
    
    async def identify_hot_money_targets(self, days: int = 5) -> Dict[str, Any]:
        """识别游资目标股票"""
        try:
            targets = await self.analysis_service.identify_hot_money_targets(days)
            
            return {
                "success": True,
                "data": {
                    "targets": targets,
                    "analysis_period": f"最近{days}天"
                },
                "message": f"识别出{len(targets)}只游资目标股票"
            }
        except Exception as e:
            logger.error(f"Failed to identify hot money targets: {e}")
            return {"success": False, "error": str(e)}
    
    async def analyze_stock_concentration(self, ts_code: str, days: int = 10) -> Dict[str, Any]:
        """分析股票席位集中度"""
        try:
            concentration = await self.analysis_service.calculate_seat_concentration(ts_code, days)
            
            return {
                "success": True,
                "data": concentration,
                "message": f"成功分析{ts_code}的席位集中度"
            }
        except Exception as e:
            logger.error(f"Failed to analyze seat concentration: {e}")
            return {"success": False, "error": str(e)}
    
    async def detect_market_anomalies(self) -> Dict[str, Any]:
        """检测市场异动"""
        try:
            alerts = await self.anomaly_service.generate_anomaly_alerts()
            
            # 按严重程度分类
            anomalies_by_severity = {
                "critical": [],
                "high": [],
                "medium": [],
                "low": []
            }
            
            for alert in alerts:
                severity = alert.severity
                anomalies_by_severity[severity].append({
                    "ts_code": alert.ts_code,
                    "name": alert.name,
                    "trade_date": alert.trade_date,
                    "anomaly_type": alert.anomaly_type,
                    "description": alert.description,
                    "confidence": alert.confidence,
                    "metrics": alert.metrics
                })
            
            return {
                "success": True,
                "data": {
                    "anomalies": anomalies_by_severity,
                    "total_alerts": len(alerts),
                    "critical_count": len(anomalies_by_severity["critical"]),
                    "high_count": len(anomalies_by_severity["high"])
                },
                "message": f"检测到{len(alerts)}个异动预警"
            }
        except Exception as e:
            logger.error(f"Failed to detect anomalies: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_stock_toplist_history(self, ts_code: str, days: int = 30) -> Dict[str, Any]:
        """获取股票龙虎榜历史"""
        try:
            history = await self.toplist_service.get_stock_top_list_history(ts_code, days)
            
            return {
                "success": True,
                "data": {
                    "history": history,
                    "appearance_count": len(history),
                    "analysis_period": f"最近{days}天"
                },
                "message": f"{ts_code}在最近{days}天内共{len(history)}次上榜"
            }
        except Exception as e:
            logger.error(f"Failed to get stock history: {e}")
            return {"success": False, "error": str(e)}
    
    async def analyze_sector_flows(self, trade_date: str) -> Dict[str, Any]:
        """分析板块资金流向"""
        try:
            sector_analysis = await self.analysis_service.analyze_sector_flow(trade_date)
            
            return {
                "success": True,
                "data": sector_analysis,
                "message": f"成功分析{trade_date}的板块资金流向"
            }
        except Exception as e:
            logger.error(f"Failed to analyze sector flows: {e}")
            return {"success": False, "error": str(e)}
    
    async def generate_toplist_report(self, trade_date: str) -> Dict[str, Any]:
        """生成龙虎榜综合分析报告"""
        try:
            # 收集各种分析数据
            top_list_data = await self.get_top_list_data(trade_date)
            institutional_analysis = await self.get_institutional_analysis(trade_date)
            sector_flows = await self.analyze_sector_flows(trade_date)
            hot_money_targets = await self.identify_hot_money_targets(5)
            anomalies = await self.detect_market_anomalies()
            
            # 构建综合报告
            report = {
                "trade_date": trade_date,
                "generated_at": datetime.now().isoformat(),
                "summary": top_list_data.get("data", {}).get("summary", {}),
                "top_stocks": top_list_data.get("data", {}).get("top_list", [])[:10],
                "institutional_flow": institutional_analysis.get("data", {}),
                "sector_analysis": sector_flows.get("data", {}),
                "hot_money_targets": hot_money_targets.get("data", {}).get("targets", [])[:10],
                "market_anomalies": anomalies.get("data", {}),
                "key_insights": self._generate_key_insights(
                    top_list_data, institutional_analysis, sector_flows, anomalies
                )
            }
            
            return {
                "success": True,
                "data": report,
                "message": f"成功生成{trade_date}的龙虎榜综合分析报告"
            }
        except Exception as e:
            logger.error(f"Failed to generate report: {e}")
            return {"success": False, "error": str(e)}
    
    def _generate_key_insights(self, top_list_data: Dict, institutional_analysis: Dict, 
                             sector_flows: Dict, anomalies: Dict) -> List[str]:
        """生成关键洞察"""
        insights = []
        
        try:
            # 市场活跃度洞察
            summary = top_list_data.get("data", {}).get("summary", {})
            total_stocks = summary.get("total_stocks", 0)
            if total_stocks > 50:
                insights.append(f"市场活跃度较高，共{total_stocks}只股票上榜龙虎榜")
            elif total_stocks < 20:
                insights.append(f"市场活跃度较低，仅{total_stocks}只股票上榜")
            
            # 机构行为洞察
            inst_data = institutional_analysis.get("data", {})
            trading_patterns = inst_data.get("trading_patterns", {})
            net_flow = trading_patterns.get("total_net_flow", 0)
            if net_flow > 100000:
                insights.append("机构呈现净买入态势，资金流入明显")
            elif net_flow < -100000:
                insights.append("机构呈现净卖出态势，需关注资金流出风险")
            
            # 异动预警洞察
            anomaly_data = anomalies.get("data", {})
            critical_count = anomaly_data.get("critical_count", 0)
            if critical_count > 0:
                insights.append(f"发现{critical_count}个严重异动预警，需重点关注")
            
            # 板块轮动洞察
            sector_data = sector_flows.get("data", {})
            sector_flows_list = sector_data.get("sector_flows", [])
            if sector_flows_list:
                top_sector = sector_flows_list[0]
                insights.append(f"{top_sector['sector']}板块资金流入最多，可能存在轮动机会")
            
        except Exception as e:
            logger.error(f"Failed to generate insights: {e}")
            insights.append("数据分析过程中出现异常，请检查数据完整性")
        
        return insights if insights else ["暂无特殊市场洞察"]