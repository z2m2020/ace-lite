from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from ace_lite.indexer import build_index, discover_source_files
from ace_lite.indexing_resilience import IndexingResilienceConfig, build_index_with_resilience
from ace_lite.parsers.treesitter_engine import TreeSitterEngine


def _write_sample_repo(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "fast.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "slow.py").write_text(
        "def mul(a: int, b: int) -> int:\n    return a * b\n",
        encoding="utf-8",
    )


def _hash_file_list(paths: list[str]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path).encode("utf-8", "ignore"))
        digest.update(b"\n")
    return digest.hexdigest()


def test_indexing_resilience_matches_baseline_build(tmp_path: Path) -> None:
    _write_sample_repo(tmp_path)
    baseline = build_index(tmp_path, languages=["python"])

    payload = build_index_with_resilience(
        tmp_path,
        languages=["python"],
        config=IndexingResilienceConfig(
            batch_size=1,
            resume=False,
            resume_state_path=Path("context-map/index.resume.test.json"),
        ),
    )

    assert payload["root_dir"] == baseline["root_dir"]
    assert payload["files"] == baseline["files"]
    assert payload["file_count"] == baseline["file_count"]
    assert "indexing_resilience" in payload
    assert payload["indexing_resilience"]["incomplete"] is False


def test_indexing_resilience_resume_state_continues_from_next_index(tmp_path: Path) -> None:
    _write_sample_repo(tmp_path)
    baseline = build_index(tmp_path, languages=["python"])

    root_path, enabled_languages, file_paths = discover_source_files(
        tmp_path, languages=["python"]
    )
    relative_paths = [path.relative_to(root_path).as_posix() for path in file_paths]
    assert relative_paths

    state_path = tmp_path / "context-map" / "index.resume.manual.json"
    journal_path = tmp_path / "context-map" / "index.resume.manual.journal.jsonl"

    first = relative_paths[0]
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    journal_path.write_text(
        json.dumps(
            {
                "type": "file",
                "path": first,
                "attempt": 0,
                "elapsed_ms": 1.0,
                "entry": baseline["files"][first],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    state_payload = {
        "schema_version": 1,
        "root_dir": str(root_path),
        "languages": list(enabled_languages),
        "file_list_sha256": _hash_file_list(relative_paths),
        "total_files": len(relative_paths),
        "next_index": 1,
        "created_at": "2026-02-01T00:00:00+00:00",
        "updated_at": "2026-02-01T00:00:00+00:00",
        "journal_path": str(journal_path),
        "stats": {
            "total_files": len(relative_paths),
            "processed_files": 1,
            "parsed_files": 1,
            "timed_out_files": 0,
            "failed_files": 0,
            "retried_files": 0,
            "retry_succeeded_files": 0,
        },
        "timed_out_files": [],
        "failed_files": [],
    }
    state_path.write_text(
        json.dumps(state_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    payload = build_index_with_resilience(
        tmp_path,
        languages=["python"],
        config=IndexingResilienceConfig(
            batch_size=1,
            resume=True,
            resume_state_path=state_path,
        ),
    )

    assert payload["files"] == baseline["files"]
    assert payload["indexing_resilience"]["stats"]["parsed_files"] == baseline["file_count"]


def test_indexing_resilience_timeout_and_retry(tmp_path: Path, monkeypatch) -> None:
    _write_sample_repo(tmp_path)

    def fake_parse_file(self: TreeSitterEngine, file_path: Path, root_path: Path):
        relative = file_path.relative_to(root_path).as_posix()
        if file_path.name == "slow.py":
            time.sleep(0.07)
        else:
            time.sleep(0.005)
        return {
            "path": relative,
            "language": "python",
            "module": relative.replace("/", ".").replace(".py", ""),
            "sha256": "0" * 64,
            "symbols": [],
            "imports": [],
            "references": [],
        }

    monkeypatch.setattr(TreeSitterEngine, "parse_file", fake_parse_file)

    payload = build_index_with_resilience(
        tmp_path,
        languages=["python"],
        config=IndexingResilienceConfig(
            batch_size=2,
            timeout_per_file_seconds=0.05,
            retry_timeouts=True,
            retry_timeout_multiplier=5.0,
            resume_state_path=Path("context-map/index.resume.timeout.json"),
        ),
    )

    assert payload["file_count"] == 2
    resilience = payload["indexing_resilience"]
    assert resilience["stats"]["retried_files"] == 1
    assert resilience["stats"]["retry_succeeded_files"] == 1
    assert resilience["stats"]["timed_out_files"] == 0
    assert resilience["timed_out_files"] == []


def test_indexing_resilience_subprocess_batch_matches_baseline(tmp_path: Path) -> None:
    _write_sample_repo(tmp_path)
    baseline = build_index(tmp_path, languages=["python"])

    payload = build_index_with_resilience(
        tmp_path,
        languages=["python"],
        config=IndexingResilienceConfig(
            batch_size=1,
            subprocess_batch=True,
            resume_state_path=Path("context-map/index.resume.subproc.json"),
        ),
    )

    assert payload["files"] == baseline["files"]
