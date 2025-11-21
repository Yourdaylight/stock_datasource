"""Trade calendar manager - prioritize CSV reading over API calls."""

import logging
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class TradeCalendarManager:
    """Manage trade calendar data with CSV caching."""
    
    def __init__(self, csv_path: Optional[str] = None):
        """Initialize trade calendar manager.
        
        Args:
            csv_path: Path to trade_calendar.csv file. If None, use default location.
        """
        if csv_path is None:
            # Default to config/trade_calendar.csv
            csv_path = Path(__file__).parent.parent / "config" / "trade_calendar.csv"
        
        self.csv_path = Path(csv_path)
        self._cache = None
        self._cache_loaded = False
        
        if not self.csv_path.exists():
            logger.warning(f"Trade calendar CSV not found at {self.csv_path}")
    
    def _load_csv(self) -> pd.DataFrame:
        """Load trade calendar from CSV file."""
        if self._cache_loaded and self._cache is not None:
            return self._cache
        
        try:
            df = pd.read_csv(self.csv_path)
            # Ensure cal_date is string format YYYYMMDD
            if 'cal_date' in df.columns:
                df['cal_date'] = df['cal_date'].astype(str)
            
            self._cache = df
            self._cache_loaded = True
            logger.info(f"Loaded {len(df)} records from trade calendar CSV")
            return df
            
        except Exception as e:
            logger.error(f"Failed to load trade calendar CSV: {e}")
            return pd.DataFrame()
    
    def get_latest_date_in_csv(self) -> Optional[str]:
        """Get the latest date available in CSV.
        
        Returns:
            Latest date in YYYYMMDD format, or None if CSV is empty
        """
        df = self._load_csv()
        if df.empty:
            return None
        
        # Find the latest date
        latest = df['cal_date'].max()
        return str(latest)
    
    def is_csv_up_to_date(self, target_date: Optional[str] = None) -> bool:
        """Check if CSV contains data up to target date.
        
        Args:
            target_date: Date to check in YYYYMMDD format. If None, use today.
        
        Returns:
            True if CSV is up to date, False otherwise
        """
        if target_date is None:
            target_date = datetime.now().strftime("%Y%m%d")
        
        latest = self.get_latest_date_in_csv()
        if latest is None:
            return False
        
        # CSV is up to date if latest date >= target date
        return latest >= target_date
    
    def get_trade_calendar(self, start_date: str, end_date: str, 
                          exchange: str = "SSE") -> pd.DataFrame:
        """Get trade calendar from CSV.
        
        Args:
            start_date: Start date in YYYYMMDD or YYYY-MM-DD format
            end_date: End date in YYYYMMDD or YYYY-MM-DD format
            exchange: Exchange code (SSE/SZSE)
        
        Returns:
            DataFrame with trade calendar data
        """
        # Normalize date format to YYYYMMDD
        start_date_norm = start_date.replace('-', '')
        end_date_norm = end_date.replace('-', '')
        
        df = self._load_csv()
        if df.empty:
            logger.warning("Trade calendar CSV is empty")
            return pd.DataFrame()
        
        # Filter by exchange and date range
        filtered = df[
            (df['exchange'] == exchange) &
            (df['cal_date'] >= start_date_norm) &
            (df['cal_date'] <= end_date_norm)
        ].copy()
        
        logger.info(f"Retrieved {len(filtered)} records from CSV for {start_date} to {end_date}")
        return filtered
    
    def get_trading_days(self, start_date: str, end_date: str,
                        exchange: str = "SSE") -> pd.DataFrame:
        """Get trading days only (is_open=1) from CSV.
        
        Args:
            start_date: Start date in YYYYMMDD or YYYY-MM-DD format
            end_date: End date in YYYYMMDD or YYYY-MM-DD format
            exchange: Exchange code (SSE/SZSE)
        
        Returns:
            DataFrame with trading days only
        """
        df = self.get_trade_calendar(start_date, end_date, exchange)
        if df.empty:
            return df
        
        # Filter for trading days only
        trading_days = df[df['is_open'] == 1].copy()
        logger.info(f"Found {len(trading_days)} trading days")
        return trading_days
    
    def is_trading_day(self, date: str, exchange: str = "SSE") -> bool:
        """Check if a date is a trading day.
        
        Args:
            date: Date in YYYYMMDD or YYYY-MM-DD format
            exchange: Exchange code (SSE/SZSE)
        
        Returns:
            True if it's a trading day, False otherwise
        """
        df = self.get_trade_calendar(date, date, exchange)
        if df.empty:
            return False
        
        return bool(df.iloc[0]['is_open'] == 1)
    
    def get_next_trading_day(self, date: str, exchange: str = "SSE") -> Optional[str]:
        """Get next trading day after given date.
        
        Args:
            date: Reference date in YYYYMMDD or YYYY-MM-DD format
            exchange: Exchange code (SSE/SZSE)
        
        Returns:
            Next trading day in YYYYMMDD format, or None if not found
        """
        date_norm = date.replace('-', '')
        df = self._load_csv()
        
        if df.empty:
            return None
        
        # Filter for dates after the given date and is_open=1
        next_days = df[
            (df['exchange'] == exchange) &
            (df['cal_date'] > date_norm) &
            (df['is_open'] == 1)
        ].sort_values('cal_date')
        
        if next_days.empty:
            return None
        
        return str(next_days.iloc[0]['cal_date'])
    
    def get_prev_trading_day(self, date: str, exchange: str = "SSE") -> Optional[str]:
        """Get previous trading day before given date.
        
        Args:
            date: Reference date in YYYYMMDD or YYYY-MM-DD format
            exchange: Exchange code (SSE/SZSE)
        
        Returns:
            Previous trading day in YYYYMMDD format, or None if not found
        """
        date_norm = date.replace('-', '')
        df = self._load_csv()
        
        if df.empty:
            return None
        
        # Filter for dates before the given date and is_open=1
        prev_days = df[
            (df['exchange'] == exchange) &
            (df['cal_date'] < date_norm) &
            (df['is_open'] == 1)
        ].sort_values('cal_date', ascending=False)
        
        if prev_days.empty:
            return None
        
        return str(prev_days.iloc[0]['cal_date'])


# Global instance for easy access
_global_manager = None


def get_trade_calendar_manager(csv_path: Optional[str] = None) -> TradeCalendarManager:
    """Get global trade calendar manager instance.
    
    Args:
        csv_path: Path to CSV file. If None, use default location.
    
    Returns:
        TradeCalendarManager instance
    """
    global _global_manager
    if _global_manager is None:
        _global_manager = TradeCalendarManager(csv_path)
    return _global_manager
