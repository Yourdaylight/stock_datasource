"""MCP server for stock data service."""

import logging
import importlib
import inspect
from pathlib import Path
from typing import Any
import json
import asyncio

from fastmcp import FastMCP

from stock_datasource.core.service_generator import ServiceGenerator
from stock_datasource.core.base_service import BaseService

logger = logging.getLogger(__name__)

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
                
                # Get the method signature to create proper handler
                method = generator.get_tool_handler(tool_name)
                if method is None:
                    logger.warning(f"Tool handler not found: {tool_name}")
                    continue
                
                # Get parameter names from the method signature
                sig = inspect.signature(method)
                param_names = [p for p in sig.parameters.keys() if p != 'self']
                
                # Create tool handler with closure
                def make_tool_handler(
                    service_prefix_inner: str,
                    tool_name_inner: str,
                    generator_inner: ServiceGenerator,
                    param_names_inner: list
                ):
                    # Create handler with explicit parameters
                    def handler_factory():
                        # Build handler with explicit parameters
                        if not param_names_inner:
                            def handler() -> str:
                                try:
                                    method = generator_inner.get_tool_handler(tool_name_inner)
                                    result = method()
                                    if isinstance(result, (dict, list)):
                                        return json.dumps(result, ensure_ascii=False, indent=2)
                                    return str(result)
                                except Exception as e:
                                    return f"Error calling {tool_name_inner}: {str(e)}"
                            return handler
                        else:
                            # Create handler with parameters
                            exec_globals = {
                                'generator_inner': generator_inner,
                                'tool_name_inner': tool_name_inner,
                                'json': json,
                            }
                            
                            # Build function signature dynamically
                            params_str = ', '.join(param_names_inner)
                            handler_code = f"""def handler({params_str}) -> str:
    try:
        method = generator_inner.get_tool_handler(tool_name_inner)
        result = method({params_str})
        if isinstance(result, (dict, list)):
            return json.dumps(result, ensure_ascii=False, indent=2)
        return str(result)
    except Exception as e:
        return f"Error calling {{tool_name_inner}}: {{str(e)}}"
"""
                            exec(handler_code, exec_globals)
                            return exec_globals['handler']
                    
                    return handler_factory()
                
                # Create handler
                handler = make_tool_handler(service_prefix, tool_name, generator, param_names)
                
                # Register tool with MCP server using decorator
                server.tool(
                    name=full_tool_name,
                    description=tool_def["description"],
                )(handler)
                
                logger.info(f"Registered MCP tool: {full_tool_name}")
        
        except Exception as e:
            logger.error(f"Failed to register service {service_prefix}: {e}")
    
    return server, service_generators


def create_app():
    """Create FastAPI app with MCP server integrated."""
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    
    app = FastAPI(
        title="Stock Data Service - MCP",
        description="MCP server for querying stock data via HTTP",
        version="1.0.0",
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Create MCP server
    mcp_server, service_generators = create_mcp_server()
    
    # Store MCP server and generators in app state for access in endpoints
    app.state.mcp_server = mcp_server
    app.state.service_generators = service_generators
    
    # MCP HTTP Streamable protocol endpoint
    @app.post("/messages")
    async def messages_endpoint(request: Request):
        """Handle MCP messages via HTTP POST (streamable-http protocol)."""
        try:
            body = await request.json()
            method = body.get("method", "")
            params = body.get("params", {})
            msg_id = body.get("id")
            
            # Handle initialize method
            if method == "initialize":
                response_data = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {}
                        },
                        "serverInfo": {
                            "name": "stock-data-service",
                            "version": "1.0.0"
                        }
                    }
                }
                return JSONResponse(content=response_data)
            
            # Handle tools/list method
            elif method == "tools/list":
                tools = []
                # Get tools from MCP server's tool manager
                try:
                    tool_list = await mcp_server._tool_manager.list_tools()
                    for tool in tool_list:
                        tools.append({
                            "name": tool.name,
                            "description": tool.description or "",
                            "inputSchema": tool.parameters or {
                                "type": "object",
                                "properties": {}
                            }
                        })
                except Exception as e:
                    logger.warning(f"Error listing tools: {e}")
                
                response_data = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"tools": tools}
                }
                return JSONResponse(content=response_data)
            
            # Handle tools/call method
            elif method == "tools/call":
                tool_name = params.get("name")
                tool_args = params.get("arguments", {})
                
                try:
                    # Convert tool arguments based on expected types
                    service_generators = getattr(request.app.state, 'service_generators', {})
                    converted_args = _convert_tool_arguments(tool_name, tool_args, mcp_server, service_generators)
                    logger.info(f"Tool: {tool_name}, Original args: {tool_args}, Converted args: {converted_args}")
                    
                    # Call the tool through MCP server's tool manager
                    result = await mcp_server._tool_manager.call_tool(tool_name, converted_args)
                    
                    # Handle ToolResult object
                    result_text = result
                    if hasattr(result, 'text'):
                        result_text = result.text
                    elif hasattr(result, 'content'):
                        result_text = result.content
                    
                    response_data = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {"content": [{"type": "text", "text": str(result_text)}]}
                    }
                    return JSONResponse(content=response_data)
                except Exception as e:
                    logger.error(f"Error calling tool {tool_name}: {e}")
                    response_data = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {"code": -32603, "message": str(e)}
                    }
                    return JSONResponse(content=response_data)
            
            # Unknown method
            response_data = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Unknown method: {method}"}
            }
            return JSONResponse(content=response_data)
        
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            response_data = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
            return JSONResponse(content=response_data)
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        return {"status": "ok", "service": "mcp"}
    
    # Info endpoint
    @app.get("/info")
    async def info():
        return {
            "name": "Stock Data Service - MCP",
            "version": "1.0.0",
            "messages_endpoint": "/messages",
            "transport": "streamable-http",
            "description": "MCP server accessible via HTTP streamable protocol"
        }
    
    return app


if __name__ == "__main__":
    import uvicorn
    
    app = create_app()
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info",
    )
