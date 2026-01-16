#!/bin/bash

# Restart backend HTTP server

echo "Restarting backend HTTP server..."

# Find and kill existing processes
PIDS=$(ps aux | grep -E "python.*http_server|uvicorn.*http_server" | grep -v grep | awk '{print $2}')

if [ -n "$PIDS" ]; then
    echo "Killing existing processes: $PIDS"
    kill $PIDS
    sleep 2
else
    echo "No existing processes found"
fi

# Start the server
echo "Starting backend server..."
nohup uv run python -m stock_datasource.services.http_server > /tmp/http_server.log 2>&1 &

# Wait for server to start
echo "Waiting for server to start..."
sleep 3

# Check if server is running
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✓ Backend server started successfully"
    echo "  Health check: curl http://localhost:8000/health"
    echo "  API docs: http://localhost:8000/docs"
    echo "  Log file: /tmp/http_server.log"
else
    echo "✗ Backend server failed to start"
    echo "Check log file: tail -f /tmp/http_server.log"
    exit 1
fi
