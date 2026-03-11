from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_TOKENIZER_MODEL = "gpt-4o-mini"
_FALLBACK_ENCODING = "cl100k_base"


def _estimate_by_whitespace(text: str) -> int:
    return max(1, len(str(text or "").split()))


def normalize_tokenizer_model(model: str | None) -> str:
    normalized = str(model or "").strip()
    return normalized or _DEFAULT_TOKENIZER_MODEL


@lru_cache(maxsize=32)
def _load_tiktoken_encoding(model: str) -> tuple[Any | None, str | None]:
    try:
        import tiktoken  # type: ignore
    except Exception:
        return None, None

    try:
        return tiktoken.encoding_for_model(model), model
    except Exception:
        try:
            return tiktoken.get_encoding(_FALLBACK_ENCODING), _FALLBACK_ENCODING
        except Exception:
            return None, None


def resolve_tokenizer_backend(model: str | None) -> tuple[str, str]:
    normalized = normalize_tokenizer_model(model)
    encoding, resolved = _load_tiktoken_encoding(normalized)
    if encoding is None or resolved is None:
        return "whitespace", "whitespace"
    return "tiktoken", str(resolved)


def estimate_tokens(text: str, *, model: str | None = None) -> int:
    normalized = normalize_tokenizer_model(model)
    body = str(text or "")
    if not body:
        return 1

    encoding, _resolved = _load_tiktoken_encoding(normalized)
    if encoding is None:
        return _estimate_by_whitespace(body)

    try:
        encoded = encoding.encode(body)
    except Exception:
        logger.debug(
            "token_estimator.encode_fallback",
            extra={"model": normalized},
            exc_info=True,
        )
        return _estimate_by_whitespace(body)

    return max(1, len(encoded))


__all__ = [
    "estimate_tokens",
    "normalize_tokenizer_model",
    "resolve_tokenizer_backend",
]
