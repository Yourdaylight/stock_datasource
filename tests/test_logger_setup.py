"""Tests for logger setup and context injection."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestPatchContext:
    """Test that patch_context injects context vars into extra."""

    def test_default_context_values(self):
        """When no context is set, request_id and user_id should default to '-'."""
        from stock_datasource.utils.request_context import reset_request_context, patch_context
        reset_request_context()

        record = {"extra": {}}
        patch_context(record)
        assert record["extra"]["request_id"] == "-"
        assert record["extra"]["user_id"] == "-"

    def test_context_values_injected(self):
        """Context vars should be injected into record extra."""
        from stock_datasource.utils.request_context import set_request_context, reset_request_context, patch_context
        reset_request_context()
        set_request_context(request_id="test-rid", user_id="test-uid")

        record = {"extra": {}}
        patch_context(record)
        assert record["extra"]["request_id"] == "test-rid"
        assert record["extra"]["user_id"] == "test-uid"

        reset_request_context()

    def test_does_not_overwrite_existing_extra(self):
        """If extra already has request_id, patch should not overwrite."""
        from stock_datasource.utils.request_context import patch_context
        record = {"extra": {"request_id": "pre-set"}}
        patch_context(record)
        assert record["extra"]["request_id"] == "pre-set"

    def test_returns_true(self):
        """patch_context should return True for Loguru compatibility."""
        from stock_datasource.utils.request_context import patch_context
        record = {"extra": {}}
        assert patch_context(record) is True


class TestLoggerModuleExports:
    """Test that the logger module exports the expected attributes."""

    def test_logger_attribute_exists(self):
        """Module should export a `logger` attribute."""
        from stock_datasource.utils.logger import logger
        assert logger is not None
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")

    def test_setup_logging_function_exists(self):
        """Module should have a setup_logging function."""
        import stock_datasource.utils.logger as mod
        # Use __dict__ because loguru's __getattr__ shadows module attrs
        assert "setup_logging" in mod.__dict__ or callable(getattr(mod, "setup_logging", None))
