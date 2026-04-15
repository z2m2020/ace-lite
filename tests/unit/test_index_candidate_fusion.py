from __future__ import annotations

from ace_lite.index_stage.candidate_fusion import apply_multi_channel_rrf_fusion


def test_apply_multi_channel_rrf_fusion_applies_docs_and_memory_rankings() -> None:
    candidates = [
        {"path": "src/a.py", "score": 10.0},
        {"path": "src/b.py", "score": 9.0},
        {"path": "src/c.py", "score": 8.0},
    ]
    files_map = {
        "src/a.py": {"path": "src/a.py", "functions": [{"name": "alpha"}]},
        "src/b.py": {
            "path": "src/b.py",
            "functions": [{"name": "beta"}, {"name": "beta2"}],
        },
        "src/c.py": {
            "path": "src/c.py",
            "functions": [{"name": "gamma"}],
            "classes": [{"name": "Gamma"}],
        },
    }
    docs_payload = {
        "hints": {
            "path_scores": [
                {"value": "src/c.py", "score": 0.9},
                {"value": "src/b.py", "score": 0.7},
            ]
        }
    }

    fused_candidates, payload = apply_multi_channel_rrf_fusion(
        root=".",
        candidates=candidates,
        files_map=files_map,
        docs_payload=docs_payload,
        memory_paths=["src/c.py", "src/a.py"],
        top_k_files=2,
        rrf_k=10,
        pool_cap=3,
        code_cap=3,
        docs_cap=2,
        memory_cap=2,
    )

    assert payload["applied"] is True
    assert payload["reason"] == "ok"
    assert payload["channels"]["docs"]["top"] == ["src/c.py", "src/b.py"]
    assert payload["channels"]["memory"]["top"] == ["src/c.py", "src/a.py"]
    assert payload["channels"]["granularity"]["top"] == ["src/b.py", "src/c.py", "src/a.py"]
    assert fused_candidates[0]["path"] == "src/c.py"
    assert fused_candidates[0]["score_breakdown"]["rrf_multi_channel"] > 0.0
    assert payload["fused"]["top"][0]["ranks"]["granularity"] > 0
    assert payload["fused"]["top"][0]["contrib"]["granularity"] > 0.0


def test_apply_multi_channel_rrf_fusion_can_use_granularity_without_docs_or_memory() -> None:
    candidates = [
        {"path": "src/a.py", "score": 10.0},
        {"path": "src/b.py", "score": 9.9},
        {"path": "src/c.py", "score": 9.8},
    ]
    files_map = {
        "src/a.py": {"path": "src/a.py", "functions": [{"name": "alpha"}]},
        "src/b.py": {
            "path": "src/b.py",
            "functions": [{"name": "beta"}, {"name": "beta2"}, {"name": "beta3"}],
        },
        "src/c.py": {"path": "src/c.py", "functions": []},
    }

    fused_candidates, payload = apply_multi_channel_rrf_fusion(
        root=".",
        candidates=candidates,
        files_map=files_map,
        docs_payload={"enabled": False},
        memory_paths=[],
        top_k_files=2,
        rrf_k=10,
        pool_cap=3,
        code_cap=3,
        docs_cap=2,
        memory_cap=2,
    )

    assert payload["applied"] is True
    assert payload["reason"] == "ok"
    assert payload["channels"]["docs"]["count"] == 0
    assert payload["channels"]["memory"]["count"] == 0
    assert payload["channels"]["granularity"]["top"] == ["src/b.py", "src/a.py"]
    assert fused_candidates[0]["score_breakdown"]["rrf_multi_channel"] > 0.0
    assert payload["fused"]["top"][0]["ranks"]["granularity"] > 0


def test_apply_multi_channel_rrf_fusion_adds_history_channel(monkeypatch) -> None:
    candidates = [
        {"path": "src/a.py", "score": 10.0},
        {"path": "src/b.py", "score": 9.5},
        {"path": "src/c.py", "score": 9.0},
    ]
    files_map = {
        "src/a.py": {"path": "src/a.py", "functions": [{"name": "alpha"}]},
        "src/b.py": {"path": "src/b.py", "functions": [{"name": "beta"}]},
        "src/c.py": {"path": "src/c.py", "functions": [{"name": "gamma"}]},
    }

    monkeypatch.setattr(
        "ace_lite.index_stage.candidate_fusion.collect_git_commit_history",
        lambda **kwargs: {
            "enabled": True,
            "reason": "ok",
            "commit_count": 2,
            "commits": [
                {
                    "hash": "c2",
                    "committed_at": "2026-04-15T10:00:00+00:00",
                    "subject": "touch b and c",
                    "files": ["src/b.py", "src/c.py"],
                },
                {
                    "hash": "c1",
                    "committed_at": "2026-04-14T10:00:00+00:00",
                    "subject": "touch b",
                    "files": ["src/b.py"],
                },
            ],
            "error": None,
        },
    )

    fused_candidates, payload = apply_multi_channel_rrf_fusion(
        root=".",
        candidates=candidates,
        files_map=files_map,
        docs_payload={"enabled": False},
        memory_paths=[],
        top_k_files=2,
        rrf_k=10,
        pool_cap=3,
        code_cap=3,
        docs_cap=2,
        memory_cap=2,
    )

    assert payload["applied"] is True
    assert payload["channels"]["history"]["count"] == 2
    assert payload["channels"]["history"]["top"] == ["src/b.py", "src/c.py"]
    assert payload["channels"]["history"]["commit_count"] == 2
    assert payload["fused"]["top"][0]["ranks"]["history"] > 0
    assert payload["fused"]["top"][0]["contrib"]["history"] > 0.0
    assert fused_candidates[0]["path"] == "src/b.py"
