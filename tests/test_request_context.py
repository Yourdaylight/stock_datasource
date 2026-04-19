"""Tests for request_context module."""

import threading

from stock_datasource.utils.request_context import (
    generate_request_id,
    get_request_id,
    get_user_id,
    reset_request_context,
    set_request_context,
)


class TestGenerateRequestId:
    """Test request ID generation."""

    def test_generates_16_char_hex(self):
        rid = generate_request_id()
        assert len(rid) == 16
        assert all(c in "0123456789abcdef" for c in rid)

    def test_generates_unique_ids(self):
        ids = {generate_request_id() for _ in range(100)}
        assert len(ids) == 100  # all unique


class TestContextVars:
    """Test contextvars get/set/reset."""

    def setup_method(self):
        reset_request_context()

    def teardown_method(self):
        reset_request_context()

    def test_default_values(self):
        assert get_request_id() == "-"
        assert get_user_id() == "-"

    def test_set_request_id(self):
        set_request_context(request_id="abc123")
        assert get_request_id() == "abc123"
        assert get_user_id() == "-"

    def test_set_user_id(self):
        set_request_context(user_id="user42")
        assert get_user_id() == "user42"
        assert get_request_id() == "-"

    def test_set_both(self):
        set_request_context(request_id="r1", user_id="u1")
        assert get_request_id() == "r1"
        assert get_user_id() == "u1"

    def test_reset(self):
        set_request_context(request_id="r1", user_id="u1")
        reset_request_context()
        assert get_request_id() == "-"
        assert get_user_id() == "-"

    def test_overwrite(self):
        set_request_context(request_id="r1")
        set_request_context(request_id="r2")
        assert get_request_id() == "r2"

    def test_thread_isolation(self):
        """Context vars should be isolated per thread."""
        set_request_context(request_id="main-r1", user_id="main-u1")
        results = {}

        def worker():
            # Inherit default from parent, but setting is independent
            results["worker_initial"] = get_request_id()
            set_request_context(request_id="worker-r2")
            results["worker_after"] = get_request_id()

        t = threading.Thread(target=worker)
        t.start()
        t.join()

        # Main thread should keep its own value
        assert get_request_id() == "main-r1"
        # Worker thread starts with inherited or default value
        assert results["worker_after"] == "worker-r2"
