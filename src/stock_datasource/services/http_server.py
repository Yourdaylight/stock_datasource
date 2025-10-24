"""HTTP server for stock data service."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import importlib
import inspect
from pathlib import Path

from stock_datasource.core.service_generator import ServiceGenerator
from stock_datasource.core.base_service import BaseService

logger = logging.getLogger(__name__)

# Global cache for services
_services_cache = {}


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="Stock Data Service",
        description="HTTP API for querying stock data",
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
    
    # Register service routes
    _register_services(app)
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        return {"status": "ok"}
    
    return app


def _get_or_create_service(service_class, service_name: str):
    """Get or create service instance (lazy initialization)."""
    if service_name not in _services_cache:
        try:
            _services_cache[service_name] = service_class()
        except Exception as e:
            logger.warning(f"Failed to initialize service {service_name}: {e}")
            # Return a dummy service that will fail gracefully
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


def _register_services(app: FastAPI) -> None:
    """Register all discovered service routes dynamically."""
    service_configs = _discover_services()
    
    if not service_configs:
        logger.warning("No services discovered")
        return
    
    for prefix, service_class in service_configs:
        try:
            # Create service instance
            service = _get_or_create_service(service_class, prefix)
            if service is None:
                logger.warning(f"Skipping service registration: {prefix}")
                continue
            
            generator = ServiceGenerator(service)
            router = generator.generate_http_routes()
            app.include_router(
                router,
                prefix=f"/api/{prefix}",
                tags=[prefix],
            )
            logger.info(f"Registered service: {prefix}")
        except Exception as e:
            logger.error(f"Failed to register service {prefix}: {e}")


if __name__ == "__main__":
    import uvicorn
    
    app = create_app()
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
