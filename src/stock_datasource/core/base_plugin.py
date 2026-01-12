"""Base plugin class for stock data source."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pathlib import Path
import json
import inspect
from datetime import datetime
import pandas as pd

from stock_datasource.utils.logger import logger


class BasePlugin(ABC):
    """Base class for all data plugins."""
    
    def __init__(self):
        self.logger = logger.bind(plugin=self.name)
        self._config = None
        self._schema = None
        self._plugin_dir = None
        self.db = None
        self._init_db()
        self._init_proxy()
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin name (must be unique)."""
        pass
    
    @property
    def version(self) -> str:
        """Plugin version (default: 1.0.0)."""
        return "1.0.0"
    
    @property
    def description(self) -> str:
        """Plugin description (default: empty)."""
        return ""
    
    @property
    def api_rate_limit(self) -> int:
        """API rate limit per minute (default: 120)."""
        return 120
    
    def _init_db(self):
        """Initialize database connection."""
        try:
            from stock_datasource.models.database import db_client
            self.db = db_client
        except Exception as e:
            self.logger.warning(f"Failed to initialize database: {e}")
    
    def _init_proxy(self):
        """Initialize HTTP proxy settings for data fetching."""
        try:
            from stock_datasource.core.proxy import apply_proxy_settings
            apply_proxy_settings()
        except Exception as e:
            self.logger.warning(f"Failed to initialize proxy: {e}")
    
    def _get_plugin_dir(self) -> Path:
        """Get the plugin directory path."""
        if self._plugin_dir is None:
            # Get the directory of the plugin's plugin.py file
            import inspect
            plugin_file = inspect.getfile(self.__class__)
            self._plugin_dir = Path(plugin_file).parent
        return self._plugin_dir
    
    def get_config(self) -> Dict[str, Any]:
        """Get plugin configuration from config.json."""
        if self._config is None:
            config_file = self._get_plugin_dir() / "config.json"
            if config_file.exists():
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        self._config = json.load(f)
                except Exception as e:
                    self.logger.warning(f"Failed to load config.json: {e}")
                    self._config = self._get_default_config()
            else:
                self._config = self._get_default_config()
        return self._config
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration if config.json doesn't exist."""
        return {
            "enabled": True,
            "rate_limit": self.api_rate_limit,
            "timeout": 30,
            "retry_attempts": 3,
            "description": self.description
        }
    
    def get_schema(self) -> Dict[str, Any]:
        """Get table schema from schema.json."""
        if self._schema is None:
            schema_file = self._get_plugin_dir() / "schema.json"
            if schema_file.exists():
                try:
                    with open(schema_file, 'r', encoding='utf-8') as f:
                        self._schema = json.load(f)
                except Exception as e:
                    self.logger.warning(f"Failed to load schema.json: {e}")
                    self._schema = self._get_default_schema()
            else:
                self._schema = self._get_default_schema()
        return self._schema
    
    def _get_default_schema(self) -> Dict[str, Any]:
        """Get default schema if schema.json doesn't exist."""
        raise NotImplementedError(f"Plugin {self.name} must implement get_schema() or provide schema.json")
    
    @abstractmethod
    def extract_data(self, **kwargs) -> Any:
        """Extract data from source."""
        pass
    
    def validate_data(self, data: Any) -> bool:
        """Validate extracted data (default: basic validation)."""
        if data is None:
            self.logger.warning("Data is None")
            return False
        
        if hasattr(data, '__len__') and len(data) == 0:
            self.logger.warning("Data is empty")
            return False
        
        return True
    
    def transform_data(self, data: Any) -> Any:
        """Transform data for database insertion (default: pass-through)."""
        return data
    
    def get_dependencies(self) -> List[str]:
        """Get list of plugin dependencies (default: none)."""
        return []
    
    def get_config_schema(self) -> Dict[str, Any]:
        """Get configuration schema for plugin parameters from config.json."""
        config = self.get_config()
        # Return the parameters_schema from config.json if it exists
        return config.get("parameters_schema", {})
    
    def is_enabled(self) -> bool:
        """Check if plugin is enabled."""
        config = self.get_config()
        return config.get("enabled", True)
    
    def get_rate_limit(self) -> int:
        """Get plugin-specific rate limit."""
        config = self.get_config()
        return config.get("rate_limit", self.api_rate_limit)
    
    def get_timeout(self) -> int:
        """Get plugin-specific timeout."""
        config = self.get_config()
        return config.get("timeout", 30)
    
    def get_retry_attempts(self) -> int:
        """Get plugin-specific retry attempts."""
        config = self.get_config()
        return config.get("retry_attempts", 3)
    
    def get_schedule(self) -> Dict[str, Any]:
        """Get plugin schedule configuration.
        
        Returns:
            Dict with schedule info:
            - frequency: 'daily' or 'weekly'
            - time: execution time in HH:MM format (default: '18:00')
            - day_of_week: for weekly frequency (default: 'monday')
        """
        config = self.get_config()
        schedule = config.get("schedule", {})
        
        # Set defaults
        if not schedule:
            schedule = {
                "frequency": "daily",
                "time": "18:00"
            }
        else:
            schedule.setdefault("frequency", "daily")
            schedule.setdefault("time", "18:00")
            if schedule.get("frequency") == "weekly":
                schedule.setdefault("day_of_week", "monday")
        
        return schedule
    
    def should_run_today(self, current_date=None) -> bool:
        """Check if plugin should run on the given date.
        
        Args:
            current_date: datetime.date object (default: today)
        
        Returns:
            True if plugin should run, False otherwise
        """
        from datetime import date, datetime
        
        if current_date is None:
            current_date = date.today()
        
        schedule = self.get_schedule()
        frequency = schedule.get("frequency", "daily")
        
        if frequency == "daily":
            return True
        elif frequency == "weekly":
            day_of_week = schedule.get("day_of_week", "monday").lower()
            weekday_map = {
                "monday": 0,
                "tuesday": 1,
                "wednesday": 2,
                "thursday": 3,
                "friday": 4,
                "saturday": 5,
                "sunday": 6
            }
            target_weekday = weekday_map.get(day_of_week, 0)
            return current_date.weekday() == target_weekday
        
        return False
    
    def run(self, **kwargs) -> Dict[str, Any]:
        """Execute complete data pipeline: extract -> validate -> transform -> load.
        
        This is the main orchestration method that all plugins use.
        Subclasses should implement extract_data(), validate_data(), transform_data(), and load_data().
        
        Args:
            **kwargs: Plugin-specific parameters (e.g., trade_date, date, etc.)
        
        Returns:
            Pipeline execution result with status and step details
        """
        result = {
            "plugin": self.name,
            "status": "success",
            "steps": {},
            "parameters": kwargs
        }
        
        try:
            # Step 1: Extract
            self.logger.info(f"[{self.name}] Step 1: Extracting data with params: {kwargs}")
            data = self.extract_data(**kwargs)
            result['steps']['extract'] = {
                "status": "success",
                "records": len(data) if hasattr(data, '__len__') else 0
            }
            
            # Check if data is empty (handle DataFrame and other types)
            is_empty = False
            if hasattr(data, 'empty'):  # DataFrame
                is_empty = data.empty
            elif hasattr(data, '__len__'):
                is_empty = len(data) == 0
            else:
                is_empty = not data
            
            if is_empty:
                self.logger.warning(f"[{self.name}] No data extracted")
                result['steps']['extract']['status'] = 'no_data'
                return result
            
            # Step 2: Validate
            self.logger.info(f"[{self.name}] Step 2: Validating data")
            if not self.validate_data(data):
                self.logger.error(f"[{self.name}] Data validation failed")
                result['steps']['validate'] = {"status": "failed"}
                result['status'] = 'failed'
                return result
            
            result['steps']['validate'] = {"status": "success"}
            
            # Step 3: Transform
            self.logger.info(f"[{self.name}] Step 3: Transforming data")
            data = self.transform_data(data)
            result['steps']['transform'] = {
                "status": "success",
                "records": len(data) if hasattr(data, '__len__') else 0
            }
            
            # Step 4: Load
            self.logger.info(f"[{self.name}] Step 4: Loading data")
            load_result = self.load_data(data)
            result['steps']['load'] = load_result
            
            if load_result.get('status') != 'success':
                result['status'] = 'failed'
            
            self.logger.info(f"[{self.name}] Pipeline completed with status: {result['status']}")
            return result
            
        except Exception as e:
            self.logger.error(f"[{self.name}] Pipeline failed: {e}")
            result['status'] = 'failed'
            result['error'] = str(e)
            return result
    
    @abstractmethod
    def load_data(self, data: Any) -> Dict[str, Any]:
        """Load transformed data into database.
        
        Subclasses must implement this method.
        
        Args:
            data: Transformed data to load
        
        Returns:
            Dict with loading statistics and status
        """
        pass
    
    def _add_system_columns(self, data: pd.DataFrame) -> pd.DataFrame:
        """Add system columns (version, _ingested_at) to data.
        
        Args:
            data: DataFrame to add system columns to
        
        Returns:
            DataFrame with system columns added
        """
        data['version'] = int(datetime.now().timestamp())
        data['_ingested_at'] = datetime.now()
        return data
    
    def _check_empty_data(self, data: Any, data_type: str = "data") -> bool:
        """Check if data is empty.
        
        Args:
            data: Data to check
            data_type: Description of data type for logging
        
        Returns:
            True if data is not empty, False otherwise
        """
        if not data or (hasattr(data, '__len__') and len(data) == 0):
            self.logger.warning(f"Empty {data_type}")
            return False
        return True
    
    def _check_null_values(self, data: pd.DataFrame, columns: List[str]) -> bool:
        """Check for null values in specified columns.
        
        Args:
            data: DataFrame to check
            columns: List of column names to check
        
        Returns:
            True if no null values found, False otherwise
        """
        for col in columns:
            if col in data.columns:
                null_count = data[col].isnull().sum()
                if null_count > 0:
                    self.logger.error(f"Found {null_count} null values in {col}")
                    return False
        return True
    
    def _prepare_data_for_insert(self, table_name: str, data: pd.DataFrame) -> pd.DataFrame:
        """Prepare data for insertion by ensuring type compatibility.
        
        Args:
            table_name: Name of the target table
            data: DataFrame to prepare
        
        Returns:
            DataFrame with types converted according to table schema
        """
        if not self.db:
            self.logger.warning(f"Database not initialized, skipping type conversion for {table_name}")
            return data
        
        try:
            schema = self.db.get_table_schema(table_name)
            schema_dict = {col['column_name']: col['data_type'] for col in schema}
            
            for col_name in data.columns:
                if col_name not in schema_dict:
                    continue
                
                target_type = schema_dict[col_name]
                
                # Handle date conversions
                if 'Date' in target_type and col_name in data.columns:
                    try:
                        data[col_name] = pd.to_datetime(data[col_name], format='%Y%m%d').dt.date
                    except Exception as e:
                        self.logger.warning(f"Failed to convert {col_name} to date: {e}")
                        data[col_name] = pd.to_datetime(data[col_name]).dt.date
                
                # Handle numeric conversions
                elif 'Float64' in target_type or 'Int64' in target_type:
                    if col_name in data.columns:
                        data[col_name] = pd.to_numeric(data[col_name], errors='coerce')
        
        except Exception as e:
            self.logger.warning(f"Failed to prepare data for {table_name}: {e}")
        
        return data
