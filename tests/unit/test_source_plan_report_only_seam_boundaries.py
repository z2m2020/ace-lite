from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_source_plan_report_only_imports_support_modules() -> None:
    text = _read("src/ace_lite/source_plan/report_only.py")

    expected_tokens = (
        "from ace_lite.source_plan.report_only_handoff import (",
        "append_handoff_payload_note",
        "build_handoff_payload",
        "build_handoff_payload_note",
        "build_session_end_report",
        "render_handoff_payload_markdown",
        "write_handoff_payload_artifacts",
        "from ace_lite.source_plan.report_only_history import build_history_hits",
        "from ace_lite.source_plan.report_only_review import (",
        "build_candidate_review",
        "build_validation_findings",
    )
    for token in expected_tokens:
        assert token in text


def test_source_plan_report_only_keeps_moved_builders_out_of_facade() -> None:
    text = _read("src/ace_lite/source_plan/report_only.py")

    forbidden_tokens = (
        "def build_history_hits(",
        "def build_candidate_review(",
        "def build_validation_findings(",
        "def build_session_end_report(",
        "def build_handoff_payload(",
        "def render_handoff_payload_markdown(",
        "def write_handoff_payload_artifacts(",
        "def build_handoff_payload_note(",
        "def append_handoff_payload_note(",
    )
    for token in forbidden_tokens:
        assert token not in text
