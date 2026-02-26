"""Global trade calendar service for unified trading day queries.

Supports both A-share (SSE) and HK stock exchange calendars.
"""

from datetime import datetime, date, timedelta
from typing import List, Optional, Union
from pathlib import Path
import pandas as pd

from stock_datasource.utils.logger import logger


# Market type constants
MARKET_CN = "cn"  # A股 (SSE/SZSE)
MARKET_HK = "hk"  # 港股 (HKEX)


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
    
    Provides unified trading day queries from config/trade_calendar.csv (A-share)
    and config/hk_trade_calendar.csv (HK stock).
    The calendar data is loaded into memory at startup for fast queries.
    
    Usage:
        from stock_datasource.core import trade_calendar_service
        
        # A-share (default)
        days = trade_calendar_service.get_trading_days(30)
        is_open = trade_calendar_service.is_trading_day('2026-01-13')
        
        # HK stock
        is_open_hk = trade_calendar_service.is_trading_day('2026-01-13', market='hk')
        days_hk = trade_calendar_service.get_trading_days(30, market='hk')
    """
    
    _instance = None
    _calendar_df: Optional[pd.DataFrame] = None
    _trading_days_set: Optional[set] = None
    # HK calendar
    _hk_calendar_df: Optional[pd.DataFrame] = None
    _hk_trading_days_set: Optional[set] = None
    
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
        self._load_hk_calendar()
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
    
    def _get_hk_calendar_path(self) -> Path:
        """Get the path to hk_trade_calendar.csv in config directory."""
        config_path = Path(__file__).parent.parent / "config" / "hk_trade_calendar.csv"
        if config_path.exists():
            return config_path
        raise CalendarNotFoundError(
            f"HK trade calendar file not found. Expected at: {config_path}"
        )
    
    def _load_calendar(self):
        """Load A-share trade calendar from CSV file into memory."""
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
                f"Loaded A-share trade calendar: {len(self._calendar_df)} total days, "
                f"{len(self._trading_days_set)} trading days"
            )
            
        except CalendarNotFoundError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to load trade calendar: {e}")
            raise TradeCalendarError(f"Failed to load trade calendar: {e}")
    
    def _load_hk_calendar(self):
        """Load HK stock trade calendar from CSV file into memory.
        
        If the CSV file does not exist, automatically fetches from TuShare API.
        """
        try:
            hk_path = self._get_hk_calendar_path()
            self._load_hk_calendar_from_csv(hk_path)
        except CalendarNotFoundError:
            self.logger.warning("HK trade calendar CSV not found, fetching from TuShare API...")
            try:
                success = self.refresh_calendar(MARKET_HK)
                if not success:
                    self.logger.error(
                        "Failed to fetch HK trade calendar from TuShare API. "
                        "HK market trading day queries will be unavailable."
                    )
                    self._hk_calendar_df = None
                    self._hk_trading_days_set = None
            except Exception as e:
                self.logger.error(
                    f"Failed to fetch HK trade calendar from TuShare API: {e}. "
                    "HK market trading day queries will be unavailable."
                )
                self._hk_calendar_df = None
                self._hk_trading_days_set = None
        except Exception as e:
            self.logger.error(f"Failed to load HK trade calendar: {e}")
            self._hk_calendar_df = None
            self._hk_trading_days_set = None
    
    def _load_hk_calendar_from_csv(self, hk_path: Path):
        """Load HK calendar data from a CSV file path."""
        self._hk_calendar_df = pd.read_csv(
            hk_path,
            parse_dates=['cal_date']
        )
        
        if not pd.api.types.is_datetime64_any_dtype(self._hk_calendar_df['cal_date']):
            self._hk_calendar_df['cal_date'] = pd.to_datetime(self._hk_calendar_df['cal_date'])
        
        self._hk_calendar_df = self._hk_calendar_df.sort_values('cal_date', ascending=False)
        
        trading_days = self._hk_calendar_df[self._hk_calendar_df['is_open'] == 1]['cal_date']
        self._hk_trading_days_set = set(trading_days.dt.strftime('%Y-%m-%d').tolist())
        
        self.logger.info(
            f"Loaded HK trade calendar: {len(self._hk_calendar_df)} total days, "
            f"{len(self._hk_trading_days_set)} trading days"
        )
    
    def _get_df(self, market: str = MARKET_CN) -> Optional[pd.DataFrame]:
        """Get the calendar DataFrame for the given market."""
        if market == MARKET_HK:
            return self._hk_calendar_df
        return self._calendar_df
    
    def _get_trading_set(self, market: str = MARKET_CN) -> Optional[set]:
        """Get the trading days set for the given market."""
        if market == MARKET_HK:
            return self._hk_trading_days_set
        return self._trading_days_set
    
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
        end_date: Optional[Union[str, date, datetime]] = None,
        market: str = MARKET_CN
    ) -> List[str]:
        """Get the most recent n trading days.
        
        Args:
            n: Number of trading days to retrieve
            end_date: End date (default: today). Can be str, date, or datetime.
            market: Market type - 'cn' for A-share (default), 'hk' for HK stock
        
        Returns:
            List of trading dates in YYYY-MM-DD format, sorted descending (most recent first)
        """
        df = self._get_df(market)
        if df is None:
            self.logger.warning("Calendar not loaded")
            return []
        
        try:
            if end_date is None:
                end_ts = pd.Timestamp.now().normalize()
            else:
                end_str = self._normalize_date(end_date)
                end_ts = pd.Timestamp(end_str)
            
            # Filter trading days up to end_date
            mask = (df['is_open'] == 1) & (df['cal_date'] <= end_ts)
            trading_days = df[mask].head(n)['cal_date']
            
            return [d.strftime('%Y-%m-%d') for d in trading_days]
            
        except Exception as e:
            self.logger.error(f"Failed to get trading days: {e}")
            return []
    
    def is_trading_day(
        self, 
        date_input: Union[str, date, datetime],
        market: str = MARKET_CN
    ) -> bool:
        """Check if a date is a trading day.
        
        Args:
            date_input: Date to check
            market: Market type - 'cn' for A-share (default), 'hk' for HK stock
        
        Returns:
            True if the date is a trading day, False otherwise
        """
        trading_set = self._get_trading_set(market)
        if trading_set is None:
            return False
        
        try:
            date_str = self._normalize_date(date_input)
            return date_str in trading_set
        except InvalidDateError:
            return False
    
    def get_prev_trading_day(
        self, 
        date_input: Union[str, date, datetime],
        market: str = MARKET_CN
    ) -> Optional[str]:
        """Get the previous trading day before the given date.
        
        Args:
            date_input: Reference date
            market: Market type - 'cn' for A-share (default), 'hk' for HK stock
        
        Returns:
            Previous trading day in YYYY-MM-DD format, or None if not found
        """
        df = self._get_df(market)
        if df is None:
            return None
        
        try:
            date_str = self._normalize_date(date_input)
            date_ts = pd.Timestamp(date_str)
            
            # Find trading days before this date
            mask = (df['is_open'] == 1) & (df['cal_date'] < date_ts)
            prev_days = df[mask]
            
            if prev_days.empty:
                return None
            
            # Get the most recent one (already sorted descending)
            return prev_days.iloc[0]['cal_date'].strftime('%Y-%m-%d')
            
        except Exception as e:
            self.logger.error(f"Failed to get previous trading day: {e}")
            return None
    
    def get_next_trading_day(
        self, 
        date_input: Union[str, date, datetime],
        market: str = MARKET_CN
    ) -> Optional[str]:
        """Get the next trading day after the given date.
        
        Args:
            date_input: Reference date
            market: Market type - 'cn' for A-share (default), 'hk' for HK stock
        
        Returns:
            Next trading day in YYYY-MM-DD format, or None if not found
        """
        df = self._get_df(market)
        if df is None:
            return None
        
        try:
            date_str = self._normalize_date(date_input)
            date_ts = pd.Timestamp(date_str)
            
            # Find trading days after this date
            mask = (df['is_open'] == 1) & (df['cal_date'] > date_ts)
            next_days = df[mask]
            
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
        end_date: Union[str, date, datetime],
        market: str = MARKET_CN
    ) -> List[str]:
        """Get all trading days between two dates (inclusive).
        
        Args:
            start_date: Start date
            end_date: End date
            market: Market type - 'cn' for A-share (default), 'hk' for HK stock
        
        Returns:
            List of trading dates in YYYY-MM-DD format, sorted ascending
        """
        df = self._get_df(market)
        if df is None:
            return []
        
        try:
            start_str = self._normalize_date(start_date)
            end_str = self._normalize_date(end_date)
            
            start_ts = pd.Timestamp(start_str)
            end_ts = pd.Timestamp(end_str)
            
            # Filter trading days within range
            mask = (
                (df['is_open'] == 1) & 
                (df['cal_date'] >= start_ts) & 
                (df['cal_date'] <= end_ts)
            )
            trading_days = df[mask]['cal_date'].sort_values()
            
            return [d.strftime('%Y-%m-%d') for d in trading_days]
            
        except Exception as e:
            self.logger.error(f"Failed to get trading days between dates: {e}")
            return []
    
    def get_trading_day_offset(
        self,
        date_input: Union[str, date, datetime],
        offset: int,
        market: str = MARKET_CN
    ) -> Optional[str]:
        """Get a trading day with offset from the given date.
        
        Args:
            date_input: Reference date
            offset: Number of trading days to offset (positive for future, negative for past)
            market: Market type - 'cn' for A-share (default), 'hk' for HK stock
        
        Returns:
            Trading day in YYYY-MM-DD format, or None if not found
        """
        df = self._get_df(market)
        if df is None:
            return None
        
        try:
            date_str = self._normalize_date(date_input)
            date_ts = pd.Timestamp(date_str)
            
            if offset == 0:
                # Return the same day if it's a trading day, otherwise the previous
                if self.is_trading_day(date_str, market=market):
                    return date_str
                return self.get_prev_trading_day(date_str, market=market)
            
            elif offset > 0:
                # Get future trading days
                mask = (df['is_open'] == 1) & (df['cal_date'] > date_ts)
                future_days = df[mask].sort_values('cal_date')
                
                if len(future_days) >= offset:
                    return future_days.iloc[offset - 1]['cal_date'].strftime('%Y-%m-%d')
                return None
            
            else:  # offset < 0
                # Get past trading days
                mask = (df['is_open'] == 1) & (df['cal_date'] < date_ts)
                past_days = df[mask]  # Already sorted descending
                
                abs_offset = abs(offset)
                if len(past_days) >= abs_offset:
                    return past_days.iloc[abs_offset - 1]['cal_date'].strftime('%Y-%m-%d')
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get trading day with offset: {e}")
            return None
    
    def refresh_calendar(self, market: str = MARKET_CN) -> bool:
        """Refresh trade calendar from TuShare API.
        
        This method fetches the latest trade calendar from TuShare
        and updates the local CSV file.
        
        Args:
            market: Market type - 'cn' for A-share (default), 'hk' for HK stock.
                    Use 'all' to refresh both calendars.
        
        Returns:
            True if refresh successful, False otherwise
        """
        if market == "all":
            cn_ok = self.refresh_calendar(MARKET_CN)
            hk_ok = self.refresh_calendar(MARKET_HK)
            return cn_ok and hk_ok
        
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
            
            if market == MARKET_HK:
                return self._refresh_hk_calendar(pro)
            else:
                return self._refresh_cn_calendar(pro)
            
        except ImportError:
            self.logger.error("TuShare not installed, cannot refresh calendar")
            return False
        except Exception as e:
            self.logger.error(f"Failed to refresh {market} trade calendar: {e}")
            return False
    
    def _refresh_cn_calendar(self, pro) -> bool:
        """Refresh A-share calendar from TuShare."""
        self.logger.info("Fetching A-share trade calendar from TuShare API (2000-2030)...")
        df = pro.trade_cal(
            exchange='SSE',
            start_date='20000101',
            end_date='20301231'
        )
        
        if df is None or df.empty:
            self.logger.error("Failed to fetch A-share trade calendar from TuShare")
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
            f"Refreshed A-share trade calendar: {len(df)} total days, "
            f"{len(self._trading_days_set)} trading days"
        )
        return True
    
    def _refresh_hk_calendar(self, pro) -> bool:
        """Refresh HK stock calendar from TuShare hk_tradecal API.
        
        Since hk_tradecal has a 2000-record limit per call, we fetch in yearly chunks.
        """
        self.logger.info("Fetching HK trade calendar from TuShare API (2000-2030)...")
        
        all_dfs = []
        for year in range(2000, 2031):
            start = f"{year}0101"
            end = f"{year}1231"
            try:
                chunk = pro.hk_tradecal(start_date=start, end_date=end)
                if chunk is not None and not chunk.empty:
                    all_dfs.append(chunk)
            except Exception as e:
                self.logger.warning(f"Failed to fetch HK calendar for {year}: {e}")
        
        if not all_dfs:
            self.logger.error("Failed to fetch HK trade calendar from TuShare")
            return False
        
        df = pd.concat(all_dfs, ignore_index=True)
        
        # Rename and convert columns
        df = df.rename(columns={'cal_date': 'cal_date_str'})
        df['cal_date'] = pd.to_datetime(df['cal_date_str'], format='%Y%m%d')
        df = df[['cal_date', 'is_open', 'pretrade_date']]
        
        # Deduplicate and sort
        df = df.drop_duplicates(subset=['cal_date']).sort_values('cal_date', ascending=False)
        
        # Save to config directory
        hk_path = Path(__file__).parent.parent / "config" / "hk_trade_calendar.csv"
        df.to_csv(hk_path, index=False)
        
        # Reload into memory
        self._hk_calendar_df = df
        trading_days = df[df['is_open'] == 1]['cal_date']
        self._hk_trading_days_set = set(trading_days.dt.strftime('%Y-%m-%d').tolist())
        
        self.logger.info(
            f"Refreshed HK trade calendar: {len(df)} total days, "
            f"{len(self._hk_trading_days_set)} trading days"
        )
        return True
    
    @property
    def calendar_loaded(self) -> bool:
        """Check if A-share calendar data is loaded."""
        return self._calendar_df is not None and not self._calendar_df.empty
    
    @property
    def hk_calendar_loaded(self) -> bool:
        """Check if HK calendar data is loaded."""
        return self._hk_calendar_df is not None and not self._hk_calendar_df.empty
    
    @property
    def total_days(self) -> int:
        """Get total number of days in A-share calendar."""
        if self._calendar_df is None:
            return 0
        return len(self._calendar_df)
    
    @property
    def total_trading_days(self) -> int:
        """Get total number of A-share trading days in calendar."""
        if self._trading_days_set is None:
            return 0
        return len(self._trading_days_set)
    
    @property
    def date_range(self) -> tuple:
        """Get the date range of the A-share calendar.
        
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
    
    @property
    def hk_date_range(self) -> tuple:
        """Get the date range of the HK calendar.
        
        Returns:
            Tuple of (start_date, end_date) in YYYY-MM-DD format
        """
        if self._hk_calendar_df is None or self._hk_calendar_df.empty:
            return (None, None)
        
        min_date = self._hk_calendar_df['cal_date'].min()
        max_date = self._hk_calendar_df['cal_date'].max()
        
        return (
            min_date.strftime('%Y-%m-%d'),
            max_date.strftime('%Y-%m-%d')
        )


# Global singleton instance
trade_calendar_service = TradeCalendarService()
