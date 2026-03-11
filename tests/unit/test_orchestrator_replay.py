from __future__ import annotations

from pathlib import Path

from ace_lite.orchestrator_replay import build_orchestrator_plan_replay_key


def _budget_knobs() -> dict[str, int]:
    return {
        "top_k_files": 8,
        "repomap_top_k": 6,
        "chunk_top_k": 24,
        "chunk_per_file_limit": 4,
        "chunk_token_budget": 1800,
        "chunk_token_estimator_chars_per_token": 4,
        "skills_token_budget": 900,
        "memory_limit": 5,
        "lsp_top_n": 6,
        "lsp_xref_top_n": 4,
    }


def _build_key(*, root: Path) -> str:
    return build_orchestrator_plan_replay_key(
        query="fix replay cache invalidation",
        repo="ace-lite-engine",
        root=str(root),
        temporal_input={},
        plugins_loaded=[],
        conventions_hashes={},
        memory_payload={"count": 0, "hits": []},
        index_payload={
            "candidate_files": [{"path": "src/demo.py"}],
            "candidate_chunks": [],
            "policy_name": "auto",
            "metadata": {"selection_fingerprint": "selection-v1"},
        },
        repomap_payload={},
        augment_payload={},
        skills_payload={},
        retrieval_policy_version="v1",
        candidate_ranker_default="rrf_hybrid",
        budget_knobs=_budget_knobs(),
    )


def test_build_orchestrator_plan_replay_key_changes_when_relevant_file_changes(
    tmp_path: Path,
) -> None:
    demo_file = tmp_path / "src" / "demo.py"
    demo_file.parent.mkdir(parents=True, exist_ok=True)
    demo_file.write_text("print('first')\n", encoding="utf-8")

    first = _build_key(root=tmp_path)

    demo_file.write_text("print('second')\n", encoding="utf-8")

    second = _build_key(root=tmp_path)

    assert first != second
