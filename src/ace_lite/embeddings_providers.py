from __future__ import annotations

import hashlib
import json
import math
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Protocol
from urllib.request import Request

from ace_lite.http_utils import safe_urlopen

_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_]+")
BGE_M3_DEFAULT_MODEL = "BAAI/bge-m3"
BGE_RERANKER_DEFAULT_MODEL = "BAAI/bge-reranker-base"
OLLAMA_DEFAULT_MODEL = "nomic-embed-text"
OLLAMA_DEFAULT_DIMENSION = 768
OLLAMA_DEFAULT_BASE_URL = "http://localhost:11434"


class EmbeddingProvider(Protocol):
    @property
    def provider(self) -> str: ...

    @property
    def model(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    def encode(self, texts: list[str]) -> list[list[float]]: ...


class CrossEncoderProvider(Protocol):
    @property
    def provider(self) -> str: ...

    @property
    def model(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    def score(self, *, query: str, texts: list[str]) -> list[float]: ...


@lru_cache(maxsize=1)
def _load_sentence_transformer_backend() -> tuple[type[Any], type[Any]]:
    try:
        from sentence_transformers import CrossEncoder, SentenceTransformer
    except Exception as exc:
        raise RuntimeError(
            "Optional dependency 'sentence-transformers' is required for bge providers. "
            "Install with: pip install \"ace-lite-engine[local-ai]\"."
        ) from exc
    return SentenceTransformer, CrossEncoder


@dataclass(frozen=True, slots=True)
class HashEmbeddingProvider:
    model_name: str = "hash-v1"
    dim: int = 256

    @property
    def provider(self) -> str:
        return "hash"

    @property
    def model(self) -> str:
        return str(self.model_name)

    @property
    def dimension(self) -> int:
        return max(8, int(self.dim))

    def encode(self, texts: list[str]) -> list[list[float]]:
        output: list[list[float]] = []
        for text in texts:
            output.append(_hash_embed(text=text, dimension=self.dimension))
        return output


@dataclass(frozen=True, slots=True)
class HashCrossEncoderProvider:
    model_name: str = "hash-cross-v1"

    @property
    def provider(self) -> str:
        return "hash_cross"

    @property
    def model(self) -> str:
        return str(self.model_name)

    @property
    def dimension(self) -> int:
        return 1

    def score(self, *, query: str, texts: list[str]) -> list[float]:
        return [_hash_cross_score(query=query, text=text) for text in texts]


@dataclass(frozen=True, slots=True)
class HashColbertLateInteractionProvider:
    """Deterministic ColBERT-style late interaction scoring using lexical tokens."""

    model_name: str = "hash-colbert-v1"
    min_token_len: int = 3
    max_query_tokens: int = 32
    max_text_tokens: int = 256

    @property
    def provider(self) -> str:
        return "hash_colbert"

    @property
    def model(self) -> str:
        return str(self.model_name)

    @property
    def dimension(self) -> int:
        return 1

    def score(self, *, query: str, texts: list[str]) -> list[float]:
        query_tokens = _late_interaction_tokens(
            str(query or ""),
            min_len=self.min_token_len,
            limit=self.max_query_tokens,
        )
        if not query_tokens:
            return [0.0 for _ in texts]

        weights = {
            token: 1.0 + (0.25 if len(token) >= 8 else 0.0)
            for token in query_tokens
        }

        scores: list[float] = []
        for text in texts:
            text_tokens = set(
                _late_interaction_tokens(
                    str(text or ""),
                    min_len=self.min_token_len,
                    limit=self.max_text_tokens,
                )
            )
            score = sum(
                float(weights[token])
                for token in sorted(weights)
                if token in text_tokens
            )
            scores.append(float(score))
        return scores


@dataclass(slots=True)
class BGEM3EmbeddingProvider:
    model_name: str = BGE_M3_DEFAULT_MODEL
    dim: int = 1024
    normalize_embeddings: bool = True
    batch_size: int = 32
    _model: Any = field(default=None, init=False, repr=False, compare=False)

    @property
    def provider(self) -> str:
        return "bge_m3"

    @property
    def model(self) -> str:
        return str(self.model_name)

    @property
    def dimension(self) -> int:
        return max(8, int(self.dim))

    def _ensure_model(self) -> Any:
        if self._model is None:
            sentence_transformer_cls, _ = _load_sentence_transformer_backend()
            self._model = sentence_transformer_cls(str(self.model_name))
        return self._model

    def encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        model = self._ensure_model()
        encoded = model.encode(
            [str(text or "") for text in texts],
            normalize_embeddings=bool(self.normalize_embeddings),
            batch_size=max(1, int(self.batch_size)),
        )
        return _coerce_matrix(
            encoded,
            dimension=self.dimension,
            expected=len(texts),
        )


@dataclass(slots=True)
class SentenceTransformersEmbeddingProvider:
    """Embedding provider backed by sentence-transformers."""

    model_name: str
    dim: int | None = None
    normalize_embeddings: bool = True
    batch_size: int = 32
    _model: Any = field(default=None, init=False, repr=False, compare=False)
    _dimension: int | None = field(default=None, init=False, repr=False, compare=False)

    @property
    def provider(self) -> str:
        return "sentence_transformers"

    @property
    def model(self) -> str:
        return str(self.model_name)

    @property
    def dimension(self) -> int:
        if self._dimension is not None:
            return max(8, int(self._dimension))
        if self.dim is not None:
            return max(8, int(self.dim))
        return 256

    def _ensure_model(self) -> Any:
        if self._model is None:
            sentence_transformer_cls, _ = _load_sentence_transformer_backend()
            self._model = sentence_transformer_cls(str(self.model_name))
            if self._dimension is None:
                try:
                    self._dimension = int(self._model.get_sentence_embedding_dimension())
                except Exception:
                    self._dimension = None
        return self._model

    def encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        model = self._ensure_model()
        encoded = model.encode(
            [str(text or "") for text in texts],
            normalize_embeddings=bool(self.normalize_embeddings),
            batch_size=max(1, int(self.batch_size)),
        )
        return _coerce_matrix(
            encoded,
            dimension=self.dimension,
            expected=len(texts),
        )


@dataclass(slots=True)
class OllamaEmbeddingProvider:
    """HTTP embedding provider for an Ollama server."""

    model_name: str = OLLAMA_DEFAULT_MODEL
    dim: int = OLLAMA_DEFAULT_DIMENSION
    base_url: str = ""
    normalize_embeddings: bool = True
    batch_size: int = 32
    timeout_seconds: float = 8.0

    @property
    def provider(self) -> str:
        return "ollama"

    @property
    def model(self) -> str:
        return str(self.model_name)

    @property
    def dimension(self) -> int:
        return max(8, int(self.dim))

    def _resolve_base_url(self) -> str:
        raw = str(self.base_url or "").strip()
        if not raw:
            raw = (
                str(os.getenv("ACE_LITE_OLLAMA_BASE_URL", "")).strip()
                or OLLAMA_DEFAULT_BASE_URL
            )
        return raw.rstrip("/")

    def _post_json(self, *, url: str, payload: dict[str, Any]) -> Any:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8", errors="ignore")
        request = Request(
            url=url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with safe_urlopen(request, timeout=max(0.1, float(self.timeout_seconds))) as response:
            return json.loads(response.read() or b"{}")

    def _l2_normalize(self, vector: list[float]) -> list[float]:
        if not bool(self.normalize_embeddings):
            return vector
        norm = math.sqrt(sum(float(value) * float(value) for value in vector))
        if norm <= 0.0:
            return vector
        return [float(value) / norm for value in vector]

    def encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        base = self._resolve_base_url()
        model = str(self.model_name or OLLAMA_DEFAULT_MODEL)
        batch = max(1, int(self.batch_size))
        vectors: list[list[float]] = []

        def _encode_via_embed(chunk: list[str]) -> list[list[float]]:
            payload = self._post_json(
                url=f"{base}/api/embed",
                payload={"model": model, "input": [str(text or "") for text in chunk]},
            )
            embeddings_raw = payload.get("embeddings", [])
            return _coerce_matrix(embeddings_raw, dimension=self.dimension, expected=len(chunk))

        def _encode_via_embeddings(chunk: list[str]) -> list[list[float]]:
            output: list[list[float]] = []
            for text in chunk:
                payload = self._post_json(
                    url=f"{base}/api/embeddings",
                    payload={"model": model, "prompt": str(text or "")},
                )
                output.append(_coerce_vector(payload.get("embedding", []), dimension=self.dimension))
            return output

        for start in range(0, len(texts), batch):
            chunk = [str(text or "") for text in texts[start : start + batch]]
            try:
                chunk_vectors = _encode_via_embed(chunk)
            except Exception:
                chunk_vectors = _encode_via_embeddings(chunk)

            for vector in chunk_vectors:
                vectors.append(self._l2_normalize(vector))

        return vectors


@dataclass(slots=True)
class BGERerankerCrossEncoderProvider:
    model_name: str = BGE_RERANKER_DEFAULT_MODEL
    _model: Any = field(default=None, init=False, repr=False, compare=False)

    @property
    def provider(self) -> str:
        return "bge_reranker"

    @property
    def model(self) -> str:
        return str(self.model_name)

    @property
    def dimension(self) -> int:
        return 1

    def _ensure_model(self) -> Any:
        if self._model is None:
            _, cross_encoder_cls = _load_sentence_transformer_backend()
            self._model = cross_encoder_cls(str(self.model_name))
        return self._model

    def score(self, *, query: str, texts: list[str]) -> list[float]:
        if not texts:
            return []

        model = self._ensure_model()
        pairs = [[str(query or ""), str(text or "")] for text in texts]
        raw_scores = model.predict(pairs)
        return _coerce_score_list(raw_scores, expected=len(texts))


def _hash_embed(*, text: str, dimension: int) -> list[float]:
    dim = max(8, int(dimension))
    vector = [0.0] * dim
    normalized = str(text or "").lower()
    tokens = _TOKEN_PATTERN.findall(normalized)
    if not tokens:
        return vector

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8", errors="ignore")).digest()
        index = int.from_bytes(digest[:4], byteorder="big", signed=False) % dim
        sign = -1.0 if digest[4] % 2 else 1.0
        weight = 1.0 + float(len(token) >= 8) * 0.25
        vector[index] += sign * weight

    norm = math.sqrt(sum(value * value for value in vector))
    if norm > 0.0:
        vector = [value / norm for value in vector]
    return vector


def _late_interaction_tokens(text: str, *, min_len: int, limit: int) -> list[str]:
    normalized = str(text or "").lower()
    tokens = [
        token
        for token in _TOKEN_PATTERN.findall(normalized)
        if len(token) >= int(min_len)
    ]
    if not tokens:
        return []

    seen: set[str] = set()
    output: list[str] = []
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        output.append(token)
        if len(output) >= max(1, int(limit)):
            break
    return output


def _coerce_vector(value: Any, *, dimension: int) -> list[float]:
    dim = max(8, int(dimension))
    if not isinstance(value, list):
        return [0.0] * dim
    output: list[float] = []
    for item in value[:dim]:
        try:
            output.append(float(item))
        except Exception:
            output.append(0.0)
    if len(output) < dim:
        output.extend([0.0] * (dim - len(output)))
    return output


def _coerce_matrix(value: Any, *, dimension: int, expected: int) -> list[list[float]]:
    dim = max(8, int(dimension))
    payload = value
    if hasattr(payload, "tolist"):
        try:
            payload = payload.tolist()
        except Exception:
            payload = []

    rows = payload if isinstance(payload, list) else []
    if rows and not isinstance(rows[0], list):
        rows = [rows]

    vectors = [_coerce_vector(row, dimension=dim) for row in rows[:expected]]
    while len(vectors) < expected:
        vectors.append([0.0] * dim)
    return vectors


def _coerce_scalar(value: Any) -> float:
    if isinstance(value, list):
        if not value:
            return 0.0
        return _coerce_scalar(value[0])

    try:
        return float(value)
    except Exception:
        return 0.0


def _coerce_score_list(value: Any, *, expected: int) -> list[float]:
    payload = value
    if hasattr(payload, "tolist"):
        try:
            payload = payload.tolist()
        except Exception:
            payload = []

    rows = payload if isinstance(payload, list) else []
    scores = [_coerce_scalar(row) for row in rows[:expected]]
    while len(scores) < expected:
        scores.append(0.0)
    return scores


def _hash_cross_score(*, query: str, text: str) -> float:
    query_tokens = set(_TOKEN_PATTERN.findall(str(query or "").lower()))
    text_tokens = set(_TOKEN_PATTERN.findall(str(text or "").lower()))
    if not query_tokens or not text_tokens:
        return 0.0

    overlap = len(query_tokens & text_tokens)
    lexical = float(overlap) / float(max(1, len(query_tokens)))

    digest = hashlib.sha256(
        f"{query}\n{text}".encode("utf-8", errors="ignore")
    ).digest()
    jitter_raw = int.from_bytes(digest[:4], byteorder="big", signed=False)
    jitter = float(jitter_raw) / float(2**32)
    return max(0.0, min(1.0, (0.85 * lexical) + (0.15 * jitter)))


__all__ = [
    "BGE_M3_DEFAULT_MODEL",
    "BGE_RERANKER_DEFAULT_MODEL",
    "OLLAMA_DEFAULT_BASE_URL",
    "OLLAMA_DEFAULT_DIMENSION",
    "OLLAMA_DEFAULT_MODEL",
    "BGEM3EmbeddingProvider",
    "BGERerankerCrossEncoderProvider",
    "CrossEncoderProvider",
    "EmbeddingProvider",
    "HashColbertLateInteractionProvider",
    "HashCrossEncoderProvider",
    "HashEmbeddingProvider",
    "OllamaEmbeddingProvider",
    "SentenceTransformersEmbeddingProvider",
]
