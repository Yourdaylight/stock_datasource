"""Tests for memory module router.

Covers:
- Fact CRUD (create / list / delete) with deterministic IDs
- fact_id stability: same content always produces the same ID
- Watchlist CRUD via stock_opinion facts
- Preference read/write
- Profile aggregation from facts
"""

import hashlib
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# We import the real memory modules (models + store + router).
# conftest.py pre-mocks heavy deps, but memory is pure-Python, no DB.
from stock_datasource.modules.memory.models import FactItem
from stock_datasource.modules.memory.store import MemoryStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _content_hash(content: str) -> str:
    """Deterministic content hash — what the router SHOULD use."""
    return hashlib.md5(content.encode()).hexdigest()[:8]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def memory_store():
    """Fresh in-memory MemoryStore for each test."""
    return MemoryStore()


@pytest.fixture()
def app(memory_store: MemoryStore):
    """FastAPI app with the memory router, wired to a test store."""
    from stock_datasource.modules.memory import router as memory_router_mod

    # Monkey-patch _get_store so the router uses our test store
    original = memory_router_mod._get_store
    memory_router_mod._get_store = lambda: memory_store

    _app = FastAPI()
    _app.include_router(memory_router_mod.router, prefix="/memory")

    # Override auth dependency — return a fake user for all endpoints
    from stock_datasource.modules.auth.dependencies import get_current_user
    _app.dependency_overrides[get_current_user] = lambda: {"id": "test_user", "email": "test@test.com"}

    yield _app

    # Restore
    memory_router_mod._get_store = original
    _app.dependency_overrides.clear()


@pytest.fixture()
def client(app: FastAPI):
    return TestClient(app)


# ===================================================================
# fact_id determinism
# ===================================================================


class TestFactIdDeterminism:
    """The core bug: hash() is not stable across processes.

    These tests assert that create → list → delete round-trips correctly,
    which requires deterministic IDs.
    """

    def test_create_fact_returns_deterministic_id(self, client: TestClient):
        """Creating the same fact content twice should yield IDs with the
        same content-hash suffix (timestamp part will differ)."""
        resp = client.post(
            "/memory/facts",
            json={"content": "看好半导体板块", "category": "sector_focus", "confidence": 0.8},
        )
        assert resp.status_code == 200
        fact1 = resp.json()
        assert "id" in fact1

        # The ID should contain a deterministic content hash, not Python hash()
        expected_hash = _content_hash("看好半导体板块")
        assert expected_hash in fact1["id"], (
            f"fact_id '{fact1['id']}' should contain deterministic hash '{expected_hash}'"
        )

    def test_create_then_list_returns_created_fact(self, client: TestClient):
        """Round-trip: POST → GET should return the fact."""
        client.post(
            "/memory/facts",
            json={"content": "持有茅台", "category": "stock_opinion"},
        )
        resp = client.get("/memory/facts")
        assert resp.status_code == 200
        facts = resp.json()
        assert any(f["content"] == "持有茅台" for f in facts)

    def test_create_then_delete_removes_fact(self, client: TestClient):
        """The delete endpoint should actually remove the fact.

        This is the test that FAILS with hash() because the ID reconstructed
        during GET differs from the one used during POST.
        """
        # Create
        resp = client.post(
            "/memory/facts",
            json={"content": "关注宁德时代", "category": "stock_opinion", "confidence": 0.9},
        )
        fact_id = resp.json()["id"]

        # Verify it exists
        facts_before = client.get("/memory/facts").json()
        assert any(f["id"] == fact_id for f in facts_before)

        # Delete
        del_resp = client.delete(f"/memory/facts/{fact_id}")
        assert del_resp.status_code == 200

        # Verify it's gone
        facts_after = client.get("/memory/facts").json()
        assert not any(f["id"] == fact_id for f in facts_after)

    def test_list_facts_ids_are_stable_across_calls(self, client: TestClient):
        """Two consecutive GET /facts should return the same IDs."""
        client.post(
            "/memory/facts",
            json={"content": "半导体利好", "category": "market_signal"},
        )
        ids1 = {f["id"] for f in client.get("/memory/facts").json()}
        ids2 = {f["id"] for f in client.get("/memory/facts").json()}
        assert ids1 == ids2, "Fact IDs should be stable across requests"


# ===================================================================
# Watchlist CRUD
# ===================================================================


class TestWatchlist:
    def test_add_and_list_watchlist(self, client: TestClient):
        resp = client.post(
            "/memory/watchlist",
            json={"ts_code": "600519.SH", "add_reason": "白酒龙头"},
        )
        assert resp.status_code == 200

        wl = client.get("/memory/watchlist").json()
        assert any(w["ts_code"] == "600519.SH" for w in wl)

    def test_delete_watchlist_item(self, client: TestClient):
        """Add then delete should remove the stock from watchlist."""
        client.post(
            "/memory/watchlist",
            json={"ts_code": "000858.SZ"},
        )
        # Confirm it's there
        wl_before = client.get("/memory/watchlist").json()
        assert any(w["ts_code"] == "000858.SZ" for w in wl_before)

        # Delete
        client.delete("/memory/watchlist/000858.SZ")

        # Confirm it's gone
        wl_after = client.get("/memory/watchlist").json()
        assert not any(w["ts_code"] == "000858.SZ" for w in wl_after)


# ===================================================================
# Preference API
# ===================================================================


class TestPreference:
    def test_get_default_preference(self, client: TestClient):
        resp = client.get("/memory/preference")
        assert resp.status_code == 200
        data = resp.json()
        assert data["risk_level"] == "moderate"

    def test_update_and_get_preference(self, client: TestClient):
        client.put(
            "/memory/preference",
            json={
                "risk_level": "aggressive",
                "investment_style": "growth",
                "favorite_sectors": ["科技", "新能源"],
            },
        )
        resp = client.get("/memory/preference")
        data = resp.json()
        assert data["risk_level"] == "aggressive"
        assert "科技" in data["favorite_sectors"]


# ===================================================================
# Profile API
# ===================================================================


class TestProfile:
    def test_profile_aggregates_from_facts(self, client: TestClient):
        """Profile endpoint should aggregate stock_opinion facts into focus_stocks."""
        client.post(
            "/memory/facts",
            json={"content": "关注 600519.SH 贵州茅台", "category": "stock_opinion", "confidence": 0.9},
        )
        resp = client.get("/memory/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert "600519.SH" in data["focus_stocks"]


# ===================================================================
# Facts filtering
# ===================================================================


class TestFactsFiltering:
    def test_filter_by_category(self, client: TestClient):
        client.post("/memory/facts", json={"content": "A", "category": "conclusion"})
        client.post("/memory/facts", json={"content": "B", "category": "market_signal"})

        resp = client.get("/memory/facts?category=market_signal")
        facts = resp.json()
        assert all(f["category"] == "market_signal" for f in facts)
        assert len(facts) == 1

    def test_filter_by_min_confidence(self, client: TestClient):
        client.post("/memory/facts", json={"content": "low", "category": "conclusion", "confidence": 0.3})
        client.post("/memory/facts", json={"content": "high", "category": "conclusion", "confidence": 0.9})

        resp = client.get("/memory/facts?min_confidence=0.8")
        facts = resp.json()
        assert all(f["confidence"] >= 0.8 for f in facts)
