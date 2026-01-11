"""
交易模拟器

模拟真实的交易执行过程，包括：
- 订单执行
- 手续费计算
- 滑点模拟
- 仓位管理
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import pandas as pd
import numpy as np
import uuid

from .models import (
    Trade, TradeType, TradeStatus, Position, TradingConfig
)
from ..strategies.base import TradingSignal

logger = logging.getLogger(__name__)


class TradingSimulator:
    """交易模拟器"""
    
    def __init__(self, config: TradingConfig):
        """
        初始化交易模拟器
        
        Args:
            config: 交易配置
        """
        self.config = config
        self.cash = config.initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.portfolio_value_history: List[float] = []
        
        logger.info(f"Trading simulator initialized with capital: {config.initial_capital}")
    
    def execute_signal(self, signal: TradingSignal, market_data: pd.Series) -> Optional[Trade]:
        """
        执行交易信号
        
        Args:
            signal: 交易信号
            market_data: 当前市场数据
            
        Returns:
            执行的交易记录，如果无法执行则返回None
        """
        try:
            # 获取当前价格
            current_price = self._get_execution_price(signal, market_data)
            
            # 计算交易数量
            quantity = self._calculate_trade_quantity(signal, current_price)
            
            if quantity == 0:
                logger.warning(f"Trade quantity is 0 for signal: {signal.action}")
                return None
            
            # 创建交易记录
            trade = Trade(
                trade_id=str(uuid.uuid4()),
                symbol=signal.symbol,
                trade_type=TradeType.BUY if signal.action == 'buy' else TradeType.SELL,
                quantity=quantity,
                price=current_price,
                timestamp=signal.timestamp,
                signal_reason=signal.reason
            )
            
            # 计算手续费和滑点
            trade.commission = self._calculate_commission(trade)
            trade.slippage = self._calculate_slippage(trade, market_data)
            
            # 检查是否可以执行交易
            if not self._can_execute_trade(trade):
                logger.warning(f"Cannot execute trade: insufficient funds or position limits")
                return None
            
            # 执行交易
            self._execute_trade(trade)
            
            logger.info(f"Executed trade: {trade.trade_type.value} {trade.quantity} {trade.symbol} @ {trade.price}")
            return trade
            
        except Exception as e:
            logger.error(f"Error executing signal: {e}")
            return None
    
    def _get_execution_price(self, signal: TradingSignal, market_data: pd.Series) -> float:
        """获取执行价格"""
        # 基础价格
        base_price = signal.price if signal.price > 0 else market_data.get('close', 0)
        
        # 添加滑点影响
        slippage_factor = 1.0
        if signal.action == 'buy':
            slippage_factor = 1 + self.config.slippage_rate
        else:
            slippage_factor = 1 - self.config.slippage_rate
        
        return base_price * slippage_factor
    
    def _calculate_trade_quantity(self, signal: TradingSignal, price: float) -> int:
        """计算交易数量"""
        if signal.quantity and signal.quantity > 0:
            return signal.quantity
        
        # 如果没有指定数量，使用默认逻辑
        symbol = signal.symbol
        
        if signal.action == 'buy':
            # 买入：使用可用资金的一定比例
            available_cash = self.cash
            max_investment = available_cash * 0.95  # 保留5%现金
            
            # 考虑手续费
            estimated_commission = max(max_investment * self.config.commission_rate, self.config.min_commission)
            net_investment = max_investment - estimated_commission
            
            if net_investment <= 0:
                return 0
            
            quantity = int(net_investment / price)
            return max(0, quantity)
        
        else:  # sell
            # 卖出：卖出当前持仓
            if symbol in self.positions:
                return self.positions[symbol].quantity
            return 0
    
    def _calculate_commission(self, trade: Trade) -> float:
        """计算手续费"""
        commission = trade.trade_value * self.config.commission_rate
        return max(commission, self.config.min_commission)
    
    def _calculate_slippage(self, trade: Trade, market_data: pd.Series) -> float:
        """计算滑点成本"""
        # 简化的滑点模型：基于交易金额和市场波动率
        base_slippage = self.config.slippage_rate
        
        # 根据成交量调整滑点
        volume = market_data.get('volume', 1000000)
        if volume > 0:
            volume_impact = min(trade.trade_value / (volume * trade.price) * 0.1, 0.01)
            base_slippage += volume_impact
        
        return base_slippage
    
    def _can_execute_trade(self, trade: Trade) -> bool:
        """检查是否可以执行交易"""
        total_cost = trade.total_cost
        
        if trade.trade_type == TradeType.BUY:
            # 买入：检查现金是否足够
            return self.cash >= total_cost
        
        elif trade.trade_type == TradeType.SELL:
            # 卖出：检查是否有足够的持仓
            symbol = trade.symbol
            if symbol not in self.positions:
                return False
            return self.positions[symbol].quantity >= trade.quantity
        
        return False
    
    def _execute_trade(self, trade: Trade) -> None:
        """执行交易"""
        symbol = trade.symbol
        
        # 确保持仓记录存在
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol=symbol)
        
        position = self.positions[symbol]
        
        if trade.trade_type == TradeType.BUY:
            # 买入逻辑
            old_quantity = position.quantity
            old_value = old_quantity * position.avg_price if old_quantity > 0 else 0
            
            new_quantity = old_quantity + trade.quantity
            new_value = old_value + trade.trade_value
            
            position.quantity = new_quantity
            position.avg_price = new_value / new_quantity if new_quantity > 0 else 0
            
            # 更新现金
            self.cash -= trade.total_cost
            
        elif trade.trade_type == TradeType.SELL:
            # 卖出逻辑
            old_quantity = position.quantity
            
            # 计算已实现盈亏
            sell_cost = trade.quantity * position.avg_price
            sell_proceeds = trade.trade_value - trade.commission
            realized_pnl = sell_proceeds - sell_cost
            
            position.quantity = old_quantity - trade.quantity
            position.realized_pnl += realized_pnl
            
            # 更新现金
            self.cash += sell_proceeds
        
        # 标记交易为已成交
        trade.status = TradeStatus.FILLED
        self.trades.append(trade)
        
        logger.debug(f"Trade executed: {trade.trade_type.value} {trade.quantity} {symbol}, Cash: {self.cash:.2f}")
    
    def update_positions(self, market_data: Dict[str, pd.Series]) -> None:
        """更新持仓的市值和未实现盈亏"""
        total_market_value = 0
        
        for symbol, position in self.positions.items():
            if position.quantity == 0:
                position.market_value = 0
                position.unrealized_pnl = 0
                continue
            
            # 获取当前市价
            if symbol in market_data:
                current_price = market_data[symbol].get('close', position.avg_price)
            else:
                current_price = position.avg_price
            
            # 更新市值
            position.market_value = position.quantity * current_price
            total_market_value += position.market_value
            
            # 更新未实现盈亏
            cost_basis = position.quantity * position.avg_price
            position.unrealized_pnl = position.market_value - cost_basis
        
        # 记录组合总价值
        portfolio_value = self.cash + total_market_value
        self.portfolio_value_history.append(portfolio_value)
    
    def get_portfolio_value(self) -> float:
        """获取当前组合价值"""
        total_market_value = sum(pos.market_value for pos in self.positions.values())
        return self.cash + total_market_value
    
    def get_portfolio_summary(self) -> Dict[str, any]:
        """获取组合摘要"""
        total_market_value = sum(pos.market_value for pos in self.positions.values())
        total_unrealized_pnl = sum(pos.unrealized_pnl for pos in self.positions.values())
        total_realized_pnl = sum(pos.realized_pnl for pos in self.positions.values())
        
        return {
            'cash': self.cash,
            'market_value': total_market_value,
            'total_value': self.cash + total_market_value,
            'unrealized_pnl': total_unrealized_pnl,
            'realized_pnl': total_realized_pnl,
            'total_pnl': total_unrealized_pnl + total_realized_pnl,
            'positions_count': len([p for p in self.positions.values() if p.quantity != 0]),
            'total_trades': len(self.trades)
        }
    
    def get_position_details(self) -> List[Dict[str, any]]:
        """获取持仓详情"""
        details = []
        for symbol, position in self.positions.items():
            if position.quantity != 0:
                details.append({
                    'symbol': symbol,
                    'quantity': position.quantity,
                    'avg_price': position.avg_price,
                    'market_value': position.market_value,
                    'unrealized_pnl': position.unrealized_pnl,
                    'realized_pnl': position.realized_pnl,
                    'total_pnl': position.unrealized_pnl + position.realized_pnl
                })
        return details
    
    def reset(self) -> None:
        """重置模拟器状态"""
        self.cash = self.config.initial_capital
        self.positions.clear()
        self.trades.clear()
        self.portfolio_value_history.clear()
        
        logger.info("Trading simulator reset")
    
    def get_equity_curve(self) -> pd.Series:
        """获取权益曲线"""
        if not self.portfolio_value_history:
            return pd.Series([self.config.initial_capital])
        
        return pd.Series(self.portfolio_value_history)
    
    def calculate_returns(self) -> pd.Series:
        """计算收益率序列"""
        equity_curve = self.get_equity_curve()
        if len(equity_curve) < 2:
            return pd.Series([0.0])
        
        returns = equity_curve.pct_change().fillna(0)
        return returns