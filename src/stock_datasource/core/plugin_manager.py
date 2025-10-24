"""Plugin manager for discovering and managing data plugins."""

import importlib
import pkgutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Type
import json

from stock_datasource.core.base_plugin import BasePlugin
from stock_datasource.utils.logger import logger


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
        for plugin in self.plugins.values():
            info.append({
                "name": plugin.name,
                "version": plugin.version,
                "description": plugin.description,
                "rate_limit": plugin.get_rate_limit(),
                "dependencies": plugin.get_dependencies(),
                "enabled": plugin.is_enabled()
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


# Global plugin manager instance
plugin_manager = PluginManager()
