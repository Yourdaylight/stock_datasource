"""Knowledge Sync Service — sync ClickHouse data to WeKnora knowledge base.

This service is **decoupled from plugins**. It queries ClickHouse tables
directly via ``db_client`` and renders the results as Markdown documents,
then pushes them to WeKnora via the REST API.
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from stock_datasource.models.database import db_client
from stock_datasource.services.weknora_client import get_weknora_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sync task status tracking (in-memory, lightweight)
# ---------------------------------------------------------------------------

class SyncTaskStatus:
    """Track the progress of a single sync task."""

    def __init__(self, task_id: str, table_name: str, kb_id: str, total: int = 0):
        self.task_id = task_id
        self.table_name = table_name
        self.kb_id = kb_id
        self.status = "pending"  # pending | running | completed | failed
        self.total = total
        self.completed = 0
        self.failed = 0
        self.error: Optional[str] = None
        self.created_at = datetime.now().isoformat()
        self.started_at: Optional[str] = None
        self.finished_at: Optional[str] = None
        self.documents: List[Dict[str, Any]] = []  # created doc summaries

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "table_name": self.table_name,
            "kb_id": self.kb_id,
            "status": self.status,
            "total": self.total,
            "completed": self.completed,
            "failed": self.failed,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "documents": self.documents,
        }


# Keep recent task history (max 100 entries)
_sync_tasks: Dict[str, SyncTaskStatus] = {}
_MAX_TASKS = 100


def _trim_tasks() -> None:
    global _sync_tasks
    if len(_sync_tasks) > _MAX_TASKS:
        sorted_keys = sorted(_sync_tasks, key=lambda k: _sync_tasks[k].created_at)
        for k in sorted_keys[: len(sorted_keys) - _MAX_TASKS]:
            del _sync_tasks[k]


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

def _dataframe_to_markdown(df: pd.DataFrame, title: str, table_name: str) -> str:
    """Render a DataFrame as a readable Markdown document."""
    # Replace NaN/Inf with empty string for safe serialisation
    df = df.copy()
    df = df.fillna("")
    for col in df.select_dtypes(include=["float", "number"]).columns:
        df[col] = df[col].replace([float("inf"), float("-inf")], "")

    lines: List[str] = []
    lines.append(f"# {title}\n")
    lines.append(f"- **数据表**: `{table_name}`")
    lines.append(f"- **记录数**: {len(df)}")
    lines.append(f"- **同步时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    if df.empty:
        lines.append("*（无数据）*")
        return "\n".join(lines)

    # Summary statistics for numeric columns
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    if numeric_cols:
        lines.append("## 数据摘要\n")
        try:
            summary = df[numeric_cols].describe().round(4)
            lines.append(summary.to_markdown())
        except Exception:
            pass
        lines.append("")

    # Data table (limit to 200 rows to avoid huge documents)
    lines.append("## 数据明细\n")
    display_df = df.head(200)
    lines.append(display_df.to_markdown(index=False))
    if len(df) > 200:
        lines.append(f"\n> 仅显示前 200 条，共 {len(df)} 条记录。")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Core sync logic
# ---------------------------------------------------------------------------

class KnowledgeSyncService:
    """Sync ClickHouse query results to WeKnora knowledge base."""

    def __init__(self) -> None:
        self.logger = logger

    # -- helpers -----------------------------------------------------------

    def list_tables(self) -> List[Dict[str, str]]:
        """List all user tables in the current ClickHouse database."""
        try:
            sql = (
                "SELECT name, comment FROM system.tables "
                "WHERE database = currentDatabase() "
                "AND engine NOT IN ('MaterializedView', 'View') "
                "ORDER BY name"
            )
            df = db_client.execute_query(sql)
            if df is None or df.empty:
                return []
            # Ensure NaN/None are replaced with empty strings for JSON safety
            df = df.fillna("")
            return [
                {"table_name": str(row["name"]), "comment": str(row.get("comment", ""))}
                for _, row in df.iterrows()
            ]
        except Exception as e:
            self.logger.warning(f"list_tables failed: {e}")
            return []

    def get_table_columns(self, table_name: str) -> List[Dict[str, str]]:
        """Get column info for a table."""
        try:
            sql = (
                "SELECT name, type, comment FROM system.columns "
                "WHERE database = currentDatabase() AND table = %(table)s "
                "ORDER BY position"
            )
            df = db_client.execute_query(sql, params={"table": table_name})
            if df is None or df.empty:
                return []
            return [
                {"name": row["name"], "type": row["type"], "comment": row.get("comment", "")}
                for _, row in df.iterrows()
            ]
        except Exception as e:
            self.logger.warning(f"get_table_columns({table_name}) failed: {e}")
            return []

    def _query_data(self, sql: str, max_rows: int = 5000) -> Optional[pd.DataFrame]:
        """Execute a read-only query and return a DataFrame."""
        # Basic safety: only allow SELECT
        stripped = sql.strip().upper()
        if not stripped.startswith("SELECT"):
            raise ValueError("只允许 SELECT 查询")

        try:
            df = db_client.execute_query(sql)
            if df is not None and len(df) > max_rows:
                df = df.head(max_rows)
            return df
        except Exception as e:
            self.logger.error(f"_query_data failed: {e}")
            raise

    def _build_query(
        self,
        table_name: str,
        ts_codes: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 5000,
    ) -> str:
        """Build a simple SELECT query from filters."""
        conditions: List[str] = []

        if ts_codes:
            escaped = ", ".join(f"'{c.replace(chr(39), '')}'" for c in ts_codes)
            conditions.append(f"ts_code IN ({escaped})")

        if start_date:
            conditions.append(f"end_date >= '{start_date.replace(chr(39), '')}'")
        if end_date:
            conditions.append(f"end_date <= '{end_date.replace(chr(39), '')}'")

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        return f"SELECT * FROM {table_name}{where} LIMIT {limit}"

    def _generate_title(
        self,
        table_name: str,
        ts_codes: Optional[List[str]] = None,
        date_range: Optional[str] = None,
        custom_title: Optional[str] = None,
    ) -> str:
        if custom_title:
            return custom_title
        parts = [table_name]
        if ts_codes:
            codes_str = ",".join(ts_codes[:3])
            if len(ts_codes) > 3:
                codes_str += f"等{len(ts_codes)}只"
            parts.append(codes_str)
        if date_range:
            parts.append(date_range)
        return "-".join(parts)

    # -- public sync methods -----------------------------------------------

    def _sync_table_impl(
        self,
        kb_id: str,
        table_name: str,
        task: "SyncTaskStatus",
        ts_codes: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        custom_sql: Optional[str] = None,
        custom_title: Optional[str] = None,
        max_rows: int = 5000,
    ) -> None:
        """Synchronous implementation — runs in a thread."""
        client = get_weknora_client()
        if client is None:
            task.status = "failed"
            task.error = "WeKnora 客户端未初始化（请检查配置）"
            task.finished_at = datetime.now().isoformat()
            return

        task.status = "running"
        task.started_at = datetime.now().isoformat()

        try:
            # 1. Query data
            if custom_sql:
                sql = custom_sql
            else:
                sql = self._build_query(table_name, ts_codes, start_date, end_date, limit=max_rows)

            self.logger.info(f"[KnowledgeSync] task={task.task_id} sql={sql[:200]}")
            df = self._query_data(sql, max_rows)

            if df is None or df.empty:
                task.status = "completed"
                task.total = 0
                task.finished_at = datetime.now().isoformat()
                return

            # 2. Determine how to chunk: group by ts_code if present, else one doc
            if "ts_code" in df.columns and ts_codes and len(ts_codes) > 1:
                groups = list(df.groupby("ts_code"))
            else:
                date_range = ""
                if start_date or end_date:
                    date_range = f"{start_date or ''}~{end_date or ''}"
                title = self._generate_title(table_name, ts_codes, date_range, custom_title)
                groups = [(title, df)]

            task.total = len(groups)

            # 3. Push each group as a document
            for group_key, group_df in groups:
                if isinstance(group_key, str):
                    title = group_key
                else:
                    date_range = ""
                    if start_date or end_date:
                        date_range = f"{start_date or ''}~{end_date or ''}"
                    title = self._generate_title(table_name, [str(group_key)], date_range, custom_title)

                content = _dataframe_to_markdown(group_df, title, table_name)

                # Check if document with same title exists (for update)
                existing = self._find_existing_doc(client, kb_id, title)

                if existing:
                    result = client.update_manual_knowledge(
                        knowledge_id=existing["id"],
                        title=title,
                        content=content,
                        status="publish",
                    )
                    action = "updated"
                else:
                    result = client.create_manual_knowledge(
                        kb_id=kb_id,
                        title=title,
                        content=content,
                        status="publish",
                    )
                    action = "created"

                if result:
                    task.completed += 1
                    task.documents.append({
                        "title": title,
                        "knowledge_id": result.get("id", ""),
                        "action": action,
                        "rows": len(group_df),
                    })
                else:
                    task.failed += 1

            task.status = "completed"
            task.finished_at = datetime.now().isoformat()
            self.logger.info(
                f"[KnowledgeSync] task={task.task_id} done: "
                f"{task.completed} created/updated, {task.failed} failed"
            )

        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            task.finished_at = datetime.now().isoformat()
            self.logger.error(f"[KnowledgeSync] task={task.task_id} error: {e}")

    async def sync_table(
        self,
        kb_id: str,
        table_name: str,
        ts_codes: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        custom_sql: Optional[str] = None,
        custom_title: Optional[str] = None,
        max_rows: int = 5000,
    ) -> SyncTaskStatus:
        """Sync data from a ClickHouse table (or custom SQL) to WeKnora.

        The entire sync (ClickHouse query + WeKnora HTTP calls) runs in a
        thread to avoid event-loop interference from the ClickHouse driver.
        """
        task_id = str(uuid.uuid4())
        task = SyncTaskStatus(task_id=task_id, table_name=table_name, kb_id=kb_id)
        _sync_tasks[task_id] = task
        _trim_tasks()

        await asyncio.to_thread(
            self._sync_table_impl,
            kb_id, table_name, task,
            ts_codes, start_date, end_date,
            custom_sql, custom_title, max_rows,
        )

        return task

    def _find_existing_doc(
        self, client: Any, kb_id: str, title: str
    ) -> Optional[dict]:
        """Search for an existing knowledge document by title (exact match)."""
        try:
            result = client.list_knowledges(kb_id, page=1, page_size=50, keyword=title)
            for doc in result.get("data", []):
                if doc.get("title") == title:
                    return doc
        except Exception as e:
            self.logger.debug(f"_find_existing_doc({title}) failed: {type(e).__name__}: {e}")
        return None

    # -- status / history --------------------------------------------------

    def get_task(self, task_id: str) -> Optional[SyncTaskStatus]:
        return _sync_tasks.get(task_id)

    def get_current_task(self) -> Optional[SyncTaskStatus]:
        """Get the currently running task, if any."""
        for t in _sync_tasks.values():
            if t.status == "running":
                return t
        return None

    def get_history(self, limit: int = 20) -> List[dict]:
        """Return recent sync tasks ordered by created_at desc."""
        tasks = sorted(_sync_tasks.values(), key=lambda t: t.created_at, reverse=True)
        return [t.to_dict() for t in tasks[:limit]]


# Singleton
knowledge_sync_service = KnowledgeSyncService()
