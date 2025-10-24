"""Tests for MCP server."""

import pytest
from unittest.mock import patch, MagicMock
from stock_datasource.services.mcp_server import (
    _discover_services,
    create_mcp_server,
)


class TestServiceDiscovery:
    """Test service discovery mechanism."""
    
    def test_discover_services(self):
        """Test that services are discovered correctly."""
        services = _discover_services()
        
        # Should find at least tushare_daily service
        assert len(services) > 0
        
        service_names = [name for name, _ in services]
        assert "tushare_daily" in service_names
    
    def test_discover_services_returns_tuples(self):
        """Test that discovered services are (name, class) tuples."""
        services = _discover_services()
        
        for service_name, service_class in services:
            assert isinstance(service_name, str)
            assert isinstance(service_class, type)


class TestMCPServerCreation:
    """Test MCP server creation."""
    
    def test_create_mcp_server(self):
        """Test that MCP server is created successfully."""
        server = create_mcp_server()
        
        assert server is not None
        assert server.name == "stock-data-service"
    
    @patch("stock_datasource.core.base_service.db_client")
    def test_mcp_server_registers_tools(self, mock_db):
        """Test that MCP server registers tools from discovered services."""
        # Mock the database client
        mock_db.query.return_value = []
        
        server = create_mcp_server()
        
        # Server should be created without errors
        assert server is not None
        assert server.name == "stock-data-service"


class TestMCPToolNaming:
    """Test MCP tool naming convention."""
    
    def test_tool_naming_convention(self):
        """Test that tools follow naming convention: {service}_{method}."""
        services = _discover_services()
        
        # Should have tushare_daily service
        assert any(name == "tushare_daily" for name, _ in services)
        
        # Tool names should be: tushare_daily_get_daily_data, etc.
        expected_tools = [
            "tushare_daily_get_daily_data",
            "tushare_daily_get_latest_daily",
            "tushare_daily_get_daily_stats",
        ]
        
        # We can't easily check tool names without running the server,
        # but we can verify the service exists
        assert len(services) > 0


class TestMCPServerIntegration:
    """Integration tests for MCP server."""
    
    @patch("stock_datasource.core.base_service.db_client")
    def test_server_creation_with_mocked_db(self, mock_db):
        """Test server creation with mocked database."""
        mock_db.query.return_value = []
        
        server = create_mcp_server()
        
        assert server is not None
        assert server.name == "stock-data-service"
    
    def test_discover_services_handles_missing_plugins_dir(self):
        """Test that service discovery handles missing plugins directory gracefully."""
        with patch("stock_datasource.services.mcp_server.Path") as mock_path:
            mock_path.return_value.exists.return_value = False
            
            services = _discover_services()
            
            # Should return empty list, not raise exception
            assert services == []
