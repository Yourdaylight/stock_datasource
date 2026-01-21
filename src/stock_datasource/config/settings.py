"""Configuration settings for stock data source."""

import os
from pathlib import Path
from pydantic import Field, ConfigDict, field_validator
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings."""
    
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # Project settings
    PROJECT_NAME: str = "stock-datasource"
    VERSION: str = "0.1.0"
    DEBUG: bool = Field(default=False)
    
    @field_validator('DEBUG', mode='before')
    @classmethod
    def parse_debug(cls, v):
        """Parse DEBUG value, handle non-boolean values gracefully."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ('true', '1', 'yes', 'on')
        return False
    
    # ClickHouse settings (Primary)
    CLICKHOUSE_HOST: str = Field(default="localhost")
    CLICKHOUSE_PORT: int = Field(default=9000)
    CLICKHOUSE_USER: str = Field(default="default")
    CLICKHOUSE_PASSWORD: str = Field(default="")
    CLICKHOUSE_DATABASE: str = Field(default="stock_data")
    
    # Backup ClickHouse settings (Optional - for dual write)
    BACKUP_CLICKHOUSE_HOST: Optional[str] = Field(default=None)
    BACKUP_CLICKHOUSE_PORT: int = Field(default=9000)
    BACKUP_CLICKHOUSE_USER: str = Field(default="default")
    BACKUP_CLICKHOUSE_PASSWORD: str = Field(default="")
    BACKUP_CLICKHOUSE_DATABASE: str = Field(default="stock_datasource")
    
    # TuShare settings
    TUSHARE_TOKEN: str = Field(default="")
    TUSHARE_RATE_LIMIT: int = Field(default=120)  # calls per minute
    TUSHARE_MAX_RETRIES: int = Field(default=3)
    
    # HTTP Proxy settings
    HTTP_PROXY_ENABLED: bool = Field(default=False)
    HTTP_PROXY_HOST: str = Field(default="")
    HTTP_PROXY_PORT: int = Field(default=0)
    HTTP_PROXY_USERNAME: Optional[str] = Field(default=None)
    HTTP_PROXY_PASSWORD: Optional[str] = Field(default=None)
    
    @property
    def http_proxy_url(self) -> Optional[str]:
        """Get formatted HTTP proxy URL."""
        if not self.HTTP_PROXY_ENABLED or not self.HTTP_PROXY_HOST or not self.HTTP_PROXY_PORT:
            return None
        
        if self.HTTP_PROXY_USERNAME and self.HTTP_PROXY_PASSWORD:
            # URL encode the password to handle special characters
            from urllib.parse import quote
            encoded_password = quote(self.HTTP_PROXY_PASSWORD, safe='')
            return f"http://{self.HTTP_PROXY_USERNAME}:{encoded_password}@{self.HTTP_PROXY_HOST}:{self.HTTP_PROXY_PORT}"
        else:
            return f"http://{self.HTTP_PROXY_HOST}:{self.HTTP_PROXY_PORT}"
    
    @property
    def proxy_dict(self) -> Optional[dict]:
        """Get proxy dict for requests library."""
        proxy_url = self.http_proxy_url
        if proxy_url:
            return {
                "http": proxy_url,
                "https": proxy_url
            }
        return None
    
    # Airflow settings
    AIRFLOW_HOME: str = Field(default="/opt/airflow")
    
    # Data settings
    DATA_START_DATE: str = Field(default="2020-01-01")
    DAILY_UPDATE_TIME: str = Field(default="18:00")
    TIMEZONE: str = Field(default="Asia/Shanghai")
    
    # File paths
    BASE_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    LOGS_DIR: Path = BASE_DIR / "logs"
    SQL_DIR: Path = BASE_DIR / "src" / "stock_datasource" / "sql"
    
    # Logging
    LOG_LEVEL: str = Field(default="INFO")
    
    # Database settings
    DATABASE_URL: Optional[str] = Field(default=None)
    
    # LLM / AI settings
    OPENAI_API_KEY: Optional[str] = Field(default=None)
    OPENAI_BASE_URL: str = Field(default="https://api.openai.com/v1")
    OPENAI_MODEL: str = Field(default="gpt-4")
    
    # Langfuse settings (AI Observability)
    LANGFUSE_PUBLIC_KEY: Optional[str] = Field(default=None)
    LANGFUSE_SECRET_KEY: Optional[str] = Field(default=None)
    LANGFUSE_HOST: str = Field(default="https://cloud.langfuse.com")
    LANGFUSE_ENABLED: bool = Field(default=True)
    
    # Redis settings (for caching)
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    REDIS_PASSWORD: Optional[str] = Field(default=None)
    REDIS_DB: int = Field(default=1)  # Use DB 1 to isolate from Langfuse (DB 0)
    REDIS_ENABLED: bool = Field(default=True)
    
    # Cache TTL settings (seconds)
    CACHE_TTL_QUOTE: int = Field(default=60)       # Real-time quotes
    CACHE_TTL_DAILY: int = Field(default=86400)    # Daily K-line data
    CACHE_TTL_BASIC: int = Field(default=3600)     # Stock basic info
    CACHE_TTL_OVERVIEW: int = Field(default=300)   # Market overview

    # Auth / Registration
    # Default: no email whitelist check (open registration)
    AUTH_EMAIL_WHITELIST_ENABLED: bool = Field(default=False)
    # Whitelist file path. Recommended for docker: "data/email.txt" (data dir is mounted).
    AUTH_EMAIL_WHITELIST_FILE: str = Field(default="data/email.txt")
    # Admin email list (comma-separated), these users will have is_admin=True
    AUTH_ADMIN_EMAILS: str = Field(default="")


# Create settings instance
settings = Settings()

# Apply runtime persisted config (proxy/concurrency overrides)
try:
    from .runtime_config import load_runtime_config

    _runtime_cfg = load_runtime_config()
    _proxy_cfg = _runtime_cfg.get("proxy", {})
    settings.HTTP_PROXY_ENABLED = _proxy_cfg.get("enabled", settings.HTTP_PROXY_ENABLED)
    settings.HTTP_PROXY_HOST = _proxy_cfg.get("host", settings.HTTP_PROXY_HOST)
    settings.HTTP_PROXY_PORT = _proxy_cfg.get("port", settings.HTTP_PROXY_PORT)
    settings.HTTP_PROXY_USERNAME = _proxy_cfg.get("username", settings.HTTP_PROXY_USERNAME)
    settings.HTTP_PROXY_PASSWORD = _proxy_cfg.get("password", settings.HTTP_PROXY_PASSWORD)
except Exception:
    # Fallback to env-only configuration on any error
    pass

# Ensure directories exist
settings.DATA_DIR.mkdir(exist_ok=True)
settings.LOGS_DIR.mkdir(exist_ok=True)

# Patch TuShare to use HTTPS instead of HTTP
# This is necessary because some proxies block HTTP POST requests but allow HTTPS
def _patch_tushare_https():
    """Patch TuShare client to use HTTPS URL."""
    try:
        import tushare.pro.client as tushare_client
        if hasattr(tushare_client, 'DataApi'):
            # Change from http:// to https://
            original_url = getattr(tushare_client.DataApi, '_DataApi__http_url', None)
            if original_url and original_url.startswith('http://'):
                tushare_client.DataApi._DataApi__http_url = original_url.replace('http://', 'https://', 1)
    except Exception:
        pass

_patch_tushare_https()
