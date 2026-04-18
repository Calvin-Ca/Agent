"""MinIO client — upload / download helpers."""

from __future__ import annotations

import asyncio
from io import BytesIO

from minio import Minio
from loguru import logger

from app.config import get_settings

_client: Minio | None = None


def _get_client() -> Minio:
    global _client
    if _client is None:
        s = get_settings()
        _client = Minio(
            s.minio_endpoint,
            access_key=s.minio_access_key,
            secret_key=s.minio_secret_key,
            secure=s.minio_secure,
        )
        logger.info("MinIO client initialized: {}", s.minio_endpoint)
    return _client


def _ensure_bucket(bucket: str) -> None:
    client = _get_client()
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        logger.info("Created MinIO bucket: {}", bucket)


def _sync_upload(bucket: str, key: str, data: bytes, content_type: str) -> None:
    _ensure_bucket(bucket)
    _get_client().put_object(bucket, key, BytesIO(data), len(data), content_type=content_type)


def _sync_download(bucket: str, key: str) -> bytes:
    response = _get_client().get_object(bucket, key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


async def upload_file(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Upload bytes to MinIO. Returns the object key."""
    bucket = get_settings().minio_bucket
    await asyncio.to_thread(_sync_upload, bucket, key, data, content_type)
    logger.info("Uploaded to MinIO: {}/{}", bucket, key)
    return key


async def download_file(key: str) -> bytes:
    """Download object from MinIO and return raw bytes."""
    bucket = get_settings().minio_bucket
    return await asyncio.to_thread(_sync_download, bucket, key)


def sync_download_file(key: str) -> bytes:
    """Sync version for use inside Celery tasks."""
    bucket = get_settings().minio_bucket
    return _sync_download(bucket, key)


def list_objects(prefix: str = "", recursive: bool = True) -> list:
    """List objects in the default bucket under the given prefix."""
    bucket = get_settings().minio_bucket
    return list(_get_client().list_objects(bucket, prefix=prefix, recursive=recursive))


def presigned_get_url(key: str, expires_seconds: int = 3600) -> str:
    """Generate a presigned GET URL (default 1 hour) for the given object key."""
    from datetime import timedelta
    bucket = get_settings().minio_bucket
    return _get_client().presigned_get_object(bucket, key, expires=timedelta(seconds=expires_seconds))
