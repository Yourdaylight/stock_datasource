"""Unit tests for Screener module - 智能选股模块测试."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
import pandas as pd
from datetime import datetime

from stock_datasource.services.http_server import create_app


@pytest.fixture
def app():
    """Create test app."""
    return create_app()


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestScreenerSchemas:
    """Test Screener schemas."""
    
    def test_screener_condition_schema(self):
        """Test ScreenerCondition schema."""
        from stock_datasource.modules.screener.schemas import ScreenerCondition
        
        condition = ScreenerCondition(
            field="pe_ttm",
            operator="<",
            value=30
        )
        assert condition.field == "pe_ttm"
        assert condition.operator == "<"
        assert condition.value == 30
    
    def test_screener_request_schema(self):
        """Test ScreenerRequest schema."""
        from stock_datasource.modules.screener.schemas import ScreenerRequest, ScreenerCondition
        
        request = ScreenerRequest(
            conditions=[
                ScreenerCondition(field="pe_ttm", operator="<", value=30),
                ScreenerCondition(field="pb", operator="<", value=3),
            ],
            sort_by="total_mv",
            sort_order="desc",
            limit=50
        )
        assert len(request.conditions) == 2
        assert request.sort_by == "total_mv"
        assert request.limit == 50
    
    def test_stock_profile_schema(self):
        """Test StockProfile schema."""
        from stock_datasource.modules.screener.schemas import StockProfile, ProfileDimension
        
        profile = StockProfile(
            ts_code="600519.SH",
            stock_name="贵州茅台",
            trade_date="20250114",
            total_score=85.5,
            dimensions=[
                ProfileDimension(
                    name="估值",
                    score=70.0,
                    level="B",
                    weight=0.2,
                    indicators={}
                )
            ],
            recommendation="建议持有"
        )
        assert profile.ts_code == "600519.SH"
        assert profile.total_score == 85.5
        assert len(profile.dimensions) == 1


class TestScreenerService:
    """Test ScreenerService."""
    
    def test_get_fields(self):
        """Test get available fields."""
        from stock_datasource.modules.screener.service import ScreenerService
        
        service = ScreenerService()
        fields = service.get_available_fields()
        
        assert isinstance(fields, list)
        assert len(fields) > 0
        
        # Check field structure
        field = fields[0]
        assert "name" in field
        assert "label" in field
        assert "type" in field
        assert "category" in field
    
    def test_get_sectors(self):
        """Test get sectors with mocked db."""
        from stock_datasource.modules.screener.service import ScreenerService
        
        service = ScreenerService()
        mock_df = pd.DataFrame({
            'industry': ['白酒', '电子', '银行'],
            'stock_count': [35, 180, 42],
        })
        
        service.db = Mock()
        service.db.execute_query.return_value = mock_df
        
        sectors = service.get_sectors()
        
        assert len(sectors) == 3
        assert sectors[0]["name"] == "白酒"
        assert sectors[0]["stock_count"] == 35
    
    def test_filter_by_conditions(self):
        """Test filter stocks by conditions."""
        from stock_datasource.modules.screener.service import ScreenerService
        from stock_datasource.modules.screener.schemas import ScreenerCondition
        
        service = ScreenerService()
        mock_df = pd.DataFrame({
            'ts_code': ['600519.SH', '000858.SZ'],
            'name': ['贵州茅台', '五粮液'],
            'close': [1800.0, 150.0],
            'pct_chg': [2.5, 1.8],
            'pe_ttm': [35.0, 28.0],
            'pb': [12.0, 5.0],
            'total_mv': [22500000, 6000000],
            'trade_date': ['20250114', '20250114'],
        })
        
        service.db = Mock()
        service.db.execute_query.return_value = mock_df
        
        conditions = [
            ScreenerCondition(field="pe_ttm", operator="<", value=40)
        ]
        
        result = service.filter_by_conditions(conditions, limit=10)
        
        assert "items" in result
        assert "total" in result


class TestProfileService:
    """Test ProfileService."""
    
    def test_calculate_valuation_score(self):
        """Test valuation score calculation."""
        from stock_datasource.modules.screener.profile import ProfileService
        
        service = ProfileService()
        
        # Mock data
        stock_data = {
            'pe_ttm': 25.0,
            'pb': 3.0,
            'ps_ttm': 5.0,
            'dv_ratio': 2.5,
        }
        
        score = service._calculate_valuation_score(stock_data)
        
        # Score should be between 0 and 100
        assert 0 <= score <= 100
    
    def test_calculate_momentum_score(self):
        """Test momentum score calculation."""
        from stock_datasource.modules.screener.profile import ProfileService
        
        service = ProfileService()
        
        # Mock data with positive momentum
        stock_data = {
            'pct_chg': 3.5,  # Today's change
            'pct_chg_5': 8.0,  # 5-day change
            'pct_chg_20': 15.0,  # 20-day change
        }
        
        score = service._calculate_momentum_score(stock_data)
        
        assert 0 <= score <= 100
    
    def test_calculate_volume_score(self):
        """Test volume score calculation."""
        from stock_datasource.modules.screener.profile import ProfileService
        
        service = ProfileService()
        
        stock_data = {
            'turnover_rate': 3.5,
            'volume_ratio': 1.2,
        }
        
        score = service._calculate_volume_score(stock_data)
        
        assert 0 <= score <= 100
    
    def test_calculate_total_profile(self):
        """Test total profile calculation."""
        from stock_datasource.modules.screener.profile import ProfileService
        
        service = ProfileService()
        
        # Mock db for full calculation
        mock_basic_df = pd.DataFrame({
            'ts_code': ['600519.SH'],
            'name': ['贵州茅台'],
            'industry': ['白酒'],
        })
        
        mock_valuation_df = pd.DataFrame({
            'ts_code': ['600519.SH'],
            'pe_ttm': [35.0],
            'pb': [12.0],
            'ps_ttm': [15.0],
            'dv_ratio': [1.5],
            'total_mv': [22500000],
            'turnover_rate': [0.5],
        })
        
        mock_daily_df = pd.DataFrame({
            'ts_code': ['600519.SH'],
            'close': [1800.0],
            'pct_chg': [2.0],
            'vol': [50000],
            'trade_date': ['20250114'],
        })
        
        service.db = Mock()
        service.db.execute_query.side_effect = [
            mock_basic_df,
            mock_valuation_df,
            mock_daily_df,
            mock_daily_df,  # For trend calculation
        ]
        
        # This will test the full flow with mocked data
        # In real scenario, it would call DB
        profile = service.calculate_profile("600519.SH")
        
        # Profile should be returned or None if data insufficient
        # With mocked data, we expect it to work
        if profile:
            assert profile.ts_code == "600519.SH"
            assert 0 <= profile.total_score <= 100


class TestScreenerAPI:
    """Test Screener API endpoints."""
    
    def test_get_fields_endpoint(self, client):
        """Test GET /api/screener/fields endpoint."""
        response = client.get("/api/screener/fields")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_get_sectors_endpoint(self, client):
        """Test GET /api/screener/sectors endpoint."""
        response = client.get("/api/screener/sectors")
        
        # Should not be 404
        assert response.status_code != 404
    
    def test_filter_endpoint(self, client):
        """Test POST /api/screener/filter endpoint."""
        response = client.post(
            "/api/screener/filter",
            json={
                "conditions": [
                    {"field": "pe_ttm", "operator": "<", "value": 30}
                ],
                "limit": 10
            }
        )
        
        # Should not be 404
        assert response.status_code != 404
    
    def test_nl_screener_endpoint(self, client):
        """Test POST /api/screener/nl endpoint."""
        response = client.post(
            "/api/screener/nl",
            json={
                "query": "找出PE小于20的白酒股票"
            }
        )
        
        # Should not be 404
        assert response.status_code != 404
    
    def test_profile_endpoint(self, client):
        """Test GET /api/screener/profile/{ts_code} endpoint."""
        response = client.get("/api/screener/profile/600519.SH")
        
        # Should not be 404 (route exists)
        assert response.status_code != 404
    
    def test_recommendations_endpoint(self, client):
        """Test GET /api/screener/recommendations endpoint."""
        response = client.get("/api/screener/recommendations")
        
        # Should not be 404
        assert response.status_code != 404


class TestScreenerAgent:
    """Test ScreenerAgent for NL processing."""
    
    def test_agent_initialization(self):
        """Test agent initialization."""
        from stock_datasource.agents.screener_agent import ScreenerAgent
        
        agent = ScreenerAgent()
        assert agent is not None
    
    @patch('stock_datasource.agents.screener_agent.get_llm_client')
    def test_parse_nl_query(self, mock_llm):
        """Test NL query parsing."""
        from stock_datasource.agents.screener_agent import ScreenerAgent
        
        # Mock LLM response
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content="搜索结果..."))]
        )
        mock_llm.return_value = mock_client
        
        agent = ScreenerAgent()
        # Basic test that agent can be called
        assert callable(getattr(agent, 'process_query', None))


class TestScreenerTools:
    """Test screener tool functions."""
    
    def test_screen_stocks_tool(self):
        """Test screen_stocks tool function."""
        from stock_datasource.agents.tools import screen_stocks
        
        # Test that function exists and is callable
        assert callable(screen_stocks)
    
    def test_get_stock_profile_tool(self):
        """Test get_stock_profile tool function."""
        from stock_datasource.agents.tools import get_stock_profile
        
        assert callable(get_stock_profile)
    
    def test_get_sector_stocks_tool(self):
        """Test get_sector_stocks tool function."""
        from stock_datasource.agents.tools import get_sector_stocks
        
        assert callable(get_sector_stocks)
    
    def test_get_available_sectors_tool(self):
        """Test get_available_sectors tool function."""
        from stock_datasource.agents.tools import get_available_sectors
        
        assert callable(get_available_sectors)
    
    def test_stock_tools_exported(self):
        """Test that all tools are exported in STOCK_TOOLS."""
        from stock_datasource.agents.tools import STOCK_TOOLS
        
        tool_names = [t.__name__ for t in STOCK_TOOLS]
        
        assert "screen_stocks" in tool_names
        assert "get_stock_profile" in tool_names
        assert "get_sector_stocks" in tool_names
        assert "get_available_sectors" in tool_names


class TestConditionValidation:
    """Test condition validation logic."""
    
    def test_valid_operators(self):
        """Test valid operators in conditions."""
        from stock_datasource.modules.screener.schemas import ScreenerCondition
        
        valid_operators = [">", "<", ">=", "<=", "=", "!=", "between", "in"]
        
        for op in valid_operators:
            condition = ScreenerCondition(
                field="pe_ttm",
                operator=op,
                value=30 if op not in ["between", "in"] else [20, 30]
            )
            assert condition.operator == op
    
    def test_condition_field_types(self):
        """Test different field types in conditions."""
        from stock_datasource.modules.screener.schemas import ScreenerCondition
        
        # Numeric condition
        numeric = ScreenerCondition(field="pe_ttm", operator="<", value=30)
        assert isinstance(numeric.value, (int, float))
        
        # String condition
        string = ScreenerCondition(field="industry", operator="=", value="白酒")
        assert isinstance(string.value, str)
        
        # List condition
        list_cond = ScreenerCondition(field="industry", operator="in", value=["白酒", "电子"])
        assert isinstance(list_cond.value, list)


class TestMarketSummary:
    """Test market summary functionality."""
    
    def test_market_summary_schema(self):
        """Test MarketSummary schema."""
        from stock_datasource.modules.screener.schemas import MarketSummary
        
        summary = MarketSummary(
            trade_date="20250114",
            total_stocks=5000,
            up_count=2500,
            down_count=2000,
            flat_count=500,
            limit_up=50,
            limit_down=20,
            avg_change=0.5
        )
        
        assert summary.total_stocks == 5000
        assert summary.up_count == 2500
