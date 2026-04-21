"""Token budget helpers with an optional tiktoken backend."""

from __future__ import annotations


def count_tokens(text: str, model: str = "") -> int:
    """Best-effort token counting with a tiktoken fallback."""
    try:
        import tiktoken

        encoding = tiktoken.encoding_for_model(model or "gpt-4o-mini")
        return len(encoding.encode(text))
    except Exception:
        return max(1, len(text) // 4)


def trim_to_budget(text: str, max_tokens: int, model: str = "") -> str:
    """Naive trimming helper for prompt budget control."""
    if count_tokens(text, model=model) <= max_tokens:
        return text

    ratio = max_tokens / max(count_tokens(text, model=model), 1)
    return text[: max(1, int(len(text) * ratio))]

