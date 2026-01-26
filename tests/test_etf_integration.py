"""Integration tests for ETF Agent and API endpoints."""

import pytest
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestETFTools:
    """Test ETF tool functions."""
    
    def test_get_index_info(self):
        """Test get_index_info returns valid data for 000300.SH."""
        from stock_datasource.agents.etf_tools import get_index_info
        
        result = get_index_info("000300.SH")
        print(f"\n[get_index_info] Result: {result}")
        
        # Should not have error
        assert "error" not in result or result.get("ts_code") == "000300.SH"
        
    def test_get_index_constituents(self):
        """Test get_index_constituents returns constituent data."""
        from stock_datasource.agents.etf_tools import get_index_constituents
        
        result = get_index_constituents("000300.SH")
        print(f"\n[get_index_constituents] Result keys: {result.keys() if isinstance(result, dict) else result}")
        
        if "error" not in result:
            assert "constituent_count" in result
            assert result["constituent_count"] > 0
            print(f"  - Constituent count: {result['constituent_count']}")
            print(f"  - Top 3: {result.get('constituents', [])[:3]}")
    
    def test_get_index_factors(self):
        """Test get_index_factors returns technical factors."""
        from stock_datasource.agents.etf_tools import get_index_factors
        
        result = get_index_factors("000300.SH", days=3)
        print(f"\n[get_index_factors] Result keys: {result.keys() if isinstance(result, dict) else result}")
        
        if "error" not in result:
            assert "data" in result
            assert len(result["data"]) > 0
            print(f"  - Days: {result['days']}")
            if result["data"]:
                print(f"  - Sample fields: {list(result['data'][0].keys())[:10]}")
    
    def test_analyze_trend(self):
        """Test analyze_trend returns trend analysis."""
        from stock_datasource.agents.etf_tools import analyze_trend
        
        result = analyze_trend("000300.SH")
        print(f"\n[analyze_trend] Result: {result}")
        
        if "error" not in result:
            assert "trend_direction" in result
            assert "trend_score" in result
            print(f"  - Direction: {result['trend_direction']}")
            print(f"  - Score: {result['trend_score']}")
    
    def test_analyze_momentum(self):
        """Test analyze_momentum returns momentum analysis."""
        from stock_datasource.agents.etf_tools import analyze_momentum
        
        result = analyze_momentum("000300.SH")
        print(f"\n[analyze_momentum] Result: {result}")
        
        if "error" not in result:
            assert "overall_status" in result
            assert "overall_score" in result
            print(f"  - Status: {result['overall_status']}")
            print(f"  - Score: {result['overall_score']}")
    
    def test_analyze_volatility(self):
        """Test analyze_volatility returns volatility analysis."""
        from stock_datasource.agents.etf_tools import analyze_volatility
        
        result = analyze_volatility("000300.SH")
        print(f"\n[analyze_volatility] Result: {result}")
        
        if "error" not in result:
            assert "volatility_score" in result
            print(f"  - Score: {result['volatility_score']}")
    
    def test_analyze_volume(self):
        """Test analyze_volume returns volume analysis."""
        from stock_datasource.agents.etf_tools import analyze_volume
        
        result = analyze_volume("000300.SH")
        print(f"\n[analyze_volume] Result: {result}")
        
        if "error" not in result:
            assert "volume_score" in result
            print(f"  - Score: {result['volume_score']}")
    
    def test_analyze_sentiment(self):
        """Test analyze_sentiment returns sentiment analysis."""
        from stock_datasource.agents.etf_tools import analyze_sentiment
        
        result = analyze_sentiment("000300.SH")
        print(f"\n[analyze_sentiment] Result: {result}")
        
        if "error" not in result:
            assert "overall_sentiment" in result
            assert "sentiment_score" in result
            print(f"  - Sentiment: {result['overall_sentiment']}")
            print(f"  - Score: {result['sentiment_score']}")
    
    def test_analyze_concentration(self):
        """Test analyze_concentration returns concentration analysis."""
        from stock_datasource.agents.etf_tools import analyze_concentration
        
        result = analyze_concentration("000300.SH")
        print(f"\n[analyze_concentration] Result: {result}")
        
        if "error" not in result:
            assert "cr10" in result
            assert "hhi" in result
            assert "risk_level" in result
            print(f"  - CR10: {result['cr10']}%")
            print(f"  - HHI: {result['hhi']}")
            print(f"  - Risk Level: {result['risk_level']}")
    
    def test_get_comprehensive_analysis(self):
        """Test get_comprehensive_analysis returns full report."""
        from stock_datasource.agents.etf_tools import get_comprehensive_analysis
        
        result = get_comprehensive_analysis("000300.SH")
        print(f"\n[get_comprehensive_analysis] Result keys: {result.keys() if isinstance(result, dict) else result}")
        
        if "error" not in result:
            assert "overall_score" in result
            assert "suggestion" in result
            assert "dimension_scores" in result
            print(f"  - Index: {result.get('index_name')}")
            print(f"  - Overall Score: {result['overall_score']}")
            print(f"  - Suggestion: {result['suggestion']}")
            print(f"  - Risks: {result.get('risks')}")


class TestETFAgent:
    """Test ETF Agent functionality."""
    
    def test_agent_creation(self):
        """Test ETF Agent can be created."""
        from stock_datasource.agents import get_etf_agent
        
        agent = get_etf_agent()
        assert agent is not None
        assert agent.config.name == "ETFAgent"
        print(f"\n[ETFAgent] Created: {agent.config.name}")
        print(f"  - Description: {agent.config.description}")
    
    def test_agent_tools(self):
        """Test ETF Agent has correct tools."""
        from stock_datasource.agents import get_etf_agent
        
        agent = get_etf_agent()
        tools = agent.get_tools()
        
        assert len(tools) == 10
        tool_names = [t.__name__ for t in tools]
        print(f"\n[ETFAgent Tools] Count: {len(tools)}")
        print(f"  - Tools: {tool_names}")
        
        expected_tools = [
            "get_index_info",
            "get_index_constituents", 
            "get_index_factors",
            "analyze_trend",
            "analyze_momentum",
            "analyze_volatility",
            "analyze_volume",
            "analyze_sentiment",
            "analyze_concentration",
            "get_comprehensive_analysis",
        ]
        for tool in expected_tools:
            assert tool in tool_names, f"Missing tool: {tool}"
    
    def test_agent_system_prompt(self):
        """Test ETF Agent has system prompt."""
        from stock_datasource.agents import get_etf_agent
        
        agent = get_etf_agent()
        prompt = agent.get_system_prompt()
        
        assert len(prompt) > 100
        assert "ETF" in prompt or "指数" in prompt
        print(f"\n[ETFAgent Prompt] Length: {len(prompt)} chars")


class TestETFService:
    """Test ETF Service layer."""
    
    def test_service_creation(self):
        """Test ETF Service can be created."""
        from stock_datasource.modules.etf.service import ETFService
        
        service = ETFService()
        assert service is not None
        print(f"\n[ETFService] Created successfully")
    
    def test_get_indices(self):
        """Test get_indices returns index list."""
        from stock_datasource.modules.etf.service import ETFService
        
        service = ETFService()
        result = service.get_indices(page=1, page_size=10)
        
        print(f"\n[get_indices] Result: {result}")
        assert "items" in result
        assert "total" in result
        print(f"  - Total: {result['total']}")
        print(f"  - Items count: {len(result['items'])}")
    
    def test_get_index_detail(self):
        """Test get_index_detail returns index info."""
        from stock_datasource.modules.etf.service import ETFService
        
        service = ETFService()
        result = service.get_index_detail("000300.SH")
        
        print(f"\n[get_index_detail] Result: {result}")
        if result:
            print(f"  - Name: {result.get('name')}")
    
    def test_get_constituents(self):
        """Test get_constituents returns constituent data."""
        from stock_datasource.modules.etf.service import ETFService
        
        service = ETFService()
        result = service.get_constituents("000300.SH")
        
        print(f"\n[get_constituents] Result keys: {result.keys() if result else None}")
        if result and "error" not in result:
            print(f"  - Count: {result.get('constituent_count')}")
    
    def test_get_quick_analysis(self):
        """Test get_quick_analysis returns analysis."""
        from stock_datasource.modules.etf.service import ETFService
        
        service = ETFService()
        result = service.get_quick_analysis("000300.SH")
        
        print(f"\n[get_quick_analysis] Result: {result}")
        if result and "error" not in result:
            print(f"  - Overall Score: {result.get('overall_score')}")
            print(f"  - Suggestion: {result.get('suggestion')}")


class TestETFRouter:
    """Test ETF API Router endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi.testclient import TestClient
        from stock_datasource.modules.etf.router import router
        from fastapi import FastAPI
        
        app = FastAPI()
        app.include_router(router, prefix="/etf")
        return TestClient(app)
    
    def test_list_indices(self, client):
        """Test GET /etf/indices endpoint."""
        response = client.get("/etf/indices?page=1&page_size=5")
        print(f"\n[GET /etf/indices] Status: {response.status_code}")
        print(f"  - Response: {response.json()}")
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
    
    def test_get_index_detail(self, client):
        """Test GET /etf/indices/{ts_code} endpoint."""
        response = client.get("/etf/indices/000300.SH")
        print(f"\n[GET /etf/indices/000300.SH] Status: {response.status_code}")
        
        # May return 404 if data not synced
        if response.status_code == 200:
            print(f"  - Response: {response.json()}")
    
    def test_get_constituents(self, client):
        """Test GET /etf/indices/{ts_code}/constituents endpoint."""
        response = client.get("/etf/indices/000300.SH/constituents")
        print(f"\n[GET /etf/indices/000300.SH/constituents] Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  - Constituent count: {data.get('constituent_count')}")
    
    def test_get_quick_analysis(self, client):
        """Test GET /etf/indices/{ts_code}/analysis endpoint."""
        response = client.get("/etf/indices/000300.SH/analysis")
        print(f"\n[GET /etf/indices/000300.SH/analysis] Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  - Overall Score: {data.get('overall_score')}")
            print(f"  - Suggestion: {data.get('suggestion')}")


if __name__ == "__main__":
    # Run with: python -m pytest tests/test_etf_integration.py -v -s
    pytest.main([__file__, "-v", "-s"])
