"""Base plugin class for stock data source."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pathlib import Path
import json
import inspect
from datetime import datetime
from enum import Enum
import pandas as pd

from stock_datasource.utils.logger import logger


class PluginCategory(str, Enum):
    """Plugin category enum - 按市场划分."""
    CN_STOCK = "cn_stock"  # A股相关
    HK_STOCK = "hk_stock"  # 港股相关
    INDEX = "index"        # 指数相关
    ETF_FUND = "etf_fund"  # ETF/基金相关（合并为一类）
    SYSTEM = "system"      # 系统数据（如交易日历）
    # 兼容旧值
    STOCK = "stock"        # 已废弃，请使用 CN_STOCK


# 分类别名映射（兼容旧分类）
CATEGORY_ALIASES = {
    "stock": "cn_stock",
}

# 前端显示标签
CATEGORY_LABELS = {
    "cn_stock": "A股",
    "hk_stock": "港股",
    "index": "指数",
    "etf_fund": "ETF基金",
    "system": "系统",
    "stock": "A股",  # 兼容
}


class PluginRole(str, Enum):
    """Plugin role enum."""
    PRIMARY = "primary"      # 主数据（如 daily 行情）
    BASIC = "basic"          # 基础数据（如 stock_basic）
    DERIVED = "derived"      # 衍生数据（如复权因子）
    AUXILIARY = "auxiliary"  # 辅助数据（如指数权重）


class BasePlugin(ABC):
    """Base class for all data plugins."""
    
    def __init__(self):
        self.logger = logger.bind(plugin=self.name)
        self._config = None
        self._schema = None
        self._plugin_dir = None
        self.db = None
        self._init_db()
    
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
        """Proxy settings are applied per request via proxy_context."""
        return
    
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
    
    def get_optional_dependencies(self) -> List[str]:
        """Get list of optional plugin dependencies (default: none).
        
        Optional dependencies are synced by default when syncing the main plugin,
        but users can choose to disable them.
        
        Example: tushare_daily has tushare_adj_factor as optional dependency.
        """
        return []
    
    def get_category(self) -> PluginCategory:
        """Get plugin category.
        
        Subclasses should override this to specify their category.
        Default: CN_STOCK (A股)
        """
        return PluginCategory.CN_STOCK
    
    def get_role(self) -> PluginRole:
        """Get plugin role.
        
        Subclasses should override this to specify their role.
        Default: PRIMARY
        """
        return PluginRole.PRIMARY
    
    def has_data(self) -> bool:
        """Check if plugin has data in its target table.
        
        This method is used for dependency checking to verify that
        dependent plugins have their data available.
        
        Returns:
            True if the plugin's table has data, False otherwise
        """
        try:
            schema = self.get_schema()
            table_name = schema.get('table_name')
            
            if not table_name or not self.db:
                return False
            
            # Use LIMIT 1 for efficiency
            result = self.db.execute_query(
                f"SELECT 1 FROM {table_name} LIMIT 1"
            )
            return result is not None and not result.empty
            
        except Exception as e:
            self.logger.warning(f"Failed to check data existence: {e}")
            return False
    
    def get_config_schema(self) -> Dict[str, Any]:
        """Get configuration schema for plugin parameters from config.json."""
        config = self.get_config()
        # Return the parameters_schema from config.json if it exists
        return config.get("parameters_schema", {})
    
    def is_enabled(self) -> bool:
        """Check if plugin is enabled."""
        config = self.get_config()
        return config.get("enabled", True)
    
    def set_enabled(self, enabled: bool) -> bool:
        """Set plugin enabled state.
        
        Args:
            enabled: Whether to enable or disable the plugin
            
        Returns:
            True if state was changed successfully
        """
        try:
            config_file = self._get_plugin_dir() / "config.json"
            config = self.get_config().copy()
            config["enabled"] = enabled
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            # Update cached config
            self._config = config
            self.logger.info(f"Plugin {self.name} {'enabled' if enabled else 'disabled'}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to set enabled state: {e}")
            return False
    
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
    
    def get_sync_mode(self) -> str:
        """Get plugin data sync mode.
        
        Returns:
            Sync mode string:
            - 'incremental': Append new data (default, for time-series data like daily bars)
            - 'full_replace': Truncate table and reload all data (for dimension/basic tables)
        
        For dimension tables (stock_basic, etf_basic, index_basic), use 'full_replace'
        because Tushare API returns complete dataset each time and we want to ensure
        data consistency without duplicates.
        """
        config = self.get_config()
        return config.get("sync_mode", "incremental")
    
    def _truncate_table(self, table_name: str) -> bool:
        """Truncate table before full data reload.
        
        Args:
            table_name: Name of table to truncate
            
        Returns:
            True if successful, False otherwise
        """
        if not self.db:
            self.logger.error("Database not initialized")
            return False
        
        try:
            self.logger.info(f"Truncating table {table_name} for full_replace sync mode")
            self.db.execute_query(f"TRUNCATE TABLE {table_name}")
            self.logger.info(f"Table {table_name} truncated successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to truncate table {table_name}: {e}")
            return False
    
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
                
                # Handle Enum type - ensure values are plain strings without quotes
                elif 'Enum' in target_type:
                    if col_name in data.columns:
                        # Extract valid enum values from type definition
                        # e.g., "Enum8('institution' = 1, 'hot_money' = 2, 'unknown' = 3)"
                        import re
                        enum_values = re.findall(r"'(\w+)'", target_type)
                        if enum_values:
                            # Ensure all values are valid enum values
                            data[col_name] = data[col_name].astype(str).str.strip()
                            # Replace invalid values with default (first enum value or 'unknown')
                            default_value = 'unknown' if 'unknown' in enum_values else enum_values[0]
                            invalid_mask = ~data[col_name].isin(enum_values)
                            if invalid_mask.any():
                                self.logger.warning(
                                    f"Replacing {invalid_mask.sum()} invalid {col_name} values with '{default_value}'"
                                )
                                data.loc[invalid_mask, col_name] = default_value
        
        except Exception as e:
            self.logger.warning(f"Failed to prepare data for {table_name}: {e}")
        
        return data
