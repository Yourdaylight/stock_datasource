"""MCP tool usage tracking service."""

import logging
import os
import uuid
from datetime import datetime
from typing import Optional, Dict, List

from stock_datasource.models.database import db_client

logger = logging.getLogger(__name__)

_schema_initialized = False


async def _ensure_schema():
    """Ensure mcp_tool_usage_log table exists (lazy init)."""
    global _schema_initialized
    if _schema_initialized:
        return
    try:
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        with open(schema_path, "r") as f:
            schema_sql = f.read()
        for statement in schema_sql.split(";"):
            statement = statement.strip()
            if statement:
                db_client.execute(statement)
        _schema_initialized = True
        logger.info("MCP tool usage schema initialized")
    except Exception as e:
        logger.error(f"Failed to initialize MCP usage schema: {e}")


class McpUsageService:
    """Service for logging and querying MCP tool usage."""

    @staticmethod
    async def log_usage(
        user_id: str,
        api_key_id: str,
        tool_name: str,
        service_prefix: str = "",
        table_name: str = "",
        arguments: str = "",
        record_count: int = 0,
        duration_ms: int = 0,
        is_error: bool = False,
        error_message: str = "",
    ) -> None:
        """Log a single MCP tool call. Fire-and-forget."""
        await _ensure_schema()
        try:
            log_id = str(uuid.uuid4())
            db_client.execute(
                "INSERT INTO mcp_tool_usage_log "
                "(id, user_id, api_key_id, tool_name, service_prefix, table_name, "
                "arguments, record_count, duration_ms, is_error, error_message, created_at) "
                "VALUES (%(id)s, %(user_id)s, %(api_key_id)s, %(tool_name)s, "
                "%(service_prefix)s, %(table_name)s, %(arguments)s, %(record_count)s, "
                "%(duration_ms)s, %(is_error)s, %(error_message)s, now())",
                {
                    "id": log_id,
                    "user_id": user_id,
                    "api_key_id": api_key_id,
                    "tool_name": tool_name,
                    "service_prefix": service_prefix,
                    "table_name": table_name,
                    "arguments": arguments[:2000],
                    "record_count": record_count,
                    "duration_ms": duration_ms,
                    "is_error": int(is_error),
                    "error_message": error_message[:500] if error_message else "",
                },
            )
            logger.debug(
                f"Logged MCP usage: tool={tool_name} table={table_name} "
                f"records={record_count} ms={duration_ms}"
            )
        except Exception as e:
            logger.error(f"Failed to log MCP usage: {e}")

    @staticmethod
    async def get_usage_history(
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        tool_name: Optional[str] = None,
    ) -> Dict:
        """Get paginated usage history for a user."""
        await _ensure_schema()
        try:
            where = "WHERE user_id = %(user_id)s"
            params: Dict = {"user_id": user_id}

            if start_date:
                where += " AND created_at >= %(start_date)s"
                params["start_date"] = start_date
            if end_date:
                where += " AND created_at <= %(end_date)s"
                params["end_date"] = end_date
            if tool_name:
                where += " AND tool_name = %(tool_name)s"
                params["tool_name"] = tool_name

            count_df = db_client.query(
                f"SELECT count() as cnt FROM mcp_tool_usage_log {where}", params
            )
            count_result = count_df.to_dict('records') if not count_df.empty else []
            total = count_result[0]["cnt"] if count_result else 0

            offset = (page - 1) * page_size
            params["limit"] = page_size
            params["offset"] = offset

            records_df = db_client.query(
                f"SELECT id, user_id, api_key_id, tool_name, service_prefix, "
                f"table_name, arguments, record_count, duration_ms, "
                f"is_error, error_message, created_at "
                f"FROM mcp_tool_usage_log {where} "
                f"ORDER BY created_at DESC "
                f"LIMIT %(limit)s OFFSET %(offset)s",
                params,
            )
            records = records_df.to_dict('records') if not records_df.empty else []

            return {
                "records": records,
                "total": total,
                "page": page,
                "page_size": page_size,
            }
        except Exception as e:
            logger.error(f"Failed to get MCP usage history: {e}")
            return {"records": [], "total": 0, "page": page, "page_size": page_size}

    @staticmethod
    async def get_usage_stats(user_id: str, days: int = 30) -> Dict:
        """Get daily aggregated usage stats."""
        await _ensure_schema()
        try:
            # Daily stats
            daily_df = db_client.query(
                "SELECT toDate(created_at) as date, "
                "count() as call_count, "
                "sum(record_count) as total_records "
                "FROM mcp_tool_usage_log "
                "WHERE user_id = %(user_id)s "
                "AND created_at >= today() - %(days)s "
                "GROUP BY date ORDER BY date",
                {"user_id": user_id, "days": days},
            )
            daily_result = daily_df.to_dict('records') if not daily_df.empty else []

            daily_stats = []
            total_calls = 0
            total_records = 0
            for row in daily_result:
                cc = row["call_count"]
                tr = row["total_records"]
                daily_stats.append({
                    "date": str(row["date"]),
                    "call_count": cc,
                    "total_records": tr,
                })
                total_calls += cc
                total_records += tr

            # Top tools
            top_df = db_client.query(
                "SELECT tool_name, any(table_name) as table_name, "
                "count() as call_count, sum(record_count) as total_records "
                "FROM mcp_tool_usage_log "
                "WHERE user_id = %(user_id)s "
                "AND created_at >= today() - %(days)s "
                "GROUP BY tool_name "
                "ORDER BY call_count DESC LIMIT 10",
                {"user_id": user_id, "days": days},
            )
            top_result = top_df.to_dict('records') if not top_df.empty else []
            top_tools = [
                {
                    "tool_name": r["tool_name"],
                    "table_name": r["table_name"],
                    "call_count": r["call_count"],
                    "total_records": r["total_records"],
                }
                for r in top_result
            ]

            num_days = max(len(daily_stats), 1)
            return {
                "daily_stats": daily_stats,
                "total_calls": total_calls,
                "total_records": total_records,
                "avg_daily_calls": round(total_calls / num_days, 1),
                "top_tools": top_tools,
            }
        except Exception as e:
            logger.error(f"Failed to get MCP usage stats: {e}")
            return {
                "daily_stats": [],
                "total_calls": 0,
                "total_records": 0,
                "avg_daily_calls": 0.0,
                "top_tools": [],
            }
