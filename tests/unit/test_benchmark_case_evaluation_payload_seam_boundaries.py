from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_case_evaluation_payload_builders_import_support_seams() -> None:
    text = _read("src/ace_lite/benchmark/case_evaluation_payload_builders.py")

    expected_tokens = (
        "from ace_lite.benchmark.case_evaluation_payload_builder_facade import (",
        "build_namespace_kwargs",
        "from ace_lite.benchmark.case_evaluation_payload_support import (",
        "DETAIL_ARGUMENT_NAMES",
        "ROW_ARGUMENT_NAMES",
    )
    for token in expected_tokens:
        assert token in text


def test_case_evaluation_payload_builders_keep_moved_lookup_and_constant_blocks_out_of_facade() -> (
    None
):
    text = _read("src/ace_lite/benchmark/case_evaluation_payload_builders.py")

    forbidden_tokens = (
        "def _lookup(",
        'error_prefix="case-evaluation payload input"',
        '"task_success_hit",',
        '"decision_trace",',
        '"top_candidates",',
        '"source_plan_packing_reason",',
    )
    for token in forbidden_tokens:
        assert token not in text
