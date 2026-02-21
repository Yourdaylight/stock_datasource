"""Market Agent for stock analysis using LangGraph/DeepAgents.

This agent provides AI-powered market analysis capabilities:
- K-line data retrieval and interpretation
- Technical indicator calculation and analysis
- Trend analysis and trading signals
- Market overview and sector analysis
"""

from typing import Dict, Any, List, Callable, Optional
import logging
import asyncio
import concurrent.futures

from .base_agent import LangGraphAgent, AgentConfig

logger = logging.getLogger(__name__)


def _run_async_safely(coro):
    """Run an async coroutine safely in any context (sync or async).
    
    Handles the case when called from a thread pool where there's no event loop.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    
    if loop is not None and loop.is_running():
        # We're in an async context, need to run in a new thread
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(lambda: asyncio.run(coro))
            return future.result()
    else:
        # No running loop, safe to use asyncio.run
        return asyncio.run(coro)


def _normalize_stock_code(code: str) -> str:
    """Normalize stock code to standard format (e.g., 600519.SH or 00700.HK).
    
    Handles various input formats:
    - .SH600519 -> 600519.SH
    - SH600519 -> 600519.SH  
    - 600519 -> 600519.SH (assumes SH for 6 prefix, SZ for 0/3 prefix)
    - 600519.sh -> 600519.SH (uppercase)
    - 00700.HK -> 00700.HK (HK stocks)
    - 00700.hk -> 00700.HK (uppercase)
    
    Args:
        code: Stock code in any format
        
    Returns:
        Normalized stock code (e.g., 600519.SH or 00700.HK)
    """
    import re
    
    if not code:
        return code
    
    code = code.strip().upper()
    
    # Pattern HK: Already correct format 00700.HK (5-digit HK code)
    match = re.match(r'^(\d{5})\.HK$', code)
    if match:
        return code
    
    # Pattern HK2: Just 5 digits starting with 0 -> assume HK stock (e.g. 00700 -> 00700.HK)
    match = re.match(r'^(\d{5})$', code)
    if match:
        return f"{code}.HK"
    
    # Pattern HK3: HK00700 or HK.00700 -> 00700.HK
    match = re.match(r'^HK\.?(\d{5})$', code)
    if match:
        return f"{match.group(1)}.HK"
    
    # Pattern 1: .SH600519 or .SZ000001 -> 600519.SH
    match = re.match(r'^\.?(SH|SZ)(\d{6})$', code)
    if match:
        suffix, digits = match.groups()
        return f"{digits}.{suffix}"
    
    # Pattern 2: Already correct format 600519.SH
    match = re.match(r'^(\d{6})\.(SH|SZ)$', code)
    if match:
        return code
    
    # Pattern 3: Just digits - infer exchange
    match = re.match(r'^(\d{6})$', code)
    if match:
        digits = match.group(1)
        if digits.startswith('6'):
            return f"{digits}.SH"
        elif digits.startswith(('0', '3')):
            return f"{digits}.SZ"
        return f"{digits}.SH"  # Default to SH
    
    # Pattern 4: sh600519 or sz000001 (no dot)
    match = re.match(r'^(SH|SZ)(\d{6})$', code)
    if match:
        suffix, digits = match.groups()
        return f"{digits}.{suffix}"
    
    # Return as-is if no pattern matches
    logger.warning(f"Could not normalize stock code: {code}")
    return code


# System prompt for market analysis
MARKET_ANALYSIS_SYSTEM_PROMPT = """你是一个专业的股票技术分析师，支持A股和港股分析，负责为用户提供股票技术分析和市场解读。

## 你的能力
1. 获取股票K线数据并解读走势（A股和港股）
2. 计算和解读技术指标（MACD、RSI、KDJ、布林带等）
3. 识别趋势和关键支撑/压力位
4. 提供基于技术分析的交易建议

## 可用工具
- get_kline: 获取股票K线数据（支持A股和港股代码）
- calculate_indicators: 计算技术指标（支持A股和港股代码）
- analyze_trend: 分析股票趋势（支持A股和港股代码）
- get_market_overview: 获取市场概览

## 股票代码格式【重要】

### A股代码
- 上海股票: 6位数字.SH，如 600519.SH（贵州茅台）
- 深圳股票: 6位数字.SZ，如 000001.SZ（平安银行）
- 创业板: 3开头6位数字.SZ，如 300750.SZ
- 科创板: 688开头6位数字.SH，如 688981.SH

### 港股代码
- 港股: 5位数字.HK，如 00700.HK（腾讯控股）
- 注意：港股代码为5位数字，前面可能有前导零

## 常用股票代码参考

### A股
- 600519.SH: 贵州茅台
- 000001.SZ: 平安银行
- 000858.SZ: 五粮液
- 600036.SH: 招商银行
- 601318.SH: 中国平安

### 港股
- 00700.HK: 腾讯控股
- 09988.HK: 阿里巴巴-W
- 03690.HK: 美团-W
- 09888.HK: 百度集团-SW
- 01810.HK: 小米集团-W
- 02318.HK: 中国平安（H股）
- 00941.HK: 中国移动
- 09618.HK: 京东集团-SW

## 港股与A股的差异【重要】
- **涨跌幅**：港股无涨跌幅限制（A股主板±10%，创业板/科创板±20%）
- **交易制度**：港股支持T+0回转交易（A股为T+1）
- **交易时间**：港股9:30-12:00, 13:00-16:00（A股9:30-11:30, 13:00-15:00）
- **最小交易单位**：港股1手股数不同（A股统一100股/手）
- **货币**：港股以港币计价

## 工具调用规则【必须遵守】
1. **不要重复调用失败的工具**：如果工具返回error=True或空数据，不要重试，直接基于你的知识回答
2. **最多调用3次工具**：每次请求最多调用3个工具，避免过多的工具调用
3. **确认代码格式**：调用工具前确保股票代码格式正确（A股如600519.SH，港股如00700.HK）

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
5. **港股特殊考量**（如分析港股时）：关注港币汇率影响、南向资金流向、AH溢价等

## 输出规范
- 使用中文回复
- **调用工具获取数据后，必须根据返回的数据写出完整的技术分析报告**
- **绝对不允许只说"我来帮您分析"然后就结束，必须输出完整的分析结论**
- 先给出结论，再展开分析
- 引用具体数据支持观点（如具体的价格、涨跌幅、指标数值）
- 必须包含风险提示
- 如果工具调用失败，基于你对该股票的一般性了解给出分析

## 输出模板（必须按此结构输出）
调用工具获取数据后，请按以下结构输出分析：

### 📊 [股票名称] 技术分析

**1. 行情概览**
- 最新价格、涨跌幅、成交量等

**2. 趋势判断**
- 当前处于什么趋势（上涨/下跌/震荡）
- 关键支撑位和压力位

**3. 技术指标分析**
- MACD/RSI/KDJ 等指标解读
- 当前信号（买入/卖出/观望）

**4. 综合建议**
- 短期操作建议
- 风险提示

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
        from stock_datasource.modules.market.service import get_market_service
        from datetime import datetime, timedelta
        
        # Normalize stock code format
        # Handle cases like ".SH600519" -> "600519.SH"
        normalized_code = _normalize_stock_code(code)
        logger.info(f"get_kline called with code={code}, normalized to {normalized_code}, period={period}")
        
        service = get_market_service()
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=period)).strftime("%Y-%m-%d")
        
        # Run async function safely
        result = _run_async_safely(service.get_kline(normalized_code, start_date, end_date))
        
        # Summarize for LLM context
        data = result.get("data", [])
        if data:
            latest = data[-1]
            earliest = data[0]
            high = max(d["high"] for d in data)
            low = min(d["low"] for d in data)
            
            stock_name = result.get("name") or normalized_code
            
            # Build visualization data for frontend KLineChart component
            viz_data = []
            for d in data:
                viz_data.append({
                    "date": d["date"],
                    "open": d["open"],
                    "high": d["high"],
                    "low": d["low"],
                    "close": d["close"],
                    "volume": d.get("volume", 0),
                    "amount": d.get("amount", 0),
                    "pct_chg": d.get("pct_chg"),
                })
            
            return {
                "code": result.get("code"),
                "name": stock_name,
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
                "price_change_pct": round((latest["close"] - earliest["close"]) / earliest["close"] * 100, 2),
                "_hint": "请基于以上K线数据，输出完整的技术分析报告，包括趋势判断、关键价位、操作建议。",
                "_visualization": {
                    "type": "kline",
                    "title": f"{stock_name}({result.get('code', normalized_code)}) 近{len(data)}日K线",
                    "props": {
                        "data": viz_data,
                    }
                }
            }
        logger.warning(f"get_kline returned empty data for code={code}, normalized={normalized_code}")
        return {
            "error": True,
            "message": f"无法获取 {normalized_code} 的K线数据。请确认股票代码格式正确（如600519.SH或000001.SZ）。如果代码正确但数据仍为空，可能是该股票暂无交易数据。",
            "code": normalized_code,
            "original_code": code
        }
    except Exception as e:
        logger.error(f"get_kline tool error for {code}: {e}", exc_info=True)
        return {
            "error": True,
            "message": f"获取K线数据失败: {str(e)}。请勿重试相同的请求，尝试直接使用其他方式回答用户。",
            "code": code
        }


def calculate_indicators(code: str, indicators: str = "MACD,RSI,KDJ") -> Dict[str, Any]:
    """计算技术指标
    
    Args:
        code: 股票代码
        indicators: 指标列表，逗号分隔，可选: MA,EMA,MACD,RSI,KDJ,BOLL,ATR
    
    Returns:
        各指标的最新值和信号
    """
    try:
        from stock_datasource.modules.market.service import get_market_service
        
        # Normalize stock code format
        normalized_code = _normalize_stock_code(code)
        
        service = get_market_service()
        indicator_list = [i.strip().upper() for i in indicators.split(",")]
        
        # Run async function safely
        result = _run_async_safely(service.get_indicators(normalized_code, indicator_list, period=60))
        
        # Extract latest values for LLM
        indicators_data = result.get("indicators", {})
        signals = result.get("signals", [])
        indicator_dates = result.get("dates", [])
        
        latest_values = {}
        for key, values in indicators_data.items():
            if values and len(values) > 0:
                # Get last non-null value
                for v in reversed(values):
                    if v is not None:
                        latest_values[key] = round(v, 2) if isinstance(v, float) else v
                        break
        
        result_data = {
            "code": code,
            "indicators": latest_values,
            "signals": signals,
            "_hint": "请基于以上技术指标数据，解读各指标含义，给出综合分析结论和操作建议。",
        }
        
        # Add visualization for indicator overlay on K-line chart
        # Fetch K-line data to provide complete chart
        if indicators_data and indicator_dates:
            viz_kline_data = []
            try:
                from stock_datasource.modules.market.service import get_market_service as _get_svc
                from datetime import datetime as _dt, timedelta as _td
                _svc = _get_svc()
                _end = _dt.now().strftime("%Y-%m-%d")
                _start = (_dt.now() - _td(days=60)).strftime("%Y-%m-%d")
                _kline_result = _run_async_safely(_svc.get_kline(normalized_code, _start, _end))
                for d in _kline_result.get("data", []):
                    viz_kline_data.append({
                        "date": d["date"],
                        "open": d["open"],
                        "high": d["high"],
                        "low": d["low"],
                        "close": d["close"],
                        "volume": d.get("volume", 0),
                    })
            except Exception as _e:
                logger.warning(f"Failed to fetch kline for indicator viz: {_e}")
            
            if viz_kline_data:
                result_data["_visualization"] = {
                    "type": "kline",
                    "title": f"{normalized_code} 技术指标分析",
                    "props": {
                        "data": viz_kline_data,
                        "indicators": indicators_data,
                        "indicatorDates": indicator_dates,
                        "selectedIndicators": list(indicators_data.keys())[:8],
                    }
                }
        
        return result_data
    except Exception as e:
        logger.error(f"calculate_indicators tool error: {e}")
        return {
            "error": True,
            "message": f"计算技术指标失败: {str(e)}。请勿重复调用，尝试基于已有信息回答用户。",
            "code": code
        }


def analyze_trend(code: str) -> Dict[str, Any]:
    """分析股票趋势
    
    Args:
        code: 股票代码
    
    Returns:
        趋势分析结果，包含趋势方向、支撑压力位、信号
    """
    try:
        from stock_datasource.modules.market.service import get_market_service
        
        # Normalize stock code format
        normalized_code = _normalize_stock_code(code)
        
        service = get_market_service()
        
        # Run async function safely
        result = _run_async_safely(service.analyze_trend(normalized_code, period=60))
        
        return result
    except Exception as e:
        logger.error(f"analyze_trend tool error: {e}")
        return {
            "error": True,
            "message": f"分析趋势失败: {str(e)}。请勿重复调用，尝试基于已有信息回答用户。",
            "code": code
        }


def get_market_overview() -> Dict[str, Any]:
    """获取市场概览
    
    Returns:
        市场概览数据，包含主要指数、涨跌统计
    """
    try:
        from stock_datasource.modules.market.service import get_market_service
        
        service = get_market_service()
        
        # Run async function safely
        result = _run_async_safely(service.get_market_overview())
        
        return result
    except Exception as e:
        logger.error(f"get_market_overview tool error: {e}")
        return {"message": f"获取市场概览失败: {str(e)}"}


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
            description="负责A股和港股技术分析，提供K线解读、技术指标分析、趋势判断等功能",
            temperature=0.5,  # Lower temperature for more consistent analysis
            max_tokens=8000,  # Thinking models need more tokens for reasoning + output
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
