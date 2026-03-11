from __future__ import annotations

from pathlib import Path

import yaml


def test_default_v1_arm_catalog_covers_bounded_router_arms() -> None:
    catalog_path = Path(__file__).resolve().parents[2] / "benchmark" / "arms" / "default_v1.yaml"
    payload = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "ace-lite-arm-catalog-v1"
    assert payload["name"] == "default_v1"
    shared = payload.get("shared_overrides", {})
    assert shared["top_k_files"] == 8
    assert shared["embedding_fail_open"] is True
    assert shared["exact_search_enabled"] is True

    arms = payload.get("arms", [])
    arm_ids = [str(item.get("arm_id") or "") for item in arms if isinstance(item, dict)]
    assert arm_ids == [
        "auto_default",
        "general_rrf",
        "general_hybrid",
        "general_heuristic",
        "bugfix_dense",
        "bugfix_heuristic",
        "feature_graph",
        "refactor_graph",
        "doc_intent_hybrid",
        "perf_proxy_refactor",
    ]

    heuristic = next(item for item in arms if item.get("arm_id") == "general_heuristic")
    assert heuristic["overrides"]["retrieval_policy"] == "general"
    assert heuristic["overrides"]["candidate_ranker"] == "heuristic"
    assert heuristic["overrides"]["embedding_enabled"] is False

    auto_default = next(item for item in arms if item.get("arm_id") == "auto_default")
    assert auto_default["overrides"]["retrieval_policy"] == "auto"
    assert auto_default["overrides"]["embedding_enabled"] is True
