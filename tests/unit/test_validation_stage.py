from __future__ import annotations

from pathlib import Path

from ace_lite.pipeline.stages.validation import run_validation_stage
from ace_lite.validation.patch_artifact import build_patch_artifact_contract_v1


class _FakeBroker:
    def __init__(self) -> None:
        self.collect_calls: list[dict[str, object]] = []
        self.collect_xref_calls: list[dict[str, object]] = []

    def collect(self, *, root: str | Path, candidate_files: list[dict[str, object]], top_n: int) -> dict[str, object]:
        self.collect_calls.append(
            {
                "root": str(root),
                "candidate_files": list(candidate_files),
                "top_n": top_n,
            }
        )
        return {
            "count": 1,
            "diagnostics": [
                {
                    "path": "src/app.py",
                    "language": "python",
                    "severity": "error",
                    "message": "invalid syntax",
                    "line": 1,
                    "column": 1,
                }
            ],
            "errors": [],
        }

    def collect_xref(
        self,
        *,
        root: str | Path,
        query: str,
        candidate_files: list[dict[str, object]],
        top_n: int,
        time_budget_ms: int,
    ) -> dict[str, object]:
        self.collect_xref_calls.append(
            {
                "root": str(root),
                "query": query,
                "candidate_files": list(candidate_files),
                "top_n": top_n,
                "time_budget_ms": time_budget_ms,
            }
        )
        return {
            "count": 1,
            "results": [{"path": "src/app.py", "message": "xref hit"}],
            "errors": [],
            "budget_exhausted": False,
            "elapsed_ms": 1.0,
            "time_budget_ms": time_budget_ms,
        }


def test_run_validation_stage_fail_open_when_disabled(tmp_path: Path) -> None:
    payload = run_validation_stage(
        root=str(tmp_path),
        query="validate patch",
        source_plan_stage={},
        index_stage={},
        enabled=False,
        include_xref=False,
        top_n=3,
        xref_top_n=2,
        sandbox_timeout_seconds=5.0,
        broker=None,
    )

    assert payload["enabled"] is False
    assert payload["reason"] == "disabled"
    assert payload["patch_artifact_present"] is False
    assert payload["result"]["summary"]["status"] == "skipped"


def test_run_validation_stage_fail_open_when_patch_artifact_missing(tmp_path: Path) -> None:
    broker = _FakeBroker()

    payload = run_validation_stage(
        root=str(tmp_path),
        query="validate patch",
        source_plan_stage={"validation_tests": ["pytest -q tests/unit/test_validation_stage.py"]},
        index_stage={},
        enabled=True,
        include_xref=True,
        top_n=3,
        xref_top_n=2,
        sandbox_timeout_seconds=5.0,
        broker=broker,
    )

    assert payload["enabled"] is True
    assert payload["reason"] == "patch_artifact_missing"
    assert payload["patch_artifact_present"] is False
    assert payload["result"]["summary"]["status"] == "skipped"
    assert broker.collect_calls == []
    assert broker.collect_xref_calls == []


def test_run_validation_stage_collects_diagnostics_in_sandbox(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    source_path = repo_root / "src" / "app.py"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("print('old')\n", encoding="utf-8")

    patch_artifact = build_patch_artifact_contract_v1(
        operations=[
            {
                "op": "update",
                "path": "src/app.py",
                "before_sha256": "before",
                "after_sha256": "after",
                "hunk_count": 1,
            }
        ],
        rollback_anchors=[
            {"path": "src/app.py", "strategy": "git_restore", "anchor": "HEAD"}
        ],
        patch_text="\n".join(
            [
                "diff --git a/src/app.py b/src/app.py",
                "--- a/src/app.py",
                "+++ b/src/app.py",
                "@@ -1 +1 @@",
                "-print('old')",
                "+print('new')",
                "",
            ]
        ),
    ).as_dict()
    broker = _FakeBroker()

    payload = run_validation_stage(
        root=str(repo_root),
        query="validate patch",
        source_plan_stage={
            "candidate_files": [{"path": "src/app.py", "language": "python"}],
            "validation_tests": ["pytest -q tests/unit/test_validation_stage.py"],
        },
        index_stage={},
        enabled=True,
        include_xref=True,
        top_n=3,
        xref_top_n=2,
        sandbox_timeout_seconds=5.0,
        broker=broker,
        patch_artifact=patch_artifact,
    )

    assert payload["enabled"] is True
    assert payload["reason"] == "ok"
    assert payload["patch_artifact_present"] is True
    assert payload["sandbox"]["patch_applied"] is True
    assert payload["sandbox"]["cleanup_ok"] is True
    assert payload["diagnostic_count"] == 1
    assert payload["result"]["summary"]["status"] == "failed"
    assert payload["result"]["syntax"]["issue_count"] == 1
    assert payload["xref"]["count"] == 1
    assert len(broker.collect_calls) == 1
    assert len(broker.collect_xref_calls) == 1
    sandbox_root = Path(str(broker.collect_calls[0]["root"]))
    assert sandbox_root.exists() is False
