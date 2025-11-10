#!/usr/bin/env python3
"""MCP server for stock-datasource that starts HTTP server."""

import sys
import os
from pathlib import Path

# Get the absolute path to the current script
current_file = Path(__file__).resolve()
project_root = current_file.parent

# Add src directory to Python path
src_dir = project_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# Set environment variables
os.environ["TUSHARE_TOKEN"] = "e1f97db376d934dc3b855e34ccbf5876d4814e16e8959fde923df436"

def main():
    """Start the MCP HTTP server."""
    try:
        print("🚀 Starting MCP HTTP server...")
        
        # Import the module
        from stock_datasource.services.mcp_server import create_app
        import uvicorn
        
        # Create FastAPI app
        app = create_app()
        
        print("✅ FastAPI app created successfully")
        print("🌐 Starting HTTP server on http://0.0.0.0:8003")
        
        # Start the HTTP server
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8003,
            log_level="info",
            timeout_keep_alive=30,
        )
        
    except Exception as e:
        print(f"❌ Error starting MCP server: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()