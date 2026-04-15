from __future__ import annotations

import argparse
import ast
import json
import math
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from ace_lite.friction import append_event, make_event

RUFF_TARGETS = ["src/ace_lite", "scripts", "tests"]

BANDIT_TARGETS = ["src/ace_lite"]

HOTSPOT_TARGETS = [
    "src/ace_lite/orchestrator.py",
    "src/ace_lite/orchestrator_contracts.py",
    "src/ace_lite/runtime_settings.py",
    "src/ace_lite/plan_quick.py",
    "src/ace_lite/plan_quick_strategies.py",
    "src/ace_lite/benchmark/report.py",
    "src/ace_lite/context_report.py",
    "src/ace_lite/benchmark/report_observability.py",
    "src/ace_lite/benchmark/summaries.py",
]

HOTSPOT_CHECK_NAMES = ("ruff_hotspots", "mypy_hotspots")

MYPY_HOTSPOT_COMPANION_TARGETS = {
    "src/ace_lite/orchestrator.py": (
        "src/ace_lite/orchestrator_runtime_support_types.py",
        "src/ace_lite/orchestrator_runtime_finalization.py",
        "src/ace_lite/orchestrator_runtime_support.py",
        "src/ace_lite/cli_app/orchestrator_factory_support.py",
        "src/ace_lite/cli_app/orchestrator_factory.py",
    ),
}


@dataclass(slots=True)
class CommandResult:
    name: str
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    elapsed_ms: float

    @property
    def passed(self) -> bool:
        return self.returncode == 0


def _resolve_path(*, root: Path, value: str) -> Path:
    candidate = Path(str(value).strip())
    if candidate.is_absolute():
        return candidate
    return (root / candidate).resolve()


def _run_command(*, name: str, command: list[str], cwd: Path) -> CommandResult:
    started = perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return CommandResult(
            name=name,
            command=command,
            returncode=int(completed.returncode),
            stdout=str(completed.stdout or ""),
            stderr=str(completed.stderr or ""),
            elapsed_ms=(perf_counter() - started) * 1000.0,
        )
    except Exception as exc:
        return CommandResult(
            name=name,
            command=command,
            returncode=2,
            stdout="",
            stderr=f"{exc.__class__.__name__}: {exc}",
            elapsed_ms=(perf_counter() - started) * 1000.0,
        )


def _write_command_logs(*, result: CommandResult, output_dir: Path) -> None:
    logs_dir = output_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = logs_dir / f"{result.name}.stdout.txt"
    stderr_path = logs_dir / f"{result.name}.stderr.txt"
    stdout_path.write_text(result.stdout, encoding="utf-8")
    stderr_path.write_text(result.stderr, encoding="utf-8")


def _extract_json_payload(raw_text: str) -> dict[str, Any]:
    text = str(raw_text or "")
    start = text.find("{")
    if start < 0:
        return {}
    candidate = text[start:]
    decoder = json.JSONDecoder()
    try:
        payload, _ = decoder.raw_decode(candidate)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _normalize_finding(item: dict[str, Any]) -> dict[str, Any]:
    package = str(item.get("package") or "").strip()
    vuln_id = str(item.get("id") or "").strip()
    fix_versions_raw = item.get("fix_versions")
    fix_versions = (
        [str(value).strip() for value in fix_versions_raw if str(value).strip()]
        if isinstance(fix_versions_raw, list)
        else []
    )
    return {
        "package": package,
        "id": vuln_id,
        "fix_versions": sorted(set(fix_versions)),
    }


def _finding_key(item: dict[str, Any]) -> tuple[str, str]:
    normalized = _normalize_finding(item)
    return normalized["package"], normalized["id"]


def _collect_findings(payload: dict[str, Any]) -> list[dict[str, Any]]:
    dependencies_raw = payload.get("dependencies")
    dependencies = dependencies_raw if isinstance(dependencies_raw, list) else []
    findings: list[dict[str, Any]] = []
    for dep in dependencies:
        if not isinstance(dep, dict):
            continue
        package = str(dep.get("name") or "").strip()
        if not package:
            continue
        vulns_raw = dep.get("vulns")
        vulns = vulns_raw if isinstance(vulns_raw, list) else []
        for vuln in vulns:
            if not isinstance(vuln, dict):
                continue
            vuln_id = str(vuln.get("id") or "").strip()
            if not vuln_id:
                continue
            findings.append(
                _normalize_finding(
                    {
                        "package": package,
                        "id": vuln_id,
                        "fix_versions": vuln.get("fix_versions"),
                    }
                )
            )
    dedup: dict[tuple[str, str], dict[str, Any]] = {}
    for item in findings:
        key = _finding_key(item)
        existing = dedup.get(key)
        if existing is None:
            dedup[key] = item
            continue
        merged_versions = sorted(
            set(existing.get("fix_versions", [])) | set(item.get("fix_versions", []))
        )
        dedup[key] = {
            "package": item["package"],
            "id": item["id"],
            "fix_versions": merged_versions,
        }
    return sorted(dedup.values(), key=lambda item: (item["package"], item["id"]))


def _load_baseline(*, path: Path) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(payload, dict):
        raw = payload.get("findings")
        findings = raw if isinstance(raw, list) else []
    elif isinstance(payload, list):
        findings = payload
    else:
        findings = []
    normalized = [
        _normalize_finding(item)
        for item in findings
        if isinstance(item, dict)
    ]
    filtered = [
        item for item in normalized if item["package"] and item["id"]
    ]
    return sorted(filtered, key=lambda item: (item["package"], item["id"]))


def _normalize_hotspot_path(value: str) -> str:
    return str(Path(str(value).strip())).replace("\\", "/")


def _load_hotspot_baseline(*, path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    hotspots_raw = payload.get("hotspots") if isinstance(payload, dict) else None
    hotspots = hotspots_raw if isinstance(hotspots_raw, list) else []
    baseline: dict[str, dict[str, Any]] = {}
    for item in hotspots:
        if not isinstance(item, dict):
            continue
        normalized_path = _normalize_hotspot_path(str(item.get("path") or ""))
        if not normalized_path:
            continue
        baseline[normalized_path] = dict(item)
    return baseline


def _load_coverage_payload(*, path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _resolve_coverage_entry(
    *,
    root: Path,
    coverage_payload: dict[str, Any],
    hotspot_path: str,
) -> dict[str, Any]:
    files_raw = coverage_payload.get("files")
    files = files_raw if isinstance(files_raw, dict) else {}
    if not files:
        return {}

    normalized_hotspot = _normalize_hotspot_path(hotspot_path)
    direct = files.get(normalized_hotspot)
    if isinstance(direct, dict):
        return direct

    hotspot_target = (root / hotspot_path).resolve()
    for candidate, payload in files.items():
        if not isinstance(payload, dict):
            continue
        candidate_path = Path(str(candidate))
        resolved = (
            candidate_path.resolve()
            if candidate_path.is_absolute()
            else (root / candidate_path).resolve()
        )
        if resolved == hotspot_target:
            return payload
    return {}


class _PythonComplexityVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.score = 1
        self.function_count = 0

    def _bump(self, amount: int = 1) -> None:
        self.score += max(0, int(amount))

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.function_count += 1
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.function_count += 1
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        self._bump()
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        self._bump()
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self._bump()
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self._bump()
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self._bump()
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> None:
        self._bump(len(node.handlers) + int(bool(node.orelse)) + int(bool(node.finalbody)))
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self._bump(max(1, len(node.values) - 1))
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> None:
        self._bump(max(1, len(node.cases)))
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        self._bump(1 + len(node.ifs))
        self.generic_visit(node)


def _compute_python_complexity(*, path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {
            "available": False,
            "metric": "ast_decision_score",
            "score": None,
            "function_count": 0,
            "error": "missing",
        }
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except Exception as exc:
        return {
            "available": False,
            "metric": "ast_decision_score",
            "score": None,
            "function_count": 0,
            "error": f"{exc.__class__.__name__}: {exc}",
        }

    visitor = _PythonComplexityVisitor()
    visitor.visit(tree)
    return {
        "available": True,
        "metric": "ast_decision_score",
        "score": int(max(1, visitor.score)),
        "function_count": int(visitor.function_count),
        "error": None,
    }


def _default_complexity_ceiling(*, score: int | None) -> int | None:
    if not isinstance(score, int):
        return None
    return int(score + max(2, math.ceil(score * 0.1)))


def _build_hotspot_baseline_payload(
    *,
    root: Path,
    coverage_json_path: Path,
    hotspot_paths: list[str] | None = None,
) -> dict[str, Any]:
    coverage_payload = _load_coverage_payload(path=coverage_json_path)
    requested_paths = hotspot_paths if isinstance(hotspot_paths, list) else HOTSPOT_TARGETS
    ordered_paths = [
        _normalize_hotspot_path(item)
        for item in requested_paths
        if _normalize_hotspot_path(item)
    ]
    hotspots: list[dict[str, Any]] = []
    for hotspot_path in ordered_paths:
        target_path = (root / hotspot_path).resolve()
        coverage_entry = _resolve_coverage_entry(
            root=root,
            coverage_payload=coverage_payload,
            hotspot_path=hotspot_path,
        )
        coverage_summary = (
            coverage_entry.get("summary", {})
            if isinstance(coverage_entry.get("summary"), dict)
            else {}
        )
        coverage_percent = coverage_summary.get("percent_covered")
        complexity = _compute_python_complexity(path=target_path)
        complexity_score = (
            int(complexity["score"]) if isinstance(complexity.get("score"), int) else None
        )
        hotspots.append(
            {
                "path": hotspot_path,
                "coverage_percent": float(coverage_percent)
                if isinstance(coverage_percent, (int, float))
                else None,
                "complexity_score": complexity_score,
                "complexity_ceiling": _default_complexity_ceiling(score=complexity_score),
            }
        )
    return {
        "mode": "report_only",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "hotspots": hotspots,
    }


def _build_hotspot_summary(
    *,
    root: Path,
    coverage_json_path: Path,
    hotspot_baseline_path: Path,
    hotspot_paths: list[str] | None = None,
) -> dict[str, Any]:
    baseline = _load_hotspot_baseline(path=hotspot_baseline_path)
    coverage_payload = _load_coverage_payload(path=coverage_json_path)

    requested_paths = hotspot_paths if isinstance(hotspot_paths, list) else HOTSPOT_TARGETS
    ordered_paths = [
        _normalize_hotspot_path(item)
        for item in requested_paths
        if _normalize_hotspot_path(item)
    ]
    for item in baseline:
        if item not in ordered_paths:
            ordered_paths.append(item)

    hotspots: list[dict[str, Any]] = []
    missing_baselines: list[str] = []
    for hotspot_path in ordered_paths:
        target_path = (root / hotspot_path).resolve()
        coverage_entry = _resolve_coverage_entry(
            root=root,
            coverage_payload=coverage_payload,
            hotspot_path=hotspot_path,
        )
        coverage_summary = (
            coverage_entry.get("summary", {})
            if isinstance(coverage_entry.get("summary"), dict)
            else {}
        )
        coverage_percent = coverage_summary.get("percent_covered")
        baseline_entry = baseline.get(hotspot_path, {})
        baseline_coverage = baseline_entry.get("coverage_percent")
        baseline_complexity = baseline_entry.get("complexity_score")
        complexity_ceiling = baseline_entry.get("complexity_ceiling")
        complexity = _compute_python_complexity(path=target_path)

        if not baseline_entry:
            missing_baselines.append(hotspot_path)

        hotspots.append(
            {
                "path": hotspot_path,
                "exists": target_path.exists(),
                "coverage": {
                    "available": bool(coverage_summary),
                    "percent": float(coverage_percent)
                    if isinstance(coverage_percent, (int, float))
                    else None,
                    "covered_lines": int(coverage_summary.get("covered_lines", 0) or 0),
                    "missing_lines": int(coverage_summary.get("missing_lines", 0) or 0),
                    "num_statements": int(coverage_summary.get("num_statements", 0) or 0),
                    "baseline_percent": float(baseline_coverage)
                    if isinstance(baseline_coverage, (int, float))
                    else None,
                    "delta_vs_baseline": (
                        float(coverage_percent) - float(baseline_coverage)
                        if isinstance(coverage_percent, (int, float))
                        and isinstance(baseline_coverage, (int, float))
                        else None
                    ),
                },
                "complexity": {
                    **complexity,
                    "baseline_score": int(baseline_complexity)
                    if isinstance(baseline_complexity, (int, float))
                    else None,
                    "ceiling": int(complexity_ceiling)
                    if isinstance(complexity_ceiling, (int, float))
                    else None,
                    "delta_vs_baseline": (
                        int(complexity["score"]) - int(baseline_complexity)
                        if isinstance(complexity.get("score"), int)
                        and isinstance(baseline_complexity, (int, float))
                        else None
                    ),
                },
                "report_only": True,
            }
        )

    return {
        "report_only": True,
        "baseline_path": str(hotspot_baseline_path),
        "coverage_json_path": str(coverage_json_path),
        "hotspot_count": len(hotspots),
        "missing_baseline_count": len(missing_baselines),
        "missing_baseline_paths": missing_baselines,
        "hotspots": hotspots,
    }


def _diff_findings(
    *,
    current: list[dict[str, Any]],
    baseline: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    current_map = {_finding_key(item): item for item in current}
    baseline_map = {_finding_key(item): item for item in baseline}

    current_keys = set(current_map.keys())
    baseline_keys = set(baseline_map.keys())

    new_keys = sorted(current_keys - baseline_keys)
    resolved_keys = sorted(baseline_keys - current_keys)
    known_keys = sorted(current_keys & baseline_keys)

    return {
        "new": [current_map[key] for key in new_keys],
        "resolved": [baseline_map[key] for key in resolved_keys],
        "known": [current_map[key] for key in known_keys],
    }


def _build_markdown(summary: dict[str, Any]) -> str:
    commands = summary.get("commands")
    command_rows = commands if isinstance(commands, list) else []
    hotspot_checks = summary.get("hotspot_checks")
    hotspot_check_rows = hotspot_checks if isinstance(hotspot_checks, list) else []
    pip_audit = summary.get("pip_audit")
    pip_audit_section = pip_audit if isinstance(pip_audit, dict) else {}
    hotspot_summary = summary.get("hotspot_summary")
    hotspot_section = hotspot_summary if isinstance(hotspot_summary, dict) else {}
    friction = summary.get("friction")
    friction_section = friction if isinstance(friction, dict) else {}
    lines = [
        "# ACE-Lite Quality Gate",
        "",
        f"- Generated: {summary.get('generated_at', '')}",
        f"- Passed: {bool(summary.get('passed', False))}",
        f"- Fail on new vulnerabilities: {bool(summary.get('fail_on_new_vulns', False))}",
        "",
        "## Commands",
        "",
        "| Name | Passed | Exit Code | Elapsed (ms) |",
        "| --- | :---: | ---: | ---: |",
    ]
    for row in command_rows:
        if not isinstance(row, dict):
            continue
        lines.append(
            "| {name} | {passed} | {code} | {elapsed:.2f} |".format(
                name=str(row.get("name") or ""),
                passed="PASS" if bool(row.get("passed", False)) else "FAIL",
                code=int(row.get("returncode", 0) or 0),
                elapsed=float(row.get("elapsed_ms", 0.0) or 0.0),
            )
        )
    lines.extend(
        [
            "",
            "## Pip Audit",
            "",
            f"- Parsed JSON: {bool(pip_audit_section.get('parsed', False))}",
            f"- Baseline path: {pip_audit_section.get('baseline_path') or ''!s}",
            f"- Current findings: {int(pip_audit_section.get('current_count', 0) or 0)}",
            f"- Baseline findings: {int(pip_audit_section.get('baseline_count', 0) or 0)}",
            f"- New findings: {int(pip_audit_section.get('new_count', 0) or 0)}",
            f"- Resolved findings: {int(pip_audit_section.get('resolved_count', 0) or 0)}",
            "",
        ]
    )
    new_findings = pip_audit_section.get("new_findings")
    new_rows = new_findings if isinstance(new_findings, list) else []
    if new_rows:
        lines.append("### New Findings")
        for item in new_rows:
            if not isinstance(item, dict):
                continue
            lines.append(
                "- {package}::{vuln_id} (fix: {fix})".format(
                    package=str(item.get("package") or ""),
                    vuln_id=str(item.get("id") or ""),
                    fix=", ".join(item.get("fix_versions", []))
                    if isinstance(item.get("fix_versions"), list)
                    else "",
                )
            )
        lines.append("")
    lines.extend(
        [
            "## Hotspot Summary",
            "",
            f"- Report only: {bool(hotspot_section.get('report_only', True))}",
            f"- Baseline path: {hotspot_section.get('baseline_path') or ''!s}",
            f"- Coverage JSON: {hotspot_section.get('coverage_json_path') or ''!s}",
            f"- Hotspot count: {int(hotspot_section.get('hotspot_count', 0) or 0)}",
            f"- Missing baselines: {int(hotspot_section.get('missing_baseline_count', 0) or 0)}",
            "",
        ]
    )
    hotspot_rows = hotspot_section.get("hotspots")
    if isinstance(hotspot_rows, list) and hotspot_rows:
        lines.extend(
            [
                "| Path | Coverage % | Complexity | Baseline Cov % | Baseline Complexity |",
                "| --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for item in hotspot_rows:
            if not isinstance(item, dict):
                continue
            coverage = item.get("coverage", {})
            complexity = item.get("complexity", {})
            coverage_percent = (
                float(coverage.get("percent"))
                if isinstance(coverage, dict)
                and isinstance(coverage.get("percent"), (int, float))
                else None
            )
            complexity_score = (
                int(complexity.get("score"))
                if isinstance(complexity, dict)
                and isinstance(complexity.get("score"), int)
                else None
            )
            baseline_coverage = (
                float(coverage.get("baseline_percent"))
                if isinstance(coverage, dict)
                and isinstance(coverage.get("baseline_percent"), (int, float))
                else None
            )
            baseline_complexity = (
                int(complexity.get("baseline_score"))
                if isinstance(complexity, dict)
                and isinstance(complexity.get("baseline_score"), int)
                else None
            )
            lines.append(
                "| {path} | {coverage_percent} | {complexity_score} | {baseline_coverage} | {baseline_complexity} |".format(
                    path=str(item.get("path") or ""),
                    coverage_percent=f"{coverage_percent:.2f}" if coverage_percent is not None else "-",
                    complexity_score=str(complexity_score) if complexity_score is not None else "-",
                    baseline_coverage=f"{baseline_coverage:.2f}" if baseline_coverage is not None else "-",
                    baseline_complexity=str(baseline_complexity)
                    if baseline_complexity is not None
                    else "-",
                )
            )
        lines.append("")
    lines.extend(
        [
            "## Hotspot Checks",
            "",
            "- Report only: True",
            "",
        ]
    )
    if hotspot_check_rows:
        lines.extend(
            [
                "| Name | Passed | Exit Code | Elapsed (ms) |",
                "| --- | :---: | ---: | ---: |",
            ]
        )
        for row in hotspot_check_rows:
            if not isinstance(row, dict):
                continue
            lines.append(
                "| {name} | {passed} | {code} | {elapsed:.2f} |".format(
                    name=str(row.get("name") or ""),
                    passed="PASS" if bool(row.get("passed", False)) else "FAIL",
                    code=int(row.get("returncode", 0) or 0),
                    elapsed=float(row.get("elapsed_ms", 0.0) or 0.0),
                )
            )
        lines.append("")
    lines.extend(
        [
            "## Friction",
            "",
            f"- Enabled: {bool(friction_section.get('enabled', False))}",
            f"- Log path: {friction_section.get('log_path') or ''!s}",
            f"- Events logged this run: {int(friction_section.get('events_logged', 0) or 0)}",
            "",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _quality_commands(
    *,
    python_exe: str,
    coverage_json_path: Path,
) -> list[tuple[str, list[str]]]:
    return [
        ("ruff", [python_exe, "-m", "ruff", "check", *RUFF_TARGETS]),
        (
            "skills_lint",
            [python_exe, "-m", "pytest", "-q", "tests/unit/test_skills.py", "-k", "lint"],
        ),
        ("mypy", [python_exe, "-m", "mypy"]),
        (
            "bandit",
            [
                python_exe,
                "-m",
                "bandit",
                "-q",
                "-c",
                "pyproject.toml",
                "-r",
                *BANDIT_TARGETS,
            ],
        ),
        (
            "pytest_cov",
            [
                python_exe,
                "-m",
                "pytest",
                "--cov=ace_lite",
                "--cov-report=term-missing",
                f"--cov-report=json:{coverage_json_path}",
                "-q",
            ],
        ),
    ]


def _quality_hotspot_commands(
    *,
    python_exe: str,
    hotspot_paths: list[str] | None = None,
) -> list[tuple[str, list[str]]]:
    base_targets = tuple(
        _normalize_hotspot_path(path)
        for path in (hotspot_paths if isinstance(hotspot_paths, list) else HOTSPOT_TARGETS)
        if _normalize_hotspot_path(path)
    )
    if not base_targets:
        return []
    mypy_targets = list(base_targets)
    for path in base_targets:
        for companion in MYPY_HOTSPOT_COMPANION_TARGETS.get(path, ()):
            normalized = _normalize_hotspot_path(companion)
            if normalized and normalized not in mypy_targets:
                mypy_targets.append(normalized)
    return [
        ("ruff_hotspots", [python_exe, "-m", "ruff", "check", *base_targets]),
        ("mypy_hotspots", [python_exe, "-m", "mypy", *mypy_targets]),
    ]


def run_quality_gate(
    *,
    root: Path,
    output_dir: Path,
    baseline_path: Path,
    hotspot_baseline_path: Path | None = None,
    fail_on_new_vulns: bool,
    python_exe: str,
    friction_log_path: Path | None = None,
    capture_friction: bool = False,
    include_hotspot_checks: bool = True,
    hotspot_paths: list[str] | None = None,
    refresh_hotspot_baseline: bool = False,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    coverage_json_path = output_dir / "coverage.json"
    resolved_hotspot_baseline = (
        hotspot_baseline_path
        if isinstance(hotspot_baseline_path, Path)
        else root / "benchmark" / "quality" / "hotspot_baseline.json"
    )

    command_summaries: list[dict[str, Any]] = []
    hotspot_check_summaries: list[dict[str, Any]] = []
    all_required_passed = True
    friction_events_logged = 0

    def _capture_friction(
        *,
        query: str,
        expected: str,
        actual: str,
        severity: str,
        root_cause: str,
        manual_fix: str,
        context: dict[str, Any] | None = None,
        time_cost_min: float = 0.0,
        tags: list[str] | None = None,
    ) -> None:
        nonlocal friction_events_logged
        if not capture_friction or not isinstance(friction_log_path, Path):
            return
        event = make_event(
            stage="quality_gate",
            query=query,
            expected=expected,
            actual=actual,
            severity=severity,
            source="quality_gate:auto",
            root_cause=root_cause,
            manual_fix=manual_fix,
            context=context or {},
            time_cost_min=time_cost_min,
            tags=tags or [],
        )
        append_event(path=friction_log_path, event=event)
        friction_events_logged += 1

    for name, command in _quality_commands(
        python_exe=python_exe,
        coverage_json_path=coverage_json_path,
    ):
        result = _run_command(name=name, command=command, cwd=root)
        _write_command_logs(result=result, output_dir=output_dir)
        summary = {
            "name": result.name,
            "command": result.command,
            "returncode": result.returncode,
            "elapsed_ms": result.elapsed_ms,
            "passed": result.passed,
        }
        command_summaries.append(summary)
        if not result.passed:
            all_required_passed = False
            _capture_friction(
                query=name,
                expected="command returncode=0",
                actual=f"returncode={result.returncode}",
                severity="high" if name == "pytest_cov" else "medium",
                root_cause="quality_gate_command_failure",
                manual_fix=(
                    "Inspect logs under artifacts/quality/latest/logs and fix lint/type/test/security issues."
                ),
                context={
                    "returncode": int(result.returncode),
                    "elapsed_ms": float(result.elapsed_ms),
                    "command": result.command,
                },
                time_cost_min=max(0.1, float(result.elapsed_ms) / 60000.0),
                tags=["quality-gate", name],
            )

    pip_command = [
        python_exe,
        "-m",
        "pip_audit",
        "--progress-spinner",
        "off",
        "--format",
        "json",
    ]
    pip_result = _run_command(name="pip_audit", command=pip_command, cwd=root)
    _write_command_logs(result=pip_result, output_dir=output_dir)
    pip_command_ok = pip_result.returncode in {0, 1}
    pip_payload = _extract_json_payload(pip_result.stdout) or _extract_json_payload(
        pip_result.stderr
    )
    pip_parsed = bool(pip_payload)
    current_findings = _collect_findings(pip_payload) if pip_parsed else []
    baseline_findings = _load_baseline(path=baseline_path)
    diff = _diff_findings(current=current_findings, baseline=baseline_findings)
    pip_new_count = len(diff["new"])
    pip_gate_passed = pip_command_ok and pip_parsed and (
        (not fail_on_new_vulns) or pip_new_count == 0
    )
    if not pip_gate_passed:
        all_required_passed = False
    if not pip_command_ok:
        _capture_friction(
            query="pip_audit invocation",
            expected="returncode in {0,1}",
            actual=f"returncode={pip_result.returncode}",
            severity="high",
            root_cause="pip_audit_invocation_failure",
            manual_fix="Check pip-audit installation/runtime and retry quality gate.",
            context={"stderr": pip_result.stderr[:500], "stdout": pip_result.stdout[:500]},
            tags=["quality-gate", "pip-audit"],
        )
    if pip_command_ok and not pip_parsed:
        _capture_friction(
            query="pip_audit parse",
            expected="valid json payload",
            actual="json parse failed",
            severity="high",
            root_cause="pip_audit_parse_failure",
            manual_fix="Verify pip-audit output format and parser compatibility.",
            context={"stdout": pip_result.stdout[:500], "stderr": pip_result.stderr[:500]},
            tags=["quality-gate", "pip-audit"],
        )
    if pip_new_count > 0:
        _capture_friction(
            query="pip_audit baseline diff",
            expected="new_findings=0",
            actual=f"new_findings={pip_new_count}",
            severity="critical" if fail_on_new_vulns else "high",
            root_cause="dependency_vulnerability_regression",
            manual_fix=(
                "Upgrade vulnerable dependencies or approve+update baseline after security review."
            ),
            context={
                "new_findings": diff["new"],
                "baseline_path": str(baseline_path),
                "fail_on_new_vulns": bool(fail_on_new_vulns),
            },
            tags=["quality-gate", "dependency-security"],
        )

    command_summaries.append(
        {
            "name": pip_result.name,
            "command": pip_result.command,
            "returncode": pip_result.returncode,
            "elapsed_ms": pip_result.elapsed_ms,
            "passed": pip_gate_passed,
            "invocation_passed": pip_command_ok,
            "json_parsed": pip_parsed,
            "new_findings": pip_new_count,
        }
    )

    if include_hotspot_checks:
        for name, command in _quality_hotspot_commands(
            python_exe=python_exe,
            hotspot_paths=hotspot_paths,
        ):
            result = _run_command(name=name, command=command, cwd=root)
            _write_command_logs(result=result, output_dir=output_dir)
            hotspot_check_summaries.append(
                {
                    "name": result.name,
                    "command": result.command,
                    "returncode": result.returncode,
                    "elapsed_ms": result.elapsed_ms,
                    "passed": result.passed,
                    "report_only": True,
                }
            )

    if refresh_hotspot_baseline:
        resolved_hotspot_baseline.parent.mkdir(parents=True, exist_ok=True)
        resolved_hotspot_baseline.write_text(
            json.dumps(
                _build_hotspot_baseline_payload(
                    root=root,
                    coverage_json_path=coverage_json_path,
                    hotspot_paths=hotspot_paths,
                ),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "fail_on_new_vulns": bool(fail_on_new_vulns),
        "commands": command_summaries,
        "hotspot_checks": hotspot_check_summaries,
        "pip_audit": {
            "parsed": pip_parsed,
            "baseline_path": str(baseline_path),
            "current_count": len(current_findings),
            "baseline_count": len(baseline_findings),
            "new_count": len(diff["new"]),
            "resolved_count": len(diff["resolved"]),
            "known_count": len(diff["known"]),
            "new_findings": diff["new"],
            "resolved_findings": diff["resolved"],
            "known_findings": diff["known"],
            "invocation_passed": pip_command_ok,
        },
        "friction": {
            "enabled": bool(capture_friction and isinstance(friction_log_path, Path)),
            "log_path": str(friction_log_path) if isinstance(friction_log_path, Path) else "",
            "events_logged": friction_events_logged,
        },
        "hotspot_summary": _build_hotspot_summary(
            root=root,
            coverage_json_path=coverage_json_path,
            hotspot_baseline_path=resolved_hotspot_baseline,
            hotspot_paths=hotspot_paths,
        ),
        "passed": all_required_passed,
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run ACE-Lite quality gate and emit machine-readable artifacts."
    )
    parser.add_argument("--root", default=".", help="Repository root path.")
    parser.add_argument(
        "--output-dir",
        default="artifacts/quality/latest",
        help="Output directory for quality artifacts.",
    )
    parser.add_argument(
        "--pip-audit-baseline",
        default="benchmark/quality/pip_audit_baseline.json",
        help="Baseline file used to detect newly introduced vulnerabilities.",
    )
    parser.add_argument(
        "--hotspot-baseline",
        default="benchmark/quality/hotspot_baseline.json",
        help="Report-only hotspot baseline metadata file.",
    )
    parser.add_argument(
        "--hotspot-path",
        action="append",
        dest="hotspot_paths",
        default=None,
        help=(
            "Limit report-only hotspot summary and ruff/mypy hotspot checks to a specific "
            "repo-relative path. Repeat for multiple paths."
        ),
    )
    parser.add_argument(
        "--refresh-hotspot-baseline",
        action="store_true",
        help="Rewrite hotspot baseline metadata from the current coverage/complexity snapshot.",
    )
    parser.add_argument(
        "--fail-on-new-vulns",
        action="store_true",
        help="Fail when pip-audit reports vulnerabilities not present in baseline.",
    )
    parser.add_argument(
        "--print-json",
        action="store_true",
        help="Print summary JSON to stdout.",
    )
    parser.add_argument(
        "--friction-log",
        default="artifacts/friction/events.jsonl",
        help="Friction JSONL output path for auto-captured quality failures.",
    )
    parser.add_argument(
        "--no-hotspot-checks",
        action="store_false",
        dest="include_hotspot_checks",
        help="Disable report-only ruff/mypy hotspot checks.",
    )
    parser.add_argument(
        "--no-capture-friction",
        action="store_false",
        dest="capture_friction",
        help="Disable automatic friction event capture.",
    )
    parser.set_defaults(capture_friction=True, include_hotspot_checks=True)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    root = _resolve_path(root=project_root, value=str(args.root))
    output_dir = _resolve_path(root=project_root, value=str(args.output_dir))
    baseline_path = _resolve_path(root=project_root, value=str(args.pip_audit_baseline))
    hotspot_baseline_path = _resolve_path(root=project_root, value=str(args.hotspot_baseline))
    friction_log_path = _resolve_path(root=project_root, value=str(args.friction_log))

    summary = run_quality_gate(
        root=root,
        output_dir=output_dir,
        baseline_path=baseline_path,
        hotspot_baseline_path=hotspot_baseline_path,
        fail_on_new_vulns=bool(args.fail_on_new_vulns),
        python_exe=sys.executable,
        friction_log_path=friction_log_path,
        capture_friction=bool(args.capture_friction),
        include_hotspot_checks=bool(args.include_hotspot_checks),
        hotspot_paths=list(args.hotspot_paths) if isinstance(args.hotspot_paths, list) else None,
        refresh_hotspot_baseline=bool(args.refresh_hotspot_baseline),
    )

    summary_path = output_dir / "summary.json"
    report_path = output_dir / "report.md"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(_build_markdown(summary), encoding="utf-8")

    print(f"[quality] summary: {summary_path}")
    print(f"[quality] report:  {report_path}")
    print(f"[quality] passed={bool(summary.get('passed', False))}")

    if args.print_json:
        print(json.dumps(summary, ensure_ascii=False))

    return 0 if bool(summary.get("passed", False)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
