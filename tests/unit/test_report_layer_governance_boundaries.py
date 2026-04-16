from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LAYER1_EXECUTION_MODULES = (
    REPO_ROOT / "src" / "ace_lite" / "orchestrator.py",
    REPO_ROOT / "src" / "ace_lite" / "pipeline" / "stages" / "memory.py",
    REPO_ROOT / "src" / "ace_lite" / "pipeline" / "stages" / "index.py",
    REPO_ROOT / "src" / "ace_lite" / "pipeline" / "stages" / "repomap.py",
    REPO_ROOT / "src" / "ace_lite" / "pipeline" / "stages" / "augment.py",
    REPO_ROOT / "src" / "ace_lite" / "pipeline" / "stages" / "skills.py",
    REPO_ROOT / "src" / "ace_lite" / "pipeline" / "stages" / "source_plan.py",
    REPO_ROOT / "src" / "ace_lite" / "pipeline" / "stages" / "validation.py",
)
FORBIDDEN_MODULE_IMPORTS = {
    "ace_lite.context_report",
    "ace_lite.retrieval_graph_view",
}
FORBIDDEN_IMPORTED_SYMBOLS = {
    "build_skill_catalog",
}
FORBIDDEN_TEXT_MARKERS = (
    ".context/",
    ".context\\",
    "artifacts/benchmark/",
    "artifacts\\benchmark\\",
)
REPORT_ONLY_VALIDATION_FINDINGS = (
    REPO_ROOT / "src" / "ace_lite" / "source_plan" / "report_only_review.py"
)
AGENT_LOOP_CONTROLLER = REPO_ROOT / "src" / "ace_lite" / "agent_loop" / "controller.py"
GOVERNANCE_DOC = REPO_ROOT / "docs" / "maintainers" / "REPORT_LAYER_GOVERNANCE.md"
CONTEXT_REPORT = REPO_ROOT / "src" / "ace_lite" / "context_report.py"
SOURCE_PLAN_STAGE = REPO_ROOT / "src" / "ace_lite" / "pipeline" / "stages" / "source_plan.py"
REPORT_LAYER_MODULES = (
    REPO_ROOT / "src" / "ace_lite" / "context_report.py",
    REPO_ROOT / "src" / "ace_lite" / "context_report_sections.py",
    REPO_ROOT / "src" / "ace_lite" / "retrieval_graph_view.py",
    REPO_ROOT / "src" / "ace_lite" / "source_plan" / "report_only.py",
    REPO_ROOT / "src" / "ace_lite" / "benchmark" / "report.py",
    REPO_ROOT / "src" / "ace_lite" / "benchmark" / "report_summary.py",
    REPO_ROOT / "src" / "ace_lite" / "benchmark" / "report_observability.py",
    REPO_ROOT / "src" / "ace_lite" / "benchmark" / "report_observability_governance.py",
    REPO_ROOT / "src" / "ace_lite" / "benchmark" / "report_observability_routing.py",
)
FORBIDDEN_EXECUTION_IMPORT_PREFIXES = (
    "ace_lite.orchestrator",
    "ace_lite.pipeline.stages",
)


def _parse_module(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))


def test_layer1_execution_modules_do_not_import_report_only_modules() -> None:
    violations: list[str] = []
    for path in LAYER1_EXECUTION_MODULES:
        tree = _parse_module(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in FORBIDDEN_MODULE_IMPORTS:
                        violations.append(f"{path.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = str(node.module or "")
                if module in FORBIDDEN_MODULE_IMPORTS:
                    violations.append(f"{path.name}: from {module} import ...")
                for alias in node.names:
                    if alias.name in FORBIDDEN_IMPORTED_SYMBOLS:
                        violations.append(
                            f"{path.name}: forbidden symbol {alias.name} from {module or '(relative import)'}"
                        )
        text = path.read_text(encoding="utf-8-sig")
        for marker in FORBIDDEN_TEXT_MARKERS:
            if marker in text:
                violations.append(f"{path.name}: forbidden Layer 3 marker {marker}")

    assert violations == []


def test_validation_findings_contract_stays_advisory_only() -> None:
    text = REPORT_ONLY_VALIDATION_FINDINGS.read_text(encoding="utf-8-sig")

    assert '"schema_version": "validation_findings_v1"' in text
    assert '"governance_mode": "advisory_report_only"' in text
    assert '"allowed_actions": ["request_more_context"]' in text


def test_report_layer_modules_do_not_import_layer1_execution_modules() -> None:
    violations: list[str] = []
    for path in REPORT_LAYER_MODULES:
        tree = _parse_module(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(FORBIDDEN_EXECUTION_IMPORT_PREFIXES):
                        violations.append(f"{path.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = str(node.module or "")
                if module.startswith(FORBIDDEN_EXECUTION_IMPORT_PREFIXES):
                    violations.append(f"{path.name}: from {module} import ...")

    assert violations == []


def test_agent_loop_consumes_validation_findings_only_as_request_more_context() -> None:
    text = AGENT_LOOP_CONTROLLER.read_text(encoding="utf-8-sig")

    assert 'findings.get("schema_version")' in text
    assert 'findings.get("governance_mode")' in text
    assert 'action_type="request_more_context"' in text
    assert '"allowed_effect": "request_more_context_only"' in text
    assert "source_plan_validation_findings" in text


def test_governance_doc_records_validation_findings_boundary() -> None:
    text = GOVERNANCE_DOC.read_text(encoding="utf-8-sig")

    assert "validation_findings_v1" in text
    assert "advisory_report_only" in text
    assert "request_more_context" in text
    assert "MUST NOT change source-plan ranking" in text
    assert "Layer 2 and Layer 3 modules MUST NOT import Layer 1 execution modules" in text


def test_context_report_uses_sections_seam_and_stays_layer2() -> None:
    text = CONTEXT_REPORT.read_text(encoding="utf-8-sig")

    expected_tokens = (
        "from ace_lite.context_report_sections import (",
        "append_history_channel_section",
        "append_history_hits_section",
        "append_context_refine_section",
        "append_core_nodes_section",
        "append_candidate_review_section",
        "append_surprising_connections_section",
        "append_confidence_breakdown_section",
        "append_validation_findings_section",
        "append_knowledge_gaps_section",
        "append_suggested_questions_section",
        "append_warnings_section",
        "append_session_end_report_section",
        "append_handoff_payload_section",
    )
    for token in expected_tokens:
        assert token in text

    forbidden_markers = (
        "## History Channel",
        "## History Hits",
        "## Context Refine",
        "## Core Nodes",
        "## Candidate Review",
        "## Surprising Connections",
        "## Confidence Breakdown",
        "## Validation Findings",
        "## Session End Report",
        "## Handoff Payload",
        "request_more_context",
        "allowed_effect",
    )
    for marker in forbidden_markers:
        assert marker not in text


def test_source_plan_consumes_context_refine_only_through_candidate_review() -> None:
    text = SOURCE_PLAN_STAGE.read_text(encoding="utf-8-sig")

    assert "from ace_lite.source_plan.context_refine_support import (" in text
    assert "resolve_source_plan_candidate_review" in text
    assert 'context_refine_state=ctx.state.get("context_refine")' in text

    forbidden_markers = (
        'context_refine_stage = _coerce_mapping(ctx.state.get("context_refine"))',
        'candidate_review = _coerce_mapping(context_refine_stage.get("candidate_review"))',
        'context_refine_stage.get("decision_counts")',
        'context_refine_stage.get("candidate_file_actions")',
        'context_refine_stage.get("candidate_chunk_actions")',
        'context_refine_stage.get("focused_files")',
        'context_refine_stage.get("policy_name")',
        'context_refine_stage.get("policy_version")',
    )
    for marker in forbidden_markers:
        assert marker not in text
