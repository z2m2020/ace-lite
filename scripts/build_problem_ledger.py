from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ace_lite.benchmark.problem_surface_reader import (
    build_problem_surface_from_benchmark_artifacts,
)

SCHEMA_VERSION = "problem_ledger_v1"
DEFAULT_PHASE = "report_only"
DEFAULT_BASELINE = "unknown"
DEFAULT_GATE_MODE = "report_only"


@dataclass(frozen=True, slots=True)
class ProblemSpec:
    problem_id: str
    title: str
    symptom: str
    metric_name: str
    metric_formula: str
    data_source: str
    validation_method: str
    threshold_or_expected_direction: str
    target_phase: str
    owner: str
    status: str
    rollback_trigger: str
    notes: str
    baseline_path: tuple[str, ...]
    benchmark_artifact_names: tuple[str, ...] = ()
    freeze_artifact_names: tuple[str, ...] = ()


BASE_PROBLEM_SPECS: tuple[ProblemSpec, ...] = (
    ProblemSpec(
        problem_id="PQ-001",
        title="Source-plan failure signals are incomplete",
        symptom="Source-plan failure evidence can be missing from validation-rich artifacts.",
        metric_name="failure_signal_present_ratio",
        metric_formula="source_plan_failure_signal_summary.present_ratio",
        data_source="benchmark summary.json",
        validation_method="Read validation-rich source_plan_failure_signal_summary fields.",
        threshold_or_expected_direction="Increase or remain stable.",
        target_phase="phase-1",
        owner="governance",
        status="open",
        rollback_trigger="Failure signal coverage drops or disappears in current runs.",
        notes="Keep report-only until current artifacts provide stable coverage.",
        baseline_path=("source_plan_failure_signal_summary", "present_ratio"),
        benchmark_artifact_names=(
            "summary.json",
            "results.json",
            "report.md",
            "archive_manifest.json",
        ),
    ),
    ProblemSpec(
        problem_id="PQ-002",
        title="Validation feedback coverage is not yet reliable",
        symptom="Validation feedback may not appear consistently across benchmark artifacts.",
        metric_name="validation_feedback_present_ratio",
        metric_formula="source_plan_validation_feedback_summary.present_ratio",
        data_source="benchmark summary.json",
        validation_method="Read validation-rich source_plan_validation_feedback_summary fields.",
        threshold_or_expected_direction="Increase or remain stable.",
        target_phase="phase-1",
        owner="governance",
        status="open",
        rollback_trigger="Validation feedback presence regresses or remains absent.",
        notes="Track report-only until the validation feedback stream is dependable.",
        baseline_path=("source_plan_validation_feedback_summary", "present_ratio"),
        benchmark_artifact_names=("summary.json", "report.md", "results.json"),
    ),
    ProblemSpec(
        problem_id="PQ-003",
        title="Validation probes need more stable execution evidence",
        symptom="Probe execution depth can be unclear or absent in lightweight runs.",
        metric_name="validation_test_count",
        metric_formula="validation_probe_summary.validation_test_count",
        data_source="benchmark summary.json",
        validation_method="Read validation-rich validation_probe_summary fields.",
        threshold_or_expected_direction="Increase or remain stable.",
        target_phase="phase-1",
        owner="governance",
        status="open",
        rollback_trigger="Validation test coverage falls below the current benchmark evidence.",
        notes="Use report-only while probe execution remains optional or sparse.",
        baseline_path=("validation_probe_summary", "validation_test_count"),
        benchmark_artifact_names=("summary.json", "results.json", "next_cycle_todo.md"),
    ),
    ProblemSpec(
        problem_id="PQ-004",
        title="Retrieval control-plane gate is not ready for enforcement",
        symptom="Control-plane checks may still fail or lack enough evidence for hard gating.",
        metric_name="retrieval_control_plane_gate_passed",
        metric_formula="retrieval_control_plane_gate_summary.gate_passed",
        data_source="benchmark summary.json",
        validation_method="Read retrieval_control_plane_gate_summary from benchmark artifacts.",
        threshold_or_expected_direction="Should trend toward passed with no failed checks.",
        target_phase="phase-2",
        owner="governance",
        status="open",
        rollback_trigger="Control-plane gate reports failures or regressions.",
        notes="Default to report-only unless a registry explicitly promotes the problem.",
        baseline_path=("retrieval_control_plane_gate_summary", "gate_passed"),
        benchmark_artifact_names=(
            "summary.json",
            "promotion_decision.json",
            "promotion_decision.md",
        ),
    ),
    ProblemSpec(
        problem_id="PQ-005",
        title="Adaptive router shadow coverage needs a stable baseline",
        symptom="Shadow coverage evidence may exist, but it is not yet promotion-ready by default.",
        metric_name="adaptive_router_shadow_coverage",
        metric_formula="retrieval_control_plane_gate_summary.adaptive_router_shadow_coverage",
        data_source="benchmark summary.json",
        validation_method="Read retrieval_control_plane_gate_summary shadow coverage metrics.",
        threshold_or_expected_direction="Increase or remain stable.",
        target_phase="phase-2",
        owner="governance",
        status="open",
        rollback_trigger="Shadow coverage drops below the current observed baseline.",
        notes="Stay report-only until shadow coverage is consistently observed.",
        baseline_path=("retrieval_control_plane_gate_summary", "adaptive_router_shadow_coverage"),
        benchmark_artifact_names=("summary.json", "archive_manifest.json"),
    ),
    ProblemSpec(
        problem_id="PQ-006",
        title="Retrieval frontier quality gate is still observational",
        symptom="Frontier quality checks may exist without enough evidence to block releases.",
        metric_name="frontier_precision_at_k",
        metric_formula="retrieval_frontier_gate_summary.precision_at_k",
        data_source="benchmark summary.json",
        validation_method="Read retrieval_frontier_gate_summary benchmark metrics.",
        threshold_or_expected_direction="Increase precision and avoid noisy regressions.",
        target_phase="phase-2",
        owner="governance",
        status="open",
        rollback_trigger="Frontier precision regresses or failed checks appear.",
        notes="Track frontier quality in report-only mode by default.",
        baseline_path=("retrieval_frontier_gate_summary", "precision_at_k"),
        benchmark_artifact_names=("summary.json", "results.json", "archive_manifest.json"),
    ),
    ProblemSpec(
        problem_id="PQ-007",
        title="Deep-symbol recall remains benchmark-only evidence",
        symptom="Deep-symbol recall may be available in summaries but is not guaranteed for all runs.",
        metric_name="deep_symbol_recall",
        metric_formula="deep_symbol_summary.recall",
        data_source="benchmark summary.json",
        validation_method="Read deep_symbol_summary fields from benchmark artifacts.",
        threshold_or_expected_direction="Increase or remain stable.",
        target_phase="phase-3",
        owner="governance",
        status="open",
        rollback_trigger="Deep-symbol recall drops below current observed evidence.",
        notes="Hold as report-only until deep-symbol evidence is broadly available.",
        baseline_path=("deep_symbol_summary", "recall"),
        benchmark_artifact_names=("summary.json", "report.md"),
    ),
    ProblemSpec(
        problem_id="PQ-008",
        title="Native SCIP readiness still depends on optional artifacts",
        symptom="Native SCIP loading evidence may be absent in runs without that integration enabled.",
        metric_name="native_scip_loaded_rate",
        metric_formula="native_scip_summary.loaded_rate",
        data_source="benchmark summary.json",
        validation_method="Read native_scip_summary fields from benchmark artifacts.",
        threshold_or_expected_direction="Increase or remain stable.",
        target_phase="phase-3",
        owner="governance",
        status="open",
        rollback_trigger="Native SCIP loaded rate regresses or disappears from observed artifacts.",
        notes="Default to report-only because native SCIP evidence is optional.",
        baseline_path=("native_scip_summary", "loaded_rate"),
        benchmark_artifact_names=("summary.json", "report.md", "archive_manifest.json"),
    ),
)

OPTIONAL_PROBLEM_SPECS: tuple[ProblemSpec, ...] = (
    ProblemSpec(
        problem_id="PQ-009",
        title="Release-freeze regression evidence needs governance tracking",
        symptom="Freeze regression artifacts can reveal recurring release-readiness failures.",
        metric_name="freeze_passed",
        metric_formula="freeze_regression.passed",
        data_source="freeze regression artifacts",
        validation_method="Read freeze_regression.json or related freeze outputs if present.",
        threshold_or_expected_direction="Should trend toward passed with fewer failure signatures.",
        target_phase="phase-2",
        owner="governance",
        status="open",
        rollback_trigger="Freeze regression artifacts show new or recurring failures.",
        notes="Only emit when freeze artifacts are available.",
        baseline_path=("passed",),
        freeze_artifact_names=("freeze_regression.json", "summary.json", "report.md"),
    ),
    ProblemSpec(
        problem_id="PQ-010",
        title="Gate registry promotion state needs explicit tracking",
        symptom="Registry-backed gate readiness can drift from observed artifact evidence.",
        metric_name="registry_configured",
        metric_formula="gate_registry entry present for problem_id",
        data_source="gate_registry.json",
        validation_method="Read the matching gate_registry entry if supplied.",
        threshold_or_expected_direction="Registry should reflect reviewed promotion intent.",
        target_phase="phase-2",
        owner="governance",
        status="open",
        rollback_trigger="Registry state conflicts with current evidence or is missing.",
        notes="Only emit when a gate registry path is available.",
        baseline_path=(),
    ),
)


def _resolve_path(*, root: Path, value: str) -> Path:
    candidate = Path(str(value).strip())
    if candidate.is_absolute():
        return candidate
    return (root / candidate).resolve()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _discover_named_files(*, root: Path | None, names: tuple[str, ...]) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {name: [] for name in names}
    if root is None or not root.exists() or not root.is_dir():
        return found

    for name in names:
        matches: list[Path] = []
        direct = root / name
        if direct.exists() and direct.is_file():
            matches.append(direct.resolve())
        for path in root.rglob(name):
            if path.is_file():
                resolved = path.resolve()
                if resolved not in matches:
                    matches.append(resolved)
        found[name] = [str(path) for path in sorted(matches, key=str)]
    return found


def _first_json_payload(*, root: Path | None, file_name: str) -> dict[str, Any]:
    if root is None or not root.exists() or not root.is_dir():
        return {}
    direct = root / file_name
    if direct.exists() and direct.is_file():
        return _load_json(direct)
    candidates = sorted((path for path in root.rglob(file_name) if path.is_file()), key=str)
    if not candidates:
        return {}
    return _load_json(candidates[0])


def _safe_baseline(value: Any) -> Any:
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str) and value.strip():
        return value
    return DEFAULT_BASELINE


def _read_nested(payload: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return DEFAULT_BASELINE
        current = current.get(key)
    return _safe_baseline(current)


def _detect_git_sha(root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            cwd=root,
        )
    except Exception:
        return "unknown"
    sha = str(completed.stdout).strip()
    return sha or "unknown"


def _normalize_registry(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}

    problems_raw = payload.get("problems")
    if isinstance(problems_raw, list):
        for item in problems_raw:
            if not isinstance(item, dict):
                continue
            problem_id = str(item.get("problem_id") or "").strip()
            if problem_id:
                normalized[problem_id] = dict(item)

    entries_raw = payload.get("entries")
    if isinstance(entries_raw, list):
        for item in entries_raw:
            if not isinstance(item, dict):
                continue
            problem_id = str(item.get("problem_id") or "").strip()
            if problem_id and problem_id not in normalized:
                normalized[problem_id] = dict(item)

    for key, value in payload.items():
        if key in normalized or not isinstance(value, dict):
            continue
        if key.startswith("PQ-"):
            normalized[key] = dict(value)

    return normalized


def _artifact_paths_for_problem(
    *,
    spec: ProblemSpec,
    benchmark_files: dict[str, list[str]],
    freeze_files: dict[str, list[str]],
    gate_registry_path: Path | None,
) -> list[str]:
    artifact_paths: list[str] = []
    for name in spec.benchmark_artifact_names:
        artifact_paths.extend(benchmark_files.get(name, []))
    for name in spec.freeze_artifact_names:
        artifact_paths.extend(freeze_files.get(name, []))
    if (
        spec.problem_id == "PQ-010"
        and gate_registry_path is not None
        and gate_registry_path.exists()
    ):
        artifact_paths.append(str(gate_registry_path.resolve()))
    return sorted(set(path for path in artifact_paths if str(path).strip()))


def _build_problem_entry(
    *,
    spec: ProblemSpec,
    benchmark_summary: dict[str, Any],
    freeze_summary: dict[str, Any],
    registry_entry: dict[str, Any] | None,
    benchmark_files: dict[str, list[str]],
    freeze_files: dict[str, list[str]],
    gate_registry_path: Path | None,
) -> dict[str, Any]:
    registry_entry = registry_entry or {}
    baseline_source = benchmark_summary
    if spec.problem_id == "PQ-009":
        baseline_source = freeze_summary

    current_baseline = (
        _read_nested(baseline_source, spec.baseline_path)
        if spec.baseline_path
        else DEFAULT_BASELINE
    )
    if registry_entry.get("current_baseline") not in (None, ""):
        current_baseline = _safe_baseline(registry_entry.get("current_baseline"))

    title = str(registry_entry.get("title") or spec.title)
    can_gate_now = bool(registry_entry.get("can_gate_now", False))
    gate_mode = (
        str(registry_entry.get("gate_mode") or DEFAULT_GATE_MODE).strip() or DEFAULT_GATE_MODE
    )

    return {
        "problem_id": spec.problem_id,
        "title": title,
        "symptom": spec.symptom,
        "metric_name": spec.metric_name,
        "metric_formula": spec.metric_formula,
        "data_source": spec.data_source,
        "validation_method": spec.validation_method,
        "threshold_or_expected_direction": spec.threshold_or_expected_direction,
        "current_baseline": current_baseline,
        "target_phase": spec.target_phase,
        "owner": spec.owner,
        "status": spec.status,
        "can_gate_now": can_gate_now,
        "gate_mode": gate_mode,
        "artifact_paths": _artifact_paths_for_problem(
            spec=spec,
            benchmark_files=benchmark_files,
            freeze_files=freeze_files,
            gate_registry_path=gate_registry_path,
        ),
        "rollback_trigger": spec.rollback_trigger,
        "notes": spec.notes,
    }


def build_problem_ledger(
    *,
    benchmark_artifacts_root: str = "",
    freeze_artifacts_root: str = "",
    gate_registry_path: str = "",
    problem_surface_artifacts_root: str = "",
) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]

    benchmark_root = (
        _resolve_path(root=repo_root, value=benchmark_artifacts_root)
        if str(benchmark_artifacts_root).strip()
        else None
    )
    freeze_root = (
        _resolve_path(root=repo_root, value=freeze_artifacts_root)
        if str(freeze_artifacts_root).strip()
        else None
    )
    registry_path = (
        _resolve_path(root=repo_root, value=gate_registry_path)
        if str(gate_registry_path).strip()
        else None
    )
    surface_root = (
        _resolve_path(root=repo_root, value=problem_surface_artifacts_root)
        if str(problem_surface_artifacts_root).strip()
        else None
    )

    benchmark_files = _discover_named_files(
        root=benchmark_root,
        names=(
            "summary.json",
            "results.json",
            "report.md",
            "archive_manifest.json",
            "promotion_decision.json",
            "promotion_decision.md",
            "next_cycle_todo.md",
        ),
    )
    freeze_files = _discover_named_files(
        root=freeze_root,
        names=("freeze_regression.json", "summary.json", "report.md"),
    )

    benchmark_summary = _first_json_payload(root=benchmark_root, file_name="summary.json")
    freeze_summary = _first_json_payload(root=freeze_root, file_name="freeze_regression.json")
    registry_payload = _load_json(registry_path) if registry_path is not None else {}
    registry_entries = _normalize_registry(registry_payload)

    # Load problem_surface_v1 from benchmark artifacts root if provided
    problem_surface: dict[str, Any] = {}
    if surface_root is not None and surface_root.exists():
        surface_payload = build_problem_surface_from_benchmark_artifacts(
            results_path=surface_root / "results.json"
            if (surface_root / "results.json").exists()
            else None,
            freeze_regression_path=surface_root / "freeze_regression.json"
            if (surface_root / "freeze_regression.json").exists()
            else None,
            summary_path=surface_root / "summary.json"
            if (surface_root / "summary.json").exists()
            else None,
        )
        if surface_payload:
            problem_surface = surface_payload

    def _build_with_surface(
        spec: ProblemSpec,
        registry_entry: dict[str, Any] | None,
    ) -> dict[str, Any]:
        entry = _build_problem_entry(
            spec=spec,
            benchmark_summary=benchmark_summary,
            freeze_summary=freeze_summary,
            registry_entry=registry_entry,
            benchmark_files=benchmark_files,
            freeze_files=freeze_files,
            gate_registry_path=registry_path,
        )
        # Wire in problem_surface artifact paths for this PQ if available
        surface_for_problem = problem_surface.get("surfaces", {}).get(spec.problem_id)
        if surface_for_problem and isinstance(surface_for_problem, dict):
            surface_paths = surface_for_problem.get("artifact_paths", [])
            if surface_paths:
                existing = entry.get("artifact_paths", [])
                merged = sorted(set(existing + surface_paths))
                entry["artifact_paths"] = merged
        return entry

    problems = [
        _build_with_surface(spec, registry_entries.get(spec.problem_id))
        for spec in BASE_PROBLEM_SPECS
    ]

    if any(paths for paths in freeze_files.values()) or freeze_summary:
        freeze_spec = OPTIONAL_PROBLEM_SPECS[0]
        problems.append(
            _build_with_surface(freeze_spec, registry_entries.get(freeze_spec.problem_id))
        )

    if registry_path is not None and (registry_path.exists() or registry_entries):
        registry_spec = OPTIONAL_PROBLEM_SPECS[1]
        problems.append(
            _build_with_surface(registry_spec, registry_entries.get(registry_spec.problem_id))
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": _detect_git_sha(repo_root),
        "phase": DEFAULT_PHASE,
        "problems": problems,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a problem_ledger_v1 JSON document from benchmark and freeze artifacts."
    )
    parser.add_argument("--benchmark-artifacts-root", default="")
    parser.add_argument("--freeze-artifacts-root", default="")
    parser.add_argument("--gate-registry-path", default="")
    parser.add_argument(
        "--problem-surface-artifacts-root",
        default="",
        help="Root directory containing benchmark/freeze artifacts for problem surface extraction.",
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    repo_root = Path(__file__).resolve().parents[1]
    output_path = _resolve_path(root=repo_root, value=str(args.output))
    payload = build_problem_ledger(
        benchmark_artifacts_root=str(args.benchmark_artifacts_root),
        freeze_artifacts_root=str(args.freeze_artifacts_root),
        gate_registry_path=str(args.gate_registry_path),
        problem_surface_artifacts_root=str(args.problem_surface_artifacts_root),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
