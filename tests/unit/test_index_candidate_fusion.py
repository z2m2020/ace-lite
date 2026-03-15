from __future__ import annotations

from ace_lite.index_stage.candidate_fusion import apply_multi_channel_rrf_fusion


def test_apply_multi_channel_rrf_fusion_applies_docs_and_memory_rankings() -> None:
    candidates = [
        {"path": "src/a.py", "score": 10.0},
        {"path": "src/b.py", "score": 9.0},
        {"path": "src/c.py", "score": 8.0},
    ]
    files_map = {path: {"path": path} for path in ("src/a.py", "src/b.py", "src/c.py")}
    docs_payload = {
        "hints": {
            "path_scores": [
                {"value": "src/c.py", "score": 0.9},
                {"value": "src/b.py", "score": 0.7},
            ]
        }
    }

    fused_candidates, payload = apply_multi_channel_rrf_fusion(
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
    assert fused_candidates[0]["path"] == "src/c.py"
    assert fused_candidates[0]["score_breakdown"]["rrf_multi_channel"] > 0.0
