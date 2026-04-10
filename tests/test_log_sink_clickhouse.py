"""Tests for log_sink_clickhouse module."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

from stock_datasource.utils.log_sink_clickhouse import (
    _transform_record,
    _flush_batch,
    _import_file,
    import_pending_files,
)


class TestTransformRecord:
    """Test _transform_record converts Loguru JSON to CH row."""

    def test_basic_fields(self):
        record = {
            "timestamp": "2026-04-09 15:30:00.123",
            "level": "INFO",
            "request_id": "abc123",
            "user_id": "user1",
            "module": "test_module",
            "function": "test_func",
            "line": 42,
            "message": "Hello world",
            "exception": None,
        }
        result = _transform_record(record)
        assert result["timestamp"] == "2026-04-09 15:30:00.123"
        assert result["level"] == "INFO"
        assert result["request_id"] == "abc123"
        assert result["user_id"] == "user1"
        assert result["module"] == "test_module"
        assert result["function"] == "test_func"
        assert result["line"] == 42
        assert result["message"] == "Hello world"
        assert result["exception"] is None

    def test_level_uppercase(self):
        record = {"level": "warning", "line": 1}
        result = _transform_record(record)
        assert result["level"] == "WARNING"

    def test_defaults_for_missing_fields(self):
        record = {}
        result = _transform_record(record)
        assert result["timestamp"] == ""
        assert result["level"] == "INFO"
        assert result["request_id"] == "-"
        assert result["user_id"] == "-"
        assert result["module"] == ""
        assert result["function"] == ""
        assert result["line"] == 0
        assert result["message"] == ""
        assert result["exception"] is None

    def test_exception_null_to_none(self):
        record = {"exception": None}
        result = _transform_record(record)
        assert result["exception"] is None

    def test_exception_string_preserved(self):
        record = {"exception": "Traceback..."}
        result = _transform_record(record)
        assert result["exception"] == "Traceback..."


class TestFlushBatch:
    """Test _flush_batch inserts into ClickHouse."""

    @patch("stock_datasource.utils.log_sink_clickhouse._get_db_client")
    def test_empty_batch_skips(self, mock_get_client):
        _flush_batch([])
        mock_get_client.assert_not_called()

    @patch("stock_datasource.utils.log_sink_clickhouse._get_db_client")
    def test_inserts_dataframe(self, mock_get_client):
        mock_db = MagicMock()
        mock_get_client.return_value = mock_db

        batch = [{"timestamp": "2026-01-01", "level": "INFO", "request_id": "-", "user_id": "-",
                  "module": "test", "function": "fn", "line": 1, "message": "msg",
                  "exception": None, "extra": "{}"}]
        _flush_batch(batch)
        mock_db.insert_dataframe.assert_called_once()
        args = mock_db.insert_dataframe.call_args
        assert args[0][0] == "system_structured_logs"

    @patch("stock_datasource.utils.log_sink_clickhouse._get_db_client")
    def test_exception_does_not_raise(self, mock_get_client):
        mock_db = MagicMock()
        mock_db.insert_dataframe.side_effect = Exception("CH down")
        mock_get_client.return_value = mock_db

        batch = [{"timestamp": "2026-01-01", "level": "INFO"}]
        _flush_batch(batch)  # Should not raise

    @patch("stock_datasource.utils.log_sink_clickhouse._get_db_client")
    def test_no_db_client_skips(self, mock_get_client):
        mock_get_client.return_value = None
        batch = [{"timestamp": "2026-01-01"}]
        _flush_batch(batch)  # Should not raise


class TestImportFile:
    """Test _import_file reads JSONL and imports batch."""

    def test_imports_and_deletes_file(self, tmp_path):
        jsonl_file = tmp_path / "test.jsonl.2026-04-09_15-30-00_123.jsonl"
        records = [
            {"timestamp": "2026-04-09 15:30:00", "level": "INFO", "request_id": "-",
             "user_id": "-", "module": "mod", "function": "fn", "line": 1,
             "message": "test msg", "exception": None},
        ]
        with open(jsonl_file, "w") as f:
            for rec in records:
                f.write(json.dumps(rec) + "\n")

        from stock_datasource.config.settings import settings as _settings
        original = getattr(_settings, "LOG_CH_SINK_BATCH_SIZE", 5000)
        try:
            _settings.LOG_CH_SINK_BATCH_SIZE = 5000
            with patch("stock_datasource.utils.log_sink_clickhouse._flush_batch") as mock_flush:
                result = _import_file(jsonl_file)
                assert result is True
                assert not jsonl_file.exists()
                mock_flush.assert_called_once()
                batch = mock_flush.call_args[0][0]
                assert len(batch) == 1
                assert batch[0]["level"] == "INFO"
        finally:
            _settings.LOG_CH_SINK_BATCH_SIZE = original

    def test_malformed_json_lines_skipped(self, tmp_path):
        jsonl_file = tmp_path / "bad.jsonl.2026-04-09.jsonl"
        with open(jsonl_file, "w") as f:
            f.write("not json at all\n")
            f.write('{"level": "INFO", "line": 1}\n')

        from stock_datasource.config.settings import settings as _settings
        original = getattr(_settings, "LOG_CH_SINK_BATCH_SIZE", 5000)
        try:
            _settings.LOG_CH_SINK_BATCH_SIZE = 5000
            with patch("stock_datasource.utils.log_sink_clickhouse._flush_batch"):
                result = _import_file(jsonl_file)
                assert result is True
                assert not jsonl_file.exists()
        finally:
            _settings.LOG_CH_SINK_BATCH_SIZE = original

    def test_empty_file_deleted(self, tmp_path):
        jsonl_file = tmp_path / "empty.jsonl.2026-04-09.jsonl"
        jsonl_file.write_text("")

        from stock_datasource.config.settings import settings as _settings
        original = getattr(_settings, "LOG_CH_SINK_BATCH_SIZE", 5000)
        try:
            _settings.LOG_CH_SINK_BATCH_SIZE = 5000
            with patch("stock_datasource.utils.log_sink_clickhouse._flush_batch"):
                result = _import_file(jsonl_file)
                assert result is True
                assert not jsonl_file.exists()
        finally:
            _settings.LOG_CH_SINK_BATCH_SIZE = original


class TestImportPendingFiles:
    """Test import_pending_files scans directory."""

    def test_scans_jsonl_rotated_files(self, tmp_path):
        rotated = tmp_path / "stock_datasource.jsonl.2026-04-09_15-30-00_123.jsonl"
        with open(rotated, "w") as f:
            f.write('{"level": "INFO", "line": 1}\n')

        with patch("stock_datasource.utils.log_sink_clickhouse._import_file", return_value=True) as mock_import:
            count = import_pending_files(tmp_path)
            assert count == 1
            mock_import.assert_called_once()

    def test_rotates_and_imports_active_jsonl(self, tmp_path):
        active = tmp_path / "stock_datasource.jsonl"
        active.write_text('{"level": "INFO", "line": 1}\n')

        with patch("stock_datasource.utils.log_sink_clickhouse._import_file", return_value=True) as mock_import:
            count = import_pending_files(tmp_path)
            assert count == 1
            assert not active.exists()
            mock_import.assert_called_once()

    def test_skips_empty_active_jsonl(self, tmp_path):
        active = tmp_path / "stock_datasource.jsonl"
        active.write_text("")

        with patch("stock_datasource.utils.log_sink_clickhouse._import_file") as mock_import:
            count = import_pending_files(tmp_path)
            assert count == 0
            mock_import.assert_not_called()

    def test_nonexistent_dir_returns_zero(self):
        count = import_pending_files(Path("/nonexistent"))
        assert count == 0
