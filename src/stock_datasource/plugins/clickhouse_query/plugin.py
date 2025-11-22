"""ClickHouse query plugin."""

from typing import Dict, Any, List
from stock_datasource.core.plugin import BasePlugin
from .service import ClickHouseQueryService


class ClickHouseQueryPlugin(BasePlugin):
    """ClickHouse query plugin."""
    
    def __init__(self):
        super().__init__("clickhouse_query")
        self.service = ClickHouseQueryService()
    
    def get_services(self) -> Dict[str, Any]:
        """Get plugin services."""
        return {
            "clickhouse_query": self.service
        }
    
    def get_schema(self) -> Dict[str, Any]:
        """Get plugin schema."""
        return {
            "name": "clickhouse_query",
            "description": "Generic ClickHouse query service with flexible conditions",
            "version": "1.0.0",
            "methods": [
                {
                    "name": "query_with_conditions",
                    "description": "Execute custom query with conditions",
                    "parameters": {
                        "table": {"type": "string", "required": True},
                        "conditions": {"type": "object", "required": False},
                        "columns": {"type": "array", "required": False},
                        "limit": {"type": "integer", "required": False, "default": 1000},
                        "order_by": {"type": "string", "required": False}
                    }
                },
                {
                    "name": "execute_raw_query",
                    "description": "Execute raw SQL query",
                    "parameters": {
                        "sql": {"type": "string", "required": True},
                        "params": {"type": "array", "required": False}
                    }
                },
                {
                    "name": "get_table_schema",
                    "description": "Get table schema information",
                    "parameters": {
                        "table": {"type": "string", "required": True}
                    }
                },
                {
                    "name": "list_tables",
                    "description": "List all tables in the database",
                    "parameters": {
                        "database": {"type": "string", "required": False}
                    }
                },
                {
                    "name": "get_table_stats",
                    "description": "Get table statistics",
                    "parameters": {
                        "table": {"type": "string", "required": True}
                    }
                }
            ]
        }