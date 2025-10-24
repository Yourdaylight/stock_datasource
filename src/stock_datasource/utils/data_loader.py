"""Data loader for inserting validated data into ClickHouse."""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import pandas as pd

from stock_datasource.models.database import db_client
from stock_datasource.utils.logger import logger
from stock_datasource.config.settings import settings

log = logger.bind(component="DataLoader")


class DataLoader:
    """Loads validated data into ClickHouse database."""
    
    def __init__(self):
        self.db = db_client
        self.logger = log
    
    def ensure_table_exists(self, table_name: str, schema: Dict[str, Any]) -> bool:
        """Ensure table exists, create if not."""
        if self.db.table_exists(table_name):
            self.logger.info(f"Table {table_name} already exists")
            return True
        
        try:
            # Build CREATE TABLE statement
            create_sql = self._build_create_table_sql(table_name, schema)
            self.db.create_table(create_sql)
            self.logger.info(f"Created table {table_name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to create table {table_name}: {e}")
            return False
    
    def _build_create_table_sql(self, table_name: str, schema: Dict[str, Any]) -> str:
        """Build CREATE TABLE SQL from schema."""
        columns = schema.get('columns', [])
        column_defs = []
        
        for col in columns:
            col_name = col['name']
            col_type = col['data_type']
            nullable = col.get('nullable', True)
            default = col.get('default', None)
            
            # Build column definition
            col_def = f"{col_name} {col_type}"
            
            if not nullable:
                col_def += " NOT NULL"
            
            if default:
                col_def += f" DEFAULT {default}"
            
            column_defs.append(col_def)
        
        # Build full CREATE TABLE statement
        sql = f"CREATE TABLE IF NOT EXISTS {table_name} (\n"
        sql += ",\n".join(f"  {col_def}" for col_def in column_defs)
        sql += "\n)"
        
        # Add engine and settings
        engine = schema.get('engine', 'MergeTree')
        sql += f"\nENGINE = {engine}"
        
        if engine == 'ReplacingMergeTree':
            engine_params = schema.get('engine_params', [])
            if engine_params:
                sql += f"({', '.join(engine_params)})"
        
        # Add partition
        partition_by = schema.get('partition_by')
        if partition_by:
            sql += f"\nPARTITION BY {partition_by}"
        
        # Add order by
        order_by = schema.get('order_by', [])
        if order_by:
            sql += f"\nORDER BY ({', '.join(order_by)})"
        
        # Add settings
        sql += "\nSETTINGS index_granularity = 8192"
        
        return sql
    
    def load_daily_data(self, data: pd.DataFrame, 
                       table_name: str = "ods_daily") -> Dict[str, Any]:
        """Load daily stock data into ClickHouse."""
        result = {
            "table": table_name,
            "records": len(data),
            "status": "success",
            "error": None,
            "start_time": datetime.now()
        }
        
        try:
            if data.empty:
                result["status"] = "skipped"
                result["records"] = 0
                self.logger.info(f"No data to load for {table_name}")
                return result
            
            # Ensure table exists
            if not self.db.table_exists(table_name):
                self.logger.info(f"Table {table_name} does not exist, creating...")
                # Table should be created by schema manager
                # For now, just log a warning
                self.logger.warning(f"Table {table_name} does not exist")
            
            # Prepare data
            data_prepared = self._prepare_daily_data(data)
            
            # Insert data
            self.db.insert_dataframe(table_name, data_prepared)
            
            result["records"] = len(data_prepared)
            self.logger.info(f"Loaded {len(data_prepared)} records into {table_name}")
            
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            self.logger.error(f"Failed to load data into {table_name}: {e}")
        
        result["end_time"] = datetime.now()
        result["duration_seconds"] = (result["end_time"] - result["start_time"]).total_seconds()
        
        return result
    
    def load_adj_factor_data(self, data: pd.DataFrame,
                            table_name: str = "ods_adj_factor") -> Dict[str, Any]:
        """Load adjustment factor data into ClickHouse."""
        result = {
            "table": table_name,
            "records": len(data),
            "status": "success",
            "error": None,
            "start_time": datetime.now()
        }
        
        try:
            if data.empty:
                result["status"] = "skipped"
                result["records"] = 0
                self.logger.info(f"No data to load for {table_name}")
                return result
            
            # Prepare data
            data_prepared = self._prepare_adj_factor_data(data)
            
            # Insert data
            self.db.insert_dataframe(table_name, data_prepared)
            
            result["records"] = len(data_prepared)
            self.logger.info(f"Loaded {len(data_prepared)} records into {table_name}")
            
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            self.logger.error(f"Failed to load data into {table_name}: {e}")
        
        result["end_time"] = datetime.now()
        result["duration_seconds"] = (result["end_time"] - result["start_time"]).total_seconds()
        
        return result
    
    def load_daily_basic_data(self, data: pd.DataFrame,
                             table_name: str = "ods_daily_basic") -> Dict[str, Any]:
        """Load daily basic data into ClickHouse."""
        result = {
            "table": table_name,
            "records": len(data),
            "status": "success",
            "error": None,
            "start_time": datetime.now()
        }
        
        try:
            if data.empty:
                result["status"] = "skipped"
                result["records"] = 0
                self.logger.info(f"No data to load for {table_name}")
                return result
            
            # Prepare data
            data_prepared = self._prepare_daily_basic_data(data)
            
            # Insert data
            self.db.insert_dataframe(table_name, data_prepared)
            
            result["records"] = len(data_prepared)
            self.logger.info(f"Loaded {len(data_prepared)} records into {table_name}")
            
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            self.logger.error(f"Failed to load data into {table_name}: {e}")
        
        result["end_time"] = datetime.now()
        result["duration_seconds"] = (result["end_time"] - result["start_time"]).total_seconds()
        
        return result
    
    # ==================== Data Preparation ====================
    
    def _prepare_daily_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Prepare daily data for insertion."""
        df = data.copy()
        
        # Ensure required columns exist
        required_cols = ['ts_code', 'trade_date', 'open', 'high', 'low', 'close', 
                        'pre_close', 'change', 'pct_chg', 'vol', 'amount']
        
        for col in required_cols:
            if col not in df.columns:
                df[col] = None
        
        # Add system columns
        df['version'] = int(datetime.now().timestamp())
        df['_ingested_at'] = datetime.now()
        
        # Select and order columns
        columns = required_cols + ['version', '_ingested_at']
        df = df[columns]
        
        # Convert data types
        df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d').dt.date
        df['open'] = pd.to_numeric(df['open'], errors='coerce')
        df['high'] = pd.to_numeric(df['high'], errors='coerce')
        df['low'] = pd.to_numeric(df['low'], errors='coerce')
        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        df['pre_close'] = pd.to_numeric(df['pre_close'], errors='coerce')
        df['change'] = pd.to_numeric(df['change'], errors='coerce')
        df['pct_chg'] = pd.to_numeric(df['pct_chg'], errors='coerce')
        df['vol'] = pd.to_numeric(df['vol'], errors='coerce').astype('Int64')
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
        
        return df
    
    def _prepare_adj_factor_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Prepare adjustment factor data for insertion."""
        df = data.copy()
        
        required_cols = ['ts_code', 'trade_date', 'adj_factor']
        
        for col in required_cols:
            if col not in df.columns:
                df[col] = None
        
        # Add system columns
        df['version'] = int(datetime.now().timestamp())
        df['_ingested_at'] = datetime.now()
        
        columns = required_cols + ['version', '_ingested_at']
        df = df[columns]
        
        # Convert data types
        df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d').dt.date
        df['adj_factor'] = pd.to_numeric(df['adj_factor'], errors='coerce')
        
        return df
    
    def _prepare_daily_basic_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Prepare daily basic data for insertion."""
        df = data.copy()
        
        required_cols = ['ts_code', 'trade_date', 'close', 'turnover_rate', 'volume_ratio', 'pe', 'pb']
        
        for col in required_cols:
            if col not in df.columns:
                df[col] = None
        
        # Add system columns
        df['version'] = int(datetime.now().timestamp())
        df['_ingested_at'] = datetime.now()
        
        columns = required_cols + ['version', '_ingested_at']
        df = df[[col for col in columns if col in df.columns]]
        
        # Convert data types
        df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d').dt.date
        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        df['turnover_rate'] = pd.to_numeric(df['turnover_rate'], errors='coerce')
        df['volume_ratio'] = pd.to_numeric(df['volume_ratio'], errors='coerce')
        df['pe'] = pd.to_numeric(df['pe'], errors='coerce')
        df['pb'] = pd.to_numeric(df['pb'], errors='coerce')
        
        return df
    
    def load_batch(self, data_dict: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """Load multiple datasets in batch."""
        results = {
            "total": len(data_dict),
            "successful": 0,
            "failed": 0,
            "tables": {},
            "start_time": datetime.now()
        }
        
        for table_name, data in data_dict.items():
            try:
                if "daily" in table_name and "basic" not in table_name:
                    result = self.load_daily_data(data, table_name)
                elif "adj_factor" in table_name:
                    result = self.load_adj_factor_data(data, table_name)
                elif "daily_basic" in table_name:
                    result = self.load_daily_basic_data(data, table_name)
                else:
                    result = {
                        "table": table_name,
                        "status": "skipped",
                        "reason": "Unknown table type"
                    }
                
                results["tables"][table_name] = result
                
                if result.get("status") == "success":
                    results["successful"] += 1
                elif result.get("status") != "skipped":
                    results["failed"] += 1
                    
            except Exception as e:
                results["tables"][table_name] = {
                    "table": table_name,
                    "status": "failed",
                    "error": str(e)
                }
                results["failed"] += 1
        
        results["end_time"] = datetime.now()
        results["duration_seconds"] = (results["end_time"] - results["start_time"]).total_seconds()
        
        return results


# Global loader instance
data_loader = DataLoader()
