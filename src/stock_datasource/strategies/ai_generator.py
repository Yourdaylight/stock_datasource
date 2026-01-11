"""
AI策略生成器

基于大语言模型生成交易策略，包括：
- 自然语言策略描述解析
- 策略代码生成
- 策略验证和优化
- 风险评估
"""

import logging
import re
import ast
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import pandas as pd
import numpy as np

from .base import BaseStrategy, AIGeneratedStrategy, StrategyMetadata, StrategyCategory, RiskLevel, ParameterSchema, TradingSignal
from .registry import strategy_registry

logger = logging.getLogger(__name__)


class StrategyIntent:
    """策略意图解析结果"""
    
    def __init__(self):
        self.strategy_type: str = ""  # 策略类型
        self.indicators: List[str] = []  # 技术指标
        self.conditions: List[str] = []  # 交易条件
        self.parameters: Dict[str, Any] = {}  # 参数设置
        self.risk_level: RiskLevel = RiskLevel.MEDIUM
        self.description: str = ""
        self.confidence: float = 0.0


class StrategyTemplate:
    """策略模板"""
    
    def __init__(self, name: str, code_template: str, parameters: List[ParameterSchema]):
        self.name = name
        self.code_template = code_template
        self.parameters = parameters
        self.usage_count = 0


class LLMAdapter:
    """LLM适配器基类"""
    
    async def generate_strategy_code(self, intent: StrategyIntent, template: StrategyTemplate) -> str:
        """生成策略代码"""
        raise NotImplementedError
    
    async def explain_strategy(self, strategy_code: str) -> str:
        """解释策略逻辑"""
        raise NotImplementedError
    
    async def suggest_improvements(self, backtest_result: Any) -> List[str]:
        """建议改进方案"""
        raise NotImplementedError


class MockLLMAdapter(LLMAdapter):
    """模拟LLM适配器（用于测试）"""
    
    async def generate_strategy_code(self, intent: StrategyIntent, template: StrategyTemplate) -> str:
        """生成策略代码"""
        # 这里应该调用真实的LLM API
        # 暂时返回基于模板的简单代码生成
        
        if "ma" in intent.strategy_type.lower() or "均线" in intent.description:
            return self._generate_ma_strategy_code(intent)
        elif "rsi" in intent.strategy_type.lower() or "RSI" in intent.description:
            return self._generate_rsi_strategy_code(intent)
        else:
            return self._generate_default_strategy_code(intent)
    
    def _generate_ma_strategy_code(self, intent: StrategyIntent) -> str:
        """生成移动平均策略代码"""
        short_period = intent.parameters.get('short_period', 5)
        long_period = intent.parameters.get('long_period', 20)
        
        code = f'''
from typing import List
import pandas as pd
import numpy as np
from datetime import datetime

class GeneratedMAStrategy(AIGeneratedStrategy):
    """AI生成的移动平均策略"""
    
    def _create_metadata(self):
        return StrategyMetadata(
            id="ai_ma_strategy_{{timestamp}}",
            name="AI生成移动平均策略",
            description="{intent.description}",
            category=StrategyCategory.AI_GENERATED,
            risk_level=RiskLevel.{intent.risk_level.name}
        )
    
    def get_parameter_schema(self):
        return [
            ParameterSchema("short_period", "int", {short_period}, 1, 50, "短期均线周期"),
            ParameterSchema("long_period", "int", {long_period}, 2, 100, "长期均线周期")
        ]
    
    def generate_signals(self, data):
        df = data.copy()
        
        short_period = self.params.get('short_period', {short_period})
        long_period = self.params.get('long_period', {long_period})
        
        # 计算移动平均
        df['ma_short'] = df['close'].rolling(short_period).mean()
        df['ma_long'] = df['close'].rolling(long_period).mean()
        
        signals = []
        symbol = df['symbol'].iloc[0] if 'symbol' in df.columns else 'UNKNOWN'
        
        for i in range(1, len(df)):
            if pd.isna(df['ma_short'].iloc[i]) or pd.isna(df['ma_long'].iloc[i]):
                continue
                
            prev_short = df['ma_short'].iloc[i-1]
            prev_long = df['ma_long'].iloc[i-1]
            curr_short = df['ma_short'].iloc[i]
            curr_long = df['ma_long'].iloc[i]
            
            # 金叉买入
            if prev_short <= prev_long and curr_short > curr_long:
                signal = TradingSignal(
                    timestamp=pd.to_datetime(df.iloc[i]['timestamp'] if 'timestamp' in df.columns else datetime.now()),
                    symbol=symbol,
                    action='buy',
                    price=df['close'].iloc[i],
                    confidence=0.8,
                    reason=f"短期均线上穿长期均线"
                )
                signals.append(signal)
            
            # 死叉卖出
            elif prev_short >= prev_long and curr_short < curr_long:
                signal = TradingSignal(
                    timestamp=pd.to_datetime(df.iloc[i]['timestamp'] if 'timestamp' in df.columns else datetime.now()),
                    symbol=symbol,
                    action='sell',
                    price=df['close'].iloc[i],
                    confidence=0.8,
                    reason=f"短期均线下穿长期均线"
                )
                signals.append(signal)
        
        return signals
'''
        return code.strip()
    
    def _generate_rsi_strategy_code(self, intent: StrategyIntent) -> str:
        """生成RSI策略代码"""
        period = intent.parameters.get('period', 14)
        oversold = intent.parameters.get('oversold', 30)
        overbought = intent.parameters.get('overbought', 70)
        
        code = f'''
from typing import List
import pandas as pd
import numpy as np
from datetime import datetime

class GeneratedRSIStrategy(AIGeneratedStrategy):
    """AI生成的RSI策略"""
    
    def _create_metadata(self):
        return StrategyMetadata(
            id="ai_rsi_strategy_{{timestamp}}",
            name="AI生成RSI策略",
            description="{intent.description}",
            category=StrategyCategory.AI_GENERATED,
            risk_level=RiskLevel.{intent.risk_level.name}
        )
    
    def get_parameter_schema(self):
        return [
            ParameterSchema("period", "int", {period}, 5, 50, "RSI计算周期"),
            ParameterSchema("oversold", "float", {oversold}, 10, 40, "超卖阈值"),
            ParameterSchema("overbought", "float", {overbought}, 60, 90, "超买阈值")
        ]
    
    def generate_signals(self, data):
        df = data.copy()
        
        period = self.params.get('period', {period})
        oversold = self.params.get('oversold', {oversold})
        overbought = self.params.get('overbought', {overbought})
        
        # 计算RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.rolling(period).mean()
        avg_loss = loss.rolling(period).mean()
        
        rs = avg_gain / avg_loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        signals = []
        symbol = df['symbol'].iloc[0] if 'symbol' in df.columns else 'UNKNOWN'
        
        for i in range(1, len(df)):
            if pd.isna(df['rsi'].iloc[i]):
                continue
                
            rsi_curr = df['rsi'].iloc[i]
            rsi_prev = df['rsi'].iloc[i-1]
            
            # 超卖买入
            if rsi_prev >= oversold and rsi_curr < oversold:
                signal = TradingSignal(
                    timestamp=pd.to_datetime(df.iloc[i]['timestamp'] if 'timestamp' in df.columns else datetime.now()),
                    symbol=symbol,
                    action='buy',
                    price=df['close'].iloc[i],
                    confidence=0.7,
                    reason=f"RSI超卖信号 (RSI: {{rsi_curr:.2f}})"
                )
                signals.append(signal)
            
            # 超买卖出
            elif rsi_prev <= overbought and rsi_curr > overbought:
                signal = TradingSignal(
                    timestamp=pd.to_datetime(df.iloc[i]['timestamp'] if 'timestamp' in df.columns else datetime.now()),
                    symbol=symbol,
                    action='sell',
                    price=df['close'].iloc[i],
                    confidence=0.7,
                    reason=f"RSI超买信号 (RSI: {{rsi_curr:.2f}})"
                )
                signals.append(signal)
        
        return signals
'''
        return code.strip()
    
    def _generate_default_strategy_code(self, intent: StrategyIntent) -> str:
        """生成默认策略代码"""
        code = f'''
from typing import List
import pandas as pd
import numpy as np
from datetime import datetime

class GeneratedDefaultStrategy(AIGeneratedStrategy):
    """AI生成的默认策略"""
    
    def _create_metadata(self):
        return StrategyMetadata(
            id="ai_default_strategy_{{timestamp}}",
            name="AI生成策略",
            description="{intent.description}",
            category=StrategyCategory.AI_GENERATED,
            risk_level=RiskLevel.{intent.risk_level.name}
        )
    
    def get_parameter_schema(self):
        return [
            ParameterSchema("threshold", "float", 0.02, 0.01, 0.1, "信号阈值")
        ]
    
    def generate_signals(self, data):
        # 简单的价格变化策略
        df = data.copy()
        threshold = self.params.get('threshold', 0.02)
        
        signals = []
        symbol = df['symbol'].iloc[0] if 'symbol' in df.columns else 'UNKNOWN'
        
        for i in range(1, len(df)):
            price_change = (df['close'].iloc[i] - df['close'].iloc[i-1]) / df['close'].iloc[i-1]
            
            if price_change < -threshold:  # 价格下跌超过阈值，买入
                signal = TradingSignal(
                    timestamp=pd.to_datetime(df.iloc[i]['timestamp'] if 'timestamp' in df.columns else datetime.now()),
                    symbol=symbol,
                    action='buy',
                    price=df['close'].iloc[i],
                    confidence=0.6,
                    reason=f"价格下跌{{price_change:.2%}}，逢低买入"
                )
                signals.append(signal)
            
            elif price_change > threshold:  # 价格上涨超过阈值，卖出
                signal = TradingSignal(
                    timestamp=pd.to_datetime(df.iloc[i]['timestamp'] if 'timestamp' in df.columns else datetime.now()),
                    symbol=symbol,
                    action='sell',
                    price=df['close'].iloc[i],
                    confidence=0.6,
                    reason=f"价格上涨{{price_change:.2%}}，获利了结"
                )
                signals.append(signal)
        
        return signals
'''
        return code.strip()
    
    async def explain_strategy(self, strategy_code: str) -> str:
        """解释策略逻辑"""
        # 简单的代码分析
        if "ma_short" in strategy_code and "ma_long" in strategy_code:
            return "这是一个基于移动平均线交叉的趋势跟踪策略。当短期均线上穿长期均线时买入，下穿时卖出。"
        elif "rsi" in strategy_code.lower():
            return "这是一个基于RSI指标的均值回归策略。当RSI指标显示超卖时买入，超买时卖出。"
        else:
            return "这是一个基于价格变化的简单策略。"
    
    async def suggest_improvements(self, backtest_result: Any) -> List[str]:
        """建议改进方案"""
        suggestions = [
            "考虑添加止损机制以控制风险",
            "可以尝试优化参数以提高收益",
            "建议结合其他技术指标进行信号确认",
            "考虑加入市场环境过滤条件"
        ]
        return suggestions


class StrategyKnowledgeBase:
    """策略知识库"""
    
    def __init__(self):
        self.templates = self._initialize_templates()
        self.indicators = self._initialize_indicators()
    
    def _initialize_templates(self) -> Dict[str, StrategyTemplate]:
        """初始化策略模板"""
        templates = {}
        
        # 移动平均模板
        ma_template = StrategyTemplate(
            name="moving_average",
            code_template="ma_template",
            parameters=[
                ParameterSchema("short_period", "int", 5, 1, 50, "短期均线周期"),
                ParameterSchema("long_period", "int", 20, 2, 100, "长期均线周期")
            ]
        )
        templates["ma"] = ma_template
        
        # RSI模板
        rsi_template = StrategyTemplate(
            name="rsi",
            code_template="rsi_template",
            parameters=[
                ParameterSchema("period", "int", 14, 5, 50, "RSI周期"),
                ParameterSchema("oversold", "float", 30, 10, 40, "超卖阈值"),
                ParameterSchema("overbought", "float", 70, 60, 90, "超买阈值")
            ]
        )
        templates["rsi"] = rsi_template
        
        return templates
    
    def _initialize_indicators(self) -> Dict[str, Dict[str, Any]]:
        """初始化技术指标库"""
        indicators = {
            "ma": {"name": "移动平均", "type": "trend", "complexity": "low"},
            "ema": {"name": "指数移动平均", "type": "trend", "complexity": "low"},
            "macd": {"name": "MACD", "type": "momentum", "complexity": "medium"},
            "rsi": {"name": "RSI", "type": "oscillator", "complexity": "medium"},
            "kdj": {"name": "KDJ", "type": "oscillator", "complexity": "medium"},
            "bollinger": {"name": "布林带", "type": "volatility", "complexity": "medium"},
        }
        return indicators
    
    def find_template(self, intent: StrategyIntent) -> Optional[StrategyTemplate]:
        """根据意图查找最匹配的模板"""
        strategy_type = intent.strategy_type.lower()
        
        # 简单的模板匹配逻辑
        if "ma" in strategy_type or "均线" in intent.description:
            return self.templates.get("ma")
        elif "rsi" in strategy_type or "RSI" in intent.description:
            return self.templates.get("rsi")
        
        # 默认返回移动平均模板
        return self.templates.get("ma")


class NLStrategyParser:
    """自然语言策略解析器"""
    
    def __init__(self):
        self.indicator_keywords = {
            "移动平均": ["移动平均", "均线", "MA", "ma"],
            "RSI": ["RSI", "rsi", "相对强弱", "超买超卖"],
            "MACD": ["MACD", "macd", "指数平滑"],
            "KDJ": ["KDJ", "kdj", "随机指标"],
            "布林带": ["布林带", "bollinger", "Bollinger"]
        }
        
        self.action_keywords = {
            "买入": ["买入", "买进", "做多", "开仓", "建仓"],
            "卖出": ["卖出", "卖空", "做空", "平仓", "止损"]
        }
    
    def parse(self, description: str) -> StrategyIntent:
        """解析自然语言描述"""
        intent = StrategyIntent()
        intent.description = description
        
        # 识别技术指标
        intent.indicators = self._extract_indicators(description)
        
        # 识别策略类型
        intent.strategy_type = self._infer_strategy_type(intent.indicators, description)
        
        # 提取参数
        intent.parameters = self._extract_parameters(description)
        
        # 评估风险等级
        intent.risk_level = self._assess_risk_level(description)
        
        # 计算置信度
        intent.confidence = self._calculate_confidence(intent)
        
        return intent
    
    def _extract_indicators(self, description: str) -> List[str]:
        """提取技术指标"""
        indicators = []
        
        for indicator, keywords in self.indicator_keywords.items():
            for keyword in keywords:
                if keyword in description:
                    indicators.append(indicator)
                    break
        
        return indicators
    
    def _infer_strategy_type(self, indicators: List[str], description: str) -> str:
        """推断策略类型"""
        if "移动平均" in indicators:
            return "moving_average"
        elif "RSI" in indicators:
            return "rsi"
        elif "MACD" in indicators:
            return "macd"
        elif "KDJ" in indicators:
            return "kdj"
        elif "布林带" in indicators:
            return "bollinger"
        else:
            # 基于描述推断
            if any(word in description for word in ["趋势", "突破", "均线"]):
                return "trend_following"
            elif any(word in description for word in ["反转", "超买", "超卖"]):
                return "mean_reversion"
            else:
                return "custom"
    
    def _extract_parameters(self, description: str) -> Dict[str, Any]:
        """提取参数"""
        parameters = {}
        
        # 提取数字参数
        numbers = re.findall(r'\d+', description)
        
        if "均线" in description or "MA" in description:
            if len(numbers) >= 2:
                parameters['short_period'] = int(numbers[0])
                parameters['long_period'] = int(numbers[1])
            elif len(numbers) == 1:
                parameters['period'] = int(numbers[0])
        
        elif "RSI" in description:
            if numbers:
                parameters['period'] = int(numbers[0])
            
            # 提取阈值
            if "30" in description or "超卖" in description:
                parameters['oversold'] = 30
            if "70" in description or "超买" in description:
                parameters['overbought'] = 70
        
        return parameters
    
    def _assess_risk_level(self, description: str) -> RiskLevel:
        """评估风险等级"""
        high_risk_keywords = ["激进", "高频", "杠杆", "做空"]
        low_risk_keywords = ["保守", "稳健", "长期", "价值"]
        
        if any(keyword in description for keyword in high_risk_keywords):
            return RiskLevel.HIGH
        elif any(keyword in description for keyword in low_risk_keywords):
            return RiskLevel.LOW
        else:
            return RiskLevel.MEDIUM
    
    def _calculate_confidence(self, intent: StrategyIntent) -> float:
        """计算解析置信度"""
        confidence = 0.5  # 基础置信度
        
        # 有识别到指标加分
        if intent.indicators:
            confidence += 0.2
        
        # 有提取到参数加分
        if intent.parameters:
            confidence += 0.2
        
        # 策略类型明确加分
        if intent.strategy_type != "custom":
            confidence += 0.1
        
        return min(confidence, 1.0)


class AIStrategyGenerator:
    """AI策略生成器"""
    
    def __init__(self, llm_adapter: Optional[LLMAdapter] = None):
        """
        初始化AI策略生成器
        
        Args:
            llm_adapter: LLM适配器实例
        """
        self.llm_adapter = llm_adapter or MockLLMAdapter()
        self.knowledge_base = StrategyKnowledgeBase()
        self.parser = NLStrategyParser()
        
        logger.info("AI strategy generator initialized")
    
    async def generate_from_description(self, 
                                      description: str, 
                                      user_profile: Optional[Dict[str, Any]] = None) -> AIGeneratedStrategy:
        """
        基于自然语言描述生成策略
        
        Args:
            description: 策略描述
            user_profile: 用户配置文件
            
        Returns:
            AI生成的策略实例
        """
        try:
            logger.info(f"Generating strategy from description: {description}")
            
            # 1. 解析用户意图
            intent = self.parser.parse(description)
            
            # 2. 匹配策略模板
            template = self.knowledge_base.find_template(intent)
            
            # 3. 生成策略代码
            strategy_code = await self.llm_adapter.generate_strategy_code(intent, template)
            
            # 4. 验证和创建策略
            strategy = await self._create_strategy_from_code(strategy_code, intent, description)
            
            logger.info(f"Successfully generated strategy: {strategy.metadata.id}")
            return strategy
            
        except Exception as e:
            logger.error(f"Failed to generate strategy: {e}")
            raise
    
    async def _create_strategy_from_code(self, 
                                       code: str, 
                                       intent: StrategyIntent,
                                       original_description: str) -> AIGeneratedStrategy:
        """从代码创建策略实例"""
        
        # 创建策略元数据
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        strategy_id = f"ai_strategy_{timestamp}"
        
        # 创建生成信息
        generation_info = {
            'prompt': original_description,
            'model': 'mock_llm',
            'confidence': intent.confidence,
            'generated_at': datetime.now(),
            'intent': {
                'strategy_type': intent.strategy_type,
                'indicators': intent.indicators,
                'parameters': intent.parameters,
                'risk_level': intent.risk_level.value
            }
        }
        
        # 创建简化的策略实例（不执行动态代码）
        strategy = self._create_simple_strategy(intent, strategy_id, generation_info)
        
        return strategy
    
    def _create_simple_strategy(self, 
                              intent: StrategyIntent, 
                              strategy_id: str,
                              generation_info: Dict[str, Any]) -> AIGeneratedStrategy:
        """创建简化的策略实例"""
        
        class SimpleAIStrategy(AIGeneratedStrategy):
            def __init__(self, intent_data, sid, gen_info):
                self.intent_data = intent_data
                self.strategy_id = sid
                super().__init__(intent_data.parameters, gen_info)
            
            def _create_metadata(self):
                return StrategyMetadata(
                    id=self.strategy_id,
                    name=f"AI生成策略_{self.strategy_id}",
                    description=self.intent_data.description,
                    category=StrategyCategory.AI_GENERATED,
                    risk_level=self.intent_data.risk_level,
                    is_ai_generated=True,
                    generation_prompt=self.intent_data.description,
                    llm_model='mock_llm',
                    confidence_score=self.intent_data.confidence
                )
            
            def get_parameter_schema(self):
                # 根据策略类型返回相应的参数schema
                if self.intent_data.strategy_type == "moving_average":
                    return [
                        ParameterSchema("short_period", "int", 5, 1, 50, "短期均线周期"),
                        ParameterSchema("long_period", "int", 20, 2, 100, "长期均线周期")
                    ]
                elif self.intent_data.strategy_type == "rsi":
                    return [
                        ParameterSchema("period", "int", 14, 5, 50, "RSI周期"),
                        ParameterSchema("oversold", "float", 30, 10, 40, "超卖阈值"),
                        ParameterSchema("overbought", "float", 70, 60, 90, "超买阈值")
                    ]
                else:
                    return [
                        ParameterSchema("threshold", "float", 0.02, 0.01, 0.1, "信号阈值")
                    ]
            
            def generate_signals(self, data):
                # 根据策略类型生成信号
                if self.intent_data.strategy_type == "moving_average":
                    return self._generate_ma_signals(data)
                elif self.intent_data.strategy_type == "rsi":
                    return self._generate_rsi_signals(data)
                else:
                    return self._generate_default_signals(data)
            
            def _generate_ma_signals(self, data):
                """生成移动平均信号"""
                df = data.copy()
                short_period = self.params.get('short_period', 5)
                long_period = self.params.get('long_period', 20)
                
                df['ma_short'] = df['close'].rolling(short_period).mean()
                df['ma_long'] = df['close'].rolling(long_period).mean()
                
                signals = []
                symbol = df['symbol'].iloc[0] if 'symbol' in df.columns else 'UNKNOWN'
                
                for i in range(1, len(df)):
                    if pd.isna(df['ma_short'].iloc[i]) or pd.isna(df['ma_long'].iloc[i]):
                        continue
                    
                    # 金叉买入
                    if (df['ma_short'].iloc[i-1] <= df['ma_long'].iloc[i-1] and 
                        df['ma_short'].iloc[i] > df['ma_long'].iloc[i]):
                        
                        timestamp = pd.to_datetime(df.iloc[i].get('timestamp', datetime.now()))
                        signal = TradingSignal(
                            timestamp=timestamp,
                            symbol=symbol,
                            action='buy',
                            price=df['close'].iloc[i],
                            confidence=0.8,
                            reason="AI策略：短期均线上穿长期均线"
                        )
                        signals.append(signal)
                    
                    # 死叉卖出
                    elif (df['ma_short'].iloc[i-1] >= df['ma_long'].iloc[i-1] and 
                          df['ma_short'].iloc[i] < df['ma_long'].iloc[i]):
                        
                        timestamp = pd.to_datetime(df.iloc[i].get('timestamp', datetime.now()))
                        signal = TradingSignal(
                            timestamp=timestamp,
                            symbol=symbol,
                            action='sell',
                            price=df['close'].iloc[i],
                            confidence=0.8,
                            reason="AI策略：短期均线下穿长期均线"
                        )
                        signals.append(signal)
                
                return signals
            
            def _generate_rsi_signals(self, data):
                """生成RSI信号"""
                df = data.copy()
                period = self.params.get('period', 14)
                oversold = self.params.get('oversold', 30)
                overbought = self.params.get('overbought', 70)
                
                # 计算RSI
                delta = df['close'].diff()
                gain = delta.where(delta > 0, 0)
                loss = -delta.where(delta < 0, 0)
                
                avg_gain = gain.rolling(period).mean()
                avg_loss = loss.rolling(period).mean()
                
                rs = avg_gain / avg_loss
                df['rsi'] = 100 - (100 / (1 + rs))
                
                signals = []
                symbol = df['symbol'].iloc[0] if 'symbol' in df.columns else 'UNKNOWN'
                
                for i in range(1, len(df)):
                    if pd.isna(df['rsi'].iloc[i]):
                        continue
                    
                    rsi_curr = df['rsi'].iloc[i]
                    rsi_prev = df['rsi'].iloc[i-1]
                    
                    # 超卖买入
                    if rsi_prev >= oversold and rsi_curr < oversold:
                        timestamp = pd.to_datetime(df.iloc[i].get('timestamp', datetime.now()))
                        signal = TradingSignal(
                            timestamp=timestamp,
                            symbol=symbol,
                            action='buy',
                            price=df['close'].iloc[i],
                            confidence=0.7,
                            reason=f"AI策略：RSI超卖信号 (RSI: {rsi_curr:.2f})"
                        )
                        signals.append(signal)
                    
                    # 超买卖出
                    elif rsi_prev <= overbought and rsi_curr > overbought:
                        timestamp = pd.to_datetime(df.iloc[i].get('timestamp', datetime.now()))
                        signal = TradingSignal(
                            timestamp=timestamp,
                            symbol=symbol,
                            action='sell',
                            price=df['close'].iloc[i],
                            confidence=0.7,
                            reason=f"AI策略：RSI超买信号 (RSI: {rsi_curr:.2f})"
                        )
                        signals.append(signal)
                
                return signals
            
            def _generate_default_signals(self, data):
                """生成默认信号"""
                df = data.copy()
                threshold = self.params.get('threshold', 0.02)
                
                signals = []
                symbol = df['symbol'].iloc[0] if 'symbol' in df.columns else 'UNKNOWN'
                
                for i in range(1, len(df)):
                    price_change = (df['close'].iloc[i] - df['close'].iloc[i-1]) / df['close'].iloc[i-1]
                    
                    if price_change < -threshold:
                        timestamp = pd.to_datetime(df.iloc[i].get('timestamp', datetime.now()))
                        signal = TradingSignal(
                            timestamp=timestamp,
                            symbol=symbol,
                            action='buy',
                            price=df['close'].iloc[i],
                            confidence=0.6,
                            reason=f"AI策略：价格下跌{price_change:.2%}，逢低买入"
                        )
                        signals.append(signal)
                    
                    elif price_change > threshold:
                        timestamp = pd.to_datetime(df.iloc[i].get('timestamp', datetime.now()))
                        signal = TradingSignal(
                            timestamp=timestamp,
                            symbol=symbol,
                            action='sell',
                            price=df['close'].iloc[i],
                            confidence=0.6,
                            reason=f"AI策略：价格上涨{price_change:.2%}，获利了结"
                        )
                        signals.append(signal)
                
                return signals
        
        return SimpleAIStrategy(intent, strategy_id, generation_info)
    
    async def explain_strategy(self, strategy: AIGeneratedStrategy) -> str:
        """解释AI生成的策略"""
        explanation = await self.llm_adapter.explain_strategy("")
        
        # 添加AI生成信息
        ai_info = f"""
## AI策略说明

**生成提示**: {strategy.metadata.generation_prompt}

**策略逻辑**: {explanation}

**置信度**: {strategy.metadata.confidence_score:.2f}

**风险警告**: 
{chr(10).join(f'- {warning}' for warning in strategy.get_risk_warnings())}
        """.strip()
        
        return ai_info
    
    async def optimize_strategy(self, 
                              strategy: AIGeneratedStrategy,
                              backtest_result: Any) -> AIGeneratedStrategy:
        """优化AI策略"""
        # 获取改进建议
        suggestions = await self.llm_adapter.suggest_improvements(backtest_result)
        
        # 这里应该基于建议重新生成策略
        # 暂时返回原策略
        logger.info(f"Strategy optimization suggestions: {suggestions}")
        
        return strategy