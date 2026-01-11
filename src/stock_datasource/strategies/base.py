"""
策略基类和核心数据模型

定义了统一的策略接口和元数据结构，支持传统策略和AI生成策略。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional, Union
import pandas as pd
import numpy as np


class StrategyCategory(Enum):
    """策略分类"""
    TREND = "trend"  # 趋势策略
    MEAN_REVERSION = "mean_reversion"  # 均值回归
    MOMENTUM = "momentum"  # 动量策略
    ARBITRAGE = "arbitrage"  # 套利策略
    AI_GENERATED = "ai_generated"  # AI生成策略
    CUSTOM = "custom"  # 自定义策略


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass
class StrategyMetadata:
    """策略元数据"""
    id: str
    name: str
    description: str
    category: StrategyCategory
    author: str = "system"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    version: str = "1.0.0"
    tags: List[str] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.MEDIUM
    
    # AI相关字段
    is_ai_generated: bool = False
    generation_prompt: Optional[str] = None
    llm_model: Optional[str] = None
    confidence_score: Optional[float] = None


@dataclass
class ParameterSchema:
    """参数配置schema"""
    name: str
    type: str  # int, float, str, bool
    default: Any
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    description: str = ""
    required: bool = True


@dataclass
class TradingSignal:
    """交易信号"""
    timestamp: datetime
    symbol: str
    action: str  # buy, sell, hold
    price: float
    quantity: Optional[int] = None
    confidence: float = 1.0
    reason: str = ""


class BaseStrategy(ABC):
    """
    策略基类
    
    所有策略都必须继承此类并实现抽象方法。
    提供统一的策略接口和基础功能。
    """
    
    def __init__(self, params: Dict[str, Any] = None):
        """
        初始化策略
        
        Args:
            params: 策略参数字典
        """
        self.params = params or {}
        self.metadata = self._create_metadata()
        self._validate_parameters()
    
    @abstractmethod
    def _create_metadata(self) -> StrategyMetadata:
        """创建策略元数据"""
        pass
    
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> List[TradingSignal]:
        """
        生成交易信号
        
        Args:
            data: 历史价格数据，包含 open, high, low, close, volume 列
            
        Returns:
            交易信号列表
        """
        pass
    
    @abstractmethod
    def get_parameter_schema(self) -> List[ParameterSchema]:
        """获取参数配置schema"""
        pass
    
    def _validate_parameters(self) -> bool:
        """验证参数有效性"""
        schema = self.get_parameter_schema()
        
        for param_def in schema:
            param_name = param_def.name
            
            # 检查必需参数
            if param_def.required and param_name not in self.params:
                if param_def.default is not None:
                    self.params[param_name] = param_def.default
                else:
                    raise ValueError(f"Missing required parameter: {param_name}")
            
            # 类型检查
            if param_name in self.params:
                value = self.params[param_name]
                expected_type = self._get_python_type(param_def.type)
                
                if not isinstance(value, expected_type):
                    try:
                        self.params[param_name] = expected_type(value)
                    except (ValueError, TypeError):
                        raise ValueError(f"Parameter {param_name} must be of type {param_def.type}")
                
                # 范围检查
                if param_def.min_value is not None and value < param_def.min_value:
                    raise ValueError(f"Parameter {param_name} must be >= {param_def.min_value}")
                if param_def.max_value is not None and value > param_def.max_value:
                    raise ValueError(f"Parameter {param_name} must be <= {param_def.max_value}")
        
        return True
    
    def _get_python_type(self, type_str: str):
        """将字符串类型转换为Python类型"""
        type_mapping = {
            'int': int,
            'float': float,
            'str': str,
            'bool': bool
        }
        return type_mapping.get(type_str, str)
    
    def explain_logic(self) -> str:
        """解释策略逻辑"""
        return f"""
## {self.metadata.name}

**描述**: {self.metadata.description}

**分类**: {self.metadata.category.value}

**风险等级**: {self.metadata.risk_level.value}

**参数配置**:
{self._format_parameters()}

**策略逻辑**: 
{self._explain_strategy_logic()}
        """.strip()
    
    def _format_parameters(self) -> str:
        """格式化参数显示"""
        lines = []
        for name, value in self.params.items():
            lines.append(f"- {name}: {value}")
        return "\n".join(lines) if lines else "无参数"
    
    def _explain_strategy_logic(self) -> str:
        """子类可重写此方法提供详细的策略逻辑说明"""
        return "策略逻辑说明待完善"
    
    def get_parameter_space(self) -> Dict[str, Dict[str, Any]]:
        """
        获取参数优化空间
        
        Returns:
            参数空间定义，用于策略优化
        """
        space = {}
        schema = self.get_parameter_schema()
        
        for param_def in schema:
            if param_def.type in ['int', 'float']:
                space[param_def.name] = {
                    'type': param_def.type,
                    'min': param_def.min_value or 1,
                    'max': param_def.max_value or 100,
                    'default': param_def.default
                }
        
        return space
    
    def create_optimized_version(self, optimal_params: Dict[str, Any]) -> 'BaseStrategy':
        """
        创建优化版本的策略
        
        Args:
            optimal_params: 优化后的参数
            
        Returns:
            新的策略实例
        """
        # 合并优化参数
        new_params = {**self.params, **optimal_params}
        
        # 创建新实例
        strategy_class = self.__class__
        return strategy_class(new_params)
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        计算技术指标
        
        Args:
            data: 价格数据
            
        Returns:
            包含指标的数据框
        """
        # 子类可重写此方法添加特定指标计算
        return data.copy()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'metadata': {
                'id': self.metadata.id,
                'name': self.metadata.name,
                'description': self.metadata.description,
                'category': self.metadata.category.value,
                'author': self.metadata.author,
                'created_at': self.metadata.created_at.isoformat(),
                'version': self.metadata.version,
                'tags': self.metadata.tags,
                'risk_level': self.metadata.risk_level.value,
                'is_ai_generated': self.metadata.is_ai_generated
            },
            'parameters': self.params,
            'parameter_schema': [
                {
                    'name': p.name,
                    'type': p.type,
                    'default': p.default,
                    'min_value': p.min_value,
                    'max_value': p.max_value,
                    'description': p.description,
                    'required': p.required
                }
                for p in self.get_parameter_schema()
            ]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseStrategy':
        """从字典创建策略实例"""
        params = data.get('parameters', {})
        return cls(params)


class AIGeneratedStrategy(BaseStrategy):
    """AI生成的策略"""
    
    def __init__(self, params: Dict[str, Any] = None, 
                 generation_info: Dict[str, Any] = None):
        """
        初始化AI生成策略
        
        Args:
            params: 策略参数
            generation_info: AI生成信息
        """
        self.generation_info = generation_info or {}
        super().__init__(params)
        
        # 更新元数据
        self.metadata.is_ai_generated = True
        self.metadata.generation_prompt = self.generation_info.get('prompt')
        self.metadata.llm_model = self.generation_info.get('model')
        self.metadata.confidence_score = self.generation_info.get('confidence')
        self.metadata.category = StrategyCategory.AI_GENERATED
    
    def get_risk_warnings(self) -> List[str]:
        """获取AI策略的风险警告"""
        warnings = [
            "这是AI生成的策略，请谨慎使用",
            "建议在小资金上测试后再大规模使用",
            "AI策略可能存在逻辑缺陷，请仔细验证",
            "历史回测表现不代表未来收益"
        ]
        
        if self.metadata.confidence_score and self.metadata.confidence_score < 0.7:
            warnings.append("该策略的AI生成置信度较低，风险较高")
        
        return warnings
    
    def explain_generation_process(self) -> str:
        """解释AI生成过程"""
        return f"""
## AI策略生成信息

**生成提示**: {self.metadata.generation_prompt or '未记录'}

**使用模型**: {self.metadata.llm_model or '未知'}

**置信度**: {self.metadata.confidence_score or 'N/A'}

**生成时间**: {self.metadata.created_at.strftime('%Y-%m-%d %H:%M:%S')}

**风险警告**:
{chr(10).join(f'- {warning}' for warning in self.get_risk_warnings())}
        """.strip()