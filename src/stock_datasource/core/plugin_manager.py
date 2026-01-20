"""Plugin manager for discovering and managing data plugins."""

import importlib
import pkgutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional, Type
import json

from stock_datasource.core.base_plugin import BasePlugin, PluginCategory, PluginRole
from stock_datasource.utils.logger import logger


class DependencyNotSatisfiedError(Exception):
    """Exception raised when plugin dependencies are not satisfied."""
    
    def __init__(self, plugin_name: str, missing: List[str], missing_data: Optional[Dict[str, str]] = None):
        self.plugin_name = plugin_name
        self.missing = missing
        self.missing_data = missing_data or {}
        
        msg_parts = [f"Plugin '{plugin_name}' dependencies not satisfied."]
        if missing:
            msg_parts.append(f"Missing plugins: {', '.join(missing)}.")
        if missing_data:
            data_msgs = [f"{k}: {v}" for k, v in missing_data.items()]
            msg_parts.append(f"Missing data: {'; '.join(data_msgs)}.")
        msg_parts.append("Please run the dependent plugins first.")
        
        super().__init__(" ".join(msg_parts))


@dataclass
class DependencyCheckResult:
    """Result of dependency check for a plugin."""
    satisfied: bool
    missing_plugins: List[str] = field(default_factory=list)
    missing_data: Dict[str, str] = field(default_factory=dict)
    optional_dependencies: List[str] = field(default_factory=list)
    
    @property
    def has_issues(self) -> bool:
        """Check if there are any dependency issues."""
        return bool(self.missing_plugins or self.missing_data)


class PluginManager:
    """Manages plugin discovery, registration, and lifecycle."""
    
    def __init__(self):
        self.plugins: Dict[str, BasePlugin] = {}
        self.logger = logger.bind(component="PluginManager")
    
    def discover_plugins(self, package_path: str = "stock_datasource.plugins") -> None:
        """Discover and load plugins from the plugins package."""
        try:
            package = importlib.import_module(package_path)
            package_path_obj = Path(package.__file__).parent
            
            self.logger.info(f"Discovering plugins in {package_path}")
            
            for finder, name, ispkg in pkgutil.iter_modules([str(package_path_obj)]):
                if name.startswith('_'):
                    continue
                
                try:
                    module = importlib.import_module(f"{package_path}.{name}")
                    
                    # Look for plugin classes that inherit from BasePlugin
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and 
                            issubclass(attr, BasePlugin) and 
                            attr != BasePlugin):
                            
                            plugin_instance = attr()
                            self.register_plugin(plugin_instance)
                            self.logger.info(f"Discovered plugin: {plugin_instance.name}")
                            
                except Exception as e:
                    self.logger.error(f"Failed to load plugin module {name}: {e}")
                    
        except Exception as e:
            self.logger.error(f"Failed to discover plugins: {e}")
    
    def register_plugin(self, plugin: BasePlugin) -> None:
        """Register a plugin instance."""
        if plugin.name in self.plugins:
            self.logger.warning(f"Plugin {plugin.name} already registered, overwriting")
        
        self.plugins[plugin.name] = plugin
        self.logger.info(f"Registered plugin: {plugin.name}")
    
    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        """Get a plugin by name."""
        return self.plugins.get(name)
    
    def list_plugins(self) -> List[str]:
        """List all registered plugin names."""
        return list(self.plugins.keys())
    
    def get_plugin_info(self) -> List[Dict[str, Any]]:
        """Get information about all registered plugins."""
        info = []
        for plugin_name, plugin in self.plugins.items():
            try:
                info.append({
                    "name": plugin.name,
                    "version": plugin.version,
                    "description": plugin.description,
                    "rate_limit": plugin.get_rate_limit(),
                    "dependencies": plugin.get_dependencies(),
                    "optional_dependencies": plugin.get_optional_dependencies(),
                    "category": plugin.get_category().value,
                    "role": plugin.get_role().value,
                    "enabled": plugin.is_enabled()
                })
            except Exception as e:
                self.logger.warning(f"Failed to get info for plugin {plugin_name}: {e}")
                # Add basic info even if some methods fail
                info.append({
                    "name": plugin_name,
                    "version": getattr(plugin, 'version', '0.0.0'),
                    "description": getattr(plugin, 'description', 'Error loading plugin info'),
                    "rate_limit": 60,
                    "dependencies": [],
                    "optional_dependencies": [],
                    "category": "unknown",
                    "role": "unknown",
                    "enabled": False,
                    "error": str(e)[:200]
                })
        return info
    
    def get_enabled_plugins(self) -> List[BasePlugin]:
        """Get only enabled plugins."""
        return [plugin for plugin in self.plugins.values() if plugin.is_enabled()]
    
    def execute_plugin(self, plugin_name: str, **kwargs) -> Any:
        """Execute a plugin with given parameters."""
        plugin = self.get_plugin(plugin_name)
        if not plugin:
            raise ValueError(f"Plugin {plugin_name} not found")
        
        if not plugin.is_enabled():
            self.logger.warning(f"Plugin {plugin_name} is disabled")
            return None
        
        try:
            self.logger.info(f"Executing plugin: {plugin_name}")
            
            # Get plugin configuration
            config = plugin.get_config()
            self.logger.debug(f"Plugin {plugin_name} config: {config}")
            
            # Extract data
            raw_data = plugin.extract_data(**kwargs)
            
            # Validate data
            if plugin.validate_data(raw_data):
                # Transform data
                transformed_data = plugin.transform_data(raw_data)
                self.logger.info(f"Plugin {plugin_name} executed successfully")
                return transformed_data
            else:
                self.logger.error(f"Data validation failed for plugin {plugin_name}")
                return None
                
        except Exception as e:
            self.logger.error(f"Plugin {plugin_name} execution failed: {e}")
            raise
    
    def reload_plugins(self) -> None:
        """Reload all plugins (useful for development)."""
        self.plugins.clear()
        self.discover_plugins()
        self.logger.info("Plugins reloaded")
    
    def get_plugin_schema(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """Get schema for a specific plugin."""
        plugin = self.get_plugin(plugin_name)
        if plugin:
            return plugin.get_schema()
        return None
    
    def get_plugin_config(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific plugin."""
        plugin = self.get_plugin(plugin_name)
        if plugin:
            return plugin.get_config()
        return None
    
    def check_dependencies(self, plugin_name: str) -> DependencyCheckResult:
        """Check if a plugin's dependencies are satisfied.
        
        This method checks:
        1. Whether all dependent plugins are registered
        2. Whether dependent plugins have data in their tables
        
        Args:
            plugin_name: Name of the plugin to check
        
        Returns:
            DependencyCheckResult with satisfaction status and details
        """
        plugin = self.get_plugin(plugin_name)
        if not plugin:
            return DependencyCheckResult(
                satisfied=False,
                missing_plugins=[plugin_name]
            )
        
        dependencies = plugin.get_dependencies()
        optional_deps = plugin.get_optional_dependencies()
        
        if not dependencies:
            return DependencyCheckResult(
                satisfied=True,
                optional_dependencies=optional_deps
            )
        
        missing_plugins = []
        missing_data = {}
        
        for dep_name in dependencies:
            dep_plugin = self.get_plugin(dep_name)
            
            if not dep_plugin:
                missing_plugins.append(dep_name)
                continue
            
            # Check if dependency has data (with error isolation)
            try:
                if not dep_plugin.has_data():
                    missing_data[dep_name] = "No data in table"
            except Exception as e:
                # Table might not exist or other DB error - treat as missing data
                self.logger.warning(f"Failed to check data for dependency {dep_name}: {e}")
                missing_data[dep_name] = f"Check failed: {str(e)[:100]}"
        
        satisfied = not missing_plugins and not missing_data
        
        return DependencyCheckResult(
            satisfied=satisfied,
            missing_plugins=missing_plugins,
            missing_data=missing_data,
            optional_dependencies=optional_deps
        )
    
    def execute_with_dependencies(
        self,
        plugin_name: str,
        auto_run_deps: bool = False,
        include_optional: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute a plugin with dependency checking.
        
        Args:
            plugin_name: Name of the plugin to execute
            auto_run_deps: If True, automatically run missing dependencies first
            include_optional: If True, also run optional dependencies (e.g., adj_factor)
            **kwargs: Plugin execution parameters
        
        Returns:
            Execution result dictionary
        
        Raises:
            DependencyNotSatisfiedError: If dependencies not satisfied and auto_run_deps is False
            ValueError: If plugin not found
        """
        plugin = self.get_plugin(plugin_name)
        if not plugin:
            raise ValueError(f"Plugin {plugin_name} not found")
        
        if not plugin.is_enabled():
            self.logger.warning(f"Plugin {plugin_name} is disabled")
            return {"status": "skipped", "reason": "Plugin disabled"}
        
        # Check dependencies
        dep_result = self.check_dependencies(plugin_name)
        
        if dep_result.has_issues:
            if not auto_run_deps:
                raise DependencyNotSatisfiedError(
                    plugin_name,
                    dep_result.missing_plugins,
                    dep_result.missing_data
                )
            
            # Auto-run missing dependencies
            self.logger.info(f"Auto-running dependencies for {plugin_name}")
            
            # First check for missing plugins (can't auto-run if not registered)
            if dep_result.missing_plugins:
                raise DependencyNotSatisfiedError(
                    plugin_name,
                    dep_result.missing_plugins,
                    {}
                )
            
            # Run dependencies that are missing data
            dep_results = {}
            for dep_name in dep_result.missing_data.keys():
                self.logger.info(f"Running dependency: {dep_name}")
                try:
                    dep_plugin = self.get_plugin(dep_name)
                    if dep_plugin:
                        result = dep_plugin.run(**kwargs)
                        dep_results[dep_name] = result
                except Exception as e:
                    self.logger.error(f"Failed to run dependency {dep_name}: {e}")
                    raise DependencyNotSatisfiedError(
                        plugin_name,
                        [],
                        {dep_name: f"Execution failed: {str(e)}"}
                    )
        
        # Execute the target plugin
        self.logger.info(f"Executing plugin: {plugin_name}")
        result = plugin.run(**kwargs)
        
        # Execute optional dependencies if requested
        if include_optional and dep_result.optional_dependencies:
            optional_results = {}
            for opt_dep_name in dep_result.optional_dependencies:
                opt_plugin = self.get_plugin(opt_dep_name)
                if opt_plugin and opt_plugin.is_enabled():
                    self.logger.info(f"Running optional dependency: {opt_dep_name}")
                    try:
                        opt_result = opt_plugin.run(**kwargs)
                        optional_results[opt_dep_name] = opt_result
                    except Exception as e:
                        self.logger.warning(f"Optional dependency {opt_dep_name} failed: {e}")
                        optional_results[opt_dep_name] = {"status": "failed", "error": str(e)}
            
            if optional_results:
                result["optional_dependencies_results"] = optional_results
        
        return result
    
    def get_dependency_graph(self) -> Dict[str, List[str]]:
        """Get the dependency graph for all plugins.
        
        Returns:
            Dictionary mapping plugin names to their dependencies
        """
        graph = {}
        for plugin_name, plugin in self.plugins.items():
            try:
                graph[plugin_name] = plugin.get_dependencies()
            except Exception as e:
                self.logger.warning(f"Failed to get dependencies for plugin {plugin_name}: {e}")
                graph[plugin_name] = []
        return graph
    
    def get_reverse_dependencies(self, plugin_name: str) -> List[str]:
        """Get plugins that depend on the given plugin.
        
        Args:
            plugin_name: Name of the plugin
        
        Returns:
            List of plugin names that depend on this plugin
        """
        dependents = []
        for name, plugin in self.plugins.items():
            try:
                if plugin_name in plugin.get_dependencies():
                    dependents.append(name)
            except Exception as e:
                self.logger.warning(f"Failed to check dependencies for plugin {name}: {e}")
        return dependents
    
    def get_plugins_by_category(self, category: PluginCategory) -> List[BasePlugin]:
        """Get plugins by category.
        
        Args:
            category: Plugin category to filter by
        
        Returns:
            List of plugins matching the category
        """
        return [p for p in self.plugins.values() if p.get_category() == category]
    
    def get_plugins_by_role(self, role: PluginRole) -> List[BasePlugin]:
        """Get plugins by role.
        
        Args:
            role: Plugin role to filter by
        
        Returns:
            List of plugins matching the role
        """
        return [p for p in self.plugins.values() if p.get_role() == role]
    
    def get_filtered_plugins(
        self,
        category: Optional[PluginCategory] = None,
        role: Optional[PluginRole] = None
    ) -> List[BasePlugin]:
        """Get plugins filtered by category and/or role.
        
        Args:
            category: Optional category filter
            role: Optional role filter
        
        Returns:
            List of plugins matching the filters
        """
        result = list(self.plugins.values())
        
        if category is not None:
            result = [p for p in result if p.get_category() == category]
        
        if role is not None:
            result = [p for p in result if p.get_role() == role]
        
        return result
    
    def batch_trigger_sync(
        self,
        plugin_names: List[str],
        task_type: str = "incremental",
        include_optional: bool = True,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Batch trigger sync for multiple plugins.
        
        Automatically sorts plugins by dependency order.
        
        Args:
            plugin_names: List of plugin names to sync
            task_type: Sync task type (incremental, full, backfill)
            include_optional: Whether to include optional dependencies
            **kwargs: Additional parameters for plugins
        
        Returns:
            List of task info dictionaries
        """
        # Build dependency graph for the requested plugins
        ordered_plugins = self._topological_sort(plugin_names)
        
        # Add optional dependencies if requested
        if include_optional:
            all_plugins = set(ordered_plugins)
            for name in ordered_plugins:
                plugin = self.get_plugin(name)
                if plugin:
                    for opt_dep in plugin.get_optional_dependencies():
                        if opt_dep not in all_plugins:
                            all_plugins.add(opt_dep)
            # Re-sort with optional dependencies
            ordered_plugins = self._topological_sort(list(all_plugins))
        
        tasks = []
        for plugin_name in ordered_plugins:
            tasks.append({
                "plugin_name": plugin_name,
                "task_type": task_type,
                "order": len(tasks) + 1
            })
        
        return tasks
    
    def _topological_sort(self, plugin_names: List[str]) -> List[str]:
        """Topologically sort plugins by dependencies.
        
        Args:
            plugin_names: List of plugin names to sort
        
        Returns:
            Sorted list of plugin names (dependencies first)
        """
        # Build adjacency list
        graph = {}
        in_degree = {}
        all_names = set(plugin_names)
        
        # Add dependencies that are in the requested list
        for name in plugin_names:
            plugin = self.get_plugin(name)
            if plugin:
                deps = plugin.get_dependencies()
                # Only consider dependencies that are in the requested list
                graph[name] = [d for d in deps if d in all_names]
            else:
                graph[name] = []
            in_degree[name] = 0
        
        # Calculate in-degrees
        for name in plugin_names:
            for dep in graph[name]:
                if dep in in_degree:
                    in_degree[name] += 1
        
        # Kahn's algorithm
        queue = [name for name in plugin_names if in_degree[name] == 0]
        result = []
        
        while queue:
            node = queue.pop(0)
            result.append(node)
            
            for name in plugin_names:
                if node in graph[name]:
                    in_degree[name] -= 1
                    if in_degree[name] == 0 and name not in result:
                        queue.append(name)
        
        # If there are remaining nodes, there's a cycle - just append them
        for name in plugin_names:
            if name not in result:
                result.append(name)
        
        return result


# Global plugin manager instance
plugin_manager = PluginManager()
