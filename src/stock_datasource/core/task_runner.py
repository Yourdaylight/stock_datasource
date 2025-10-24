"""Task runner for plugin-based data ingestion."""

import asyncio
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.core.plugin_manager import plugin_manager
from stock_datasource.core.base_plugin import BasePlugin
from stock_datasource.utils.logger import logger
from stock_datasource.models.database import db_client
from stock_datasource.utils.schema_manager import schema_manager
from stock_datasource.services.metadata import metadata_service


class TaskRunner:
    """Runs plugin-based data ingestion tasks."""
    
    def __init__(self):
        self.logger = logger.bind(component="TaskRunner")
        self.plugin_manager = plugin_manager
        self.db = db_client
        self.schema_manager = schema_manager
        self.metadata_service = metadata_service
    
    def discover_tasks(self, tasks_dir: str = "stock_datasource/tasks") -> List[Dict[str, Any]]:
        """Discover available tasks from task definitions."""
        tasks = []
        
        try:
            # Look for task definition files
            tasks_path = Path(__file__).parent.parent / "tasks"
            if not tasks_path.exists():
                self.logger.warning(f"Tasks directory not found: {tasks_path}")
                return tasks
            
            for task_file in tasks_path.glob("*.json"):
                try:
                    with open(task_file, 'r', encoding='utf-8') as f:
                        task_def = json.load(f)
                        tasks.append(task_def)
                        self.logger.info(f"Discovered task: {task_def.get('name', task_file.stem)}")
                except Exception as e:
                    self.logger.error(f"Failed to load task file {task_file}: {e}")
            
            # Also discover plugin-based tasks
            plugin_tasks = self._discover_plugin_tasks()
            tasks.extend(plugin_tasks)
            
        except Exception as e:
            self.logger.error(f"Failed to discover tasks: {e}")
        
        return tasks
    
    def _discover_plugin_tasks(self) -> List[Dict[str, Any]]:
        """Discover tasks from registered plugins."""
        tasks = []
        
        for plugin_name in self.plugin_manager.list_plugins():
            plugin = self.plugin_manager.get_plugin(plugin_name)
            if plugin:
                task_def = {
                    "name": plugin.name,
                    "type": "plugin",
                    "plugin_name": plugin.name,
                    "description": plugin.description,
                    "enabled": True,
                    "config_schema": plugin.get_config_schema(),
                    "dependencies": plugin.get_dependencies()
                }
                tasks.append(task_def)
        
        return tasks
    
    def run_task(self, task_def: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Run a single task."""
        task_name = task_def.get('name', 'unknown')
        task_id = f"{task_name}_{int(time.time())}"
        
        self.logger.info(f"Starting task: {task_name}")
        
        result = {
            "task_id": task_id,
            "task_name": task_name,
            "start_time": datetime.now(),
            "status": "running",
            "data": None,
            "error": None,
            "duration_seconds": 0
        }
        
        try:
            # Log task start
            self.metadata_service.log_ingestion_start(
                task_id=task_id,
                api_name=task_name,
                table_name=task_def.get('table_name', task_name)
            )
            
            # Check task type
            task_type = task_def.get('type', 'plugin')
            
            if task_type == 'plugin':
                result = self._run_plugin_task(task_def, task_id, **kwargs)
            else:
                result = self._run_custom_task(task_def, task_id, **kwargs)
            
            # Log task completion
            self.metadata_service.log_ingestion_complete(
                task_id=task_id,
                records_processed=result.get('records_processed', 0),
                status=result['status'],
                error_message=result.get('error')
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Task {task_name} failed: {e}")
            result['status'] = 'failed'
            result['error'] = str(e)
            result['end_time'] = datetime.now()
            result['duration_seconds'] = (result['end_time'] - result['start_time']).total_seconds()
            
            # Log failure
            self.metadata_service.log_ingestion_complete(
                task_id=task_id,
                records_processed=0,
                status='failed',
                error_message=str(e)
            )
            
            return result
    
    def _run_plugin_task(self, task_def: Dict[str, Any], task_id: str, **kwargs) -> Dict[str, Any]:
        """Run a plugin-based task."""
        plugin_name = task_def['plugin_name']
        plugin = self.plugin_manager.get_plugin(plugin_name)
        
        if not plugin:
            raise ValueError(f"Plugin {plugin_name} not found")
        
        result = {
            "task_id": task_id,
            "task_name": task_def['name'],
            "start_time": datetime.now(),
            "status": "running",
            "data": None,
            "error": None,
            "records_processed": 0
        }
        
        try:
            # Ensure table exists
            schema = plugin.get_schema()
            table_name = schema['table_name']
            
            self.logger.info(f"Ensuring table {table_name} exists for plugin {plugin_name}")
            self.schema_manager.create_table_from_schema(
                self._schema_dict_to_object(schema)
            )
            
            # Extract data
            self.logger.info(f"Extracting data with plugin {plugin_name}")
            raw_data = plugin.extract_data(**kwargs)
            
            if raw_data is None or len(raw_data) == 0:
                self.logger.warning(f"No data extracted from plugin {plugin_name}")
                result['status'] = 'no_data'
                result['records_processed'] = 0
            else:
                # Validate data
                if plugin.validate_data(raw_data):
                    # Transform data
                    transformed_data = plugin.transform_data(raw_data)
                    
                    # Load data
                    self.logger.info(f"Loading {len(transformed_data)} records into {table_name}")
                    self._load_data(table_name, transformed_data)
                    
                    result['data'] = transformed_data
                    result['records_processed'] = len(transformed_data)
                    result['status'] = 'success'
                    
                    self.logger.info(f"Plugin {plugin_name} completed successfully with {len(transformed_data)} records")
                else:
                    self.logger.error(f"Data validation failed for plugin {plugin_name}")
                    result['status'] = 'validation_failed'
                    result['records_processed'] = 0
            
            result['end_time'] = datetime.now()
            result['duration_seconds'] = (result['end_time'] - result['start_time']).total_seconds()
            return result
            
        except Exception as e:
            self.logger.error(f"Plugin task {plugin_name} failed: {e}")
            result['status'] = 'failed'
            result['error'] = str(e)
            result['end_time'] = datetime.now()
            result['duration_seconds'] = (result['end_time'] - result['start_time']).total_seconds()
            return result
    
    def _run_custom_task(self, task_def: Dict[str, Any], task_id: str, **kwargs) -> Dict[str, Any]:
        """Run a custom task definition."""
        # Implementation for custom task types
        raise NotImplementedError("Custom tasks not yet implemented")
    
    def _schema_dict_to_object(self, schema_dict: Dict[str, Any]) -> Any:
        """Convert schema dictionary to schema object."""
        from stock_datasource.models.schemas import TableSchema, ColumnDefinition, TableType
        
        columns = []
        for col_def in schema_dict.get('columns', []):
            column = ColumnDefinition(
                name=col_def['name'],
                data_type=col_def['data_type'],
                nullable=col_def.get('nullable', True),
                default_value=col_def.get('default'),
                comment=col_def.get('comment')
            )
            columns.append(column)
        
        return TableSchema(
            table_name=schema_dict['table_name'],
            table_type=TableType(schema_dict.get('table_type', 'ods')),
            columns=columns,
            partition_by=schema_dict.get('partition_by'),
            order_by=schema_dict.get('order_by', []),
            engine=schema_dict.get('engine', 'ReplacingMergeTree'),
            engine_params=schema_dict.get('engine_params'),
            comment=schema_dict.get('comment')
        )
    
    def _load_data(self, table_name: str, data: Any) -> None:
        """Load data into database."""
        if isinstance(data, pd.DataFrame):
            self.db.insert_dataframe(table_name, data)
        else:
            # Handle other data types
            raise ValueError(f"Unsupported data type: {type(data)}")
    
    def run_task_chain(self, task_chain: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
        """Run a chain of tasks with dependencies."""
        results = []
        
        for task_def in task_chain:
            try:
                # Check dependencies
                dependencies = task_def.get('dependencies', [])
                for dep in dependencies:
                    dep_result = next((r for r in results if r['task_name'] == dep), None)
                    if not dep_result or dep_result['status'] != 'success':
                        raise ValueError(f"Dependency {dep} not satisfied")
                
                # Run task
                result = self.run_task(task_def, **kwargs)
                results.append(result)
                
                # Stop chain if task failed
                if result['status'] == 'failed':
                    self.logger.error(f"Task chain stopped due to failure in {task_def['name']}")
                    break
                    
            except Exception as e:
                self.logger.error(f"Task {task_def['name']} in chain failed: {e}")
                results.append({
                    "task_name": task_def['name'],
                    "status": "failed",
                    "error": str(e),
                    "start_time": datetime.now(),
                    "end_time": datetime.now(),
                    "duration_seconds": 0
                })
                break
        
        return results


# Global task runner instance
task_runner = TaskRunner()
