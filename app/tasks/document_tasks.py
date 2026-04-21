"""Document processing Celery task — parse → chunk → embed → update DB.

This is the async pipeline triggered after file upload:
1. Read file based on type (PDF/image/text)
2. Extract and clean text content
3. Split into chunks
4. Generate embeddings via Ollama
5. Store vectors in Milvus
6. Update document record in MySQL
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
from pathlib import Path

from loguru import logger
from sqlalchemy import text as sql_text, update

from agent.input.preprocessor import (
    chunk_text,
    extract_from_image,
    extract_from_pdf,
    extract_from_text,
    merge_extracted_content,
)
from agent.infra.logger import request_log_scope
from agent.llm.local_provider import embed_texts
from agent.memory.long_term import vector_memory
from app.tasks.celery_app import celery_app
from app.db.mysql import get_session_factory
from app.db.minio import sync_download_file
from app.models.document import Document


def _run_async(coro):
    """Run an async coroutine from sync Celery task."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


async def _update_document(doc_id: str, **kwargs) -> None:
    """Update document record in MySQL."""
    factory = get_session_factory()
    async with factory() as session:
        stmt = update(Document).where(Document.id == doc_id).values(**kwargs)
        await session.execute(stmt)
        await session.commit()


@celery_app.task(
    name="process_document",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def process_document(
    self,
    document_id: str,
    user_id: str = "-",
    request_id: str = "-",
    request_log_file: str = "",
) -> dict:
    """Main document processing task.

    Args:
        document_id: Document record ID in MySQL

    Returns:
        {"status": "done", "chunk_count": N, "vector_count": N}
    """
    with request_log_scope(
        request_id=request_id,
        user_id=str(user_id),
        request_log_file=request_log_file,
    ):
        task_start = time.perf_counter()
        logger.info("Document task started | task_id={} document={}", self.request.id, document_id)

        # 1. Fetch document metadata from DB
        doc_meta = _run_async(_get_document(document_id))
        if doc_meta is None:
            logger.error("Document {} not found in DB", document_id)
            return {"status": "error", "message": "document not found"}

        minio_key = doc_meta["file_path"]
        file_type = doc_meta["file_type"]
        project_id = doc_meta["project_id"]

        # Mark as processing
        _run_async(_update_document(document_id, process_status=1, process_message="处理中..."))

        # Determine temp file suffix from original key
        suffix = Path(minio_key).suffix or f".{file_type}"
        tmp_path = None

        try:
            # 2. Download from MinIO to a temporary local file
            file_bytes = sync_download_file(minio_key)
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
            logger.info("Downloaded {} ({} bytes) from MinIO → {}", minio_key, len(file_bytes), tmp_path)

            # 3. Extract content based on file type
            extracted_text = ""
            tables = []
            ocr_text = ""
            vlm_desc = ""

            if file_type == "pdf":
                pdf_result = extract_from_pdf(tmp_path)
                extracted_text = pdf_result.text
                tables = pdf_result.tables

            elif file_type == "image":
                img_result = extract_from_image(tmp_path, use_vlm=True)
                ocr_text = img_result.ocr_text
                vlm_desc = img_result.vlm_description

            elif file_type == "text":
                txt_result = extract_from_text(tmp_path)
                extracted_text = txt_result["text"]

            else:
                raise ValueError(f"Unsupported file type: {file_type}")

            # 3. Merge all content
            full_text = merge_extracted_content(
                text=extracted_text,
                tables=tables,
                ocr_text=ocr_text,
                vlm_description=vlm_desc,
            )

            if not full_text.strip():
                _run_async(_update_document(
                    document_id,
                    process_status=3,
                    process_message="未能提取到任何文本内容",
                ))
                return {"status": "empty", "chunk_count": 0, "vector_count": 0}

            # 4. Chunk
            chunks = chunk_text(full_text)
            logger.info("Document {} → {} chunks", document_id, len(chunks))

            # 5. Embed and store to Milvus
            embeddings = embed_texts([chunk.text for chunk in chunks])
            vector_count = vector_memory.store(
                chunks,
                embeddings,
                project_id=project_id,
                document_id=document_id,
            )

            # 6. Update DB status
            _run_async(_update_document(
                document_id,
                process_status=2,
                chunk_count=len(chunks),
                process_message=f"处理完成: {len(chunks)}个分块, {vector_count}个向量",
            ))

            elapsed_ms = (time.perf_counter() - task_start) * 1000
            logger.info(
                "Document {} done: {} chunks, {} vectors ({:.0f}ms)",
                document_id,
                len(chunks),
                vector_count,
                elapsed_ms,
            )
            return {"status": "done", "chunk_count": len(chunks), "vector_count": vector_count}

        except Exception as e:
            logger.exception("Document {} processing failed: {}", document_id, e)
            _run_async(_update_document(
                document_id,
                process_status=3,
                process_message=f"处理失败: {str(e)[:500]}",
            ))

            # Retry on transient errors
            try:
                self.retry(exc=e)
            except self.MaxRetriesExceededError:
                pass

            return {"status": "error", "message": str(e)}

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)


async def _get_document(doc_id: str) -> dict | None:
    """Fetch document metadata from MySQL."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            sql_text("SELECT id, project_id, file_path, file_type FROM documents WHERE id = :id"),
            {"id": doc_id},
        )
        row = result.first()
        if row is None:
            return None
        return {"id": row[0], "project_id": row[1], "file_path": row[2], "file_type": row[3]}
