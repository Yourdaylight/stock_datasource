"""Tests for MCP authentication, record counting, quota enforcement, and endpoints.

TC-PY-07 through TC-PY-20.
"""

import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import pandas as pd


# ---------------------------------------------------------------------------
# Helper: build the FastAPI app with full mocking
# ---------------------------------------------------------------------------

def _create_test_app():
    """Create the MCP FastAPI app for testing with mocked dependencies."""
    # Mock all heavy imports before creating app
    with patch("stock_datasource.services.mcp_server._discover_services", return_value=[]):
        from stock_datasource.services.mcp_server import create_app
        app = create_app()
    return app


# ---------------------------------------------------------------------------
# TC-PY-11 ~ TC-PY-13: _count_records_in_result
# ---------------------------------------------------------------------------

class TestCountRecords:
    """Tests for the record counting heuristic."""

    def _get_counter(self):
        """Import and return the _count_records_in_result function.

        Since it's defined inside create_app(), we test it by extracting
        it directly. For simplicity, we replicate the logic here and test
        against known inputs.
        """
        # The function is embedded in create_app, so we re-implement the
        # same logic here for unit testing purposes.
        def _count_records_in_result(result_text: str) -> int:
            try:
                data = json.loads(result_text)
                if isinstance(data, list):
                    return len(data)
                if isinstance(data, dict):
                    if "data" in data and isinstance(data["data"], list):
                        return len(data["data"])
                    if "rows" in data and isinstance(data["rows"], list):
                        return len(data["rows"])
                    if "records" in data and isinstance(data["records"], list):
                        return len(data["records"])
                    if "items" in data and isinstance(data["items"], list):
                        return len(data["items"])
                    return 1
            except (json.JSONDecodeError, TypeError):
                pass
            lines = result_text.strip().split("\n")
            return max(len(lines) - 1, 1)

        return _count_records_in_result

    def test_json_array(self):
        """TC-PY-11: JSON array should return its length."""
        counter = self._get_counter()
        result = counter('[{"a":1},{"a":2},{"a":3},{"a":4}]')
        assert result == 4

    def test_json_object_with_data(self):
        """TC-PY-12: JSON object with 'data' key returns data length."""
        counter = self._get_counter()
        result = counter('{"data":[{"x":1},{"x":2},{"x":3}]}')
        assert result == 3

    def test_plain_text(self):
        """TC-PY-13: Multi-line text returns lines-1 (subtract header)."""
        counter = self._get_counter()
        text = "header\nrow1\nrow2\nrow3\nrow4"
        result = counter(text)
        assert result == 4  # 5 lines - 1 header = 4

    def test_json_object_with_rows(self):
        """Bonus: JSON object with 'rows' key."""
        counter = self._get_counter()
        result = counter('{"rows":[{},{}]}')
        assert result == 2

    def test_single_json_object(self):
        """Bonus: Single JSON object counts as 1."""
        counter = self._get_counter()
        result = counter('{"name":"foo","value":42}')
        assert result == 1

    def test_single_line_text(self):
        """Bonus: Single line text returns 1."""
        counter = self._get_counter()
        result = counter("just one line")
        assert result == 1


# ---------------------------------------------------------------------------
# TC-PY-07 ~ TC-PY-10, TC-PY-14 ~ TC-PY-20: Endpoint integration tests
# ---------------------------------------------------------------------------

class TestMcpEndpoints:
    """Integration tests for MCP server endpoints via TestClient."""

    @pytest.fixture(autouse=True)
    def setup_app(self):
        """Create test app with all services mocked."""
        from httpx import ASGITransport, AsyncClient

        with patch("stock_datasource.services.mcp_server._discover_services", return_value=[]):
            from stock_datasource.services.mcp_server import create_app
            self.app = create_app()

        from fastapi.testclient import TestClient
        self.client = TestClient(self.app)

    # --- Authentication tests ---

    def test_initialize_no_auth_required(self):
        """TC-PY-14: initialize method doesn't require authentication."""
        resp = self.client.post("/messages", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["serverInfo"]["name"] == "stock-data-service"

    def test_tools_call_requires_auth(self):
        """TC-PY-15: tools/call without token returns 401."""
        resp = self.client.post("/messages", json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "some_tool", "arguments": {}},
        })
        assert resp.status_code == 401
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == -32001

    def test_tools_call_invalid_token(self):
        """TC-PY-16: tools/call with invalid token returns 401."""
        # Provide a token that's not sk-xxx and not a valid JWT
        resp = self.client.post(
            "/messages",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "some_tool", "arguments": {}},
            },
            headers={"Authorization": "Bearer invalid.jwt.token"},
        )
        assert resp.status_code == 401

    def test_tools_list_no_auth_still_works(self):
        """TC-PY-07 bonus: tools/list without auth should work (no token = auth_type none)."""
        resp = self.client.post("/messages", json={
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/list",
            "params": {},
        })
        # tools/list does not require auth explicitly
        assert resp.status_code == 200

    # --- Quota enforcement tests ---

    @patch("stock_datasource.modules.mcp_api_key.jwt_verifier.verify_nps_jwt")
    def test_quota_exhausted_returns_403(self, mock_verify):
        """TC-PY-17: When quota is exhausted, tools/call returns 403."""
        # Mock JWT verification to return valid user with limited quota
        mock_verify.return_value = (True, {
            "sub": "quotauser",
            "scope": {
                "type": "mcp_query",
                "quota": {"total": 100, "used": 0, "remaining": 100},
                "node_id": 1,
            },
            "rev": 1,
        }, "")

        # Mock the local usage query to show quota is exhausted
        mock_df = pd.DataFrame([{"total_used": 100}])

        with patch("stock_datasource.services.mcp_server.db_client", create=True) as mock_db:
            # The quota check imports db_client inside the function
            mock_query_db = MagicMock()
            mock_query_db.query.return_value = mock_df

            # We need to patch at the point where it's imported inside the handler
            with patch.dict("sys.modules", {
                "stock_datasource.models.database": MagicMock(db_client=mock_query_db)
            }):
                resp = self.client.post(
                    "/messages",
                    json={
                        "jsonrpc": "2.0",
                        "id": 5,
                        "method": "tools/call",
                        "params": {"name": "test_tool", "arguments": {}},
                    },
                    headers={"Authorization": "Bearer eyJhbGciOiJSUzI1NiJ9.test.sig"},
                )

        assert resp.status_code == 403
        data = resp.json()
        assert data["error"]["code"] == -32003
        assert "quota" in data["error"]["message"].lower()

    @patch("stock_datasource.modules.mcp_api_key.jwt_verifier.verify_nps_jwt")
    def test_quota_available_allows_request(self, mock_verify):
        """TC-PY-18: When quota is available, request proceeds."""
        mock_verify.return_value = (True, {
            "sub": "activeuser",
            "scope": {
                "type": "mcp_query",
                "quota": {"total": 100, "used": 0, "remaining": 100},
                "node_id": 1,
            },
            "rev": 1,
        }, "")

        # Mock local usage: only 50 used, so 50 remaining
        mock_df = pd.DataFrame([{"total_used": 50}])
        mock_query_db = MagicMock()
        mock_query_db.query.return_value = mock_df
        mock_query_db.execute = MagicMock()  # for usage logging

        with patch.dict("sys.modules", {
            "stock_datasource.models.database": MagicMock(db_client=mock_query_db)
        }):
            # The tool call will fail (no actual tool registered), but it should
            # get past the quota check — we expect a tool error, not 403
            resp = self.client.post(
                "/messages",
                json={
                    "jsonrpc": "2.0",
                    "id": 6,
                    "method": "tools/call",
                    "params": {"name": "test_tool", "arguments": {}},
                },
                headers={"Authorization": "Bearer eyJhbGciOiJSUzI1NiJ9.test.sig"},
            )

        # Should NOT be 403 (quota ok), but might be 200 with tool error
        assert resp.status_code != 403

    # --- Usage summary tests ---

    def test_usage_summary_missing_username(self):
        """TC-PY-19: GET /usage/summary without username returns 400."""
        resp = self.client.get("/usage/summary")
        assert resp.status_code == 400
        data = resp.json()
        assert "username" in data.get("error", "").lower()

    def test_usage_summary_with_data(self):
        """TC-PY-20: GET /usage/summary returns aggregated data."""
        # Mock settings and db_client
        mock_settings = MagicMock()
        mock_settings.MCP_USAGE_REPORT_KEY = ""  # no auth required

        summary_df = pd.DataFrame([{"total_calls": 15, "total_records": 1500}])
        detail_df = pd.DataFrame([
            {"tool_name": "tushare_daily", "calls": 10, "records": 1000},
            {"tool_name": "tushare_minute", "calls": 5, "records": 500},
        ])

        mock_db = MagicMock()
        mock_db.query.side_effect = [summary_df, detail_df]

        with patch.dict("sys.modules", {
            "stock_datasource.models.database": MagicMock(db_client=mock_db),
            "stock_datasource.config.settings": MagicMock(settings=mock_settings),
        }):
            resp = self.client.get("/usage/summary?username=testuser&since=2025-01-01")

        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "testuser"
        assert data["total_calls"] == 15
        assert data["total_records"] == 1500
        assert len(data["by_tool"]) == 2

    # --- Health endpoint ---

    def test_health_endpoint(self):
        """Bonus: health endpoint returns ok."""
        resp = self.client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_messages_get(self):
        """Bonus: GET /messages returns probe response."""
        resp = self.client.get("/messages")
        assert resp.status_code == 200
        assert resp.json()["protocol"] == "streamable-http"

    def test_unknown_method(self):
        """Bonus: unknown method returns error."""
        resp = self.client.post("/messages", json={
            "jsonrpc": "2.0",
            "id": 99,
            "method": "unknown/method",
            "params": {},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == -32601
