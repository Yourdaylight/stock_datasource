"""Base service class for all data query services."""

import inspect
from abc import ABC
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any

from stock_datasource.models.database import db_client


@dataclass
class QueryParam:
    """Query parameter metadata."""

    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None


def query_method(description: str = "", params: list[QueryParam] | None = None):
    """Decorator to mark query methods and attach metadata."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper._query_method = True
        wrapper._query_metadata = {
            "description": description,
            "params": params or [],
            "func": func,
        }
        return wrapper

    return decorator


class BaseService(ABC):
    """Base class for all data query services."""

    def __init__(self, plugin_name: str):
        self.plugin_name = plugin_name
        self.db = db_client

    def get_query_methods(self) -> dict[str, dict[str, Any]]:
        """Extract all query methods with their metadata."""
        methods = {}

        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if hasattr(method, "_query_method") and method._query_method:
                signature = inspect.signature(method)
                type_hints = self._get_type_hints(method)

                methods[name] = {
                    "method": method,
                    "metadata": method._query_metadata,
                    "signature": signature,
                    "type_hints": type_hints,
                    "docstring": inspect.getdoc(method),
                }

        return methods

    @staticmethod
    def _get_type_hints(func: Callable) -> dict[str, type]:
        """Get type hints from function."""
        try:
            return inspect.get_annotations(func)
        except Exception:
            return {}

    @staticmethod
    def python_type_to_json_schema(python_type: type) -> str:
        """Convert Python type to JSON Schema type."""
        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }

        # Handle generic types like List[str], Dict[str, Any]
        origin = getattr(python_type, "__origin__", None)
        if origin is not None:
            return type_map.get(origin, "string")

        return type_map.get(python_type, "string")
