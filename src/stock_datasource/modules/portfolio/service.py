"""Portfolio service for managing user positions."""

import logging
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Position data model."""
    id: str
    ts_code: str
    stock_name: str
    quantity: int
    cost_price: float
    buy_date: str
    current_price: Optional[float] = None
    market_value: Optional[float] = None
    profit_loss: Optional[float] = None
    profit_rate: Optional[float] = None
    notes: Optional[str] = None


@dataclass
class PortfolioSummary:
    """Portfolio summary data model."""
    total_value: float
    total_cost: float
    total_profit: float
    profit_rate: float
    daily_change: float
    daily_change_rate: float
    position_count: int


class PortfolioService:
    """Portfolio service for managing positions."""
    
    def __init__(self):
        self._db = None
        # In-memory storage for demo (should be replaced with database)
        self._positions: Dict[str, Position] = {}
        
        # Add some sample data
        sample_position = Position(
            id="pos_001",
            ts_code="600519.SH",
            stock_name="贵州茅台",
            quantity=100,
            cost_price=1700.0,
            buy_date="2024-01-01",
            current_price=1800.0,
            market_value=180000.0,
            profit_loss=10000.0,
            profit_rate=5.88,
            notes="初始持仓"
        )
        self._positions[sample_position.id] = sample_position
    
    @property
    def db(self):
        """Lazy load database client."""
        if self._db is None:
            try:
                from stock_datasource.models.database import db_client
                self._db = db_client
            except Exception as e:
                logger.warning(f"Failed to get DB client: {e}")
        return self._db
    
    async def get_positions(self, user_id: str = "default_user") -> List[Position]:
        """Get all positions for a user."""
        try:
            if self.db is not None:
                # Always filter by user_id for security
                query = """
                    SELECT 
                        id, ts_code, stock_name, quantity, cost_price, 
                        buy_date, current_price, market_value, profit_loss, 
                        profit_rate, notes
                    FROM user_positions 
                    WHERE user_id = %(user_id)s
                    ORDER BY buy_date DESC
                """
                df = self.db.execute_query(query, {'user_id': user_id})
                
                if not df.empty:
                    positions = []
                    ts_codes = df['ts_code'].unique().tolist()
                    
                    # 批量获取所有股票的最新价格
                    prices_cache = await self._batch_get_latest_prices(ts_codes)
                    
                    for _, row in df.iterrows():
                        position = Position(
                            id=str(row['id']),
                            ts_code=row['ts_code'],
                            stock_name=row['stock_name'],
                            quantity=int(row['quantity']),
                            cost_price=float(row['cost_price']),
                            buy_date=str(row['buy_date']),
                            current_price=float(row['current_price']) if pd.notna(row['current_price']) else None,
                            market_value=float(row['market_value']) if pd.notna(row['market_value']) else None,
                            profit_loss=float(row['profit_loss']) if pd.notna(row['profit_loss']) else None,
                            profit_rate=float(row['profit_rate']) if pd.notna(row['profit_rate']) else None,
                            notes=row['notes'] if pd.notna(row['notes']) else None
                        )
                        # Update current prices and calculations using cached prices
                        await self._update_position_prices(position, prices_cache)
                        positions.append(position)
                    
                    return positions
        except Exception as e:
            logger.warning(f"Failed to get positions from database: {e}")
        
        # Fallback to in-memory storage
        positions = list(self._positions.values())
        
        # Update current prices and calculations
        for position in positions:
            await self._update_position_prices(position)
        
        return positions
    
    async def add_position(self, ts_code: str, quantity: int, cost_price: float, 
                          buy_date: str, notes: Optional[str] = None, user_id: str = "default_user") -> Position:
        """Add a new position."""
        position_id = str(uuid.uuid4())
        
        # Get stock name
        stock_name = await self._get_stock_name(ts_code)
        
        position = Position(
            id=position_id,
            ts_code=ts_code,
            stock_name=stock_name,
            quantity=quantity,
            cost_price=cost_price,
            buy_date=buy_date,
            notes=notes
        )
        
        # Update current price and calculations
        await self._update_position_prices(position)
        
        try:
            if self.db is not None:
                # Try to save to database
                query = """
                    INSERT INTO user_positions 
                    (id, user_id, ts_code, stock_name, quantity, cost_price, buy_date, 
                     current_price, market_value, profit_loss, profit_rate, notes)
                    VALUES (%(id)s, %(user_id)s, %(ts_code)s, %(stock_name)s, %(quantity)s, %(cost_price)s, 
                            %(buy_date)s, %(current_price)s, %(market_value)s, 
                            %(profit_loss)s, %(profit_rate)s, %(notes)s)
                """
                params = {
                    'id': position.id,
                    'user_id': user_id,
                    'ts_code': position.ts_code,
                    'stock_name': position.stock_name,
                    'quantity': position.quantity,
                    'cost_price': position.cost_price,
                    'buy_date': position.buy_date,
                    'current_price': position.current_price,
                    'market_value': position.market_value,
                    'profit_loss': position.profit_loss,
                    'profit_rate': position.profit_rate,
                    'notes': position.notes
                }
                self.db.execute(query, params)
                logger.info(f"Position {position_id} saved to database for user {user_id}")
        except Exception as e:
            logger.warning(f"Failed to save position to database: {e}")
        
        # Always save to in-memory storage as backup
        self._positions[position_id] = position
        logger.info(f"Position {position_id} added: {ts_code}")
        
        return position
    
    async def delete_position(self, position_id: str, user_id: str = "default_user") -> bool:
        """Delete a position."""
        try:
            if self.db is not None:
                # Try to delete from database (only if belongs to user)
                query = "DELETE FROM user_positions WHERE id = %(id)s AND user_id = %(user_id)s"
                self.db.execute(query, {'id': position_id, 'user_id': user_id})
                logger.info(f"Position {position_id} deleted from database for user {user_id}")
        except Exception as e:
            logger.warning(f"Failed to delete position from database: {e}")
        
        # Always delete from in-memory storage
        if position_id in self._positions:
            del self._positions[position_id]
            logger.info(f"Position {position_id} deleted")
            return True
        
        return False
    
    async def get_summary(self, user_id: str = "default_user") -> PortfolioSummary:
        """Get portfolio summary for a user."""
        positions = await self.get_positions(user_id=user_id)
        
        if not positions:
            return PortfolioSummary(
                total_value=0.0,
                total_cost=0.0,
                total_profit=0.0,
                profit_rate=0.0,
                daily_change=0.0,
                daily_change_rate=0.0,
                position_count=0
            )
        
        total_cost = sum(p.quantity * p.cost_price for p in positions)
        total_value = sum(p.market_value or 0 for p in positions)
        total_profit = total_value - total_cost
        profit_rate = (total_profit / total_cost * 100) if total_cost > 0 else 0
        
        # Mock daily change (should be calculated from actual data)
        daily_change = total_value * 0.01  # 1% mock change
        daily_change_rate = 1.0
        
        return PortfolioSummary(
            total_value=total_value,
            total_cost=total_cost,
            total_profit=total_profit,
            profit_rate=profit_rate,
            daily_change=daily_change,
            daily_change_rate=daily_change_rate,
            position_count=len(positions)
        )
    
    async def _get_stock_name(self, ts_code: str) -> str:
        """Get stock name by code."""
        try:
            if self.db is not None:
                query = """
                    SELECT name FROM ods_stock_basic 
                    WHERE ts_code = %(code)s
                    LIMIT 1
                """
                df = self.db.execute_query(query, {'code': ts_code})
                if not df.empty:
                    return df.iloc[0]['name']
        except Exception as e:
            logger.warning(f"Failed to get stock name from database: {e}")
        
        # Fallback to mock names
        stock_names = {
            '600519.SH': '贵州茅台',
            '000001.SZ': '平安银行',
            '000002.SZ': '万科A',
            '600036.SH': '招商银行',
            '000858.SZ': '五粮液'
        }
        return stock_names.get(ts_code, f"股票{ts_code}")
    
    async def _batch_get_latest_prices(self, ts_codes: List[str]) -> Dict[str, float]:
        """Batch get latest prices for multiple stocks."""
        prices = {}
        if not ts_codes:
            return prices
            
        try:
            if self.db is not None:
                # 使用单条 SQL 批量获取所有股票的最新价格
                codes_str = "', '".join(ts_codes)
                query = f"""
                    SELECT ts_code, close 
                    FROM (
                        SELECT ts_code, close, 
                               ROW_NUMBER() OVER (PARTITION BY ts_code ORDER BY trade_date DESC) as rn
                        FROM ods_daily 
                        WHERE ts_code IN ('{codes_str}')
                    ) t
                    WHERE rn = 1
                """
                df = self.db.execute_query(query)
                if not df.empty:
                    for _, row in df.iterrows():
                        prices[row['ts_code']] = float(row['close'])
        except Exception as e:
            logger.warning(f"Failed to batch get prices from database: {e}")
        
        return prices
    
    async def _update_position_prices(self, position: Position, prices_cache: Dict[str, float] = None):
        """Update position current price and calculations."""
        # 优先使用缓存的价格
        if prices_cache and position.ts_code in prices_cache:
            position.current_price = prices_cache[position.ts_code]
        elif position.current_price is None:
            try:
                if self.db is not None:
                    # Try to get latest price from database
                    query = """
                        SELECT close FROM ods_daily 
                        WHERE ts_code = %(code)s 
                        ORDER BY trade_date DESC 
                        LIMIT 1
                    """
                    df = self.db.execute_query(query, {'code': position.ts_code})
                    if not df.empty:
                        position.current_price = float(df.iloc[0]['close'])
            except Exception as e:
                logger.warning(f"Failed to get current price from database: {e}")
        
        # Fallback to mock prices
        if position.current_price is None:
            mock_prices = {
                '600519.SH': 1800.0,
                '000001.SZ': 12.5,
                '000002.SZ': 18.3,
                '600036.SH': 35.2,
                '000858.SZ': 150.8
            }
            position.current_price = mock_prices.get(position.ts_code, position.cost_price * 1.05)
        
        # Calculate market value and profit/loss
        if position.current_price:
            position.market_value = position.quantity * position.current_price
            cost_total = position.quantity * position.cost_price
            position.profit_loss = position.market_value - cost_total
            position.profit_rate = (position.profit_loss / cost_total * 100) if cost_total > 0 else 0
    
    async def _batch_update_positions(self, positions: List[Position], user_id: str = "default_user"):
        """Batch update positions in database with latest prices."""
        if not self.db or not positions:
            return
        
        try:
            # Since we're using ReplacingMergeTree, we need to insert full records
            # The engine will automatically deduplicate based on ORDER BY keys
            for position in positions:
                query = """
                    INSERT INTO user_positions 
                    (id, user_id, ts_code, stock_name, quantity, cost_price, buy_date, 
                     current_price, market_value, profit_loss, profit_rate, notes, updated_at)
                    VALUES (%(id)s, %(user_id)s, %(ts_code)s, %(stock_name)s, %(quantity)s, %(cost_price)s, 
                            %(buy_date)s, %(current_price)s, %(market_value)s, 
                            %(profit_loss)s, %(profit_rate)s, %(notes)s, %(updated_at)s)
                """
                params = {
                    'id': position.id,
                    'user_id': user_id,
                    'ts_code': position.ts_code,
                    'stock_name': position.stock_name,
                    'quantity': position.quantity,
                    'cost_price': position.cost_price,
                    'buy_date': position.buy_date,
                    'current_price': position.current_price,
                    'market_value': position.market_value,
                    'profit_loss': position.profit_loss,
                    'profit_rate': position.profit_rate,
                    'notes': position.notes,
                    'updated_at': datetime.now()
                }
                self.db.execute(query, params)
            
            logger.info(f"Batch updated {len(positions)} positions for user {user_id}")
            
        except Exception as e:
            logger.warning(f"Failed to batch update positions: {e}")


# Global service instance
_portfolio_service = None


def get_portfolio_service() -> PortfolioService:
    """Get portfolio service instance."""
    global _portfolio_service
    if _portfolio_service is None:
        _portfolio_service = PortfolioService()
    return _portfolio_service