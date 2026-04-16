"""Open API Gateway service — policy CRUD, endpoint discovery, usage logging."""

import logging
import os
import time
import uuid
from datetime import datetime
from typing import Any

from stock_datasource.models.database import db_client

logger = logging.getLogger(__name__)

_schema_initialized = False


def _ensure_tables() -> None:
    """Ensure api_access_policies and api_usage_log tables exist (lazy init, dual-write)."""
    global _schema_initialized
    if _schema_initialized:
        return

    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    try:
        with open(schema_path) as f:
            schema_sql = f.read()
        for statement in schema_sql.split(";"):
            statement = statement.strip()
            if statement:
                try:
                    db_client.primary.execute(statement)
                except Exception as e:
                    logger.warning(f"Failed to execute open_api schema on primary: {e}")
                if db_client.backup:
                    try:
                        db_client.backup.execute(statement)
                    except Exception as e:
                        logger.warning(
                            f"Failed to execute open_api schema on backup: {e}"
                        )
        _schema_initialized = True
        logger.info("Open API Gateway schema initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Open API Gateway schema: {e}")


class OpenApiService:
    """Manages access policies, endpoint discovery, and usage logging."""

    def __init__(self):
        self.client = db_client
        # In-memory policy cache: {api_path: policy_dict}
        self._policy_cache: dict[str, dict[str, Any]] = {}
        self._cache_ts: float = 0
        self._cache_ttl: float = float(os.getenv("OPEN_API_POLICY_CACHE_TTL", "300"))

    # ------------------------------------------------------------------
    # Endpoint discovery — ONLY from plugin services
    # ------------------------------------------------------------------

    def discover_endpoints(self) -> list[dict[str, Any]]:
        """Discover all available plugin endpoints.

        CRITICAL: Only scans plugins/*/service.py via ServiceGenerator.
        Never scans module routers or app.routes.
        """
        from stock_datasource.core.service_generator import ServiceGenerator
        from stock_datasource.services.http_server import (
            _discover_services,
            _get_or_create_service,
        )

        endpoints: list[dict[str, Any]] = []

        for service_name, service_class in _discover_services():
            try:
                service = _get_or_create_service(service_class, service_name)
                if service is None:
                    continue
                gen = ServiceGenerator(service)
                for method_name, info in gen.methods.items():
                    api_path = f"{service_name}/{method_name}"
                    params = []
                    for p in info["metadata"]["params"]:
                        params.append(
                            {
                                "name": p.name,
                                "type": p.type,
                                "description": p.description,
                                "required": p.required,
                                "default": p.default,
                            }
                        )
                    endpoints.append(
                        {
                            "plugin_name": service_name,
                            "method_name": method_name,
                            "api_path": api_path,
                            "description": info["metadata"]["description"],
                            "parameters": params,
                        }
                    )
            except Exception as e:
                logger.warning(f"Failed to discover endpoints for {service_name}: {e}")

        return endpoints

    # ------------------------------------------------------------------
    # Policy CRUD
    # ------------------------------------------------------------------

    def get_all_policies(self) -> list[dict[str, Any]]:
        """Get all access policies (with FINAL for ReplacingMergeTree)."""
        _ensure_tables()
        try:
            rows = self.client.query(
                "SELECT policy_id, api_path, api_type, is_enabled, "
                "rate_limit_per_min, rate_limit_per_day, max_records, "
                "description, created_at, updated_at "
                "FROM api_access_policies FINAL "
                "ORDER BY api_path",
            )
            return [
                {
                    "policy_id": r["policy_id"],
                    "api_path": r["api_path"],
                    "api_type": r["api_type"],
                    "is_enabled": bool(r["is_enabled"]),
                    "rate_limit_per_min": r["rate_limit_per_min"],
                    "rate_limit_per_day": r["rate_limit_per_day"],
                    "max_records": r["max_records"],
                    "description": r["description"],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                }
                for r in (rows or [])
            ]
        except Exception as e:
            logger.error(f"Failed to get policies: {e}")
            return []

    def get_policy(self, api_path: str) -> dict[str, Any] | None:
        """Get policy for a specific api_path (cache-first)."""
        self._refresh_cache_if_needed()
        return self._policy_cache.get(api_path)

    def upsert_policy(
        self,
        api_path: str,
        is_enabled: bool | None = None,
        rate_limit_per_min: int | None = None,
        rate_limit_per_day: int | None = None,
        max_records: int | None = None,
        description: str | None = None,
    ) -> tuple[bool, str]:
        """Create or update an access policy."""
        _ensure_tables()
        try:
            existing = self._query_policy_from_db(api_path)
            now = datetime.now()

            if existing:
                # Update: insert new version (ReplacingMergeTree)
                policy_id = existing["policy_id"]
                new_vals = {
                    "policy_id": policy_id,
                    "api_path": api_path,
                    "api_type": existing["api_type"],
                    "is_enabled": int(is_enabled)
                    if is_enabled is not None
                    else existing["is_enabled"],
                    "rate_limit_per_min": rate_limit_per_min
                    if rate_limit_per_min is not None
                    else existing["rate_limit_per_min"],
                    "rate_limit_per_day": rate_limit_per_day
                    if rate_limit_per_day is not None
                    else existing["rate_limit_per_day"],
                    "max_records": max_records
                    if max_records is not None
                    else existing["max_records"],
                    "description": description
                    if description is not None
                    else existing["description"],
                    "created_at": existing["created_at"],
                    "now": now,
                }
            else:
                # Create
                policy_id = str(uuid.uuid4())
                new_vals = {
                    "policy_id": policy_id,
                    "api_path": api_path,
                    "api_type": "http",
                    "is_enabled": int(is_enabled) if is_enabled is not None else 0,
                    "rate_limit_per_min": rate_limit_per_min or 60,
                    "rate_limit_per_day": rate_limit_per_day or 10000,
                    "max_records": max_records or 5000,
                    "description": description or "",
                    "created_at": now,
                    "now": now,
                }

            insert_sql = (
                "INSERT INTO api_access_policies "
                "(policy_id, api_path, api_type, is_enabled, rate_limit_per_min, "
                "rate_limit_per_day, max_records, description, created_at, updated_at) "
                "VALUES (%(policy_id)s, %(api_path)s, %(api_type)s, %(is_enabled)s, "
                "%(rate_limit_per_min)s, %(rate_limit_per_day)s, %(max_records)s, "
                "%(description)s, %(created_at)s, %(now)s)"
            )
            self.client.primary.execute(insert_sql, new_vals)
            if self.client.backup:
                try:
                    self.client.backup.execute(insert_sql, new_vals)
                except Exception as e:
                    logger.warning(f"Failed to write policy to backup: {e}")

            # Invalidate cache
            self._cache_ts = 0

            action = "更新" if existing else "创建"
            return True, f"策略{action}成功: {api_path}"

        except Exception as e:
            logger.error(f"Failed to upsert policy for {api_path}: {e}")
            return False, f"策略操作失败: {e}"

    def batch_toggle(self, api_paths: list[str], is_enabled: bool) -> tuple[bool, str]:
        """Batch enable/disable policies."""
        _ensure_tables()
        success_count = 0
        for path in api_paths:
            ok, _ = self.upsert_policy(path, is_enabled=is_enabled)
            if ok:
                success_count += 1
        return (
            True,
            f"已{'启用' if is_enabled else '禁用'} {success_count}/{len(api_paths)} 个接口",
        )

    def sync_policies_from_plugins(self) -> tuple[int, int]:
        """Discover all plugin endpoints and create default policies for new ones.

        Returns (created, existing).
        """
        _ensure_tables()
        endpoints = self.discover_endpoints()
        existing_policies = {p["api_path"] for p in self.get_all_policies()}

        created = 0
        existing = 0
        for ep in endpoints:
            api_path = ep["api_path"]
            if api_path in existing_policies:
                existing += 1
                continue
            ok, _ = self.upsert_policy(
                api_path=api_path,
                is_enabled=False,  # default: disabled (safe)
                description=ep.get("description", ""),
            )
            if ok:
                created += 1

        logger.info(f"Policy sync: {created} created, {existing} already exist")
        return created, existing

    # ------------------------------------------------------------------
    # Usage logging (async-safe, best-effort)
    # ------------------------------------------------------------------

    def log_usage(
        self,
        api_path: str,
        user_id: str = "",
        api_key_id: str = "",
        record_count: int = 0,
        response_time_ms: int = 0,
        status_code: int = 200,
        error_message: str = "",
        client_ip: str = "",
    ) -> None:
        """Write a usage log entry (fire-and-forget)."""
        _ensure_tables()
        try:
            log_id = str(uuid.uuid4())
            now = datetime.now()
            insert_sql = (
                "INSERT INTO api_usage_log "
                "(log_id, api_path, api_type, user_id, api_key_id, "
                "record_count, response_time_ms, status_code, error_message, "
                "client_ip, created_at) "
                "VALUES (%(log_id)s, %(api_path)s, 'http', %(user_id)s, "
                "%(api_key_id)s, %(record_count)s, %(response_time_ms)s, "
                "%(status_code)s, %(error_message)s, %(client_ip)s, %(now)s)"
            )
            params = {
                "log_id": log_id,
                "api_path": api_path,
                "user_id": user_id,
                "api_key_id": api_key_id,
                "record_count": record_count,
                "response_time_ms": response_time_ms,
                "status_code": status_code,
                "error_message": error_message,
                "client_ip": client_ip,
                "now": now,
            }
            self.client.primary.execute(insert_sql, params)
        except Exception as e:
            logger.warning(f"Failed to log API usage: {e}")

    def get_usage_stats(
        self,
        days: int = 7,
        api_path: str | None = None,
        api_key_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get aggregated usage statistics."""
        _ensure_tables()
        try:
            conditions = ["created_at >= now() - toIntervalDay(%(days)s)"]
            params: dict[str, Any] = {"days": days}

            if api_path:
                conditions.append("api_path = %(api_path)s")
                params["api_path"] = api_path
            if api_key_id:
                conditions.append("api_key_id = %(api_key_id)s")
                params["api_key_id"] = api_key_id

            where_clause = " AND ".join(conditions)

            query = f"""
                SELECT
                    api_path,
                    count() AS total_calls,
                    countIf(status_code >= 200 AND status_code < 400) AS success_calls,
                    countIf(status_code >= 400) AS error_calls,
                    avg(response_time_ms) AS avg_response_ms,
                    sum(record_count) AS total_records
                FROM api_usage_log
                WHERE {where_clause}
                GROUP BY api_path
                ORDER BY total_calls DESC
            """
            rows = self.client.query(query, params)
            return [
                {
                    "api_path": r["api_path"],
                    "total_calls": r["total_calls"],
                    "success_calls": r["success_calls"],
                    "error_calls": r["error_calls"],
                    "avg_response_ms": round(float(r["avg_response_ms"]), 1),
                    "total_records": r["total_records"],
                }
                for r in (rows or [])
            ]
        except Exception as e:
            logger.error(f"Failed to get usage stats: {e}")
            return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _query_policy_from_db(self, api_path: str) -> dict[str, Any] | None:
        """Query a single policy directly from DB."""
        try:
            rows = self.client.query(
                "SELECT policy_id, api_path, api_type, is_enabled, "
                "rate_limit_per_min, rate_limit_per_day, max_records, "
                "description, created_at, updated_at "
                "FROM api_access_policies FINAL "
                "WHERE api_path = %(api_path)s "
                "LIMIT 1",
                {"api_path": api_path},
            )
            if rows:
                r = rows[0]
                return {
                    "policy_id": r["policy_id"],
                    "api_path": r["api_path"],
                    "api_type": r["api_type"],
                    "is_enabled": r["is_enabled"],
                    "rate_limit_per_min": r["rate_limit_per_min"],
                    "rate_limit_per_day": r["rate_limit_per_day"],
                    "max_records": r["max_records"],
                    "description": r["description"],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                }
        except Exception as e:
            logger.warning(f"Failed to query policy for {api_path}: {e}")
        return None

    def _refresh_cache_if_needed(self) -> None:
        """Refresh in-memory policy cache if TTL expired."""
        now = time.time()
        if now - self._cache_ts < self._cache_ttl:
            return
        try:
            policies = self.get_all_policies()
            self._policy_cache = {p["api_path"]: p for p in policies}
            self._cache_ts = now
        except Exception as e:
            logger.warning(f"Failed to refresh policy cache: {e}")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_service: OpenApiService | None = None


def get_open_api_service() -> OpenApiService:
    """Get the Open API service singleton."""
    global _service
    if _service is None:
        _service = OpenApiService()
    return _service
