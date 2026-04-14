from __future__ import annotations

from ace_lite.benchmark.report_summary import (
    copy_optional_summary_sections,
    get_nested_mapping,
    get_summary_mapping,
)


def test_get_summary_mapping_returns_mapping_only() -> None:
    results = {
        "runtime_stats_summary": {"db_path": "runtime.db"},
        "invalid_summary": ["x"],
    }

    assert get_summary_mapping(results=results, key="runtime_stats_summary") == {
        "db_path": "runtime.db"
    }
    assert get_summary_mapping(results=results, key="invalid_summary") == {}
    assert get_summary_mapping(results=results, key="missing") == {}


def test_get_nested_mapping_returns_mapping_only() -> None:
    payload = {
        "summary": {"session": {"count": 1}},
        "invalid": ["x"],
    }

    assert get_nested_mapping(payload=payload, key="summary") == {
        "session": {"count": 1}
    }
    assert get_nested_mapping(payload=payload, key="invalid") == {}
    assert get_nested_mapping(payload=payload, key="missing") == {}


def test_copy_optional_summary_sections_uses_mapping_helpers() -> None:
    payload = copy_optional_summary_sections(
        results={
            "task_success_summary": {"case_count": 1},
            "policy_profile_distribution": {"default": 2},
            "invalid_summary": ["x"],
        }
    )

    assert payload["task_success_summary"] == {"case_count": 1}
    assert payload["policy_profile_distribution"] == {"default": 2}
    assert "invalid_summary" not in payload
