"""Tests for user-scoped features: chat history, admin access, task history, portfolio isolation.

Tests cover:
- 7.1: Chat history CRUD (create, query, delete)
- 7.2: Non-admin access to data management returns 403
- 7.3: Task history includes user information
- 7.4: Portfolio analysis returns only current user's data
"""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from fastapi import HTTPException, status


def create_test_user(user_id: str, username: str = "testuser", is_admin: bool = False) -> dict:
    """Create a test user dict."""
    return {
        "id": user_id,
        "username": username,
        "email": f"{username}@test.com",
        "is_admin": is_admin,
        "created_at": "2026-01-01T00:00:00",
    }


# ============ 7.1 Chat History Tests ============

class TestChatHistory:
    """Test chat session and message CRUD operations (Task 7.1)."""
    
    def test_create_session_requires_auth(self):
        """Test that creating a session requires authentication."""
        from stock_datasource.services.http_server import create_app
        app = create_app()
        client = TestClient(app)
        
        response = client.post("/api/chat/session")
        assert response.status_code == 401
        assert "未提供认证令牌" in response.json()["detail"]
    
    def test_chat_service_create_session_with_user_id(self):
        """Test that ChatService.create_session binds user_id."""
        from stock_datasource.modules.chat.service import ChatService
        
        with patch('stock_datasource.modules.chat.service.db_client') as mock_db:
            mock_db.execute = Mock(return_value=[])
            mock_db.primary = Mock()
            mock_db.primary.execute = Mock()
            
            service = ChatService()
            service._tables_initialized = True  # Skip table creation
            
            session_id = service.create_session(user_id="test_user_001", title="Test")
            
            assert session_id.startswith("session_")
    
    def test_chat_service_get_user_sessions_filters_by_user(self):
        """Test that get_user_sessions only returns sessions for the specified user."""
        from stock_datasource.modules.chat.service import ChatService
        
        with patch('stock_datasource.modules.chat.service.db_client') as mock_db:
            # Mock database to return user-specific sessions
            mock_db.execute = Mock(return_value=[
                ("session_1", "Title 1", "2026-01-01", "2026-01-01", 5),
                ("session_2", "Title 2", "2026-01-02", "2026-01-02", 3),
            ])
            mock_db.primary = Mock()
            
            service = ChatService()
            service._tables_initialized = True
            
            sessions = service.get_user_sessions(user_id="user_123", limit=50)
            
            # Verify the query was called with user_id
            mock_db.execute.assert_called()
            call_args = mock_db.execute.call_args
            assert "user_id" in call_args[1] or "user_123" in str(call_args)
    
    def test_chat_service_verify_session_ownership(self):
        """Test that verify_session_ownership correctly checks user_id."""
        from stock_datasource.modules.chat.service import ChatService
        
        with patch('stock_datasource.modules.chat.service.db_client') as mock_db:
            # Mock session belonging to user_A
            mock_db.execute = Mock(return_value=[
                ("session_xyz", "user_A", "Title", "2026-01-01", "2026-01-01", "2026-01-01", 0)
            ])
            mock_db.primary = Mock()
            
            service = ChatService()
            service._tables_initialized = True
            
            # user_A should have ownership
            assert service.verify_session_ownership("session_xyz", "user_A") is True
            
            # user_B should NOT have ownership
            assert service.verify_session_ownership("session_xyz", "user_B") is False
    
    def test_chat_service_delete_session_requires_ownership(self):
        """Test that delete_session checks ownership before deleting."""
        from stock_datasource.modules.chat.service import ChatService
        
        with patch('stock_datasource.modules.chat.service.db_client') as mock_db:
            # Mock session belonging to user_A
            mock_db.execute = Mock(return_value=[
                ("session_xyz", "user_A", "Title", "2026-01-01", "2026-01-01", "2026-01-01", 0)
            ])
            mock_db.primary = Mock()
            
            service = ChatService()
            service._tables_initialized = True
            
            # user_B cannot delete user_A's session
            result = service.delete_session("session_xyz", "user_B")
            assert result is False


# ============ 7.2 Admin Access Tests ============

class TestAdminAccess:
    """Test that non-admin users get 403 for data management (Task 7.2)."""
    
    def test_require_admin_dependency_allows_admin(self):
        """Test that require_admin allows admin users."""
        import asyncio
        from stock_datasource.modules.auth.dependencies import require_admin
        
        admin_user = create_test_user("admin_001", "admin", is_admin=True)
        
        # Simulate the dependency
        result = asyncio.get_event_loop().run_until_complete(
            require_admin(current_user=admin_user)
        )
        
        assert result == admin_user
    
    def test_require_admin_dependency_blocks_non_admin(self):
        """Test that require_admin raises 403 for non-admin users."""
        import asyncio
        from stock_datasource.modules.auth.dependencies import require_admin
        
        non_admin_user = create_test_user("user_001", "testuser", is_admin=False)
        
        # Should raise HTTPException with 403
        with pytest.raises(HTTPException) as exc_info:
            asyncio.get_event_loop().run_until_complete(
                require_admin(current_user=non_admin_user)
            )
        
        assert exc_info.value.status_code == 403
        assert "仅管理员可访问" in exc_info.value.detail
    
    def test_datamanage_router_uses_require_admin(self):
        """Test that datamanage router endpoints use require_admin dependency."""
        from stock_datasource.modules.datamanage import router
        import inspect
        
        # Check that routes have require_admin in their dependencies
        # by examining the router's routes
        routes_with_admin_dependency = []
        
        for route in router.router.routes:
            if hasattr(route, 'dependant') and hasattr(route.dependant, 'dependencies'):
                for dep in route.dependant.dependencies:
                    if 'require_admin' in str(dep.call):
                        routes_with_admin_dependency.append(route.path)
        
        # Critical endpoints should have admin dependency
        assert len(routes_with_admin_dependency) > 0, "No routes have require_admin dependency"
    
    def test_non_admin_returns_403_for_datasources(self):
        """Test non-admin user gets 403 for /datasources endpoint."""
        from stock_datasource.services.http_server import create_app
        from stock_datasource.modules.auth.dependencies import get_current_user, require_admin
        
        app = create_app()
        
        non_admin_user = create_test_user("user_nonadmin", "nonadmin", is_admin=False)
        
        # Override dependencies to return non-admin user
        async def override_get_current_user():
            return non_admin_user
        
        async def override_require_admin(current_user=None):
            if not non_admin_user.get("is_admin", False):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="仅管理员可访问此功能",
                )
            return non_admin_user
        
        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[require_admin] = override_require_admin
        
        client = TestClient(app)
        
        response = client.get("/api/datamanage/datasources")
        
        assert response.status_code == 403
        assert "仅管理员可访问" in response.json()["detail"]
        
        # Cleanup
        app.dependency_overrides.clear()
    
    def test_admin_allowed_for_datasources(self):
        """Test admin user can access /datasources endpoint."""
        from stock_datasource.services.http_server import create_app
        from stock_datasource.modules.auth.dependencies import get_current_user, require_admin
        
        app = create_app()
        
        admin_user = create_test_user("user_admin", "admin", is_admin=True)
        
        async def override_get_current_user():
            return admin_user
        
        async def override_require_admin(current_user=None):
            return admin_user
        
        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[require_admin] = override_require_admin
        
        client = TestClient(app)
        
        response = client.get("/api/datamanage/datasources")
        
        assert response.status_code == 200
        
        # Cleanup
        app.dependency_overrides.clear()


# ============ 7.3 Task History User Info Tests ============

class TestTaskHistoryUserInfo:
    """Test that task history includes user information (Task 7.3)."""
    
    def test_create_task_stores_user_info(self):
        """Test that creating a task stores user_id and username."""
        from stock_datasource.modules.datamanage.service import SyncTaskManager
        from stock_datasource.modules.datamanage.schemas import TaskType
        
        manager = SyncTaskManager()
        
        task = manager.create_task(
            plugin_name="test_plugin",
            task_type=TaskType.INCREMENTAL,
            trade_dates=["2026-01-01"],
            user_id="test_user_123",
            username="test_admin",
        )
        
        assert task.user_id == "test_user_123"
        assert task.username == "test_admin"
    
    def test_get_tasks_includes_user_info(self):
        """Test that getting tasks returns user information."""
        from stock_datasource.modules.datamanage.service import SyncTaskManager
        from stock_datasource.modules.datamanage.schemas import TaskType
        
        manager = SyncTaskManager()
        
        # Create a task with user info
        task = manager.create_task(
            plugin_name="test_plugin_info",
            task_type=TaskType.FULL,
            trade_dates=None,
            user_id="admin_user_001",
            username="adminuser",
        )
        
        # Retrieve the task
        retrieved = manager.get_task(task.task_id)
        
        assert retrieved is not None
        assert retrieved.user_id == "admin_user_001"
        assert retrieved.username == "adminuser"
    
    def test_get_tasks_paginated_filters_by_user_id(self):
        """Test that get_tasks_paginated can filter by user_id."""
        from stock_datasource.modules.datamanage.service import SyncTaskManager
        from stock_datasource.modules.datamanage.schemas import TaskType
        
        manager = SyncTaskManager()
        
        # Create tasks for different users
        manager.create_task(
            plugin_name="plugin_a",
            task_type=TaskType.INCREMENTAL,
            user_id="user_A",
            username="User A",
        )
        manager.create_task(
            plugin_name="plugin_b",
            task_type=TaskType.INCREMENTAL,
            user_id="user_B",
            username="User B",
        )
        manager.create_task(
            plugin_name="plugin_c",
            task_type=TaskType.FULL,
            user_id="user_A",
            username="User A",
        )
        
        # Get tasks filtered by user_A
        result = manager.get_tasks_paginated(user_id="user_A")
        
        # Should only return tasks for user_A
        for task in result.items:
            assert task.user_id == "user_A"
    
    def test_sync_task_schema_has_user_fields(self):
        """Test that SyncTask schema includes user_id and username fields."""
        from stock_datasource.modules.datamanage.schemas import SyncTask
        
        # Check that the model has user fields
        fields = SyncTask.model_fields
        
        assert "user_id" in fields
        assert "username" in fields


# ============ 7.4 Portfolio User Isolation Tests ============

class TestPortfolioUserIsolation:
    """Test that portfolio data is isolated per user (Task 7.4)."""
    
    def test_portfolio_storage_per_user(self):
        """Test that portfolio storage is isolated per user."""
        from stock_datasource.agents import portfolio_agent
        
        # Reset the storage
        portfolio_agent._user_portfolio_store = {}
        
        # User A adds a position
        portfolio_agent._current_user_id = "user_A"
        result_a = portfolio_agent.add_position("600519", 100, 1800.0)
        assert "600519" in result_a
        
        # User B adds a different position
        portfolio_agent._current_user_id = "user_B"
        result_b = portfolio_agent.add_position("000001", 500, 12.0)
        assert "000001" in result_b
        
        # Verify user A only sees their position
        portfolio_agent._current_user_id = "user_A"
        positions_a = portfolio_agent.get_positions()
        assert "600519" in positions_a
        assert "000001" not in positions_a
        
        # Verify user B only sees their position
        portfolio_agent._current_user_id = "user_B"
        positions_b = portfolio_agent.get_positions()
        assert "000001" in positions_b
        assert "600519" not in positions_b
    
    def test_portfolio_update_position_isolation(self):
        """Test that updating position is isolated per user."""
        from stock_datasource.agents import portfolio_agent
        
        # Reset the storage
        portfolio_agent._user_portfolio_store = {}
        
        # User A adds and updates position
        portfolio_agent._current_user_id = "user_A"
        portfolio_agent.add_position("600036", 200, 30.0)
        portfolio_agent.update_position("600036", "buy", 100, 32.0)
        
        # User B shouldn't see user A's position
        portfolio_agent._current_user_id = "user_B"
        result = portfolio_agent.update_position("600036", "sell", 50, 35.0)
        assert "持仓中没有" in result
    
    def test_portfolio_pnl_isolation(self):
        """Test that PnL calculation is isolated per user."""
        from stock_datasource.agents import portfolio_agent
        
        # Reset the storage
        portfolio_agent._user_portfolio_store = {}
        
        # User A has positions
        portfolio_agent._current_user_id = "user_A"
        portfolio_agent.add_position("600519", 100, 1800.0)
        pnl_a = portfolio_agent.calculate_portfolio_pnl()
        assert "600519" in pnl_a
        
        # User B has no positions
        portfolio_agent._current_user_id = "user_B"
        pnl_b = portfolio_agent.calculate_portfolio_pnl()
        assert "没有持仓" in pnl_b
    
    def test_portfolio_agent_has_execute_override(self):
        """Test that PortfolioAgent has execute() override for user context."""
        from stock_datasource.agents.portfolio_agent import PortfolioAgent
        import inspect
        
        agent = PortfolioAgent()
        
        # Verify execute method exists and is overridden
        assert hasattr(agent, 'execute')
        
        # Check that execute() method is defined in PortfolioAgent (not just inherited)
        execute_method = getattr(PortfolioAgent, 'execute', None)
        assert execute_method is not None
        
        # Check source code contains user_id context handling
        source = inspect.getsource(execute_method)
        assert 'user_id' in source or '_current_user_id' in source
    
    def test_portfolio_agent_has_execute_stream_override(self):
        """Test that PortfolioAgent has execute_stream() override for user context."""
        from stock_datasource.agents.portfolio_agent import PortfolioAgent
        import inspect
        
        agent = PortfolioAgent()
        
        # Verify execute_stream method exists
        assert hasattr(agent, 'execute_stream')
        
        # Check that execute_stream() method is defined in PortfolioAgent
        execute_stream_method = getattr(PortfolioAgent, 'execute_stream', None)
        assert execute_stream_method is not None
        
        # Check source code contains user_id context handling
        source = inspect.getsource(execute_stream_method)
        assert 'user_id' in source or '_current_user_id' in source
    
    def test_get_user_portfolio_helper(self):
        """Test that _get_user_portfolio returns isolated storage."""
        from stock_datasource.agents import portfolio_agent
        
        # Reset
        portfolio_agent._user_portfolio_store = {}
        
        # Get portfolio for user_X
        portfolio_agent._current_user_id = "user_X"
        portfolio_x = portfolio_agent._get_user_portfolio()
        portfolio_x["positions"]["test"] = {"qty": 100}
        
        # Get portfolio for user_Y
        portfolio_agent._current_user_id = "user_Y"
        portfolio_y = portfolio_agent._get_user_portfolio()
        
        # user_Y should not have user_X's data
        assert "test" not in portfolio_y.get("positions", {})


# ============ Enhanced Portfolio Agent Tests ============

class TestEnhancedPortfolioAgent:
    """Test EnhancedPortfolioAgent user context handling."""
    
    def test_enhanced_portfolio_agent_has_execute_override(self):
        """Test that EnhancedPortfolioAgent has execute() override."""
        from stock_datasource.agents.enhanced_portfolio_agent import EnhancedPortfolioAgent
        import inspect
        
        # Check execute method is defined
        execute_method = getattr(EnhancedPortfolioAgent, 'execute', None)
        assert execute_method is not None
        
        source = inspect.getsource(execute_method)
        assert 'user_id' in source or '_current_user_id' in source
    
    def test_enhanced_portfolio_agent_has_execute_stream_override(self):
        """Test that EnhancedPortfolioAgent has execute_stream() override."""
        from stock_datasource.agents.enhanced_portfolio_agent import EnhancedPortfolioAgent
        import inspect
        
        # Check execute_stream method is defined
        execute_stream_method = getattr(EnhancedPortfolioAgent, 'execute_stream', None)
        assert execute_stream_method is not None
        
        source = inspect.getsource(execute_stream_method)
        assert 'user_id' in source or '_current_user_id' in source
    
    def test_enhanced_portfolio_agent_tools_use_instance_variable(self):
        """Test that tools use self._current_user_id instead of parameter."""
        from stock_datasource.agents.enhanced_portfolio_agent import EnhancedPortfolioAgent
        import inspect
        
        # Check analyze_portfolio_performance method at class level
        method = getattr(EnhancedPortfolioAgent, 'analyze_portfolio_performance', None)
        if method:
            source = inspect.getsource(method)
            # Should use self._current_user_id, not user_id parameter
            assert '_current_user_id' in source
            # Should NOT have user_id as a method parameter with default value
            assert 'user_id: str = "default_user"' not in source


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
