from __future__ import annotations

from pathlib import Path

from ace_lite.pipeline.stages.validation import run_validation_stage
from ace_lite.preference_capture_store import DurablePreferenceCaptureStore
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


class _CleanBroker(_FakeBroker):
    def collect(self, *, root: str | Path, candidate_files: list[dict[str, object]], top_n: int) -> dict[str, object]:
        self.collect_calls.append(
            {
                "root": str(root),
                "candidate_files": list(candidate_files),
                "top_n": top_n,
            }
        )
        return {
            "count": 0,
            "diagnostics": [],
            "errors": [],
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
    assert payload["probes"]["status"] == "disabled"
    assert payload["probes"]["available"] == ["compile", "import", "tests"]
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
    assert payload["probes"]["status"] == "disabled"
    assert payload["probes"]["available"] == ["compile", "import", "tests"]
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
    assert payload["probes"]["status"] == "passed"
    assert payload["probes"]["available"] == ["compile", "import", "tests"]
    assert payload["probes"]["executed_count"] == 1
    assert payload["probes"]["issue_count"] == 0
    assert payload["result"]["summary"]["status"] == "failed"
    assert payload["result"]["syntax"]["issue_count"] == 1
    assert payload["xref"]["count"] == 1
    assert len(broker.collect_calls) == 1
    assert len(broker.collect_xref_calls) == 1
    sandbox_root = Path(str(broker.collect_calls[0]["root"]))
    assert sandbox_root.exists() is False


def test_run_validation_stage_reports_compile_probe_failure(tmp_path: Path) -> None:
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
                "+print(",
                "",
            ]
        ),
    ).as_dict()
    broker = _CleanBroker()

    payload = run_validation_stage(
        root=str(repo_root),
        query="validate patch",
        source_plan_stage={
            "candidate_files": [{"path": "src/app.py", "language": "python"}],
            "validation_tests": ["pytest -q tests/unit/test_validation_stage.py"],
        },
        index_stage={},
        enabled=True,
        include_xref=False,
        top_n=3,
        xref_top_n=2,
        sandbox_timeout_seconds=5.0,
        broker=broker,
        patch_artifact=patch_artifact,
    )

    assert payload["reason"] == "ok"
    assert payload["diagnostic_count"] == 0
    assert payload["probes"]["status"] == "failed"
    assert payload["probes"]["executed_count"] == 1
    assert payload["probes"]["issue_count"] == 1
    assert payload["result"]["summary"]["status"] == "failed"
    assert payload["result"]["summary"]["issue_count"] == 1
    assert payload["result"]["probes"]["results"][0]["name"] == "compile"
    assert payload["result"]["probes"]["results"][0]["status"] == "failed"


def test_run_validation_stage_executes_pytest_probe_when_test_path_exists(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    source_path = repo_root / "src" / "app.py"
    test_path = repo_root / "tests" / "test_sample.py"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("print('old')\n", encoding="utf-8")
    test_path.write_text(
        "\n".join(
            [
                "def test_smoke() -> None:",
                "    assert 1 + 1 == 2",
                "",
            ]
        ),
        encoding="utf-8",
    )

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
    broker = _CleanBroker()

    payload = run_validation_stage(
        root=str(repo_root),
        query="validate patch",
        source_plan_stage={
            "candidate_files": [{"path": "src/app.py", "language": "python"}],
            "validation_tests": ["pytest -q tests/test_sample.py"],
        },
        index_stage={},
        enabled=True,
        include_xref=False,
        top_n=3,
        xref_top_n=2,
        sandbox_timeout_seconds=5.0,
        broker=broker,
        patch_artifact=patch_artifact,
    )

    assert payload["reason"] == "ok"
    assert payload["diagnostic_count"] == 0
    assert payload["probes"]["status"] == "passed"
    assert payload["probes"]["executed_count"] == 2
    assert payload["probes"]["issue_count"] == 0
    assert {item["name"] for item in payload["result"]["probes"]["results"]} == {
        "compile",
        "tests",
    }
    assert payload["result"]["tests"]["executed"] == ["pytest -q tests/test_sample.py"]
    assert payload["result"]["summary"]["status"] == "passed"


def test_run_validation_stage_falls_back_to_first_source_plan_patch_artifact(tmp_path: Path) -> None:
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
                "+print('fallback')",
                "",
            ]
        ),
    ).as_dict()
    broker = _CleanBroker()

    payload = run_validation_stage(
        root=str(repo_root),
        query="validate patch",
        source_plan_stage={
            "candidate_files": [{"path": "src/app.py", "language": "python"}],
            "validation_tests": ["pytest -q tests/unit/test_validation_stage.py"],
            "patch_artifacts": [patch_artifact],
        },
        index_stage={},
        enabled=True,
        include_xref=False,
        top_n=3,
        xref_top_n=2,
        sandbox_timeout_seconds=5.0,
        broker=broker,
        patch_artifact=None,
    )

    assert payload["reason"] == "ok"
    assert payload["patch_artifact_present"] is True
    assert payload["sandbox"]["patch_applied"] is True
    assert payload["probes"]["status"] == "passed"
    assert payload["selected_branch_id"] == "candidate-1"
    assert payload["patch_artifact"] == patch_artifact
    assert payload["patch_artifacts"] == [patch_artifact]
    assert payload["branch_batch"]["candidate_count"] == 1
    assert payload["branch_batch"]["candidates"][0]["artifact_refs"] == [
        "validation.patch_artifact"
    ]


def test_run_validation_stage_selects_best_patch_artifact_candidate(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    source_path = repo_root / "src" / "app.py"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("print('old')\n", encoding="utf-8")

    failing_patch_artifact = build_patch_artifact_contract_v1(
        operations=[
            {
                "op": "update",
                "path": "src/app.py",
                "before_sha256": "before-a",
                "after_sha256": "after-a",
                "hunk_count": 2,
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
                "+print(",
                "",
            ]
        ),
    ).as_dict()
    passing_patch_artifact = build_patch_artifact_contract_v1(
        operations=[
            {
                "op": "update",
                "path": "src/app.py",
                "before_sha256": "before-b",
                "after_sha256": "after-b",
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
                "+print('winner')",
                "",
            ]
        ),
    ).as_dict()
    broker = _CleanBroker()

    payload = run_validation_stage(
        root=str(repo_root),
        query="validate patch",
        source_plan_stage={
            "candidate_files": [{"path": "src/app.py", "language": "python"}],
            "validation_tests": [],
            "patch_artifacts": [failing_patch_artifact, passing_patch_artifact],
        },
        index_stage={},
        enabled=True,
        include_xref=False,
        top_n=3,
        xref_top_n=2,
        sandbox_timeout_seconds=5.0,
        broker=broker,
        patch_artifact=None,
    )

    assert payload["reason"] == "ok"
    assert payload["patch_artifact_present"] is True
    assert payload["result"]["summary"]["status"] == "passed"
    assert payload["selected_branch_id"] == "candidate-2"
    assert payload["patch_artifact"] == passing_patch_artifact
    assert payload["patch_artifacts"] == [passing_patch_artifact, failing_patch_artifact]
    assert payload["branch_batch"]["candidates"][1]["artifact_refs"] == [
        "validation.patch_artifact"
    ]
    assert payload["branch_batch"]["schema_version"] == "agent_loop_branch_batch_v1"
    assert payload["branch_batch"]["candidate_count"] == 2
    assert payload["branch_selection"]["winner_branch_id"] == "candidate-2"
    assert payload["branch_selection"]["rejected"][0]["branch_id"] == "candidate-1"
    assert payload["branch_selection"]["rejected"][0]["rejected_reason"] == "lower_pass_status"
    assert payload["branch_outcome_preference_capture"] == {
        "schema_version": "branch_outcome_preference_capture_v1",
        "selected_branch_id": "candidate-2",
        "candidate_count": 2,
        "ranked_branch_ids": ["candidate-2", "candidate-1"],
        "rejected_count": 1,
        "rejected_reasons": ["lower_pass_status"],
        "winner_patch_scope_lines": 1,
        "winner_status": "passed",
        "winner_artifact_present": True,
        "rejected_artifact_count": 1,
        "execution_mode": "parallel",
        "candidate_origin": "source_plan.patch_artifacts",
        "source": "validation_stage",
        "target_file_manifest": ["src/app.py"],
        "winner_validation_branch_score": payload["branch_selection"][
            "winner_validation_branch_score"
        ],
        "rejected": payload["branch_selection"]["rejected"],
    }
    assert payload["rejected_patch_artifacts"] == [
        {
            "branch_id": "candidate-1",
            "rejected_reason": "lower_pass_status",
            "patch_artifact": failing_patch_artifact,
        }
    ]


def test_run_validation_stage_records_branch_outcome_preference_when_store_available(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    source_path = repo_root / "src" / "app.py"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("print('old')\n", encoding="utf-8")
    failing_patch_artifact = build_patch_artifact_contract_v1(
        operations=[
            {
                "op": "update",
                "path": "src/app.py",
                "before_sha256": "before-a",
                "after_sha256": "after-a",
                "hunk_count": 2,
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
                "+print(",
                "",
            ]
        ),
    ).as_dict()
    passing_patch_artifact = build_patch_artifact_contract_v1(
        operations=[
            {
                "op": "update",
                "path": "src/app.py",
                "before_sha256": "before-b",
                "after_sha256": "after-b",
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
                "+print('winner')",
                "",
            ]
        ),
    ).as_dict()
    broker = _CleanBroker()
    store = DurablePreferenceCaptureStore(
        db_path=tmp_path / "context-map" / "preference-capture.db"
    )

    payload = run_validation_stage(
        root=str(repo_root),
        query="validate candidate patches",
        source_plan_stage={
            "candidate_files": [{"path": "src/app.py", "language": "python"}],
            "validation_tests": [],
            "patch_artifacts": [failing_patch_artifact, passing_patch_artifact],
        },
        index_stage={},
        enabled=True,
        include_xref=False,
        top_n=3,
        xref_top_n=2,
        sandbox_timeout_seconds=5.0,
        broker=broker,
        preference_capture_store=store,
        preference_capture_repo_key="ace-lite",
        preference_capture_profile_key="bugfix",
    )

    capture_record = payload["branch_outcome_preference_capture_record"]
    assert capture_record["ok"] is True
    assert capture_record["skipped"] is False
    assert capture_record["recorded"]["preference_kind"] == "branch_outcome_preference"
    rows = store.list_events(
        repo_key="ace-lite",
        profile_key="bugfix",
        preference_kind="branch_outcome_preference",
        signal_source="runtime",
        limit=10,
    )
    assert len(rows) == 1
    assert rows[0].payload["summary"]["candidate_count"] == 2
