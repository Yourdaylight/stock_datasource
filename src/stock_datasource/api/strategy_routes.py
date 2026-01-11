"""
策略相关的API路由
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from ..strategies.registry import StrategyRegistry
from ..strategies.init import get_strategy_registry
# 延迟导入避免依赖问题
# from ..strategies.ai_generator import AIStrategyGenerator
# from ..strategies.optimizer import StrategyOptimizer
# from ..backtest.engine import IntelligentBacktestEngine
# from ..backtest.models import BacktestConfig, BacktestResult

"""
策略相关的API路由
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from ..strategies.registry import StrategyRegistry
from ..strategies.init import get_strategy_registry

router = APIRouter(prefix="/api/strategies", tags=["strategies"])

# 请求/响应模型
class StrategyResponse(BaseModel):
    id: str
    name: str
    description: str
    category: str
    author: str
    version: str
    tags: List[str]
    risk_level: str
    created_at: str
    updated_at: str
    usage_count: int
    is_ai_generated: bool
    parameter_schema: List[Dict[str, Any]]

class StrategyListResponse(BaseModel):
    strategies: List[StrategyResponse]

class AIStrategyRequest(BaseModel):
    description: str
    market_type: str = "stock"
    risk_level: str = "medium"
    time_frame: str = "daily"

class BacktestRequest(BaseModel):
    strategy_id: str
    symbol: str
    start_date: str
    end_date: str
    initial_capital: float = 100000.0
    parameters: Dict[str, Any] = {}

@router.get("/", response_model=StrategyListResponse)
async def get_strategies():
    """获取所有可用策略列表"""
    try:
        registry = get_strategy_registry()
        strategies = []
        
        for strategy_id, strategy_info in registry._strategies.items():
            metadata = strategy_info.metadata
            
            strategies.append(StrategyResponse(
                id=metadata.id,
                name=metadata.name,
                description=metadata.description,
                category=metadata.category.value,
                author=metadata.author,
                version=metadata.version,
                tags=metadata.tags,
                risk_level=metadata.risk_level.value,
                created_at=metadata.created_at.isoformat() if metadata.created_at else "",
                updated_at=metadata.updated_at.isoformat() if metadata.updated_at else "",
                usage_count=getattr(metadata, 'usage_count', 0),  # 使用默认值
                is_ai_generated=metadata.is_ai_generated,
                parameter_schema=[
                    {
                        "name": param.name,
                        "type": param.type,
                        "default": param.default,
                        "min_value": param.min_value,
                        "max_value": param.max_value,
                        "description": param.description,
                        "required": param.required
                    }
                    for param in registry.get_strategy_class(strategy_id)().get_parameter_schema()
                ]
            ))
        
        return StrategyListResponse(strategies=strategies)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/category-stats")
async def get_category_stats():
    """获取策略分类统计"""
    try:
        registry = get_strategy_registry()
        stats = {}
        
        for strategy_id, strategy_info in registry._strategies.items():
            category = strategy_info.metadata.category.value
            stats[category] = stats.get(category, 0) + 1
        
        return {"data": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{strategy_id}/explain")
async def explain_strategy(strategy_id: str):
    """获取策略解释"""
    try:
        registry = get_strategy_registry()
        strategy_class = registry.get_strategy_class(strategy_id)
        
        if not strategy_class:
            raise HTTPException(status_code=404, detail=f"策略 {strategy_id} 不存在")
        
        strategy = strategy_class()
        explanation = strategy._explain_strategy_logic()
        
        return {"data": {"explanation": explanation}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{strategy_id}")
async def get_strategy(strategy_id: str):
    """获取单个策略详情"""
    try:
        registry = get_strategy_registry()
        strategy_class = registry.get_strategy_class(strategy_id)
        
        if not strategy_class:
            raise HTTPException(status_code=404, detail=f"策略 {strategy_id} 不存在")
        
        strategy_info = registry._strategies[strategy_id]
        metadata = strategy_info.metadata
        
        return {
            "id": metadata.id,
            "name": metadata.name,
            "description": metadata.description,
            "category": metadata.category.value,
            "author": metadata.author,
            "version": metadata.version,
            "tags": metadata.tags,
            "risk_level": metadata.risk_level.value,
            "created_at": metadata.created_at.isoformat() if metadata.created_at else "",
            "updated_at": metadata.updated_at.isoformat() if metadata.updated_at else "",
            "usage_count": getattr(metadata, 'usage_count', 0),  # 使用默认值
            "is_ai_generated": metadata.is_ai_generated,
            "parameter_schema": [
                {
                    "name": param.name,
                    "type": param.type,
                    "default": param.default,
                    "min_value": param.min_value,
                    "max_value": param.max_value,
                    "description": param.description,
                    "required": param.required
                }
                for param in strategy_class().get_parameter_schema()
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))