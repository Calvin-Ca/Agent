"""Centralized configuration — all settings parsed from environment variables."""

from __future__ import annotations # 避免 定义相互引用的类时 因 类型注解而报错

from functools import lru_cache # 给函数加缓存层，相同参数再次调用时，会直接返回缓存结果，避免重复计算，提高速度
from pathlib import Path

# BaseSettings 配置类基类，用于定义应用配置项：环境变量、.env 文件等，可自动校验类型并填充默认值
# SettingsConfigDict给配置类提供"运行时规则"，例如控制 BaseSettings 的加载和解析行为
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.  Reads from .env file automatically."""

    model_config = SettingsConfigDict(  # model_config 是特殊的类变量，用于配置模型行为。
        env_file=".env",  # 指定 .env 文件路径
        env_file_encoding="utf-8",  # 指定 .env 编码
        case_sensitive=False,   # 环境变量名大小写不敏感
        extra="ignore", # 如果 .env 或环境变量里有多余配置，不会报错
    )

    # 自动从环境变量或.env文件中加载下列字段，没有则使用默认值
    # ── App ──────────────────────────────────────────────────
    app_name: str = "agent"
    app_env: str = "development"
    debug: bool = True
    secret_key: str = "change-me-to-a-random-64-char-string"
    api_v1_prefix: str = "/api/v1"

    # ── MySQL ────────────────────────────────────────────────
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "report_user"
    mysql_password: str = "report_pass_123"
    mysql_database: str = "weekly_report"

    @property
    def mysql_dsn(self) -> str: # DSN(Data Source Name)在数据库连接中，它是一个字符串，包含连接所须的所有信息：协议（mysql+aiomysql）、用户名和密码、主机和端口、数据库名
        return (
            f"mysql+aiomysql://{self.mysql_user}:{self.mysql_password}" # 使用 aiomysql 异步驱动
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            "?charset=utf8mb4" # 参数，指定 UTF-8 字符集
        )

    @property
    def mysql_dsn_sync(self) -> str:
        """Sync DSN for Alembic migrations.""" # 数据库迁移工具，帮助管理数据库 schema 的版本控制
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}" # 使用 pymysql 同步驱动
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            "?charset=utf8mb4"
        )

    # ── Redis ────────────────────────────────────────────────
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0

    # 配置 Redis 客户端连接
    @property
    def redis_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # ── Milvus ───────────────────────────────────────────────
    milvus_host: str = "127.0.0.1"
    milvus_port: int = 19530
    milvus_collection: str = "doc_embeddings"
    milvus_dim: int = 1024  # BGE-large-zh output dim

    # ── 模型服务 — ollama | api(vLLM) ──────────────────────────
    backend: str = "vllm"  # 统一后端选择: vllm | ollama
    llm_max_tokens: int = 2048

    # Ollama
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_llm_model: str = "qwen3-8b"
    ollama_embed_model: str = "bge-large"
    ollama_vlm_model: str = "llava"

    # vLLM API
    llm_api_base: str = "http://127.0.0.1:8099/v1"
    llm_api_key: str = ""
    llm_model_name: str = "/model"
    embed_api_base: str = "http://127.0.0.1:8097/v1"
    embed_model_name: str = "/model"

    # VLM（可选）
    vlm_enabled: bool = False
    vlm_model_name: str = ""

    # ── PaddleOCR Server ─────────────────────────────────────
    paddleocr_api_url: str = ""  # e.g. http://127.0.0.1:8868/predict/ocr_system; empty = disabled

    # ── MinIO ────────────────────────────────────────────────
    minio_endpoint: str = "127.0.0.1:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "weekly-report"
    minio_secure: bool = False

    # ── Celery ───────────────────────────────────────────────
    # FastAPI只能解决请求在 I/O 等待时不要阻塞线程，
    # 但Celery可以解决长时间CPU的重任：PDF解析向量化、embedding模型推理（大模型）、RAG构建、视频处理
    # Celery 需要一个"消息队列"，最常用的是：redis
    celery_broker_url: str = "redis://127.0.0.1:6379/1"
    celery_result_backend: str = "redis://127.0.0.1:6379/2"

    # ── JWT ──────────────────────────────────────────────────
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 hours # 设置 JWT 令牌的过期时间

    # ── Paths ────────────────────────────────────────────────
    @property
    def upload_dir(self) -> Path:
        p = Path("./storage/uploads")
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def export_dir(self) -> Path:
        p = Path("./storage/exports")
        p.mkdir(parents=True, exist_ok=True)
        return p

# 第一次调用后缓存实例，由于缓存，实际只创建一次，确保全局唯一，实现了单例模式，确保应用中只有一个配置实例。
@lru_cache
def get_settings() -> Settings:
    """Singleton settings instance, cached after first call."""
    return Settings()
