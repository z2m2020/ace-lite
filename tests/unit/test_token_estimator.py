from __future__ import annotations

from ace_lite import token_estimator


def test_normalize_tokenizer_model_defaults() -> None:
    assert token_estimator.normalize_tokenizer_model(None) == "gpt-4o-mini"
    assert token_estimator.normalize_tokenizer_model(" ") == "gpt-4o-mini"


def test_estimate_tokens_falls_back_to_whitespace(monkeypatch) -> None:
    monkeypatch.setattr(token_estimator, "_load_tiktoken_encoding", lambda model: (None, None))
    assert token_estimator.estimate_tokens("one two three", model="demo") == 3


def test_resolve_tokenizer_backend_returns_whitespace_when_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(token_estimator, "_load_tiktoken_encoding", lambda model: (None, None))
    backend, encoding = token_estimator.resolve_tokenizer_backend("gpt-4.1-mini")
    assert backend == "whitespace"
    assert encoding == "whitespace"
