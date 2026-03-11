from __future__ import annotations

import pytest

from ace_lite.runtime_fingerprint import (
    GIT_FAST_FINGERPRINT_TRUST_CLASSES,
    GitFastFingerprint,
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
