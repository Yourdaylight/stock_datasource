"""Base list service class for paginated, filterable data queries.

Provides common patterns for:
- Pagination
- Filtering
- Keyword search
- Sorting
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import logging

from stock_datasource.models.database import db_client

logger = logging.getLogger(__name__)


@dataclass
class FilterConfig:
    """Configuration for a filter field."""
    field: str
    label: str
    type: str = "select"  # select, input, date, range
    options_query: Optional[str] = None  # SQL to get options
    options: Optional[List[Dict[str, Any]]] = None  # Static options


@dataclass
class SortConfig:
    """Configuration for sorting."""
    field: str
    direction: str = "ASC"  # ASC or DESC


@dataclass
class ListQueryParams:
    """Common parameters for list queries."""
    page: int = 1
    page_size: int = 20
    keyword: Optional[str] = None
    filters: Dict[str, Any] = field(default_factory=dict)
    sort: Optional[SortConfig] = None


@dataclass
class ListResponse:
    """Standard response for list queries."""
    total: int
    page: int
    page_size: int
    data: List[Dict[str, Any]]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "page": self.page,
            "page_size": self.page_size,
            "data": self.data
        }


class BaseListService(ABC):
    """Base class for services that provide paginated list queries.
    
    Subclasses should implement:
    - table_name: The main table to query
    - get_list_columns(): Columns to select for list view
    - get_search_fields(): Fields to search with keyword
    - get_filter_configs(): Filter configurations
    """
    
    def __init__(self):
        self.db = db_client
    
    @property
    @abstractmethod
    def table_name(self) -> str:
        """Main table name for queries."""
        pass
    
    @abstractmethod
    def get_list_columns(self) -> List[str]:
        """Columns to select for list view."""
        pass
    
    @abstractmethod
    def get_search_fields(self) -> List[str]:
        """Fields to search with keyword (using ILIKE)."""
        pass
    
    def get_filter_configs(self) -> List[FilterConfig]:
        """Filter configurations. Override in subclass."""
        return []
    
    def get_default_sort(self) -> SortConfig:
        """Default sort configuration. Override in subclass."""
        return SortConfig(field="ts_code", direction="ASC")
    
    def _execute_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute query and return results as list of dicts."""
        df = self.db.execute_query(query)
        if df is None or df.empty:
            return []
        return df.to_dict('records')
    
    def _build_where_clause(
        self,
        keyword: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build WHERE clause from keyword and filters."""
        conditions = ["1=1"]
        
        # Keyword search
        if keyword:
            search_fields = self.get_search_fields()
            if search_fields:
                keyword_escaped = keyword.replace("'", "''")
                search_conditions = [
                    f"{field} ILIKE '%{keyword_escaped}%'" 
                    for field in search_fields
                ]
                conditions.append(f"({' OR '.join(search_conditions)})")
        
        # Filters
        if filters:
            for field, value in filters.items():
                if value is not None and value != "":
                    if isinstance(value, str):
                        value_escaped = value.replace("'", "''")
                        conditions.append(f"{field} = '{value_escaped}'")
                    elif isinstance(value, (int, float)):
                        conditions.append(f"{field} = {value}")
                    elif isinstance(value, list) and len(value) > 0:
                        # Handle list values (IN clause)
                        values_str = ", ".join(
                            f"'{v.replace(chr(39), chr(39)+chr(39))}'" if isinstance(v, str) else str(v)
                            for v in value
                        )
                        conditions.append(f"{field} IN ({values_str})")
        
        return " AND ".join(conditions)
    
    def get_list(self, params: ListQueryParams) -> ListResponse:
        """Get paginated list with filters and search.
        
        Args:
            params: Query parameters
            
        Returns:
            ListResponse with total count and data
        """
        where_clause = self._build_where_clause(params.keyword, params.filters)
        
        # Count total
        count_query = f"""
        SELECT count() as total
        FROM {self.table_name}
        WHERE {where_clause}
        """
        count_result = self._execute_query(count_query)
        total = count_result[0].get('total', 0) if count_result else 0
        
        # Get data with pagination
        columns_str = ", ".join(self.get_list_columns())
        offset = (params.page - 1) * params.page_size
        
        sort = params.sort or self.get_default_sort()
        order_clause = f"ORDER BY {sort.field} {sort.direction}"
        
        query = f"""
        SELECT {columns_str}
        FROM {self.table_name}
        WHERE {where_clause}
        {order_clause}
        LIMIT {params.page_size}
        OFFSET {offset}
        """
        
        data = self._execute_query(query)
        
        return ListResponse(
            total=total,
            page=params.page,
            page_size=params.page_size,
            data=data
        )
    
    def get_filter_options(self, filter_field: str) -> List[Dict[str, Any]]:
        """Get available options for a filter field.
        
        Args:
            filter_field: Field name to get options for
            
        Returns:
            List of {value, label, count} dicts
        """
        configs = {c.field: c for c in self.get_filter_configs()}
        config = configs.get(filter_field)
        
        if not config:
            return []
        
        if config.options:
            return config.options
        
        if config.options_query:
            return self._execute_query(config.options_query)
        
        # Default: distinct values from table
        query = f"""
        SELECT DISTINCT {filter_field} as value, 
               {filter_field} as label,
               count() as count
        FROM {self.table_name}
        WHERE {filter_field} IS NOT NULL AND {filter_field} != ''
        GROUP BY {filter_field}
        ORDER BY count DESC
        """
        return self._execute_query(query)
    
    def get_all_filter_options(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get options for all configured filters.
        
        Returns:
            Dict mapping filter field to list of options
        """
        result = {}
        for config in self.get_filter_configs():
            result[config.field] = self.get_filter_options(config.field)
        return result
    
    def get_detail(self, id_field: str, id_value: str) -> Optional[Dict[str, Any]]:
        """Get single record by ID.
        
        Args:
            id_field: ID field name
            id_value: ID value
            
        Returns:
            Record dict or None
        """
        id_escaped = id_value.replace("'", "''")
        query = f"""
        SELECT *
        FROM {self.table_name}
        WHERE {id_field} = '{id_escaped}'
        """
        result = self._execute_query(query)
        return result[0] if result else None
