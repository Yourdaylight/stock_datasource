"""Dynamic service generator for HTTP routes and MCP tools."""

import inspect
from typing import Any, Callable, Dict, List, Optional, Type
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, create_model

from stock_datasource.core.base_service import BaseService


class ServiceGenerator:
    """Generate HTTP routes and MCP tools from service classes."""
    
    def __init__(self, service: BaseService):
        self.service = service
        self.methods = service.get_query_methods()
    
    def generate_http_routes(self) -> APIRouter:
        """Generate FastAPI router with all query methods as endpoints."""
        router = APIRouter()
        
        for method_name, info in self.methods.items():
            # Create request model dynamically
            request_model = self._create_request_model(method_name, info)
            
            # Create response model
            response_model = self._create_response_model(method_name)
            
            # Create endpoint handler with closure to capture method_name and info
            def make_handler(method_name_inner: str, info_inner: Dict):
                async def handler(request: request_model):
                    try:
                        # Convert request to kwargs
                        kwargs = request.model_dump(exclude_unset=True)
                        
                        # Call the service method
                        result = info_inner['method'](**kwargs)
                        
                        return {
                            "status": "success",
                            "data": result,
                            "message": None,
                        }
                    except Exception as e:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Error calling {method_name_inner}: {str(e)}"
                        )
                return handler
            
            # Add route
            router.add_api_route(
                f"/{method_name}",
                make_handler(method_name, info),
                methods=["POST"],
                name=method_name,
                description=info['metadata']['description'],
                response_model=response_model,
            )
        
        return router
    
    def generate_mcp_tools(self) -> List[Dict[str, Any]]:
        """Generate MCP tool definitions."""
        tools = []
        
        for method_name, info in self.methods.items():
            tool = {
                "name": method_name,
                "description": info['metadata']['description'],
                "inputSchema": self._build_input_schema(method_name, info),
            }
            tools.append(tool)
        
        return tools
    
    def get_tool_handler(self, tool_name: str) -> Optional[Callable]:
        """Get handler for a specific tool."""
        if tool_name in self.methods:
            return self.methods[tool_name]['method']
        return None
    
    def _create_request_model(
        self, 
        method_name: str, 
        info: Dict[str, Any]
    ) -> Type[BaseModel]:
        """Create Pydantic request model from method signature."""
        from pydantic import Field
        
        signature = info['signature']
        type_hints = info['type_hints']
        
        fields = {}
        
        for param_name, param in signature.parameters.items():
            if param_name == 'self':
                continue
            
            # Get type annotation
            param_type = type_hints.get(param_name, str)
            
            # Determine if required
            is_required = param.default == inspect.Parameter.empty
            
            # Get description from metadata
            param_description = ""
            for meta_param in info['metadata']['params']:
                if meta_param.name == param_name:
                    param_description = meta_param.description
                    break
            
            # Create field with description
            if is_required:
                fields[param_name] = (param_type, Field(..., description=param_description))
            else:
                fields[param_name] = (param_type, Field(default=param.default, description=param_description))
        
        # Create model
        model_name = f"{method_name.capitalize()}Request"
        return create_model(model_name, **fields)
    
    def _create_response_model(self, method_name: str) -> Type[BaseModel]:
        """Create Pydantic response model."""
        model_name = f"{method_name.capitalize()}Response"
        
        return create_model(
            model_name,
            status=(str, ...),
            data=(Any, ...),
            message=(Optional[str], None),
        )
    
    def _build_input_schema(
        self, 
        method_name: str, 
        info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build JSON Schema for MCP tool input."""
        signature = info['signature']
        type_hints = info['type_hints']
        
        properties = {}
        required = []
        
        for param_name, param in signature.parameters.items():
            if param_name == 'self':
                continue
            
            param_type = type_hints.get(param_name, str)
            json_type = BaseService.python_type_to_json_schema(param_type)
            
            # Get description
            param_description = ""
            for meta_param in info['metadata']['params']:
                if meta_param.name == param_name:
                    param_description = meta_param.description
                    break
            
            properties[param_name] = {
                "type": json_type,
                "description": param_description or f"Parameter: {param_name}",
            }
            
            if param.default == inspect.Parameter.empty:
                required.append(param_name)
        
        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }
