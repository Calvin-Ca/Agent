"""Embedding service — load model from local ModelScope/HuggingFace cache.

Supports:
- sentence-transformers (default, works with BGE/m3e/GTE etc.)
- API fallback (vLLM embedding endpoint)

Model is loaded ONCE as singleton, stays in GPU memory.
Thread-safe: sentence-transformers .encode() is safe for concurrent calls.
"""

from __future__ import annotations

import threading
from pathlib import Path

from loguru import logger

from app.config import get_settings

_embedder = None
_lock = threading.Lock()


def get_embedder():
    """Get or initialize the embedding model (singleton).

    Returns a sentence_transformers.SentenceTransformer instance.
    """
    global _embedder
    if _embedder is not None:
        return _embedder

    with _lock:   # 锁（Lock）是"同一时间只允许一个线程进入某段代码"的机制:同一时间只能有一个线程加载模型
        # Double-check after acquiring lock
        if _embedder is not None:
            return _embedder

        settings = get_settings()
        model_path = settings.embed_model_path

        if not Path(model_path).exists():
            raise FileNotFoundError(
                f"Embedding model not found at: {model_path}\n"
                f"Download it first: modelscope download --model BAAI/bge-large-zh-v1.5 --local_dir {model_path}"
            )

        logger.info("Loading embedding model from {} ...", model_path)

        from sentence_transformers import SentenceTransformer

        _embedder = SentenceTransformer(
            model_path,
            device=settings.embed_device,
            trust_remote_code=True,
        )

        # Log model info
        dim = _embedder.get_sentence_embedding_dimension()
        logger.info(
            "Embedding model loaded: dim={}, device={}, path={}",
            dim, settings.embed_device, model_path,
        )

        # Verify dimension matches Milvus config
        if dim != settings.milvus_dim:
            logger.warning(
                "⚠ Embedding dim ({}) != MILVUS_DIM ({}). Update .env!",
                dim, settings.milvus_dim,
            )

        return _embedder


def embed_texts(
    texts: list[str],
    batch_size: int | None = None,
    normalize: bool = True,
) -> list[list[float]]:
    """Generate embeddings for a list of texts.

    Dispatches to local / api / ollama based on EMBED_BACKEND config.

    Args:
        texts: List of text strings
        batch_size: Override default batch size
        normalize: L2 normalize embeddings (required for cosine similarity)

    Returns:
        List of embedding vectors
    """
    if not texts:
        return []

    settings = get_settings()

    if settings.embed_backend == "api":
        return _embed_via_api(texts, batch_size)
    elif settings.embed_backend == "ollama":
        return _embed_via_ollama(texts, batch_size)
    else:
        return _embed_local(texts, batch_size, normalize)


def _embed_local(
    texts: list[str],
    batch_size: int | None = None,
    normalize: bool = True,
) -> list[list[float]]:
    """Embed via local sentence-transformers model."""
    settings = get_settings()
    bs = batch_size or settings.embed_batch_size
    model = get_embedder()

    embeddings = model.encode(
        texts,
        batch_size=bs,
        show_progress_bar=len(texts) > 100,
        normalize_embeddings=normalize,
    )

    result = [emb.tolist() for emb in embeddings]
    logger.debug("Embedded {} texts locally (batch_size={})", len(result), bs)
    return result


def _embed_via_api(
    texts: list[str],
    batch_size: int | None = None,
) -> list[list[float]]:
    """Embed via OpenAI-compatible embedding API (vLLM / TGI).

    调用 vLLM 等部署的 OpenAI 兼容 embedding 端点。
    服务器启动方式: vllm serve models/embeddings/bge-m3 --port 8002 --task embed
    """
    import httpx

    settings = get_settings()
    bs = batch_size or settings.embed_batch_size
    all_embeddings: list[list[float]] = []

    headers = {"Content-Type": "application/json"}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"

    for i in range(0, len(texts), bs):
        batch = texts[i : i + bs]
        try:
            resp = httpx.post(
                f"{settings.embed_api_base}/embeddings",
                json={
                    "model": settings.embed_model_name,
                    "input": batch,
                },
                headers=headers,
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            # OpenAI format: {"data": [{"embedding": [...], "index": 0}, ...]}
            batch_embeddings = [item["embedding"] for item in data["data"]]
            all_embeddings.extend(batch_embeddings)
            logger.debug("API embedded batch {}-{}/{}", i, i + len(batch), len(texts))
        except Exception as e:
            logger.error("API embedding failed for batch {}: {}", i, e)
            dim = settings.milvus_dim
            all_embeddings.extend([[0.0] * dim] * len(batch))

    logger.debug("Embedded {} texts via API", len(all_embeddings))
    return all_embeddings


def _embed_via_ollama(
    texts: list[str],
    batch_size: int | None = None,
) -> list[list[float]]:
    """Embed via Ollama HTTP API."""
    import httpx

    settings = get_settings()
    bs = batch_size or settings.embed_batch_size
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), bs):
        batch = texts[i : i + bs]
        try:
            resp = httpx.post(
                f"{settings.ollama_base_url}/api/embed",
                json={"model": settings.ollama_embed_model, "input": batch},
                timeout=120,
            )
            resp.raise_for_status()
            embeddings = resp.json().get("embeddings", [])
            all_embeddings.extend(embeddings)
        except Exception as e:
            logger.error("Ollama embedding failed for batch {}: {}", i, e)
            dim = settings.milvus_dim
            all_embeddings.extend([[0.0] * dim] * len(batch))

    logger.debug("Embedded {} texts via Ollama", len(all_embeddings))
    return all_embeddings


def unload_embedder() -> None:
    """Unload model from memory (for testing or model switching)."""
    " 把已经加载到内存（甚至 GPU）的 embedding 模型释放掉 "
    global _embedder
    with _lock:
        if _embedder is not None:
            del _embedder
            _embedder = None
            logger.info("Embedding model unloaded")

            # Free GPU memory
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass
