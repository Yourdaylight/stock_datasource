"""MCP API Key service: create, list, revoke, validate."""

import hashlib
import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

from stock_datasource.models.database import db_client

logger = logging.getLogger(__name__)

_schema_initialized = False


def _ensure_tables() -> None:
    """Ensure mcp_api_keys table exists (lazy init, dual write)."""
    global _schema_initialized
    if _schema_initialized:
        return

    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    try:
        with open(schema_path, "r") as f:
            schema_sql = f.read()
        for statement in schema_sql.split(";"):
            statement = statement.strip()
            if statement:
                try:
                    db_client.primary.execute(statement)
                except Exception as e:
                    logger.warning(f"Failed to execute schema on primary: {e}")
                if db_client.backup:
                    try:
                        db_client.backup.execute(statement)
                    except Exception as e:
                        logger.warning(f"Failed to execute schema on backup: {e}")
        _schema_initialized = True
        logger.info("MCP API key schema initialized")
    except Exception as e:
        logger.error(f"Failed to initialize MCP API key schema: {e}")


def _hash_key(raw_key: str) -> str:
    """SHA-256 hash of the raw API key."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


class McpApiKeyService:
    """Service for managing MCP API Keys."""

    def __init__(self):
        self.client = db_client

    def create_api_key(
        self,
        user_id: str,
        key_name: str = "",
        expires_days: Optional[int] = None,
    ) -> Tuple[bool, str, dict]:
        """Create a new API key.

        Returns:
            (success, message, info_dict)
            info_dict contains the plaintext api_key (shown only once).
        """
        _ensure_tables()
        try:
            key_id = str(uuid.uuid4())
            raw_key = f"sk-{secrets.token_hex(32)}"
            api_key_hash = _hash_key(raw_key)
            api_key_prefix = raw_key[:12] + "..."
            now = datetime.now()

            expires_at = None
            if expires_days:
                expires_at = now + timedelta(days=expires_days)

            insert_sql = (
                "INSERT INTO mcp_api_keys "
                "(id, user_id, key_name, api_key_hash, api_key_prefix, "
                "is_active, expires_at, created_at, updated_at) "
                "VALUES (%(id)s, %(user_id)s, %(key_name)s, %(api_key_hash)s, "
                "%(api_key_prefix)s, 1, %(expires_at)s, %(now)s, %(now)s)"
            )
            params = {
                "id": key_id,
                "user_id": user_id,
                "key_name": key_name,
                "api_key_hash": api_key_hash,
                "api_key_prefix": api_key_prefix,
                "expires_at": expires_at,
                "now": now,
            }

            self.client.primary.execute(insert_sql, params)
            if self.client.backup:
                try:
                    self.client.backup.execute(insert_sql, params)
                except Exception as e:
                    logger.warning(f"Failed to write API key to backup: {e}")

            info = {
                "key_id": key_id,
                "api_key": raw_key,
                "key_name": key_name,
                "api_key_prefix": api_key_prefix,
                "created_at": now,
                "expires_at": expires_at,
            }
            logger.info(f"Created MCP API key {api_key_prefix} for user {user_id}")
            return True, "API Key 创建成功", info

        except Exception as e:
            logger.error(f"Failed to create API key: {e}")
            return False, f"创建失败: {e}", {}

    def list_api_keys(self, user_id: str) -> list:
        """List all active API keys for a user (never returns full key)."""
        _ensure_tables()
        try:
            rows = self.client.query(
                "SELECT id, key_name, api_key_prefix, is_active, "
                "last_used_at, expires_at, created_at "
                "FROM mcp_api_keys FINAL "
                "WHERE user_id = %(user_id)s AND is_active = 1 "
                "ORDER BY created_at DESC",
                {"user_id": user_id},
            )
            return [
                {
                    "id": r["id"],
                    "key_name": r["key_name"],
                    "api_key_prefix": r["api_key_prefix"],
                    "is_active": bool(r["is_active"]),
                    "last_used_at": r["last_used_at"],
                    "expires_at": r["expires_at"],
                    "created_at": r["created_at"],
                }
                for r in (rows or [])
            ]
        except Exception as e:
            logger.error(f"Failed to list API keys: {e}")
            return []

    def revoke_api_key(self, user_id: str, key_id: str) -> Tuple[bool, str]:
        """Revoke an API key (soft-delete via ReplacingMergeTree)."""
        _ensure_tables()
        try:
            # Verify ownership
            rows = self.client.query(
                "SELECT id, key_name, api_key_hash, api_key_prefix, expires_at, created_at "
                "FROM mcp_api_keys FINAL "
                "WHERE id = %(key_id)s AND user_id = %(user_id)s AND is_active = 1",
                {"key_id": key_id, "user_id": user_id},
            )
            if not rows:
                return False, "API Key 不存在或已撤销"

            row = rows[0]
            now = datetime.now()

            # Insert new version with is_active=0
            insert_sql = (
                "INSERT INTO mcp_api_keys "
                "(id, user_id, key_name, api_key_hash, api_key_prefix, "
                "is_active, expires_at, created_at, updated_at) "
                "VALUES (%(id)s, %(user_id)s, %(key_name)s, %(api_key_hash)s, "
                "%(api_key_prefix)s, 0, %(expires_at)s, %(created_at)s, %(now)s)"
            )
            params = {
                "id": key_id,
                "user_id": user_id,
                "key_name": row["key_name"],
                "api_key_hash": row["api_key_hash"],
                "api_key_prefix": row["api_key_prefix"],
                "expires_at": row["expires_at"],
                "created_at": row["created_at"],
                "now": now,
            }
            self.client.primary.execute(insert_sql, params)
            if self.client.backup:
                try:
                    self.client.backup.execute(insert_sql, params)
                except Exception as e:
                    logger.warning(f"Failed to revoke API key on backup: {e}")

            logger.info(f"Revoked MCP API key {key_id} for user {user_id}")
            return True, "API Key 已撤销"

        except Exception as e:
            logger.error(f"Failed to revoke API key: {e}")
            return False, f"撤销失败: {e}"

    def validate_api_key(self, raw_key: str) -> Tuple[bool, dict, str]:
        """Validate an API key.

        Returns:
            (is_valid, user_dict, api_key_id)
        """
        _ensure_tables()
        try:
            api_key_hash = _hash_key(raw_key)
            rows = self.client.query(
                "SELECT id, user_id, is_active, expires_at "
                "FROM mcp_api_keys FINAL "
                "WHERE api_key_hash = %(hash)s AND is_active = 1",
                {"hash": api_key_hash},
            )
            if not rows:
                return False, {}, ""

            row = rows[0]

            # Check expiration
            expires_at = row.get("expires_at")
            if expires_at and expires_at < datetime.now():
                return False, {}, ""

            key_id = row["id"]
            user_id = row["user_id"]

            # Update last_used_at (fire-and-forget, best-effort)
            try:
                self.client.primary.execute(
                    "INSERT INTO mcp_api_keys "
                    "(id, user_id, key_name, api_key_hash, api_key_prefix, "
                    "is_active, last_used_at, expires_at, created_at, updated_at) "
                    "SELECT id, user_id, key_name, api_key_hash, api_key_prefix, "
                    "is_active, %(now)s, expires_at, created_at, %(now)s "
                    "FROM mcp_api_keys FINAL "
                    "WHERE id = %(key_id)s AND is_active = 1",
                    {"key_id": key_id, "now": datetime.now()},
                )
            except Exception:
                pass

            # Fetch user info
            from stock_datasource.modules.auth.service import get_auth_service
            auth_service = get_auth_service()
            user = auth_service.get_user_by_id(user_id)
            if not user:
                return False, {}, ""

            return True, user, key_id

        except Exception as e:
            logger.error(f"Failed to validate API key: {e}")
            return False, {}, ""


# Singleton
_service: Optional[McpApiKeyService] = None


def get_mcp_api_key_service() -> McpApiKeyService:
    """Get the MCP API key service singleton."""
    global _service
    if _service is None:
        _service = McpApiKeyService()
    return _service
