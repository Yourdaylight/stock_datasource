"""Shared test configuration.

Pre-mocks the entire stock_datasource package tree to avoid triggering
database connections, file logging, and other heavy imports during tests.
Individual test files then import specific modules they need.
"""

import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import MagicMock

_test_log_dir = Path(tempfile.mkdtemp(prefix="sd_test_logs_"))
_src_dir = Path(__file__).parent.parent / "src"


def _make_module(name, is_pkg=False):
    """Create a mock module and register it in sys.modules."""
    mod = types.ModuleType(name)
    if is_pkg:
        mod.__path__ = [str(_src_dir / name.replace(".", "/"))]
    sys.modules[name] = mod
    return mod


def pytest_configure(config):
    """Pre-mock the stock_datasource package tree."""
    if "stock_datasource" in sys.modules:
        return

    # --- settings ---
    class _S:
        LOGS_DIR = _test_log_dir
        LOG_LEVEL = "WARNING"
        BASE_DIR = _src_dir / "stock_datasource"
        DEBUG = False
        MCP_JWT_PUBLIC_KEY_PATH = None
        MCP_USAGE_REPORT_KEY = None
        CLICKHOUSE_HOST = "localhost"
        CLICKHOUSE_PORT = 9000
        CLICKHOUSE_DATABASE = "test"
        CLICKHOUSE_USER = "test"
        CLICKHOUSE_PASSWORD = ""
        CLICKHOUSE_BACKUP_HOST = ""
        CLICKHOUSE_BACKUP_PORT = 9000
        BACKUP_CLICKHOUSE_HOST = ""
        BACKUP_CLICKHOUSE_PORT = 9000
        BACKUP_CLICKHOUSE_USER = ""
        BACKUP_CLICKHOUSE_PASSWORD = ""
        BACKUP_CLICKHOUSE_DATABASE = ""
        AUTH_ADMIN_EMAILS = []

    settings_obj = _S()

    # Top-level package — we need a REAL import, not a mock, so that
    # sub-packages under stock_datasource.modules resolve correctly.
    # But we need to prevent __init__.py from running its heavy imports.
    # Strategy: create the package module manually, set __path__, and
    # skip the __init__.py entirely.
    sd = _make_module("stock_datasource", is_pkg=True)

    # config
    cfg = _make_module("stock_datasource.config", is_pkg=True)
    cfg_settings = _make_module("stock_datasource.config.settings")
    cfg_settings.settings = settings_obj
    cfg_settings.Settings = type(settings_obj)
    cfg_settings.Optional = None  # in case anything references it

    # config.runtime_config
    _make_module("stock_datasource.config.runtime_config")

    # models
    mock_db_client = MagicMock(name="db_client")
    models = _make_module("stock_datasource.models", is_pkg=True)
    models.db_client = mock_db_client
    db_mod = _make_module("stock_datasource.models.database")
    db_mod.db_client = mock_db_client
    _make_module("stock_datasource.models.schemas")

    # utils
    mock_logger = MagicMock()
    utils = _make_module("stock_datasource.utils", is_pkg=True)
    logger_mod = _make_module("stock_datasource.utils.logger")
    logger_mod.logger = mock_logger
    logger_mod.setup_logging = lambda: mock_logger
    _make_module("stock_datasource.utils.extractor")

    # core
    core = _make_module("stock_datasource.core", is_pkg=True)
    bs = _make_module("stock_datasource.core.base_service")
    bs.BaseService = type("BaseService", (), {})
    bs.db_client = mock_db_client
    sg = _make_module("stock_datasource.core.service_generator")
    sg.ServiceGenerator = MagicMock

    # services (mock the heavy sub-modules)
    services = _make_module("stock_datasource.services", is_pkg=True)
    _make_module("stock_datasource.services.ingestion")
    # mcp_server is real — we'll let it import naturally
    # http_server mock
    _make_module("stock_datasource.services.http_server")

    # modules (real package — needs __path__ to resolve sub-packages)
    modules = _make_module("stock_datasource.modules", is_pkg=True)

    # modules.mcp_api_key (real package for jwt_verifier)
    mcp_api_key = _make_module("stock_datasource.modules.mcp_api_key", is_pkg=True)

    # modules.auth (mock)
    _make_module("stock_datasource.modules.auth", is_pkg=True)
    _make_module("stock_datasource.modules.auth.service")

    # plugins (mock)
    _make_module("stock_datasource.plugins", is_pkg=True)

    _test_log_dir.mkdir(parents=True, exist_ok=True)


def pytest_unconfigure(config):
    import shutil
    try:
        shutil.rmtree(_test_log_dir, ignore_errors=True)
    except Exception:
        pass
