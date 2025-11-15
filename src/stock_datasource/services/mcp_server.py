"""MCP server for stock data service."""

import logging
import importlib
import inspect
from pathlib import Path
import json
from datetime import datetime

from fastmcp import FastMCP

from stock_datasource.core.service_generator import ServiceGenerator
from stock_datasource.core.base_service import BaseService

logger = logging.getLogger(__name__)

# Connection tracking
_connection_count = 0
_connection_history = []

# Global cache for services
_services_cache = {}


def _get_or_create_service(service_class, service_name: str):
    """Get or create service instance (lazy initialization)."""
    if service_name not in _services_cache:
        try:
            _services_cache[service_name] = service_class()
        except Exception as e:
            logger.warning(f"Failed to initialize service {service_name}: {e}")
            return None
    return _services_cache[service_name]


def _discover_services() -> list[tuple[str, type]]:
    """Dynamically discover all service classes from plugins directory.
    
    Returns:
        List of (service_name, service_class) tuples
    """
    services = []
    plugins_dir = Path(__file__).parent.parent / "plugins"
    
    if not plugins_dir.exists():
        logger.warning(f"Plugins directory not found: {plugins_dir}")
        return services
    
    # Iterate through each plugin directory
    for plugin_dir in plugins_dir.iterdir():
        if not plugin_dir.is_dir() or plugin_dir.name.startswith("_"):
            continue
        
        service_module_path = plugin_dir / "service.py"
        if not service_module_path.exists():
            continue
        
        try:
            # Dynamically import the service module
            module_name = f"stock_datasource.plugins.{plugin_dir.name}.service"
            module = importlib.import_module(module_name)
            
            # Find all BaseService subclasses in the module
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    issubclass(obj, BaseService) and 
                    obj is not BaseService and
                    obj.__module__ == module_name):
                    
                    # Use plugin directory name as service prefix
                    service_name = plugin_dir.name
                    services.append((service_name, obj))
                    logger.info(f"Discovered service: {service_name} -> {obj.__name__}")
        
        except Exception as e:
            logger.warning(f"Failed to discover services in {plugin_dir.name}: {e}")
    
    return services


def _convert_tool_arguments(tool_name: str, arguments: dict, mcp_server: FastMCP, service_generators: dict = None) -> dict:
    """Convert tool arguments to correct types based on tool definition.
    
    Args:
        tool_name: Name of the tool (e.g., "tushare_daily_get_latest_daily")
        arguments: Raw arguments from MCP client
        mcp_server: FastMCP server instance
        service_generators: Dict of service generators for type info
    
    Returns:
        Converted arguments with correct types
    """
    try:
        # Extract service prefix and method name from tool_name
        # Format: "{service_prefix}_{method_name}"
        # Try to find the service prefix by checking available generators
        service_prefix = None
        method_name = None
        
        if service_generators:
            # Try each service prefix to find a match
            for prefix in service_generators.keys():
                if tool_name.startswith(prefix + '_'):
                    service_prefix = prefix
                    method_name = tool_name[len(prefix) + 1:]
                    break
        
        if not service_prefix or not method_name:
            return arguments
        
        # Get service generator if available
        if service_generators and service_prefix in service_generators:
            generator = service_generators[service_prefix]
            methods = generator.methods
            
            if method_name in methods:
                method_info = methods[method_name]
                type_hints = method_info.get('type_hints', {})
                
                converted = {}
                for arg_name, arg_value in arguments.items():
                    arg_type = type_hints.get(arg_name, str)
                    
                    # Convert based on type hint
                    if arg_type == list or (hasattr(arg_type, '__origin__') and arg_type.__origin__ is list):
                        # Convert to list
                        if isinstance(arg_value, str):
                            if ',' in arg_value:
                                converted[arg_name] = [s.strip() for s in arg_value.split(',')]
                            else:
                                converted[arg_name] = [arg_value]
                        elif isinstance(arg_value, list):
                            converted[arg_name] = arg_value
                        else:
                            converted[arg_name] = [arg_value]
                    
                    elif arg_type == int:
                        converted[arg_name] = int(arg_value) if isinstance(arg_value, str) else arg_value
                    
                    elif arg_type == float:
                        converted[arg_name] = float(arg_value) if isinstance(arg_value, str) else arg_value
                    
                    elif arg_type == bool:
                        if isinstance(arg_value, str):
                            converted[arg_name] = arg_value.lower() in ('true', '1', 'yes')
                        else:
                            converted[arg_name] = bool(arg_value)
                    
                    else:
                        converted[arg_name] = arg_value
                
                return converted
        
        # Fallback: try to use tool parameters from MCP server
        if hasattr(mcp_server._tool_manager, '_tools'):
            tools_dict = mcp_server._tool_manager._tools
            if tool_name in tools_dict:
                tool = tools_dict[tool_name]
                if tool and hasattr(tool, 'parameters') and tool.parameters:
                    converted = {}
                    properties = tool.parameters.get('properties', {})
                    
                    for arg_name, arg_value in arguments.items():
                        if arg_name not in properties:
                            converted[arg_name] = arg_value
                            continue
                        
                        prop_schema = properties[arg_name]
                        prop_type = prop_schema.get('type', 'string')
                        
                        if prop_type == 'array':
                            if isinstance(arg_value, str):
                                if ',' in arg_value:
                                    converted[arg_name] = [s.strip() for s in arg_value.split(',')]
                                else:
                                    converted[arg_name] = [arg_value]
                            elif isinstance(arg_value, list):
                                converted[arg_name] = arg_value
                            else:
                                converted[arg_name] = [arg_value]
                        
                        elif prop_type == 'integer':
                            converted[arg_name] = int(arg_value) if isinstance(arg_value, str) else arg_value
                        
                        elif prop_type == 'number':
                            converted[arg_name] = float(arg_value) if isinstance(arg_value, str) else arg_value
                        
                        elif prop_type == 'boolean':
                            if isinstance(arg_value, str):
                                converted[arg_name] = arg_value.lower() in ('true', '1', 'yes')
                            else:
                                converted[arg_name] = bool(arg_value)
                        
                        else:
                            converted[arg_name] = arg_value
                    
                    return converted
        
        return arguments
    
    except Exception as e:
        logger.warning(f"Error converting tool arguments: {e}")
        return arguments


def _print_startup_banner(service_count: int, tool_count: int, port: int = 8001):
    """Print beautiful startup banner with configuration."""
    banner = f"""
{'=' * 80}
🚀 Stock Data MCP Server - Starting Up
{'=' * 80}
📊 Configuration:
   • Protocol: MCP (Model Context Protocol)
   • Transport: HTTP Streamable
   • Version: 2024-11-05
   • Server Name: stock-data-service
   • Port: {port}
   
📦 Loaded Resources:
   • Services Discovered: {service_count}
   • Tools Registered: {tool_count}
   
🔌 Endpoints:
   • MCP Messages: http://0.0.0.0:{port}/mcp
   • Health Check: http://0.0.0.0:{port}/health
   • Server Info: http://0.0.0.0:{port}/info
   
📝 Log Level: INFO
🕐 Started At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'=' * 80}
✅ MCP Server is ready to accept connections!
{'=' * 80}
"""
    print(banner)


def _log_connection(client_info: str, method: str):
    """Log incoming connection with timestamp.
    
    Note: Currently not actively used due to streamable-http compatibility.
    Can be enabled for non-streaming endpoints if needed.
    """
    global _connection_count, _connection_history
    _connection_count += 1
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    connection_info = {
        'count': _connection_count,
        'timestamp': timestamp,
        'client': client_info,
        'method': method
    }
    _connection_history.append(connection_info)
    
    # Keep only last 100 connections
    if len(_connection_history) > 100:
        _connection_history.pop(0)
    
    logger.info(f"📨 Connection #{_connection_count} | {timestamp} | Method: {method} | Client: {client_info}")


def create_mcp_server() -> tuple[FastMCP, dict]:
    """Create and configure MCP server with all discovered services.
    
    Returns:
        Tuple of (FastMCP server, dict of service generators)
    """
    server = FastMCP("stock-data-service")
    service_generators = {}
    
    # Discover and register all services
    service_configs = _discover_services()
    
    if not service_configs:
        logger.warning("No services discovered")
        return server, service_generators
    
    # Register tools for each service
    for service_prefix, service_class in service_configs:
        try:
            # Create service instance
            service = _get_or_create_service(service_class, service_prefix)
            if service is None:
                logger.warning(f"Skipping service registration: {service_prefix}")
                continue
            
            generator = ServiceGenerator(service)
            service_generators[service_prefix] = generator
            mcp_tools = generator.generate_mcp_tools()
            
            # Register each tool
            for tool_def in mcp_tools:
                tool_name = tool_def["name"]
                full_tool_name = f"{service_prefix}_{tool_name}"
                
                logger.info(f"Processing tool: {full_tool_name}")
                logger.debug(f"Tool definition: {json.dumps(tool_def, ensure_ascii=False, indent=2)}")
                
                # Get the method to validate it exists
                method = generator.get_tool_handler(tool_name)
                if method is None:
                    logger.warning(f"Tool handler not found: {tool_name}")
                    continue
                
                # Create tool handler using closure with explicit parameters
                def make_tool_handler(generator_ref: ServiceGenerator, tool_name_ref: str, tool_schema: dict):
                    """Create handler with explicit parameters from schema."""
                    try:
                        # Extract parameter names from schema
                        input_schema = tool_schema.get("inputSchema", {})
                        properties = input_schema.get("properties", {})
                        required_params = input_schema.get("required", [])
                        
                        # Build parameter annotations
                        from typing import Optional
                        import inspect
                        
                        # Create parameter list
                        params = []
                        for param_name, param_schema in properties.items():
                            param_type = param_schema.get("type", "string")
                            is_required = param_name in required_params
                            
                            # Map JSON schema types to Python types
                            if param_type == "string":
                                py_type = str
                            elif param_type == "integer":
                                py_type = int
                            elif param_type == "number":
                                py_type = float
                            elif param_type == "boolean":
                                py_type = bool
                            elif param_type == "array":
                                py_type = list
                            else:
                                py_type = str
                            
                            # Add Optional for non-required params
                            if not is_required:
                                py_type = Optional[py_type]
                            
                            params.append(inspect.Parameter(
                                param_name,
                                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                                default=None if not is_required else inspect.Parameter.empty,
                                annotation=py_type
                            ))
                        
                        # Create function with dynamic parameters
                        def handler(*args, **kwargs) -> str:
                            try:
                                # Convert args/kwargs to dict
                                call_kwargs = {}
                                for i, param in enumerate(params):
                                    if i < len(args):
                                        call_kwargs[param.name] = args[i]
                                    elif param.name in kwargs:
                                        call_kwargs[param.name] = kwargs[param.name]
                                
                                method = generator_ref.get_tool_handler(tool_name_ref)
                                # Call method with unpacked kwargs
                                result = method(**call_kwargs)
                                
                                # Format result as JSON string for dict/list, otherwise as string
                                if isinstance(result, (dict, list)):
                                    return json.dumps(result, ensure_ascii=False, indent=2)
                                return str(result)
                            except Exception as e:
                                error_msg = f"Error calling {tool_name_ref}: {str(e)}"
                                logger.error(error_msg)
                                return error_msg
                        
                        # Set function signature AND annotations for FastMCP
                        handler.__signature__ = inspect.Signature(params, return_annotation=str)
                        handler.__annotations__ = {param.name: param.annotation for param in params}
                        handler.__annotations__['return'] = str
                        
                        return handler
                    
                    except Exception as e:
                        logger.error(f"Failed to create handler for {tool_name_ref}: {e}")
                        raise
                
                # Create handler with explicit parameters
                try:
                    handler = make_tool_handler(generator, tool_name, tool_def)
                except Exception as e:
                    import traceback
                    logger.error(f"Failed to create handler for {full_tool_name}: {e}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    continue
                
                # Register tool with MCP server using decorator
                try:
                    server.tool(
                        name=full_tool_name,
                        description=tool_def["description"],
                    )(handler)
                    logger.info(f"Registered MCP tool: {full_tool_name}")
                except Exception as e:
                    import traceback
                    logger.error(f"Failed to register tool {full_tool_name} with FastMCP: {e}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    continue
        
        except Exception as e:
            import traceback
            logger.error(f"Failed to register service {service_prefix}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    return server, service_generators


def create_app():
    """Create FastAPI app with MCP server integrated."""
    # Create MCP server first
    mcp_server, service_generators = create_mcp_server()
    
    # Calculate tool count for banner
    tool_count = 0
    try:
        for generator in service_generators.values():
            tool_count += len(generator.methods)
    except:
        pass
    
    # Get FastMCP's HTTP app (provides native streamable-http transport)
    # This app already has its own lifespan configured
    mcp_http_app = mcp_server.http_app()
    
    # Print startup banner when app starts
    _print_startup_banner(len(service_generators), tool_count)
    
    # Simply return the MCP app directly - it's already a complete FastAPI app
    # with proper lifespan management and /mcp endpoint configured
    return mcp_http_app


if __name__ == "__main__":
    import uvicorn
    
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8001)