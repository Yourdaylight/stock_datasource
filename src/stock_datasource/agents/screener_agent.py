"""Screener Agent for intelligent stock screening using LangGraph/DeepAgents.

增强功能：
- 自然语言选股条件解析
- 智能推荐
- 条件验证
- Langfuse 可观测性集成
"""

from typing import Dict, Any, List, Callable, Optional
import logging
import json

from .base_agent import LangGraphAgent, AgentConfig
from .tools import screen_stocks, get_market_overview, get_stock_info

logger = logging.getLogger(__name__)


# 条件解析的系统提示词
NL_PARSE_SYSTEM_PROMPT = """你是一个专业的A股选股分析师，负责将用户的自然语言选股需求转换为结构化筛选条件。

## 可用筛选字段
| 字段 | 说明 | 示例值 |
|------|------|--------|
| pe | 市盈率(TTM) | pe < 20 表示低估值 |
| pb | 市净率 | pb < 2 表示低估值 |
| ps | 市销率 | ps < 5 |
| dv_ratio | 股息率(%) | dv_ratio > 3 表示高股息 |
| turnover_rate | 换手率(%) | turnover_rate > 5 表示活跃 |
| volume_ratio | 量比 | volume_ratio > 1.5 表示放量 |
| pct_chg | 涨跌幅(%) | pct_chg > 5 表示强势 |
| close | 收盘价 | close < 10 表示低价股 |
| total_mv | 总市值(万元) | total_mv > 10000000 表示>1000亿 |
| circ_mv | 流通市值(万元) | |
| industry | 行业 | industry = "白酒" |

## 可用操作符
- gt: 大于 (>)
- gte: 大于等于 (>=)
- lt: 小于 (<)
- lte: 小于等于 (<=)
- eq: 等于 (=)
- in: 包含于列表

## 市值换算
- 1亿 = 10000万元
- 100亿 = 1000000万元
- 1000亿 = 10000000万元

## 常见自然语言映射
- "低估值" → pe < 20, pb < 3
- "高股息" → dv_ratio > 3
- "活跃股" → turnover_rate > 5
- "大盘股" → total_mv > 10000000 (1000亿)
- "小盘股" → total_mv < 1000000 (100亿)
- "强势股" → pct_chg > 5
- "科技股" → industry in ["电子", "计算机", "通信"]
- "消费股" → industry in ["白酒", "食品饮料", "家用电器"]
- "金融股" → industry in ["银行", "证券", "保险"]
- "高成长" → 暂不支持（需要财务数据）

## 输出格式
你必须返回一个JSON对象，包含：
1. conditions: 筛选条件数组
2. explanation: 解释你如何理解用户需求

示例输出：
```json
{
  "conditions": [
    {"field": "pe", "operator": "lt", "value": 20},
    {"field": "pb", "operator": "lt", "value": 3}
  ],
  "explanation": "已为您筛选PE<20、PB<3的低估值股票"
}
```

## 注意事项
- 如果无法理解用户需求，返回空conditions并在explanation中说明
- 优先解析数值条件，行业条件作为补充
- 市值条件需要换算为万元单位
"""


class ScreenerAgent(LangGraphAgent):
    """Screener Agent for intelligent stock screening using DeepAgents.
    
    Handles:
    - Condition-based stock filtering
    - Natural language stock screening  
    - Preset strategy application
    - AI recommendations
    """
    
    def __init__(self):
        config = AgentConfig(
            name="ScreenerAgent",
            description="负责智能选股，支持条件筛选、自然语言选股、预设策略等"
        )
        super().__init__(config)
        self._llm_client = None
    
    @property
    def llm_client(self):
        """Lazy load LLM client with Langfuse integration."""
        if self._llm_client is None:
            try:
                from stock_datasource.llm.client import get_llm_client
                self._llm_client = get_llm_client()
            except Exception as e:
                logger.warning(f"Failed to get LLM client: {e}")
        return self._llm_client
    
    def get_tools(self) -> List[Callable]:
        """Return screening tools."""
        return [
            screen_stocks,
            get_market_overview,
            get_stock_info,
        ]
    
    def get_system_prompt(self) -> str:
        """Return system prompt for stock screening."""
        return """你是一个专业的A股选股分析师。

## 可用工具
- screen_stocks: 根据条件筛选股票（PE、PB、市值、行业等）
- get_market_overview: 获取市场整体情况
- get_stock_info: 获取单只股票的详细信息

## 选股条件参数
- min_pe / max_pe: PE范围
- min_pb / max_pb: PB范围
- min_market_cap / max_market_cap: 市值范围（亿元）
- industry: 行业名称（模糊匹配）
- limit: 返回数量

## 预设策略
1. **低估值策略**: PE < 15, PB < 2
2. **高股息策略**: 股息率 > 3%
3. **高成长策略**: 关注营收和利润增速
4. **动量策略**: 近期涨幅较好
5. **大盘蓝筹策略**: 市值 > 500亿

## 工作流程
1. 理解用户的选股需求
2. 转换为具体的筛选条件
3. 调用 screen_stocks 工具
4. 分析筛选结果并给出建议

## 注意事项
- 使用中文回复
- 解释选股逻辑
- 提示投资风险
- 返回的股票需同时包含代码和名称

## 免责声明
选股结果仅供参考，不构成投资建议。
"""
    
    async def parse_nl_conditions(self, query: str) -> Dict[str, Any]:
        """解析自然语言选股条件
        
        Args:
            query: 用户的自然语言查询
            
        Returns:
            包含 conditions 和 explanation 的字典
        """
        if not self.llm_client:
            logger.warning("LLM client not available for NL parsing")
            return {
                "conditions": [],
                "explanation": "LLM服务不可用，无法解析自然语言条件"
            }
        
        try:
            # 使用 LLM 解析条件，带 Langfuse 追踪
            prompt = f"""请将以下用户选股需求转换为结构化筛选条件：

用户需求：{query}

请返回JSON格式的条件。"""

            logger.info(f"Calling LLM to parse query: {query}")
            result = await self.llm_client.generate(
                prompt=prompt,
                system_prompt=NL_PARSE_SYSTEM_PROMPT,
                temperature=0.3,
                max_tokens=1000,
                trace_name="screener_nl_parse",
                trace_metadata={"module": "screener", "action": "nl_parse", "query": query}
            )
            logger.info(f"LLM response (first 500 chars): {result[:500] if result else 'None'}")
            
            # 尝试解析JSON
            try:
                # 提取JSON部分 - 支持 ```json 格式
                json_str = result
                if '```json' in result:
                    start = result.find('```json') + 7
                    end = result.find('```', start)
                    if end > start:
                        json_str = result[start:end].strip()
                elif '```' in result:
                    start = result.find('```') + 3
                    end = result.find('```', start)
                    if end > start:
                        json_str = result[start:end].strip()
                else:
                    # 提取JSON部分
                    json_start = result.find('{')
                    json_end = result.rfind('}') + 1
                    if json_start >= 0 and json_end > json_start:
                        json_str = result[json_start:json_end]
                
                logger.debug(f"Extracted JSON string: {json_str[:300] if json_str else 'None'}")
                parsed = json.loads(json_str)
                conditions = parsed.get("conditions", [])
                explanation = parsed.get("explanation", "")
                logger.info(f"Parsed {len(conditions)} conditions: {conditions}")
                return {
                    "conditions": conditions,
                    "explanation": explanation
                }
            except json.JSONDecodeError as je:
                logger.warning(f"Failed to parse LLM response as JSON: {je}, response: {result[:500]}")
            
            return {
                "conditions": [],
                "explanation": result or "无法解析您的选股条件"
            }
            
        except Exception as e:
            logger.error(f"Failed to parse NL conditions: {e}")
            return {
                "conditions": [],
                "explanation": f"解析失败: {str(e)}"
            }
    
    async def execute(self, query: str, context: Optional[Dict[str, Any]] = None) -> Any:
        """执行选股请求
        
        增强：支持自然语言条件解析并返回结构化数据
        """
        context = context or {}
        
        # 尝试解析自然语言条件
        parsed = await self.parse_nl_conditions(query)
        
        if parsed["conditions"]:
            # 如果成功解析出条件，返回结构化数据
            from .base_agent import AgentResult
            return AgentResult(
                response=parsed["explanation"],
                success=True,
                metadata={"parsed_conditions": parsed}
            )
        
        # 否则使用父类的默认执行流程
        return await super().execute(query, context)


# 单例实例
_screener_agent: Optional[ScreenerAgent] = None


def get_screener_agent() -> ScreenerAgent:
    """获取 ScreenerAgent 单例实例"""
    global _screener_agent
    if _screener_agent is None:
        _screener_agent = ScreenerAgent()
    return _screener_agent
