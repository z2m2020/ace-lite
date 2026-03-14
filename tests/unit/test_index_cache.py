from __future__ import annotations

import json
import os
from pathlib import Path

import ace_lite.index_cache as index_cache


def test_save_and_load_index_cache_roundtrip(tmp_path: Path) -> None:
    cache_path = tmp_path / "context-map" / "index.json"
    payload = {
        "root_dir": str(tmp_path.resolve()),
        "configured_languages": ["python"],
        "files": {},
    }

    index_cache.save_index_cache(payload=payload, cache_path=cache_path)
    loaded = index_cache.load_index_cache(
        cache_path=cache_path,
        root_dir=tmp_path,
        languages=["python"],
    )

    assert loaded is not None
    assert loaded["root_dir"] == str(tmp_path.resolve())


def test_load_index_cache_rejects_root_or_language_mismatch(tmp_path: Path) -> None:
    cache_path = tmp_path / "index.json"
    payload = {
        "root_dir": str((tmp_path / "another").resolve()),
        "configured_languages": ["python"],
        "files": {},
    }
    cache_path.write_text(json.dumps(payload), encoding="utf-8")

    assert (
        index_cache.load_index_cache(
            cache_path=cache_path, root_dir=tmp_path, languages=["python"]
        )
        is None
    )

    payload["root_dir"] = str(tmp_path.resolve())
    cache_path.write_text(json.dumps(payload), encoding="utf-8")

    assert (
        index_cache.load_index_cache(
            cache_path=cache_path, root_dir=tmp_path, languages=["go"]
        )
        is None
    )


def test_load_index_cache_rejects_git_head_mismatch(
    tmp_path: Path, monkeypatch
) -> None:
    cache_path = tmp_path / "index.json"
    payload = {
        "root_dir": str(tmp_path.resolve()),
        "configured_languages": ["python"],
        "git_head_sha": "a" * 40,
        "files": {},
    }
    cache_path.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(index_cache, "_get_git_head_sha", lambda **_: "b" * 40)

    assert (
        index_cache.load_index_cache(
            cache_path=cache_path,
            root_dir=tmp_path,
            languages=["python"],
        )
        is None
    )


def test_build_or_refresh_index_cache_only_when_no_changes(
    tmp_path: Path, monkeypatch
) -> None:
    cache_path = tmp_path / "context-map" / "index.json"
    initial = {
        "root_dir": str(tmp_path.resolve()),
        "configured_languages": ["python"],
        "files": {"a.py": {"path": "a.py"}},
    }
    index_cache.save_index_cache(payload=initial, cache_path=cache_path)

    monkeypatch.setattr(index_cache, "detect_changed_files_from_git", lambda **_: [])

    payload, info = index_cache.build_or_refresh_index(
        root_dir=tmp_path,
        cache_path=cache_path,
        languages=["python"],
        incremental=True,
    )

    assert payload["files"] == initial["files"]
    assert info["cache_hit"] is True
    assert info["mode"] == "cache_only"
    assert info["changed_files"] == 0


def test_build_or_refresh_index_cache_only_when_only_non_indexable_changes(
    tmp_path: Path, monkeypatch
) -> None:
    cache_path = tmp_path / "context-map" / "index.json"
    initial = {
        "root_dir": str(tmp_path.resolve()),
        "configured_languages": ["python"],
        "files": {"a.py": {"path": "a.py"}},
    }
    index_cache.save_index_cache(payload=initial, cache_path=cache_path)

    monkeypatch.setattr(
        index_cache,
        "detect_changed_files_from_git",
        lambda **_: [
            "README.md",
            "docs/ARCHITECTURE.md",
            "artifacts/benchmark/summary.json",
            "context-map/index.json",
        ],
    )

    def fail_update_index(*_args, **_kwargs):
        raise AssertionError("update_index should not run for non-indexable changes")

    monkeypatch.setattr(index_cache, "update_index", fail_update_index)

    payload, info = index_cache.build_or_refresh_index(
        root_dir=tmp_path,
        cache_path=cache_path,
        languages=["python"],
        incremental=True,
    )

    assert payload["files"] == initial["files"]
    assert info["cache_hit"] is True
    assert info["mode"] == "cache_only"
    assert info["changed_files"] == 0
    assert info.get("reason") == "non_indexable_changes"
    assert info.get("changed_files_detected") == 4


def test_build_or_refresh_index_does_not_rewrite_cache_for_non_indexable_changes_when_aceignore_unchanged(
    tmp_path: Path, monkeypatch
) -> None:
    cache_path = tmp_path / "context-map" / "index.json"
    initial = {
        "root_dir": str(tmp_path.resolve()),
        "configured_languages": ["python"],
        "files": {"a.py": {"path": "a.py"}},
        "aceignore": {"present": False, "mtime_ns": 0, "size_bytes": 0},
    }
    index_cache.save_index_cache(payload=initial, cache_path=cache_path)

    monkeypatch.setattr(
        index_cache,
        "detect_changed_files_from_git",
        lambda **_: ["README.md", "docs/ARCHITECTURE.md"],
    )

    save_calls = {"count": 0}
    original_save = index_cache.save_index_cache

    def tracking_save(*, payload, cache_path):  # type: ignore[no-untyped-def]
        save_calls["count"] += 1
        return original_save(payload=payload, cache_path=cache_path)

    monkeypatch.setattr(index_cache, "save_index_cache", tracking_save)

    payload, info = index_cache.build_or_refresh_index(
        root_dir=tmp_path,
        cache_path=cache_path,
        languages=["python"],
        incremental=True,
    )

    assert payload["files"] == initial["files"]
    assert info["mode"] == "cache_only"
    assert info.get("reason") == "non_indexable_changes"
    assert save_calls["count"] == 0


def test_detect_changed_files_from_git_reuses_short_ttl_cache(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("ACE_LITE_GIT_STATUS_CACHE_TTL_SECONDS", "5")
    monkeypatch.setattr(index_cache, "_GIT_STATUS_MEMORY_CACHE", {})
    monkeypatch.setattr(index_cache, "_get_git_head_sha", lambda **_: "a" * 40)
    monkeypatch.setattr(index_cache, "_git_index_fingerprint", lambda **_: (0, 0))

    calls = {"count": 0}

    def fake_run_capture_output(*_args, **_kwargs):
        calls["count"] += 1
        return 0, " M src/app.py\x00?? README.md\x00", "", False

    clock = iter([100.0, 100.2, 100.3])
    monkeypatch.setattr(index_cache, "run_capture_output", fake_run_capture_output)
    monkeypatch.setattr(index_cache, "monotonic", lambda: next(clock))

    first = index_cache.detect_changed_files_from_git(root_dir=tmp_path)
    second = index_cache.detect_changed_files_from_git(root_dir=tmp_path)

    assert first == ["src/app.py", "README.md"]
    assert second == first
    assert calls["count"] == 1


def test_build_or_refresh_index_incremental_update(tmp_path: Path, monkeypatch) -> None:
    cache_path = tmp_path / "context-map" / "index.json"
    initial = {
        "root_dir": str(tmp_path.resolve()),
        "configured_languages": ["python"],
        "files": {"old.py": {"path": "old.py"}},
    }
    index_cache.save_index_cache(payload=initial, cache_path=cache_path)

    (tmp_path / "new.py").write_text("print('hi')\n", encoding="utf-8")
    monkeypatch.setattr(
        index_cache, "detect_changed_files_from_git", lambda **_: ["new.py"]
    )

    def fake_update(existing_index, root_dir, changed_files, languages=None):
        updated = dict(existing_index)
        updated["files"] = {"new.py": {"path": "new.py"}}
        updated["configured_languages"] = ["python"]
        updated["root_dir"] = str(Path(root_dir).resolve())
        return updated

    monkeypatch.setattr(index_cache, "update_index", fake_update)

    payload, info = index_cache.build_or_refresh_index(
        root_dir=tmp_path,
        cache_path=cache_path,
        languages=["python"],
        incremental=True,
    )

    assert "new.py" in payload["files"]
    assert info["cache_hit"] is True
    assert info["mode"] == "incremental_update"
    assert info["changed_files"] == 1


def test_build_or_refresh_index_cache_only_when_dirty_worktree_has_no_effective_changes(
    tmp_path: Path, monkeypatch
) -> None:
    cache_path = tmp_path / "context-map" / "index.json"
    tracked = tmp_path / "a.py"
    tracked.write_text("print('stable')\n", encoding="utf-8")
    stat_result = tracked.stat()
    mtime_ns = int(getattr(stat_result, "st_mtime_ns", 0) or 0)
    size_bytes = int(getattr(stat_result, "st_size", 0) or 0)

    initial = {
        "root_dir": str(tmp_path.resolve()),
        "configured_languages": ["python"],
        "files": {
            "a.py": {
                "path": "a.py",
                "mtime_ns": mtime_ns,
                "size_bytes": size_bytes,
            }
        },
    }
    index_cache.save_index_cache(payload=initial, cache_path=cache_path)

    monkeypatch.setattr(index_cache, "detect_changed_files_from_git", lambda **_: ["a.py"])

    def fail_update_index(*_args, **_kwargs):
        raise AssertionError("update_index should not run when no effective changes")

    monkeypatch.setattr(index_cache, "update_index", fail_update_index)

    payload, info = index_cache.build_or_refresh_index(
        root_dir=tmp_path,
        cache_path=cache_path,
        languages=["python"],
        incremental=True,
    )

    assert payload["files"] == initial["files"]
    assert info["cache_hit"] is True
    assert info["mode"] == "cache_only"
    assert info["changed_files"] == 0
    assert info.get("changed_files_detected") == 1
    assert info.get("reason") == "worktree_dirty_no_effective_changes"


def test_build_or_refresh_index_does_not_rewrite_cache_for_no_effective_changes_when_aceignore_unchanged(
    tmp_path: Path, monkeypatch
) -> None:
    cache_path = tmp_path / "context-map" / "index.json"
    tracked = tmp_path / "a.py"
    tracked.write_text("print('stable')\n", encoding="utf-8")
    stat_result = tracked.stat()
    mtime_ns = int(getattr(stat_result, "st_mtime_ns", 0) or 0)
    size_bytes = int(getattr(stat_result, "st_size", 0) or 0)

    initial = {
        "root_dir": str(tmp_path.resolve()),
        "configured_languages": ["python"],
        "files": {
            "a.py": {
                "path": "a.py",
                "mtime_ns": mtime_ns,
                "size_bytes": size_bytes,
            }
        },
        "aceignore": {"present": False, "mtime_ns": 0, "size_bytes": 0},
    }
    index_cache.save_index_cache(payload=initial, cache_path=cache_path)

    monkeypatch.setattr(index_cache, "detect_changed_files_from_git", lambda **_: ["a.py"])

    save_calls = {"count": 0}
    original_save = index_cache.save_index_cache

    def tracking_save(*, payload, cache_path):  # type: ignore[no-untyped-def]
        save_calls["count"] += 1
        return original_save(payload=payload, cache_path=cache_path)

    monkeypatch.setattr(index_cache, "save_index_cache", tracking_save)

    payload, info = index_cache.build_or_refresh_index(
        root_dir=tmp_path,
        cache_path=cache_path,
        languages=["python"],
        incremental=True,
    )

    assert payload["files"] == initial["files"]
    assert info["mode"] == "cache_only"
    assert info.get("reason") == "worktree_dirty_no_effective_changes"
    assert save_calls["count"] == 0


def test_build_or_refresh_index_full_build_when_aceignore_changes(
    tmp_path: Path, monkeypatch
) -> None:
    cache_path = tmp_path / "context-map" / "index.json"
    (tmp_path / ".aceignore").write_text("artifacts/\n", encoding="utf-8")
    initial = {
        "root_dir": str(tmp_path.resolve()),
        "configured_languages": ["python"],
        "files": {"old.py": {"path": "old.py"}},
    }
    index_cache.save_index_cache(payload=initial, cache_path=cache_path)

    monkeypatch.setattr(
        index_cache, "detect_changed_files_from_git", lambda **_: [".aceignore"]
    )

    calls = {"build": 0, "update": 0}

    def fake_build_index(root_dir, languages=None):
        calls["build"] += 1
        return {
            "root_dir": str(Path(root_dir).resolve()),
            "configured_languages": ["python"],
            "files": {"rebuilt.py": {"path": "rebuilt.py"}},
        }

    def fake_update_index(*_args, **_kwargs):
        calls["update"] += 1
        raise AssertionError("update_index should not run when .aceignore changed")

    monkeypatch.setattr(index_cache, "build_index", fake_build_index)
    monkeypatch.setattr(index_cache, "update_index", fake_update_index)

    payload, info = index_cache.build_or_refresh_index(
        root_dir=tmp_path,
        cache_path=cache_path,
        languages=["python"],
        incremental=True,
    )

    assert calls == {"build": 1, "update": 0}
    assert payload["files"] == {"rebuilt.py": {"path": "rebuilt.py"}}
    assert info["cache_hit"] is True
    assert info["mode"] == "full_build"
    assert info.get("reason") == "aceignore_changed"


def test_build_or_refresh_index_cache_only_when_aceignore_is_already_indexed(
    tmp_path: Path, monkeypatch
) -> None:
    cache_path = tmp_path / "context-map" / "index.json"
    aceignore_path = tmp_path / ".aceignore"
    aceignore_path.write_text("artifacts/\n", encoding="utf-8")
    stat_result = aceignore_path.stat()
    initial = {
        "root_dir": str(tmp_path.resolve()),
        "configured_languages": ["python"],
        "files": {"old.py": {"path": "old.py"}},
        "aceignore": {
            "present": True,
            "mtime_ns": int(getattr(stat_result, "st_mtime_ns", 0) or 0),
            "size_bytes": int(getattr(stat_result, "st_size", 0) or 0),
        },
    }
    index_cache.save_index_cache(payload=initial, cache_path=cache_path)

    monkeypatch.setattr(
        index_cache, "detect_changed_files_from_git", lambda **_: [".aceignore"]
    )

    def fail_build_index(*_args, **_kwargs):
        raise AssertionError("build_index should not run when .aceignore is unchanged")

    def fail_update_index(*_args, **_kwargs):
        raise AssertionError("update_index should not run when .aceignore is unchanged")

    monkeypatch.setattr(index_cache, "build_index", fail_build_index)
    monkeypatch.setattr(index_cache, "update_index", fail_update_index)

    payload, info = index_cache.build_or_refresh_index(
        root_dir=tmp_path,
        cache_path=cache_path,
        languages=["python"],
        incremental=True,
    )

    assert payload["files"] == initial["files"]
    assert info["cache_hit"] is True
    assert info["mode"] == "cache_only"
    assert info["changed_files"] == 0
    assert info.get("reason") == "aceignore_unchanged"


def test_build_or_refresh_index_rebuilds_when_git_head_changes(
    tmp_path: Path, monkeypatch
) -> None:
    cache_path = tmp_path / "context-map" / "index.json"
    calls = {"build": 0}

    current_sha = {"value": "a" * 40}

    def fake_get_git_head_sha(**_):
        return current_sha["value"]

    def fake_build_index(root_dir, languages=None):
        calls["build"] += 1
        return {
            "root_dir": str(Path(root_dir).resolve()),
            "configured_languages": ["python"],
            "files": {
                f"file-{calls['build']}.py": {"path": f"file-{calls['build']}.py"}
            },
        }

    monkeypatch.setattr(index_cache, "_get_git_head_sha", fake_get_git_head_sha)
    monkeypatch.setattr(index_cache, "build_index", fake_build_index)
    monkeypatch.setattr(index_cache, "detect_changed_files_from_git", lambda **_: [])

    first_payload, first_info = index_cache.build_or_refresh_index(
        root_dir=tmp_path,
        cache_path=cache_path,
        languages=["python"],
        incremental=True,
    )

    assert calls["build"] == 1
    assert first_info == {"cache_hit": False, "mode": "full_build", "changed_files": 0}
    assert first_payload.get("git_head_sha") == "a" * 40

    current_sha["value"] = "b" * 40

    second_payload, second_info = index_cache.build_or_refresh_index(
        root_dir=tmp_path,
        cache_path=cache_path,
        languages=["python"],
        incremental=True,
    )

    assert calls["build"] == 2
    assert second_info == {"cache_hit": False, "mode": "full_build", "changed_files": 0}
    assert second_payload.get("git_head_sha") == "b" * 40


def test_load_index_cache_memory_cache_mtime_change_triggers_reload(
    tmp_path: Path, monkeypatch
) -> None:
    cache_path = tmp_path / "context-map" / "index.json"
    payload = {
        "root_dir": str(tmp_path.resolve()),
        "configured_languages": ["python"],
        "files": {"a.py": {"path": "a.py"}},
    }

    index_cache.save_index_cache(payload=payload, cache_path=cache_path)

    calls = {"count": 0}
    original = Path.read_text

    def tracked(self: Path, *args, **kwargs):
        calls["count"] += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", tracked)

    first = index_cache.load_index_cache(
        cache_path=cache_path, root_dir=tmp_path, languages=["python"]
    )
    assert first is not None
    assert calls["count"] == 1

    updated = {
        "root_dir": str(tmp_path.resolve()),
        "configured_languages": ["python"],
        "files": {"b.py": {"path": "b.py"}},
    }

    previous_mtime_ns = cache_path.stat().st_mtime_ns
    cache_path.write_text(json.dumps(updated), encoding="utf-8")
    next_mtime_ns = previous_mtime_ns + 1_000_000_000
    os.utime(cache_path, ns=(next_mtime_ns, next_mtime_ns))

    second = index_cache.load_index_cache(
        cache_path=cache_path, root_dir=tmp_path, languages=["python"]
    )
    assert second is not None
    assert second is not first
    assert second["files"] == updated["files"]
    assert calls["count"] == 2


def test_load_index_cache_memory_cache_hit_avoids_disk_read(
    tmp_path: Path, monkeypatch
) -> None:
    cache_path = tmp_path / "context-map" / "index.json"
    payload = {
        "root_dir": str(tmp_path.resolve()),
        "configured_languages": ["python"],
        "files": {},
    }

    index_cache.save_index_cache(payload=payload, cache_path=cache_path)

    calls = {"count": 0}
    original = Path.read_text

    def tracked(self: Path, *args, **kwargs):
        calls["count"] += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", tracked)

    first = index_cache.load_index_cache(
        cache_path=cache_path, root_dir=tmp_path, languages=["python"]
    )
    second = index_cache.load_index_cache(
        cache_path=cache_path, root_dir=tmp_path, languages=["python"]
    )

    assert first is not None
    assert second is first
    assert calls["count"] == 1


def test_get_git_head_sha_times_out_gracefully(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ACE_LITE_GIT_TIMEOUT_SECONDS", "0.25")
    (tmp_path / ".git").mkdir()

    observed: dict[str, object] = {}

    def fake_run_capture_output(*args, **kwargs):
        observed.update(kwargs)
        return 1, "", "", True

    monkeypatch.setattr(index_cache, "run_capture_output", fake_run_capture_output)

    assert index_cache._get_git_head_sha(root_dir=tmp_path) is None
    assert observed.get("timeout_seconds") == 0.25


def test_get_git_head_sha_prefers_fast_ref_read(tmp_path: Path, monkeypatch) -> None:
    git_dir = tmp_path / ".git"
    (git_dir / "refs" / "heads").mkdir(parents=True)
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    expected_sha = "a" * 40
    (git_dir / "refs" / "heads" / "main").write_text(expected_sha, encoding="utf-8")

    def fail_run_capture_output(*_args, **_kwargs):
        raise AssertionError("run_capture_output should not be called on fast path")

    monkeypatch.setattr(index_cache, "run_capture_output", fail_run_capture_output)

    assert index_cache._get_git_head_sha(root_dir=tmp_path) == expected_sha


def test_get_git_head_sha_reads_packed_refs_when_ref_file_missing(
    tmp_path: Path, monkeypatch
) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    expected_sha = "b" * 40
    (git_dir / "packed-refs").write_text(
        "\n".join(["# pack-refs with: peeled fully-peeled", f"{expected_sha} refs/heads/main"]),
        encoding="utf-8",
    )

    def fail_run_capture_output(*_args, **_kwargs):
        raise AssertionError("run_capture_output should not be called on packed-refs fast path")

    monkeypatch.setattr(index_cache, "run_capture_output", fail_run_capture_output)

    assert index_cache._get_git_head_sha(root_dir=tmp_path) == expected_sha


def test_load_index_cache_uses_supplied_current_sha_without_git_call(
    tmp_path: Path, monkeypatch
) -> None:
    cache_path = tmp_path / "context-map" / "index.json"
    payload = {
        "root_dir": str(tmp_path.resolve()),
        "configured_languages": ["python"],
        "git_head_sha": "c" * 40,
        "files": {},
    }
    index_cache.save_index_cache(payload=payload, cache_path=cache_path)

    def fail_get_git_head_sha(**_kwargs):
        raise AssertionError("_get_git_head_sha should not be called when current_sha provided")

    monkeypatch.setattr(index_cache, "_get_git_head_sha", fail_get_git_head_sha)

    loaded = index_cache.load_index_cache(
        cache_path=cache_path,
        root_dir=tmp_path,
        languages=["python"],
        current_sha="c" * 40,
    )
    assert loaded is not None
    assert loaded.get("git_head_sha") == "c" * 40


def test_detect_changed_files_times_out_gracefully(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ACE_LITE_GIT_TIMEOUT_SECONDS", "0.25")
    (tmp_path / ".git").mkdir()

    observed: dict[str, object] = {}

    def fake_run_capture_output(*args, **kwargs):
        observed.update(kwargs)
        return 1, "", "", True

    monkeypatch.setattr(index_cache, "run_capture_output", fake_run_capture_output)

    assert index_cache.detect_changed_files_from_git(root_dir=tmp_path) == []
    assert observed.get("timeout_seconds") == 0.25


def test_detect_changed_files_parses_porcelain_z_rename(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / ".git").mkdir()

    stdout = " M src/app.py\0R  src/old.py\0src/new.py\0?? docs/read me.md\0"

    def fake_run_capture_output(*args, **kwargs):
        return 0, stdout, "", False

    monkeypatch.setattr(index_cache, "run_capture_output", fake_run_capture_output)

    changed = index_cache.detect_changed_files_from_git(root_dir=tmp_path)
    assert changed == [
        "src/app.py",
        "src/old.py",
        "src/new.py",
        "docs/read me.md",
    ]


def test_expand_changed_files_with_reverse_dependencies_depth_two() -> None:
    files = {
        "src/a.py": {
            "module": "demo.a",
            "imports": [],
        },
        "src/b.py": {
            "module": "demo.b",
            "imports": [{"module": "demo.a"}],
        },
        "src/c.py": {
            "module": "demo.c",
            "imports": [{"module": "demo.b"}],
        },
    }
    expanded, added = index_cache.expand_changed_files_with_reverse_dependencies(
        changed_files=["src/a.py"],
        index_files=files,
        max_depth=2,
        max_extra=16,
    )

    assert expanded == ["src/a.py", "src/b.py", "src/c.py"]
    assert added == 2


def test_build_or_refresh_index_expands_reverse_dependencies(
    tmp_path: Path, monkeypatch
) -> None:
    cache_path = tmp_path / "context-map" / "index.json"
    initial = {
        "root_dir": str(tmp_path.resolve()),
        "configured_languages": ["python"],
        "files": {
            "src/a.py": {"module": "demo.a", "imports": []},
            "src/b.py": {"module": "demo.b", "imports": [{"module": "demo.a"}]},
        },
    }
    index_cache.save_index_cache(payload=initial, cache_path=cache_path)

    monkeypatch.setattr(
        index_cache,
        "detect_changed_files_from_git",
        lambda **_: ["src/a.py"],
    )
    monkeypatch.setenv("ACE_LITE_INDEX_REVERSE_DEP_DEPTH", "1")

    observed: dict[str, object] = {}

    def fake_update(existing_index, root_dir, changed_files, languages=None):
        observed["changed_files"] = list(changed_files)
        updated = dict(existing_index)
        updated["files"] = dict(existing_index.get("files") or {})
        return updated

    monkeypatch.setattr(index_cache, "update_index", fake_update)

    _payload, info = index_cache.build_or_refresh_index(
        root_dir=tmp_path,
        cache_path=cache_path,
        languages=["python"],
        incremental=True,
    )

    assert observed["changed_files"] == ["src/a.py", "src/b.py"]
    assert info["mode"] == "incremental_update"
    assert info["changed_files"] == 2
    assert info["reverse_dependencies_added"] == 1
