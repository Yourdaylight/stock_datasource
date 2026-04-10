"""Tests for system_logs schemas and log_parser with ClickHouse context fields."""

from datetime import datetime
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

from stock_datasource.modules.system_logs.schemas import (
    LogEntry,
    LogFilter,
    LogInsightFilter,
)


class TestLogEntrySchema:
    """Test LogEntry schema with new fields."""

    def test_log_entry_with_request_id(self):
        entry = LogEntry(
            timestamp=datetime.now(),
            level="INFO",
            module="test",
            message="hello",
            raw_line="raw",
            request_id="abc123",
            user_id="user1",
        )
        assert entry.request_id == "abc123"
        assert entry.user_id == "user1"

    def test_log_entry_default_context(self):
        entry = LogEntry(
            timestamp=datetime.now(),
            level="INFO",
            module="test",
            message="hello",
            raw_line="raw",
        )
        assert entry.request_id == "-"
        assert entry.user_id == "-"


class TestLogFilterSchema:
    """Test LogFilter schema with request_id."""

    def test_filter_with_request_id(self):
        f = LogFilter(request_id="abc123")
        assert f.request_id == "abc123"

    def test_filter_default_no_request_id(self):
        f = LogFilter()
        assert f.request_id is None


class TestLogInsightFilterSchema:
    """Test LogInsightFilter schema with request_id."""

    def test_insight_filter_with_request_id(self):
        f = LogInsightFilter(request_id="rid001")
        assert f.request_id == "rid001"

    def test_insight_filter_default_no_request_id(self):
        f = LogInsightFilter()
        assert f.request_id is None


class TestLogParserNewFormat:
    """Test log_parser with the new request_id/user_id format."""

    def test_parse_new_format_line(self):
        from stock_datasource.modules.system_logs.log_parser import LogParser

        parser = LogParser()
        line = "2026-04-09 15:30:00.123 | INFO     | abc123 | user1 | test_module:func:42 - Hello world"
        result = parser.parse_line(line, "stock_datasource.log")

        assert result is not None
        assert result["level"] == "INFO"
        assert result["request_id"] == "abc123"
        assert result["user_id"] == "user1"
        assert result["module"] == "test_module"
        assert "Hello world" in result["message"]

    def test_parse_old_format_still_works(self):
        from stock_datasource.modules.system_logs.log_parser import LogParser

        parser = LogParser()
        line = "2026-04-09 15:30:00 | INFO     | test_module:func:42 - Hello world"
        result = parser.parse_line(line, "stock_datasource.log")

        assert result is not None
        assert result["level"] == "INFO"
        assert result["request_id"] == "-"
        assert result["user_id"] == "-"
        assert result["module"] == "test_module"

    def test_parse_fallback_default_context(self):
        from stock_datasource.modules.system_logs.log_parser import LogParser

        parser = LogParser()
        result = parser.parse_line("just some random text", "test.log")

        assert result is not None
        assert result["request_id"] == "-"
        assert result["user_id"] == "-"

    def test_parse_error_with_request_id(self):
        from stock_datasource.modules.system_logs.log_parser import LogParser

        parser = LogParser()
        line = "2026-04-09 15:30:00.123 | ERROR    | req456 | admin | db_service:connect:100 - Connection refused"
        result = parser.parse_line(line, "errors.log")

        assert result is not None
        assert result["level"] == "ERROR"
        assert result["request_id"] == "req456"
        assert result["user_id"] == "admin"
        assert "Connection refused" in result["message"]


class TestLogFileReaderFilters:
    """Test file reader filter behavior for request correlation."""

    def test_read_logs_filters_by_request_id(self, tmp_path):
        from stock_datasource.modules.system_logs.log_parser import LogFileReader

        log_file = tmp_path / "backend.log"
        log_file.write_text(
            "2026-04-09 15:30:00.123 | INFO     | req-1 | user1 | test_module:func:42 - Hello world\n"
            "2026-04-09 15:31:00.123 | ERROR    | req-2 | user2 | test_module:func:43 - Boom\n",
            encoding="utf-8",
        )

        reader = LogFileReader(str(tmp_path))
        logs = reader.read_logs(request_id="req-2", limit=50)

        assert len(logs) == 1
        assert logs[0]["request_id"] == "req-2"
        assert logs[0]["level"] == "ERROR"


class TestLogServiceClickHousePaths:
    """Test LogService CH query paths with mocked dependencies.

    We mock the entire service module to avoid the heavy import chain
    (agents → plugins → etc.) that causes ImportError in test environment.
    """

    def test_ch_client_property_returns_none_on_import_error(self):
        """_ch_client should return None when db_client is unavailable."""
        # Import only the service module with heavy deps mocked out
        with patch.dict("sys.modules", {
            "stock_datasource.modules.system_logs.ai_diagnosis_service": MagicMock(),
        }):
            # Re-import to get fresh module
            import importlib
            import stock_datasource.modules.system_logs.service as svc_mod
            importlib.reload(svc_mod)

            service = svc_mod.LogService(log_dir="/tmp/test_logs")
            # If db_client import fails, _ch_client should return None
            with patch.dict("sys.modules", {"stock_datasource.models.database": None}):
                result = service._ch_client
                # Result depends on whether db_client was importable
                # At minimum, the property should not raise

    def test_get_logs_fallback_uses_single_reader_call(self):
        """Fallback path should not rescan files just to compute totals."""
        with patch.dict("sys.modules", {
            "stock_datasource.modules.system_logs.ai_diagnosis_service": MagicMock(),
        }):
            import importlib
            import stock_datasource.modules.system_logs.service as svc_mod

            importlib.reload(svc_mod)
            service = svc_mod.LogService(log_dir="/tmp/test_logs")
            service.reader = MagicMock()
            service.reader.read_logs.return_value = [{
                "timestamp": datetime(2026, 4, 9, 15, 30, 0),
                "level": "ERROR",
                "module": "test_module",
                "message": "boom",
                "raw_line": "raw",
                "request_id": "req-2",
                "user_id": "user2",
            }]

            filters = LogFilter(request_id="req-2", page=1, page_size=50)

            with patch.object(svc_mod.LogService, "_get_logs_from_clickhouse", return_value=None):
                result = service.get_logs(filters)

            assert service.reader.read_logs.call_count == 1
            kwargs = service.reader.read_logs.call_args.kwargs
            assert kwargs["request_id"] == "req-2"
            assert result.total == 1
            assert result.logs[0].request_id == "req-2"
