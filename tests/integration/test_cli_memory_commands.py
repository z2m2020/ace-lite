from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

import ace_lite.cli as cli_module
from ace_lite.memory_long_term.contracts import build_long_term_fact_contract_v1
from ace_lite.memory_long_term.store import LongTermMemoryStore


def _cli_env(root: Path) -> dict[str, str]:
    return {"HOME": str(root), "USERPROFILE": str(root)}


def test_cli_memory_store_search_and_wipe(tmp_path: Path) -> None:
    runner = CliRunner()
    notes_path = tmp_path / "context-map" / "memory_notes.jsonl"

    store_a = runner.invoke(
        cli_module.cli,
        [
            "memory",
            "store",
            "Fix auth fallback logic",
            "--namespace",
            "repo:a",
            "--tag",
            "kind=bugfix",
            "--notes-path",
            str(notes_path),
        ],
        env=_cli_env(tmp_path),
    )
    assert store_a.exit_code == 0

    store_b = runner.invoke(
        cli_module.cli,
        [
            "memory",
            "store",
            "Refactor benchmark report formatting",
            "--namespace",
            "repo:b",
            "--notes-path",
            str(notes_path),
        ],
        env=_cli_env(tmp_path),
    )
    assert store_b.exit_code == 0

    search_a = runner.invoke(
        cli_module.cli,
        [
            "memory",
            "search",
            "fix auth",
            "--namespace",
            "repo:a",
            "--notes-path",
            str(notes_path),
        ],
        env=_cli_env(tmp_path),
    )
    assert search_a.exit_code == 0
    search_a_payload = json.loads(search_a.output)
    assert search_a_payload["count"] == 1
    assert search_a_payload["items"][0]["namespace"] == "repo:a"

    wipe_a = runner.invoke(
        cli_module.cli,
        [
            "memory",
            "wipe",
            "--namespace",
            "repo:a",
            "--notes-path",
            str(notes_path),
        ],
        env=_cli_env(tmp_path),
    )
    assert wipe_a.exit_code == 0
    wipe_a_payload = json.loads(wipe_a.output)
    assert wipe_a_payload["removed_count"] == 1

    search_all = runner.invoke(
        cli_module.cli,
        [
            "memory",
            "search",
            "refactor",
            "--notes-path",
            str(notes_path),
        ],
        env=_cli_env(tmp_path),
    )
    assert search_all.exit_code == 0
    search_all_payload = json.loads(search_all.output)
    assert search_all_payload["count"] == 1
    assert search_all_payload["items"][0]["namespace"] == "repo:b"


def test_cli_memory_store_accepts_task_level_slots(tmp_path: Path) -> None:
    runner = CliRunner()
    notes_path = tmp_path / "context-map" / "memory_notes.jsonl"

    result = runner.invoke(
        cli_module.cli,
        [
            "memory",
            "store",
            "EXPL-01 trace constraints",
            "--namespace",
            "repo:a",
            "--req",
            "EXPL-01",
            "--contract",
            "trace-v1",
            "--area",
            "retrieval",
            "--decision-type",
            "constraint",
            "--task-id",
            "TASK-123",
            "--notes-path",
            str(notes_path),
        ],
        env=_cli_env(tmp_path),
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["stored"]["tags"]["req"] == "EXPL-01"
    assert payload["stored"]["tags"]["contract"] == "trace-v1"
    assert payload["stored"]["tags"]["area"] == "retrieval"
    assert payload["stored"]["tags"]["decision_type"] == "constraint"
    assert payload["stored"]["tags"]["task_id"] == "TASK-123"
    assert payload["stored"]["req"] == "EXPL-01"


def test_cli_memory_vacuum_prunes_expired_notes_idempotent(tmp_path: Path) -> None:
    runner = CliRunner()
    notes_path = tmp_path / "context-map" / "memory_notes.jsonl"
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    notes_path.write_text(
        "\n".join(
            [
                '{"text":"stale","namespace":"repo:a","captured_at":"2020-01-01T00:00:00+00:00"}',
                '{"text":"fresh","namespace":"repo:a","captured_at":"2099-01-01T00:00:00+00:00"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    first = runner.invoke(
        cli_module.cli,
        [
            "memory",
            "vacuum",
            "--namespace",
            "repo:a",
            "--notes-path",
            str(notes_path),
            "--ttl-days",
            "90",
            "--max-age-days",
            "365",
        ],
        env=_cli_env(tmp_path),
    )
    assert first.exit_code == 0
    first_payload = json.loads(first.output)
    assert first_payload["removed_count"] == 1

    second = runner.invoke(
        cli_module.cli,
        [
            "memory",
            "vacuum",
            "--namespace",
            "repo:a",
            "--notes-path",
            str(notes_path),
            "--ttl-days",
            "90",
            "--max-age-days",
            "365",
        ],
        env=_cli_env(tmp_path),
    )
    assert second.exit_code == 0
    second_payload = json.loads(second.output)
    assert second_payload["removed_count"] == 0

    search = runner.invoke(
        cli_module.cli,
        [
            "memory",
            "search",
            "fresh",
            "--namespace",
            "repo:a",
            "--notes-path",
            str(notes_path),
        ],
        env=_cli_env(tmp_path),
    )
    assert search.exit_code == 0
    search_payload = json.loads(search.output)
    assert search_payload["count"] == 1
    assert search_payload["items"][0]["text"] == "fresh"


def test_cli_memory_graph_outputs_read_only_ltm_view(tmp_path: Path) -> None:
    runner = CliRunner()
    db_path = tmp_path / "context-map" / "long_term_memory.db"
    store = LongTermMemoryStore(db_path=db_path)
    store.upsert_fact(
        build_long_term_fact_contract_v1(
            fact_id="fact-1",
            fact_type="repo_policy",
            subject="runtime.validation.git",
            predicate="fallback_policy",
            object_value="reuse_checkout_or_skip",
            repo="ace-lite",
            namespace="repo/ace-lite",
            user_id="tester",
            profile_key="bugfix",
            as_of="2026-03-19T09:44:00+08:00",
            valid_from="2026-03-19T09:44:00+08:00",
            derived_from_observation_id="obs-1",
        )
    )
    store.upsert_fact(
        build_long_term_fact_contract_v1(
            fact_id="fact-2",
            fact_type="repo_policy",
            subject="reuse_checkout_or_skip",
            predicate="recommended_for",
            object_value="runtime.validation.git",
            repo="ace-lite",
            namespace="repo/ace-lite",
            user_id="tester",
            profile_key="bugfix",
            as_of="2026-03-19T09:43:00+08:00",
            valid_from="2026-03-19T09:43:00+08:00",
            derived_from_observation_id="obs-2",
        )
    )

    result = runner.invoke(
        cli_module.cli,
        [
            "memory",
            "graph",
            "--db-path",
            str(db_path),
            "--fact-handle",
            "fact-1",
            "--max-hops",
            "2",
            "--limit",
            "8",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["schema_version"] == "ltm_graph_view_v1"
    assert payload["focus"]["handle"] == "fact-1"
    assert payload["summary"]["triple_count"] == 2
    assert payload["edges"][0]["is_focus"] is True
