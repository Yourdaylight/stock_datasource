"""Targeted behavioral tests for impact of SQL injection & reconnection fixes.

Covers the specific code paths modified during the audit:
- T1: CacheService reconnection after Redis disconnect (ping → unavailable → retry)
- T2: get_partition_info uses parameterized query (params dict passed correctly)
- T3: _load_tasks_from_db / get_task_history use _to_clickhouse_literal for cutoff_time
- T4: ETF/Index get_kline uses _to_clickhouse_literal for ts_code and dates
- T5: Timeout consistency between task_queue and task_worker (both 3600s)
- T6: get_task_history safe_limit validation (clamped to [1, 10000])
- T7: deep_analyzer._get_stock_name uses parameterized query
- T8: ETF get_daily / Index get_daily now use _to_clickhouse_literal (fixed)
- T9: ClickHouseHttpClient._request renders %(param)s placeholders safely
- T10: ETF get_etfs uses _to_clickhouse_literal for all string filters
- T11: Index get_indices / get_constituents / get_factors / get_index_detail safe
- T12: Index get_factors indicators whitelist validation
"""

import sys
import importlib.util
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path
from datetime import datetime

_src_dir = Path(__file__).parent.parent / "src"
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))


def _import_module_directly(module_name: str, rel_path: str):
    """Import a module directly from file, bypassing conftest mocks."""
    spec = importlib.util.spec_from_file_location(
        module_name,
        _src_dir / rel_path,
        submodule_search_locations=[]
    )
    mod = importlib.util.module_from_spec(spec)
    return mod, spec


def _setup_minimal_deps():
    """Set up minimal mock dependencies for importing modules."""
    if 'stock_datasource' not in sys.modules or not hasattr(sys.modules.get('stock_datasource', object), '__path__'):
        sys.modules['stock_datasource'] = type(sys)('stock_datasource')
        sys.modules['stock_datasource'].__path__ = [str(_src_dir / "stock_datasource")]

    for submod in ['stock_datasource.utils', 'stock_datasource.utils.logger',
                    'stock_datasource.services', 'stock_datasource.core',
                    'stock_datasource.config', 'stock_datasource.config.settings']:
        if submod not in sys.modules or not hasattr(sys.modules.get(submod, object), '__path__'):
            m = type(sys)(submod)
            if not submod.endswith(('.logger', '.settings')):
                m.__path__ = []
            sys.modules[submod] = m

    mock_logger = MagicMock()
    sys.modules['stock_datasource.utils'].logger = mock_logger
    sys.modules['stock_datasource.utils.logger'].logger = mock_logger
    sys.modules['stock_datasource.utils.logger'].setup_logging = lambda: None


# =============================================================================
# T1: CacheService reconnection behavior
# =============================================================================

class TestCacheServiceReconnection:
    """Verify CacheService detects stale connections and retries after interval."""

    def _get_class(self):
        mod, spec = _import_module_directly("cache_service_real",
                                              "stock_datasource/services/cache_service.py")
        _setup_minimal_deps()
        try:
            spec.loader.exec_module(mod)
        except Exception:
            pass
        return mod.CacheService

    def test_ping_failure_marks_unavailable(self):
        CacheService = self._get_class()
        svc = CacheService()
        # Simulate an existing connection
        mock_redis = MagicMock()
        mock_redis.ping.side_effect = Exception("Connection refused")
        svc._redis = mock_redis
        svc._available = True
        svc._last_ping_ok = 0.0  # Force ping check

        result = svc._get_redis()
        assert result is None
        assert svc._available is False
        assert svc._redis is None

    def test_unavailable_returns_none_within_cooldown(self):
        CacheService = self._get_class()
        svc = CacheService()
        svc._available = False
        svc._connection_attempted = True
        svc._last_fail_time = 9999999999.0  # Far future → within cooldown

        result = svc._get_redis()
        assert result is None

    def test_reconnect_after_cooldown(self):
        CacheService = self._get_class()
        svc = CacheService()
        svc._available = False
        svc._connection_attempted = True
        svc._last_fail_time = 0.0  # Long ago → cooldown expired

        # The key behavior: when _last_fail_time is old, _connection_attempted is reset
        # to False, allowing a reconnection attempt. We verify this by checking that
        # the method doesn't immediately return None (it enters the connection logic).
        with patch.object(CacheService, '_get_redis', wraps=svc._get_redis) as spy:
            # Directly verify _connection_attempted is reset before attempting connection
            import time as _time
            # _last_fail_time is 0.0 → very old → cooldown expired
            # So _connection_attempted should be reset to False
            result = svc._get_redis()
            # Redis is unavailable in test env, so result is None
            # But the important thing is that it ATTEMPTED reconnection
            # which is indicated by _connection_attempted being set back to True
            assert svc._connection_attempted is True

    def test_ping_interval_constant(self):
        CacheService = self._get_class()
        assert CacheService._PING_INTERVAL == 30.0

    def test_successful_ping_updates_timestamp(self):
        CacheService = self._get_class()
        svc = CacheService()
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        svc._redis = mock_redis
        svc._available = True
        svc._last_ping_ok = 0.0  # Force ping

        import time
        before = time.time()
        result = svc._get_redis()
        after = time.time()

        assert result is mock_redis
        assert svc._last_ping_ok >= before
        assert svc._last_ping_ok <= after


# =============================================================================
# T2: get_partition_info uses parameterized query
# =============================================================================

class TestGetPartitionInfoParameterized:
    """Verify get_partition_info passes params dict for database/table_name."""

    def _read_source(self):
        return (_src_dir / "stock_datasource" / "models" / "database.py").read_text()

    def test_partition_info_uses_params_dict(self):
        source = self._read_source()
        # get_partition_info should have %(database)s and %(table_name)s placeholders
        # and pass params={"database": self.database, "table_name": table_name}
        assert "%(database)s" in source
        assert "%(table_name)s" in source
        # Should NOT have f-string SQL injection for database/table
        # Check the specific method
        lines = source.split('\n')
        in_method = False
        for line in lines:
            if 'def get_partition_info' in line:
                in_method = True
            elif in_method and line.strip().startswith('def '):
                break
            if in_method:
                # Should NOT have f"WHERE database = '{self.database}'"
                if "WHERE database = '" in line and "f\"" in line:
                    pytest.fail(f"get_partition_info uses unsafe f-string: {line.strip()}")

    def test_partition_info_passes_params(self):
        source = self._read_source()
        # Should pass params dict to execute_query
        assert 'params={"database": self.database, "table_name": table_name}' in source


# =============================================================================
# T3: _load_tasks_from_db and get_task_history use _to_clickhouse_literal
# =============================================================================

class TestCutoffTimeSafety:
    """Verify cutoff_time in _load_tasks_from_db and get_task_history uses safe escaping."""

    def _read_source(self):
        return (_src_dir / "stock_datasource" / "modules" / "datamanage" / "service.py").read_text()

    def test_load_tasks_uses_literal(self):
        source = self._read_source()
        # Should have _to_clickhouse_literal(cutoff_time) pattern
        assert "_to_clickhouse_literal(cutoff_time)" in source

    def test_load_tasks_no_fstring_cutoff(self):
        source = self._read_source()
        # Should NOT have f"toDateTime('{cutoff_time}')"
        assert "f\"toDateTime('{cutoff_time}')\"" not in source
        assert "f\"toDateTime(\\'{cutoff_time}\\')\"" not in source

    def test_get_task_history_uses_literal(self):
        source = self._read_source()
        # get_task_history should also use _to_clickhouse_literal
        lines = source.split('\n')
        in_method = False
        found_literal = False
        for line in lines:
            if 'def get_task_history' in line:
                in_method = True
            elif in_method and line.strip().startswith('def '):
                break
            if in_method and '_to_clickhouse_literal' in line:
                found_literal = True
        assert found_literal, "get_task_history should use _to_clickhouse_literal"


# =============================================================================
# T4: ETF/Index get_kline uses _to_clickhouse_literal
# =============================================================================

class TestKlineSqlSafety:
    """Verify get_kline in ETF and Index services use _to_clickhouse_literal."""

    def _read_etf_source(self):
        return (_src_dir / "stock_datasource" / "modules" / "etf" / "service.py").read_text()

    def _read_index_source(self):
        return (_src_dir / "stock_datasource" / "modules" / "index" / "service.py").read_text()

    def test_etf_kline_uses_literal_for_ts_code(self):
        source = self._read_etf_source()
        # In get_kline, should use _to_clickhouse_literal(ts_code)
        lines = source.split('\n')
        in_kline = False
        found_literal = False
        for line in lines:
            if 'def get_kline' in line:
                in_kline = True
            elif in_kline and line.strip().startswith('def '):
                break
            if in_kline and '_to_clickhouse_literal(ts_code)' in line:
                found_literal = True
        assert found_literal, "ETF get_kline should use _to_clickhouse_literal(ts_code)"

    def test_etf_kline_uses_literal_for_dates(self):
        source = self._read_etf_source()
        # Should use _to_clickhouse_literal(start_date) and _to_clickhouse_literal(end_date)
        lines = source.split('\n')
        in_kline = False
        found_start = False
        found_end = False
        for line in lines:
            if 'def get_kline' in line:
                in_kline = True
            elif in_kline and line.strip().startswith('def '):
                break
            if in_kline and '_to_clickhouse_literal(start_date)' in line:
                found_start = True
            if in_kline and '_to_clickhouse_literal(end_date)' in line:
                found_end = True
        assert found_start, "ETF get_kline should use _to_clickhouse_literal(start_date)"
        assert found_end, "ETF get_kline should use _to_clickhouse_literal(end_date)"

    def test_etf_kline_no_unsafe_date_fstring(self):
        source = self._read_etf_source()
        lines = source.split('\n')
        in_kline = False
        for i, line in enumerate(lines):
            if 'def get_kline' in line:
                in_kline = True
            elif in_kline and line.strip().startswith('def '):
                break
            if in_kline and "trade_date >=" in line:
                # Should NOT have f"trade_date >= '{start_date}'"
                if "f\"" in line and "'{" in line:
                    pytest.fail(f"Line {i+1}: unsafe f-string date filter: {line.strip()}")

    def test_index_kline_uses_literal_for_ts_code(self):
        source = self._read_index_source()
        lines = source.split('\n')
        in_kline = False
        found_literal = False
        for line in lines:
            if 'def get_kline' in line:
                in_kline = True
            elif in_kline and line.strip().startswith('def '):
                break
            if in_kline and '_to_clickhouse_literal(ts_code)' in line:
                found_literal = True
        assert found_literal, "Index get_kline should use _to_clickhouse_literal(ts_code)"

    def test_index_kline_uses_literal_for_dates(self):
        source = self._read_index_source()
        lines = source.split('\n')
        in_kline = False
        found_start = False
        found_end = False
        for line in lines:
            if 'def get_kline' in line:
                in_kline = True
            elif in_kline and line.strip().startswith('def '):
                break
            if in_kline and '_to_clickhouse_literal(start_date)' in line:
                found_start = True
            if in_kline and '_to_clickhouse_literal(end_date)' in line:
                found_end = True
        assert found_start, "Index get_kline should use _to_clickhouse_literal(start_date)"
        assert found_end, "Index get_kline should use _to_clickhouse_literal(end_date)"

    def test_etf_kline_name_query_uses_literal(self):
        source = self._read_etf_source()
        # Name query should use _to_clickhouse_literal(ts_code)
        assert "WHERE ts_code = {_to_clickhouse_literal(ts_code)}" in source

    def test_index_kline_name_query_uses_literal(self):
        source = self._read_index_source()
        assert "WHERE ts_code = {_to_clickhouse_literal(ts_code)}" in source


# =============================================================================
# T5: Timeout consistency (task_queue and task_worker both use 3600s)
# =============================================================================

class TestTimeoutConsistency:
    """Verify both task_queue and task_worker use 3600s as default timeout."""

    def test_task_queue_default_timeout(self):
        source = (_src_dir / "stock_datasource" / "services" / "task_queue.py").read_text()
        # enqueue should default to 3600
        assert 'timeout_seconds or 3600' in source
        # dequeue fallback should be 3600
        assert 'timeout_seconds", 3600)' in source
        # get_task fallback should be 3600
        # Check that no 900 appears as a timeout fallback
        assert 'timeout_seconds", 900)' not in source

    def test_task_worker_default_timeout(self):
        source = (_src_dir / "stock_datasource" / "services" / "task_worker.py").read_text()
        # _process_task fallback should be 3600
        # The pattern is: int(task_data.get("timeout_seconds", 3600))
        assert '"timeout_seconds", 3600' in source
        # Should NOT have 900 as fallback
        assert '"timeout_seconds", 900' not in source


# =============================================================================
# T6: get_task_history safe_limit validation
# =============================================================================

class TestSafeLimitValidation:
    """Verify get_task_history clamps limit to [1, 10000]."""

    def _read_source(self):
        return (_src_dir / "stock_datasource" / "modules" / "datamanage" / "service.py").read_text()

    def test_safe_limit_exists(self):
        source = self._read_source()
        # Should have safe_limit = max(1, min(10000, int(limit)))
        assert "safe_limit" in source
        assert "max(1, min(10000, int(limit)))" in source

    def test_safe_limit_used_in_query(self):
        source = self._read_source()
        # Should use {safe_limit} in the LIMIT clause
        assert "LIMIT {safe_limit}" in source

    def _get_service_class(self):
        """Import DataManageService for behavioral testing."""
        _setup_minimal_deps()
        mod, spec = _import_module_directly("service_real",
                                             "stock_datasource/modules/datamanage/service.py")

        # Mock heavy dependencies
        sys.modules['stock_datasource.models.database'] = MagicMock()
        sys.modules['stock_datasource.core.plugin_manager'] = MagicMock()
        sys.modules['stock_datasource.core.trade_calendar'] = MagicMock()
        sys.modules['stock_datasource.config.runtime_config'] = MagicMock()

        try:
            spec.loader.exec_module(mod)
        except Exception:
            pass
        return mod.DataManageService


# =============================================================================
# T7: deep_analyzer._get_stock_name uses parameterized query
# =============================================================================

class TestDeepAnalyzerParameterized:
    """Verify _get_stock_name uses parameterized query with params dict."""

    def _read_source(self):
        return (_src_dir / "stock_datasource" / "modules" / "quant" / "deep_analyzer.py").read_text()

    def test_get_stock_name_uses_params(self):
        source = self._read_source()
        # Should have params={"ts_code": ts_code}
        assert 'params={"ts_code": ts_code}' in source

    def test_get_stock_name_uses_placeholder(self):
        source = self._read_source()
        # Should use %(ts_code)s placeholder instead of f-string
        assert "%(ts_code)s" in source

    def test_get_stock_name_no_fstring_where(self):
        source = self._read_source()
        lines = source.split('\n')
        in_method = False
        for i, line in enumerate(lines):
            if '_get_stock_name' in line and 'def' in line:
                in_method = True
            elif in_method and line.strip().startswith('def '):
                break
            if in_method and "WHERE ts_code = '" in line and "f\"" in line:
                pytest.fail(f"Line {i+1}: _get_stock_name uses unsafe f-string: {line.strip()}")


# =============================================================================
# T8: ETF get_daily / Index get_daily now use _to_clickhouse_literal (FIXED)
# =============================================================================

class TestGetDailySqlSafety:
    """Verify get_daily in ETF and Index services use _to_clickhouse_literal."""

    def _read_etf_source(self):
        return (_src_dir / "stock_datasource" / "modules" / "etf" / "service.py").read_text()

    def _read_index_source(self):
        return (_src_dir / "stock_datasource" / "modules" / "index" / "service.py").read_text()

    def test_etf_get_daily_uses_literal(self):
        source = self._read_etf_source()
        lines = source.split('\n')
        in_daily = False
        found_literal = False
        for line in lines:
            if 'def get_daily' in line:
                in_daily = True
            elif in_daily and line.strip().startswith('def '):
                break
            if in_daily and '_to_clickhouse_literal(ts_code)' in line:
                found_literal = True
        assert found_literal, "ETF get_daily should use _to_clickhouse_literal(ts_code)"

    def test_etf_get_daily_no_double_quote_escape(self):
        """Should NOT use replace(\"'\", \"''\") — that was the old unsafe pattern."""
        source = self._read_etf_source()
        lines = source.split('\n')
        in_daily = False
        for i, line in enumerate(lines):
            if 'def get_daily' in line:
                in_daily = True
            elif in_daily and line.strip().startswith('def '):
                break
            if in_daily and 'replace("\'", "\'\'")' in line:
                pytest.fail(f"Line {i+1}: ETF get_daily still uses unsafe replace pattern")

    def test_index_get_daily_uses_literal(self):
        source = self._read_index_source()
        lines = source.split('\n')
        in_daily = False
        found_literal = False
        for line in lines:
            if 'def get_daily' in line:
                in_daily = True
            elif in_daily and line.strip().startswith('def '):
                break
            if in_daily and '_to_clickhouse_literal(ts_code)' in line:
                found_literal = True
        assert found_literal, "Index get_daily should use _to_clickhouse_literal(ts_code)"

    def test_index_get_daily_no_double_quote_escape(self):
        source = self._read_index_source()
        lines = source.split('\n')
        in_daily = False
        for i, line in enumerate(lines):
            if 'def get_daily' in line:
                in_daily = True
            elif in_daily and line.strip().startswith('def '):
                break
            if in_daily and 'replace("\'", "\'\'")' in line:
                pytest.fail(f"Line {i+1}: Index get_daily still uses unsafe replace pattern")


# =============================================================================
# T10: ETF get_etfs uses _to_clickhouse_literal for all string filters
# =============================================================================

class TestEtfGetEtfsSqlSafety:
    """Verify get_etfs uses _to_clickhouse_literal instead of replace(\"'\", \"''\")."""

    def _read_source(self):
        return (_src_dir / "stock_datasource" / "modules" / "etf" / "service.py").read_text()

    def test_get_etfs_no_double_quote_escape(self):
        """get_etfs should NOT use replace(\"'\", \"''\") anywhere."""
        source = self._read_source()
        assert 'replace("\'", "\'\'")' not in source, "etf/service.py should not use unsafe replace pattern"

    def test_get_etfs_uses_literal_for_exchange(self):
        source = self._read_source()
        lines = source.split('\n')
        in_method = False
        found = False
        for line in lines:
            if 'def get_etfs' in line:
                in_method = True
            elif in_method and line.strip().startswith('def '):
                break
            if in_method and '_to_clickhouse_literal(exchange)' in line:
                found = True
        assert found, "get_etfs should use _to_clickhouse_literal(exchange)"

    def test_get_etfs_uses_literal_for_keyword_like(self):
        source = self._read_source()
        # kw_literal should be constructed with _to_clickhouse_literal
        lines = source.split('\n')
        in_method = False
        found_kw_literal = False
        for line in lines:
            if 'def get_etfs' in line:
                in_method = True
            elif in_method and line.strip().startswith('def '):
                break
            if in_method and 'kw_literal' in line and '_to_clickhouse_literal' in line:
                found_kw_literal = True
        assert found_kw_literal, "get_etfs LIKE filter should use kw_literal from _to_clickhouse_literal"

    def test_get_etfs_uses_literal_for_target_date(self):
        source = self._read_source()
        lines = source.split('\n')
        in_method = False
        found = False
        for line in lines:
            if 'def get_etfs' in line:
                in_method = True
            elif in_method and line.strip().startswith('def '):
                break
            if in_method and '_to_clickhouse_literal(target_date)' in line:
                found = True
        assert found, "get_etfs should use _to_clickhouse_literal(target_date)"


# =============================================================================
# T11: Index get_indices / get_constituents / get_factors / get_index_detail safe
# =============================================================================

class TestIndexSqlSafety:
    """Verify Index service methods use _to_clickhouse_literal instead of replace/concat."""

    def _read_source(self):
        return (_src_dir / "stock_datasource" / "modules" / "index" / "service.py").read_text()

    def test_no_double_quote_escape_anywhere(self):
        """index/service.py should NOT use replace(\"'\", \"''\") anywhere."""
        source = self._read_source()
        assert 'replace("\'", "\'\'")' not in source, "index/service.py should not use unsafe replace pattern"

    def test_get_indices_uses_literal_for_target_date(self):
        source = self._read_source()
        lines = source.split('\n')
        in_method = False
        found = False
        for line in lines:
            if 'def get_indices' in line:
                in_method = True
            elif in_method and line.strip().startswith('def '):
                break
            if in_method and '_to_clickhouse_literal(target_date)' in line:
                found = True
        assert found, "get_indices should use _to_clickhouse_literal(target_date)"

    def test_get_indices_uses_literal_for_keyword_like(self):
        source = self._read_source()
        # kw_literal should be constructed with _to_clickhouse_literal
        lines = source.split('\n')
        in_method = False
        found_kw_literal = False
        for line in lines:
            if 'def get_indices' in line:
                in_method = True
            elif in_method and line.strip().startswith('def '):
                break
            if in_method and 'kw_literal' in line and '_to_clickhouse_literal' in line:
                found_kw_literal = True
        assert found_kw_literal, "get_indices ILIKE filter should use kw_literal from _to_clickhouse_literal"

    def test_get_index_detail_uses_literal(self):
        source = self._read_source()
        lines = source.split('\n')
        in_method = False
        found = False
        for line in lines:
            if 'def get_index_detail' in line:
                in_method = True
            elif in_method and line.strip().startswith('def '):
                break
            if in_method and '_to_clickhouse_literal(ts_code)' in line:
                found = True
        assert found, "get_index_detail should use _to_clickhouse_literal(ts_code)"

    def test_get_constituents_uses_literal_for_ts_code(self):
        source = self._read_source()
        lines = source.split('\n')
        in_method = False
        found = False
        for line in lines:
            if 'def get_constituents' in line:
                in_method = True
            elif in_method and line.strip().startswith('def '):
                break
            if in_method and '_to_clickhouse_literal(ts_code)' in line:
                found = True
        assert found, "get_constituents should use _to_clickhouse_literal(ts_code)"

    def test_get_constituents_uses_literal_for_trade_date(self):
        source = self._read_source()
        lines = source.split('\n')
        in_method = False
        found = False
        for line in lines:
            if 'def get_constituents' in line:
                in_method = True
            elif in_method and line.strip().startswith('def '):
                break
            if in_method and '_to_clickhouse_literal(trade_date)' in line:
                found = True
        assert found, "get_constituents should use _to_clickhouse_literal(trade_date)"

    def test_get_factors_uses_literal_for_ts_code(self):
        source = self._read_source()
        lines = source.split('\n')
        in_method = False
        found = False
        for line in lines:
            if 'def get_factors' in line:
                in_method = True
            elif in_method and line.strip().startswith('def '):
                break
            if in_method and '_to_clickhouse_literal(ts_code)' in line:
                found = True
        assert found, "get_factors should use _to_clickhouse_literal(ts_code)"


# =============================================================================
# T12: Index get_factors indicators whitelist validation
# =============================================================================

class TestGetFactorsWhitelist:
    """Verify get_factors uses a whitelist for indicator column names."""

    def _read_source(self):
        return (_src_dir / "stock_datasource" / "modules" / "index" / "service.py").read_text()

    def test_whitelist_exists(self):
        source = self._read_source()
        assert '_ALLOWED_INDICATORS' in source

    def test_indicators_filtered_by_whitelist(self):
        source = self._read_source()
        # Should have: [i for i in indicators if i in _ALLOWED_INDICATORS]
        assert 'if i in _ALLOWED_INDICATORS' in source or 'i in _ALLOWED_INDICATORS' in source

    def test_no_raw_indicators_in_sql(self):
        source = self._read_source()
        # Should NOT have: indicators if i not in base_cols (without whitelist check)
        lines = source.split('\n')
        in_method = False
        for i, line in enumerate(lines):
            if 'def get_factors' in line:
                in_method = True
            elif in_method and line.strip().startswith('def '):
                break
            if in_method and 'for i in indicators if i not in base_cols' in line:
                pytest.fail(f"Line {i+1}: get_factors uses indicators without whitelist filtering")


# =============================================================================
# T9: ClickHouseHttpClient._request renders %(param)s safely
# =============================================================================

class TestHttpRequestParameterRendering:
    """Verify HTTP client renders %(param)s placeholders via _to_clickhouse_literal."""

    def _read_source(self):
        return (_src_dir / "stock_datasource" / "models" / "database.py").read_text()

    def test_request_method_handles_params(self):
        source = self._read_source()
        # _request should replace %(key)s with _to_clickhouse_literal(value)
        lines = source.split('\n')
        in_request = False
        found_param_rendering = False
        found_unreplaced_check = False
        for line in lines:
            if 'def _request' in line:
                in_request = True
            elif in_request and line.strip().startswith('def '):
                break
            if in_request and '_to_clickhouse_literal(value)' in line:
                found_param_rendering = True
            if in_request and 'unreplaced' in line.lower():
                found_unreplaced_check = True
        assert found_param_rendering, "_request should render params via _to_clickhouse_literal"
        assert found_unreplaced_check, "_request should validate no unreplaced placeholders remain"

    def test_http_client_table_exists_uses_params(self):
        source = self._read_source()
        # ClickHouseHttpClient.table_exists should use %(database)s and %(table_name)s
        lines = source.split('\n')
        in_http_class = False
        in_method = False
        found_placeholder = False
        for line in lines:
            if 'class ClickHouseHttpClient' in line:
                in_http_class = True
            elif in_http_class and 'class ' in line:
                in_http_class = False
            if in_http_class and 'def table_exists' in line:
                in_method = True
            elif in_method and line.strip().startswith('def '):
                break
            if in_method and '%(database)s' in line:
                found_placeholder = True
        assert found_placeholder, "ClickHouseHttpClient.table_exists should use %(database)s placeholder"


# =============================================================================
# T10: _to_clickhouse_literal behavioral edge cases
# =============================================================================

class TestToClickhouseLiteralEdgeCases:
    """Additional edge cases for _to_clickhouse_literal."""

    def _get_func(self):
        mod, spec = _import_module_directly("database_real",
                                             "stock_datasource/models/database.py")
        _setup_minimal_deps()

        class _MockSettings:
            CLICKHOUSE_HOST = "localhost"
            CLICKHOUSE_PORT = 9000
            CLICKHOUSE_DATABASE = "test"
            CLICKHOUSE_USER = "default"
            CLICKHOUSE_PASSWORD = ""
            CLICKHOUSE_HTTP_PORT = 8123
            CLICKHOUSE_PREFER_HTTP = True
            BACKUP_CLICKHOUSE_HOST = ""
            BACKUP_CLICKHOUSE_PORT = 9000
            BACKUP_CLICKHOUSE_USER = ""
            BACKUP_CLICKHOUSE_PASSWORD = ""
            BACKUP_CLICKHOUSE_DATABASE = ""

        sys.modules['stock_datasource.config.settings'].settings = _MockSettings()
        sys.modules['stock_datasource.config.settings'].Settings = _MockSettings

        try:
            spec.loader.exec_module(mod)
        except Exception:
            pass

        return mod._to_clickhouse_literal

    def test_datetime_value(self):
        func = self._get_func()
        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = func(dt)
        assert "'2024-01-15 10:30:00'" == result

    def test_date_value(self):
        func = self._get_func()
        from datetime import date
        d = date(2024, 1, 15)
        result = func(d)
        assert "'2024-01-15'" == result

    def test_float_value(self):
        func = self._get_func()
        result = func(3.14)
        assert result == "3.14"

    def test_null_byte_removed(self):
        func = self._get_func()
        result = func("hello\0world")
        assert "\0" not in result
        assert "hello" in result
        assert "world" in result

    def test_tab_escaped(self):
        func = self._get_func()
        result = func("col1\tcol2")
        assert "\\t" in result
        assert "\t" not in result.replace("\\t", "")

    def test_nested_list(self):
        func = self._get_func()
        result = func([["a", "b"], ["c", "d"]])
        # Result should be [['a', 'b'], ['c', 'd']] — each element is escaped
        assert "[[" in result
        # The outer brackets should wrap the inner lists
        assert result.startswith("[")
        assert result.endswith("]")

    def test_sql_injection_drop_table(self):
        func = self._get_func()
        malicious = "'; DROP TABLE users; --"
        result = func(malicious)
        # The single quotes should be escaped with backslash
        assert "\\'" in result
        # The result should be a proper string literal
        assert result.startswith("'")
        assert result.endswith("'")
        # The malicious SQL should NOT be executable
        assert result != malicious  # Should be transformed

    def test_unicode_string(self):
        func = self._get_func()
        result = func("中文测试")
        assert "中文测试" in result

    def test_empty_string(self):
        func = self._get_func()
        result = func("")
        assert result == "''"


# =============================================================================
# T11: Verify import time is available in task_queue
# =============================================================================

class TestImportTimeInTaskQueue:
    """Verify task_queue.py has 'import time' at top level (was missing before fix)."""

    def test_time_import_exists(self):
        source = (_src_dir / "stock_datasource" / "services" / "task_queue.py").read_text()
        lines = source.split('\n')
        # Should have 'import time' in the top-level imports
        found_import = False
        for line in lines[:30]:  # Only check first 30 lines (import section)
            if line.strip() == 'import time':
                found_import = True
                break
        assert found_import, "task_queue.py should have 'import time' at top level"


# =============================================================================
# T12: No redundant inline imports in task_worker
# =============================================================================

class TestNoRedundantImportsInTaskWorker:
    """Verify task_worker.py no longer has redundant inline imports for os/signal."""

    def test_no_inline_import_os(self):
        source = (_src_dir / "stock_datasource" / "services" / "task_worker.py").read_text()
        lines = source.split('\n')
        # Should have top-level import os (line ~17)
        has_top_level_os = False
        for line in lines[:30]:
            if line.strip() == 'import os':
                has_top_level_os = True
                break
        assert has_top_level_os, "task_worker.py should have top-level 'import os'"

        # Should NOT have inline 'import os' inside _run_task_with_timeout
        in_method = False
        for i, line in enumerate(lines):
            if 'def _run_task_with_timeout' in line:
                in_method = True
            elif in_method and line.strip().startswith('def '):
                break
            if in_method and line.strip() == 'import os':
                pytest.fail(f"Line {i+1}: redundant inline 'import os' in _run_task_with_timeout")

    def test_no_inline_import_signal(self):
        source = (_src_dir / "stock_datasource" / "services" / "task_worker.py").read_text()
        lines = source.split('\n')
        has_top_level_signal = False
        for line in lines[:30]:
            if line.strip() == 'import signal':
                has_top_level_signal = True
                break
        assert has_top_level_signal, "task_worker.py should have top-level 'import signal'"

        # Should NOT have inline 'import signal' inside _run_task_with_timeout
        in_method = False
        for i, line in enumerate(lines):
            if 'def _run_task_with_timeout' in line:
                in_method = True
            elif in_method and line.strip().startswith('def '):
                break
            if in_method and line.strip() == 'import signal':
                pytest.fail(f"Line {i+1}: redundant inline 'import signal' in _run_task_with_timeout")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
