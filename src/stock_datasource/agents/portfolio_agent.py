"""Portfolio Agent for position management using LangGraph/DeepAgents."""

from typing import Dict, Any, List, Callable
import logging
from datetime import datetime

from .base_agent import LangGraphAgent, AgentConfig
from .tools import get_stock_info

logger = logging.getLogger(__name__)

# 用户隔离的持仓存储（生产环境应使用数据库）
# 格式: {user_id: {"positions": {...}}}
_user_portfolio_store: Dict[str, Dict] = {}

# 当前上下文中的 user_id (用于工具函数访问)
_current_user_id: str = "default_user"


def _get_user_portfolio() -> Dict:
    """获取当前用户的持仓存储."""
    global _user_portfolio_store, _current_user_id
    if _current_user_id not in _user_portfolio_store:
        _user_portfolio_store[_current_user_id] = {"positions": {}}
    return _user_portfolio_store[_current_user_id]


def add_position(
    code: str,
    quantity: int,
    cost_price: float,
    buy_date: str = ""
) -> str:
    """添加持仓记录。
    
    Args:
        code: 股票代码，如 600519 或 600519.SH
        quantity: 持仓数量（股）
        cost_price: 成本价
        buy_date: 买入日期，格式YYYY-MM-DD，留空使用当前日期
    
    Returns:
        添加结果消息
    """
    # Auto-complete code suffix
    if len(code) == 6 and code.isdigit():
        if code.startswith('6'):
            code = f"{code}.SH"
        elif code.startswith(('0', '3')):
            code = f"{code}.SZ"
    
    code = code.upper()
    
    if not buy_date:
        buy_date = datetime.now().strftime("%Y-%m-%d")
    
    portfolio = _get_user_portfolio()
    if "positions" not in portfolio:
        portfolio["positions"] = {}
    
    portfolio["positions"][code] = {
        "quantity": quantity,
        "cost_price": cost_price,
        "buy_date": buy_date,
        "total_cost": quantity * cost_price,
    }
    
    return f"已添加持仓: {code}, 数量: {quantity}股, 成本价: {cost_price:.2f}元, 买入日期: {buy_date}"


def update_position(
    code: str,
    action: str,
    quantity: int,
    price: float
) -> str:
    """更新持仓（加仓/减仓）。
    
    Args:
        code: 股票代码
        action: 操作类型 - buy(买入/加仓), sell(卖出/减仓)
        quantity: 数量
        price: 成交价格
    
    Returns:
        更新结果消息
    """
    code = code.upper()
    if len(code) == 6 and code.isdigit():
        if code.startswith('6'):
            code = f"{code}.SH"
        elif code.startswith(('0', '3')):
            code = f"{code}.SZ"
    
    portfolio = _get_user_portfolio()
    positions = portfolio.get("positions", {})
    
    if code not in positions:
        if action == "buy":
            return add_position(code, quantity, price)
        return f"持仓中没有 {code}"
    
    pos = positions[code]
    
    if action == "buy":
        # 加仓：计算新的平均成本
        old_cost = pos["quantity"] * pos["cost_price"]
        new_cost = quantity * price
        new_quantity = pos["quantity"] + quantity
        new_avg_price = (old_cost + new_cost) / new_quantity
        
        pos["quantity"] = new_quantity
        pos["cost_price"] = new_avg_price
        pos["total_cost"] = new_quantity * new_avg_price
        
        return f"已加仓 {code}: +{quantity}股 @ {price:.2f}元, 新持仓: {new_quantity}股, 平均成本: {new_avg_price:.2f}元"
    
    elif action == "sell":
        if quantity > pos["quantity"]:
            return f"卖出数量({quantity})超过持仓数量({pos['quantity']})"
        
        pos["quantity"] -= quantity
        if pos["quantity"] == 0:
            del positions[code]
            return f"已清仓 {code}: -{quantity}股 @ {price:.2f}元"
        
        pos["total_cost"] = pos["quantity"] * pos["cost_price"]
        return f"已减仓 {code}: -{quantity}股 @ {price:.2f}元, 剩余: {pos['quantity']}股"
    
    return f"未知操作: {action}"


def get_positions() -> str:
    """获取用户持仓列表。
    
    Returns:
        持仓列表，包含股票代码、数量、成本价等
    """
    portfolio = _get_user_portfolio()
    positions = portfolio.get("positions", {})
    
    if not positions:
        return "当前没有持仓记录。\n\n💡 使用 add_position 添加持仓。"
    
    lines = ["## 持仓列表\n"]
    lines.append("| 代码 | 数量(股) | 成本价 | 成本金额 | 买入日期 |")
    lines.append("|------|----------|--------|----------|----------|")
    
    total_cost = 0
    for code, pos in positions.items():
        lines.append(
            f"| {code} | {pos['quantity']} | {pos['cost_price']:.2f} | "
            f"{pos['total_cost']:.2f} | {pos['buy_date']} |"
        )
        total_cost += pos["total_cost"]
    
    lines.append(f"\n**总成本金额**: {total_cost:.2f}元")
    
    return "\n".join(lines)


def calculate_portfolio_pnl() -> str:
    """计算持仓组合的总体盈亏。
    
    Returns:
        盈亏统计（注：需要实时行情数据计算真实盈亏）
    """
    portfolio = _get_user_portfolio()
    positions = portfolio.get("positions", {})
    
    if not positions:
        return "当前没有持仓，无法计算盈亏。"
    
    lines = ["## 持仓盈亏统计\n"]
    lines.append("⚠️ 注意：实时盈亏需要获取最新行情数据。\n")
    
    total_cost = 0
    for code, pos in positions.items():
        total_cost += pos["total_cost"]
        lines.append(f"- {code}: 成本 {pos['total_cost']:.2f}元")
    
    lines.append(f"\n**总成本**: {total_cost:.2f}元")
    lines.append("\n💡 提示：使用 get_stock_info 获取最新价格计算实时盈亏。")
    
    return "\n".join(lines)


class PortfolioAgent(LangGraphAgent):
    """Portfolio Agent for position and portfolio management using DeepAgents.
    
    Handles:
    - Position tracking
    - P&L calculation
    - Portfolio analysis
    """
    
    def __init__(self):
        config = AgentConfig(
            name="PortfolioAgent",
            description="负责持仓管理，包括模拟持仓、盈亏计算、持仓分析等"
        )
        super().__init__(config)
    
    async def execute(self, task: str, context: Dict[str, Any] = None):
        """Execute with user context injection."""
        global _current_user_id
        context = context or {}
        _current_user_id = context.get("user_id", "default_user")
        return await super().execute(task, context)
    
    async def execute_stream(self, task: str, context: Dict[str, Any] = None):
        """Execute stream with user context injection."""
        global _current_user_id
        context = context or {}
        _current_user_id = context.get("user_id", "default_user")
        async for event in super().execute_stream(task, context):
            yield event
    
    def get_tools(self) -> List[Callable]:
        """Return portfolio management tools."""
        return [
            add_position,
            update_position,
            get_positions,
            calculate_portfolio_pnl,
            get_stock_info,
        ]
    
    def get_system_prompt(self) -> str:
        """Return system prompt for portfolio management."""
        return """你是持仓管理助手，帮助用户管理模拟持仓和计算盈亏。

## 可用工具
- add_position: 添加新持仓
- update_position: 更新持仓（加仓/减仓）
- get_positions: 获取持仓列表
- calculate_portfolio_pnl: 计算持仓盈亏
- get_stock_info: 获取股票最新行情

## 持仓操作
1. **添加持仓**: add_position(code, quantity, cost_price, buy_date)
2. **加仓**: update_position(code, "buy", quantity, price)
3. **减仓**: update_position(code, "sell", quantity, price)
4. **查看持仓**: get_positions()

## 盈亏计算
- 浮动盈亏 = (现价 - 成本价) × 持仓数量
- 盈亏比例 = 浮动盈亏 / 成本金额 × 100%

## 工作流程
1. 理解用户的持仓操作需求
2. 调用相应工具执行操作
3. 返回操作结果和当前持仓状态

## 注意事项
- 确认操作参数后再执行
- 卖出时检查持仓数量
- 计算盈亏时获取最新行情
"""
