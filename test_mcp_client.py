#!/usr/bin/env python3
"""Test MCP client connection to HTTP Streamable server."""

import asyncio
import httpx
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_mcp_connection():
    """Test MCP HTTP Streamable connection."""
    base_url = "http://localhost:8001"
    
    async with httpx.AsyncClient() as client:
        # Test 1: Check health
        logger.info("Testing /health endpoint...")
        response = await client.get(f"{base_url}/health")
        logger.info(f"Health: {response.json()}")
        
        # Test 2: Check info
        logger.info("\nTesting /info endpoint...")
        response = await client.get(f"{base_url}/info")
        logger.info(f"Info: {response.json()}")
        
        # Test 3: List tools
        logger.info("\nTesting tools/list via /messages...")
        response = await client.post(
            f"{base_url}/messages",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {}
            }
        )
        tools_response = response.json()
        logger.info(f"Tools count: {len(tools_response['result']['tools'])}")
        for tool in tools_response['result']['tools']:
            logger.info(f"  - {tool['name']}: {tool['description']}")
        
        # Test 4: Call a tool
        logger.info("\nTesting tools/call via /messages...")
        response = await client.post(
            f"{base_url}/messages",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "tushare_daily_get_latest_daily",
                    "arguments": {
                        "codes": "000001",
                        "limit": 5
                    }
                }
            }
        )
        call_response = response.json()
        logger.info(f"Tool call response: {json.dumps(call_response, indent=2, ensure_ascii=False)[:500]}")
        
        # Test 5: Test SSE endpoint
        logger.info("\nTesting /sse endpoint...")
        async with client.stream("GET", f"{base_url}/sse") as response:
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    logger.info(f"SSE data: {line[:100]}")
                    break


if __name__ == "__main__":
    asyncio.run(test_mcp_connection())
