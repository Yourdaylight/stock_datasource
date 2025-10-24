#!/usr/bin/env python3
"""Verification script for dynamic service architecture."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from stock_datasource.services.http_server import _discover_services as http_discover
from stock_datasource.services.mcp_server import _discover_services as mcp_discover
from stock_datasource.services.http_server import create_app
from stock_datasource.services.mcp_server import create_mcp_server


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def verify_service_discovery():
    """Verify that services are discovered correctly."""
    print_section("1. Service Discovery")
    
    # HTTP service discovery
    print("HTTP Server Service Discovery:")
    http_services = http_discover()
    for service_name, service_class in http_services:
        print(f"  ✓ {service_name}: {service_class.__name__}")
    
    # MCP service discovery
    print("\nMCP Server Service Discovery:")
    mcp_services = mcp_discover()
    for service_name, service_class in mcp_services:
        print(f"  ✓ {service_name}: {service_class.__name__}")
    
    assert len(http_services) > 0, "No HTTP services discovered"
    assert len(mcp_services) > 0, "No MCP services discovered"
    assert http_services == mcp_services, "HTTP and MCP services don't match"
    
    print(f"\n✓ Discovered {len(http_services)} services")
    return http_services


def verify_http_server(services):
    """Verify HTTP server creation and route registration."""
    print_section("2. HTTP Server Verification")
    
    try:
        app = create_app()
        print(f"✓ HTTP server created successfully")
        print(f"✓ Server name: {app.title}")
        
        # Check routes
        routes = []
        for route in app.routes:
            if hasattr(route, 'path'):
                routes.append(route.path)
        
        print(f"\n✓ Registered {len(routes)} routes:")
        for route in sorted(set(routes)):
            if route.startswith("/api/"):
                print(f"  - {route}")
        
        return app
    except Exception as e:
        print(f"✗ Failed to create HTTP server: {e}")
        raise


def verify_mcp_server(services):
    """Verify MCP server creation and tool registration."""
    print_section("3. MCP Server Verification")
    
    try:
        server = create_mcp_server()
        print(f"✓ MCP server created successfully")
        print(f"✓ Server name: {server.name}")
        
        # Count expected tools
        expected_tool_count = 0
        for service_name, service_class in services:
            # Create a temporary service instance to count methods
            try:
                service = service_class()
                methods = service.get_query_methods()
                expected_tool_count += len(methods)
                print(f"\n✓ Service '{service_name}' has {len(methods)} query methods:")
                for method_name in methods.keys():
                    print(f"  - {service_name}_{method_name}")
            except Exception as e:
                print(f"  (Could not instantiate service: {e})")
        
        print(f"\n✓ Expected {expected_tool_count} MCP tools")
        return server
    except Exception as e:
        print(f"✗ Failed to create MCP server: {e}")
        raise


def verify_service_methods(services):
    """Verify that services have query methods."""
    print_section("4. Service Methods Verification")
    
    for service_name, service_class in services:
        try:
            service = service_class()
            methods = service.get_query_methods()
            
            print(f"✓ {service_name}:")
            for method_name, method_info in methods.items():
                description = method_info['metadata']['description']
                params = method_info['metadata']['params']
                print(f"  - {method_name}: {description}")
                for param in params:
                    required = "required" if param.required else "optional"
                    print(f"    • {param.name} ({param.type}): {param.description} [{required}]")
        except Exception as e:
            print(f"✗ Failed to verify {service_name}: {e}")
            raise


def verify_dynamic_generation():
    """Verify that routes and tools are dynamically generated."""
    print_section("5. Dynamic Generation Verification")
    
    from stock_datasource.core.service_generator import ServiceGenerator
    from stock_datasource.plugins.tushare_daily.service import TuShareDailyService
    
    try:
        service = TuShareDailyService()
        generator = ServiceGenerator(service)
        
        # Verify HTTP routes
        router = generator.generate_http_routes()
        print(f"✓ Generated HTTP routes:")
        for route in router.routes:
            if hasattr(route, 'path'):
                print(f"  - {route.path}")
        
        # Verify MCP tools
        tools = generator.generate_mcp_tools()
        print(f"\n✓ Generated {len(tools)} MCP tools:")
        for tool in tools:
            print(f"  - {tool['name']}: {tool['description']}")
        
        return True
    except Exception as e:
        print(f"✗ Failed to verify dynamic generation: {e}")
        raise


def main():
    """Run all verification checks."""
    print("\n" + "="*60)
    print("  Dynamic Service Architecture Verification")
    print("="*60)
    
    try:
        # 1. Verify service discovery
        services = verify_service_discovery()
        
        # 2. Verify HTTP server
        http_app = verify_http_server(services)
        
        # 3. Verify MCP server
        mcp_server = verify_mcp_server(services)
        
        # 4. Verify service methods
        verify_service_methods(services)
        
        # 5. Verify dynamic generation
        verify_dynamic_generation()
        
        # Final summary
        print_section("✓ All Verifications Passed!")
        print("The dynamic service architecture is working correctly.")
        print("\nYou can now:")
        print("  1. Start HTTP server: python -m stock_datasource.services.http_server")
        print("  2. Start MCP server: python -m stock_datasource.services.mcp_server")
        print("  3. Add new services: Create plugins/{name}/service.py")
        print("\nServices will be automatically discovered and registered!")
        
        return 0
    
    except Exception as e:
        print_section("✗ Verification Failed!")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
