from __future__ import annotations

import pytest

from ace_lite.runtime_fingerprint import (
    GIT_FAST_FINGERPRINT_TRUST_CLASSES,
    GitFastFingerprint,
    build_git_fast_fingerprint,
    build_git_fast_fingerprint_observability,
    normalize_git_fast_fingerprint,
)


def test_normalize_git_fast_fingerprint_supports_required_trust_classes() -> None:
    for trust_class in GIT_FAST_FINGERPRINT_TRUST_CLASSES:
        fingerprint = normalize_git_fast_fingerprint(
            {
                "fingerprint": "fp-123",
                "trust_class": trust_class,
                "dirty_path_count": 2,
                "dirty_paths_sample": ["src/a.py", "src/b.py"],
            }
        )

        assert fingerprint.trust_class == trust_class
        assert fingerprint.dirty_path_count == 2
        assert fingerprint.dirty_paths_sample == ("src/a.py", "src/b.py")


def test_normalize_git_fast_fingerprint_rejects_invalid_trust_class() -> None:
    with pytest.raises(ValueError, match="unsupported git fast fingerprint trust_class"):
        normalize_git_fast_fingerprint(
            {
                "fingerprint": "fp-123",
                "trust_class": "unknown",
            }
        )


def test_git_fast_fingerprint_observability_payload_includes_contract_fields() -> None:
    payload = build_git_fast_fingerprint_observability(
        GitFastFingerprint(
            fingerprint="fp-abc",
            trust_class="git_partial",
            strategy="git_head_dirty_settings",
            repo_root="F:/repo/demo",
            head_commit="abc123",
            head_ref="refs/heads/main",
            settings_fingerprint="settings-1",
            dirty_path_count=3,
            dirty_paths_sample=("src/a.py", "src/b.py"),
            elapsed_ms=18.5,
            timed_out=False,
            fallback_reason="",
            git_available=True,
            worktree_available=True,
        )
    )

    assert payload == {
        "fingerprint": "fp-abc",
        "trust_class": "git_partial",
        "strategy": "git_head_dirty_settings",
        "head_commit": "abc123",
        "head_ref": "refs/heads/main",
        "settings_fingerprint": "settings-1",
        "dirty_path_count": 3,
        "dirty_paths_sample": ["src/a.py", "src/b.py"],
        "elapsed_ms": 18.5,
        "timed_out": False,
        "fallback_reason": "",
        "git_available": True,
        "worktree_available": True,
    }


def test_build_git_fast_fingerprint_uses_head_dirty_summary_and_settings() -> None:
    fingerprint = build_git_fast_fingerprint(
        repo_root="F:/repo/demo",
        settings_fingerprint="settings-1",
        collect_head_snapshot_fn=lambda **_kwargs: {
            "enabled": True,
            "reason": "ok",
            "head_commit": "abc123",
            "head_ref": "main",
            "elapsed_ms": 5.0,
        },
        collect_worktree_summary_fn=lambda **_kwargs: {
            "enabled": True,
            "reason": "ok",
            "changed_count": 2,
            "entries": [
                {"path": "src/a.py", "status": "M "},
                {"path": "src/b.py", "status": "??"},
            ],
            "truncated": False,
            "elapsed_ms": 7.5,
        },
        build_worktree_state_token_fn=lambda summary, max_entries=32: "worktree-token",
    )

    assert fingerprint.trust_class == "exact"
    assert fingerprint.strategy == "git_head_dirty_settings"
    assert fingerprint.head_commit == "abc123"
    assert fingerprint.head_ref == "main"
    assert fingerprint.settings_fingerprint == "settings-1"
    assert fingerprint.dirty_path_count == 2
    assert fingerprint.dirty_paths_sample == ("src/a.py", "src/b.py")
    assert fingerprint.elapsed_ms == 12.5
    assert fingerprint.metadata == {
        "head_reason": "ok",
        "worktree_reason": "ok",
        "worktree_token": "worktree-token",
        "worktree_truncated": False,
    }


def test_build_git_fast_fingerprint_degrades_to_git_partial_on_timeout() -> None:
    fingerprint = build_git_fast_fingerprint(
        repo_root="F:/repo/demo",
        settings_fingerprint="settings-2",
        collect_head_snapshot_fn=lambda **_kwargs: {
            "enabled": True,
            "reason": "ok",
            "head_commit": "abc123",
            "head_ref": "",
        },
        collect_worktree_summary_fn=lambda **_kwargs: {
            "enabled": True,
            "reason": "timeout",
            "changed_count": 0,
            "entries": [],
            "truncated": False,
        },
        build_worktree_state_token_fn=lambda summary, max_entries=32: "timeout-token",
    )

    assert fingerprint.trust_class == "git_partial"
    assert fingerprint.timed_out is True
    assert fingerprint.fallback_reason == "timeout"


def test_build_git_fast_fingerprint_keeps_exact_when_only_diff_timeout_occurs() -> None:
    fingerprint = build_git_fast_fingerprint(
        repo_root="F:/repo/demo",
        settings_fingerprint="settings-diff-timeout",
        collect_head_snapshot_fn=lambda **_kwargs: {
            "enabled": True,
            "reason": "ok",
            "head_commit": "abc123",
            "head_ref": "main",
            "elapsed_ms": 5.0,
        },
        collect_worktree_summary_fn=lambda **_kwargs: {
            "enabled": True,
            "reason": "partial",
            "error": "diff_timeout",
            "changed_count": 2,
            "entries": [
                {"path": "src/a.py", "status": "M "},
                {"path": "src/b.py", "status": "??"},
            ],
            "truncated": False,
            "elapsed_ms": 7.5,
        },
        build_worktree_state_token_fn=lambda summary, max_entries=32: "diff-timeout-token",
    )

    assert fingerprint.trust_class == "exact"
    assert fingerprint.timed_out is False
    assert fingerprint.fallback_reason == ""
    assert fingerprint.metadata is not None
    assert fingerprint.metadata["worktree_reason"] == "partial"


def test_build_git_fast_fingerprint_uses_budgeted_subcall_timeouts() -> None:
    captured: dict[str, float | None] = {}

    def _collect_head(**kwargs: object) -> dict[str, object]:
        captured["head_timeout_seconds"] = kwargs.get("timeout_seconds")  # type: ignore[assignment]
        return {
            "enabled": True,
            "reason": "ok",
            "head_commit": "abc123",
            "head_ref": "main",
            "elapsed_ms": 4.0,
        }

    def _collect_worktree(**kwargs: object) -> dict[str, object]:
        captured["worktree_timeout_seconds"] = kwargs.get("timeout_seconds")  # type: ignore[assignment]
        return {
            "enabled": True,
            "reason": "timeout",
            "changed_count": 0,
            "entries": [],
            "truncated": False,
            "elapsed_ms": 12.0,
        }

    fingerprint = build_git_fast_fingerprint(
        repo_root="F:/repo/demo",
        settings_fingerprint="settings-3",
        timeout_seconds=1.0,
        latency_budget_ms=15.0,
        collect_head_snapshot_fn=_collect_head,
        collect_worktree_summary_fn=_collect_worktree,
        build_worktree_state_token_fn=lambda summary, max_entries=32: "budget-timeout-token",
    )

    assert captured["head_timeout_seconds"] == pytest.approx(0.015, rel=0, abs=1e-6)
    assert captured["worktree_timeout_seconds"] == pytest.approx(0.011, rel=0, abs=1e-6)
    assert fingerprint.trust_class == "git_partial"
    assert fingerprint.timed_out is True
    assert fingerprint.fallback_reason == "timeout"
    assert fingerprint.metadata is not None
    assert fingerprint.metadata["budget_ms"] == 15.0
    assert fingerprint.metadata["budget_exhausted"] is True
    assert fingerprint.metadata["downgrade_reason"] == "timeout"


def test_build_git_fast_fingerprint_falls_back_on_head_timeout_with_budget() -> None:
    captured: dict[str, float | None] = {}

    def _collect_head(**kwargs: object) -> dict[str, object]:
        captured["head_timeout_seconds"] = kwargs.get("timeout_seconds")  # type: ignore[assignment]
        return {
            "enabled": True,
            "reason": "timeout",
            "head_commit": "",
            "head_ref": "",
            "elapsed_ms": 6.0,
        }

    fingerprint = build_git_fast_fingerprint(
        repo_root="F:/repo/demo",
        latency_budget_ms=5.0,
        collect_head_snapshot_fn=_collect_head,
        collect_worktree_summary_fn=lambda **_kwargs: pytest.fail("worktree should be skipped"),
        build_worktree_state_token_fn=lambda summary, max_entries=32: "budget-head-timeout-token",
    )

    assert captured["head_timeout_seconds"] == pytest.approx(0.005, rel=0, abs=1e-6)
    assert fingerprint.trust_class == "fallback"
    assert fingerprint.timed_out is True
    assert fingerprint.fallback_reason == "timeout"
    assert fingerprint.metadata is not None
    assert fingerprint.metadata["worktree_reason"] == "budget_exhausted"
    assert fingerprint.metadata["budget_exhausted"] is True
    assert fingerprint.metadata["downgrade_reason"] == "timeout"


def test_build_git_fast_fingerprint_marks_budget_exceeded_when_collectors_overrun() -> None:
    fingerprint = build_git_fast_fingerprint(
        repo_root="F:/repo/demo",
        settings_fingerprint="settings-4",
        latency_budget_ms=10.0,
        collect_head_snapshot_fn=lambda **_kwargs: {
            "enabled": True,
            "reason": "ok",
            "head_commit": "abc123",
            "head_ref": "main",
            "elapsed_ms": 4.0,
        },
        collect_worktree_summary_fn=lambda **_kwargs: {
            "enabled": True,
            "reason": "ok",
            "changed_count": 1,
            "entries": [{"path": "src/a.py", "status": "M "}],
            "truncated": False,
            "elapsed_ms": 9.0,
        },
        build_worktree_state_token_fn=lambda summary, max_entries=32: "budget-overrun-token",
    )

    assert fingerprint.trust_class == "git_partial"
    assert fingerprint.timed_out is True
    assert fingerprint.fallback_reason == "latency_budget_exceeded"
    assert fingerprint.metadata is not None
    assert fingerprint.metadata["budget_exhausted"] is True
    assert fingerprint.metadata["downgrade_reason"] == "latency_budget_exceeded"
    assert fingerprint.metadata["budget_remaining_ms"] == 0.0


def test_build_git_fast_fingerprint_falls_back_when_head_missing() -> None:
    fingerprint = build_git_fast_fingerprint(
        repo_root="F:/repo/demo",
        collect_head_snapshot_fn=lambda **_kwargs: {
            "enabled": False,
            "reason": "not_git_repo",
            "head_commit": "",
            "head_ref": "",
        },
        collect_worktree_summary_fn=lambda **_kwargs: {
            "enabled": False,
            "reason": "not_git_repo",
            "changed_count": 0,
            "entries": [],
            "truncated": False,
        },
        build_worktree_state_token_fn=lambda summary, max_entries=32: "none",
    )

    assert fingerprint.trust_class == "fallback"
    assert fingerprint.fallback_reason == "not_git_repo"
    assert fingerprint.git_available is False
