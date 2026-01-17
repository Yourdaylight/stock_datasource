"""Market Agent for stock analysis using LangGraph/DeepAgents.

This agent provides AI-powered market analysis capabilities:
- K-line data retrieval and interpretation
- Technical indicator calculation and analysis
- Trend analysis and trading signals
- Market overview and sector analysis
"""

from typing import Dict, Any, List, Callable, Optional
import logging

from .base_agent import LangGraphAgent, AgentConfig

logger = logging.getLogger(__name__)


# System prompt for market analysis
MARKET_ANALYSIS_SYSTEM_PROMPT = """你是一个专业的A股技术分析师，负责为用户提供股票技术分析和市场解读。

## 你的能力
1. 获取股票K线数据并解读走势
2. 计算和解读技术指标（MACD、RSI、KDJ、布林带等）
3. 识别趋势和关键支撑/压力位
4. 提供基于技术分析的交易建议

## 可用工具
- get_kline: 获取股票K线数据
- calculate_indicators: 计算技术指标
- analyze_trend: 分析股票趋势
- get_market_overview: 获取市场概览

## 技术指标说明
| 指标 | 用途 | 关键信号 |
|------|------|----------|
| MACD | 趋势跟踪 | 金叉买入、死叉卖出 |
| RSI | 超买超卖 | >70超买、<30超卖 |
| KDJ | 短期超买超卖 | K/D金叉、J>100超买、J<0超卖 |
| BOLL | 波动区间 | 突破上轨回调、突破下轨反弹 |
| MA | 趋势方向 | 短期均线上穿长期均线看多 |

## 分析框架
1. **趋势分析**：判断当前处于上涨、下跌还是震荡趋势
2. **关键位置**：识别支撑位和压力位
3. **技术信号**：列出当前的技术指标信号
4. **综合建议**：结合多个指标给出操作建议

## 输出规范
- 使用中文回复
- 先给出结论，再展开分析
- 引用具体数据支持观点
- 必须包含风险提示

## 风险提示
每次分析结束时，必须加上：
"以上分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。"
"""


# Tool functions for MarketAgent
def get_kline(code: str, period: int = 60) -> Dict[str, Any]:
    """获取股票K线数据
    
    Args:
        code: 股票代码，如 000001.SZ、600519.SH
        period: 获取天数，默认60天
    
    Returns:
        K线数据，包含日期、开高低收、成交量
    """
    try:
        import asyncio
        from stock_datasource.modules.market.service import get_market_service
        from datetime import datetime, timedelta
        
        service = get_market_service()
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=period)).strftime("%Y-%m-%d")
        
        # Run async function in sync context
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    service.get_kline(code, start_date, end_date)
                )
                result = future.result()
        else:
            result = asyncio.run(service.get_kline(code, start_date, end_date))
        
        # Summarize for LLM context
        data = result.get("data", [])
        if data:
            latest = data[-1]
            earliest = data[0]
            high = max(d["high"] for d in data)
            low = min(d["low"] for d in data)
            
            return {
                "code": result.get("code"),
                "name": result.get("name"),
                "period_days": len(data),
                "latest": {
                    "date": latest["date"],
                    "open": latest["open"],
                    "high": latest["high"],
                    "low": latest["low"],
                    "close": latest["close"],
                    "volume": latest["volume"]
                },
                "period_high": high,
                "period_low": low,
                "price_change": round(latest["close"] - earliest["close"], 2),
                "price_change_pct": round((latest["close"] - earliest["close"]) / earliest["close"] * 100, 2)
            }
        return {"error": "No data available"}
    except Exception as e:
        logger.error(f"get_kline tool error: {e}")
        return {"error": str(e)}


def calculate_indicators(code: str, indicators: str = "MACD,RSI,KDJ") -> Dict[str, Any]:
    """计算技术指标
    
    Args:
        code: 股票代码
        indicators: 指标列表，逗号分隔，可选: MA,EMA,MACD,RSI,KDJ,BOLL,ATR
    
    Returns:
        各指标的最新值和信号
    """
    try:
        import asyncio
        from stock_datasource.modules.market.service import get_market_service
        
        service = get_market_service()
        indicator_list = [i.strip().upper() for i in indicators.split(",")]
        
        # Run async function
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    service.get_indicators(code, indicator_list, period=60)
                )
                result = future.result()
        else:
            result = asyncio.run(service.get_indicators(code, indicator_list, period=60))
        
        # Extract latest values for LLM
        indicators_data = result.get("indicators", {})
        signals = result.get("signals", [])
        
        latest_values = {}
        for key, values in indicators_data.items():
            if values and len(values) > 0:
                # Get last non-null value
                for v in reversed(values):
                    if v is not None:
                        latest_values[key] = round(v, 2) if isinstance(v, float) else v
                        break
        
        return {
            "code": code,
            "indicators": latest_values,
            "signals": signals
        }
    except Exception as e:
        logger.error(f"calculate_indicators tool error: {e}")
        return {"error": str(e)}


def analyze_trend(code: str) -> Dict[str, Any]:
    """分析股票趋势
    
    Args:
        code: 股票代码
    
    Returns:
        趋势分析结果，包含趋势方向、支撑压力位、信号
    """
    try:
        import asyncio
        from stock_datasource.modules.market.service import get_market_service
        
        service = get_market_service()
        
        # Run async function
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    service.analyze_trend(code, period=60)
                )
                result = future.result()
        else:
            result = asyncio.run(service.analyze_trend(code, period=60))
        
        return result
    except Exception as e:
        logger.error(f"analyze_trend tool error: {e}")
        return {"error": str(e)}


def get_market_overview() -> Dict[str, Any]:
    """获取市场概览
    
    Returns:
        市场概览数据，包含主要指数、涨跌统计
    """
    try:
        import asyncio
        from stock_datasource.modules.market.service import get_market_service
        
        service = get_market_service()
        
        # Run async function
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    service.get_market_overview()
                )
                result = future.result()
        else:
            result = asyncio.run(service.get_market_overview())
        
        return result
    except Exception as e:
        logger.error(f"get_market_overview tool error: {e}")
        return {"error": str(e)}


class MarketAgent(LangGraphAgent):
    """Market Agent for AI-powered stock technical analysis.
    
    Inherits from LangGraphAgent and provides:
    - K-line data retrieval and analysis
    - Technical indicator calculation
    - Trend analysis with trading signals
    - Market overview
    """
    
    def __init__(self):
        config = AgentConfig(
            name="MarketAgent",
            description="负责股票技术分析，提供K线解读、技术指标分析、趋势判断等功能",
            temperature=0.5,  # Lower temperature for more consistent analysis
            max_tokens=2000,
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
        """Return market analysis tools."""
        return [
            get_kline,
            calculate_indicators,
            analyze_trend,
            get_market_overview,
        ]
    
    def get_system_prompt(self) -> str:
        """Return system prompt for market analysis."""
        return MARKET_ANALYSIS_SYSTEM_PROMPT


# Singleton instance
_market_agent: Optional[MarketAgent] = None


def get_market_agent() -> MarketAgent:
    """Get MarketAgent singleton instance."""
    global _market_agent
    if _market_agent is None:
        _market_agent = MarketAgent()
    return _market_agent
