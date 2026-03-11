from __future__ import annotations

import json
from pathlib import Path

import pytest

from ace_lite.workspace.summary_index import (
    SUMMARY_INDEX_V1_VERSION,
    build_repo_summary_v1,
    build_repo_summary_v1_from_index_payload,
    build_workspace_summary_index_v1,
    load_summary_index_v1,
    save_summary_index_v1,
    summary_tokens_for_repo,
)


def test_build_repo_summary_from_index_payload_extracts_core_fields() -> None:
    payload = {
        "files": {
            "src/billing/service.py": {"language": "python", "module": "billing.service"},
            "src/billing/models.py": {"language": "python", "module": "billing.models"},
            "web/checkout/app.ts": {"language": "typescript", "module": "checkout.app"},
        }
    }
    summary = build_repo_summary_v1_from_index_payload(
        repo_name="billing-api",
        repo_root="/tmp/billing-api",
        index_payload=payload,
        token_limit=16,
    )
    assert summary.name == "billing-api"
    assert summary.file_count == 3
    assert summary.language_counts["python"] == 2
    assert "src" in summary.top_directories
    assert "billing" in summary.summary_tokens


def test_summary_index_roundtrip_save_and_load(tmp_path: Path) -> None:
    summary = build_repo_summary_v1_from_index_payload(
        repo_name="repo-a",
        repo_root=str(tmp_path / "repo-a"),
        index_payload={"files": {"src/app.py": {"language": "python", "module": "app"}}},
    )
    index = build_workspace_summary_index_v1(repo_summaries=[summary], generated_at="2026-03-05T00:00:00+00:00")
    output = tmp_path / "context-map" / "workspace" / "summary-index.v1.json"
    saved = save_summary_index_v1(summary_index=index, path=output)
    loaded = load_summary_index_v1(saved)
    assert loaded.as_dict()["version"] == SUMMARY_INDEX_V1_VERSION
    assert summary_tokens_for_repo(summary_index=loaded, repo_name="repo-a")


def test_build_repo_summary_v1_refreshes_index_cache(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo-x"
    src = repo_root / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "feature.py").write_text("def run() -> int:\n    return 1\n", encoding="utf-8")

    summary = build_repo_summary_v1(
        repo_name="repo-x",
        repo_root=str(repo_root),
        languages="python",
        index_cache_path="context-map/index.summary.json",
        index_incremental=True,
    )
    assert summary.file_count >= 1
    cache_path = repo_root / "context-map" / "index.summary.json"
    assert cache_path.exists()
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)


def test_build_repo_summary_v1_from_index_payload_rejects_bool_limits() -> None:
    payload = {"files": {"src/app.py": {"language": "python", "module": "app"}}}
    with pytest.raises(ValueError, match=r"token_limit must be an integer"):
        build_repo_summary_v1_from_index_payload(
            repo_name="repo-a",
            repo_root="/tmp/repo-a",
            index_payload=payload,
            token_limit=True,
        )
