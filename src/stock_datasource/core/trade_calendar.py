"""Global trade calendar service for unified trading day queries."""

from datetime import datetime, date, timedelta
from typing import List, Optional, Union
from pathlib import Path
import pandas as pd

from stock_datasource.utils.logger import logger


class TradeCalendarError(Exception):
    """Base exception for trade calendar errors."""
    pass


class CalendarNotFoundError(TradeCalendarError):
    """Trade calendar file not found."""
    pass


class InvalidDateError(TradeCalendarError):
    """Invalid date provided."""
    pass


class TradeCalendarService:
    """Global trade calendar service (Singleton pattern).
    
    Provides unified trading day queries from config/trade_calendar.csv.
    The calendar data is loaded into memory at startup for fast queries.
    
    Usage:
        from stock_datasource.core import trade_calendar_service
        
        # Get recent trading days
        days = trade_calendar_service.get_trading_days(30)
        
        # Check if a date is a trading day
        is_open = trade_calendar_service.is_trading_day('2026-01-13')
        
        # Get previous/next trading day
        prev_day = trade_calendar_service.get_prev_trading_day('2026-01-13')
        next_day = trade_calendar_service.get_next_trading_day('2026-01-13')
    """
    
    _instance = None
    _calendar_df: Optional[pd.DataFrame] = None
    _trading_days_set: Optional[set] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self.logger = logger.bind(component="TradeCalendarService")
        self._load_calendar()
        self._initialized = True
    
    def _get_calendar_path(self) -> Path:
        """Get the path to trade_calendar.csv in config directory."""
        # Try config directory first
        config_path = Path(__file__).parent.parent / "config" / "trade_calendar.csv"
        if config_path.exists():
            return config_path
        
        # Fallback to datamanage directory (for backward compatibility)
        fallback_path = Path(__file__).parent.parent / "modules" / "datamanage" / "trade_calendar.csv"
        if fallback_path.exists():
            return fallback_path
        
        raise CalendarNotFoundError(
            f"Trade calendar file not found. Expected at: {config_path}"
        )
    
    def _load_calendar(self):
        """Load trade calendar from CSV file into memory."""
        try:
            calendar_path = self._get_calendar_path()
            
            self._calendar_df = pd.read_csv(
                calendar_path,
                parse_dates=['cal_date']
            )
            
            # Ensure cal_date is datetime
            if not pd.api.types.is_datetime64_any_dtype(self._calendar_df['cal_date']):
                self._calendar_df['cal_date'] = pd.to_datetime(self._calendar_df['cal_date'])
            
            # Sort by date descending for efficient recent day queries
            self._calendar_df = self._calendar_df.sort_values('cal_date', ascending=False)
            
            # Build set of trading days for O(1) lookup
            trading_days = self._calendar_df[self._calendar_df['is_open'] == 1]['cal_date']
            self._trading_days_set = set(trading_days.dt.strftime('%Y-%m-%d').tolist())
            
            self.logger.info(
                f"Loaded trade calendar: {len(self._calendar_df)} total days, "
                f"{len(self._trading_days_set)} trading days"
            )
            
        except CalendarNotFoundError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to load trade calendar: {e}")
            raise TradeCalendarError(f"Failed to load trade calendar: {e}")
    
    def _normalize_date(self, date_input: Union[str, date, datetime]) -> str:
        """Normalize date input to YYYY-MM-DD string format.
        
        Args:
            date_input: Date in various formats (str, date, datetime)
        
        Returns:
            Date string in YYYY-MM-DD format
        
        Raises:
            InvalidDateError: If date format is invalid
        """
        if isinstance(date_input, datetime):
            return date_input.strftime('%Y-%m-%d')
        elif isinstance(date_input, date):
            return date_input.strftime('%Y-%m-%d')
        elif isinstance(date_input, str):
            # Handle YYYYMMDD format
            if len(date_input) == 8 and date_input.isdigit():
                return f"{date_input[:4]}-{date_input[4:6]}-{date_input[6:]}"
            # Validate YYYY-MM-DD format
            try:
                datetime.strptime(date_input, '%Y-%m-%d')
                return date_input
            except ValueError:
                raise InvalidDateError(f"Invalid date format: {date_input}. Expected YYYY-MM-DD or YYYYMMDD")
        else:
            raise InvalidDateError(f"Invalid date type: {type(date_input)}")
    
    def get_trading_days(
        self, 
        n: int = 30, 
        end_date: Optional[Union[str, date, datetime]] = None
    ) -> List[str]:
        """Get the most recent n trading days.
        
        Args:
            n: Number of trading days to retrieve
            end_date: End date (default: today). Can be str, date, or datetime.
        
        Returns:
            List of trading dates in YYYY-MM-DD format, sorted descending (most recent first)
        """
        if self._calendar_df is None:
            self.logger.warning("Calendar not loaded")
            return []
        
        try:
            if end_date is None:
                end_ts = pd.Timestamp.now().normalize()
            else:
                end_str = self._normalize_date(end_date)
                end_ts = pd.Timestamp(end_str)
            
            # Filter trading days up to end_date
            mask = (self._calendar_df['is_open'] == 1) & (self._calendar_df['cal_date'] <= end_ts)
            trading_days = self._calendar_df[mask].head(n)['cal_date']
            
            return [d.strftime('%Y-%m-%d') for d in trading_days]
            
        except Exception as e:
            self.logger.error(f"Failed to get trading days: {e}")
            return []
    
    def is_trading_day(self, date_input: Union[str, date, datetime]) -> bool:
        """Check if a date is a trading day.
        
        Args:
            date_input: Date to check
        
        Returns:
            True if the date is a trading day, False otherwise
        """
        if self._trading_days_set is None:
            return False
        
        try:
            date_str = self._normalize_date(date_input)
            return date_str in self._trading_days_set
        except InvalidDateError:
            return False
    
    def get_prev_trading_day(
        self, 
        date_input: Union[str, date, datetime]
    ) -> Optional[str]:
        """Get the previous trading day before the given date.
        
        Args:
            date_input: Reference date
        
        Returns:
            Previous trading day in YYYY-MM-DD format, or None if not found
        """
        if self._calendar_df is None:
            return None
        
        try:
            date_str = self._normalize_date(date_input)
            date_ts = pd.Timestamp(date_str)
            
            # Find trading days before this date
            mask = (self._calendar_df['is_open'] == 1) & (self._calendar_df['cal_date'] < date_ts)
            prev_days = self._calendar_df[mask]
            
            if prev_days.empty:
                return None
            
            # Get the most recent one (already sorted descending)
            return prev_days.iloc[0]['cal_date'].strftime('%Y-%m-%d')
            
        except Exception as e:
            self.logger.error(f"Failed to get previous trading day: {e}")
            return None
    
    def get_next_trading_day(
        self, 
        date_input: Union[str, date, datetime]
    ) -> Optional[str]:
        """Get the next trading day after the given date.
        
        Args:
            date_input: Reference date
        
        Returns:
            Next trading day in YYYY-MM-DD format, or None if not found
        """
        if self._calendar_df is None:
            return None
        
        try:
            date_str = self._normalize_date(date_input)
            date_ts = pd.Timestamp(date_str)
            
            # Find trading days after this date
            mask = (self._calendar_df['is_open'] == 1) & (self._calendar_df['cal_date'] > date_ts)
            next_days = self._calendar_df[mask]
            
            if next_days.empty:
                return None
            
            # Get the earliest one (data is sorted descending, so get last)
            return next_days.iloc[-1]['cal_date'].strftime('%Y-%m-%d')
            
        except Exception as e:
            self.logger.error(f"Failed to get next trading day: {e}")
            return None
    
    def get_trading_days_between(
        self, 
        start_date: Union[str, date, datetime],
        end_date: Union[str, date, datetime]
    ) -> List[str]:
        """Get all trading days between two dates (inclusive).
        
        Args:
            start_date: Start date
            end_date: End date
        
        Returns:
            List of trading dates in YYYY-MM-DD format, sorted ascending
        """
        if self._calendar_df is None:
            return []
        
        try:
            start_str = self._normalize_date(start_date)
            end_str = self._normalize_date(end_date)
            
            start_ts = pd.Timestamp(start_str)
            end_ts = pd.Timestamp(end_str)
            
            # Filter trading days within range
            mask = (
                (self._calendar_df['is_open'] == 1) & 
                (self._calendar_df['cal_date'] >= start_ts) & 
                (self._calendar_df['cal_date'] <= end_ts)
            )
            trading_days = self._calendar_df[mask]['cal_date'].sort_values()
            
            return [d.strftime('%Y-%m-%d') for d in trading_days]
            
        except Exception as e:
            self.logger.error(f"Failed to get trading days between dates: {e}")
            return []
    
    def get_trading_day_offset(
        self,
        date_input: Union[str, date, datetime],
        offset: int
    ) -> Optional[str]:
        """Get a trading day with offset from the given date.
        
        Args:
            date_input: Reference date
            offset: Number of trading days to offset (positive for future, negative for past)
        
        Returns:
            Trading day in YYYY-MM-DD format, or None if not found
        """
        if self._calendar_df is None:
            return None
        
        try:
            date_str = self._normalize_date(date_input)
            date_ts = pd.Timestamp(date_str)
            
            if offset == 0:
                # Return the same day if it's a trading day, otherwise the previous
                if self.is_trading_day(date_str):
                    return date_str
                return self.get_prev_trading_day(date_str)
            
            elif offset > 0:
                # Get future trading days
                mask = (self._calendar_df['is_open'] == 1) & (self._calendar_df['cal_date'] > date_ts)
                future_days = self._calendar_df[mask].sort_values('cal_date')
                
                if len(future_days) >= offset:
                    return future_days.iloc[offset - 1]['cal_date'].strftime('%Y-%m-%d')
                return None
            
            else:  # offset < 0
                # Get past trading days
                mask = (self._calendar_df['is_open'] == 1) & (self._calendar_df['cal_date'] < date_ts)
                past_days = self._calendar_df[mask]  # Already sorted descending
                
                abs_offset = abs(offset)
                if len(past_days) >= abs_offset:
                    return past_days.iloc[abs_offset - 1]['cal_date'].strftime('%Y-%m-%d')
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get trading day with offset: {e}")
            return None
    
    def refresh_calendar(self) -> bool:
        """Refresh trade calendar from TuShare API.
        
        This method fetches the latest trade calendar from TuShare
        and updates the local CSV file.
        
        Returns:
            True if refresh successful, False otherwise
        """
        try:
            import tushare as ts
            import os
            
            # Get TuShare token
            from stock_datasource.config.settings import settings
            token = getattr(settings, 'tushare_token', None)
            if not token:
                token = os.environ.get('TUSHARE_TOKEN')
            
            if not token:
                self.logger.error("TuShare token not configured, cannot refresh calendar")
                return False
            
            pro = ts.pro_api(token)
            
            # Fetch trade calendar from 2000 to 2030
            self.logger.info("Fetching trade calendar from TuShare API (2000-2030)...")
            df = pro.trade_cal(
                exchange='SSE',
                start_date='20000101',
                end_date='20301231'
            )
            
            if df is None or df.empty:
                self.logger.error("Failed to fetch trade calendar from TuShare")
                return False
            
            # Rename and convert columns
            df = df.rename(columns={'cal_date': 'cal_date_str'})
            df['cal_date'] = pd.to_datetime(df['cal_date_str'], format='%Y%m%d')
            df = df[['cal_date', 'is_open', 'pretrade_date']]
            
            # Sort by date descending
            df = df.sort_values('cal_date', ascending=False)
            
            # Save to config directory
            calendar_path = Path(__file__).parent.parent / "config" / "trade_calendar.csv"
            df.to_csv(calendar_path, index=False)
            
            # Reload into memory
            self._calendar_df = df
            trading_days = df[df['is_open'] == 1]['cal_date']
            self._trading_days_set = set(trading_days.dt.strftime('%Y-%m-%d').tolist())
            
            self.logger.info(
                f"Refreshed trade calendar: {len(df)} total days, "
                f"{len(self._trading_days_set)} trading days"
            )
            return True
            
        except ImportError:
            self.logger.error("TuShare not installed, cannot refresh calendar")
            return False
        except Exception as e:
            self.logger.error(f"Failed to refresh trade calendar: {e}")
            return False
    
    @property
    def calendar_loaded(self) -> bool:
        """Check if calendar data is loaded."""
        return self._calendar_df is not None and not self._calendar_df.empty
    
    @property
    def total_days(self) -> int:
        """Get total number of days in calendar."""
        if self._calendar_df is None:
            return 0
        return len(self._calendar_df)
    
    @property
    def total_trading_days(self) -> int:
        """Get total number of trading days in calendar."""
        if self._trading_days_set is None:
            return 0
        return len(self._trading_days_set)
    
    @property
    def date_range(self) -> tuple:
        """Get the date range of the calendar.
        
        Returns:
            Tuple of (start_date, end_date) in YYYY-MM-DD format
        """
        if self._calendar_df is None or self._calendar_df.empty:
            return (None, None)
        
        min_date = self._calendar_df['cal_date'].min()
        max_date = self._calendar_df['cal_date'].max()
        
        return (
            min_date.strftime('%Y-%m-%d'),
            max_date.strftime('%Y-%m-%d')
        )


# Global singleton instance
trade_calendar_service = TradeCalendarService()
