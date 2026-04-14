from __future__ import annotations

from types import SimpleNamespace

import pytest

from ace_lite.benchmark import case_evaluation_payload_builders as builders


def test_build_case_evaluation_row_from_namespace_forwards_expected_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_build_case_evaluation_row(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(
        builders,
        "build_case_evaluation_row",
        fake_build_case_evaluation_row,
    )

    namespace = {name: f"value:{name}" for name in builders._ROW_ARGUMENT_NAMES}
    result = builders.build_case_evaluation_row_from_namespace(namespace=namespace)

    assert result == {"ok": True}
    assert captured["case"] == "value:case"
    assert captured["top_k"] == "value:top_k"
    assert captured["decision_trace"] == "value:decision_trace"
    assert captured["evidence_insufficiency"] == "value:evidence_insufficiency"


def test_build_case_detail_payload_from_namespace_forwards_expected_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_build_case_detail_payload(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return {"details": True}

    monkeypatch.setattr(
        builders,
        "build_case_detail_payload",
        fake_build_case_detail_payload,
    )

    namespace = {name: f"value:{name}" for name in builders._DETAIL_ARGUMENT_NAMES}
    result = builders.build_case_detail_payload_from_namespace(namespace=namespace)

    assert result == {"details": True}
    assert captured["top_candidates"] == "value:top_candidates"
    assert captured["skills_payload"] == "value:skills_payload"
    assert captured["source_plan_packing_reason"] == (
        "value:source_plan_packing_reason"
    )


def test_build_case_evaluation_payload_builders_raise_for_missing_input() -> None:
    with pytest.raises(KeyError, match="top_k"):
        builders.build_case_evaluation_row_from_namespace(
            namespace={"case": {}, "expected": []}
        )

    with pytest.raises(KeyError, match="top_candidates"):
        builders.build_case_detail_payload_from_namespace(namespace={})


def test_build_case_evaluation_payload_builders_use_bundle_fallbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_build_case_evaluation_row(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(
        builders,
        "build_case_evaluation_row",
        fake_build_case_evaluation_row,
    )

    namespace = {name: f"value:{name}" for name in builders._ROW_ARGUMENT_NAMES}
    del namespace["precision"]
    del namespace["dependency_recall"]
    del namespace["task_success_hit"]

    namespace.update(
        {
            "case": {"id": "demo"},
            "expected": ["src/app.py"],
            "candidate_match_details": {"precision": 0.5},
            "diagnostics": SimpleNamespace(task_success_hit=1.0),
            "metrics": SimpleNamespace(dependency_recall=0.4),
        }
    )

    result = builders.build_case_evaluation_row_from_namespace(namespace=namespace)

    assert result == {"ok": True}
    assert captured["task_success_hit"] == 1.0
    assert captured["dependency_recall"] == 0.4
    assert captured["precision"] == 0.5
