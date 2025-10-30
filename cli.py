"""Command line interface for stock data source."""

import click
from datetime import datetime, timedelta
import sys
import os
from pathlib import Path
from typing import Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Clear cached ClickHouse environment variables to ensure .env file is loaded fresh
# This is critical because pydantic-settings prioritizes environment variables over .env
# Only clear ClickHouse-related variables, keep others like TUSHARE_TOKEN
env_vars_to_clear = [
    'CLICKHOUSE_HOST', 'CLICKHOUSE_PORT', 'CLICKHOUSE_USER', 
    'CLICKHOUSE_PASSWORD', 'CLICKHOUSE_DATABASE'
]
for var in env_vars_to_clear:
    os.environ.pop(var, None)

from stock_datasource.services.ingestion import ingestion_service
from stock_datasource.services.metadata import metadata_service
from stock_datasource.utils.schema_manager import schema_manager
from stock_datasource.utils.logger import logger
from stock_datasource.config.settings import settings, reload_settings


@click.group()
def cli():
    """Stock Data Source CLI - Local financial database for A-share/HK stocks."""
    # Reload settings to ensure latest .env configuration is loaded
    reload_settings()
    # Reconnect database with new settings
    from stock_datasource.models.database import db_client
    db_client.reconnect()


@cli.command()
@click.option('--table', help='Specific table to create')
@click.option('--timeout', default=300, help='Timeout in seconds (default: 300)')
def init_db(table, timeout):
    """Initialize database and create tables."""
    import signal
    import time
    
    def timeout_handler(signum, frame):
        raise TimeoutError(f"Database initialization timed out after {timeout} seconds")
    
    # Reload settings and reconnect to database
    from stock_datasource.models.database import db_client
    from stock_datasource.config.settings import reload_settings
    reload_settings()
    db_client.reconnect()
    
    # Set timeout
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout)
    
    try:
        click.echo("Initializing database...")
        start_time = time.time()
        
        # Create database
        from stock_datasource.models.database import db_client
        db_client.create_database(settings.CLICKHOUSE_DATABASE)
        click.echo("✓ Database created or already exists")
        
        if table:
            # Create specific table
            from stock_datasource.core.plugin_manager import plugin_manager
            from stock_datasource.models.schemas import PREDEFINED_SCHEMAS, TableSchema, ColumnDefinition, TableType
            
            # Try to load from plugins first
            plugin_manager.discover_plugins()
            
            # Search in all plugins for the table
            table_found = False
            for plugin_name in plugin_manager.list_plugins():
                plugin = plugin_manager.get_plugin(plugin_name)
                schema_dicts = plugin.get_schemas()
                for schema_dict in schema_dicts:
                    if schema_dict['table_name'] == table:
                        click.echo(f"Creating table: {table} (from plugin {plugin_name})")
                        schema = _dict_to_schema(schema_dict)
                        schema_manager.create_table_from_schema(schema)
                        click.echo(f"✓ Table {table} created successfully")
                        table_found = True
                        break
                if table_found:
                    break
            
            if not table_found:
                # Fall back to metadata schemas
                if table in PREDEFINED_SCHEMAS:
                    schema = PREDEFINED_SCHEMAS[table]
                    click.echo(f"Creating table: {table} (metadata)")
                    schema_manager.create_table_from_schema(schema)
                    click.echo(f"✓ Table {table} created successfully")
                else:
                    click.echo(f"✗ Table {table} not found in plugins or predefined schemas", err=True)
                    return
        else:
            # Create all plugin tables + metadata tables
            from stock_datasource.core.plugin_manager import plugin_manager
            from stock_datasource.models.schemas import PREDEFINED_SCHEMAS
            
            # Discover plugins first
            plugin_manager.discover_plugins()
            
            click.echo("Creating all plugin tables...")
            for plugin_name in plugin_manager.list_plugins():
                try:
                    plugin = plugin_manager.get_plugin(plugin_name)
                    # Get all schemas from plugin (supports multiple schema files)
                    schema_dicts = plugin.get_schemas()
                    for schema_dict in schema_dicts:
                        # Convert dict to TableSchema object
                        schema = _dict_to_schema(schema_dict)
                        click.echo(f"Creating table: {schema.table_name} (from {plugin_name})")
                        schema_manager.create_table_from_schema(schema)
                        click.echo(f"✓ Table {schema.table_name} created successfully")
                except Exception as e:
                    click.echo(f"✗ Failed to create table for {plugin_name}: {e}", err=True)
            
            click.echo("Creating metadata tables...")
            for table_name, schema in PREDEFINED_SCHEMAS.items():
                try:
                    click.echo(f"Creating table: {table_name}")
                    schema_manager.create_table_from_schema(schema)
                    click.echo(f"✓ Table {table_name} created successfully")
                except Exception as e:
                    click.echo(f"✗ Failed to create table {table_name}: {e}", err=True)
            
            click.echo("✓ All tables created successfully")
        
        elapsed_time = time.time() - start_time
        click.echo(f"✓ Database initialization completed in {elapsed_time:.2f} seconds")
        
    except TimeoutError as e:
        click.echo(f"✗ {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"✗ Database initialization failed: {e}", err=True)
        sys.exit(1)
    finally:
        # Cancel timeout
        signal.alarm(0)


@cli.command()
@click.option('--date', required=True, help='Trade date in YYYYMMDD format')
@click.option('--no-quality-checks', is_flag=True, help='Skip quality checks')
@click.option('--ignore-schedule', is_flag=True, help='Ignore plugin schedule and extract all data')
def ingest_daily(date, no_quality_checks, ignore_schedule):
    """Ingest daily data for a specific date."""
    click.echo(f"Ingesting daily data for {date}...")
    
    try:
        # Ensure all tables exist before ingesting
        click.echo("Checking database tables...")
        _ensure_tables_exist(silent=True)
        
        result = ingestion_service.ingest_daily_data(
            trade_date=date,
            run_quality_checks=not no_quality_checks,
            check_schedule=not ignore_schedule
        )
        
        click.echo(f"Ingestion status: {result['status']}")
        click.echo(f"Duration: {result.get('duration_seconds', 0):.2f} seconds")
        click.echo(f"Tables processed: {len(result.get('loading', {}).get('tables_processed', []))}")
        
        if result['status'] == 'failed':
            click.echo(f"Error: {result.get('error', 'Unknown error')}", err=True)
            sys.exit(1)
        elif result['status'] == 'warning':
            click.echo("Completed with warnings - check logs for details")
        
        sys.exit(0)
    except Exception as e:
        click.echo(f"Daily ingestion failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--start-date', required=True, help='Start date in YYYYMMDD format')
@click.option('--end-date', required=True, help='End date in YYYYMMDD format')
@click.option('--no-quality-checks', is_flag=True, help='Skip quality checks')
def backfill(start_date, end_date, no_quality_checks):
    """Backfill data for a date range."""
    click.echo(f"Backfilling data from {start_date} to {end_date}...")
    
    try:
        # Reload settings and reconnect to database
        from stock_datasource.models.database import db_client
        from stock_datasource.config.settings import reload_settings
        reload_settings()
        db_client.reconnect()
        
        # Ensure all tables exist before backfilling
        click.echo("Checking database tables...")
        _ensure_tables_exist(silent=False)
        click.echo("")
        
        result = ingestion_service.backfill_data(
            start_date=start_date,
            end_date=end_date,
            run_quality_checks=not no_quality_checks
        )
        
        click.echo(f"Backfill status: {result['status']}")
        click.echo(f"Duration: {result.get('duration_seconds', 0):.2f} seconds")
        click.echo(f"Dates processed: {result['summary']['total_dates']}")
        click.echo(f"Successful: {result['summary']['successful']}")
        click.echo(f"Warnings: {result['summary']['warnings']}")
        click.echo(f"Failed: {result['summary']['failed']}")
        
        if result['status'] == 'failed':
            click.echo(f"Error: {result.get('error', 'Unknown error')}", err=True)
            sys.exit(1)
        
    except Exception as e:
        click.echo(f"Backfill failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--date', help='Specific date in YYYYMMDD format')
@click.option('--start-date', help='Start date in YYYYMMDD format')
@click.option('--end-date', help='End date in YYYYMMDD format')
def status(date, start_date, end_date):
    """Check ingestion status."""
    try:
        if date:
            # Check specific date
            result = ingestion_service.get_ingestion_status(date)
            click.echo(f"Ingestion status for {date}: {result['overall_status']}")
            
            if 'table_status' in result:
                for table, status in result['table_status'].items():
                    if status.get('has_data'):
                        click.echo(f"  {table}: {status['record_count']} records")
                    else:
                        click.echo(f"  {table}: no data")
        
        else:
            # Get statistics for date range
            stats = metadata_service.get_ingestion_statistics(start_date, end_date)
            
            if 'error' in stats:
                click.echo(f"Error: {stats['error']}", err=True)
                return
            
            click.echo("Ingestion Statistics:")
            click.echo(f"  Total tasks: {stats['summary']['total_tasks']}")
            click.echo(f"  Successful: {stats['summary']['successful_tasks']}")
            click.echo(f"  Failed: {stats['summary']['failed_tasks']}")
            click.echo(f"  Total records: {stats['summary']['total_records']}")
            
            if 'by_api' in stats:
                click.echo("\nBy API:")
                for api, api_stats in stats['by_api'].items():
                    click.echo(f"  {api}: {api_stats['total_tasks']} tasks, "
                             f"{api_stats['total_records']} records")
        
    except Exception as e:
        click.echo(f"Status check failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--table', required=True, help='Table name to check')
def coverage(table):
    """Check data coverage for a table."""
    try:
        result = metadata_service.get_data_coverage(table)
        
        if 'error' in result:
            click.echo(f"Error: {result['error']}", err=True)
            return
        
        click.echo(f"Data coverage for {table}:")
        click.echo(f"  Date range: {result['date_range']['min_date']} to {result['date_range']['max_date']}")
        click.echo(f"  Total records: {result['statistics']['total_records']}")
        click.echo(f"  Unique dates: {result['statistics']['unique_dates']}")
        click.echo(f"  Expected dates: {result['statistics']['expected_dates']}")
        click.echo(f"  Coverage: {result['statistics']['coverage_percentage']:.1f}%")
        
    except Exception as e:
        click.echo(f"Coverage check failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--date', required=True, help='Date in YYYYMMDD format')
def quality_check(date):
    """Run quality checks for a specific date."""
    try:
        from stock_datasource.utils.quality_checks import quality_checker
        
        click.echo(f"Running quality checks for {date}...")
        
        result = quality_checker.run_all_checks(date)
        
        click.echo(f"Quality check status: {result['overall_status']}")
        click.echo(f"Total checks: {result['summary']['total_checks']}")
        click.echo(f"Passed: {result['summary']['passed']}")
        click.echo(f"Warning: {result['summary']['warning']}")
        click.echo(f"Failed: {result['summary']['failed']}")
        
        if result['overall_status'] != 'passed':
            click.echo("\nIssues found:")
            for check in result['checks']:
                if check['status'] != 'passed':
                    click.echo(f"  {check['check_name']}: {check['status']}")
                    if 'issues' in check:
                        for issue in check['issues']:
                            click.echo(f"    - {issue}")
        
    except Exception as e:
        click.echo(f"Quality check failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--days', default=30, help='Number of days to keep')
def cleanup(days):
    """Clean up old data versions."""
    try:
        click.echo(f"Cleaning up data older than {days} days...")
        
        result = ingestion_service.cleanup_old_data(days_to_keep=days)
        
        click.echo(f"Cleanup status: {result['status']}")
        click.echo(f"Tables cleaned: {len(result.get('tables_cleaned', []))}")
        
        if result['status'] == 'failed':
            click.echo(f"Error: {result.get('error', 'Unknown error')}", err=True)
            sys.exit(1)
        
    except Exception as e:
        click.echo(f"Cleanup failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--date', help='Generate report for specific date (YYYYMMDD)')
def report(date):
    """Generate daily report."""
    try:
        if not date:
            date = datetime.now().strftime('%Y%m%d')
        
        click.echo(f"Generating daily report for {date}...")
        
        result = metadata_service.generate_daily_report(date)
        
        if 'error' in result:
            click.echo(f"Error: {result['error']}", err=True)
            return
        
        click.echo(f"Report status: {result['summary']['overall_status']}")
        
        if result['summary']['issues']:
            click.echo("Issues:")
            for issue in result['summary']['issues']:
                click.echo(f"  - {issue}")
        
        # Show key statistics
        if 'ingestion_statistics' in result:
            stats = result['ingestion_statistics']
            if 'summary' in stats:
                click.echo(f"Total tasks: {stats['summary']['total_tasks']}")
                click.echo(f"Successful: {stats['summary']['successful_tasks']}")
                click.echo(f"Failed: {stats['summary']['failed_tasks']}")
        
    except Exception as e:
        click.echo(f"Report generation failed: {e}", err=True)
        sys.exit(1)


def _dict_to_schema(schema_dict: dict) -> Any:
    """Convert schema dictionary to TableSchema object."""
    from stock_datasource.models.schemas import TableSchema, ColumnDefinition, TableType
    
    # Convert columns
    columns = []
    for col_dict in schema_dict.get('columns', []):
        col = ColumnDefinition(
            name=col_dict['name'],
            data_type=col_dict['data_type'],
            nullable=col_dict.get('nullable', True),
            default_value=col_dict.get('default'),
            comment=col_dict.get('comment')
        )
        columns.append(col)
    
    # Get table type
    table_type_str = schema_dict.get('table_type', 'ods')
    table_type = TableType(table_type_str)
    
    # Create TableSchema
    schema = TableSchema(
        table_name=schema_dict['table_name'],
        table_type=table_type,
        columns=columns,
        partition_by=schema_dict.get('partition_by'),
        order_by=schema_dict.get('order_by', []),
        engine=schema_dict.get('engine', 'ReplacingMergeTree'),
        engine_params=schema_dict.get('engine_params'),
        comment=schema_dict.get('comment')
    )
    
    return schema


def _ensure_tables_exist(silent: bool = False) -> None:
    """
    Ensure all required tables exist, create them if not.
    
    Args:
        silent: If True, suppress output messages
    """
    from stock_datasource.models.database import db_client
    from stock_datasource.core.plugin_manager import plugin_manager
    from stock_datasource.models.schemas import PREDEFINED_SCHEMAS
    
    try:
        # Create database if not exists
        db_client.create_database(settings.CLICKHOUSE_DATABASE)
        if not silent:
            click.echo("✓ Database ready")
        
        # Discover plugins
        plugin_manager.discover_plugins()
        
        # Create all plugin tables
        tables_created = 0
        tables_existed = 0
        
        for plugin_name in plugin_manager.list_plugins():
            try:
                plugin = plugin_manager.get_plugin(plugin_name)
                schema_dicts = plugin.get_schemas()
                
                for schema_dict in schema_dicts:
                    table_name = schema_dict['table_name']
                    
                    # Check if table exists
                    if db_client.table_exists(table_name):
                        tables_existed += 1
                        continue
                    
                    # Create table
                    schema = _dict_to_schema(schema_dict)
                    schema_manager.create_table_from_schema(schema)
                    tables_created += 1
                    if not silent:
                        click.echo(f"✓ Created table: {table_name}")
                        
            except Exception as e:
                if not silent:
                    click.echo(f"✗ Failed to process plugin {plugin_name}: {e}", err=True)
                logger.error(f"Failed to process plugin {plugin_name}: {e}")
        
        # Create metadata tables
        for table_name, schema in PREDEFINED_SCHEMAS.items():
            try:
                if db_client.table_exists(table_name):
                    tables_existed += 1
                    continue
                
                schema_manager.create_table_from_schema(schema)
                tables_created += 1
                if not silent:
                    click.echo(f"✓ Created metadata table: {table_name}")
                    
            except Exception as e:
                if not silent:
                    click.echo(f"✗ Failed to create metadata table {table_name}: {e}", err=True)
                logger.error(f"Failed to create metadata table {table_name}: {e}")
        
        if not silent:
            if tables_created > 0:
                click.echo(f"✓ Created {tables_created} new table(s), {tables_existed} already existed")
            else:
                click.echo(f"✓ All tables ready ({tables_existed} tables)")
                
    except Exception as e:
        if not silent:
            click.echo(f"✗ Failed to ensure tables exist: {e}", err=True)
        logger.error(f"Failed to ensure tables exist: {e}")
        raise


@cli.command()
@click.option('--list-status', default='L', help='List status: L(listed), D(delisted), P(paused) (default: L)')
def load_stock_basic(list_status):
    """Load stock basic information table (ods_stock_basic)."""
    click.echo(f"Loading ods_stock_basic with list_status={list_status}...")
    
    try:
        from stock_datasource.core.plugin_manager import plugin_manager
        
        # Discover plugins
        plugin_manager.discover_plugins()
        
        # Get and execute plugin
        plugin = plugin_manager.get_plugin('tushare_stock_basic')
        if not plugin:
            click.echo("✗ Plugin tushare_stock_basic not found", err=True)
            sys.exit(1)
        
        result = plugin.run(list_status=list_status)
        
        click.echo(f"Status: {result['status']}")
        for step, step_result in result.get('steps', {}).items():
            status = step_result.get('status', 'unknown')
            records = step_result.get('records', 0)
            click.echo(f"  {step:15} : {status:10} ({records} records)")
        
        if result['status'] != 'success':
            if 'error' in result:
                click.echo(f"Error: {result['error']}", err=True)
            sys.exit(1)
        
        click.echo("✓ ods_stock_basic loaded successfully")
        
    except Exception as e:
        click.echo(f"✗ Failed to load ods_stock_basic: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--start-date', required=True, help='Start date in YYYYMMDD format')
@click.option('--end-date', required=True, help='End date in YYYYMMDD format')
@click.option('--exchange', default='SSE', help='Exchange: SSE or SZSE (default: SSE)')
def load_trade_calendar(start_date, end_date, exchange):
    """Load trade calendar table (ods_trade_calendar)."""
    click.echo(f"Loading ods_trade_calendar from {start_date} to {end_date} ({exchange})...")
    
    try:
        from stock_datasource.core.plugin_manager import plugin_manager
        
        # Discover plugins
        plugin_manager.discover_plugins()
        
        # Get and execute plugin
        plugin = plugin_manager.get_plugin('tushare_trade_calendar')
        if not plugin:
            click.echo("✗ Plugin tushare_trade_calendar not found", err=True)
            sys.exit(1)
        
        result = plugin.run(start_date=start_date, end_date=end_date, exchange=exchange)
        
        click.echo(f"Status: {result['status']}")
        for step, step_result in result.get('steps', {}).items():
            status = step_result.get('status', 'unknown')
            records = step_result.get('records', 0)
            click.echo(f"  {step:15} : {status:10} ({records} records)")
        
        if result['status'] != 'success':
            if 'error' in result:
                click.echo(f"Error: {result['error']}", err=True)
            sys.exit(1)
        
        click.echo("✓ ods_trade_calendar loaded successfully")
        
    except Exception as e:
        click.echo(f"✗ Failed to load ods_trade_calendar: {e}", err=True)
        sys.exit(1)


@cli.command()
def load_hk_stock_list():
    """Load Hong Kong stock list table (ods_hk_stock_list)."""
    click.echo("Loading ods_hk_stock_list...")
    
    try:
        from stock_datasource.core.plugin_manager import plugin_manager
        
        # Discover plugins
        plugin_manager.discover_plugins()
        
        # Get and execute plugin
        plugin = plugin_manager.get_plugin('akshare_hk_stock_list')
        if not plugin:
            click.echo("✗ Plugin akshare_hk_stock_list not found", err=True)
            sys.exit(1)
        
        result = plugin.run()
        
        click.echo(f"Status: {result['status']}")
        for step, step_result in result.get('steps', {}).items():
            status = step_result.get('status', 'unknown')
            records = step_result.get('records', 0)
            click.echo(f"  {step:15} : {status:10} ({records} records)")
        
        if result['status'] != 'success':
            if 'error' in result:
                click.echo(f"Error: {result['error']}", err=True)
            sys.exit(1)
        
        click.echo("✓ ods_hk_stock_list loaded successfully")
        
    except Exception as e:
        click.echo(f"✗ Failed to load ods_hk_stock_list: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--symbol', required=True, help='Hong Kong stock symbol, e.g., 00700')
@click.option('--start-date', help='Start date in YYYYMMDD format (optional)')
@click.option('--end-date', help='End date in YYYYMMDD format (optional)')
def load_hk_daily(symbol, start_date, end_date):
    """Load Hong Kong daily data table (ods_hk_daily)."""
    click.echo(f"Loading ods_hk_daily for {symbol}...")
    
    try:
        from stock_datasource.core.plugin_manager import plugin_manager
        
        # Discover plugins
        plugin_manager.discover_plugins()
        
        # Get and execute plugin
        plugin = plugin_manager.get_plugin('akshare_hk_daily')
        if not plugin:
            click.echo("✗ Plugin akshare_hk_daily not found", err=True)
            sys.exit(1)
        
        kwargs = {'symbol': symbol}
        if start_date:
            kwargs['start_date'] = start_date
        if end_date:
            kwargs['end_date'] = end_date
        
        result = plugin.run(**kwargs)
        
        click.echo(f"Status: {result['status']}")
        for step, step_result in result.get('steps', {}).items():
            status = step_result.get('status', 'unknown')
            records = step_result.get('records', 0)
            click.echo(f"  {step:15} : {status:10} ({records} records)")
        
        if result['status'] != 'success':
            if 'error' in result:
                click.echo(f"Error: {result['error']}", err=True)
            sys.exit(1)
        
        click.echo("✓ ods_hk_daily loaded successfully")
        
    except Exception as e:
        click.echo(f"✗ Failed to load ods_hk_daily: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--plugin', help='Plugin name to test')
@click.option('--date', default='20251015', help='Trade date in YYYYMMDD format (default: 20251015)')
def test_plugin(plugin, date):
    """Test a specific plugin's complete data flow (extract -> load -> verify)."""
    from stock_datasource.core.plugin_manager import plugin_manager
    from stock_datasource.models.database import db_client
    import pandas as pd
    
    # Discover plugins
    plugin_manager.discover_plugins()
    available_plugins = plugin_manager.list_plugins()
    
    if not available_plugins:
        click.echo("✗ No plugins found", err=True)
        sys.exit(1)
    
    if not plugin:
        click.echo("Available plugins:")
        for p in sorted(available_plugins):
            click.echo(f"  - {p}")
        click.echo("\nUsage: cli.py test-plugin --plugin <plugin_name> --date <YYYYMMDD>")
        return
    
    if plugin not in available_plugins:
        click.echo(f"✗ Plugin '{plugin}' not found. Available: {', '.join(sorted(available_plugins))}", err=True)
        sys.exit(1)
    
    click.echo(f"Testing plugin: {plugin}")
    click.echo(f"Trade date: {date}")
    click.echo("=" * 60)
    
    try:
        # Run complete plugin pipeline (extract -> validate -> transform -> load)
        click.echo("\nRunning plugin pipeline (extract -> validate -> transform -> load)...")
        plugin_obj = plugin_manager.get_plugin(plugin)
        
        # Determine parameters based on plugin type
        if plugin == 'tushare_trade_calendar':
            params = {'start_date': date, 'end_date': date}
        elif plugin == 'tushare_stock_basic':
            params = {}
        else:
            params = {'trade_date': date}
        
        # Run the plugin
        result = plugin_obj.run(**params)
        
        # Display results
        click.echo(f"\nPlugin: {result['plugin']}")
        click.echo(f"Status: {result['status']}")
        click.echo(f"Parameters: {result.get('parameters', {})}")
        
        # Show step details
        for step_name, step_result in result.get('steps', {}).items():
            status = step_result.get('status', 'unknown')
            records = step_result.get('records', 0)
            click.echo(f"  {step_name:15} : {status:10} ({records} records)")
        
        # Check for errors
        if result['status'] != 'success':
            if 'error' in result:
                click.echo(f"\n✗ Error: {result['error']}", err=True)
            sys.exit(1)
        
        # Verify data in database
        click.echo("\nVerifying data in database...")
        schema = plugin_obj.get_schema()
        table_name = schema.get('table_name') or schema.get('name')
        
        from stock_datasource.config.settings import settings
        verify_query = f"SELECT COUNT(*) as count FROM {settings.CLICKHOUSE_DATABASE}.{table_name}"
        verify_result = db_client.execute_query(verify_query)
        if not verify_result.empty:
            db_count = verify_result.iloc[0]['count']
            click.echo(f"✓ Database contains {db_count} total records in '{table_name}'")
        
        click.echo("\n" + "=" * 60)
        click.echo("✓ Plugin test completed successfully")
        
    except Exception as e:
        click.echo(f"\n✗ Plugin test failed: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    cli()

