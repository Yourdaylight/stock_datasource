"""
Arena Module

Multi-Agent Strategy Arena API module.
Routes are loaded lazily via modules/__init__.py get_all_routers().
"""

# Do not import router at module level to avoid circular imports
# The router is imported directly in modules/__init__.py::get_all_routers()

__all__ = []
