"""HTTP server for stock data service."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import importlib
import inspect
from pathlib import Path

# Load environment variables at module import
from dotenv import load_dotenv
load_dotenv()

from stock_datasource.core.service_generator import ServiceGenerator
from stock_datasource.core.base_service import BaseService

logger = logging.getLogger(__name__)

# Global cache for services
_services_cache = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown events."""
    # Startup
    logger.info("Starting application initialization...")

    # Clear proxy env on startup (safety)
    try:
        from stock_datasource.core.proxy import clear_proxy_settings
        clear_proxy_settings()
        logger.info("Proxy environment cleared on startup")
    except Exception as e:
        logger.warning(f"Proxy cleanup failed: {e}")

    # Initialize auth tables and import whitelist (optional)
    try:
        from stock_datasource.config.settings import settings
        from stock_datasource.modules.auth.service import get_auth_service

        auth_service = get_auth_service()

        # Only import seed file when whitelist is enabled (avoids surprises for default open registration)
        if bool(getattr(settings, "AUTH_EMAIL_WHITELIST_ENABLED", False)):
            email_file = Path(getattr(settings, "AUTH_EMAIL_WHITELIST_FILE", "data/email.txt"))
            if not email_file.is_absolute():
                # Resolve relative path from current working directory (docker: /app)
                email_file = Path.cwd() / email_file

            fallback_candidates = [
                email_file,
                Path.cwd() / "email.txt",
                Path.cwd() / "data" / "email.txt",
            ]
            seed_file = next((p for p in fallback_candidates if p.exists()), None)

            if seed_file:
                imported, skipped = auth_service.import_whitelist_from_file(str(seed_file))
                logger.info(f"Email whitelist imported: {imported} new, {skipped} existing")
            else:
                logger.warning(
                    "Email whitelist enabled but no whitelist file found. "
                    "Set AUTH_EMAIL_WHITELIST_FILE (recommended: data/email.txt)."
                )
    except Exception as e:
        logger.warning(f"Auth initialization failed: {e}")
    
    # Initialize portfolio tables
    try:
        from stock_datasource.modules.portfolio.init import ensure_portfolio_tables
        ensure_portfolio_tables()
    except Exception as e:
        logger.warning(f"Portfolio table initialization failed: {e}")
    
    # Initialize plugin manager
    try:
        from stock_datasource.core.plugin_manager import plugin_manager
        plugin_manager.discover_plugins()
        logger.info(f"Discovered {len(plugin_manager.list_plugins())} plugins")
    except Exception as e:
        logger.warning(f"Plugin discovery failed: {e}")

    # Ensure ClickHouse tables exist (predefined + essential plugin tables)
    # Keep it lightweight and synchronous to avoid long lock contention at runtime.
    try:
        from stock_datasource.config.settings import settings
        from stock_datasource.models.database import db_client
        from stock_datasource.models.schemas import PREDEFINED_SCHEMAS
        from stock_datasource.utils.schema_manager import schema_manager, dict_to_schema
        from stock_datasource.core.plugin_manager import plugin_manager

        # Ensure database exists
        db_client.create_database(settings.CLICKHOUSE_DATABASE)

        # Create predefined tables (meta + core facts) via DDL only (no extra exists checks / changelog writes)
        for schema in PREDEFINED_SCHEMAS.values():
            try:
                db_client.create_table(schema_manager._build_create_table_sql(schema))
            except Exception as inner_e:
                logger.warning(f"Failed to ensure predefined table {schema.table_name}: {inner_e}")

        # Create only the plugin tables required by the default frontend pages
        required_plugins = [
            "tushare_ths_daily",
            "tushare_ths_index",
            "tushare_idx_factor_pro",
            "tushare_index_basic",
            "tushare_etf_fund_daily",
            "tushare_etf_basic",
        ]

        for plugin_name in required_plugins:
            try:
                plugin = plugin_manager.get_plugin(plugin_name)
                if not plugin:
                    logger.warning(f"Required plugin not found: {plugin_name}")
                    continue

                schema_dict = plugin.get_schema()
                if not schema_dict or not schema_dict.get("table_name"):
                    logger.warning(f"Plugin {plugin_name} schema is empty")
                    continue

                schema = dict_to_schema(schema_dict)
                db_client.create_table(schema_manager._build_create_table_sql(schema))
            except Exception as inner_e:
                logger.warning(f"Failed to ensure table for plugin {plugin_name}: {inner_e}")

        logger.info("ClickHouse table initialization completed")
    except Exception as e:
        logger.warning(f"ClickHouse table initialization failed: {e}")
    
    # Start sync task manager（延迟启动，避免与初始化建表并发造成断连）
    try:
        from stock_datasource.modules.datamanage.service import sync_task_manager
        import threading, time
        def _delayed_start():
            try:
                time.sleep(8)
                sync_task_manager.start()
                logger.info("SyncTaskManager started (delayed)")
            except Exception as inner_e:
                logger.warning(f"SyncTaskManager delayed start failed: {inner_e}")
        threading.Thread(target=_delayed_start, daemon=True).start()
    except Exception as e:
        logger.warning(f"SyncTaskManager start failed: {e}")
    
    logger.info("Application initialization completed")
    
    yield  # Application runs here
    
    # Shutdown
    logger.info("Shutting down application...")
    
    # Stop sync task manager
    try:
        from stock_datasource.modules.datamanage.service import sync_task_manager
        sync_task_manager.stop()
        logger.info("SyncTaskManager stopped")
    except Exception as e:
        logger.warning(f"SyncTaskManager stop failed: {e}")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="AI Stock Platform",
        description="AI智能股票分析平台 - HTTP API",
        version="2.0.0",
        lifespan=lifespan,
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Register plugin service routes
    _register_services(app)
    
    # Register module routes (8 business modules)
    _register_module_routes(app)
    
    # Register strategy routes
    _register_strategy_routes(app)
    
    # Register top list routes
    _register_toplist_routes(app)
    
    # Register workflow routes
    _register_workflow_routes(app)
    
    # Register cache routes
    _register_cache_routes(app)
    
    # Health check endpoint with cache stats
    @app.get("/health")
    async def health_check():
        """Health check endpoint with service status."""
        response = {"status": "ok"}
        
        # Check cache service
        try:
            from stock_datasource.services.cache_service import get_cache_service
            cache_service = get_cache_service()
            cache_stats = cache_service.get_stats()
            response["cache"] = cache_stats
        except Exception as e:
            response["cache"] = {"available": False, "error": str(e)}
        
        # Check ClickHouse
        try:
            from stock_datasource.models.database import ClickHouseClient
            client = ClickHouseClient()
            client.execute("SELECT 1")
            response["clickhouse"] = "connected"
        except Exception as e:
            response["clickhouse"] = f"error: {str(e)}"
        
        return response
    
    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "name": "AI Stock Platform",
            "version": "2.0.0",
            "modules": ["chat", "market", "screener", "report", "memory", "datamanage", "portfolio", "backtest", "toplist"]
        }
    
    return app


def _register_module_routes(app: FastAPI) -> None:
    """Register all business module routes."""
    try:
        from stock_datasource.modules import get_all_routers
        
        for prefix, router, tags in get_all_routers():
            app.include_router(
                router,
                prefix=f"/api{prefix}",
                tags=tags,
            )
            logger.info(f"Registered module: {prefix}")
    except Exception as e:
        logger.warning(f"Failed to register module routes: {e}")


def _register_strategy_routes(app: FastAPI) -> None:
    """Register strategy management routes."""
    try:
        from stock_datasource.api.strategy_routes import router as strategy_router
        app.include_router(strategy_router)
        logger.info("Registered strategy routes")
    except Exception as e:
        logger.warning(f"Failed to register strategy routes: {e}")


def _register_toplist_routes(app: FastAPI) -> None:
    """Register top list (龙虎榜) routes."""
    try:
        from stock_datasource.api.toplist_routes import router as toplist_router
        app.include_router(toplist_router)
        logger.info("Registered top list routes")
    except Exception as e:
        logger.warning(f"Failed to register top list routes: {e}")


def _register_workflow_routes(app: FastAPI) -> None:
    """Register workflow management routes."""
    try:
        from stock_datasource.api.workflow_routes import router as workflow_router
        app.include_router(workflow_router)
        logger.info("Registered workflow routes")
    except Exception as e:
        logger.warning(f"Failed to register workflow routes: {e}")


def _register_cache_routes(app: FastAPI) -> None:
    """Register cache management routes."""
    try:
        from stock_datasource.api.cache_routes import router as cache_router
        app.include_router(cache_router)
        logger.info("Registered cache routes")
    except Exception as e:
        logger.warning(f"Failed to register cache routes: {e}")


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


# Create app instance for uvicorn
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
