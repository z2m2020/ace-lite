from __future__ import annotations

from ace_lite.chunk_cache_contract import (
    CHUNK_CACHE_CONTRACT_SCHEMA_VERSION,
    CHUNK_FINGERPRINT_SCHEMA_VERSION,
    build_chunk_cache_contract,
    build_chunk_fingerprint_records,
    diff_chunk_cache_contract_paths,
)


def _sample_entry() -> dict[str, object]:
    return {
        "module": "src.demo",
        "language": "python",
        "symbols": [
            {
                "kind": "class",
                "name": "DemoService",
                "qualified_name": "src.demo.DemoService",
                "lineno": 3,
                "end_lineno": 8,
            },
            {
                "kind": "method",
                "name": "run",
                "qualified_name": "src.demo.DemoService.run",
                "lineno": 4,
                "end_lineno": 6,
            },
        ],
        "imports": [{"type": "from", "module": "pkg.auth", "name": "validate"}],
        "references": [{"qualified_name": "pkg.auth.validate"}],
    }


def test_build_chunk_fingerprint_records_is_stable() -> None:
    first = build_chunk_fingerprint_records(path="src/demo.py", entry=_sample_entry())
    second = build_chunk_fingerprint_records(path="src/demo.py", entry=_sample_entry())

    assert first == second
    assert len(first) == 2
    assert all(item["fingerprint"] for item in first)
    assert all("|" in str(item["key"]) for item in first)


def test_build_chunk_fingerprint_records_change_when_references_change() -> None:
    baseline = build_chunk_fingerprint_records(path="src/demo.py", entry=_sample_entry())
    changed_entry = _sample_entry()
    changed_entry["references"] = [{"qualified_name": "pkg.auth.refresh"}]
    changed = build_chunk_fingerprint_records(path="src/demo.py", entry=changed_entry)

    assert baseline[0]["key"] == changed[0]["key"]
    assert baseline[0]["fingerprint"] != changed[0]["fingerprint"]


def test_build_chunk_cache_contract_includes_summary_and_file_fingerprint() -> None:
    contract = build_chunk_cache_contract({"src/demo.py": _sample_entry()})

    assert contract["schema_version"] == CHUNK_CACHE_CONTRACT_SCHEMA_VERSION
    assert contract["file_count"] == 1
    assert contract["chunk_count"] == 2
    assert contract["fingerprint"]
    assert contract["files"]["src/demo.py"]["chunk_count"] == 2
    assert contract["files"]["src/demo.py"]["fingerprint"]


def test_chunk_fingerprint_schema_version_is_exposed() -> None:
    assert CHUNK_FINGERPRINT_SCHEMA_VERSION == "chunk-fingerprint-v1"


def test_diff_chunk_cache_contract_paths_detects_changed_and_removed_files() -> None:
    previous = build_chunk_cache_contract(
        {
            "src/demo.py": _sample_entry(),
            "src/legacy.py": {
                "module": "src.legacy",
                "language": "python",
                "symbols": [],
            },
        }
    )
    changed_entry = _sample_entry()
    changed_entry["references"] = [{"qualified_name": "pkg.auth.refresh"}]
    current = build_chunk_cache_contract({"src/demo.py": changed_entry})

    diff = diff_chunk_cache_contract_paths(previous, current)

    assert diff["changed_paths"] == ["src/demo.py"]
    assert diff["unchanged_paths"] == []
    assert diff["removed_paths"] == ["src/legacy.py"]
