from __future__ import annotations

from ace_lite.index_stage.exact_search_boost import apply_exact_search_boost


def test_apply_exact_search_boost_injects_candidate() -> None:
    deep_path = "src/deep/module.py"
    files_map = {
        "src/current.py": {
            "module": "src.current",
            "language": "python",
            "symbols": [],
            "imports": [],
        },
        deep_path: {
            "module": "src.deep.module",
            "language": "python",
            "symbols": [],
            "imports": [],
        },
    }
    candidates = [{"path": "src/current.py", "score": 4.0, "score_breakdown": {}}]

    class _Result:
        def __init__(self) -> None:
            self.hits_by_path = {deep_path: 5}

        def to_payload(self) -> dict[str, object]:
            return {
                "backend": "ripgrep",
                "reason": "ok",
                "hit_paths": 1,
                "elapsed_ms": 1.0,
                "timed_out": False,
                "returncode": 0,
                "stderr": "",
            }

    def fake_run_exact_search(*, root, query, include_globs, timeout_ms):  # type: ignore[no-untyped-def]
        return _Result()

    def fake_score_exact_hits(*, hits_by_path):  # type: ignore[no-untyped-def]
        assert hits_by_path == {deep_path: 5}
        return {deep_path: 1.0}

    result = apply_exact_search_boost(
        root=".",
        query="needle",
        files_map=files_map,
        candidates=candidates,
        include_globs=["*.py"],
        time_budget_ms=20,
        max_paths=5,
        run_exact_search=fake_run_exact_search,
        score_exact_hits=fake_score_exact_hits,
    )

    candidate_paths = [str(item.get("path") or "") for item in result.candidates]
    assert deep_path in candidate_paths
    assert result.payload["enabled"] is True
    assert result.payload["applied"] is True
    assert result.payload["eligible_paths"] == 1
    assert result.payload["injected_count"] == 1


def test_apply_exact_search_boost_updates_existing_candidate() -> None:
    deep_path = "src/existing.py"
    files_map = {
        deep_path: {
            "module": "src.existing",
            "language": "python",
            "symbols": [],
            "imports": [],
        }
    }
    candidates = [{"path": deep_path, "score": 4.0, "score_breakdown": {}}]

    class _Result:
        def __init__(self) -> None:
            self.hits_by_path = {deep_path: 3}

        def to_payload(self) -> dict[str, object]:
            return {
                "backend": "ripgrep",
                "reason": "ok",
                "hit_paths": 1,
                "elapsed_ms": 1.0,
                "timed_out": False,
                "returncode": 0,
                "stderr": "",
            }

    def fake_run_exact_search(*, root, query, include_globs, timeout_ms):  # type: ignore[no-untyped-def]
        return _Result()

    def fake_score_exact_hits(*, hits_by_path):  # type: ignore[no-untyped-def]
        assert hits_by_path == {deep_path: 3}
        return {deep_path: 0.5}

    result = apply_exact_search_boost(
        root=".",
        query="needle",
        files_map=files_map,
        candidates=candidates,
        include_globs=["*.py"],
        time_budget_ms=20,
        max_paths=5,
        run_exact_search=fake_run_exact_search,
        score_exact_hits=fake_score_exact_hits,
    )

    boosted = result.candidates[0]
    assert boosted["path"] == deep_path
    assert boosted["score"] == 4.7
    assert boosted["score_breakdown"]["exact_search"] == 0.7
    assert result.payload["applied"] is True
    assert result.payload["boosted_count"] == 1
    assert result.payload["injected_count"] == 0
