from __future__ import annotations

from ace_lite.text_tokens import code_tokens


def test_code_tokens_splits_camel_case_and_keeps_original() -> None:
    tokens = code_tokens("getUserById", min_len=2, max_tokens=32)
    assert tokens[0] == "getuserbyid"
    assert "get" in tokens
    assert "user" in tokens
    assert "by" in tokens
    assert "id" in tokens


def test_code_tokens_splits_snake_case_and_keeps_original() -> None:
    tokens = code_tokens("get_user_by_id", min_len=2, max_tokens=32)
    assert tokens[0] == "get_user_by_id"
    assert "get" in tokens
    assert "user" in tokens
    assert "by" in tokens
    assert "id" in tokens


def test_code_tokens_splits_paths() -> None:
    tokens = code_tokens("internal/app/api/shutdown", min_len=2, max_tokens=32)
    assert "internal" in tokens
    assert "app" in tokens
    assert "api" in tokens
    assert "shutdown" in tokens

