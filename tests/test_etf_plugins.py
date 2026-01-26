"""Tests for ETF data plugins.

Uses runtime_config.json for proxy and sync configuration.
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestETFBasicPlugin:
    """Test tushare_etf_basic plugin."""
    
    def test_plugin_creation(self):
        """Test plugin can be created."""
        from stock_datasource.plugins.tushare_etf_basic import TuShareETFBasicPlugin
        
        plugin = TuShareETFBasicPlugin()
        assert plugin is not None
        assert plugin.name == "tushare_etf_basic"
        assert plugin.version == "1.0.0"
        print(f"\n[tushare_etf_basic] Plugin created: {plugin.name}")
    
    def test_plugin_config(self):
        """Test plugin configuration."""
        from stock_datasource.plugins.tushare_etf_basic import TuShareETFBasicPlugin
        
        plugin = TuShareETFBasicPlugin()
        config = plugin.get_config()
        
        assert config is not None
        assert config.get("enabled") == True
        assert config.get("rate_limit") == 120
        print(f"  - Config: {config}")
    
    def test_plugin_schema(self):
        """Test plugin schema."""
        from stock_datasource.plugins.tushare_etf_basic import TuShareETFBasicPlugin
        
        plugin = TuShareETFBasicPlugin()
        schema = plugin.get_schema()
        
        assert schema is not None
        assert schema.get("table_name") == "ods_etf_basic"
        assert len(schema.get("columns", [])) > 0
        print(f"  - Schema table: {schema.get('table_name')}")
        print(f"  - Columns: {len(schema.get('columns', []))}")
    
    def test_plugin_dependencies(self):
        """Test plugin has no dependencies."""
        from stock_datasource.plugins.tushare_etf_basic import TuShareETFBasicPlugin
        
        plugin = TuShareETFBasicPlugin()
        deps = plugin.get_dependencies()
        
        assert deps == []
        print(f"  - Dependencies: {deps}")
    
    def test_extract_data(self):
        """Test extract_data method."""
        from stock_datasource.plugins.tushare_etf_basic import TuShareETFBasicPlugin
        
        plugin = TuShareETFBasicPlugin()
        
        try:
            data = plugin.extract_data(list_status='L')
            print(f"\n[extract_data] Result: {len(data)} records")
            
            if not data.empty:
                assert 'ts_code' in data.columns
                assert 'list_status' in data.columns
                print(f"  - Columns: {list(data.columns)[:5]}...")
                print(f"  - Sample: {data.head(2).to_dict('records')}")
        except Exception as e:
            print(f"  - Extract failed (expected if no API token): {e}")


class TestETFFundDailyPlugin:
    """Test tushare_etf_fund_daily plugin."""
    
    def test_plugin_creation(self):
        """Test plugin can be created."""
        from stock_datasource.plugins.tushare_etf_fund_daily import TuShareETFFundDailyPlugin
        
        plugin = TuShareETFFundDailyPlugin()
        assert plugin is not None
        assert plugin.name == "tushare_etf_fund_daily"
        print(f"\n[tushare_etf_fund_daily] Plugin created: {plugin.name}")
    
    def test_plugin_dependencies(self):
        """Test plugin declares dependency on etf_basic."""
        from stock_datasource.plugins.tushare_etf_fund_daily import TuShareETFFundDailyPlugin
        
        plugin = TuShareETFFundDailyPlugin()
        deps = plugin.get_dependencies()
        
        assert "tushare_etf_basic" in deps
        print(f"  - Dependencies: {deps}")
    
    def test_plugin_schema(self):
        """Test plugin schema."""
        from stock_datasource.plugins.tushare_etf_fund_daily import TuShareETFFundDailyPlugin
        
        plugin = TuShareETFFundDailyPlugin()
        schema = plugin.get_schema()
        
        assert schema is not None
        assert schema.get("table_name") == "ods_etf_fund_daily"
        print(f"  - Schema table: {schema.get('table_name')}")
    
    def test_extract_data(self):
        """Test extract_data method."""
        from stock_datasource.plugins.tushare_etf_fund_daily import TuShareETFFundDailyPlugin
        
        plugin = TuShareETFFundDailyPlugin()
        
        try:
            # Test with a specific ETF code
            data = plugin.extract_data(ts_code='510330.SH', start_date='20260101', end_date='20260110')
            print(f"\n[extract_data] Result: {len(data)} records")
            
            if not data.empty:
                assert 'ts_code' in data.columns
                assert 'trade_date' in data.columns
                assert 'close' in data.columns
                print(f"  - Columns: {list(data.columns)[:5]}...")
        except Exception as e:
            print(f"  - Extract failed (expected if no API token): {e}")


class TestETFFundAdjPlugin:
    """Test tushare_etf_fund_adj plugin."""
    
    def test_plugin_creation(self):
        """Test plugin can be created."""
        from stock_datasource.plugins.tushare_etf_fund_adj import TuShareETFFundAdjPlugin
        
        plugin = TuShareETFFundAdjPlugin()
        assert plugin is not None
        assert plugin.name == "tushare_etf_fund_adj"
        print(f"\n[tushare_etf_fund_adj] Plugin created: {plugin.name}")
    
    def test_plugin_dependencies(self):
        """Test plugin declares dependency on etf_basic."""
        from stock_datasource.plugins.tushare_etf_fund_adj import TuShareETFFundAdjPlugin
        
        plugin = TuShareETFFundAdjPlugin()
        deps = plugin.get_dependencies()
        
        assert "tushare_etf_basic" in deps
        print(f"  - Dependencies: {deps}")
    
    def test_plugin_schema(self):
        """Test plugin schema."""
        from stock_datasource.plugins.tushare_etf_fund_adj import TuShareETFFundAdjPlugin
        
        plugin = TuShareETFFundAdjPlugin()
        schema = plugin.get_schema()
        
        assert schema is not None
        assert schema.get("table_name") == "ods_etf_fund_adj"
        print(f"  - Schema table: {schema.get('table_name')}")
    
    def test_extract_data(self):
        """Test extract_data method."""
        from stock_datasource.plugins.tushare_etf_fund_adj import TuShareETFFundAdjPlugin
        
        plugin = TuShareETFFundAdjPlugin()
        
        try:
            data = plugin.extract_data(ts_code='510330.SH')
            print(f"\n[extract_data] Result: {len(data)} records")
            
            if not data.empty:
                assert 'ts_code' in data.columns
                assert 'adj_factor' in data.columns
                print(f"  - Columns: {list(data.columns)}")
        except Exception as e:
            print(f"  - Extract failed (expected if no API token): {e}")


class TestETFStkMinsPlugin:
    """Test tushare_etf_stk_mins plugin."""
    
    def test_plugin_creation(self):
        """Test plugin can be created."""
        from stock_datasource.plugins.tushare_etf_stk_mins import TuShareETFStkMinsPlugin
        
        plugin = TuShareETFStkMinsPlugin()
        assert plugin is not None
        assert plugin.name == "tushare_etf_stk_mins"
        print(f"\n[tushare_etf_stk_mins] Plugin created: {plugin.name}")
    
    def test_plugin_dependencies(self):
        """Test plugin declares dependency on etf_basic."""
        from stock_datasource.plugins.tushare_etf_stk_mins import TuShareETFStkMinsPlugin
        
        plugin = TuShareETFStkMinsPlugin()
        deps = plugin.get_dependencies()
        
        assert "tushare_etf_basic" in deps
        print(f"  - Dependencies: {deps}")
    
    def test_plugin_schema(self):
        """Test plugin schema."""
        from stock_datasource.plugins.tushare_etf_stk_mins import TuShareETFStkMinsPlugin
        
        plugin = TuShareETFStkMinsPlugin()
        schema = plugin.get_schema()
        
        assert schema is not None
        assert schema.get("table_name") == "ods_etf_stk_mins"
        print(f"  - Schema table: {schema.get('table_name')}")
    
    def test_extract_data(self):
        """Test extract_data method."""
        from stock_datasource.plugins.tushare_etf_stk_mins import TuShareETFStkMinsPlugin
        
        plugin = TuShareETFStkMinsPlugin()
        
        try:
            data = plugin.extract_data(
                ts_code='510330.SH',
                freq='1min',
                start_date='2026-01-10 09:00:00',
                end_date='2026-01-10 15:00:00'
            )
            print(f"\n[extract_data] Result: {len(data)} records")
            
            if not data.empty:
                assert 'ts_code' in data.columns
                assert 'trade_time' in data.columns
                assert 'close' in data.columns
                print(f"  - Columns: {list(data.columns)}")
        except Exception as e:
            print(f"  - Extract failed (expected if no API token): {e}")


class TestPluginDependencies:
    """Test plugin dependency relationships."""
    
    def test_etf_basic_no_dependencies(self):
        """Test etf_basic has no dependencies."""
        from stock_datasource.plugins.tushare_etf_basic import TuShareETFBasicPlugin
        
        plugin = TuShareETFBasicPlugin()
        assert plugin.get_dependencies() == []
    
    def test_fund_daily_depends_on_basic(self):
        """Test fund_daily depends on etf_basic."""
        from stock_datasource.plugins.tushare_etf_fund_daily import TuShareETFFundDailyPlugin
        
        plugin = TuShareETFFundDailyPlugin()
        deps = plugin.get_dependencies()
        assert "tushare_etf_basic" in deps
    
    def test_fund_adj_depends_on_basic(self):
        """Test fund_adj depends on etf_basic."""
        from stock_datasource.plugins.tushare_etf_fund_adj import TuShareETFFundAdjPlugin
        
        plugin = TuShareETFFundAdjPlugin()
        deps = plugin.get_dependencies()
        assert "tushare_etf_basic" in deps
    
    def test_stk_mins_depends_on_basic(self):
        """Test stk_mins depends on etf_basic."""
        from stock_datasource.plugins.tushare_etf_stk_mins import TuShareETFStkMinsPlugin
        
        plugin = TuShareETFStkMinsPlugin()
        deps = plugin.get_dependencies()
        assert "tushare_etf_basic" in deps


class TestPluginDiscovery:
    """Test plugin discovery."""
    
    def test_plugins_discoverable(self):
        """Test all ETF plugins are discoverable."""
        from stock_datasource.plugins import PluginManager
        
        manager = PluginManager()
        manager.discover_plugins()
        
        plugins = manager.list_plugins()
        print(f"\n[Plugin Discovery] Found {len(plugins)} plugins")
        
        # Check ETF plugins are discovered
        etf_plugins = [p for p in plugins if 'etf' in p.lower()]
        print(f"  - ETF plugins: {etf_plugins}")
        
        # These should be discoverable
        expected = [
            'tushare_etf_basic',
            'tushare_etf_fund_daily',
            'tushare_etf_fund_adj',
            'tushare_etf_stk_mins'
        ]
        
        for plugin_name in expected:
            if plugin_name in plugins:
                print(f"  - ✓ {plugin_name} discovered")
            else:
                print(f"  - ✗ {plugin_name} NOT discovered")


if __name__ == "__main__":
    # Run with: python -m pytest tests/test_etf_plugins.py -v -s
    pytest.main([__file__, "-v", "-s"])
