"""Plugin system for stock data source."""

from typing import Dict, List, Any, Optional
import importlib
import pkgutil
from pathlib import Path

# Import BasePlugin from core module
from stock_datasource.core.base_plugin import BasePlugin
from stock_datasource.utils.logger import logger


class PluginManager:
    """Manages data plugins."""
    
    def __init__(self):
        self.plugins: Dict[str, BasePlugin] = {}
        self.logger = logger.bind(component="PluginManager")
    
    def discover_plugins(self, package_path: str = "stock_datasource.plugins"):
        """Discover and load plugins from package."""
        try:
            package = importlib.import_module(package_path)
            package_path_obj = Path(package.__file__).parent
            
            for finder, name, ispkg in pkgutil.iter_modules([str(package_path_obj)]):
                if name.startswith('_'):
                    continue
                
                try:
                    module = importlib.import_module(f"{package_path}.{name}")
                    
                    # Look for plugin classes
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
    
    def register_plugin(self, plugin: BasePlugin):
        """Register a plugin."""
        if plugin.name in self.plugins:
            self.logger.warning(f"Plugin {plugin.name} already registered, overwriting")
        
        self.plugins[plugin.name] = plugin
        self.logger.info(f"Registered plugin: {plugin.name}")
    
    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        """Get plugin by name."""
        return self.plugins.get(name)
    
    def list_plugins(self) -> List[str]:
        """List all registered plugin names."""
        return list(self.plugins.keys())
    
    def get_plugin_info(self) -> List[Dict[str, Any]]:
        """Get information about all plugins."""
        info = []
        for plugin in self.plugins.values():
            info.append({
                "name": plugin.name,
                "version": plugin.version,
                "description": plugin.description,
                "rate_limit": plugin.api_rate_limit,
                "dependencies": plugin.get_dependencies()
            })
        return info
    
    def execute_plugin(self, plugin_name: str, **kwargs) -> Any:
        """Execute a plugin."""
        plugin = self.get_plugin(plugin_name)
        if not plugin:
            raise ValueError(f"Plugin {plugin_name} not found")
        
        try:
            self.logger.info(f"Executing plugin: {plugin_name}")
            data = plugin.extract_data(**kwargs)
            
            if plugin.validate_data(data):
                transformed_data = plugin.transform_data(data)
                self.logger.info(f"Plugin {plugin_name} executed successfully")
                return transformed_data
            else:
                self.logger.error(f"Plugin {plugin_name} data validation failed")
                return None
                
        except Exception as e:
            self.logger.error(f"Plugin {plugin_name} execution failed: {e}")
            raise


# Global plugin manager instance
plugin_manager = PluginManager()
