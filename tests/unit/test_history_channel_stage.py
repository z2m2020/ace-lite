from __future__ import annotations

from ace_lite.pipeline.stages.history_channel import run_history_channel
from ace_lite.pipeline.types import StageContext


def test_run_history_channel_emits_stable_history_payload() -> None:
    ctx = StageContext(query="inspect recent auth fix", repo="r", root="/tmp/repo")
    ctx.state = {
        "index": {
            "candidate_files": [
                {"path": "src/app.py", "score": 1.0},
                {"path": "tests/test_app.py", "score": 0.5},
            ],
            "policy_name": "general",
            "policy_version": "v1",
        },
        "repomap": {"focused_files": ["src/app.py"]},
        "augment": {
            "vcs_history": {
                "enabled": True,
                "reason": "ok",
                "commit_count": 2,
                "path_count": 1,
                "commits": [
                    {
                        "hash": "abc123",
                        "subject": "fix app behavior",
                        "author": "dev",
                        "committed_at": "2026-04-14T00:00:00Z",
                        "files": ["src/app.py"],
                    },
                    {
                        "hash": "def456",
                        "subject": "update docs",
                        "author": "dev",
                        "committed_at": "2026-04-13T00:00:00Z",
                        "files": ["docs/readme.md"],
                    },
                ],
            }
        },
    }

    payload = run_history_channel(ctx=ctx)

    assert payload["schema_version"] == "history_channel_v1"
    assert payload["enabled"] is True
    assert payload["reason"] == "matched"
    assert payload["focused_files"] == ["src/app.py"]
    assert payload["commit_count"] == 2
    assert payload["path_count"] == 1
    assert payload["hit_count"] == 1
    assert payload["history_hits"]["schema_version"] == "history_hits_v1"
    assert payload["history_hits"]["hits"][0]["hash"] == "abc123"
    assert payload["history_hits"]["hits"][0]["matched_path_count"] == 1
    assert payload["recommendations"]


def test_run_history_channel_handles_missing_history_fail_open() -> None:
    ctx = StageContext(query="inspect recent auth fix", repo="r", root="/tmp/repo")
    ctx.state = {
        "index": {
            "candidate_files": [{"path": "src/app.py", "score": 1.0}],
            "policy_name": "general",
            "policy_version": "v1",
        },
        "repomap": {"focused_files": ["src/app.py"]},
        "augment": {"vcs_history": {"enabled": False, "reason": "disabled", "commits": []}},
    }

    payload = run_history_channel(ctx=ctx)

    assert payload["enabled"] is False
    assert payload["reason"] == "disabled"
    assert payload["path_count"] == 1
    assert payload["hit_count"] == 0
    assert payload["history_hits"]["hit_count"] == 0
