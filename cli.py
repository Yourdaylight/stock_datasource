"""Command line interface for stock data source."""

import click
from datetime import datetime, timedelta
import sys
import json
from pathlib import Path
from typing import Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from stock_datasource.services.ingestion import ingestion_service
from stock_datasource.services.metadata import metadata_service
from stock_datasource.utils.schema_manager import schema_manager
from stock_datasource.utils.logger import logger
from stock_datasource.config.settings import settings
from stock_datasource.core.proxy import proxy_context, is_proxy_enabled, get_proxy_url


@click.group()
def cli():
    """Stock Data Source CLI - Local financial database for A-share/HK stocks."""
    pass


@cli.group()
def logs():
    """Log management commands."""
    pass


@logs.command()
@click.option('--retention-days', default=30, help='Number of days to keep (default: 30)')
def archive(retention_days):
    """Archive old log files."""
    click.echo(f"Archiving logs older than {retention_days} days...")

    try:
        from stock_datasource.modules.system_logs.service import get_log_service

        log_service = get_log_service()
        result = log_service.archive_logs(retention_days=retention_days)

        click.echo(f"✓ Archive status: {result['status']}")
        click.echo(f"✓ Archived {result['archived_count']} files")

        if result['archived_files']:
            click.echo("Archived files:")
            for filename in result['archived_files']:
                click.echo(f"  - {filename}")

    except Exception as e:
        click.echo(f"✗ Log archiving failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--table', help='Specific table to create')
@click.option('--timeout', default=300, help='Timeout in seconds (default: 300)')
def init_db(table, timeout):
    """Initialize database and create tables."""
    import signal
    import time
    
    def timeout_handler(signum, frame):
        raise TimeoutError(f"Database initialization timed out after {timeout} seconds")
    
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
            plugin = plugin_manager.get_plugin(table)
            if plugin:
                click.echo(f"Creating table: {table} (from plugin)")
                schema_dict = plugin.get_schema()
                # Convert dict to TableSchema object
                schema = _dict_to_schema(schema_dict)
                schema_manager.create_table_from_schema(schema)
                click.echo(f"✓ Table {table} created successfully")
            elif table in PREDEFINED_SCHEMAS:
                # Fall back to metadata schemas
                schema = PREDEFINED_SCHEMAS[table]
                click.echo(f"Creating table: {table} (metadata)")
                schema_manager.create_table_from_schema(schema)
                click.echo(f"✓ Table {table} created successfully")
            elif table in ['user_positions', 'portfolio_analysis']:
                # Portfolio module tables
                from stock_datasource.modules.portfolio.schemas import PORTFOLIO_SCHEMAS
                schema = PORTFOLIO_SCHEMAS[table]
                click.echo(f"Creating table: {table} (portfolio)")
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
                    schema_dict = plugin.get_schema()
                    # Convert dict to TableSchema object
                    schema = _dict_to_schema(schema_dict)
                    click.echo(f"Creating table: {schema.table_name}")
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
            
            # Create portfolio module tables
            click.echo("Creating portfolio module tables...")
            try:
                from stock_datasource.modules.portfolio.init import init_portfolio_tables
                if init_portfolio_tables():
                    click.echo("✓ Portfolio tables created successfully")
                else:
                    click.echo("✗ Failed to create portfolio tables", err=True)
            except Exception as e:
                click.echo(f"✗ Failed to create portfolio tables: {e}", err=True)
            
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
    _show_proxy_status()
    
    try:
        with proxy_context():
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
    _show_proxy_status()
    
    try:
        with proxy_context():
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


def _show_proxy_status():
    """Display current proxy configuration status."""
    if is_proxy_enabled():
        click.echo(f"🔗 Proxy enabled: {get_proxy_url()}")
    else:
        click.echo("⚠️  Proxy is NOT enabled — data fetching may fail in restricted environments")


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


@cli.command()
@click.option('--list-status', default='L', help='List status: L(listed), D(delisted), P(paused) (default: L)')
def load_stock_basic(list_status):
    """Load stock basic information table (ods_stock_basic)."""
    click.echo(f"Loading ods_stock_basic with list_status={list_status}...")
    _show_proxy_status()
    
    try:
        from stock_datasource.core.plugin_manager import plugin_manager
        
        # Discover plugins
        plugin_manager.discover_plugins()
        
        # Get and execute plugin
        plugin = plugin_manager.get_plugin('tushare_stock_basic')
        if not plugin:
            click.echo("✗ Plugin tushare_stock_basic not found", err=True)
            sys.exit(1)
        
        with proxy_context():
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
    _show_proxy_status()
    
    try:
        from stock_datasource.core.plugin_manager import plugin_manager
        
        # Discover plugins
        plugin_manager.discover_plugins()
        
        # Get and execute plugin
        plugin = plugin_manager.get_plugin('tushare_trade_calendar')
        if not plugin:
            click.echo("✗ Plugin tushare_trade_calendar not found", err=True)
            sys.exit(1)
        
        with proxy_context():
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
    _show_proxy_status()
    
    try:
        from stock_datasource.core.plugin_manager import plugin_manager
        
        # Discover plugins
        plugin_manager.discover_plugins()
        
        # Get and execute plugin
        plugin = plugin_manager.get_plugin('akshare_hk_stock_list')
        if not plugin:
            click.echo("✗ Plugin akshare_hk_stock_list not found", err=True)
            sys.exit(1)
        
        with proxy_context():
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
    _show_proxy_status()
    
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
        
        with proxy_context():
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


# ============================================================
# New commands: run-plugin, list-plugins, proxy, task
# ============================================================

@cli.command()
@click.argument('plugin_name')
@click.option('--trade-date', help='Trade date in YYYYMMDD format')
@click.option('--start-date', help='Start date in YYYYMMDD format')
@click.option('--end-date', help='End date in YYYYMMDD format')
@click.option('--param', '-p', multiple=True, help='Extra key=value params, e.g. -p symbol=00700 -p exchange=SSE')
@click.option('--auto-deps', is_flag=True, default=False, help='Automatically run missing dependencies first')
def run_plugin(plugin_name, trade_date, start_date, end_date, param, auto_deps):
    """Run any registered plugin by name (with proxy).

    Examples:

      python cli.py run-plugin tushare_daily --trade-date 20260323

      python cli.py run-plugin tushare_stock_basic -p list_status=L

      python cli.py run-plugin akshare_hk_daily -p symbol=00700 --start-date 20260101
    """
    click.echo(f"Running plugin: {plugin_name}")
    _show_proxy_status()

    try:
        from stock_datasource.core.plugin_manager import plugin_manager

        plugin_manager.discover_plugins()

        plugin = plugin_manager.get_plugin(plugin_name)
        if not plugin:
            available = plugin_manager.list_plugins()
            click.echo(f"✗ Plugin '{plugin_name}' not found", err=True)
            if available:
                click.echo(f"  Available plugins: {', '.join(sorted(available))}", err=True)
            sys.exit(1)

        if not plugin.is_enabled():
            click.echo(f"✗ Plugin '{plugin_name}' is disabled", err=True)
            sys.exit(1)

        # Build kwargs from options
        kwargs: Dict[str, Any] = {}
        if trade_date:
            kwargs['trade_date'] = trade_date
        if start_date:
            kwargs['start_date'] = start_date
        if end_date:
            kwargs['end_date'] = end_date

        # Parse extra -p key=value pairs
        for p in param:
            if '=' not in p:
                click.echo(f"✗ Invalid param format '{p}', expected key=value", err=True)
                sys.exit(1)
            key, value = p.split('=', 1)
            kwargs[key.strip()] = value.strip()

        # Execute with proxy context
        with proxy_context():
            if auto_deps:
                result = plugin_manager.execute_with_dependencies(
                    plugin_name, auto_run_deps=True, **kwargs
                )
            else:
                result = plugin.run(**kwargs)

        # Display results
        click.echo(f"Status: {result.get('status', 'unknown')}")
        for step, step_result in result.get('steps', {}).items():
            status = step_result.get('status', 'unknown')
            records = step_result.get('records', 0)
            click.echo(f"  {step:20} : {status:10} ({records} records)")

        if result.get('status') == 'success':
            click.echo(f"✓ Plugin '{plugin_name}' completed successfully")
        else:
            if 'error' in result:
                click.echo(f"Error: {result['error']}", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"✗ Plugin '{plugin_name}' failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--category', help='Filter by category (e.g. a_share, hk_stock, index, fund)')
@click.option('--enabled-only', is_flag=True, default=False, help='Show only enabled plugins')
@click.option('--format', 'fmt', type=click.Choice(['table', 'json']), default='table', help='Output format')
def list_plugins(category, enabled_only, fmt):
    """List all registered plugins and their status."""
    try:
        from stock_datasource.core.plugin_manager import plugin_manager

        plugin_manager.discover_plugins()
        plugins_info = plugin_manager.get_plugin_info()

        if not plugins_info:
            click.echo("No plugins found.")
            return

        # Apply filters
        if category:
            plugins_info = [p for p in plugins_info if p.get('category', '') == category]
        if enabled_only:
            plugins_info = [p for p in plugins_info if p.get('enabled', False)]

        if fmt == 'json':
            click.echo(json.dumps(plugins_info, indent=2, ensure_ascii=False))
            return

        # Table format
        click.echo(f"{'Name':<35} {'Category':<12} {'Role':<12} {'Enabled':<8} {'Description'}")
        click.echo("─" * 100)
        for p in sorted(plugins_info, key=lambda x: (x.get('category', ''), x.get('name', ''))):
            enabled_mark = "✓" if p.get('enabled') else "✗"
            desc = (p.get('description', '') or '')[:40]
            click.echo(
                f"{p['name']:<35} {p.get('category', '-'):<12} "
                f"{p.get('role', '-'):<12} {enabled_mark:<8} {desc}"
            )

        click.echo(f"\nTotal: {len(plugins_info)} plugins")

    except Exception as e:
        click.echo(f"✗ Failed to list plugins: {e}", err=True)
        sys.exit(1)


# ---- proxy subcommand group ----

@cli.group()
def proxy():
    """Proxy configuration management."""
    pass


@proxy.command('status')
def proxy_status():
    """Show current proxy configuration and status."""
    try:
        from stock_datasource.config.runtime_config import load_runtime_config

        config = load_runtime_config()
        proxy_cfg = config.get('proxy', {})

        enabled = proxy_cfg.get('enabled', False)
        host = proxy_cfg.get('host', '')
        port = proxy_cfg.get('port', 0)
        username = proxy_cfg.get('username', '')

        click.echo("Proxy Configuration:")
        click.echo(f"  Enabled:  {'✓ Yes' if enabled else '✗ No'}")
        click.echo(f"  Host:     {host or '(not set)'}")
        click.echo(f"  Port:     {port or '(not set)'}")
        click.echo(f"  Username: {username or '(none)'}")
        click.echo(f"  Password: {'****' if proxy_cfg.get('password') else '(none)'}")

        if is_proxy_enabled():
            click.echo(f"\n  Effective URL: {get_proxy_url()}")
            click.echo("  Status: 🟢 Active")
        else:
            click.echo("\n  Status: 🔴 Inactive")

    except Exception as e:
        click.echo(f"✗ Failed to get proxy status: {e}", err=True)
        sys.exit(1)


@proxy.command('set')
@click.option('--host', required=True, help='Proxy host')
@click.option('--port', required=True, type=int, help='Proxy port')
@click.option('--username', default=None, help='Proxy username (optional)')
@click.option('--password', default=None, help='Proxy password (optional)')
@click.option('--disable', is_flag=True, default=False, help='Disable proxy instead of enabling')
def proxy_set(host, port, username, password, disable):
    """Set proxy configuration (persisted to runtime_config.json)."""
    try:
        from stock_datasource.config.runtime_config import save_runtime_config

        proxy_cfg = {
            'enabled': not disable,
            'host': host,
            'port': port,
        }
        if username is not None:
            proxy_cfg['username'] = username
        if password is not None:
            proxy_cfg['password'] = password

        save_runtime_config(proxy=proxy_cfg)

        if not disable:
            click.echo(f"✓ Proxy enabled: {host}:{port}")
        else:
            click.echo("✓ Proxy disabled")

        click.echo("  Note: Restart the backend service for full effect, or use CLI commands directly.")

    except Exception as e:
        click.echo(f"✗ Failed to set proxy: {e}", err=True)
        sys.exit(1)


@proxy.command('test')
@click.option('--url', default='https://httpbin.org/ip', help='URL to test connectivity (default: httpbin.org/ip)')
@click.option('--timeout', default=10, type=int, help='Timeout in seconds (default: 10)')
def proxy_test(url, timeout):
    """Test proxy connectivity."""
    click.echo(f"Testing proxy connectivity to {url}...")
    _show_proxy_status()

    try:
        import requests

        with proxy_context():
            proxy_url = get_proxy_url()
            proxies = None
            if proxy_url:
                proxies = {'http': proxy_url, 'https': proxy_url}

            resp = requests.get(url, proxies=proxies, timeout=timeout)

            click.echo(f"  HTTP Status: {resp.status_code}")
            if resp.status_code == 200:
                click.echo(f"  Response: {resp.text[:200]}")
                click.echo("✓ Proxy connection successful!")
            else:
                click.echo(f"✗ Unexpected status code: {resp.status_code}", err=True)
                sys.exit(1)

    except requests.exceptions.ProxyError as e:
        click.echo(f"✗ Proxy connection error: {e}", err=True)
        sys.exit(1)
    except requests.exceptions.Timeout:
        click.echo(f"✗ Connection timed out after {timeout}s", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"✗ Connection test failed: {e}", err=True)
        sys.exit(1)


# ---- task subcommand group ----

@cli.group()
def task():
    """Task queue management (requires Redis)."""
    pass


@task.command('list')
@click.option('--limit', default=20, type=int, help='Max number of tasks to show (default: 20)')
@click.option('--status', 'task_status', help='Filter by status: pending, running, completed, failed, cancelled')
def task_list(limit, task_status):
    """List tasks in the queue."""
    try:
        from stock_datasource.services.task_queue import task_queue

        tasks = task_queue.list_tasks(limit=limit)

        if task_status:
            tasks = [t for t in tasks if t.get('status') == task_status]

        if not tasks:
            click.echo("No tasks found.")
            return

        click.echo(f"{'Task ID':<38} {'Plugin':<30} {'Status':<12} {'Created'}")
        click.echo("─" * 100)
        for t in tasks:
            task_id = t.get('task_id', '?')[:36]
            plugin = t.get('plugin_name', '?')[:28]
            status = t.get('status', '?')
            created = t.get('created_at', '?')
            if isinstance(created, str) and len(created) > 19:
                created = created[:19]
            click.echo(f"{task_id:<38} {plugin:<30} {status:<12} {created}")

        click.echo(f"\nShowing {len(tasks)} task(s)")

    except Exception as e:
        click.echo(f"✗ Failed to list tasks: {e}", err=True)
        sys.exit(1)


@task.command('stats')
def task_stats():
    """Show task queue statistics."""
    try:
        from stock_datasource.services.task_queue import task_queue

        stats = task_queue.get_queue_stats()

        click.echo("Task Queue Statistics:")
        click.echo(f"  Pending (high):   {stats.get('pending_high', 0)}")
        click.echo(f"  Pending (normal): {stats.get('pending_normal', 0)}")
        click.echo(f"  Pending (low):    {stats.get('pending_low', 0)}")
        click.echo(f"  Running:          {stats.get('running', 0)}")
        click.echo(f"  Total pending:    {stats.get('total_pending', 0)}")

    except Exception as e:
        click.echo(f"✗ Failed to get queue stats: {e}", err=True)
        sys.exit(1)


@task.command('cancel')
@click.argument('task_id')
def task_cancel(task_id):
    """Cancel a pending task by ID."""
    try:
        from stock_datasource.services.task_queue import task_queue

        success = task_queue.cancel_task(task_id)

        if success:
            click.echo(f"✓ Task {task_id} cancelled")
        else:
            click.echo(f"✗ Could not cancel task {task_id} (may be already running or completed)", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"✗ Failed to cancel task: {e}", err=True)
        sys.exit(1)


@task.command('info')
@click.argument('task_id')
def task_info(task_id):
    """Show detailed information about a task."""
    try:
        from stock_datasource.services.task_queue import task_queue

        info = task_queue.get_task(task_id)

        if not info:
            click.echo(f"✗ Task {task_id} not found", err=True)
            sys.exit(1)

        click.echo("Task Details:")
        for key, value in info.items():
            click.echo(f"  {key}: {value}")

    except Exception as e:
        click.echo(f"✗ Failed to get task info: {e}", err=True)
        sys.exit(1)


# ============================================================
# Register CLI subcommand modules (setup, doctor, server, config)
# ============================================================

from stock_datasource.cli import register_commands
register_commands(cli)


if __name__ == '__main__':
    cli()
