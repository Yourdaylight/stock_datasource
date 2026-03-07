"""Token usage tracking and quota management service."""

import logging
import math
import os
import uuid
from datetime import datetime
from typing import Optional, Dict, List, Tuple

from ...models.database import db_client

logger = logging.getLogger(__name__)

DEFAULT_QUOTA = 1_000_000

_schema_initialized = False


async def _ensure_schema():
    """Ensure token usage tables exist (lazy init)."""
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
        logger.info("Token usage schema initialized")
    except Exception as e:
        logger.error(f"Failed to initialize token usage schema: {e}")


class TokenUsageService:
    """Service for managing user token quotas and usage logs."""

    @staticmethod
    async def initialize_quota(user_id: str, quota: int = DEFAULT_QUOTA) -> None:
        """Initialize token quota for a new user."""
        await _ensure_schema()
        try:
            db_client.execute(
                "INSERT INTO user_token_quota (user_id, total_quota, used_tokens, remaining_tokens, updated_at) "
                "VALUES (%(user_id)s, %(total_quota)s, 0, %(remaining_tokens)s, now())",
                {
                    "user_id": user_id,
                    "total_quota": quota,
                    "remaining_tokens": quota,
                }
            )
            logger.info(f"Initialized token quota for user {user_id}: {quota}")
        except Exception as e:
            logger.error(f"Failed to initialize quota for user {user_id}: {e}")

    @staticmethod
    async def get_balance(user_id: str) -> Dict:
        """Get user's token balance."""
        await _ensure_schema()
        try:
            df = db_client.query(
                "SELECT total_quota, used_tokens, remaining_tokens "
                "FROM user_token_quota FINAL "
                "WHERE user_id = %(user_id)s",
                {"user_id": user_id}
            )
            result = df.to_dict('records') if not df.empty else []
            if result:
                row = result[0]
                total = row["total_quota"]
                used = row["used_tokens"]
                remaining = row["remaining_tokens"]
                usage_percent = round((used / total * 100), 2) if total > 0 else 0.0
                return {
                    "user_id": user_id,
                    "total_quota": total,
                    "used_tokens": used,
                    "remaining_tokens": remaining,
                    "usage_percent": usage_percent,
                }
            # User has no quota record yet — auto-init
            await TokenUsageService.initialize_quota(user_id)
            return {
                "user_id": user_id,
                "total_quota": DEFAULT_QUOTA,
                "used_tokens": 0,
                "remaining_tokens": DEFAULT_QUOTA,
                "usage_percent": 0.0,
            }
        except Exception as e:
            logger.error(f"Failed to get balance for user {user_id}: {e}")
            return {
                "user_id": user_id,
                "total_quota": DEFAULT_QUOTA,
                "used_tokens": 0,
                "remaining_tokens": DEFAULT_QUOTA,
                "usage_percent": 0.0,
            }

    @staticmethod
    async def has_sufficient_balance(user_id: str) -> bool:
        """Check if user has remaining token balance."""
        balance = await TokenUsageService.get_balance(user_id)
        return balance["remaining_tokens"] > 0

    @staticmethod
    async def deduct_tokens(
        user_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        session_id: str = "",
        message_id: str = "",
        agent_name: str = "",
        model_name: str = "",
    ) -> Dict:
        """Deduct tokens from user's balance and log usage.
        
        Returns updated balance dict.
        """
        await _ensure_schema()
        try:
            # Get current balance
            balance = await TokenUsageService.get_balance(user_id)
            new_used = balance["used_tokens"] + total_tokens
            new_remaining = max(balance["total_quota"] - new_used, 0)

            # Update quota (INSERT new version for ReplacingMergeTree)
            db_client.execute(
                "INSERT INTO user_token_quota (user_id, total_quota, used_tokens, remaining_tokens, updated_at) "
                "VALUES (%(user_id)s, %(total_quota)s, %(used_tokens)s, %(remaining_tokens)s, now())",
                {
                    "user_id": user_id,
                    "total_quota": balance["total_quota"],
                    "used_tokens": new_used,
                    "remaining_tokens": new_remaining,
                }
            )

            # Insert usage log
            log_id = str(uuid.uuid4())
            db_client.execute(
                "INSERT INTO token_usage_log "
                "(id, user_id, session_id, message_id, agent_name, model_name, "
                "prompt_tokens, completion_tokens, total_tokens, created_at) "
                "VALUES (%(id)s, %(user_id)s, %(session_id)s, %(message_id)s, "
                "%(agent_name)s, %(model_name)s, %(prompt_tokens)s, "
                "%(completion_tokens)s, %(total_tokens)s, now())",
                {
                    "id": log_id,
                    "user_id": user_id,
                    "session_id": session_id,
                    "message_id": message_id,
                    "agent_name": agent_name,
                    "model_name": model_name,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                }
            )

            logger.info(
                f"Deducted {total_tokens} tokens for user {user_id} "
                f"(prompt={prompt_tokens}, completion={completion_tokens})"
            )
            return {
                "user_id": user_id,
                "total_quota": balance["total_quota"],
                "used_tokens": new_used,
                "remaining_tokens": new_remaining,
                "usage_percent": round((new_used / balance["total_quota"] * 100), 2) if balance["total_quota"] > 0 else 0.0,
            }
        except Exception as e:
            logger.error(f"Failed to deduct tokens for user {user_id}: {e}")
            return await TokenUsageService.get_balance(user_id)

    @staticmethod
    async def get_usage_history(
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict:
        """Get paginated usage history with optional date filter."""
        await _ensure_schema()
        try:
            where = "WHERE t.user_id = %(user_id)s"
            params: Dict = {"user_id": user_id}

            if start_date:
                where += " AND t.created_at >= %(start_date)s"
                params["start_date"] = start_date
            if end_date:
                where += " AND t.created_at <= %(end_date)s"
                params["end_date"] = end_date

            # Count total
            count_df = db_client.query(
                f"SELECT count() as cnt FROM token_usage_log t {where}", params
            )
            count_result = count_df.to_dict('records') if not count_df.empty else []
            total = count_result[0]["cnt"] if count_result else 0

            offset = (page - 1) * page_size
            params["limit"] = page_size
            params["offset"] = offset

            records_df = db_client.query(
                f"SELECT t.id, t.user_id, t.session_id, t.message_id, "
                f"t.agent_name, t.model_name, t.prompt_tokens, t.completion_tokens, "
                f"t.total_tokens, t.created_at, "
                f"s.title as session_title "
                f"FROM token_usage_log t "
                f"LEFT JOIN chat_sessions s ON t.session_id = s.session_id "
                f"{where} "
                f"ORDER BY t.created_at DESC "
                f"LIMIT %(limit)s OFFSET %(offset)s",
                params
            )
            records = records_df.to_dict('records') if not records_df.empty else []

            # Clean NaN values from LEFT JOIN / nullable columns
            for rec in records:
                for key, val in rec.items():
                    if isinstance(val, float) and math.isnan(val):
                        rec[key] = "" if isinstance(records_df[key].dtype, object) or key in (
                            "session_title", "message_id", "session_id", "agent_name", "model_name"
                        ) else 0

            return {
                "records": records,
                "total": total,
                "page": page,
                "page_size": page_size,
            }
        except Exception as e:
            logger.error(f"Failed to get usage history for user {user_id}: {e}")
            return {"records": [], "total": 0, "page": page, "page_size": page_size}

    @staticmethod
    async def get_usage_stats(
        user_id: str,
        days: int = 30,
    ) -> Dict:
        """Get daily aggregated usage stats for the last N days."""
        await _ensure_schema()
        try:
            df = db_client.query(
                "SELECT toDate(created_at) as date, "
                "sum(prompt_tokens) as prompt_tokens, "
                "sum(completion_tokens) as completion_tokens, "
                "sum(total_tokens) as total_tokens "
                "FROM token_usage_log "
                "WHERE user_id = %(user_id)s "
                "AND created_at >= today() - %(days)s "
                "GROUP BY date "
                "ORDER BY date",
                {"user_id": user_id, "days": days}
            )
            result = df.to_dict('records') if not df.empty else []

            daily_stats = []
            total_prompt = 0
            total_completion = 0
            total_all = 0
            for row in result:
                d = str(row["date"])
                pt = row["prompt_tokens"]
                ct = row["completion_tokens"]
                tt = row["total_tokens"]
                daily_stats.append({
                    "date": d,
                    "prompt_tokens": pt,
                    "completion_tokens": ct,
                    "total_tokens": tt,
                })
                total_prompt += pt
                total_completion += ct
                total_all += tt

            num_days = max(len(daily_stats), 1)
            return {
                "daily_stats": daily_stats,
                "total_prompt_tokens": total_prompt,
                "total_completion_tokens": total_completion,
                "total_tokens": total_all,
                "avg_daily_tokens": round(total_all / num_days, 1),
            }
        except Exception as e:
            logger.error(f"Failed to get usage stats for user {user_id}: {e}")
            return {
                "daily_stats": [],
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_tokens": 0,
                "avg_daily_tokens": 0.0,
            }

    @staticmethod
    async def ensure_existing_users_have_quota() -> int:
        """Backfill quota for existing users who don't have one yet."""
        await _ensure_schema()
        try:
            df = db_client.query(
                "SELECT id FROM users FINAL "
                "WHERE id NOT IN (SELECT user_id FROM user_token_quota FINAL)"
            )
            users_without_quota = df.to_dict('records') if not df.empty else []
            count = 0
            for user in users_without_quota:
                await TokenUsageService.initialize_quota(user["id"])
                count += 1
            if count:
                logger.info(f"Backfilled token quota for {count} existing users")
            return count
        except Exception as e:
            logger.error(f"Failed to backfill user quotas: {e}")
            return 0
