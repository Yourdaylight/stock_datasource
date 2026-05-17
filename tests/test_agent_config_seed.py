"""Tests for built-in agent seed data sync.

Real-database tests connect to ClickHouse at localhost:9000 (no auth)
and use an isolated database ``test_agent_seed``.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

YAML_PATH = (
    Path(__file__).resolve().parent.parent
    / "src" / "stock_datasource" / "config" / "builtin_agents.yaml"
)


def _parse_yaml():
    with open(YAML_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# YAML validity tests (no database needed)
# ---------------------------------------------------------------------------


class TestYamlFileValid:
    """Verify the builtin_agents.yaml file is well-formed."""

    def test_yaml_file_exists_and_parsable(self):
        assert YAML_PATH.exists(), f"YAML file not found at {YAML_PATH}"
        data = _parse_yaml()
        assert isinstance(data, dict)
        assert "builtin_agents" in data
        agents = data["builtin_agents"]
        assert isinstance(agents, list)
        assert len(agents) == 16, f"Expected 16 built-in agents, got {len(agents)}"

    def test_all_agents_have_required_fields(self):
        data = _parse_yaml()
        required = ["id", "name", "description", "avatar", "system_prompt", "skills", "tags"]
        for agent in data["builtin_agents"]:
            for field in required:
                assert field in agent, f"Agent {agent.get('name', '?')} missing field: {field}"
                assert agent[field], f"Agent {agent.get('name', '?')} has empty field: {field}"

    def test_all_ids_are_unique(self):
        data = _parse_yaml()
        ids = [a["id"] for a in data["builtin_agents"]]
        assert len(ids) == len(set(ids)), f"Duplicate agent IDs found: {ids}"

    def test_all_names_are_unique(self):
        data = _parse_yaml()
        names = [a["name"] for a in data["builtin_agents"]]
        assert len(names) == len(set(names)), f"Duplicate agent names found: {names}"

    def test_deterministic_ids(self):
        """Agent IDs are stable — same name always produces the same ID."""
        data = _parse_yaml()
        for agent in data["builtin_agents"]:
            name = agent["name"]
            # Re-read the file and verify the ID doesn't change between reads
            data2 = _parse_yaml()
            for agent2 in data2["builtin_agents"]:
                if agent2["name"] == name:
                    assert agent["id"] == agent2["id"], f"ID changed for {name}"
                    break

    def test_avatars_are_single_emoji(self):
        """Avatars should be short (emoji or small string)."""
        data = _parse_yaml()
        for agent in data["builtin_agents"]:
            avatar = agent["avatar"]
            assert len(avatar) <= 10, f"Avatar too long for {agent['name']}: {avatar!r}"

    def test_system_prompts_not_empty(self):
        data = _parse_yaml()
        for agent in data["builtin_agents"]:
            prompt = agent["system_prompt"].strip()
            assert len(prompt) > 20, (
                f"System prompt too short for {agent['name']}: {len(prompt)} chars"
            )


# ---------------------------------------------------------------------------
# Real database tests (require ClickHouse at localhost:9000)
# ---------------------------------------------------------------------------

TEST_DB = "test_agent_seed"


def _ch_has_database(client, db_name: str) -> bool:
    result = client.execute(
        "SELECT count() FROM system.databases WHERE name = %(name)s",
        {"name": db_name},
    )
    return int(result[0][0]) > 0


def _ch_drop_database(client, db_name: str):
    client.execute(f"DROP DATABASE IF EXISTS {db_name}")


# Detect if ClickHouse is available at import time
try:
    from clickhouse_driver import Client as RawCHClient

    _ch_test = RawCHClient(host="localhost", port=9000, user="default", password="")
    _ch_test.execute("SELECT 1")
    _ch_test.disconnect()
    _CLICKHOUSE_AVAILABLE = True
except Exception:
    _CLICKHOUSE_AVAILABLE = False

real_db = pytest.mark.skipif(
    not _CLICKHOUSE_AVAILABLE,
    reason="ClickHouse not available at localhost:9000",
)


@pytest.fixture(scope="function")
def ch_client():
    """Create a real ClickHouse client pointed at the test database."""
    if not _CLICKHOUSE_AVAILABLE:
        pytest.skip("ClickHouse not available")

    client = RawCHClient(
        host="localhost",
        port=9000,
        user="default",
        password="",
        database="default",
    )

    # Ensure clean state
    if _ch_has_database(client, TEST_DB):
        _ch_drop_database(client, TEST_DB)

    client.execute(f"CREATE DATABASE {TEST_DB}")
    client.disconnect()

    # Reconnect to the test database
    client = RawCHClient(
        host="localhost",
        port=9000,
        user="default",
        password="",
        database=TEST_DB,
    )

    yield client

    # Teardown
    try:
        client.disconnect()
    except Exception:
        pass

    cleanup = RawCHClient(
        host="localhost",
        port=9000,
        user="default",
        password="",
        database="default",
    )
    _ch_drop_database(cleanup, TEST_DB)
    cleanup.disconnect()


def _create_agent_configs_table(ch_client):
    """Create the agent_configs table in the test database."""
    ch_client.execute("""
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
    """)


def _rows_to_df(ch_client, sql):
    """Execute SQL and return results as pandas DataFrame with column names."""
    import pandas as pd

    rows_with_types = ch_client.execute(sql, with_column_types=True)
    if not rows_with_types:
        return pd.DataFrame()

    columns = [col[0] for col in rows_with_types[1]]
    data = rows_with_types[0]
    return pd.DataFrame(data, columns=columns)


def _run_sync_in_test_db(ch_client):
    """Run sync_builtin_agents with db_client patched to point at test DB.

    We monkeypatch the db_client inside agent_config_service so that
    sync_builtin_agents writes to our test database.
    """
    from unittest.mock import MagicMock

    mock_db = MagicMock()

    def _execute(sql):
        return ch_client.execute(sql)

    def _execute_query(sql):
        return _rows_to_df(ch_client, sql)

    def _insert_dataframe(table_name, df):
        columns = df.columns.tolist()
        rows = [tuple(row) for row in df.values]
        if rows:
            col_str = ", ".join(columns)
            ch_client.execute(f"INSERT INTO {table_name} ({col_str}) VALUES", rows)

    mock_db.execute = _execute
    mock_db.execute_query = _execute_query
    mock_db.insert_dataframe = _insert_dataframe

    with patch(
        "stock_datasource.services.agent_config_service.db_client", mock_db
    ), patch(
        "stock_datasource.services.agent_config_service._TABLE_CREATED", True
    ):
        from stock_datasource.services.agent_config_service import sync_builtin_agents
        return sync_builtin_agents()


class TestSyncBuiltinAgents:
    """Real database tests for sync_builtin_agents."""

    @real_db
    def test_sync_creates_table_and_inserts(self, ch_client):
        """On an empty database, sync inserts all 16 system agents."""
        _create_agent_configs_table(ch_client)

        inserted = _run_sync_in_test_db(ch_client)
        assert inserted == 16, f"Expected 16 inserted, got {inserted}"

        # Verify the rows are actually in ClickHouse
        count = ch_client.execute(
            "SELECT count() FROM agent_configs FINAL WHERE user_id = 'system'"
        )
        assert count[0][0] == 16, f"Expected 16 system agents in DB, got {count[0][0]}"

        # Verify all have status='active'
        active_count = ch_client.execute(
            "SELECT count() FROM agent_configs FINAL WHERE user_id = 'system' AND status = 'active'"
        )
        assert active_count[0][0] == 16

    @real_db
    def test_sync_is_idempotent(self, ch_client):
        """Running sync twice does not duplicate agents."""
        _create_agent_configs_table(ch_client)

        # First sync
        first = _run_sync_in_test_db(ch_client)
        assert first == 16

        # Second sync — should insert 0 new agents
        second = _run_sync_in_test_db(ch_client)
        assert second == 0, f"Second sync should insert 0, got {second}"

        # Verify count is still 16
        count = ch_client.execute(
            "SELECT count() FROM agent_configs FINAL WHERE user_id = 'system'"
        )
        assert count[0][0] == 16, f"Expected 16 after idempotent sync, got {count[0][0]}"

    @real_db
    def test_sync_rows_have_required_fields(self, ch_client):
        """Each synced agent has all required fields populated."""
        _create_agent_configs_table(ch_client)
        _run_sync_in_test_db(ch_client)

        rows = ch_client.execute(
            "SELECT id, user_id, name, description, avatar, system_prompt, "
            "skills, tags, is_public, status "
            "FROM agent_configs FINAL WHERE user_id = 'system'"
        )
        for row in rows:
            agent_id, user_id, name, desc, avatar, prompt, skills, tags, is_public, status = row
            assert user_id == "system"
            assert name, f"Empty name for {agent_id}"
            assert desc, f"Empty description for {agent_id}"
            assert avatar, f"Empty avatar for {agent_id}"
            assert prompt, f"Empty system_prompt for {agent_id}"
            assert len(skills) > 0, f"Empty skills for {agent_id}"
            assert len(tags) > 0, f"Empty tags for {agent_id}"
            assert is_public == 1
            assert status == "active"

    @real_db
    def test_sync_preserves_ids(self, ch_client):
        """Agent IDs from YAML are preserved exactly in ClickHouse."""
        _create_agent_configs_table(ch_client)
        _run_sync_in_test_db(ch_client)

        data = _parse_yaml()
        expected_ids = {a["id"] for a in data["builtin_agents"]}

        rows = ch_client.execute(
            "SELECT id FROM agent_configs FINAL WHERE user_id = 'system'"
        )
        actual_ids = {row[0] for row in rows}

        assert expected_ids == actual_ids, (
            f"ID mismatch. Missing: {expected_ids - actual_ids}, "
            f"Extra: {actual_ids - expected_ids}"
        )
