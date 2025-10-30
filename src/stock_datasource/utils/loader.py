"""Data loader for ODS to DM/Fact layer transformation."""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import pandas as pd

from stock_datasource.models.database import db_client
from stock_datasource.models.schemas import TableType
from stock_datasource.utils.schema_manager import schema_manager
from stock_datasource.config.settings import settings

logger = logging.getLogger(__name__)


class DataLoader:
    """Loads data from ODS to DM/Fact layers with transformation logic."""
    
    def __init__(self):
        self.db = db_client
        self.schema_manager = schema_manager
    
    def load_ods_data(self, table_name: str, data: pd.DataFrame, 
                     api_name: str) -> Dict[str, Any]:
        """
        Load data into ODS layer with schema synchronization.
        Returns loading statistics.
        """
        logger.info(f"Loading data into ODS table {table_name}")
        
        if data.empty:
            logger.warning(f"No data to load for {table_name}")
            return {"loaded_records": 0, "status": "no_data"}
        
        # Skip schema sync for now - tables are already created
        # TODO: Implement async schema sync if needed
        schema_changed = False
        logger.info(f"Skipping schema sync for {table_name} (tables pre-created)")
        
        # Add system columns
        logger.info(f"Adding system columns to {table_name}")
        data['version'] = int(datetime.now().timestamp())
        data['_ingested_at'] = datetime.now()
        
        # Ensure data types match table schema
        logger.info(f"Preparing data for insert into {table_name}")
        data = self._prepare_data_for_insert(table_name, data)
        
        try:
            # Insert data
            logger.info(f"Inserting {len(data)} records into {table_name}")
            self.db.insert_dataframe(table_name, data)
            logger.info(f"Insert completed for {table_name}")
            
            stats = {
                "loaded_records": len(data),
                "table_name": table_name,
                "api_name": api_name,
                "schema_changed": schema_changed,
                "status": "success"
            }
            
            logger.info(f"Successfully loaded {len(data)} records into {table_name}")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to load data into {table_name}: {e}")
            raise
    
    def _prepare_data_for_insert(self, table_name: str, data: pd.DataFrame) -> pd.DataFrame:
        """Prepare data for insertion by ensuring type compatibility."""
        # Get table schema
        schema = self.db.get_table_schema(table_name)
        schema_dict = {col['column_name']: col['data_type'] for col in schema}
        
        # Convert data types based on target schema
        for col_name in data.columns:
            if col_name not in schema_dict:
                continue
            
            target_type = schema_dict[col_name]
            
            # Handle date conversions
            if 'Date' in target_type and col_name in data.columns:
                # Convert YYYYMMDD string to datetime.date object
                try:
                    data[col_name] = pd.to_datetime(data[col_name], format='%Y%m%d').dt.date
                except Exception as e:
                    logger.warning(f"Failed to convert {col_name} to date: {e}, trying alternative format")
                    data[col_name] = pd.to_datetime(data[col_name]).dt.date
            
            # Handle numeric conversions
            elif 'Float64' in target_type or 'Int64' in target_type:
                if col_name in data.columns:
                    data[col_name] = pd.to_numeric(data[col_name], errors='coerce')
        
        return data
    
    def load_dim_security(self, stock_basic_data: pd.DataFrame) -> Dict[str, Any]:
        """Load security master data into dim_security table."""
        logger.info("Loading security master data")
        
        if stock_basic_data.empty:
            return {"loaded_records": 0, "status": "no_data"}
        
        # Transform data for dim_security
        dim_data = stock_basic_data.copy()
        
        # Add system columns first (before selecting columns)
        now = datetime.now()
        dim_data['version'] = int(now.timestamp())
        dim_data['_ingested_at'] = now
        
        # Ensure all required columns exist
        required_columns = ['ts_code', 'symbol', 'name', 'area', 'industry', 'market', 
                           'list_date', 'delist_date', 'list_status']
        
        for col in required_columns:
            if col not in dim_data.columns:
                if col == 'area':
                    dim_data[col] = None
                elif col == 'industry':
                    dim_data[col] = None
                elif col == 'market':
                    # Infer market from ts_code
                    dim_data[col] = dim_data['ts_code'].apply(
                        lambda x: 'SZSE' if x.endswith('.SZ') else ('SSE' if x.endswith('.SH') else 'OTHER')
                    )
                elif col == 'list_status':
                    dim_data[col] = 'L'  # Default to Listed
                else:
                    logger.warning(f"Missing required column {col} in stock basic data")
        
        # Select only required columns (including system columns)
        dim_data = dim_data[required_columns + ['version', '_ingested_at']]
        
        # Convert date formats
        if 'list_date' in dim_data.columns:
            dim_data['list_date'] = pd.to_datetime(dim_data['list_date'], format='%Y%m%d', errors='coerce').dt.date
        
        if 'delist_date' in dim_data.columns:
            dim_data['delist_date'] = pd.to_datetime(dim_data['delist_date'], format='%Y%m%d', errors='coerce').dt.date
        
        try:
            # Insert into dim_security
            self.db.insert_dataframe('dim_security', dim_data)
            
            stats = {
                "loaded_records": len(dim_data),
                "table_name": "dim_security",
                "status": "success"
            }
            
            logger.info(f"Loaded {len(dim_data)} securities into dim_security")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to load dim_security: {e}")
            raise
    
    def load_fact_daily_bar(self, daily_data: pd.DataFrame, 
                           adj_factor_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Load daily bar data into fact_daily_bar table."""
        logger.info("Loading daily bar data")
        
        if daily_data.empty:
            return {"loaded_records": 0, "status": "no_data"}
        
        # Start with daily data
        fact_data = daily_data.copy()
        
        # Merge with adjustment factors if available
        if adj_factor_data is not None and not adj_factor_data.empty:
            fact_data = pd.merge(
                fact_data,
                adj_factor_data[['ts_code', 'trade_date', 'adj_factor']],
                on=['ts_code', 'trade_date'],
                how='left'
            )
        
        # Add timestamps
        now = datetime.now()
        fact_data['created_at'] = now
        fact_data['updated_at'] = now
        
        try:
            # Insert into fact_daily_bar
            self.db.insert_dataframe('fact_daily_bar', fact_data)
            
            stats = {
                "loaded_records": len(fact_data),
                "table_name": "fact_daily_bar",
                "status": "success",
                "has_adj_factors": adj_factor_data is not None and not adj_factor_data.empty
            }
            
            logger.info(f"Loaded {len(fact_data)} daily bars into fact_daily_bar")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to load fact_daily_bar: {e}")
            raise
    
    def process_daily_ingestion(self, trade_date: str, 
                               extracted_data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """Process daily data ingestion for all tables."""
        logger.info(f"Processing daily ingestion for {trade_date}")
        
        results = {
            "trade_date": trade_date,
            "tables_processed": [],
            "total_records": 0,
            "status": "success"
        }
        
        try:
            # Load ODS tables
            ods_tables = {
                'ods_daily': ('daily', extracted_data.get('daily')),
                'ods_adj_factor': ('adj_factor', extracted_data.get('adj_factor')),
                'ods_daily_basic': ('daily_basic', extracted_data.get('daily_basic')),
                'ods_suspend_d': ('suspend_d', extracted_data.get('suspend_d')),
                'ods_stk_limit': ('stk_limit', extracted_data.get('stk_limit'))
            }
            
            for table_name, (api_name, data) in ods_tables.items():
                if data is not None and not data.empty:
                    try:
                        stats = self.load_ods_data(table_name, data, api_name)
                        results['tables_processed'].append(stats)
                        results['total_records'] += stats['loaded_records']
                    except Exception as e:
                        logger.error(f"Failed to load {table_name}: {e}")
                        results['status'] = "partial_success"
            
            # Load DM/Fact tables
            if 'daily' in extracted_data and not extracted_data['daily'].empty:
                try:
                    daily_stats = self.load_fact_daily_bar(
                        extracted_data['daily'],
                        extracted_data.get('adj_factor')
                    )
                    results['tables_processed'].append(daily_stats)
                    results['total_records'] += daily_stats['loaded_records']
                except Exception as e:
                    logger.error(f"Failed to load fact_daily_bar: {e}")
                    results['status'] = "partial_success"
            
            # Load security master data (only if needed)
            if 'stock_basic' in extracted_data and not extracted_data['stock_basic'].empty:
                try:
                    security_stats = self.load_dim_security(extracted_data['stock_basic'])
                    results['tables_processed'].append(security_stats)
                    results['total_records'] += security_stats['loaded_records']
                except Exception as e:
                    logger.error(f"Failed to load dim_security: {e}")
                    results['status'] = "partial_success"
            
            logger.info(f"Daily ingestion completed for {trade_date}: "
                       f"{len(results['tables_processed'])} tables, "
                       f"{results['total_records']} total records")
            
            return results
            
        except Exception as e:
            logger.error(f"Daily ingestion failed for {trade_date}: {e}")
            results['status'] = "failed"
            results['error'] = str(e)
            return results
    
    def get_loading_statistics(self, table_name: str, 
                             start_date: Optional[str] = None,
                             end_date: Optional[str] = None) -> Dict[str, Any]:
        """Get loading statistics for a table."""
        if not self.db.table_exists(table_name):
            return {"exists": False}
        
        # Build query
        query = f"SELECT COUNT(*) as total_records, MAX(_ingested_at) as last_load"
        
        if start_date or end_date:
            query += f" FROM {table_name} WHERE 1=1"
            if start_date:
                query += f" AND trade_date >= '{start_date}'"
            if end_date:
                query += f" AND trade_date <= '{end_date}'"
        else:
            query += f" FROM {table_name}"
        
        try:
            result = self.db.execute_query(query)
            if not result.empty:
                return {
                    "exists": True,
                    "total_records": result.iloc[0]['total_records'],
                    "last_load": result.iloc[0]['last_load'],
                    "table_name": table_name
                }
        except Exception as e:
            logger.error(f"Failed to get statistics for {table_name}: {e}")
        
        return {"exists": True, "error": str(e)}
    
    def cleanup_old_versions(self, table_name: str, keep_days: int = 30) -> Dict[str, Any]:
        """Clean up old versions from ReplacingMergeTree tables."""
        logger.info(f"Cleaning up old versions in {table_name}, keeping {keep_days} days")
        
        try:
            # Calculate cutoff date
            cutoff_date = datetime.now() - pd.Timedelta(days=keep_days)
            cutoff_timestamp = int(cutoff_date.timestamp())
            
            # Optimize table to remove old versions
            query = f"""
            ALTER TABLE {table_name} 
            DELETE WHERE version < {cutoff_timestamp}
            """
            
            self.db.execute(query)
            
            # Force optimization
            self.db.optimize_table(table_name, final=True)
            
            stats = {
                "table_name": table_name,
                "cleanup_date": datetime.now(),
                "keep_days": keep_days,
                "status": "success"
            }
            
            logger.info(f"Cleanup completed for {table_name}")
            return stats
            
        except Exception as e:
            logger.error(f"Cleanup failed for {table_name}: {e}")
            return {
                "table_name": table_name,
                "error": str(e),
                "status": "failed"
            }


# Global loader instance
loader = DataLoader()
