"""Embedding service — generate embeddings via vLLM or ollama."""

from __future__ import annotations

from loguru import logger

from app.config import get_settings

# 默认 batch size（api 和 ollama 模式通用）
_DEFAULT_BATCH_SIZE = 32


def embed_texts(
    texts: list[str],
    batch_size: int | None = None,
    normalize: bool = True,
) -> list[list[float]]:
    """Generate embeddings for a list of texts.

    Dispatches to api / ollama based on EMBED_BACKEND config.
    """
    if not texts:
        return []

    settings = get_settings()

    if settings.backend == "vllm":
        return _embed_via_api(texts, batch_size)
    if settings.backend == "ollama":
        return _embed_via_ollama(texts, batch_size)

    raise ValueError(f"不支持的 Embedding 后端: {settings.backend}，可选: vllm / ollama")


def _embed_via_api(
    texts: list[str],
    batch_size: int | None = None,
) -> list[list[float]]:
    """Embed via OpenAI-compatible embedding API (vLLM / TGI)."""
    import httpx

    settings = get_settings()
    bs = batch_size or _DEFAULT_BATCH_SIZE
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
    bs = batch_size or _DEFAULT_BATCH_SIZE
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


if __name__ == "__main__":
    settings = get_settings()
    print(f"Embedding backend: {settings.backend}")
    if settings.backend == "vllm":
        print(f"  API: {settings.embed_api_base}  model: {settings.embed_model_name}")
    else:
        print(f"  Ollama: {settings.ollama_base_url}  model: {settings.ollama_embed_model}")

    print("Testing embed_texts...")
    try:
        vecs = embed_texts(["测试文本"])
        print(f"OK: dim={len(vecs[0])}, first 5 values={vecs[0][:5]}")
    except Exception as e:
        print(f"FAILED: {e}")
