---
name: mcp-api-key-auth
description: This skill should be used when the user needs to set up, manage, or troubleshoot MCP API Key authentication and tool usage tracking for this stock data service. Use it when configuring external MCP clients (Claude Code, Cursor) to connect to the data service.
---

## Purpose

Enable external MCP clients (Claude Code, Cursor, etc.) to authenticate with the stock data service using independent API keys, and track per-tool usage (table name, record count) for monitoring.

## When to Use

- User wants to create or manage MCP API keys
- User wants to configure an external MCP client to connect to this service
- User wants to view MCP tool usage statistics (which tools called, which tables queried, how many records)
- User needs to troubleshoot MCP authentication errors (401, invalid key, expired key)

## Architecture

- **API Key management** is on the HTTP server (port 8000), protected by JWT login
- **MCP protocol** is on the MCP server (port 8001), protected by API key in request headers
- **Usage tracking** records are stored in ClickHouse `mcp_tool_usage_log` table

## Workflow

### 1) Create an API Key

First login to get a JWT token, then create an API key:

```bash
# Login
JWT=$(curl -s -X POST http://<host>:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"your@email.com","password":"yourpassword"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Create API key
curl -s -X POST http://<host>:8000/api/mcp-keys/create \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"key_name": "my-cursor-key", "expires_days": 90}'
```

The response contains the full API key (e.g., `sk-a1b2c3d4...`). **Save it immediately** — it is only shown once.

### 2) Configure MCP Client

#### Claude Code / Claude Desktop

Add to your MCP configuration (`claude_desktop_config.json` or project `.mcp.json`):

```json
{
  "mcpServers": {
    "stock-data": {
      "url": "http://<host>:8001/messages",
      "transport": "streamable-http",
      "headers": {
        "Authorization": "Bearer sk-your-api-key-here"
      }
    }
  }
}
```

#### Cursor

In Cursor settings, add an MCP server with:
- **URL**: `http://<host>:8001/messages`
- **Header**: `Authorization: Bearer sk-your-api-key-here`

### 3) Verify Connectivity

```bash
# Should return tool list (not 401)
curl -s -X POST http://<host>:8001/messages \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-your-api-key-here" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

### 4) View Usage Statistics

```bash
# Usage history (paginated)
curl -s "http://<host>:8000/api/mcp-usage/history?page=1&page_size=20" \
  -H "Authorization: Bearer $JWT"

# Aggregated stats (last 30 days)
curl -s "http://<host>:8000/api/mcp-usage/stats?days=30" \
  -H "Authorization: Bearer $JWT"
```

### 5) Manage API Keys

```bash
# List all keys
curl -s http://<host>:8000/api/mcp-keys/list \
  -H "Authorization: Bearer $JWT"

# Revoke a key
curl -s -X POST http://<host>:8000/api/mcp-keys/revoke \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"key_id": "<key-id>"}'
```

## Key Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/mcp-keys/create` | POST | JWT | Create new API key |
| `/api/mcp-keys/list` | GET | JWT | List user's API keys |
| `/api/mcp-keys/revoke` | POST | JWT | Revoke an API key |
| `/api/mcp-usage/history` | GET | JWT | Paginated usage history |
| `/api/mcp-usage/stats` | GET | JWT | Aggregated usage stats |
| `/messages` (MCP) | POST | API Key | MCP protocol endpoint |

## Troubleshooting

- **401 "API key required"**: Missing `Authorization` header on MCP calls
- **401 "Invalid or expired API key"**: Key was revoked or expired — create a new one
- **`initialize` works but `tools/list` fails**: `initialize` does not require auth; `tools/list` and `tools/call` do
- **Usage not showing up**: Usage logging is fire-and-forget; check ClickHouse `mcp_tool_usage_log` table directly

## Verification Checklist

- [ ] API key created and full key returned (shown only once)
- [ ] `tools/list` returns 401 without API key
- [ ] `tools/list` returns tool list with valid API key
- [ ] `tools/call` records usage in `mcp_tool_usage_log` table
- [ ] Revoked key returns 401 on subsequent calls
- [ ] Usage history API returns correct data
- [ ] Usage stats show daily call counts and top tools
