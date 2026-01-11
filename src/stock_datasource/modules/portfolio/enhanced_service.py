"""Enhanced Portfolio service for managing user positions."""

import logging
import uuid
from datetime import datetime, date
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, asdict
import pandas as pd
import json

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Enhanced position data model."""
    id: str
    user_id: str = "default_user"
    ts_code: str = ""
    stock_name: str = ""
    quantity: int = 0
    cost_price: float = 0.0
    buy_date: str = ""
    current_price: Optional[float] = None
    market_value: Optional[float] = None
    profit_loss: Optional[float] = None
    profit_rate: Optional[float] = None
    notes: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    last_price_update: Optional[datetime] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class PortfolioSummary:
    """Enhanced portfolio summary data model."""
    total_value: float
    total_cost: float
    total_profit: float
    profit_rate: float
    daily_change: float
    daily_change_rate: float
    position_count: int
    risk_score: Optional[float] = None
    top_performer: Optional[str] = None
    worst_performer: Optional[str] = None
    sector_distribution: Optional[Dict[str, float]] = None


@dataclass
class PositionAlert:
    """Position alert data model."""
    id: str
    user_id: str
    position_id: str
    ts_code: str
    alert_type: str  # 'price_high', 'price_low', 'profit_target', 'stop_loss', 'change_rate'
    condition_value: float
    current_value: float
    is_triggered: bool = False
    is_active: bool = True
    trigger_count: int = 0
    last_triggered: Optional[datetime] = None
    message: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class EnhancedPortfolioService:
    """Enhanced Portfolio service for managing positions."""
    
    def __init__(self):
        self._db = None
        # In-memory storage for demo (should be replaced with database)
        self._positions: Dict[str, Position] = {}
        self._alerts: Dict[str, PositionAlert] = {}
        
        # Add some sample data
        self._init_sample_data()
    
    def _init_sample_data(self):
        """Initialize with sample data."""
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
            notes="初始持仓",
            sector="消费品",
            industry="白酒",
            created_at=datetime.now(),
            updated_at=datetime.now()
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
    
    async def get_positions(self, user_id: str = "default_user", 
                           include_inactive: bool = False) -> List[Position]:
        """Get all positions for a user."""
        try:
            if self.db is not None:
                # Try to get from database first
                where_clause = "WHERE user_id = %(user_id)s"
                if not include_inactive:
                    where_clause += " AND is_active = 1"
                
                query = f"""
                    SELECT 
                        id, user_id, ts_code, stock_name, quantity, cost_price, 
                        buy_date, current_price, market_value, profit_loss, 
                        profit_rate, notes, sector, industry, last_price_update,
                        is_active, created_at, updated_at
                    FROM user_positions 
                    {where_clause}
                    ORDER BY buy_date DESC
                """
                df = self.db.execute_query(query, {'user_id': user_id})
                
                if not df.empty:
                    positions = []
                    for _, row in df.iterrows():
                        position = Position(
                            id=str(row['id']),
                            user_id=str(row['user_id']),
                            ts_code=row['ts_code'],
                            stock_name=row['stock_name'],
                            quantity=int(row['quantity']),
                            cost_price=float(row['cost_price']),
                            buy_date=str(row['buy_date']),
                            current_price=float(row['current_price']) if pd.notna(row['current_price']) else None,
                            market_value=float(row['market_value']) if pd.notna(row['market_value']) else None,
                            profit_loss=float(row['profit_loss']) if pd.notna(row['profit_loss']) else None,
                            profit_rate=float(row['profit_rate']) if pd.notna(row['profit_rate']) else None,
                            notes=row['notes'] if pd.notna(row['notes']) else None,
                            sector=row['sector'] if pd.notna(row['sector']) else None,
                            industry=row['industry'] if pd.notna(row['industry']) else None,
                            last_price_update=row['last_price_update'] if pd.notna(row['last_price_update']) else None,
                            is_active=bool(row['is_active']),
                            created_at=row['created_at'] if pd.notna(row['created_at']) else None,
                            updated_at=row['updated_at'] if pd.notna(row['updated_at']) else None
                        )
                        # Update current prices and calculations
                        await self._update_position_prices(position)
                        positions.append(position)
                    
                    # Update positions in database with latest prices
                    await self._batch_update_positions(positions)
                    return positions
        except Exception as e:
            logger.warning(f"Failed to get positions from database: {e}")
        
        # Fallback to in-memory storage
        positions = [p for p in self._positions.values() 
                    if p.user_id == user_id and (include_inactive or p.is_active)]
        
        # Update current prices and calculations
        for position in positions:
            await self._update_position_prices(position)
        
        return positions
    
    async def add_position(self, user_id: str, ts_code: str, quantity: int, 
                          cost_price: float, buy_date: str, 
                          notes: Optional[str] = None) -> Position:
        """Add a new position."""
        position_id = str(uuid.uuid4())
        
        # Get stock name and sector info
        stock_name, sector, industry = await self._get_stock_info(ts_code)
        
        position = Position(
            id=position_id,
            user_id=user_id,
            ts_code=ts_code,
            stock_name=stock_name,
            quantity=quantity,
            cost_price=cost_price,
            buy_date=buy_date,
            notes=notes,
            sector=sector,
            industry=industry,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # Update current price and calculations
        await self._update_position_prices(position)
        
        # Save to database and memory
        await self._save_position(position)
        
        # Record position history
        await self._record_position_history(position, 'create')
        
        logger.info(f"Position {position_id} added: {ts_code}")
        return position
    
    async def update_position(self, position_id: str, user_id: str,
                             **updates) -> Optional[Position]:
        """Update an existing position."""
        position = await self.get_position_by_id(position_id, user_id)
        if not position:
            return None
        
        # Update fields
        for field, value in updates.items():
            if hasattr(position, field):
                setattr(position, field, value)
        
        position.updated_at = datetime.now()
        
        # Recalculate if quantity or cost_price changed
        if 'quantity' in updates or 'cost_price' in updates:
            await self._update_position_prices(position)
        
        # Save to database and memory
        await self._save_position(position)
        
        # Record position history
        await self._record_position_history(position, 'update')
        
        logger.info(f"Position {position_id} updated")
        return position
    
    async def delete_position(self, position_id: str, user_id: str) -> bool:
        """Delete a position (soft delete)."""
        position = await self.get_position_by_id(position_id, user_id)
        if not position:
            return False
        
        position.is_active = False
        position.updated_at = datetime.now()
        
        # Save to database and memory
        await self._save_position(position)
        
        # Record position history
        await self._record_position_history(position, 'delete')
        
        logger.info(f"Position {position_id} deleted")
        return True
    
    async def get_position_by_id(self, position_id: str, user_id: str) -> Optional[Position]:
        """Get a specific position by ID."""
        try:
            if self.db is not None:
                query = """
                    SELECT * FROM user_positions 
                    WHERE id = %(id)s AND user_id = %(user_id)s
                    LIMIT 1
                """
                df = self.db.execute_query(query, {'id': position_id, 'user_id': user_id})
                if not df.empty:
                    row = df.iloc[0]
                    return Position(
                        id=str(row['id']),
                        user_id=str(row['user_id']),
                        ts_code=row['ts_code'],
                        stock_name=row['stock_name'],
                        quantity=int(row['quantity']),
                        cost_price=float(row['cost_price']),
                        buy_date=str(row['buy_date']),
                        current_price=float(row['current_price']) if pd.notna(row['current_price']) else None,
                        market_value=float(row['market_value']) if pd.notna(row['market_value']) else None,
                        profit_loss=float(row['profit_loss']) if pd.notna(row['profit_loss']) else None,
                        profit_rate=float(row['profit_rate']) if pd.notna(row['profit_rate']) else None,
                        notes=row['notes'] if pd.notna(row['notes']) else None,
                        sector=row['sector'] if pd.notna(row['sector']) else None,
                        industry=row['industry'] if pd.notna(row['industry']) else None,
                        is_active=bool(row['is_active']),
                        created_at=row['created_at'] if pd.notna(row['created_at']) else None,
                        updated_at=row['updated_at'] if pd.notna(row['updated_at']) else None
                    )
        except Exception as e:
            logger.warning(f"Failed to get position from database: {e}")
        
        # Fallback to in-memory storage
        return self._positions.get(position_id)
    
    async def get_summary(self, user_id: str = "default_user") -> PortfolioSummary:
        """Get enhanced portfolio summary."""
        positions = await self.get_positions(user_id)
        
        if not positions:
            return PortfolioSummary(
                total_value=0.0, total_cost=0.0, total_profit=0.0,
                profit_rate=0.0, daily_change=0.0, daily_change_rate=0.0,
                position_count=0
            )
        
        total_cost = sum(p.quantity * p.cost_price for p in positions)
        total_value = sum(p.market_value or 0 for p in positions)
        total_profit = total_value - total_cost
        profit_rate = (total_profit / total_cost * 100) if total_cost > 0 else 0
        
        # Calculate daily change (mock for now)
        daily_change = total_value * 0.01  # 1% mock change
        daily_change_rate = 1.0
        
        # Find top and worst performers
        performers = [(p.ts_code, p.profit_rate or 0) for p in positions if p.profit_rate is not None]
        performers.sort(key=lambda x: x[1])
        
        top_performer = performers[-1][0] if performers else None
        worst_performer = performers[0][0] if performers else None
        
        # Calculate sector distribution
        sector_distribution = {}
        for position in positions:
            sector = position.sector or "未分类"
            value = position.market_value or 0
            sector_distribution[sector] = sector_distribution.get(sector, 0) + value
        
        # Normalize to percentages
        if total_value > 0:
            sector_distribution = {k: v/total_value*100 for k, v in sector_distribution.items()}
        
        return PortfolioSummary(
            total_value=total_value,
            total_cost=total_cost,
            total_profit=total_profit,
            profit_rate=profit_rate,
            daily_change=daily_change,
            daily_change_rate=daily_change_rate,
            position_count=len(positions),
            top_performer=top_performer,
            worst_performer=worst_performer,
            sector_distribution=sector_distribution
        )
    
    async def batch_update_prices(self, user_id: str = "default_user") -> int:
        """Batch update all position prices."""
        positions = await self.get_positions(user_id)
        updated_count = 0
        
        for position in positions:
            old_price = position.current_price
            await self._update_position_prices(position)
            
            if position.current_price != old_price:
                await self._save_position(position)
                await self._record_position_history(position, 'price_update')
                updated_count += 1
        
        logger.info(f"Updated prices for {updated_count} positions")
        return updated_count
    
    async def get_profit_history(self, user_id: str = "default_user", 
                                days: int = 30) -> List[Dict[str, Any]]:
        """Get profit history for the last N days."""
        try:
            if self.db is not None:
                query = """
                    SELECT 
                        record_date,
                        sum(market_value) as total_value,
                        sum(quantity * cost_price) as total_cost,
                        sum(profit_loss) as total_profit
                    FROM position_history
                    WHERE user_id = %(user_id)s 
                    AND record_date >= today() - %(days)s
                    GROUP BY record_date
                    ORDER BY record_date
                """
                df = self.db.execute_query(query, {'user_id': user_id, 'days': days})
                
                if not df.empty:
                    return df.to_dict('records')
        except Exception as e:
            logger.warning(f"Failed to get profit history: {e}")
        
        # Return mock data
        return [
            {
                'record_date': '2024-01-01',
                'total_value': 180000.0,
                'total_cost': 170000.0,
                'total_profit': 10000.0
            }
        ]
    
    # Alert management methods
    async def create_alert(self, user_id: str, position_id: str, ts_code: str,
                          alert_type: str, condition_value: float, 
                          message: str = "") -> PositionAlert:
        """Create a new position alert."""
        alert_id = str(uuid.uuid4())
        
        alert = PositionAlert(
            id=alert_id,
            user_id=user_id,
            position_id=position_id,
            ts_code=ts_code,
            alert_type=alert_type,
            condition_value=condition_value,
            current_value=0.0,
            message=message,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        self._alerts[alert_id] = alert
        logger.info(f"Alert {alert_id} created for {ts_code}")
        return alert
    
    async def check_alerts(self, user_id: str = "default_user") -> List[PositionAlert]:
        """Check all active alerts and return triggered ones."""
        triggered_alerts = []
        
        for alert in self._alerts.values():
            if not alert.is_active or alert.user_id != user_id:
                continue
            
            # Get current position data
            position = await self.get_position_by_id(alert.position_id, user_id)
            if not position or not position.current_price:
                continue
            
            alert.current_value = position.current_price
            
            # Check alert conditions
            is_triggered = False
            if alert.alert_type == 'price_high' and position.current_price >= alert.condition_value:
                is_triggered = True
            elif alert.alert_type == 'price_low' and position.current_price <= alert.condition_value:
                is_triggered = True
            elif alert.alert_type == 'profit_target' and (position.profit_rate or 0) >= alert.condition_value:
                is_triggered = True
            elif alert.alert_type == 'stop_loss' and (position.profit_rate or 0) <= alert.condition_value:
                is_triggered = True
            
            if is_triggered and not alert.is_triggered:
                alert.is_triggered = True
                alert.trigger_count += 1
                alert.last_triggered = datetime.now()
                alert.updated_at = datetime.now()
                triggered_alerts.append(alert)
        
        return triggered_alerts
    
    # Private helper methods
    async def _get_stock_info(self, ts_code: str) -> Tuple[str, str, str]:
        """Get stock name, sector and industry."""
        try:
            if self.db is not None:
                query = """
                    SELECT name, industry, area FROM ods_stock_basic 
                    WHERE ts_code = %(code)s
                    LIMIT 1
                """
                df = self.db.execute_query(query, {'code': ts_code})
                if not df.empty:
                    row = df.iloc[0]
                    return (
                        row['name'],
                        row.get('area', '未知'),
                        row.get('industry', '未知')
                    )
        except Exception as e:
            logger.warning(f"Failed to get stock info from database: {e}")
        
        # Fallback to mock data
        stock_info = {
            '600519.SH': ('贵州茅台', '消费品', '白酒'),
            '000001.SZ': ('平安银行', '金融', '银行'),
            '000002.SZ': ('万科A', '房地产', '房地产开发'),
            '600036.SH': ('招商银行', '金融', '银行'),
            '000858.SZ': ('五粮液', '消费品', '白酒')
        }
        return stock_info.get(ts_code, (f"股票{ts_code}", "未知", "未知"))
    
    async def _update_position_prices(self, position: Position):
        """Update position current price and calculations."""
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
                    position.last_price_update = datetime.now()
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
            position.last_price_update = datetime.now()
        
        # Calculate market value and profit/loss
        if position.current_price:
            position.market_value = position.quantity * position.current_price
            cost_total = position.quantity * position.cost_price
            position.profit_loss = position.market_value - cost_total
            position.profit_rate = (position.profit_loss / cost_total * 100) if cost_total > 0 else 0
    
    async def _save_position(self, position: Position):
        """Save position to database and memory."""
        try:
            if self.db is not None:
                # Save to database (using ReplacingMergeTree for upsert)
                query = """
                    INSERT INTO user_positions 
                    (id, user_id, ts_code, stock_name, quantity, cost_price, buy_date, 
                     current_price, market_value, profit_loss, profit_rate, notes,
                     sector, industry, last_price_update, is_active, created_at, updated_at)
                    VALUES (%(id)s, %(user_id)s, %(ts_code)s, %(stock_name)s, %(quantity)s, 
                            %(cost_price)s, %(buy_date)s, %(current_price)s, %(market_value)s, 
                            %(profit_loss)s, %(profit_rate)s, %(notes)s, %(sector)s, 
                            %(industry)s, %(last_price_update)s, %(is_active)s, 
                            %(created_at)s, %(updated_at)s)
                """
                params = asdict(position)
                self.db.execute(query, params)
        except Exception as e:
            logger.warning(f"Failed to save position to database: {e}")
        
        # Always save to in-memory storage as backup
        self._positions[position.id] = position
    
    async def _record_position_history(self, position: Position, change_type: str):
        """Record position change in history table."""
        try:
            if self.db is not None:
                history_id = str(uuid.uuid4())
                query = """
                    INSERT INTO position_history
                    (id, position_id, user_id, ts_code, stock_name, quantity, cost_price,
                     current_price, market_value, profit_loss, profit_rate, record_date,
                     record_time, change_type, created_at)
                    VALUES (%(id)s, %(position_id)s, %(user_id)s, %(ts_code)s, %(stock_name)s,
                            %(quantity)s, %(cost_price)s, %(current_price)s, %(market_value)s,
                            %(profit_loss)s, %(profit_rate)s, %(record_date)s, %(record_time)s,
                            %(change_type)s, %(created_at)s)
                """
                params = {
                    'id': history_id,
                    'position_id': position.id,
                    'user_id': position.user_id,
                    'ts_code': position.ts_code,
                    'stock_name': position.stock_name,
                    'quantity': position.quantity,
                    'cost_price': position.cost_price,
                    'current_price': position.current_price,
                    'market_value': position.market_value,
                    'profit_loss': position.profit_loss,
                    'profit_rate': position.profit_rate,
                    'record_date': date.today(),
                    'record_time': datetime.now(),
                    'change_type': change_type,
                    'created_at': datetime.now()
                }
                self.db.execute(query, params)
        except Exception as e:
            logger.warning(f"Failed to record position history: {e}")
    
    async def _batch_update_positions(self, positions: List[Position]):
        """Batch update positions in database with latest prices."""
        if not self.db or not positions:
            return
        
        try:
            for position in positions:
                await self._save_position(position)
            
            logger.info(f"Batch updated {len(positions)} positions")
            
        except Exception as e:
            logger.warning(f"Failed to batch update positions: {e}")


# Global service instance
_enhanced_portfolio_service = None


def get_enhanced_portfolio_service() -> EnhancedPortfolioService:
    """Get enhanced portfolio service instance."""
    global _enhanced_portfolio_service
    if _enhanced_portfolio_service is None:
        _enhanced_portfolio_service = EnhancedPortfolioService()
    return _enhanced_portfolio_service