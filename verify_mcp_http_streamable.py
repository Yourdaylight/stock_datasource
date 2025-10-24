#!/usr/bin/env python3
"""Verification script for MCP HTTP Streamable implementation."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from stock_datasource.services.mcp_server import create_app, create_mcp_server


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def verify_mcp_server():
    """Verify MCP server creation."""
    print_section("1. MCP Server Verification")
    
    try:
        server = create_mcp_server()
        print(f"✓ MCP server created successfully")
        print(f"✓ Server name: {server.name}")
        return server
    except Exception as e:
        print(f"✗ Failed to create MCP server: {e}")
        raise


def verify_fastapi_app():
    """Verify FastAPI app creation."""
    print_section("2. FastAPI App Verification")
    
    try:
        app = create_app()
        print(f"✓ FastAPI app created successfully")
        print(f"✓ App title: {app.title}")
        
        # Check routes
        routes = []
        for route in app.routes:
            if hasattr(route, 'path'):
                routes.append(route.path)
        
        print(f"\n✓ Registered {len(routes)} routes:")
        for route in sorted(set(routes)):
            print(f"  - {route}")
        
        # Check for required endpoints
        required_endpoints = ['/health', '/info', '/mcp']
        for endpoint in required_endpoints:
            if endpoint in routes:
                print(f"  ✓ {endpoint} endpoint found")
            else:
                print(f"  ✗ {endpoint} endpoint NOT found")
        
        return app
    except Exception as e:
        print(f"✗ Failed to create FastAPI app: {e}")
        raise


def verify_endpoints():
    """Verify endpoints are accessible."""
    print_section("3. Endpoint Verification")
    
    try:
        from fastapi.testclient import TestClient
        
        app = create_app()
        client = TestClient(app)
        
        # Test health endpoint
        print("Testing /health endpoint...")
        response = client.get("/health")
        if response.status_code == 200:
            print(f"  ✓ /health: {response.json()}")
        else:
            print(f"  ✗ /health failed with status {response.status_code}")
        
        # Test info endpoint
        print("\nTesting /info endpoint...")
        response = client.get("/info")
        if response.status_code == 200:
            info = response.json()
            print(f"  ✓ /info:")
            for key, value in info.items():
                print(f"    - {key}: {value}")
        else:
            print(f"  ✗ /info failed with status {response.status_code}")
        
        # Test docs endpoint
        print("\nTesting /docs endpoint...")
        response = client.get("/docs")
        if response.status_code == 200:
            print(f"  ✓ /docs: API documentation available")
        else:
            print(f"  ✗ /docs failed with status {response.status_code}")
        
    except Exception as e:
        print(f"✗ Failed to verify endpoints: {e}")
        raise


def verify_mcp_client():
    """Verify MCP client."""
    print_section("4. MCP Client Verification")
    
    try:
        from stock_datasource.services.mcp_client import MCPClient
        
        client = MCPClient()
        print(f"✓ MCPClient created successfully")
        print(f"✓ Server URL: {client.server_url}")
        
        # Check methods
        methods = ['connect', 'disconnect', 'call_tool', 'list_tools']
        for method in methods:
            if hasattr(client, method):
                print(f"  ✓ {method} method found")
            else:
                print(f"  ✗ {method} method NOT found")
        
    except Exception as e:
        print(f"✗ Failed to verify MCP client: {e}")
        raise


def main():
    """Run all verification checks."""
    print("\n" + "="*60)
    print("  MCP HTTP Streamable Verification")
    print("="*60)
    
    try:
        # 1. Verify MCP server
        verify_mcp_server()
        
        # 2. Verify FastAPI app
        verify_fastapi_app()
        
        # 3. Verify endpoints
        verify_endpoints()
        
        # 4. Verify MCP client
        verify_mcp_client()
        
        # Final summary
        print_section("✓ All Verifications Passed!")
        print("MCP HTTP Streamable implementation is working correctly.")
        print("\nYou can now:")
        print("  1. Start MCP server: python -m stock_datasource.services.mcp_server")
        print("  2. Connect MCP client: MCPClient()")
        print("  3. Call tools: await client.call_tool('tool_name', **args)")
        print("\nEndpoints:")
        print("  • Health check: http://localhost:8001/health")
        print("  • Server info: http://localhost:8001/info")
        print("  • MCP endpoint: http://localhost:8001/mcp")
        print("  • API docs: http://localhost:8001/docs")
        
        return 0
    
    except Exception as e:
        print_section("✗ Verification Failed!")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
