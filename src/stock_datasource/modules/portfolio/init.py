"""Portfolio module initialization."""

import logging
from stock_datasource.utils.schema_manager import schema_manager
from .schemas import PORTFOLIO_SCHEMAS

logger = logging.getLogger(__name__)


def init_portfolio_tables():
    """Initialize portfolio module database tables."""
    logger.info("Initializing portfolio module tables...")
    
    try:
        for table_name, schema in PORTFOLIO_SCHEMAS.items():
            logger.info(f"Creating table: {table_name}")
            schema_manager.create_table_from_schema(schema)
            logger.info(f"✅ Table {table_name} created successfully")
        
        logger.info("🎉 Portfolio module tables initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize portfolio tables: {e}")
        return False


def ensure_portfolio_tables():
    """Ensure portfolio tables exist, create if missing."""
    from stock_datasource.models.database import db_client
    
    missing_tables = []
    for table_name in PORTFOLIO_SCHEMAS.keys():
        if not db_client.table_exists(table_name):
            missing_tables.append(table_name)
    
    if missing_tables:
        logger.info(f"Missing portfolio tables: {missing_tables}")
        return init_portfolio_tables()
    else:
        logger.info("All portfolio tables exist")
        return True