# BasePlugin Quick Reference Guide

## Available Methods in BasePlugin

### Pipeline Orchestration

#### `run(**kwargs) -> Dict[str, Any]`
Execute complete ETL pipeline (Extract → Validate → Transform → Load).

```python
plugin = TuShareDailyPlugin()
result = plugin.run(trade_date="20240101")
```

**Returns**:
```python
{
    "plugin": "plugin_name",
    "status": "success|failed",
    "steps": {
        "extract": {"status": "...", "records": N},
        "validate": {"status": "..."},
        "transform": {"status": "...", "records": N},
        "load": {...}
    },
    "parameters": {...},
    "error": "error message if failed"
}
```

---

### Database Management

#### `_init_db()`
Initialize database connection. Called automatically in `__init__()`.

```python
# Automatically called, no need to call manually
self.db  # Database client available after initialization
```

#### `_prepare_data_for_insert(table_name: str, data: pd.DataFrame) -> pd.DataFrame`
Prepare data for insertion by converting types according to table schema.

```python
# Handles date and numeric conversions
prepared_data = self._prepare_data_for_insert('ods_daily', data)
self.db.insert_dataframe('ods_daily', prepared_data)
```

---

### Data Validation Helpers

#### `_check_empty_data(data: Any, data_type: str = "data") -> bool`
Check if data is empty.

```python
if not self._check_empty_data(data, "daily data"):
    return False
```

#### `_check_null_values(data: pd.DataFrame, columns: List[str]) -> bool`
Check for null values in specified columns.

```python
if not self._check_null_values(data, ['ts_code', 'trade_date']):
    return False
```

#### `_add_system_columns(data: pd.DataFrame) -> pd.DataFrame`
Add system columns (version, _ingested_at) to data.

```python
data = self._add_system_columns(data)
# data now has 'version' and '_ingested_at' columns
```

---

### Configuration Management

#### `get_config() -> Dict[str, Any]`
Get plugin configuration from config.json.

```python
config = self.get_config()
rate_limit = config.get("rate_limit", 500)
```

#### `get_schema() -> Dict[str, Any]`
Get table schema from schema.json.

```python
schema = self.get_schema()
```

#### `get_rate_limit() -> int`
Get plugin-specific rate limit.

```python
rate_limit = self.get_rate_limit()
```

#### `get_timeout() -> int`
Get plugin-specific timeout.

```python
timeout = self.get_timeout()
```

#### `get_retry_attempts() -> int`
Get plugin-specific retry attempts.

```python
retries = self.get_retry_attempts()
```

#### `get_schedule() -> Dict[str, Any]`
Get plugin schedule configuration.

```python
schedule = self.get_schedule()
# Returns: {"frequency": "daily", "time": "18:00"}
```

---

### Plugin Information

#### `name` (property)
Plugin name (must be unique).

```python
@property
def name(self) -> str:
    return "tushare_daily"
```

#### `version` (property)
Plugin version (default: "1.0.0").

```python
@property
def version(self) -> str:
    return "1.0.0"
```

#### `description` (property)
Plugin description.

```python
@property
def description(self) -> str:
    return "TuShare daily stock price data"
```

#### `api_rate_limit` (property)
API rate limit per minute (default: 120).

```python
@property
def api_rate_limit(self) -> int:
    return 500
```

---

### Abstract Methods (Must Implement)

#### `extract_data(**kwargs) -> Any`
Extract data from source.

```python
def extract_data(self, **kwargs) -> pd.DataFrame:
    trade_date = kwargs.get('trade_date')
    # ... extraction logic ...
    return data
```

#### `validate_data(data: Any) -> bool`
Validate extracted data.

```python
def validate_data(self, data: pd.DataFrame) -> bool:
    if not self._check_empty_data(data):
        return False
    # ... validation logic ...
    return True
```

#### `transform_data(data: Any) -> Any`
Transform data for database insertion.

```python
def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
    # ... transformation logic ...
    return data
```

#### `load_data(data: Any) -> Dict[str, Any]`
Load transformed data into database.

```python
def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
    if not self.db:
        return {"status": "failed", "error": "Database not initialized"}
    
    # ... loading logic ...
    return {"status": "success", "loaded_records": len(data)}
```

---

## Plugin Template

```python
"""Plugin description."""

import pandas as pd
from typing import Dict, Any, List
from datetime import datetime

from stock_datasource.plugins import BasePlugin
from .extractor import extractor


class MyPlugin(BasePlugin):
    """Plugin description."""
    
    @property
    def name(self) -> str:
        return "my_plugin"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "Plugin description"
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        """Extract data from source."""
        # Use self.logger for logging
        self.logger.info("Extracting data...")
        
        # Extract data
        data = extractor.extract(**kwargs)
        
        # Add system columns
        data = self._add_system_columns(data)
        
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate data."""
        # Check if empty
        if not self._check_empty_data(data):
            return False
        
        # Check for null values
        if not self._check_null_values(data, ['ts_code']):
            return False
        
        # Plugin-specific validation
        # ...
        
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data."""
        # Plugin-specific transformation
        # ...
        
        return data
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load data into database."""
        if not self.db:
            return {"status": "failed", "error": "Database not initialized"}
        
        try:
            # Prepare data
            data = self._prepare_data_for_insert('table_name', data)
            
            # Insert data
            self.db.insert_dataframe('table_name', data)
            
            return {
                "status": "success",
                "table": "table_name",
                "loaded_records": len(data)
            }
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            return {"status": "failed", "error": str(e)}


if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="My Plugin")
    parser.add_argument("--param", required=True, help="Parameter")
    
    args = parser.parse_args()
    
    plugin = MyPlugin()
    result = plugin.run(param=args.param)
    
    print(f"\nPlugin: {result['plugin']}")
    print(f"Status: {result['status']}")
    
    for step, step_result in result.get('steps', {}).items():
        status = step_result.get('status', 'unknown')
        records = step_result.get('records', 0)
        print(f"{step:15} : {status:10} ({records} records)")
    
    if result['status'] != 'success':
        if 'error' in result:
            print(f"\nError: {result['error']}")
        sys.exit(1)
    
    sys.exit(0)
```

---

## Common Patterns

### Pattern 1: Simple Daily Data Plugin
```python
def extract_data(self, **kwargs) -> pd.DataFrame:
    trade_date = kwargs.get('trade_date')
    data = extractor.extract(trade_date)
    data = self._add_system_columns(data)
    return data

def validate_data(self, data: pd.DataFrame) -> bool:
    if not self._check_empty_data(data):
        return False
    if not self._check_null_values(data, ['ts_code', 'trade_date']):
        return False
    return True

def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
    data = self._prepare_data_for_insert('ods_table', data)
    self.db.insert_dataframe('ods_table', data)
    return {"status": "success", "loaded_records": len(data)}
```

### Pattern 2: Multi-Table Loading
```python
def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
    results = {"status": "success", "tables_loaded": [], "total_records": 0}
    
    # Load to ODS
    ods_data = self._prepare_data_for_insert('ods_table', data.copy())
    self.db.insert_dataframe('ods_table', ods_data)
    results['tables_loaded'].append({'table': 'ods_table', 'records': len(ods_data)})
    results['total_records'] += len(ods_data)
    
    # Load to DIM
    dim_data = self._prepare_data_for_insert('dim_table', data.copy())
    self.db.insert_dataframe('dim_table', dim_data)
    results['tables_loaded'].append({'table': 'dim_table', 'records': len(dim_data)})
    results['total_records'] += len(dim_data)
    
    return results
```

### Pattern 3: Date Range Plugin
```python
def extract_data(self, **kwargs) -> pd.DataFrame:
    start_date = kwargs.get('start_date')
    end_date = kwargs.get('end_date')
    data = extractor.extract(start_date, end_date)
    data = self._add_system_columns(data)
    return data
```

---

## Logging

Use `self.logger` for logging:

```python
self.logger.info("Processing data...")
self.logger.warning("No data found")
self.logger.error("Failed to process data")
```

---

## Error Handling

Always return proper status in `load_data()`:

```python
def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
    if not self.db:
        return {"status": "failed", "error": "Database not initialized"}
    
    if data.empty:
        return {"status": "no_data", "loaded_records": 0}
    
    try:
        # ... loading logic ...
        return {"status": "success", "loaded_records": len(data)}
    except Exception as e:
        self.logger.error(f"Failed to load data: {e}")
        return {"status": "failed", "error": str(e)}
```

---

## Testing

Test plugins using the `run()` method:

```python
plugin = MyPlugin()
result = plugin.run(param="value")

assert result['status'] == 'success'
assert result['steps']['extract']['status'] == 'success'
assert result['steps']['load']['status'] == 'success'
```

---

## CLI Execution

Run plugin from command line:

```bash
python src/stock_datasource/plugins/my_plugin/plugin.py --param value
```

---

## Troubleshooting

### Database Not Initialized
```
Warning: Failed to initialize database
```
**Solution**: Ensure database configuration is correct

### Type Conversion Failed
```
Warning: Failed to convert column_name to date
```
**Solution**: Check data format matches expected format

### Empty Data
```
Warning: Empty data
```
**Solution**: Check if data source has records for the requested period
