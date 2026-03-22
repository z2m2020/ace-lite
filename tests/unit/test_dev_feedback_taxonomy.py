from __future__ import annotations

from ace_lite.dev_feedback_store import normalize_dev_fix
from ace_lite.dev_feedback_store import normalize_dev_issue
from ace_lite.dev_feedback_taxonomy import describe_dev_feedback_reason
from ace_lite.dev_feedback_taxonomy import normalize_dev_feedback_reason_code


def test_normalize_dev_feedback_reason_code_maps_known_aliases() -> None:
    assert normalize_dev_feedback_reason_code("manual selection override") == (
        "manual_override"
    )
    assert normalize_dev_feedback_reason_code("retry_loop") == "repeated_retry"
    assert normalize_dev_feedback_reason_code("sandbox_timeout") == "validation_timeout"
    assert normalize_dev_feedback_reason_code("patch_apply_failed") == (
        "validation_apply_failed"
    )
    assert normalize_dev_feedback_reason_code("missing_validation") == (
        "evidence_insufficient"
    )
    assert normalize_dev_feedback_reason_code("cache_corruption") == (
        "stage_artifact_cache_corrupt"
    )
    assert normalize_dev_feedback_reason_code("editable_install_drift") == (
        "install_drift"
    )


def test_describe_dev_feedback_reason_returns_family_and_capture_class() -> None:
    payload = describe_dev_feedback_reason("parallel_docs_timeout")

    assert payload == {
        "reason_code": "parallel_docs_timeout",
        "reason_family": "parallelism",
        "capture_class": "timeout",
    }
    assert describe_dev_feedback_reason("validation_timeout") == {
        "reason_code": "validation_timeout",
        "reason_family": "validation",
        "capture_class": "timeout",
    }
    assert describe_dev_feedback_reason("git_unavailable") == {
        "reason_code": "git_unavailable",
        "reason_family": "runtime_environment",
        "capture_class": "environment",
    }


def test_normalize_dev_issue_and_fix_use_canonical_reason_codes() -> None:
    issue = normalize_dev_issue(
        {
            "title": "Manual override observed",
            "reason_code": "manual selection override",
            "repo": "demo",
        }
    )
    fix = normalize_dev_fix(
        {
            "reason_code": "retry loop",
            "repo": "demo",
            "resolution_note": "tightened retry budget",
        }
    )

    assert issue.reason_code == "manual_override"
    assert fix.reason_code == "repeated_retry"
