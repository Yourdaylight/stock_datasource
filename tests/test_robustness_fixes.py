"""Tests for robustness fixes applied to the data fetching pipeline.

Covers:
- C1-C5: SQL injection prevention via _to_clickhouse_literal and parameterized queries
- I1: Redis connection recovery after disconnect
- I2: Full sync failure threshold (>10% fails → task fails)
- I3: Dequeue fallback timeout alignment (3600 not 900)
- I5: Subprocess tree cleanup on timeout
- I7: insert_dataframe has retry decorator
- M1: _classify_error_type recognizes rate_limit
"""

import sys
import os
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

# Add src to path so we can import the real modules (bypass conftest mocks)
_src_dir = Path(__file__).parent.parent / "src"
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))


# =============================================================================
# C1-C5: _to_clickhouse_literal prevents SQL injection
# =============================================================================

class TestToClickhouseLiteral:
    """Verify _to_clickhouse_literal handles special characters safely."""

    def _get_func(self):
        # Import directly from the real file, bypassing conftest mock
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "database_real",
            _src_dir / "stock_datasource" / "models" / "database.py",
            submodule_search_locations=[]
        )
        mod = importlib.util.module_from_spec(spec)
        # Set up minimal dependencies
        sys.modules['stock_datasource'] = type(sys)('stock_datasource')
        sys.modules['stock_datasource'].__path__ = [str(_src_dir / "stock_datasource")]
        sys.modules['stock_datasource.config'] = type(sys)('stock_datasource.config')
        sys.modules['stock_datasource.config'].__path__ = [str(_src_dir / "stock_datasource" / "config")]
        sys.modules['stock_datasource.config.settings'] = type(sys)('stock_datasource.config.settings')

        class _MockSettings:
            CLICKHOUSE_HOST = "localhost"
            CLICKHOUSE_PORT = 9000
            CLICKHOUSE_DATABASE = "test"
            CLICKHOUSE_USER = "default"
            CLICKHOUSE_PASSWORD = ""
            CLICKHOUSE_HTTP_PORT = 8123
            CLICKHOUSE_BACKUP_HOST = ""
            CLICKHOUSE_BACKUP_PORT = 9000
            BACKUP_CLICKHOUSE_HOST = ""
            BACKUP_CLICKHOUSE_PORT = 9000
            BACKUP_CLICKHOUSE_USER = ""
            BACKUP_CLICKHOUSE_PASSWORD = ""
            BACKUP_CLICKHOUSE_DATABASE = ""
            CLICKHOUSE_PREFER_HTTP = True

        sys.modules['stock_datasource.config.settings'].settings = _MockSettings()
        sys.modules['stock_datasource.config.settings'].Settings = _MockSettings

        # Skip heavy __init__ imports by providing mock submodules
        for submod in ['stock_datasource.utils', 'stock_datasource.utils.logger',
                        'stock_datasource.services', 'stock_datasource.core']:
            if submod not in sys.modules or not hasattr(sys.modules[submod], '__path__'):
                sys.modules[submod] = type(sys)(submod)

        # Provide mock logger
        mock_logger = MagicMock()
        sys.modules['stock_datasource.utils'].logger = mock_logger
        sys.modules['stock_datasource.utils.logger'].logger = mock_logger
        sys.modules['stock_datasource.utils.logger'].setup_logging = lambda: None

        try:
            spec.loader.exec_module(mod)
        except Exception:
            pass  # May fail on some imports, but _to_clickhouse_literal is at top level

        return mod._to_clickhouse_literal

    def test_escapes_single_quotes(self):
        func = self._get_func()
        result = func("it's a test")
        assert "\\'" in result
        assert result == "'it\\'s a test'"

    def test_handles_none(self):
        func = self._get_func()
        assert func(None) == "NULL"

    def test_handles_list_of_strings(self):
        func = self._get_func()
        result = func(["2024-01-01", "2024-01-02"])
        assert "2024-01-01" in result
        assert result.startswith("[")
        assert result.endswith("]")

    def test_handles_int(self):
        func = self._get_func()
        assert func(42) == "42"

    def test_handles_bool(self):
        func = self._get_func()
        assert func(True) == "1"
        assert func(False) == "0"

    def test_sql_injection_attempt_escaped(self):
        func = self._get_func()
        malicious = "'; DROP TABLE users; --"
        result = func(malicious)
        assert "\\'" in result
        assert result.startswith("'")
        assert result.endswith("'")

    def test_escapes_backslashes(self):
        func = self._get_func()
        result = func("path\\to\\file")
        assert "\\\\" in result


# =============================================================================
# M1: Error classification
# =============================================================================

class TestErrorClassification:
    """Verify _classify_error_type recognizes rate_limit errors."""

    def _get_func(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "task_worker_real",
            _src_dir / "stock_datasource" / "services" / "task_worker.py",
        )
        mod = importlib.util.module_from_spec(spec)

        # Provide minimal mocks
        for submod in ['stock_datasource', 'stock_datasource.utils',
                        'stock_datasource.utils.logger',
                        'stock_datasource.config', 'stock_datasource.config.settings',
                        'stock_datasource.services']:
            if submod not in sys.modules or not hasattr(sys.modules.get(submod, object), '__path__'):
                m = type(sys)(submod)
                if '.' not in submod or submod.endswith(('.logger', '.settings')):
                    pass
                else:
                    m.__path__ = []
                sys.modules[submod] = m

        mock_logger = MagicMock()
        sys.modules['stock_datasource.utils.logger'].logger = mock_logger
        sys.modules['stock_datasource.utils.logger'].setup_logging = lambda: None

        class _MockSettings:
            REDIS_ENABLED = True
            REDIS_HOST = "localhost"
            REDIS_PORT = 6379
            REDIS_PASSWORD = None
            REDIS_DB = 0

        sys.modules['stock_datasource.config.settings'].settings = _MockSettings()

        try:
            spec.loader.exec_module(mod)
        except Exception:
            pass

        return mod._classify_error_type

    def test_ip_limit(self):
        func = self._get_func()
        assert func("IP数量超限") == "ip_limit"

    def test_rate_limit_per_minute(self):
        func = self._get_func()
        assert func("每分钟最多访问120次") == "rate_limit"

    def test_rate_limit_frequency(self):
        func = self._get_func()
        assert func("访问频次超限") == "rate_limit"

    def test_rate_limit_english(self):
        func = self._get_func()
        assert func("rate limit exceeded") == "rate_limit"

    def test_config_error(self):
        func = self._get_func()
        assert func("TUSHARE_TOKEN not configured") == "config_error"

    def test_generic_retryable(self):
        func = self._get_func()
        assert func("Connection timeout") == "retryable"

    def test_empty_message(self):
        func = self._get_func()
        assert func("") == "retryable"
        assert func(None) == "retryable"


# =============================================================================
# Source-code level verification (doesn't need imports)
# =============================================================================

class TestSourceCodeVerification:
    """Verify fixes by inspecting source code directly."""

    def _read_file(self, rel_path):
        return (_src_dir / rel_path).read_text()

    # I3: Dequeue fallback timeout
    def test_dequeue_fallback_is_3600(self):
        source = self._read_file("stock_datasource/services/task_queue.py")
        # Should NOT have 900 as timeout fallback
        assert 'timeout_seconds", 900)' not in source
        # Should have 3600 as timeout fallback
        assert 'timeout_seconds", 3600)' in source

    # I5: Subprocess tree cleanup
    def test_killpg_in_run_task_with_timeout(self):
        source = self._read_file("stock_datasource/services/task_worker.py")
        assert "killpg" in source
        assert "SIGTERM" in source
        assert "SIGKILL" in source

    # I2: Full sync failure tracking
    def test_full_sync_failure_tracking(self):
        source = self._read_file("stock_datasource/services/task_worker.py")
        assert "failed_dates" in source
        assert "0.1" in source  # 10% threshold

    # C5: table_exists parameterized (TCP path)
    def test_table_exists_uses_params(self):
        source = self._read_file("stock_datasource/models/database.py")
        # TCP client table_exists should use %(database)s and %(table_name)s
        # Find the table_exists in ClickHouseClient (not ClickHouseHttpClient)
        # Both should use parameterized queries now
        assert "%(database)s" in source
        assert "%(table_name)s" in source

    # C2: Extractor parameterized queries
    def test_extractor_no_fstring_sql_injection(self):
        source = self._read_file("stock_datasource/utils/extractor.py")
        lines = source.split('\n')
        for i, line in enumerate(lines):
            # Should not have f"... WHERE trade_date = '{trade_date}'"
            if "WHERE trade_date = '" in line:
                assert "f\"" not in line, f"Line {i+1}: unsafe f-string SQL: {line.strip()}"
            if "WHERE cal_date = '" in line:
                assert "f\"" not in line, f"Line {i+1}: unsafe f-string SQL: {line.strip()}"

    # I7: insert_dataframe has retry
    def test_insert_dataframe_has_retry(self):
        source = self._read_file("stock_datasource/models/database.py")
        # Find ALL insert_dataframe method definitions
        # The ClickHouseClient.insert_dataframe (the one we care about) should have @retry
        lines = source.split('\n')
        for i, line in enumerate(lines):
            # Look for the one in ClickHouseClient class (has @retry before it)
            if 'def insert_dataframe' in line and 'self' in line and 'table_name' in line:
                # Check previous lines for @retry
                for j in range(i-1, max(i-5, 0), -1):
                    if '@retry' in lines[j]:
                        return  # Found it!
                    elif lines[j].strip().startswith('def ') or lines[j].strip().startswith('class '):
                        break
        # If we get here without finding @retry on any insert_dataframe, fail
        # Actually, let's just check if @retry appears before the LAST insert_dataframe
        # (which is the ClickHouseClient one)
        last_idx = max(i for i, l in enumerate(lines) if 'def insert_dataframe' in l and 'self' in l)
        for j in range(last_idx-1, max(last_idx-5, 0), -1):
            if '@retry' in lines[j]:
                return
        pytest.fail("ClickHouseClient.insert_dataframe should have @retry decorator")

    # I1: Redis ping check
    def test_redis_has_ping_check(self):
        source = self._read_file("stock_datasource/services/task_queue.py")
        # _get_redis should have a ping() call in the connection check path
        assert "self._redis.ping()" in source
        # Should handle ping failure
        assert "Reconnect" in source or "reconnect" in source or "_connected = False" in source

    # C1: _save_task_to_db uses _to_clickhouse_literal
    def test_save_task_uses_to_clickhouse_literal(self):
        source = self._read_file("stock_datasource/modules/datamanage/service.py")
        # Should NOT have f"'{task.error_message}'" pattern
        assert "f\"'{task.error_message}'\"" not in source.replace(' ', '')
        # Should use _to_clickhouse_literal
        assert "_to_clickhouse_literal(task.error_message)" in source
        assert "_to_clickhouse_literal(task.plugin_name)" in source

    # C3: check_dates_data_exists uses _to_clickhouse_literal
    def test_check_dates_uses_safe_literal(self):
        source = self._read_file("stock_datasource/modules/datamanage/service.py")
        # Should NOT have f"'{d}'" for date escaping
        assert "[f\"'{d}'\" for d in dates]" not in source.replace(' ', '')
        # Should use _to_clickhouse_literal
        assert "_to_clickhouse_literal(d) for d in dates" in source

    # C4: _batch_get_latest_dates uses _to_clickhouse_literal
    def test_batch_get_latest_dates_uses_safe_literal(self):
        source = self._read_file("stock_datasource/modules/datamanage/service.py")
        assert "_to_clickhouse_literal(t) for t in table_names" in source


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
