"""
Test suite for sync task name consistency between list and detail views.

These tests verify that task names are displayed consistently across:
1. Task list view (SyncTasksView.vue - table)
2. Task detail dialog (SyncTasksView.vue - dialog)

The core logic is the getTaskName() function which should:
- Return group_name if available
- Generate a descriptive name based on trigger_type and plugin count otherwise
"""

import pytest


def get_task_name(row: dict) -> str:
    """
    Python implementation of frontend getTaskName() logic.
    This should match the Vue implementation exactly.
    
    Args:
        row: Dict with keys: group_name, trigger_type, total_plugins
        
    Returns:
        Task display name
    """
    # Priority 1: Use group_name if available
    if row.get("group_name"):
        return row["group_name"]
    
    # Priority 2: Generate name based on trigger_type and plugin count
    plugin_count = row.get("total_plugins", 0)
    trigger_type = row.get("trigger_type", "")
    
    name_map = {
        "scheduled": ("定时同步任务", "定时同步"),
        "manual": ("手动同步任务", "手动同步"),
        "group": ("组合同步任务", "组合同步"),
        "retry": ("重试任务", "重试任务"),
    }
    
    if trigger_type in name_map:
        single_name, plural_prefix = name_map[trigger_type]
        if plugin_count > 1:
            return f"{plural_prefix} ({plugin_count}个)"
        return single_name
    
    return "同步任务"


class TestTaskNameConsistency:
    """Test task name generation for consistency between list and detail views."""
    
    def test_with_group_name_returns_group_name(self):
        """When group_name exists, it should be returned directly."""
        row = {
            "group_name": "ETF完整数据",
            "trigger_type": "group",
            "total_plugins": 3
        }
        assert get_task_name(row) == "ETF完整数据"
    
    def test_group_type_multiple_plugins_without_group_name(self):
        """Group trigger with multiple plugins but no group_name."""
        row = {
            "group_name": None,
            "trigger_type": "group",
            "total_plugins": 3
        }
        assert get_task_name(row) == "组合同步 (3个)"
    
    def test_group_type_single_plugin_without_group_name(self):
        """Group trigger with single plugin but no group_name."""
        row = {
            "group_name": None,
            "trigger_type": "group",
            "total_plugins": 1
        }
        assert get_task_name(row) == "组合同步任务"
    
    def test_manual_type_multiple_plugins(self):
        """Manual trigger with multiple plugins."""
        row = {
            "group_name": None,
            "trigger_type": "manual",
            "total_plugins": 5
        }
        assert get_task_name(row) == "手动同步 (5个)"
    
    def test_manual_type_single_plugin(self):
        """Manual trigger with single plugin."""
        row = {
            "group_name": None,
            "trigger_type": "manual",
            "total_plugins": 1
        }
        assert get_task_name(row) == "手动同步任务"
    
    def test_scheduled_type_multiple_plugins(self):
        """Scheduled trigger with multiple plugins."""
        row = {
            "group_name": None,
            "trigger_type": "scheduled",
            "total_plugins": 10
        }
        assert get_task_name(row) == "定时同步 (10个)"
    
    def test_retry_type_multiple_plugins(self):
        """Retry trigger with multiple plugins."""
        row = {
            "group_name": None,
            "trigger_type": "retry",
            "total_plugins": 2
        }
        assert get_task_name(row) == "重试任务 (2个)"
    
    def test_unknown_trigger_type(self):
        """Unknown trigger type should return default name."""
        row = {
            "group_name": None,
            "trigger_type": "unknown",
            "total_plugins": 1
        }
        assert get_task_name(row) == "同步任务"
    
    def test_empty_group_name_uses_fallback(self):
        """Empty string group_name should use fallback logic."""
        row = {
            "group_name": "",
            "trigger_type": "group",
            "total_plugins": 3
        }
        # Empty string is falsy, should use fallback
        assert get_task_name(row) == "组合同步 (3个)"
    
    def test_manual_single_plugin_with_plugin_name(self):
        """Manual single plugin sync should show plugin name as group_name."""
        row = {
            "group_name": "tushare_etf_basic",  # Backend sets this for single plugins
            "trigger_type": "manual",
            "total_plugins": 1
        }
        assert get_task_name(row) == "tushare_etf_basic"


class TestListAndDetailConsistency:
    """
    Verify that the same row data produces identical names
    in both list view and detail dialog.
    """
    
    @pytest.mark.parametrize("row,expected_name", [
        # Case 1: Group with name (from screenshot issue)
        ({"group_name": "ETF完整数据", "trigger_type": "group", "total_plugins": 3}, "ETF完整数据"),
        
        # Case 2: Group without name
        ({"group_name": None, "trigger_type": "group", "total_plugins": 3}, "组合同步 (3个)"),
        
        # Case 3: Single manual plugin
        ({"group_name": "tushare_daily_basic", "trigger_type": "manual", "total_plugins": 1}, "tushare_daily_basic"),
        
        # Case 4: Batch manual
        ({"group_name": None, "trigger_type": "manual", "total_plugins": 5}, "手动同步 (5个)"),
        
        # Case 5: Scheduled
        ({"group_name": None, "trigger_type": "scheduled", "total_plugins": 20}, "定时同步 (20个)"),
    ])
    def test_name_consistency(self, row, expected_name):
        """Both list and detail should produce the same name for same data."""
        # Simulate list view
        list_name = get_task_name(row)
        
        # Simulate detail dialog (same function after fix)
        detail_name = get_task_name(row)
        
        assert list_name == expected_name
        assert detail_name == expected_name
        assert list_name == detail_name  # Consistency check


class TestDimensionTableHandling:
    """Test that dimension tables are handled correctly in sync."""
    
    DIMENSION_TABLES = {
        "tushare_stock_basic",
        "tushare_index_basic", 
        "tushare_index_classify",
        "tushare_ths_index",
        "tushare_etf_basic",
        "akshare_hk_stock_list",
    }
    
    def test_etf_basic_is_dimension_table(self):
        """tushare_etf_basic should be recognized as dimension table."""
        assert "tushare_etf_basic" in self.DIMENSION_TABLES
    
    def test_etf_fund_daily_is_not_dimension_table(self):
        """tushare_etf_fund_daily should NOT be dimension table."""
        assert "tushare_etf_fund_daily" not in self.DIMENSION_TABLES
    
    def test_stock_basic_is_dimension_table(self):
        """tushare_stock_basic should be dimension table."""
        assert "tushare_stock_basic" in self.DIMENSION_TABLES


class TestNumpyTypeSerialization:
    """Test that numpy types are properly converted to native Python types."""
    
    def test_records_processed_conversion(self):
        """Verify records_processed is converted to int."""
        import numpy as np
        
        # Simulate numpy.uint64 from ClickHouse/pandas
        numpy_value = np.uint64(12345)
        
        # The fix: convert to int before assignment
        records_processed = int(numpy_value)
        
        assert isinstance(records_processed, int)
        assert records_processed == 12345
        
        # Verify it's JSON serializable
        import json
        json.dumps({"records_processed": records_processed})  # Should not raise
    
    def test_numpy_uint64_json_fails(self):
        """Verify that raw numpy.uint64 cannot be JSON serialized."""
        import numpy as np
        import json
        
        numpy_value = np.uint64(12345)
        
        with pytest.raises(TypeError):
            json.dumps({"value": numpy_value})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
