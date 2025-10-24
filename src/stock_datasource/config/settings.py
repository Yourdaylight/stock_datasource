"""Configuration settings for stock data source."""

import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Application settings."""
    
    # Project settings
    PROJECT_NAME: str = "stock-datasource"
    VERSION: str = "0.1.0"
    DEBUG: bool = Field(default=False, env="DEBUG")
    
    # ClickHouse settings
    CLICKHOUSE_HOST: str = Field(default="localhost", env="CLICKHOUSE_HOST")
    CLICKHOUSE_PORT: int = Field(default=9000, env="CLICKHOUSE_PORT")
    CLICKHOUSE_USER: str = Field(default="default", env="CLICKHOUSE_USER")
    CLICKHOUSE_PASSWORD: str = Field(default="", env="CLICKHOUSE_PASSWORD")
    CLICKHOUSE_DATABASE: str = Field(default="stock_data", env="CLICKHOUSE_DATABASE")
    
    # TuShare settings
    TUSHARE_TOKEN: str = Field(env="TUSHARE_TOKEN")
    TUSHARE_RATE_LIMIT: int = Field(default=120, env="TUSHARE_RATE_LIMIT")  # calls per minute
    TUSHARE_MAX_RETRIES: int = Field(default=3, env="TUSHARE_MAX_RETRIES")
    
    # Airflow settings
    AIRFLOW_HOME: str = Field(default="/opt/airflow", env="AIRFLOW_HOME")
    
    # Data settings
    DATA_START_DATE: str = Field(default="2020-01-01", env="DATA_START_DATE")
    DAILY_UPDATE_TIME: str = Field(default="18:00", env="DAILY_UPDATE_TIME")
    TIMEZONE: str = Field(default="Asia/Shanghai", env="TIMEZONE")
    
    # File paths
    BASE_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    LOGS_DIR: Path = BASE_DIR / "logs"
    SQL_DIR: Path = BASE_DIR / "src" / "stock_datasource" / "sql"
    
    # Logging
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    
    # Database settings
    DATABASE_URL: Optional[str] = Field(default=None, env="DATABASE_URL")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Create settings instance
settings = Settings()

# Ensure directories exist
settings.DATA_DIR.mkdir(exist_ok=True)
settings.LOGS_DIR.mkdir(exist_ok=True)
