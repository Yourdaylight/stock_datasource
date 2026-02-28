"""
策略相关的API路由
"""
from typing import List, Dict, Any, Optional
import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from ..strategies.registry import StrategyRegistry
from ..strategies.init import get_strategy_registry
from ..modules.auth.dependencies import get_current_user, get_current_user_optional
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
    additional_requirements: Optional[str] = None

class TradingConfig(BaseModel):
    initial_capital: float = 100000.0
    commission_rate: float = 0.0003
    slippage_rate: float = 0.001
    min_commission: float = 5.0


class IntelligentConfig(BaseModel):
    enable_optimization: bool = False
    enable_robustness: bool = False
    optimization_algorithm: str = "grid_search"


class BacktestRequest(BaseModel):
    strategy_id: str
    symbols: List[str] = []  # 支持多个股票
    symbol: Optional[str] = None  # 兼容单个股票
    start_date: str
    end_date: str
    benchmark: Optional[str] = "000300.SH"
    initial_capital: float = 100000.0  # 兼容旧格式
    trading_config: Optional[TradingConfig] = None
    parameters: Dict[str, Any] = {}
    intelligent_config: Optional[IntelligentConfig] = None

class CreateStrategyRequest(BaseModel):
    """创建策略请求"""
    name: str
    strategy_data: Dict[str, Any]
    parameters: Dict[str, Any] = {}
    description: Optional[str] = None


logger = logging.getLogger(__name__)

# 用户策略持久化存储路径
_USER_STRATEGY_STORE_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "strategies" / "user_strategies.json"
)


def _load_user_strategies() -> Dict[str, Dict[str, Any]]:
    if not _USER_STRATEGY_STORE_PATH.exists():
        return {}
    try:
        with _USER_STRATEGY_STORE_PATH.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if isinstance(data, dict):
            return data
        logger.warning("用户策略存储格式异常，已忽略加载")
    except Exception as error:
        logger.warning(f"加载用户策略失败: {error}")
    return {}


def _save_user_strategies() -> None:
    try:
        _USER_STRATEGY_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _USER_STRATEGY_STORE_PATH.open("w", encoding="utf-8") as file:
            json.dump(_user_strategies, file, ensure_ascii=False, indent=2)
    except Exception as error:
        logger.error(f"保存用户策略失败: {error}")


# 存储用户创建的策略（持久化到文件，生产环境应使用数据库）
# 结构: {strategy_id: {"user_id": str, "strategy": Dict}}
_user_strategies: Dict[str, Dict[str, Any]] = _load_user_strategies()


@router.post("/")
async def create_strategy(
    request: CreateStrategyRequest,
    current_user: dict = Depends(get_current_user),
):
    """创建新策略（需要登录，策略将绑定到当前用户）"""
    import uuid
    from datetime import datetime
    
    try:
        # 获取当前用户ID
        user_id = current_user["id"]
        
        # 从 strategy_data 中获取基本信息
        strategy_data = request.strategy_data
        strategy_id = strategy_data.get("id", f"user_{uuid.uuid4().hex[:8]}")
        
        # 构建完整的策略信息
        strategy = {
            "id": strategy_id,
            "user_id": user_id,  # Add user ownership
            "name": request.name,
            "description": request.description or strategy_data.get("description", ""),
            "category": strategy_data.get("category", "custom"),
            "author": strategy_data.get("author", current_user.get("username", "User")),
            "version": strategy_data.get("version", "1.0.0"),
            "tags": strategy_data.get("tags", []),
            "risk_level": strategy_data.get("risk_level", "medium"),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "usage_count": 0,
            "is_ai_generated": strategy_data.get("is_ai_generated", False),
            "generation_prompt": strategy_data.get("generation_prompt", ""),
            "parameter_schema": strategy_data.get("parameter_schema", []),
            "parameters": request.parameters,
            "confidence_score": strategy_data.get("confidence_score", 0)
        }
        
        # 存储策略（带有user_id）
        _user_strategies[strategy_id] = {
            "user_id": user_id,
            "strategy": strategy
        }
        _save_user_strategies()
        
        return {"data": strategy}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建策略失败: {str(e)}")


@router.get("/", response_model=StrategyListResponse)
async def get_strategies(
    current_user: dict = Depends(get_current_user_optional),
):
    """获取所有可用策略列表（内置策略 + 当前用户的自定义策略）"""
    try:
        registry = get_strategy_registry()
        strategies = []
        
        # 获取内置策略
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
        
        # 添加当前用户的自定义策略（如果已登录）
        if current_user:
            user_id = current_user["id"]
            for strategy_id, strategy_data in _user_strategies.items():
                # 只返回属于当前用户的策略，或管理员可以看到所有策略
                if strategy_data.get("user_id") == user_id or current_user.get("is_admin", False):
                    strategy = strategy_data.get("strategy", strategy_data)
                    strategies.append(StrategyResponse(
                        id=strategy["id"],
                        name=strategy["name"],
                        description=strategy.get("description", ""),
                        category=strategy.get("category", "custom"),
                        author=strategy.get("author", "User"),
                        version=strategy.get("version", "1.0.0"),
                        tags=strategy.get("tags", []),
                        risk_level=strategy.get("risk_level", "medium"),
                        created_at=strategy.get("created_at", ""),
                        updated_at=strategy.get("updated_at", ""),
                        usage_count=strategy.get("usage_count", 0),
                        is_ai_generated=strategy.get("is_ai_generated", False),
                        parameter_schema=strategy.get("parameter_schema", [])
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

@router.post("/backtest")
async def run_backtest(request: BacktestRequest):
    """运行策略回测"""
    import uuid
    from datetime import datetime
    
    try:
        registry = get_strategy_registry()
        strategy_class = registry.get_strategy_class(request.strategy_id)
        
        if not strategy_class:
            raise HTTPException(status_code=404, detail=f"策略 {request.strategy_id} 不存在")
        
        # 获取策略信息
        strategy_info = registry._strategies[request.strategy_id]
        strategy_name = strategy_info.metadata.name
        
        # TODO: 实现真实回测逻辑，目前返回模拟数据
        backtest_id = str(uuid.uuid4())
        
        # 处理 symbols（兼容 symbols 数组和 symbol 单个字符串）
        symbols = request.symbols if request.symbols else ([request.symbol] if request.symbol else [])
        
        # 获取初始资金（优先从 trading_config 获取）
        if request.trading_config:
            initial_capital = request.trading_config.initial_capital
        else:
            initial_capital = request.initial_capital
        
        final_capital = initial_capital * 1.15  # 模拟15%收益
        
        return {
            "data": {
                "id": backtest_id,
                "strategy_id": request.strategy_id,
                "config": {
                    "strategy_id": request.strategy_id,
                    "symbol": symbols[0] if symbols else "",
                    "symbols": symbols,
                    "start_date": request.start_date,
                    "end_date": request.end_date,
                    "initial_capital": initial_capital,
                    "parameters": request.parameters
                },
                "performance_metrics": {
                    "total_return": 15.0,
                    "annual_return": 12.5,
                    "sharpe_ratio": 1.2,
                    "max_drawdown": 8.5,
                    "win_rate": 55.0,
                    "profit_factor": 1.8
                },
                "trades": [
                    {
                        "date": request.start_date,
                        "direction": "buy",
                        "price": 100.0,
                        "quantity": int(initial_capital / 100),
                        "amount": initial_capital,
                        "signal_reason": "策略信号"
                    }
                ],
                "equity_curve": [
                    {"date": request.start_date, "value": initial_capital},
                    {"date": request.end_date, "value": final_capital}
                ],
                "created_at": datetime.now().isoformat()
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/backtest/{backtest_id}")
async def get_backtest_result(backtest_id: str):
    """获取回测结果"""
    from datetime import datetime
    
    # TODO: 从数据库获取真实回测结果
    return {
        "data": {
            "id": backtest_id,
            "strategy_id": "ma_strategy",
            "config": {
                "strategy_id": "ma_strategy",
                "symbol": "600519.SH",
                "start_date": "2023-01-01",
                "end_date": "2024-01-01",
                "initial_capital": 100000,
                "parameters": {}
            },
            "performance_metrics": {
                "total_return": 15.0,
                "annual_return": 12.5,
                "sharpe_ratio": 1.2,
                "max_drawdown": 8.5,
                "win_rate": 55.0,
                "profit_factor": 1.8
            },
            "trades": [],
            "equity_curve": [],
            "created_at": datetime.now().isoformat()
        }
    }


@router.post("/ai-generate")
async def generate_ai_strategy(
    request: AIStrategyRequest,
    current_user: dict = Depends(get_current_user),
):
    """AI生成策略（需要登录，生成的策略将绑定到当前用户）"""
    import uuid
    from datetime import datetime
    
    try:
        # 获取当前用户ID
        user_id = current_user["id"]
        
        # 根据用户描述生成策略
        strategy_id = f"ai_{uuid.uuid4().hex[:8]}"
        
        # 解析用户描述，生成策略名称
        description = request.description
        market_type = request.market_type
        risk_level = request.risk_level
        time_frame = request.time_frame
        
        # 根据描述生成策略名称
        strategy_name = f"AI策略-{strategy_id[-8:]}"
        if "均线" in description or "ma" in description.lower():
            strategy_name = "AI均线交叉策略"
        elif "动量" in description or "momentum" in description.lower():
            strategy_name = "AI动量策略"
        elif "趋势" in description or "trend" in description.lower():
            strategy_name = "AI趋势跟踪策略"
        elif "反转" in description or "reversal" in description.lower():
            strategy_name = "AI均值回归策略"
        elif "突破" in description or "breakout" in description.lower():
            strategy_name = "AI突破策略"
        
        # 根据风险等级设置参数
        if risk_level == "low":
            stop_loss = 0.03
            take_profit = 0.06
        elif risk_level == "high":
            stop_loss = 0.08
            take_profit = 0.20
        else:  # medium
            stop_loss = 0.05
            take_profit = 0.10
        
        # 根据时间周期设置参数
        if time_frame == "1min":
            short_period = 5
            long_period = 20
        elif time_frame == "5min":
            short_period = 10
            long_period = 30
        elif time_frame == "weekly":
            short_period = 4
            long_period = 12
        else:  # daily
            short_period = 10
            long_period = 30
        
        # 构建生成的策略响应
        generated_strategy = {
            "id": strategy_id,
            "user_id": user_id,  # Add user ownership
            "name": strategy_name,
            "description": f"基于用户描述自动生成: {description}",
            "category": "ai_generated",
            "author": current_user.get("username", "AI Generator"),
            "version": "1.0.0",
            "tags": ["AI生成", market_type, risk_level, time_frame],
            "risk_level": risk_level,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "usage_count": 0,
            "is_ai_generated": True,
            "generation_prompt": description,
            "confidence_score": 0.85,  # AI confidence score
            "parameter_schema": [
                {
                    "name": "short_period",
                    "type": "int",
                    "default": short_period,
                    "min_value": 2,
                    "max_value": 50,
                    "description": "短期周期",
                    "required": True
                },
                {
                    "name": "long_period",
                    "type": "int",
                    "default": long_period,
                    "min_value": 10,
                    "max_value": 200,
                    "description": "长期周期",
                    "required": True
                },
                {
                    "name": "stop_loss",
                    "type": "float",
                    "default": stop_loss,
                    "min_value": 0.01,
                    "max_value": 0.2,
                    "description": "止损比例",
                    "required": False
                },
                {
                    "name": "take_profit",
                    "type": "float",
                    "default": take_profit,
                    "min_value": 0.02,
                    "max_value": 0.5,
                    "description": "止盈比例",
                    "required": False
                }
            ]
        }
        
        _user_strategies[strategy_id] = {
            "user_id": user_id,
            "strategy": generated_strategy
        }
        _save_user_strategies()

        # Generate explanation based on strategy type
        explanation = f"根据您的描述，AI生成了一个{strategy_name}。"
        if "均线" in description or "ma" in description.lower():
            explanation += "该策略基于移动平均线的交叉信号，当短期均线上穿长期均线时产生买入信号，下穿时产生卖出信号。"
        elif "动量" in description or "momentum" in description.lower():
            explanation += "该策略追踪市场动量，在趋势形成初期入场，捕捉价格惯性带来的收益。"
        elif "趋势" in description or "trend" in description.lower():
            explanation += "该策略专注于识别和跟踪市场主要趋势，在趋势延续时持有仓位。"
        else:
            explanation += "该策略结合了技术指标分析，通过参数优化来适应不同的市场环境。"
        
        # Generate risk warnings based on risk level
        risk_warnings = []
        if risk_level == "high":
            risk_warnings = [
                "高风险策略可能导致较大的资金回撤",
                "建议使用较小的仓位进行测试",
                "在实盘前请务必进行充分的回测验证"
            ]
        elif risk_level == "medium":
            risk_warnings = [
                "中等风险策略需要关注市场波动",
                "建议设置合理的止损止盈参数"
            ]
        else:
            risk_warnings = [
                "低风险策略收益可能相对有限",
                "适合长期稳健投资"
            ]
        
        return {
            "data": {
                "strategy": generated_strategy,
                "explanation": explanation,
                "risk_warnings": risk_warnings
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI策略生成失败: {str(e)}")


@router.get("/{strategy_id}/backtest-history")
async def get_backtest_history(strategy_id: str):
    """获取策略回测历史"""
    # TODO: 从数据库获取真实历史记录
    return {"data": []}


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