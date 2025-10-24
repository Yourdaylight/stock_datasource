"""MCP client for connecting to stock data service via HTTP streamable."""

import asyncio
import logging
from typing import Any, Optional

from fastmcp import Client

logger = logging.getLogger(__name__)


class MCPClient:
    """MCP client for stock data service."""
    
    def __init__(self, server_url: str = "http://localhost:8001/mcp"):
        """Initialize MCP client.
        
        Args:
            server_url: URL of the MCP server (HTTP streamable endpoint)
        """
        self.server_url = server_url
        self.client: Optional[Client] = None
    
    async def connect(self) -> None:
        """Connect to MCP server."""
        try:
            self.client = Client(
                name="stock-data-client",
                url=self.server_url,
            )
            logger.info(f"Connected to MCP server at {self.server_url}")
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from MCP server."""
        if self.client:
            await self.client.close()
            logger.info("Disconnected from MCP server")
    
    async def call_tool(self, tool_name: str, **kwargs) -> Any:
        """Call a tool on the MCP server.
        
        Args:
            tool_name: Name of the tool to call
            **kwargs: Tool arguments
        
        Returns:
            Tool result
        """
        if not self.client:
            raise RuntimeError("Not connected to MCP server")
        
        try:
            result = await self.client.call_tool(tool_name, kwargs)
            logger.info(f"Called tool {tool_name} successfully")
            return result
        except Exception as e:
            logger.error(f"Failed to call tool {tool_name}: {e}")
            raise
    
    async def list_tools(self) -> list:
        """List all available tools on the MCP server.
        
        Returns:
            List of tool definitions
        """
        if not self.client:
            raise RuntimeError("Not connected to MCP server")
        
        try:
            tools = await self.client.list_tools()
            logger.info(f"Retrieved {len(tools)} tools from MCP server")
            return tools
        except Exception as e:
            logger.error(f"Failed to list tools: {e}")
            raise


async def main():
    """Example usage of MCP client."""
    client = MCPClient()
    
    try:
        # Connect to MCP server
        await client.connect()
        
        # List available tools
        tools = await client.list_tools()
        print(f"\nAvailable tools ({len(tools)}):")
        for tool in tools:
            print(f"  - {tool.name}: {tool.description}")
        
        # Call a tool
        if tools:
            tool_name = tools[0].name
            print(f"\nCalling tool: {tool_name}")
            
            # Example: call tushare_daily_get_daily_data
            if "get_daily_data" in tool_name:
                result = await client.call_tool(
                    tool_name,
                    code="000001",
                    start_date="2024-01-01",
                    end_date="2024-01-31",
                )
                print(f"Result: {result}")
    
    finally:
        # Disconnect from MCP server
        await client.disconnect()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
