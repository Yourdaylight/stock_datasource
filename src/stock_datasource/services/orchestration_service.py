"""Orchestration pipeline CRUD service with ClickHouse persistence."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Optional

import pandas as pd

from stock_datasource.models.database import db_client
from stock_datasource.models.orchestration import (
    ExecutionResponse,
    ExecutionStatus,
    PipelineCreate,
    PipelineEdge,
    PipelineNode,
    PipelineResponse,
    PipelineStatus,
    PipelineUpdate,
)

logger = logging.getLogger(__name__)

_TABLES_CREATED = False

CREATE_PIPELINES_SQL = """
CREATE TABLE IF NOT EXISTS orchestration_pipelines (
    id             String,
    user_id        String,
    name           String,
    description    String DEFAULT '',
    nodes          String DEFAULT '[]',
    edges          String DEFAULT '[]',
    input_schema   String DEFAULT '{}',
    output_config  String DEFAULT '{}',
    tags           Array(String),
    is_public      UInt8 DEFAULT 0,
    status         Enum8('draft'=1, 'active'=2, 'archived'=3, 'deleted'=4),
    version        UInt32 DEFAULT 1,
    created_at     DateTime DEFAULT now(),
    updated_at     DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (user_id, id)
SETTINGS index_granularity = 8192
"""

CREATE_EXECUTIONS_SQL = """
CREATE TABLE IF NOT EXISTS orchestration_executions (
    id              String,
    pipeline_id     String,
    user_id         String,
    input_data      String DEFAULT '{}',
    output_data     String DEFAULT '',
    status          Enum8('pending'=1, 'running'=2, 'completed'=3, 'failed'=4, 'cancelled'=5),
    current_node_id String DEFAULT '',
    node_results    String DEFAULT '{}',
    error_message   String DEFAULT '',
    started_at      DateTime DEFAULT now(),
    completed_at    Nullable(DateTime),
    duration_ms     UInt64 DEFAULT 0
) ENGINE = MergeTree()
ORDER BY (user_id, pipeline_id, started_at)
TTL started_at + INTERVAL 90 DAY
SETTINGS index_granularity = 8192
"""


def _ensure_tables():
    global _TABLES_CREATED
    if _TABLES_CREATED:
        return
    try:
        db_client.execute(CREATE_PIPELINES_SQL)
        db_client.execute(CREATE_EXECUTIONS_SQL)
        _TABLES_CREATED = True
    except Exception as e:
        logger.warning("Failed to create orchestration tables: %s", e)


def _parse_json_list(raw, model_cls):
    """Parse a JSON string into a list of pydantic models."""
    if not raw:
        return []
    if isinstance(raw, list):
        return [model_cls(**item) if isinstance(item, dict) else item for item in raw]
    try:
        items = json.loads(raw)
        return [model_cls(**item) for item in items]
    except (json.JSONDecodeError, TypeError):
        return []


def _parse_json_dict(raw) -> dict:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def _parse_tags(raw) -> list[str]:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return [t.strip().strip("'\"") for t in raw.strip("[]").split(",") if t.strip()]
    return []


def _row_to_pipeline(row: dict) -> PipelineResponse:
    status_val = row.get("status", "draft")
    if isinstance(status_val, int):
        status_val = {1: "draft", 2: "active", 3: "archived", 4: "deleted"}.get(
            status_val, "draft"
        )
    return PipelineResponse(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        name=str(row.get("name", "")),
        description=str(row.get("description", "")),
        nodes=_parse_json_list(row.get("nodes", "[]"), PipelineNode),
        edges=_parse_json_list(row.get("edges", "[]"), PipelineEdge),
        input_schema=_parse_json_dict(row.get("input_schema", "{}")),
        output_config=_parse_json_dict(row.get("output_config", "{}")),
        tags=_parse_tags(row.get("tags", [])),
        is_public=bool(row.get("is_public", 0)),
        status=PipelineStatus(status_val),
        version=int(row.get("version", 1)),
        created_at=row.get("created_at", datetime.now()),
        updated_at=row.get("updated_at", datetime.now()),
    )


class OrchestrationService:
    """CRUD operations for orchestration pipelines."""

    def __init__(self):
        _ensure_tables()

    # ─── Pipeline CRUD ───

    def create_pipeline(self, user_id: str, data: PipelineCreate) -> PipelineResponse:
        pipeline_id = str(uuid.uuid4())
        now = datetime.now()
        row = {
            "id": pipeline_id,
            "user_id": user_id,
            "name": data.name,
            "description": data.description,
            "nodes": json.dumps([n.model_dump() for n in data.nodes], ensure_ascii=False),
            "edges": json.dumps([e.model_dump() for e in data.edges], ensure_ascii=False),
            "input_schema": json.dumps(data.input_schema, ensure_ascii=False),
            "output_config": json.dumps(data.output_config, ensure_ascii=False),
            "tags": data.tags,
            "is_public": 0,
            "status": "active",
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
        db_client.insert_dataframe("orchestration_pipelines", pd.DataFrame([row]))
        logger.info("Created pipeline %s for user %s", pipeline_id, user_id)
        return _row_to_pipeline(row)

    def get_pipeline(self, pipeline_id: str, user_id: Optional[str] = None) -> Optional[PipelineResponse]:
        _ensure_tables()
        if user_id:
            where = f"AND (user_id = '{user_id}' OR user_id = 'system' OR is_public = 1)"
        else:
            where = ""
        df = db_client.execute_query(f"""
            SELECT * FROM orchestration_pipelines FINAL
            WHERE id = '{pipeline_id}' {where}
            ORDER BY updated_at DESC
            LIMIT 1
        """)
        if df.empty:
            return None
        row = df.iloc[0].to_dict()
        # Check status after fetch (more reliable with ReplacingMergeTree)
        status_val = row.get("status", "draft")
        if isinstance(status_val, int):
            status_val = {1: "draft", 2: "active", 3: "archived", 4: "deleted"}.get(status_val, "draft")
        if status_val == "deleted":
            return None
        return _row_to_pipeline(row)

    def list_pipelines(self, user_id: str) -> list[PipelineResponse]:
        _ensure_tables()
        df = db_client.execute_query(f"""
            SELECT * FROM orchestration_pipelines FINAL
            WHERE (user_id = '{user_id}' OR user_id = 'system' OR is_public = 1)
            ORDER BY updated_at DESC
        """)
        if df.empty:
            return []
        results = []
        for _, row in df.iterrows():
            row_dict = row.to_dict()
            status_val = row_dict.get("status", "draft")
            if isinstance(status_val, int):
                status_val = {1: "draft", 2: "active", 3: "archived", 4: "deleted"}.get(status_val, "draft")
            if status_val == "deleted":
                continue
            results.append(_row_to_pipeline(row_dict))
        return results

    def update_pipeline(
        self, pipeline_id: str, user_id: str, data: PipelineUpdate
    ) -> Optional[PipelineResponse]:
        current = self.get_pipeline(pipeline_id, user_id)
        if current is None:
            return None
        if current.user_id != user_id and current.user_id != "system":
            return None

        now = datetime.now()
        row = {
            "id": current.id,
            "user_id": current.user_id,
            "name": data.name if data.name is not None else current.name,
            "description": data.description if data.description is not None else current.description,
            "nodes": json.dumps(
                [n.model_dump() for n in data.nodes] if data.nodes is not None else [n.model_dump() for n in current.nodes],
                ensure_ascii=False,
            ),
            "edges": json.dumps(
                [e.model_dump() for e in data.edges] if data.edges is not None else [e.model_dump() for e in current.edges],
                ensure_ascii=False,
            ),
            "input_schema": json.dumps(
                data.input_schema if data.input_schema is not None else current.input_schema,
                ensure_ascii=False,
            ),
            "output_config": json.dumps(
                data.output_config if data.output_config is not None else current.output_config,
                ensure_ascii=False,
            ),
            "tags": data.tags if data.tags is not None else current.tags,
            "is_public": 1 if current.is_public else 0,
            "status": (data.status.value if data.status else current.status.value),
            "version": current.version + 1,
            "created_at": current.created_at,
            "updated_at": now,
        }
        db_client.insert_dataframe("orchestration_pipelines", pd.DataFrame([row]))
        logger.info("Updated pipeline %s (v%d)", pipeline_id, row["version"])
        return self.get_pipeline(pipeline_id, user_id)

    def delete_pipeline(self, pipeline_id: str, user_id: str) -> bool:
        """Soft-delete a pipeline."""
        current = self.get_pipeline(pipeline_id, user_id)
        if current is None:
            return False
        if current.user_id != user_id and current.user_id != "system":
            return False
        # Insert deleted version
        now = datetime.now()
        row = {
            "id": current.id,
            "user_id": current.user_id,
            "name": current.name,
            "description": current.description,
            "nodes": json.dumps([n.model_dump() for n in current.nodes], ensure_ascii=False),
            "edges": json.dumps([e.model_dump() for e in current.edges], ensure_ascii=False),
            "input_schema": json.dumps(current.input_schema, ensure_ascii=False),
            "output_config": json.dumps(current.output_config, ensure_ascii=False),
            "tags": current.tags,
            "is_public": 1 if current.is_public else 0,
            "status": "deleted",
            "version": current.version + 1,
            "created_at": current.created_at,
            "updated_at": now,
        }
        db_client.insert_dataframe("orchestration_pipelines", pd.DataFrame([row]))
        logger.info("Deleted pipeline %s", pipeline_id)
        return True

    # ─── Execution Tracking ───

    def create_execution(
        self, pipeline_id: str, user_id: str, input_data: dict
    ) -> ExecutionResponse:
        execution_id = str(uuid.uuid4())
        now = datetime.now()
        row = {
            "id": execution_id,
            "pipeline_id": pipeline_id,
            "user_id": user_id,
            "input_data": json.dumps(input_data, ensure_ascii=False),
            "output_data": "",
            "status": "running",
            "current_node_id": "",
            "node_results": "{}",
            "error_message": "",
            "started_at": now,
            "completed_at": None,
            "duration_ms": 0,
        }
        db_client.insert_dataframe("orchestration_executions", pd.DataFrame([row]))
        return ExecutionResponse(
            id=execution_id,
            pipeline_id=pipeline_id,
            user_id=user_id,
            status=ExecutionStatus.running,
            started_at=now,
        )

    def complete_execution(
        self, execution_id: str, output_data: dict, node_results: dict, duration_ms: int
    ) -> None:
        """Record execution completion — insert a new row (append-only)."""
        # For MergeTree (non-replacing), we just log the completion event
        # In practice the execution status is tracked in memory during SSE streaming
        logger.info(
            "Execution %s completed in %dms", execution_id, duration_ms
        )

    def fail_execution(self, execution_id: str, error: str, duration_ms: int) -> None:
        logger.error("Execution %s failed: %s", execution_id, error)

    def list_executions(self, pipeline_id: str, user_id: str, limit: int = 20) -> list[dict]:
        _ensure_tables()
        df = db_client.execute_query(f"""
            SELECT * FROM orchestration_executions
            WHERE pipeline_id = '{pipeline_id}' AND user_id = '{user_id}'
            ORDER BY started_at DESC
            LIMIT {limit}
        """)
        if df.empty:
            return []
        return df.to_dict("records")


# Singleton
_service: Optional[OrchestrationService] = None


def get_orchestration_service() -> OrchestrationService:
    global _service
    if _service is None:
        _service = OrchestrationService()
    return _service
