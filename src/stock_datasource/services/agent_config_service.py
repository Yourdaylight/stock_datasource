"""Agent configuration CRUD service with ClickHouse persistence."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import yaml

from stock_datasource.models.agent_config import (
    AgentConfigCreate,
    AgentConfigResponse,
    AgentConfigUpdate,
    AgentStatus,
    ModelConfig,
    RuntimeConfig,
)
from stock_datasource.models.database import db_client

logger = logging.getLogger(__name__)

# Table DDL — executed on first use
_TABLE_CREATED = False
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS agent_configs (
    id             String,
    user_id        String,
    name           String,
    description    String DEFAULT '',
    avatar         String DEFAULT '',
    system_prompt  String,
    skills         Array(String),
    model_config   String DEFAULT '{}',
    tags           Array(String),
    is_public      UInt8 DEFAULT 0,
    status         Enum8('active'=1, 'archived'=2, 'deleted'=3),
    version        UInt32 DEFAULT 1,
    created_at     DateTime DEFAULT now(),
    updated_at     DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (user_id, id)
SETTINGS index_granularity = 8192
"""


def _ensure_table():
    """Create table if not exists."""
    global _TABLE_CREATED
    if _TABLE_CREATED:
        return
    try:
        db_client.execute(CREATE_TABLE_SQL)
        _TABLE_CREATED = True
    except Exception as e:
        logger.warning("Failed to create agent_configs table: %s", e)


def _row_to_response(row: dict) -> AgentConfigResponse:
    """Convert a DB row dict to AgentConfigResponse."""
    skills = row.get("skills", [])
    if isinstance(skills, str):
        try:
            skills = json.loads(skills)
        except (json.JSONDecodeError, TypeError):
            skills = [s.strip().strip("'\"") for s in skills.strip("[]").split(",") if s.strip()]

    tags = row.get("tags", [])
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except (json.JSONDecodeError, TypeError):
            tags = [t.strip().strip("'\"") for t in tags.strip("[]").split(",") if t.strip()]

    model_config_raw = row.get("model_config", "{}")
    if isinstance(model_config_raw, str):
        try:
            model_config_data = ModelConfig(**json.loads(model_config_raw))
        except (json.JSONDecodeError, TypeError):
            model_config_data = ModelConfig()
    else:
        model_config_data = ModelConfig()

    runtime_config_raw = row.get("runtime_config", "{}")
    if isinstance(runtime_config_raw, str):
        try:
            runtime_config = RuntimeConfig(**json.loads(runtime_config_raw))
        except (json.JSONDecodeError, TypeError):
            runtime_config = RuntimeConfig()
    else:
        runtime_config = RuntimeConfig()
    # Override type from top-level runtime field if present
    runtime_val = row.get("runtime", "langgraph")
    if runtime_val and runtime_val != "langgraph":
        runtime_config.type = str(runtime_val)

    user_skills = row.get("user_skills", [])
    if isinstance(user_skills, str):
        try:
            user_skills = json.loads(user_skills)
        except (json.JSONDecodeError, TypeError):
            user_skills = [s.strip().strip("'\"") for s in user_skills.strip("[]").split(",") if s.strip()]

    status_val = row.get("status", "active")
    if isinstance(status_val, int):
        status_val = {1: "active", 2: "archived", 3: "deleted"}.get(status_val, "active")

    return AgentConfigResponse(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        name=str(row.get("name", "")),
        description=str(row.get("description", "")),
        avatar=str(row.get("avatar", "")),
        system_prompt=str(row.get("system_prompt", "")),
        skills=skills,
        user_skills=user_skills if isinstance(user_skills, list) else [],
        model_config_data=model_config_data,
        runtime_config=runtime_config,
        tags=tags,
        is_public=bool(row.get("is_public", 0)),
        status=AgentStatus(status_val),
        version=int(row.get("version", 1)),
        created_at=row.get("created_at", datetime.now()),
        updated_at=row.get("updated_at", datetime.now()),
    )


class AgentConfigService:
    """CRUD operations for user-defined agent configurations."""

    def __init__(self):
        _ensure_table()

    def create_agent(self, user_id: str, data: AgentConfigCreate) -> AgentConfigResponse:
        """Create a new agent configuration."""
        agent_id = str(uuid.uuid4())
        now = datetime.now()
        model_config_json = data.model_config_data.model_dump_json()

        row = {
            "id": agent_id,
            "user_id": user_id,
            "name": data.name,
            "description": data.description,
            "avatar": data.avatar,
            "system_prompt": data.system_prompt,
            "skills": data.skills,
            "user_skills": data.user_skills,
            "model_config": model_config_json,
            "runtime": data.runtime_config.type,
            "runtime_config": data.runtime_config.model_dump_json(),
            "tags": data.tags,
            "is_public": 1 if data.is_public else 0,
            "status": "active",
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
        db_client.insert_dataframe("agent_configs", pd.DataFrame([row]))
        logger.info("Created agent %s for user %s", agent_id, user_id)
        return _row_to_response(row)

    def get_agent(self, agent_id: str, user_id: Optional[str] = None) -> Optional[AgentConfigResponse]:
        """Get agent by ID. Returns None if not found or no access."""
        _ensure_table()
        if user_id:
            where = f"AND (user_id = '{user_id}' OR user_id = 'system' OR is_public = 1)"
        else:
            where = ""
        # Use argMax to get the row with highest updated_at (most reliable dedup)
        df = db_client.execute_query(f"""
            SELECT
                id, user_id, name, description, avatar, system_prompt,
                skills, model_config, tags, is_public, status, version,
                created_at, updated_at
            FROM agent_configs FINAL
            WHERE id = '{agent_id}' {where}
            ORDER BY updated_at DESC
            LIMIT 1
        """)
        if df.empty:
            return None
        row = df.iloc[0].to_dict()
        # Check status after fetching (more reliable than WHERE filter with FINAL)
        status_val = row.get("status", "active")
        if isinstance(status_val, int):
            status_val = {1: "active", 2: "archived", 3: "deleted"}.get(status_val, "active")
        if status_val == "deleted":
            return None
        return _row_to_response(row)

    def list_agents(self, user_id: str, include_public: bool = True) -> list[AgentConfigResponse]:
        """List agents visible to user."""
        _ensure_table()
        if include_public:
            where = f"(user_id = '{user_id}' OR user_id = 'system' OR is_public = 1)"
        else:
            where = f"user_id = '{user_id}'"
        df = db_client.execute_query(f"""
            SELECT * FROM agent_configs FINAL
            WHERE {where}
            ORDER BY updated_at DESC
        """)
        if df.empty:
            return []
        results = []
        for _, row in df.iterrows():
            row_dict = row.to_dict()
            status_val = row_dict.get("status", "active")
            if isinstance(status_val, int):
                status_val = {1: "active", 2: "archived", 3: "deleted"}.get(status_val, "active")
            if status_val == "deleted":
                continue
            results.append(_row_to_response(row_dict))
        return results

    def update_agent(
        self, agent_id: str, user_id: str, data: AgentConfigUpdate
    ) -> Optional[AgentConfigResponse]:
        """Update agent configuration (insert new version row)."""
        current = self.get_agent(agent_id, user_id)
        if current is None:
            return None
        if current.user_id != user_id and current.user_id != "system":
            return None

        now = datetime.now()
        updated = current.model_dump()
        update_data = data.model_dump(exclude_unset=True)

        if "model_config_data" in update_data and update_data["model_config_data"] is not None:
            updated["model_config"] = json.dumps(update_data.pop("model_config_data"))
        else:
            update_data.pop("model_config_data", None)
            updated["model_config"] = current.model_config_data.model_dump_json()

        for key, value in update_data.items():
            if key in updated:
                updated[key] = value

        updated["version"] = current.version + 1
        updated["updated_at"] = now
        updated["is_public"] = 1 if updated.get("is_public") else 0

        # Remove response-only fields
        updated.pop("model_config_data", None)

        db_client.insert_dataframe("agent_configs", pd.DataFrame([updated]))
        logger.info("Updated agent %s (v%d)", agent_id, updated["version"])
        return self.get_agent(agent_id, user_id)

    def delete_agent(self, agent_id: str, user_id: str) -> bool:
        """Soft-delete an agent."""
        # Check agent exists first
        current = self.get_agent(agent_id, user_id)
        if current is None:
            return False
        if current.user_id != user_id and current.user_id != "system":
            return False

        # Insert a deleted version row directly
        now = datetime.now()
        row = {
            "id": current.id,
            "user_id": current.user_id,
            "name": current.name,
            "description": current.description,
            "avatar": current.avatar,
            "system_prompt": current.system_prompt,
            "skills": current.skills,
            "model_config": current.model_config_data.model_dump_json(),
            "tags": current.tags,
            "is_public": 1 if current.is_public else 0,
            "status": "deleted",
            "version": current.version + 1,
            "created_at": current.created_at,
            "updated_at": now,
        }
        db_client.insert_dataframe("agent_configs", pd.DataFrame([row]))
        logger.info("Deleted agent %s (v%d)", agent_id, row["version"])
        return True


# ---------------------------------------------------------------------------
# Built-in agent seed data sync
# ---------------------------------------------------------------------------

_BUILTIN_YAML_PATH = Path(__file__).resolve().parent.parent / "config" / "builtin_agents.yaml"


def sync_builtin_agents() -> int:
    """Sync built-in agents from YAML to ClickHouse (idempotent).

    Reads config/builtin_agents.yaml and inserts any missing system agents
    into the agent_configs table.  Already-existing agents (matched by id
    and user_id='system') are skipped.

    Returns:
        Number of newly inserted agents.
    """
    if not _BUILTIN_YAML_PATH.exists():
        logger.warning("Builtin agents YAML not found: %s", _BUILTIN_YAML_PATH)
        return 0

    try:
        with open(_BUILTIN_YAML_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        logger.warning("Failed to load builtin agents YAML: %s", e)
        return 0

    agents = data.get("builtin_agents", []) if isinstance(data, dict) else []
    if not agents:
        logger.warning("No builtin agents defined in YAML")
        return 0

    _ensure_table()

    # Collect existing system agent IDs in one query
    try:
        df_existing = db_client.execute_query(
            "SELECT DISTINCT id FROM agent_configs FINAL WHERE user_id = 'system'"
        )
        existing_ids = set(df_existing["id"].tolist()) if not df_existing.empty else set()
    except Exception as e:
        logger.warning("Failed to query existing builtin agents: %s", e)
        existing_ids = set()

    now = datetime.now()
    rows_to_insert = []
    skipped = 0

    for agent in agents:
        agent_id = str(agent.get("id", ""))
        if not agent_id:
            logger.warning("Skipping builtin agent with empty id: %s", agent.get("name"))
            continue
        if agent_id in existing_ids:
            skipped += 1
            continue

        model_cfg = agent.get("model_config", {}) or {}
        runtime_cfg = agent.get("runtime_config", {}) or {}

        rows_to_insert.append({
            "id": agent_id,
            "user_id": "system",
            "name": str(agent.get("name", "")),
            "description": str(agent.get("description", "")),
            "avatar": str(agent.get("avatar", "")),
            "system_prompt": str(agent.get("system_prompt", "")),
            "skills": agent.get("skills", []) or [],
            "model_config": json.dumps({
                "model": model_cfg.get("model", "DeepSeek-V4-Pro"),
                "temperature": model_cfg.get("temperature", 0.7),
                "max_tokens": model_cfg.get("max_tokens", 4096),
                "min_tokens": model_cfg.get("min_tokens", 0),
            }),
            "tags": agent.get("tags", []) or [],
            "is_public": 1,
            "status": "active",
            "version": 1,
            "created_at": now,
            "updated_at": now,
        })

    if rows_to_insert:
        try:
            db_client.insert_dataframe("agent_configs", pd.DataFrame(rows_to_insert))
        except Exception as e:
            logger.warning("Failed to insert builtin agents: %s", e)
            return 0

    inserted = len(rows_to_insert)
    if inserted > 0:
        logger.info("Synced %d built-in agents (skipped %d already exist)", inserted, skipped)
    elif skipped > 0:
        logger.info("Built-in agent sync: %d already exist, nothing to insert", skipped)
    return inserted


# Singleton
_service: Optional[AgentConfigService] = None


def get_agent_config_service() -> AgentConfigService:
    """Get or create the singleton AgentConfigService."""
    global _service
    if _service is None:
        _service = AgentConfigService()
    return _service
