"""Unit tests for HTTP service."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
import pandas as pd

from stock_datasource.services.http_server import create_app
from stock_datasource.plugins.tushare_daily.service import TuShareDailyService
from stock_datasource.core.service_generator import ServiceGenerator


@pytest.fixture
def app():
    """Create test app."""
    return create_app()


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestHttpServer:
    """Test HTTP server functionality."""
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    
    def test_api_routes_registered(self, client):
        """Test that API routes are registered."""
        # Try to access the daily API endpoint
        response = client.post(
            "/api/daily/get_daily_data",
            json={
                "code": "000001.SZ",
                "start_date": "20250101",
                "end_date": "20250131",
            }
        )
        # Should not be 404 (route exists)
        assert response.status_code != 404


class TestServiceGenerator:
    """Test service generator functionality."""
    
    def test_extract_query_methods(self):
        """Test extracting query methods from service."""
        service = TuShareDailyService()
        methods = service.get_query_methods()
        
        # Should have 3 query methods
        assert len(methods) == 3
        assert "get_daily_data" in methods
        assert "get_latest_daily" in methods
        assert "get_daily_stats" in methods
    
    def test_method_metadata(self):
        """Test method metadata extraction."""
        service = TuShareDailyService()
        methods = service.get_query_methods()
        
        daily_data_method = methods["get_daily_data"]
        assert daily_data_method["metadata"]["description"] == "Query daily stock data by code and date range"
        assert len(daily_data_method["metadata"]["params"]) == 3
    
    def test_generate_http_routes(self):
        """Test HTTP route generation."""
        service = TuShareDailyService()
        generator = ServiceGenerator(service)
        router = generator.generate_http_routes()
        
        # Check that routes are created
        assert len(router.routes) > 0
    
    def test_generate_mcp_tools(self):
        """Test MCP tool generation."""
        service = TuShareDailyService()
        generator = ServiceGenerator(service)
        tools = generator.generate_mcp_tools()
        
        # Should have 3 tools
        assert len(tools) == 3
        
        # Check tool structure
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            assert tool["inputSchema"]["type"] == "object"
            assert "properties" in tool["inputSchema"]
            assert "required" in tool["inputSchema"]
    
    def test_mcp_tool_schema(self):
        """Test MCP tool input schema."""
        service = TuShareDailyService()
        generator = ServiceGenerator(service)
        tools = generator.generate_mcp_tools()
        
        # Find get_daily_data tool
        daily_tool = next(t for t in tools if t["name"] == "get_daily_data")
        
        schema = daily_tool["inputSchema"]
        assert "code" in schema["properties"]
        assert "start_date" in schema["properties"]
        assert "end_date" in schema["properties"]
        
        # All three should be required
        assert set(schema["required"]) == {"code", "start_date", "end_date"}
    
    def test_optional_parameter_schema(self):
        """Test optional parameter in schema."""
        service = TuShareDailyService()
        generator = ServiceGenerator(service)
        tools = generator.generate_mcp_tools()
        
        # Find get_latest_daily tool
        latest_tool = next(t for t in tools if t["name"] == "get_latest_daily")
        
        schema = latest_tool["inputSchema"]
        # codes is required, limit is optional
        assert "codes" in schema["required"]
        assert "limit" not in schema["required"]


class TestGetDailyDataEndpoint:
    """Test get_daily_data endpoint."""
    
    def test_get_daily_data_success(self, client):
        """Test successful daily data query."""
        # Create a service with mocked db
        service = TuShareDailyService()
        mock_df = pd.DataFrame({
            'ts_code': ['000001.SZ', '000001.SZ'],
            'trade_date': ['20250101', '20250102'],
            'open': [10.0, 10.5],
            'high': [10.5, 11.0],
            'low': [9.9, 10.4],
            'close': [10.2, 10.8],
            'vol': [1000000, 1100000],
            'amount': [10200000, 11880000],
        })
        
        service.db = Mock()
        service.db.execute_query.return_value = mock_df
        
        # Call the method directly
        result = service.get_daily_data(
            code="000001.SZ",
            start_date="20250101",
            end_date="20250131",
        )
        
        assert len(result) == 2
        assert result[0]["ts_code"] == "000001.SZ"
    
    def test_get_daily_data_missing_parameter(self, client):
        """Test missing required parameter."""
        response = client.post(
            "/api/daily/get_daily_data",
            json={
                "code": "000001.SZ",
                # Missing start_date and end_date
            }
        )
        
        # Should return validation error
        assert response.status_code == 422
    
    def test_get_daily_data_empty_result(self, client):
        """Test empty result handling."""
        service = TuShareDailyService()
        mock_df = pd.DataFrame({
            'ts_code': [],
            'trade_date': [],
            'open': [],
            'high': [],
            'low': [],
            'close': [],
            'vol': [],
            'amount': [],
        })
        
        service.db = Mock()
        service.db.execute_query.return_value = mock_df
        
        result = service.get_daily_data(
            code="999999.SZ",
            start_date="20250101",
            end_date="20250131",
        )
        
        assert len(result) == 0


class TestGetLatestDailyEndpoint:
    """Test get_latest_daily endpoint."""
    
    def test_get_latest_daily_success(self, client):
        """Test successful latest daily data query."""
        service = TuShareDailyService()
        mock_df = pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ'],
            'trade_date': ['20250124', '20250124'],
            'open': [10.0, 20.0],
            'high': [10.5, 20.5],
            'low': [9.9, 19.9],
            'close': [10.2, 20.2],
            'vol': [1000000, 2000000],
            'amount': [10200000, 40400000],
        })
        
        service.db = Mock()
        service.db.execute_query.return_value = mock_df
        
        result = service.get_latest_daily(
            codes=["000001.SZ", "000002.SZ"],
            limit=1,
        )
        
        assert len(result) == 2
    
    def test_get_latest_daily_default_limit(self, client):
        """Test default limit parameter."""
        service = TuShareDailyService()
        mock_df = pd.DataFrame({
            'ts_code': ['000001.SZ'],
            'trade_date': ['20250124'],
            'open': [10.0],
            'high': [10.5],
            'low': [9.9],
            'close': [10.2],
            'vol': [1000000],
            'amount': [10200000],
        })
        
        service.db = Mock()
        service.db.execute_query.return_value = mock_df
        
        result = service.get_latest_daily(
            codes=["000001.SZ"],
            # limit not specified, should use default
        )
        
        assert len(result) == 1


class TestGetDailyStatsEndpoint:
    """Test get_daily_stats endpoint."""
    
    def test_get_daily_stats_success(self, client):
        """Test successful daily stats query."""
        service = TuShareDailyService()
        mock_df = pd.DataFrame({
            'trading_days': [20],
            'min_close': [9.5],
            'max_close': [11.0],
            'avg_close': [10.2],
            'total_volume': [20000000],
            'total_amount': [204000000],
        })
        
        service.db = Mock()
        service.db.execute_query.return_value = mock_df
        
        result = service.get_daily_stats(
            code="000001.SZ",
            start_date="20250101",
            end_date="20250131",
        )
        
        assert result["trading_days"] == 20
        assert result["avg_close"] == 10.2
    
    def test_get_daily_stats_empty_result(self, client):
        """Test empty stats result."""
        service = TuShareDailyService()
        mock_df = pd.DataFrame({
            'trading_days': [],
            'min_close': [],
            'max_close': [],
            'avg_close': [],
            'total_volume': [],
            'total_amount': [],
        })
        
        service.db = Mock()
        service.db.execute_query.return_value = mock_df
        
        result = service.get_daily_stats(
            code="999999.SZ",
            start_date="20250101",
            end_date="20250131",
        )
        
        assert result == {}


class TestTypeConversion:
    """Test type conversion utilities."""
    
    def test_python_type_to_json_schema(self):
        """Test Python type to JSON schema conversion."""
        from stock_datasource.core.base_service import BaseService
        
        assert BaseService.python_type_to_json_schema(str) == "string"
        assert BaseService.python_type_to_json_schema(int) == "integer"
        assert BaseService.python_type_to_json_schema(float) == "number"
        assert BaseService.python_type_to_json_schema(bool) == "boolean"
        assert BaseService.python_type_to_json_schema(list) == "array"
        assert BaseService.python_type_to_json_schema(dict) == "object"
    
    def test_generic_type_conversion(self):
        """Test generic type conversion."""
        from typing import List, Dict
        from stock_datasource.core.base_service import BaseService
        
        assert BaseService.python_type_to_json_schema(List[str]) == "array"
        assert BaseService.python_type_to_json_schema(Dict[str, int]) == "object"


class TestErrorHandling:
    """Test error handling."""
    
    def test_database_error_handling(self, client):
        """Test database error handling."""
        service = TuShareDailyService()
        service.db = Mock()
        service.db.execute_query.side_effect = Exception("Database connection failed")
        
        with pytest.raises(Exception):
            service.get_daily_data(
                code="000001.SZ",
                start_date="20250101",
                end_date="20250131",
            )
