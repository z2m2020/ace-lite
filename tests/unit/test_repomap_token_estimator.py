from __future__ import annotations

from typing import Any

from ace_lite.repomap.builder import build_repo_map, build_stage_repo_map


def test_build_repo_map_uses_token_estimator_model(monkeypatch: Any) -> None:
    calls: list[tuple[str, str | None]] = []

    def _stub_estimate_tokens(text: str, *, model: str | None = None) -> int:
        calls.append((str(text), model))
        return 10

    def _stub_rank_index_files(*, files: dict[str, Any], profile: str, signal_weights: Any = None) -> list[dict[str, Any]]:
        return [
            {
                "path": "src/a.py",
                "module": "src.a",
                "language": "python",
                "score": 1.0,
                "symbol_count": 1,
                "import_count": 0,
            },
            {
                "path": "src/b.py",
                "module": "src.b",
                "language": "python",
                "score": 0.5,
                "symbol_count": 1,
                "import_count": 0,
            },
        ]

    monkeypatch.setattr("ace_lite.repomap.builder.estimate_tokens", _stub_estimate_tokens)
    monkeypatch.setattr("ace_lite.repomap.builder.rank_index_files", _stub_rank_index_files)

    payload = build_repo_map(
        index_payload={"files": {"src/a.py": {}, "src/b.py": {}}},
        budget_tokens=25,
        top_k=10,
        ranking_profile="heuristic",
        tokenizer_model="unit-test-model",
    )

    assert payload["selected_count"] == 2
    assert payload["used_tokens"] == 20
    assert any(model == "unit-test-model" for _text, model in calls)


def test_build_stage_repo_map_passes_tokenizer_model(monkeypatch: Any) -> None:
    calls: list[tuple[str, str | None]] = []

    def _stub_estimate_tokens(text: str, *, model: str | None = None) -> int:
        calls.append((str(text), model))
        return 1

    def _stub_rank_index_files(
        *,
        files: dict[str, Any],
        profile: str,
        signal_weights: Any = None,
        seed_paths: Any = None,
    ) -> list[dict[str, Any]]:
        return [
            {"path": "src/a.py", "score": 1.0, "module": "src.a", "language": "python"},
            {"path": "src/b.py", "score": 0.5, "module": "src.b", "language": "python"},
        ]

    monkeypatch.setattr("ace_lite.repomap.builder.estimate_tokens", _stub_estimate_tokens)
    monkeypatch.setattr("ace_lite.repomap.builder.rank_index_files", _stub_rank_index_files)

    files_map = {
        "src/a.py": {
            "language": "python",
            "module": "src.a",
            "symbols": [{"name": "a", "qualified_name": "src.a.a"}],
            "imports": [{"module": "src.b"}],
        },
        "src/b.py": {
            "language": "python",
            "module": "src.b",
            "symbols": [{"name": "b", "qualified_name": "src.b.b"}],
            "imports": [],
        },
    }

    payload = build_stage_repo_map(
        index_files=files_map,
        seed_candidates=[{"path": "src/a.py", "score": 1.0}],
        ranking_profile="graph",
        top_k=2,
        neighbor_limit=4,
        neighbor_depth=1,
        budget_tokens=64,
        tokenizer_model="unit-test-model",
    )

    assert payload["enabled"] is True
    assert any(model == "unit-test-model" for _text, model in calls)

