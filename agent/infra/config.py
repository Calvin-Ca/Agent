"""Centralized configuration for the refactored agent platform."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Application settings loaded from environment variables and .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "agent"
    app_env: str = "development"
    debug: bool = True
    secret_key: str = "change-me-to-a-random-64-char-string"
    api_v1_prefix: str = "/api/v1"

    database_backend: str = "mysql"
    database_url: str = ""
    database_url_sync: str = ""
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "report_user"
    mysql_password: str = "report_pass_123"
    mysql_database: str = "weekly_report"

    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_database: str = "agent_platform"

    @property
    def mysql_dsn(self) -> str:
        return (
            f"mysql+aiomysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            "?charset=utf8mb4"
        )

    @property
    def mysql_dsn_sync(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            "?charset=utf8mb4"
        )

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_database}"
        )

    @property
    def postgres_dsn_sync(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_database}"
        )

    @property
    def sqlalchemy_dsn(self) -> str:
        if self.database_url:
            return self.database_url
        if self.database_backend.lower() == "postgres":
            return self.postgres_dsn
        return self.mysql_dsn

    @property
    def sqlalchemy_dsn_sync(self) -> str:
        if self.database_url_sync:
            return self.database_url_sync
        if self.database_backend.lower() == "postgres":
            return self.postgres_dsn_sync
        return self.mysql_dsn_sync

    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0

    @property
    def redis_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    milvus_host: str = "127.0.0.1"
    milvus_port: int = 19530
    milvus_collection: str = "doc_embeddings"
    milvus_dim: int = 1024

    backend: str = "vllm"
    llm_max_tokens: int = 2048

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_llm_model: str = "qwen3-8b"
    ollama_embed_model: str = "bge-large"
    ollama_vlm_model: str = "llava"

    llm_api_base: str = "http://127.0.0.1:8099/v1"
    llm_api_key: str = ""
    llm_model_name: str = "/model"
    embed_api_base: str = "http://127.0.0.1:8097/v1"
    embed_model_name: str = "/model"

    vlm_enabled: bool = False
    vlm_model_name: str = ""
    paddleocr_api_url: str = ""

    minio_endpoint: str = "127.0.0.1:19000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "weekly-report"
    minio_secure: bool = False

    celery_broker_url: str = "redis://127.0.0.1:6379/1"
    celery_result_backend: str = "redis://127.0.0.1:6379/2"

    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    @property
    def upload_dir(self) -> Path:
        path = Path("./storage/uploads")
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def export_dir(self) -> Path:
        path = Path("./storage/exports")
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> AppSettings:
    """Return the singleton settings instance."""
    return AppSettings()
