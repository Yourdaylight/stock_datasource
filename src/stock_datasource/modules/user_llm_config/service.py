"""User LLM configuration service."""

import logging
import math
import os
from typing import Dict, List, Optional

from ...models.database import db_client

logger = logging.getLogger(__name__)

_schema_initialized = False


async def _ensure_schema():
    """Ensure user_llm_config table exists."""
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
        logger.info("User LLM config schema initialized")
    except Exception as e:
        logger.error(f"Failed to initialize user_llm_config schema: {e}")


def _mask_key(key: str) -> str:
    """Mask API key for display, showing first 4 and last 4 chars."""
    if len(key) <= 12:
        return key[:3] + "***" + key[-2:]
    return key[:6] + "***" + key[-4:]


def _clean_nan(records: List[Dict]) -> List[Dict]:
    """Clean NaN values from DataFrame-converted records."""
    for rec in records:
        for key, val in rec.items():
            if isinstance(val, float) and math.isnan(val):
                rec[key] = ""
    return records


class UserLlmConfigService:
    """Service for managing user-level LLM configurations."""

    @staticmethod
    async def get_configs(user_id: str) -> List[Dict]:
        """Get all LLM configs for a user."""
        await _ensure_schema()
        try:
            df = db_client.query(
                "SELECT provider, api_key, base_url, model_name, is_active, "
                "toString(updated_at) as updated_at "
                "FROM user_llm_config FINAL "
                "WHERE user_id = %(user_id)s AND is_active = 1",
                {"user_id": user_id}
            )
            records = df.to_dict('records') if not df.empty else []
            records = _clean_nan(records)
            return [
                {
                    "provider": r["provider"],
                    "api_key_masked": _mask_key(r["api_key"]),
                    "base_url": r.get("base_url", ""),
                    "model_name": r.get("model_name", ""),
                    "is_active": bool(r.get("is_active", 1)),
                    "updated_at": r.get("updated_at", ""),
                }
                for r in records
            ]
        except Exception as e:
            logger.error(f"Failed to get LLM configs for user {user_id}: {e}")
            return []

    @staticmethod
    async def save_config(
        user_id: str,
        provider: str,
        api_key: str,
        base_url: str = "",
        model_name: str = "",
    ) -> Dict:
        """Create or update a user's LLM config for a provider."""
        await _ensure_schema()
        try:
            db_client.execute(
                "INSERT INTO user_llm_config "
                "(user_id, provider, api_key, base_url, model_name, is_active, updated_at) "
                "VALUES (%(user_id)s, %(provider)s, %(api_key)s, %(base_url)s, "
                "%(model_name)s, 1, now())",
                {
                    "user_id": user_id,
                    "provider": provider,
                    "api_key": api_key,
                    "base_url": base_url or "",
                    "model_name": model_name or "",
                }
            )
            logger.info(f"Saved LLM config for user {user_id}, provider={provider}")
            return {
                "provider": provider,
                "api_key_masked": _mask_key(api_key),
                "base_url": base_url or "",
                "model_name": model_name or "",
                "is_active": True,
            }
        except Exception as e:
            logger.error(f"Failed to save LLM config for user {user_id}: {e}")
            raise

    @staticmethod
    async def delete_config(user_id: str, provider: str) -> bool:
        """Soft-delete a user's LLM config by setting is_active=0."""
        await _ensure_schema()
        try:
            db_client.execute(
                "INSERT INTO user_llm_config "
                "(user_id, provider, api_key, base_url, model_name, is_active, updated_at) "
                "SELECT user_id, provider, api_key, base_url, model_name, 0, now() "
                "FROM user_llm_config FINAL "
                "WHERE user_id = %(user_id)s AND provider = %(provider)s",
                {"user_id": user_id, "provider": provider}
            )
            logger.info(f"Deleted LLM config for user {user_id}, provider={provider}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete LLM config: {e}")
            return False

    @staticmethod
    async def get_active_key(user_id: str, provider: str = "openai") -> Optional[Dict]:
        """Get the active API key for a user and provider (returns raw key)."""
        await _ensure_schema()
        try:
            df = db_client.query(
                "SELECT api_key, base_url, model_name "
                "FROM user_llm_config FINAL "
                "WHERE user_id = %(user_id)s AND provider = %(provider)s AND is_active = 1",
                {"user_id": user_id, "provider": provider}
            )
            records = df.to_dict('records') if not df.empty else []
            records = _clean_nan(records)
            if records:
                return records[0]
            return None
        except Exception as e:
            logger.error(f"Failed to get active key for user {user_id}: {e}")
            return None

    @staticmethod
    async def test_config(
        api_key: str,
        base_url: str = "",
        model_name: str = "",
        provider: str = "openai",
    ) -> Dict:
        """Test an LLM config by making a simple API call."""
        try:
            import httpx
            url = base_url.rstrip("/") if base_url else "https://api.openai.com/v1"
            test_model = model_name or "gpt-4o-mini"

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{url}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": test_model,
                        "messages": [{"role": "user", "content": "Hi"}],
                        "max_tokens": 5,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    actual_model = data.get("model", test_model)
                    return {
                        "success": True,
                        "message": "连接成功",
                        "model_name": actual_model,
                    }
                else:
                    body = resp.text[:200]
                    return {
                        "success": False,
                        "message": f"API 返回 {resp.status_code}: {body}",
                        "model_name": "",
                    }
        except Exception as e:
            return {
                "success": False,
                "message": f"连接失败: {str(e)}",
                "model_name": "",
            }
