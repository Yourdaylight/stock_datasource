"""Hong Kong stock data placeholder DAG - limited API calls (10/day)."""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
import pendulum

from utils.logger import logger
from config.settings import settings

# Set timezone
local_tz = pendulum.timezone(settings.TIMEZONE)

default_args = {
    'owner': 'stock-datasource',
    'depends_on_past': False,
    'start_date': days_ago(1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'hk_placeholders',
    default_args=default_args,
    description='Hong Kong stock data placeholder (limited to 10 API calls/day)',
    schedule_interval=None,  # Manual trigger only due to API limits
    timezone=local_tz,
    catchup=False,
    max_active_runs=1,
)


def create_hk_table_structure(**context):
    """Create HK table structures without importing data."""
    try:
        from utils.schema_manager import schema_manager
        from models.schemas import PREDEFINED_SCHEMAS
        
        logger.info("Creating Hong Kong table structures")
        
        # Create HK-specific tables (placeholders)
        hk_tables = [
            'ods_hk_basic',
            'ods_hk_daily',
            'dim_hk_security',
            'fact_hk_daily_bar'
        ]
        
        created_tables = []
        
        for table_name in hk_tables:
            try:
                if table_name in PREDEFINED_SCHEMAS:
                    schema = PREDEFINED_SCHEMAS[table_name]
                    schema_manager.create_table_from_schema(schema)
                    created_tables.append(table_name)
                    logger.info(f"Created HK table: {table_name}")
                else:
                    logger.warning(f"No schema definition found for {table_name}")
                    
            except Exception as e:
                logger.error(f"Failed to create {table_name}: {e}")
                continue
        
        result = {
            "status": "success",
            "tables_created": created_tables,
            "message": f"Created {len(created_tables)} HK table structures"
        }
        
        logger.info("HK table structures created successfully")
        return result
        
    except Exception as e:
        logger.error(f"HK table creation failed: {e}")
        raise


def log_hk_api_limitations(**context):
    """Log HK API limitations and recommendations."""
    try:
        logger.info("Hong Kong Stock Exchange Data API Limitations")
        logger.info("=" * 50)
        logger.info("HK Basic Data: 10 API calls per day")
        logger.info("HK Daily Data: 10 API calls per day")
        logger.info("=" * 50)
        logger.info("Recommendations:")
        logger.info("1. Use manual trigger only when necessary")
        logger.info("2. Consider batch processing for multiple dates")
        logger.info("3. Monitor API usage to avoid hitting limits")
        logger.info("4. Implement caching for HK data")
        logger.info("5. Consider alternative data sources for HK stocks")
        
        result = {
            "status": "success",
            "message": "HK API limitations logged",
            "limitations": {
                "hk_basic_calls_per_day": 10,
                "hk_daily_calls_per_day": 10
            },
            "recommendations": [
                "Use manual trigger only when necessary",
                "Consider batch processing for multiple dates",
                "Monitor API usage to avoid hitting limits",
                "Implement caching for HK data",
                "Consider alternative data sources for HK stocks"
            ]
        }
        
        return result
        
    except Exception as e:
        logger.error(f"HK API limitation logging failed: {e}")
        raise


def sample_hk_data_extraction(**context):
    """Extract a small sample of HK data to test API connectivity."""
    try:
        from utils.extractor import extractor
        
        logger.info("Extracting sample HK data (limited API usage)")
        
        # Get current date
        current_date = datetime.now().strftime('%Y%m%d')
        
        # Extract minimal sample (1 call for basic, 1 call for daily)
        logger.info("Extracting HK basic data sample...")
        hk_basic = extractor.get_hk_basic(list_status="L")
        
        logger.info("Extracting HK daily data sample...")
        hk_daily = extractor.get_hk_daily(trade_date=current_date)
        
        result = {
            "status": "success",
            "sample_date": current_date,
            "hk_basic_records": len(hk_basic),
            "hk_daily_records": len(hk_daily),
            "api_calls_used": 2,
            "api_calls_remaining": 8,
            "message": "Sample HK data extracted successfully"
        }
        
        logger.info(f"Sample HK data extracted: {len(hk_basic)} basic records, "
                   f"{len(hk_daily)} daily records, 2 API calls used")
        
        return result
        
    except Exception as e:
        logger.error(f"HK sample data extraction failed: {e}")
        raise


# Define tasks
create_tables_task = PythonOperator(
    task_id='create_hk_table_structure',
    python_callable=create_hk_table_structure,
    dag=dag,
)

log_limitations_task = PythonOperator(
    task_id='log_hk_api_limitations',
    python_callable=log_hk_api_limitations,
    dag=dag,
)

sample_extraction_task = PythonOperator(
    task_id='sample_hk_data_extraction',
    python_callable=sample_hk_data_extraction,
    dag=dag,
)

# Set task dependencies
create_tables_task >> log_limitations_task >> sample_extraction_task
