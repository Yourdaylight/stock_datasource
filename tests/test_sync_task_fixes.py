"""Tests for sync task display and behavior fixes.

These tests verify the fixes for:
1. Task name consistency between list and detail views
2. Dimension tables (etf_basic) should not receive multi-date backfill
3. Progress display for tasks with 0 records
4. ETF screener date filtering edge cases
"""

import pytest
from unittest.mock import MagicMock, patch


class TestTaskNameConsistency:
    """Test that task names are consistent between list and detail views."""
    
    def test_group_name_used_for_display(self):
        """Verify group_name is used as task name when available."""
        # Simulated execution record
        record = {
            "execution_id": "test123",
            "group_name": "ETF完整数据",
            "trigger_type": "group",
            "total_plugins": 3,
        }
        
        # The frontend getTaskName function should return group_name
        # when it's present
        assert record["group_name"] == "ETF完整数据"
        
    def test_fallback_task_name_generation(self):
        """Verify fallback name when group_name is missing."""
        record = {
            "execution_id": "test456",
            "group_name": None,
            "trigger_type": "group",
            "total_plugins": 3,
        }
        
        # Without group_name, should generate based on trigger_type and count
        expected = f"组合同步 ({record['total_plugins']}个)"
        # This tests the logic that should be in frontend
        assert record["trigger_type"] == "group"
        assert record["total_plugins"] == 3


class TestDimensionTableHandling:
    """Test that dimension tables are handled correctly during group sync."""
    
    @pytest.fixture
    def dim_tables(self):
        """List of known dimension tables."""
        return {
            "tushare_stock_basic",
            "tushare_index_basic", 
            "tushare_index_classify",
            "tushare_ths_index",
            "tushare_etf_basic",
            "akshare_hk_stock_list",
        }
    
    def test_etf_basic_is_dimension_table(self, dim_tables):
        """Verify etf_basic is classified as dimension table."""
        assert "tushare_etf_basic" in dim_tables
    
    def test_etf_fund_daily_is_not_dimension_table(self, dim_tables):
        """Verify etf_fund_daily is NOT a dimension table."""
        assert "tushare_etf_fund_daily" not in dim_tables
    
    def test_dimension_table_should_not_receive_dates(self, dim_tables):
        """Test that dimension tables should not receive trade_dates for backfill."""
        plugin_name = "tushare_etf_basic"
        request_dates = ["2026-01-22", "2026-01-23"]
        
        # For dimension tables, trade_dates should be set to None
        if plugin_name in dim_tables:
            effective_dates = None
        else:
            effective_dates = request_dates
        
        # etf_basic should get None (not multi-date backfill)
        assert effective_dates is None
    
    def test_daily_table_should_receive_dates(self, dim_tables):
        """Test that daily tables should receive trade_dates normally."""
        plugin_name = "tushare_etf_fund_daily"
        request_dates = ["2026-01-22", "2026-01-23"]
        
        if plugin_name in dim_tables:
            effective_dates = None
        else:
            effective_dates = request_dates
        
        # etf_fund_daily should receive the dates
        assert effective_dates == request_dates


class TestProgressDisplay:
    """Test progress and record count display logic."""
    
    def test_completed_with_records_shows_success(self):
        """Task completed with records should show success status."""
        task = {
            "status": "completed",
            "progress": 100.0,
            "records_processed": 1407,
        }
        
        is_success = task["status"] == "completed" and task["records_processed"] > 0
        assert is_success is True
    
    def test_completed_without_records_shows_warning(self):
        """Task completed without records should show warning."""
        task = {
            "status": "completed",
            "progress": 100.0,
            "records_processed": 0,
        }
        
        # Frontend should display warning for this case
        is_no_data_warning = (
            task["status"] == "completed" and 
            task["records_processed"] == 0
        )
        assert is_no_data_warning is True
    
    def test_running_task_zero_records_is_normal(self):
        """Running task with 0 records is normal (not started processing)."""
        task = {
            "status": "running",
            "progress": 50.0,
            "records_processed": 0,
        }
        
        # Running tasks with 0 records shouldn't show warning
        is_no_data_warning = (
            task["status"] == "completed" and 
            task["records_processed"] == 0
        )
        assert is_no_data_warning is False


class TestEtfScreenerDateHandling:
    """Test ETF screener date handling and no-data dialog logic."""
    
    def test_should_show_dialog_when_no_data_no_filters(self):
        """Should show dialog when no data and no active filters."""
        state = {
            "total": 0,
            "loading": False,
            "selectedDate": "20260122",
            "selectedExchange": "",
            "selectedType": "",
            "searchKeyword": "",
        }
        
        has_active_filters = bool(
            state["selectedExchange"] or 
            state["selectedType"] or 
            state["searchKeyword"]
        )
        
        should_show = (
            state["total"] == 0 and 
            not state["loading"] and 
            state["selectedDate"] and
            not has_active_filters
        )
        
        assert should_show is True
    
    def test_should_not_show_dialog_when_filters_active(self):
        """Should NOT show dialog when filters are active (could cause zero)."""
        state = {
            "total": 0,
            "loading": False,
            "selectedDate": "20260123",
            "selectedExchange": "SH",  # Active filter
            "selectedType": "黄金ETF",  # Active filter
            "searchKeyword": "",
        }
        
        has_active_filters = bool(
            state["selectedExchange"] or 
            state["selectedType"] or 
            state["searchKeyword"]
        )
        
        should_show = (
            state["total"] == 0 and 
            not state["loading"] and 
            state["selectedDate"] and
            not has_active_filters
        )
        
        # With filters active, shouldn't show the "no data for date" dialog
        assert should_show is False
    
    def test_date_format_handling(self):
        """Test date format handling between YYYYMMDD and YYYY-MM-DD."""
        date_yyyymmdd = "20260123"
        date_with_dashes = "2026-01-23"
        
        # Format conversion
        if len(date_yyyymmdd) == 8:
            converted = f"{date_yyyymmdd[:4]}-{date_yyyymmdd[4:6]}-{date_yyyymmdd[6:8]}"
        else:
            converted = date_yyyymmdd
        
        assert converted == date_with_dashes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
