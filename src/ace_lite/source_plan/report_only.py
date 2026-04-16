"""Report-only source-plan summary helpers facade."""

from __future__ import annotations

from ace_lite.source_plan.report_only_handoff import (
    append_handoff_payload_note,
    build_handoff_payload,
    build_handoff_payload_note,
    build_session_end_report,
    render_handoff_payload_markdown,
    write_handoff_payload_artifacts,
)
from ace_lite.source_plan.report_only_history import build_history_hits
from ace_lite.source_plan.report_only_review import (
    build_candidate_review,
    build_validation_findings,
)

__all__ = [
    "append_handoff_payload_note",
    "build_candidate_review",
    "build_handoff_payload",
    "build_handoff_payload_note",
    "build_history_hits",
    "build_session_end_report",
    "build_validation_findings",
    "render_handoff_payload_markdown",
    "write_handoff_payload_artifacts",
]
