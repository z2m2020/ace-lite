from __future__ import annotations

from ace_lite.exact_search import (
    run_exact_search_ripgrep,
    score_exact_search_hits,
    tokenize_query_for_exact_search,
)


def test_tokenize_query_for_exact_search_dedup_and_limit() -> None:
    query = "a A a0 _ xx XX foo Foo foo/bar.py foo/bar.py z"
    tokens = tokenize_query_for_exact_search(query)
    assert "a" not in tokens  # too short
    assert "_" not in tokens  # too short
    assert tokens.count("xx") == 1
    assert tokens.count("foo") == 1
    assert tokens.count("Foo") == 0  # case-insensitive de-dupe
    assert "foo/bar.py" in tokens


def test_score_exact_search_hits_normalizes_to_unit_interval() -> None:
    scores = score_exact_search_hits(hits_by_path={"a": 1, "b": 10})
    assert set(scores) == {"a", "b"}
    assert 0.0 <= scores["a"] <= 1.0
    assert 0.0 <= scores["b"] <= 1.0
    assert scores["b"] >= scores["a"]


def test_run_exact_search_ripgrep_parses_count_matches(monkeypatch) -> None:
    import ace_lite.exact_search as exact_search

    captured_cmd: list[str] = []

    def fake_run_capture_output(cmd, *, cwd, timeout_seconds, env_overrides):  # type: ignore[no-untyped-def]
        nonlocal captured_cmd
        captured_cmd = list(cmd)
        stdout = "src/app.py:3\nREADME.md:1\n"
        return 0, stdout, "", False

    monkeypatch.setattr(exact_search, "run_capture_output", fake_run_capture_output)

    result = run_exact_search_ripgrep(
        root=".",
        query="app",
        include_globs=["*.py"],
        timeout_ms=50,
    )
    assert result.reason == "ok"
    assert result.hits_by_path["src/app.py"] == 3
    assert result.hits_by_path["README.md"] == 1
    assert "--count-matches" in captured_cmd
    assert any(arg.startswith("--glob=") for arg in captured_cmd)


def test_run_exact_search_ripgrep_rg_unavailable(monkeypatch) -> None:
    import ace_lite.exact_search as exact_search

    def fake_run_capture_output(cmd, *, cwd, timeout_seconds, env_overrides):  # type: ignore[no-untyped-def]
        return 127, "", "rg: not found", False

    monkeypatch.setattr(exact_search, "run_capture_output", fake_run_capture_output)

    result = run_exact_search_ripgrep(
        root=".",
        query="app",
        include_globs=[],
        timeout_ms=50,
    )
    assert result.reason == "rg_unavailable"
