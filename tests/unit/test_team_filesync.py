from __future__ import annotations

from pathlib import Path

from ace_lite.team.filesync import FileBasedTeamSync


def test_filesync_push_pull_roundtrip(tmp_path: Path) -> None:
    backend = FileBasedTeamSync(tmp_path / "shared")
    payload = [
        {
            "content": "remember release freeze checklist",
            "namespace": "repo:ace-lite",
            "updated_at": "2026-02-13T10:00:00+00:00",
            "metadata": {"source": "user"},
        }
    ]

    backend.push(payload, "repo:ace-lite")
    rows = backend.pull("repo:ace-lite")

    assert len(rows) == 1
    assert rows[0]["content"] == "remember release freeze checklist"
    assert str(rows[0]["handle"]).startswith("sha256:")


def test_filesync_resolve_conflicts_prefers_newer_updated_at(tmp_path: Path) -> None:
    backend = FileBasedTeamSync(tmp_path / "shared")
    shared_handle = "fact-1"
    remote = [
        {
            "handle": shared_handle,
            "content": "old",
            "namespace": "repo:ace-lite",
            "updated_at": "2026-02-13T08:00:00+00:00",
            "metadata": {},
        }
    ]
    local = [
        {
            "handle": shared_handle,
            "content": "new",
            "namespace": "repo:ace-lite",
            "updated_at": "2026-02-13T09:00:00+00:00",
            "metadata": {},
        }
    ]

    merged = backend.resolve_conflicts(local=local, remote=remote)
    assert len(merged) == 1
    assert merged[0]["content"] == "new"


def test_filesync_namespaces_are_container_isolated(tmp_path: Path) -> None:
    backend = FileBasedTeamSync(tmp_path / "shared")
    backend.push(
        [
            {
                "content": "repo-a fact",
                "namespace": "repo:a",
                "updated_at": "2026-02-13T10:00:00+00:00",
                "metadata": {},
            }
        ],
        "repo:a",
    )
    backend.push(
        [
            {
                "content": "repo-b fact",
                "namespace": "repo:b",
                "updated_at": "2026-02-13T10:00:00+00:00",
                "metadata": {},
            }
        ],
        "repo:b",
    )

    rows_a = backend.pull("repo:a")
    rows_b = backend.pull("repo:b")
    assert len(rows_a) == 1
    assert len(rows_b) == 1
    assert rows_a[0]["content"] == "repo-a fact"
    assert rows_b[0]["content"] == "repo-b fact"
