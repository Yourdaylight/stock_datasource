"""MCP server for stock data service."""

import logging
import importlib
import inspect
from pathlib import Path
from typing import Any, Optional, Tuple
import json
import asyncio
import time as time_module

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
    from fastapi import FastAPI, Request, Header
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from starlette.responses import StreamingResponse
    
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
    
    # --- Dual Authentication Helper ---
    def _authenticate_mcp_request(request: Request) -> Tuple[Optional[dict], str, str]:
        """Authenticate MCP request using sk-xxx API key or nps_enhanced JWT.
        
        Returns:
            (user_info, auth_type, error_message)
            auth_type is 'api_key', 'jwt', or 'none'
        """
        auth_header = request.headers.get("Authorization", "")
        if not auth_header:
            return None, "none", ""
        
        token = auth_header
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
        
        if not token:
            return None, "none", ""
        
        # Try sk-xxx API key (existing system)
        if token.startswith("sk-"):
            try:
                from stock_datasource.modules.mcp_api_key.service import get_mcp_api_key_service
                service = get_mcp_api_key_service()
                valid, user, key_id = service.validate_api_key(token)
                if valid:
                    return {"id": user.get("id", ""), "username": user.get("username", user.get("email", "")), "source": "api_key", "key_id": key_id}, "api_key", ""
                return None, "api_key", "Invalid or expired API key"
            except Exception as e:
                logger.warning(f"API key validation error: {e}")
                return None, "api_key", str(e)
        
        # Try JWT from nps_enhanced
        try:
            from stock_datasource.modules.mcp_api_key.jwt_verifier import verify_nps_jwt
            valid, claims, err = verify_nps_jwt(token)
            if valid:
                scope = claims.get("scope", {})
                return {
                    "id": claims.get("sub", ""),
                    "username": claims.get("sub", ""),
                    "scope": scope,
                    "source": "nps_enhanced",
                    "revision": claims.get("rev", 0),
                }, "jwt", ""
            return None, "jwt", err
        except ImportError:
            logger.debug("JWT verifier not available")
        except Exception as e:
            logger.warning(f"JWT validation error: {e}")
            return None, "jwt", str(e)
        
        return None, "none", "Unrecognized token format"
    
    def _count_records_in_result(result_text: str) -> int:
        """Attempt to count data records in a tool call result.
        
        Heuristic: parse JSON, count rows in lists/tables.
        """
        try:
            data = json.loads(result_text)
            if isinstance(data, list):
                return len(data)
            if isinstance(data, dict):
                # Check common patterns: {"data": [...], "columns": [...]}
                if "data" in data and isinstance(data["data"], list):
                    return len(data["data"])
                if "rows" in data and isinstance(data["rows"], list):
                    return len(data["rows"])
                if "records" in data and isinstance(data["records"], list):
                    return len(data["records"])
                if "items" in data and isinstance(data["items"], list):
                    return len(data["items"])
                # Count as 1 record if it's a single object result
                return 1
        except (json.JSONDecodeError, TypeError):
            pass
        # If we can't parse, count newlines as a rough heuristic
        lines = result_text.strip().split("\n")
        return max(len(lines) - 1, 1)  # subtract header line
    
    async def _log_mcp_usage(user_info: dict, tool_name: str, record_count: int, auth_type: str):
        """Fire-and-forget usage logging."""
        try:
            from stock_datasource.models.database import db_client
            import uuid
            from datetime import datetime
            
            db_client.execute(
                "INSERT INTO mcp_tool_usage_log "
                "(id, user_id, api_key_id, tool_name, record_count, created_at) "
                "VALUES (%(id)s, %(user_id)s, %(api_key_id)s, %(tool_name)s, "
                "%(record_count)s, %(now)s)",
                {
                    "id": str(uuid.uuid4()),
                    "user_id": user_info.get("id", "") or user_info.get("username", ""),
                    "api_key_id": user_info.get("key_id", ""),
                    "tool_name": tool_name,
                    "record_count": record_count,
                    "now": datetime.now(),
                },
            )
        except Exception as e:
            logger.warning(f"Usage logging failed: {e}")
    
    async def _report_usage_to_nps(user_info: dict, tool_name: str, record_count: int):
        """Report usage to nps_enhanced for quota deduction (fire-and-forget)."""
        try:
            import httpx
            from datetime import datetime
            
            scope = user_info.get("scope", {})
            node_id = scope.get("node_id", 0)
            username = user_info.get("username", "") or user_info.get("id", "")
            
            if not username or not node_id:
                return
            
            # nps_enhanced runs on localhost:8081
            nps_url = "http://127.0.0.1:8081/nps/mcp-query/usage-report"
            
            payload = {
                "node_id": node_id,
                "records": [
                    {
                        "username": username,
                        "tool_name": tool_name,
                        "record_count": record_count,
                        "reported_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    }
                ],
            }
            
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.post(nps_url, json=payload)
                if resp.status_code != 200:
                    logger.warning(f"nps usage report failed: status={resp.status_code}, body={resp.text[:200]}")
                else:
                    logger.info(f"Reported usage to nps: user={username}, records={record_count}")
        except Exception as e:
            logger.warning(f"Failed to report usage to nps: {e}", exc_info=True)
    
    # MCP HTTP Streamable protocol endpoint - GET for probing
    @app.get("/messages")
    async def messages_get():
        """Handle GET requests to /messages endpoint (for client probing)."""
        return {
            "status": "ok",
            "message": "MCP server is running. Use POST /messages for MCP protocol communication.",
            "protocol": "streamable-http",
            "version": "2024-11-05"
        }
    
    # MCP HTTP Streamable protocol endpoint - POST for messages
    @app.post("/messages")
    async def messages_endpoint(request: Request):
        """Handle MCP messages via HTTP POST (streamable-http protocol)."""
        try:
            body = await request.json()
            method = body.get("method", "")
            params = body.get("params", {})
            msg_id = body.get("id")
            
            # Authenticate (initialize does not require auth)
            user_info = None
            auth_type = "none"
            if method not in ("initialize",):
                user_info, auth_type, auth_error = _authenticate_mcp_request(request)
                if user_info is None and auth_type != "none":
                    # Token was provided but invalid
                    return JSONResponse(
                        status_code=401,
                        content={
                            "jsonrpc": "2.0",
                            "id": msg_id,
                            "error": {"code": -32001, "message": auth_error or "Authentication failed"}
                        }
                    )
            
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
                
                # Require authentication for tools/call
                if user_info is None:
                    auth_header = request.headers.get("Authorization", "")
                    if auth_header:
                        return JSONResponse(
                            status_code=401,
                            content={
                                "jsonrpc": "2.0",
                                "id": msg_id,
                                "error": {"code": -32001, "message": "Invalid or expired token"}
                            }
                        )
                    return JSONResponse(
                        status_code=401,
                        content={
                            "jsonrpc": "2.0",
                            "id": msg_id,
                            "error": {"code": -32001, "message": "API key required. Provide Authorization: Bearer <token>"}
                        }
                    )
                
                # Quota enforcement for JWT users
                if auth_type == "jwt" and user_info.get("scope"):
                    scope = user_info["scope"]
                    quota = scope.get("quota", {})
                    quota_total = quota.get("total", 0)
                    if quota_total > 0:
                        try:
                            from stock_datasource.models.database import db_client as _quota_db
                            usage_df = _quota_db.query(
                                "SELECT sum(record_count) as total_used "
                                "FROM mcp_tool_usage_log "
                                "WHERE user_id = %(uid)s",
                                {"uid": user_info.get("id", "")},
                            )
                            total_used = int(usage_df.iloc[0]["total_used"]) if not usage_df.empty and usage_df.iloc[0]["total_used"] else 0
                            if total_used >= quota_total:
                                return JSONResponse(
                                    status_code=403,
                                    content={
                                        "jsonrpc": "2.0",
                                        "id": msg_id,
                                        "error": {
                                            "code": -32003,
                                            "message": "Quota exhausted",
                                            "data": {"total": quota_total, "used": total_used}
                                        }
                                    }
                                )
                        except Exception as e:
                            logger.warning(f"Quota check failed (allowing request): {e}")
                
                try:
                    # Convert tool arguments based on expected types
                    service_generators = getattr(request.app.state, 'service_generators', {})
                    converted_args = _convert_tool_arguments(tool_name, tool_args, mcp_server, service_generators)
                    logger.info(f"Tool: {tool_name}, User: {user_info.get('username', 'unknown')}, Auth: {auth_type}")
                    
                    # Call the tool through MCP server's tool manager
                    result = await mcp_server._tool_manager.call_tool(tool_name, converted_args)
                    
                    # Handle ToolResult object
                    result_text = result
                    if hasattr(result, 'text'):
                        result_text = result.text
                    elif hasattr(result, 'content'):
                        result_text = result.content
                    
                    result_str = str(result_text)
                    
                    # Count records and log usage
                    record_count = _count_records_in_result(result_str)
                    await _log_mcp_usage(user_info, tool_name, record_count, auth_type)
                    
                    # Report usage to nps_enhanced for quota deduction
                    if auth_type == "jwt" and record_count > 0:
                        await _report_usage_to_nps(user_info, tool_name, record_count)
                    
                    # Build response with usage metadata
                    response_content = [{"type": "text", "text": result_str}]
                    usage_meta = {"record_count": record_count}
                    
                    # Include quota info for JWT users
                    if auth_type == "jwt" and user_info.get("scope"):
                        scope = user_info["scope"]
                        quota = scope.get("quota", {})
                        if quota:
                            remaining = quota.get("remaining", 0)
                            usage_meta["quota_remaining"] = max(remaining - record_count, 0)
                    
                    response_data = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "content": response_content,
                            "_usage": usage_meta,
                        }
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
    
    # --- SSE compatibility layer for legacy MCP clients (mcp-remote / npx) ---
    # Stores active SSE sessions: session_id -> asyncio.Queue
    _sse_sessions: dict[str, asyncio.Queue] = {}

    @app.get("/sse")
    async def sse_endpoint(request: Request):
        """Legacy SSE endpoint for mcp-remote clients.
        
        Opens a Server-Sent Events stream. Sends an 'endpoint' event
        with the POST URL for the client to send messages to.
        Then streams back JSON-RPC responses as SSE 'message' events.
        """
        import uuid as _uuid
        session_id = str(_uuid.uuid4())
        queue: asyncio.Queue = asyncio.Queue()
        _sse_sessions[session_id] = queue

        # Build the POST URL the client should send messages to
        post_url = f"/messages?sessionId={session_id}"

        async def event_generator():
            # First event: tell the client where to POST
            yield f"event: endpoint\ndata: {post_url}\n\n"
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        data = await asyncio.wait_for(queue.get(), timeout=30)
                        yield f"event: message\ndata: {json.dumps(data)}\n\n"
                    except asyncio.TimeoutError:
                        # Send keep-alive comment
                        yield ": ping\n\n"
            finally:
                _sse_sessions.pop(session_id, None)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Patch the existing POST /messages to also handle SSE session routing
    _original_messages_endpoint = messages_endpoint

    @app.post("/messages", name="messages_endpoint_v2")
    async def messages_endpoint_sse_compat(request: Request):
        """Handle POST /messages for both streamable-http and SSE sessions."""
        session_id = request.query_params.get("sessionId")
        if session_id and session_id in _sse_sessions:
            # This is an SSE-mode request: process & push response to SSE queue
            try:
                body = await request.json()
                # Build a fake direct response by calling original logic
                response = await _original_messages_endpoint(request)
                # Extract JSON body from the JSONResponse
                if hasattr(response, 'body'):
                    result = json.loads(response.body)
                else:
                    result = {"jsonrpc": "2.0", "error": {"code": -32603, "message": "Internal error"}}
                # Push to SSE queue
                await _sse_sessions[session_id].put(result)
                return JSONResponse(content={"ok": True}, status_code=202)
            except Exception as e:
                logger.error(f"SSE compat error: {e}")
                err = {"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}}
                queue = _sse_sessions.get(session_id)
                if queue:
                    await queue.put(err)
                return JSONResponse(content={"ok": True}, status_code=202)
        else:
            # Normal streamable-http mode
            return await _original_messages_endpoint(request)

    # Remove the old route to avoid conflicts (FastAPI keeps the last registered)
    # The new handler already delegates to the original
    app.routes[:] = [
        r for r in app.routes
        if not (hasattr(r, 'name') and r.name == 'messages_endpoint')
    ]

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        return {"status": "ok", "service": "mcp"}
    
    # Usage summary endpoint (for nps_enhanced reconciliation)
    @app.get("/usage/summary")
    async def usage_summary(
        request: Request,
        username: str = "",
        since: str = "",
    ):
        """Return aggregated MCP tool usage for a user.
        
        Protected by X-Report-Key header or the stock policy bearer.
        Used by nps_enhanced for periodic usage reconciliation.
        """
        from stock_datasource.config.settings import settings
        
        report_key = request.headers.get("X-Report-Key", "")
        bearer = request.headers.get("Authorization", "")
        if bearer.lower().startswith("bearer "):
            bearer = bearer[7:].strip()
        
        expected_key = getattr(settings, "MCP_USAGE_REPORT_KEY", None) or ""
        if expected_key and report_key != expected_key and bearer != expected_key:
            return JSONResponse(status_code=401, content={"error": "Unauthorized"})
        
        if not username:
            return JSONResponse(status_code=400, content={"error": "username is required"})
        
        try:
            from stock_datasource.models.database import db_client
            from datetime import datetime
            
            where = "WHERE user_id = %(username)s"
            params = {"username": username}
            
            if since:
                where += " AND created_at >= %(since)s"
                params["since"] = since
            
            # Aggregated totals
            summary_df = db_client.query(
                f"SELECT "
                f"  count() as total_calls, "
                f"  sum(record_count) as total_records "
                f"FROM mcp_tool_usage_log "
                f"{where}",
                params,
            )
            summary = summary_df.to_dict("records") if not summary_df.empty else []
            
            # Per-tool breakdown
            detail_df = db_client.query(
                f"SELECT "
                f"  tool_name, "
                f"  count() as calls, "
                f"  sum(record_count) as records "
                f"FROM mcp_tool_usage_log "
                f"{where} "
                f"GROUP BY tool_name "
                f"ORDER BY records DESC",
                params,
            )
            details = detail_df.to_dict("records") if not detail_df.empty else []
            
            result = {
                "username": username,
                "since": since or "all_time",
                "total_calls": summary[0]["total_calls"] if summary else 0,
                "total_records": summary[0]["total_records"] if summary else 0,
                "by_tool": details,
            }
            return JSONResponse(content=result)
        
        except Exception as e:
            logger.error(f"Usage summary error: {e}")
            return JSONResponse(status_code=500, content={"error": str(e)})
    
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
