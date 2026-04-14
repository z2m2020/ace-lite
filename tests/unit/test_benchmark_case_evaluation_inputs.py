from __future__ import annotations

from ace_lite.benchmark.case_evaluation_inputs import build_case_evaluation_inputs


def test_build_case_evaluation_inputs_normalizes_case_and_payload() -> None:
    inputs = build_case_evaluation_inputs(
        case={
            "comparison_lane": " stale_majority ",
            "expected_keys": "auth; validate_token ; ;",
            "top_k": 4,
        },
        plan_payload={
            "index": {
                "metadata": {"lang": "python"},
                "benchmark_filters": {"include": ["src"]},
            },
            "source_plan": {"candidate_files": ["src/app.py"]},
        },
    )

    assert inputs.comparison_lane == "stale_majority"
    assert inputs.expected == ["auth", "validate_token"]
    assert inputs.top_k == 4
    assert inputs.index_metadata == {"lang": "python"}
    assert inputs.index_benchmark_filters == {"include": ["src"]}
    assert inputs.source_plan_payload == {"candidate_files": ["src/app.py"]}


def test_build_case_evaluation_inputs_defaults_missing_payloads() -> None:
    inputs = build_case_evaluation_inputs(
        case={"expected_keys": ["worker", "", None]},
        plan_payload={"index": "invalid", "source_plan": []},
    )

    assert inputs.comparison_lane == ""
    assert inputs.expected == ["worker", "None"]
    assert inputs.top_k == 8
    assert inputs.index_payload == {}
    assert inputs.index_metadata == {}
    assert inputs.index_benchmark_filters == {}
    assert inputs.source_plan_payload == {}
