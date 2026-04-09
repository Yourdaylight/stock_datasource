"""MCP client for connecting to stock data service via HTTP streamable."""

import asyncio
import inspect
import logging
import os
from pathlib import Path
from urllib.parse import urlparse
from typing import Any, Optional

from fastmcp import Client

logger = logging.getLogger(__name__)


def normalize_mcp_server_url(server_url: str) -> str:
    """Map legacy MCP paths to the streamable-http endpoint used by this service."""
    normalized = server_url.rstrip("/")
    if normalized.endswith("/mcp"):
        return normalized[:-4] + "/messages"
    return normalized


def get_default_mcp_server_url() -> str:
    """Return the best default MCP endpoint for the current runtime."""
    configured = os.getenv("MCP_SERVER_URL")
    if configured:
        return normalize_mcp_server_url(configured)
    if Path("/.dockerenv").exists():
        return "http://127.0.0.1:8001/messages"
    return "http://localhost:8001/messages"


def _should_use_internal_auth(server_url: str) -> bool:
    hostname = (urlparse(server_url).hostname or "").lower()
    return hostname in {"127.0.0.1", "localhost", "::1"}


def get_internal_mcp_bearer() -> Optional[str]:
    bearer = os.getenv("MCP_INTERNAL_BEARER", "").strip()
    return bearer or None


class MCPClient:
    """MCP client for stock data service."""
    
    def __init__(self, server_url: Optional[str] = None):
        """Initialize MCP client.
        
        Args:
            server_url: URL of the MCP server (HTTP streamable endpoint)
        """
        self.server_url = normalize_mcp_server_url(server_url) if server_url else get_default_mcp_server_url()
        self.client: Optional[Client] = None
        self._entered = False
    
    async def connect(self) -> None:
        """Connect to MCP server."""
        try:
            client_signature = inspect.signature(Client.__init__)
            client_kwargs = {"name": "stock-data-client"}
            internal_bearer = get_internal_mcp_bearer()
            if internal_bearer and _should_use_internal_auth(self.server_url):
                client_kwargs["auth"] = internal_bearer
            if "url" in client_signature.parameters:
                self.client = Client(
                    url=self.server_url,
                    **client_kwargs,
                )
            else:
                self.client = Client(
                    self.server_url,
                    **client_kwargs,
                )
            enter = getattr(self.client, "__aenter__", None)
            if callable(enter):
                entered_client = enter()
                if inspect.isawaitable(entered_client):
                    entered_client = await entered_client
                if entered_client is not None:
                    self.client = entered_client
                self._entered = True
            logger.info(f"Connected to MCP server at {self.server_url}")
        except Exception as e:
            self._entered = False
            logger.error(f"Failed to connect to MCP server: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from MCP server."""
        if self.client:
            try:
                if self._entered and hasattr(self.client, "__aexit__"):
                    exit_result = self.client.__aexit__(None, None, None)
                    if inspect.isawaitable(exit_result):
                        await exit_result
                else:
                    close_result = self.client.close()
                    if inspect.isawaitable(close_result):
                        await close_result
                logger.info("Disconnected from MCP server")
            except Exception as e:
                logger.warning(f"Failed to disconnect cleanly from MCP server: {e}")
            finally:
                self._entered = False
                self.client = None
    
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
