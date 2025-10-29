"""Configuration settings for stock data source."""

import os
from pathlib import Path
from pydantic import Field, ConfigDict
from pydantic_settings import BaseSettings
from typing import Optional
from dotenv import load_dotenv

# Force load .env file, overriding system environment variables
load_dotenv(override=True)


class Settings(BaseSettings):
    """Application settings."""
    
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        env_prefix=""
    )
    
    # Project settings
    PROJECT_NAME: str = "stock-datasource"
    VERSION: str = "0.1.0"
    DEBUG: bool = Field(default=False)
    
    # ClickHouse settings
    CLICKHOUSE_HOST: str = Field(default="localhost")
    CLICKHOUSE_PORT: int = Field(default=9000)
    CLICKHOUSE_USER: str = Field(default="default")
    CLICKHOUSE_PASSWORD: str = Field(default="")
    CLICKHOUSE_DATABASE: str = Field(default="stock_data")
    
    # TuShare settings
    TUSHARE_TOKEN: str = Field(default="")
    TUSHARE_RATE_LIMIT: int = Field(default=120)  # calls per minute
    TUSHARE_MAX_RETRIES: int = Field(default=3)
    
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


# Create settings instance
settings = Settings()

# Ensure directories exist
settings.DATA_DIR.mkdir(exist_ok=True)
settings.LOGS_DIR.mkdir(exist_ok=True)


def reload_settings() -> Settings:
    """Reload settings from .env file and environment variables.
    
    This function should be called when .env file is modified to ensure
    the latest configuration is loaded.
    
    Returns:
        Updated Settings instance
    """
    global settings
    settings = Settings()
    settings.DATA_DIR.mkdir(exist_ok=True)
    settings.LOGS_DIR.mkdir(exist_ok=True)
    return settings
