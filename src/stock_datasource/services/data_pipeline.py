"""Data pipeline service for ETL operations."""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import pandas as pd

from stock_datasource.core.plugin_manager import plugin_manager
from stock_datasource.utils.data_validator import data_validator
from stock_datasource.utils.data_loader import data_loader
from stock_datasource.utils.logger import logger
from stock_datasource.models.database import db_client

log = logger.bind(component="DataPipeline")


class DataPipeline:
    """Orchestrates the complete ETL pipeline."""
    
    def __init__(self):
        self.plugin_manager = plugin_manager
        self.validator = data_validator
        self.loader = data_loader
        self.db = db_client
        self.logger = log
    
    def initialize(self):
        """Initialize the pipeline (discover plugins, create tables, etc.)."""
        self.logger.info("Initializing data pipeline...")
        
        # Discover plugins
        self.plugin_manager.discover_plugins()
        plugins = self.plugin_manager.list_plugins()
        self.logger.info(f"Discovered {len(plugins)} plugins")
        
        # Create database
        try:
            self.db.create_database("stock_datasource")
            self.logger.info("Database created or already exists")
        except Exception as e:
            self.logger.error(f"Failed to create database: {e}")
        
        return {
            "status": "success",
            "plugins_discovered": len(plugins),
            "database_ready": True
        }
    
    def extract_daily_data(self, trade_date: str) -> Dict[str, Any]:
        """Extract daily data for all plugins."""
        result = {
            "trade_date": trade_date,
            "start_time": datetime.now(),
            "plugins": {},
            "total_records": 0,
            "status": "success"
        }
        
        self.logger.info(f"Extracting daily data for {trade_date}")
        
        # Get active plugins (enabled and not ignored)
        active_plugins = self.plugin_manager.get_active_plugins()
        
        for plugin in active_plugins:
            try:
                self.logger.info(f"Extracting data from {plugin.name}")
                
                # Prepare parameters based on plugin type
                if plugin.name == 'tushare_trade_calendar':
                    # Trade calendar needs date range
                    data = plugin.extract_data(start_date=trade_date, end_date=trade_date)
                elif plugin.name == 'tushare_stock_basic':
                    # Stock basic doesn't need date
                    data = plugin.extract_data()
                else:
                    # Other plugins need trade_date
                    data = plugin.extract_data(trade_date=trade_date)
                
                # Validate data
                if data is not None and not data.empty:
                    validation = self.validator.validate_daily_data(data, trade_date)
                    result["plugins"][plugin.name] = {
                        "records": len(data),
                        "validation": validation,
                        "status": "success" if validation["passed"] else "warning"
                    }
                    result["total_records"] += len(data)
                    self.logger.info(f"Extracted {len(data)} records from {plugin.name}")
                else:
                    result["plugins"][plugin.name] = {
                        "records": 0,
                        "status": "no_data"
                    }
                    self.logger.warning(f"No data extracted from {plugin.name}")
                    
            except Exception as e:
                result["plugins"][plugin.name] = {
                    "status": "failed",
                    "error": str(e)
                }
                result["status"] = "partial_success"
                self.logger.error(f"Failed to extract data from {plugin.name}: {e}")
        
        result["end_time"] = datetime.now()
        result["duration_seconds"] = (result["end_time"] - result["start_time"]).total_seconds()
        
        return result
    
    def validate_daily_data(self, data_dict: Dict[str, pd.DataFrame], 
                           trade_date: str) -> Dict[str, Any]:
        """Validate daily data from all sources."""
        result = {
            "trade_date": trade_date,
            "start_time": datetime.now(),
            "validations": {},
            "summary": {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "issues": []
            }
        }
        
        self.logger.info(f"Validating daily data for {trade_date}")
        
        for source_name, data in data_dict.items():
            try:
                if "adj_factor" in source_name:
                    validation = self.validator.validate_adj_factor_data(data, trade_date)
                else:
                    validation = self.validator.validate_daily_data(data, trade_date)
                
                result["validations"][source_name] = validation
                result["summary"]["total"] += 1
                
                if validation["passed"]:
                    result["summary"]["passed"] += 1
                else:
                    result["summary"]["failed"] += 1
                    result["summary"]["issues"].extend(validation.get("issues", []))
                    
            except Exception as e:
                result["validations"][source_name] = {
                    "status": "error",
                    "error": str(e)
                }
                result["summary"]["total"] += 1
                result["summary"]["failed"] += 1
                result["summary"]["issues"].append(f"{source_name}: {str(e)}")
        
        result["end_time"] = datetime.now()
        result["duration_seconds"] = (result["end_time"] - result["start_time"]).total_seconds()
        
        return result
    
    def load_daily_data(self, data_dict: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """Load validated daily data into database."""
        result = {
            "start_time": datetime.now(),
            "tables": {},
            "summary": {
                "total": 0,
                "successful": 0,
                "failed": 0,
                "total_records": 0
            }
        }
        
        self.logger.info("Loading daily data into database")
        
        # Map data sources to table names
        table_mapping = {
            "tushare_daily": "ods_daily",
            "tushare_adj_factor": "ods_adj_factor",
            "tushare_daily_basic": "ods_daily_basic",
            "tushare_stock_basic": "ods_stock_basic",
            "tushare_stk_limit": "ods_stk_limit",
            "tushare_suspend_d": "ods_suspend_d",
            "tushare_trade_calendar": "ods_trade_calendar"
        }
        
        for source_name, data in data_dict.items():
            table_name = table_mapping.get(source_name, source_name)
            
            try:
                load_result = self.loader.load_batch({table_name: data})
                result["tables"][table_name] = load_result["tables"].get(table_name, {})
                
                result["summary"]["total"] += 1
                if load_result["tables"].get(table_name, {}).get("status") == "success":
                    result["summary"]["successful"] += 1
                    result["summary"]["total_records"] += load_result["tables"].get(table_name, {}).get("records", 0)
                else:
                    result["summary"]["failed"] += 1
                    
            except Exception as e:
                result["tables"][table_name] = {
                    "status": "failed",
                    "error": str(e)
                }
                result["summary"]["total"] += 1
                result["summary"]["failed"] += 1
                self.logger.error(f"Failed to load data into {table_name}: {e}")
        
        result["end_time"] = datetime.now()
        result["duration_seconds"] = (result["end_time"] - result["start_time"]).total_seconds()
        
        return result
    
    def run_daily_pipeline(self, trade_date: str, 
                          skip_validation: bool = False) -> Dict[str, Any]:
        """Run complete daily ETL pipeline."""
        pipeline_result = {
            "trade_date": trade_date,
            "start_time": datetime.now(),
            "stages": {},
            "status": "success",
            "summary": {
                "total_records_extracted": 0,
                "total_records_loaded": 0,
                "validation_issues": 0
            }
        }
        
        self.logger.info(f"Starting daily pipeline for {trade_date}")
        
        try:
            # Stage 1: Extract
            self.logger.info("Stage 1: Extracting data...")
            extraction_result = self.extract_daily_data(trade_date)
            pipeline_result["stages"]["extraction"] = extraction_result
            pipeline_result["summary"]["total_records_extracted"] = extraction_result["total_records"]
            
            if extraction_result["status"] == "failed":
                pipeline_result["status"] = "failed"
                self.logger.error("Extraction failed")
                return pipeline_result
            
            # Collect extracted data
            extracted_data = {}
            for plugin_name, plugin_result in extraction_result["plugins"].items():
                if plugin_result.get("status") in ["success", "warning"]:
                    # Get data from plugin
                    plugin = self.plugin_manager.get_plugin(plugin_name)
                    if plugin:
                        try:
                            if plugin_name == 'tushare_trade_calendar':
                                data = plugin.extract_data(start_date=trade_date, end_date=trade_date)
                            elif plugin_name == 'tushare_stock_basic':
                                data = plugin.extract_data()
                            else:
                                data = plugin.extract_data(trade_date=trade_date)
                            
                            if data is not None and not data.empty:
                                extracted_data[plugin_name] = data
                        except Exception as e:
                            self.logger.warning(f"Failed to re-extract data from {plugin_name}: {e}")
            
            # Stage 2: Validate (optional)
            if not skip_validation:
                self.logger.info("Stage 2: Validating data...")
                validation_result = self.validate_daily_data(extracted_data, trade_date)
                pipeline_result["stages"]["validation"] = validation_result
                pipeline_result["summary"]["validation_issues"] = validation_result["summary"]["failed"]
                
                if validation_result["summary"]["failed"] > 0:
                    pipeline_result["status"] = "warning"
                    self.logger.warning(f"Validation found {validation_result['summary']['failed']} issues")
            
            # Stage 3: Load
            self.logger.info("Stage 3: Loading data...")
            loading_result = self.load_daily_data(extracted_data)
            pipeline_result["stages"]["loading"] = loading_result
            pipeline_result["summary"]["total_records_loaded"] = loading_result["summary"]["total_records"]
            
            if loading_result["summary"]["failed"] > 0:
                pipeline_result["status"] = "warning"
                self.logger.warning(f"Loading had {loading_result['summary']['failed']} failures")
            
        except Exception as e:
            pipeline_result["status"] = "failed"
            pipeline_result["error"] = str(e)
            self.logger.error(f"Pipeline failed: {e}")
        
        pipeline_result["end_time"] = datetime.now()
        pipeline_result["duration_seconds"] = (pipeline_result["end_time"] - pipeline_result["start_time"]).total_seconds()
        
        self.logger.info(f"Pipeline completed with status: {pipeline_result['status']}")
        
        return pipeline_result
    
    def get_pipeline_status(self) -> Dict[str, Any]:
        """Get current pipeline status."""
        return {
            "plugins_loaded": len(self.plugin_manager.list_plugins()),
            "database_connected": self.db.client is not None,
            "timestamp": datetime.now().isoformat()
        }


# Global pipeline instance
data_pipeline = DataPipeline()
