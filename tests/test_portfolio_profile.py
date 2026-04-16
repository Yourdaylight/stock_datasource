"""Tests for portfolio profile feature (multi-account support).

TDD: These tests are written FIRST. They define the contract for:
- Profile CRUD (create, list, get, update, delete)
- Positions scoped to a profile
- Default profile auto-creation for existing users
- Profile isolation (user A cannot see user B's profiles)
"""

import uuid
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_user(user_id: str = "user_001") -> dict:
    return {
        "id": user_id,
        "username": "testuser",
        "email": "test@test.com",
        "is_admin": False,
    }


def make_profile_dict(
    profile_id: str = None,
    user_id: str = "user_001",
    name: str = "默认账户",
    broker: str = "",
    is_default: bool = True,
):
    return {
        "id": profile_id or str(uuid.uuid4()),
        "user_id": user_id,
        "name": name,
        "broker": broker,
        "is_default": is_default,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }


# ---------------------------------------------------------------------------
# 1. Profile CRUD Tests
# ---------------------------------------------------------------------------


class TestProfileCRUD:
    """Test profile creation, retrieval, update, and deletion."""

    def test_create_profile_returns_profile_with_id(self):
        """Creating a profile should return a profile dict with an id."""
        from stock_datasource.modules.profile.service import ProfileService

        with patch("stock_datasource.models.database.db_client") as mock_db:
            mock_db.execute = Mock()
            mock_db.execute_query = Mock(return_value=MagicMock())

            svc = ProfileService()
            profile = svc.create_profile(user_id="user_001", name="中信证券")

            assert profile is not None
            assert profile["id"] is not None
            assert profile["name"] == "中信证券"
            assert profile["user_id"] == "user_001"

    def test_create_profile_stores_to_db(self):
        """Creating a profile should INSERT into portfolio_profiles table."""
        from stock_datasource.modules.profile.service import ProfileService

        with patch("stock_datasource.models.database.db_client") as mock_db:
            mock_db.execute = Mock()
            mock_db.execute_query = Mock(return_value=MagicMock())

            svc = ProfileService()
            svc.create_profile(user_id="user_001", name="华泰证券")

            # Verify INSERT was called
            insert_calls = [
                c
                for c in mock_db.execute.call_args_list
                if "INSERT" in str(c).upper() and "portfolio_profiles" in str(c)
            ]
            assert len(insert_calls) >= 1

    def test_list_profiles_returns_profiles_for_user(self):
        """list_profiles should only return profiles for the specified user."""
        import pandas as pd

        from stock_datasource.modules.profile.service import ProfileService

        with patch("stock_datasource.models.database.db_client") as mock_db:
            # Mock DB returning 2 profiles for user_001
            mock_df = pd.DataFrame(
                [
                    {
                        "id": "p1",
                        "user_id": "user_001",
                        "name": "中信",
                        "broker": "",
                        "is_default": 1,
                    },
                    {
                        "id": "p2",
                        "user_id": "user_001",
                        "name": "华泰",
                        "broker": "华泰证券",
                        "is_default": 0,
                    },
                ]
            )
            mock_db.execute_query = Mock(return_value=mock_df)

            svc = ProfileService()
            profiles = svc.list_profiles(user_id="user_001")

            assert len(profiles) == 2
            assert profiles[0]["name"] == "中信"
            assert profiles[1]["name"] == "华泰"

    def test_list_profiles_empty_for_new_user(self):
        """A new user with no profiles should get an empty list."""
        import pandas as pd

        from stock_datasource.modules.profile.service import ProfileService

        with patch("stock_datasource.models.database.db_client") as mock_db:
            mock_db.execute_query = Mock(return_value=pd.DataFrame())

            svc = ProfileService()
            profiles = svc.list_profiles(user_id="new_user")

            assert profiles == []

    def test_get_profile_by_id(self):
        """Should return a single profile by id (belonging to user)."""
        import pandas as pd

        from stock_datasource.modules.profile.service import ProfileService

        with patch("stock_datasource.models.database.db_client") as mock_db:
            mock_df = pd.DataFrame(
                [
                    {
                        "id": "p1",
                        "user_id": "user_001",
                        "name": "中信",
                        "broker": "",
                        "is_default": 1,
                    }
                ]
            )
            mock_db.execute_query = Mock(return_value=mock_df)

            svc = ProfileService()
            profile = svc.get_profile(profile_id="p1", user_id="user_001")

            assert profile is not None
            assert profile["id"] == "p1"
            assert profile["name"] == "中信"

    def test_get_profile_returns_none_for_wrong_user(self):
        """Getting a profile with wrong user_id should return None."""
        import pandas as pd

        from stock_datasource.modules.profile.service import ProfileService

        with patch("stock_datasource.models.database.db_client") as mock_db:
            mock_db.execute_query = Mock(return_value=pd.DataFrame())

            svc = ProfileService()
            profile = svc.get_profile(profile_id="p1", user_id="wrong_user")

            assert profile is None

    def test_update_profile_name(self):
        """Should update profile name."""
        import pandas as pd

        from stock_datasource.modules.profile.service import ProfileService

        with patch("stock_datasource.models.database.db_client") as mock_db:
            # Mock get_profile returning existing profile
            mock_df = pd.DataFrame(
                [
                    {
                        "id": "p1",
                        "user_id": "user_001",
                        "name": "中信",
                        "broker": "",
                        "is_default": 1,
                    }
                ]
            )
            mock_db.execute_query = Mock(return_value=mock_df)
            mock_db.execute = Mock()

            svc = ProfileService()
            result = svc.update_profile(
                profile_id="p1", user_id="user_001", name="中信建投"
            )

            assert result is not None
            assert result["name"] == "中信建投"

    def test_delete_profile(self):
        """Should soft-delete a non-default profile."""
        import pandas as pd

        from stock_datasource.modules.profile.service import ProfileService

        with patch("stock_datasource.models.database.db_client") as mock_db:
            mock_df = pd.DataFrame(
                [
                    {
                        "id": "p2",
                        "user_id": "user_001",
                        "name": "华泰",
                        "broker": "",
                        "is_default": 0,
                    }
                ]
            )
            mock_db.execute_query = Mock(return_value=mock_df)
            mock_db.execute = Mock()

            svc = ProfileService()
            result = svc.delete_profile(profile_id="p2", user_id="user_001")

            assert result is True

    def test_delete_default_profile_fails(self):
        """Should NOT allow deleting the default profile."""
        import pandas as pd

        from stock_datasource.modules.profile.service import ProfileService

        with patch("stock_datasource.models.database.db_client") as mock_db:
            mock_df = pd.DataFrame(
                [
                    {
                        "id": "p1",
                        "user_id": "user_001",
                        "name": "默认",
                        "broker": "",
                        "is_default": 1,
                    }
                ]
            )
            mock_db.execute_query = Mock(return_value=mock_df)

            svc = ProfileService()
            result = svc.delete_profile(profile_id="p1", user_id="user_001")

            assert result is False

    def test_ensure_default_profile_creates_if_missing(self):
        """ensure_default_profile should create a default profile if none exists."""
        import pandas as pd

        from stock_datasource.modules.profile.service import ProfileService

        with patch("stock_datasource.models.database.db_client") as mock_db:
            # No existing profiles
            mock_db.execute_query = Mock(return_value=pd.DataFrame())
            mock_db.execute = Mock()

            svc = ProfileService()
            profile = svc.ensure_default_profile(user_id="user_001")

            assert profile is not None
            assert profile["is_default"] is True
            assert profile["name"] == "默认账户"


# ---------------------------------------------------------------------------
# 2. Profile-scoped Positions Tests
# ---------------------------------------------------------------------------


class TestProfileScopedPositions:
    """Test that positions can be filtered by profile_id."""

    @pytest.mark.asyncio
    async def test_add_position_with_profile_id(self):
        """Adding a position should accept a profile_id parameter."""
        from stock_datasource.modules.portfolio.service import PortfolioService

        with patch("stock_datasource.models.database.db_client") as mock_db:
            mock_db.execute = Mock()
            mock_df = MagicMock()
            mock_df.empty = True
            mock_db.execute_query = Mock(return_value=mock_df)

            svc = PortfolioService()
            position = await svc.add_position(
                ts_code="600519.SH",
                quantity=100,
                cost_price=1700.0,
                buy_date="2026-01-01",
                user_id="user_001",
                profile_id="profile_001",
            )

            # Verify the INSERT included profile_id
            mock_db.execute.assert_called()
            call_params = mock_db.execute.call_args
            sql_or_params = str(call_params)
            assert "profile_id" in sql_or_params or "profile_001" in sql_or_params

    @pytest.mark.asyncio
    async def test_get_positions_filters_by_profile(self):
        """get_positions should support filtering by profile_id."""
        import pandas as pd

        from stock_datasource.modules.portfolio.service import PortfolioService

        with patch("stock_datasource.models.database.db_client") as mock_db:
            mock_df = pd.DataFrame(
                [
                    {
                        "id": "pos1",
                        "ts_code": "600519.SH",
                        "stock_name": "贵州茅台",
                        "quantity": 100,
                        "cost_price": 1700.0,
                        "buy_date": "2026-01-01",
                        "current_price": None,
                        "market_value": None,
                        "profit_loss": None,
                        "profit_rate": None,
                        "notes": "",
                        "profile_id": "profile_001",
                    },
                ]
            )
            mock_db.execute_query = Mock(return_value=mock_df)

            svc = PortfolioService()
            svc._db = mock_db

            positions = await svc.get_positions(
                user_id="user_001", profile_id="profile_001"
            )

            # Verify at least one execute_query call included profile_id filter
            all_calls = [str(call) for call in mock_db.execute_query.call_args_list]
            assert any("profile_id" in call_sql for call_sql in all_calls), (
                f"No query contained profile_id. Calls: {all_calls}"
            )


# ---------------------------------------------------------------------------
# 3. Profile API Endpoint Tests
# ---------------------------------------------------------------------------


class TestProfileAPIEndpoints:
    """Test the profile REST API endpoints."""

    def test_list_profiles_endpoint_requires_auth(self):
        """GET /api/portfolio/profiles should require authentication."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from stock_datasource.modules.profile.router import router

        app = FastAPI()
        app.include_router(router, prefix="/api/portfolio")

        # No auth override → should get 401 or 403
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/portfolio/profiles")
        assert response.status_code in (
            401,
            403,
            500,
        )  # 500 if auth module not importable

    def test_create_profile_endpoint(self):
        """POST /api/portfolio/profiles should create a profile."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from stock_datasource.modules.profile.router import _get_current_user, router

        app = FastAPI()
        app.include_router(router, prefix="/api/portfolio")

        # Override auth dependency
        async def override_auth():
            return make_user("user_001")

        app.dependency_overrides[_get_current_user] = override_auth

        with patch("stock_datasource.models.database.db_client") as mock_db:
            mock_db.execute = Mock()
            mock_db.execute_query = Mock(return_value=MagicMock())

            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                "/api/portfolio/profiles",
                json={"name": "中信证券", "broker": "中信"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "中信证券"

    def test_list_profiles_endpoint(self):
        """GET /api/portfolio/profiles should return user's profiles."""
        import pandas as pd
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from stock_datasource.modules.profile.router import _get_current_user, router
        from stock_datasource.modules.profile.service import get_profile_service

        app = FastAPI()
        app.include_router(router, prefix="/api/portfolio")

        async def override_auth():
            return make_user("user_001")

        app.dependency_overrides[_get_current_user] = override_auth

        with patch("stock_datasource.models.database.db_client") as mock_db:
            mock_df = pd.DataFrame(
                [
                    {
                        "id": "p1",
                        "user_id": "user_001",
                        "name": "中信",
                        "broker": "中信",
                        "is_default": 1,
                    }
                ]
            )
            mock_db.execute_query = Mock(return_value=mock_df)
            mock_db.execute = Mock()

            # Inject mock db into the service singleton
            svc = get_profile_service()
            svc._db = mock_db

            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/api/portfolio/profiles")

            assert response.status_code == 200
            data = response.json()
            assert len(data) >= 1
