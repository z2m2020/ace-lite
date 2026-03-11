from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

import yaml

DEFAULT_REQUIRED_STAGES = [
    "memory",
    "index",
    "repomap",
    "augment",
    "skills",
    "source_plan",
]


@dataclass
class CommandResult:
    cmd: list[str]
    returncode: int
    stdout: str
    stderr: str
    elapsed_ms: float


def _run_command(*, cmd: list[str], cwd: Path | None = None) -> CommandResult:
    started = perf_counter()
    completed = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=False,
        capture_output=True,
        text=True,
    )
    elapsed_ms = (perf_counter() - started) * 1000.0
    return CommandResult(
        cmd=cmd,
        returncode=int(completed.returncode),
        stdout=str(completed.stdout or ""),
        stderr=str(completed.stderr or ""),
        elapsed_ms=elapsed_ms,
    )


def _resolve_path(*, root: Path, value: str) -> Path:
    candidate = Path(str(value).strip())
    if candidate.is_absolute():
        return candidate
    return (root / candidate).resolve()


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _coerce_int(value: Any, default: int = 0, minimum: int | None = None) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = int(default)
    if minimum is not None:
        return max(minimum, parsed)
    return parsed


def _coerce_float(value: Any, default: float = 0.0, minimum: float | None = None) -> float:
    try:
        parsed = float(value)
    except Exception:
        parsed = float(default)
    if minimum is not None:
        return max(minimum, parsed)
    return parsed


def _load_cases(*, path: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        cases = data.get("cases")
        if isinstance(cases, list):
            return [item for item in cases if isinstance(item, dict)]
        return []
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def _parse_plan_payload(stdout: str) -> dict[str, Any]:
    candidate = str(stdout or "").strip()
    if not candidate:
        raise ValueError("empty stdout from ace-lite plan")

    try:
        payload = json.loads(candidate)
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass

    for line in reversed(candidate.splitlines()):
        text = line.strip()
        if not text:
            continue
        if not text.startswith("{"):
            continue
        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                return payload
        except Exception:
            continue

    raise ValueError("unable to parse plan payload JSON from stdout")


def _normalize_stage_names(raw: Any) -> list[str]:
    source = raw if isinstance(raw, list) else []
    output: list[str] = []
    for item in source:
        name = str(item).strip().lower()
        if not name:
            continue
        if name not in output:
            output.append(name)
    return output


def _build_plan_command(
    *,
    cli_bin: str,
    query: str,
    repo: str,
    root: str,
    skills_dir: str,
    top_k_files: int,
    chunk_top_k: int,
    retrieval_policy: str,
    candidate_ranker: str,
    repomap_enabled: bool,
    case_overrides: dict[str, Any],
) -> list[str]:
    cmd = [
        str(cli_bin),
        "plan",
        "--query",
        query,
        "--repo",
        repo,
        "--root",
        root,
        "--skills-dir",
        skills_dir,
        "--memory-primary",
        "none",
        "--memory-secondary",
        "none",
        "--no-memory-cache",
        "--no-plugins",
        "--no-lsp",
        "--no-lsp-xref",
        "--no-cochange",
        "--no-scip",
        "--no-trace-export",
        "--no-trace-otlp",
        "--top-k-files",
        str(max(1, int(top_k_files))),
        "--chunk-top-k",
        str(max(1, int(chunk_top_k))),
        "--candidate-ranker",
        candidate_ranker,
        "--retrieval-policy",
        retrieval_policy,
    ]

    if repomap_enabled:
        cmd.append("--repomap")
    else:
        cmd.append("--no-repomap")

    if case_overrides.get("top_k_files") is not None:
        cmd.extend(["--top-k-files", str(max(1, _coerce_int(case_overrides.get("top_k_files"), 1, 1)))])

    if case_overrides.get("chunk_top_k") is not None:
        cmd.extend(["--chunk-top-k", str(max(1, _coerce_int(case_overrides.get("chunk_top_k"), 1, 1)))])

    if case_overrides.get("candidate_ranker") is not None:
        cmd.extend(["--candidate-ranker", str(case_overrides.get("candidate_ranker") or "heuristic")])

    if case_overrides.get("retrieval_policy") is not None:
        cmd.extend(["--retrieval-policy", str(case_overrides.get("retrieval_policy") or "auto")])

    if case_overrides.get("repomap") is not None:
        if _coerce_bool(case_overrides.get("repomap"), default=True):
            cmd.append("--repomap")
        else:
            cmd.append("--no-repomap")

    return cmd


def _extract_metrics(plan_payload: dict[str, Any]) -> dict[str, Any]:
    source_plan = plan_payload.get("source_plan")
    source_payload = source_plan if isinstance(source_plan, dict) else {}

    index_payload_raw = plan_payload.get("index")
    index_payload = index_payload_raw if isinstance(index_payload_raw, dict) else {}

    candidate_files = (
        index_payload.get("candidate_files") if isinstance(index_payload.get("candidate_files"), list) else []
    )
    candidate_chunks = (
        source_payload.get("candidate_chunks")
        if isinstance(source_payload.get("candidate_chunks"), list)
        else []
    )
    chunk_steps = (
        source_payload.get("chunk_steps") if isinstance(source_payload.get("chunk_steps"), list) else []
    )
    steps = source_payload.get("steps") if isinstance(source_payload.get("steps"), list) else []
    validation_tests = (
        source_payload.get("validation_tests")
        if isinstance(source_payload.get("validation_tests"), list)
        else []
    )

    stage_names = _normalize_stage_names(source_payload.get("stages"))
    if not stage_names:
        stage_names = _normalize_stage_names(plan_payload.get("pipeline_order"))

    return {
        "source_plan_steps": len(steps),
        "candidate_files": len(candidate_files),
        "candidate_chunks": len(candidate_chunks),
        "chunk_steps": len(chunk_steps),
        "validation_tests": len(validation_tests),
        "writeback_template_present": bool(source_payload.get("writeback_template")),
        "stage_names": stage_names,
    }


def _evaluate_case_success(
    *,
    case: dict[str, Any],
    plan_payload: dict[str, Any],
) -> tuple[bool, dict[str, Any], list[dict[str, Any]]]:
    expectations_raw = case.get("expectations")
    expectations = expectations_raw if isinstance(expectations_raw, dict) else {}

    metrics = _extract_metrics(plan_payload)

    min_steps = _coerce_int(
        expectations.get("min_source_plan_steps", expectations.get("min_steps", 1)),
        default=1,
        minimum=0,
    )
    min_candidate_files = _coerce_int(
        expectations.get("min_candidate_files", 1), default=1, minimum=0
    )
    min_candidate_chunks = _coerce_int(
        expectations.get("min_candidate_chunks", 1), default=1, minimum=0
    )
    min_chunk_steps = _coerce_int(
        expectations.get("min_chunk_steps", 1), default=1, minimum=0
    )
    min_validation_tests = _coerce_int(
        expectations.get("min_validation_tests", 0), default=0, minimum=0
    )

    required_stages_raw = expectations.get("required_stages", DEFAULT_REQUIRED_STAGES)
    required_stages = _normalize_stage_names(required_stages_raw)
    require_writeback_template = _coerce_bool(
        expectations.get("require_writeback_template", True), default=True
    )

    checks: list[dict[str, Any]] = []

    def add_min_check(metric: str, actual: int, expected: int) -> None:
        checks.append(
            {
                "metric": metric,
                "operator": ">=",
                "actual": int(actual),
                "expected": int(expected),
                "passed": int(actual) >= int(expected),
            }
        )

    add_min_check("source_plan_steps", int(metrics["source_plan_steps"]), min_steps)
    add_min_check("candidate_files", int(metrics["candidate_files"]), min_candidate_files)
    add_min_check("candidate_chunks", int(metrics["candidate_chunks"]), min_candidate_chunks)
    add_min_check("chunk_steps", int(metrics["chunk_steps"]), min_chunk_steps)
    add_min_check("validation_tests", int(metrics["validation_tests"]), min_validation_tests)

    if require_writeback_template:
        checks.append(
            {
                "metric": "writeback_template_present",
                "operator": "==",
                "actual": bool(metrics["writeback_template_present"]),
                "expected": True,
                "passed": bool(metrics["writeback_template_present"]),
            }
        )

    if required_stages:
        present = set(_normalize_stage_names(metrics.get("stage_names")))
        missing = [stage for stage in required_stages if stage not in present]
        checks.append(
            {
                "metric": "required_stages",
                "operator": "contains_all",
                "actual": sorted(present),
                "expected": required_stages,
                "missing": missing,
                "passed": len(missing) == 0,
            }
        )

    passed = all(bool(item.get("passed", False)) for item in checks)
    return passed, metrics, checks


def _render_markdown(*, summary: dict[str, Any], results: list[dict[str, Any]]) -> str:
    lines: list[str] = [
        "# ACE-Lite E2E Success Slice",
        "",
        f"- Generated: {summary.get('generated_at', '')}",
        f"- Passed: {bool(summary.get('passed', False))}",
        f"- Case count: {int(summary.get('case_count', 0) or 0)}",
        f"- Passed count: {int(summary.get('passed_count', 0) or 0)}",
        f"- Failed count: {int(summary.get('failed_count', 0) or 0)}",
        "- Task success rate: {value:.4f}".format(
            value=float(summary.get("task_success_rate", 0.0) or 0.0)
        ),
    ]

    if bool(summary.get("threshold_enabled", False)):
        lines.append(
            "- Success floor: {value:.4f}".format(
                value=float(summary.get("min_success_rate", 0.0) or 0.0)
            )
        )
        lines.append(
            "- Floor passed: {value}".format(
                value=bool(summary.get("threshold_passed", False))
            )
        )

    lines.extend([
        "",
        "## Cases",
        "",
        "| Case | Passed | Latency (ms) | Failure Count |",
        "| --- | :---: | ---: | ---: |",
    ])

    for item in results:
        if not isinstance(item, dict):
            continue
        checks = item.get("checks")
        check_list = checks if isinstance(checks, list) else []
        failure_count = sum(1 for check in check_list if not bool(check.get("passed", False)))
        lines.append(
            "| {case_id} | {passed} | {latency:.2f} | {failure_count} |".format(
                case_id=str(item.get("case_id", "(unknown)")),
                passed="PASS" if bool(item.get("passed", False)) else "FAIL",
                latency=float(item.get("elapsed_ms", 0.0) or 0.0),
                failure_count=int(failure_count),
            )
        )

    failures = summary.get("failed_cases")
    failed_cases = failures if isinstance(failures, list) else []
    lines.append("")
    if failed_cases:
        lines.append("## Failed Cases")
        lines.append("")
        for item in failed_cases:
            if not isinstance(item, dict):
                continue
            lines.append(
                "- {case_id}: {reason}".format(
                    case_id=str(item.get("case_id", "(unknown)")),
                    reason=str(item.get("reason", "validation_failed")),
                )
            )
            failed_checks = item.get("failed_checks")
            if isinstance(failed_checks, list) and failed_checks:
                lines.append(
                    "  - failed_checks: "
                    + ", ".join(str(value) for value in failed_checks if str(value).strip())
                )
            metrics_raw = item.get("metrics")
            metrics = metrics_raw if isinstance(metrics_raw, dict) else {}
            if metrics:
                lines.append(
                    "  - metrics: source_plan_steps={steps}, candidate_files={files}, candidate_chunks={chunks}, chunk_steps={chunk_steps}, validation_tests={tests}".format(
                        steps=int(metrics.get("source_plan_steps", 0) or 0),
                        files=int(metrics.get("candidate_files", 0) or 0),
                        chunks=int(metrics.get("candidate_chunks", 0) or 0),
                        chunk_steps=int(metrics.get("chunk_steps", 0) or 0),
                        tests=int(metrics.get("validation_tests", 0) or 0),
                    )
                )
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic E2E success slice for ACE-Lite.")
    parser.add_argument(
        "--cases",
        default="benchmark/cases/e2e/internal.yaml",
        help="YAML case file path.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/benchmark/e2e/latest",
        help="Output directory for e2e artifacts.",
    )
    parser.add_argument(
        "--cli-bin",
        default="ace-lite",
        help="CLI binary used to execute plan calls.",
    )
    parser.add_argument("--repo", default="ace-lite-engine", help="Repository id passed to plan.")
    parser.add_argument("--root", default=".", help="Repository root path passed to plan.")
    parser.add_argument("--skills-dir", default="skills", help="Skills directory path passed to plan.")
    parser.add_argument("--top-k-files", type=int, default=6, help="Default top-k files for cases.")
    parser.add_argument("--chunk-top-k", type=int, default=12, help="Default top-k chunks for cases.")
    parser.add_argument(
        "--retrieval-policy",
        default="auto",
        help="Default retrieval policy for cases.",
    )
    parser.add_argument(
        "--candidate-ranker",
        default="heuristic",
        help="Default candidate ranker for cases.",
    )
    parser.add_argument(
        "--repomap",
        dest="repomap_enabled",
        action="store_true",
        default=True,
        help="Enable repomap during case execution.",
    )
    parser.add_argument(
        "--no-repomap",
        dest="repomap_enabled",
        action="store_false",
        help="Disable repomap during case execution.",
    )
    parser.add_argument(
        "--min-success-rate",
        type=float,
        default=-1.0,
        help="Optional success floor; negative value disables threshold.",
    )
    parser.add_argument(
        "--fail-on-thresholds",
        action="store_true",
        help="Exit non-zero when threshold-enabled run fails the success floor.",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    cases_path = _resolve_path(root=project_root, value=str(args.cases))

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = project_root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    if not cases_path.exists() or not cases_path.is_file():
        raise FileNotFoundError(f"cases file not found: {cases_path}")

    cases = _load_cases(path=cases_path)
    if not cases:
        raise ValueError(f"no cases found in: {cases_path}")

    results: list[dict[str, Any]] = []
    failed_cases: list[dict[str, Any]] = []

    for index, case in enumerate(cases, start=1):
        query = str(case.get("query") or "").strip()
        case_id = str(case.get("case_id") or f"case-{index}").strip() or f"case-{index}"
        if not query:
            results.append(
                {
                    "case_id": case_id,
                    "query": query,
                    "passed": False,
                    "elapsed_ms": 0.0,
                    "command": "",
                    "checks": [],
                    "metrics": {},
                    "error": "missing query",
                }
            )
            failed_cases.append({"case_id": case_id, "reason": "missing_query"})
            continue

        command = _build_plan_command(
            cli_bin=str(args.cli_bin),
            query=query,
            repo=str(case.get("repo") or args.repo),
            root=str(case.get("root") or args.root),
            skills_dir=str(case.get("skills_dir") or args.skills_dir),
            top_k_files=max(1, int(args.top_k_files)),
            chunk_top_k=max(1, int(args.chunk_top_k)),
            retrieval_policy=str(args.retrieval_policy),
            candidate_ranker=str(args.candidate_ranker),
            repomap_enabled=bool(args.repomap_enabled),
            case_overrides=case,
        )

        command_result = _run_command(cmd=command, cwd=project_root)

        if command_result.returncode != 0:
            reason = f"plan_exit_{command_result.returncode}"
            failed_cases.append({"case_id": case_id, "reason": reason})
            results.append(
                {
                    "case_id": case_id,
                    "query": query,
                    "passed": False,
                    "elapsed_ms": command_result.elapsed_ms,
                    "command": " ".join(shlex.quote(part) for part in command),
                    "checks": [],
                    "metrics": {},
                    "error": reason,
                    "stderr": command_result.stderr.strip()[:1200],
                }
            )
            continue

        try:
            payload = _parse_plan_payload(command_result.stdout)
            passed, metrics, checks = _evaluate_case_success(case=case, plan_payload=payload)
            results.append(
                {
                    "case_id": case_id,
                    "query": query,
                    "passed": passed,
                    "elapsed_ms": command_result.elapsed_ms,
                    "command": " ".join(shlex.quote(part) for part in command),
                    "checks": checks,
                    "metrics": metrics,
                }
            )
            if not passed:
                failed_cases.append(
                    {
                        "case_id": case_id,
                        "reason": "validation_failed",
                        "failed_checks": [
                            str(item.get("metric", "")).strip()
                            for item in checks
                            if not bool(item.get("passed", False))
                            and str(item.get("metric", "")).strip()
                        ],
                        "metrics": metrics,
                    }
                )
        except Exception as exc:
            failed_cases.append({"case_id": case_id, "reason": "parse_or_validate_error"})
            results.append(
                {
                    "case_id": case_id,
                    "query": query,
                    "passed": False,
                    "elapsed_ms": command_result.elapsed_ms,
                    "command": " ".join(shlex.quote(part) for part in command),
                    "checks": [],
                    "metrics": {},
                    "error": str(exc),
                }
            )

    case_count = len(results)
    passed_count = sum(1 for item in results if bool(item.get("passed", False)))
    failed_count = max(0, case_count - passed_count)
    task_success_rate = float(passed_count) / float(case_count) if case_count > 0 else 0.0

    min_success_rate = _coerce_float(args.min_success_rate, default=-1.0)
    threshold_enabled = min_success_rate >= 0.0
    threshold_passed = (task_success_rate >= min_success_rate) if threshold_enabled else True

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo": str(args.repo),
        "root": str(args.root),
        "cases_path": str(cases_path),
        "case_count": case_count,
        "passed_count": passed_count,
        "failed_count": failed_count,
        "task_success_rate": task_success_rate,
        "failed_cases": failed_cases,
        "threshold_enabled": threshold_enabled,
        "min_success_rate": min_success_rate if threshold_enabled else None,
        "threshold_passed": threshold_passed,
        "passed": failed_count == 0 and threshold_passed,
    }

    results_path = output_dir / "results.json"
    summary_path = output_dir / "summary.json"
    report_path = output_dir / "report.md"

    results_path.write_text(
        json.dumps(
            {
                "generated_at": summary["generated_at"],
                "cases_path": str(cases_path),
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(_render_markdown(summary=summary, results=results), encoding="utf-8")

    print(f"[e2e] report summary: {summary_path}")
    print(f"[e2e] report details: {results_path}")
    print(f"[e2e] report markdown: {report_path}")
    print(
        f"[e2e] cases={case_count} passed={passed_count} failed={failed_count} task_success_rate={task_success_rate:.4f}"
    )

    if args.fail_on_thresholds and threshold_enabled and not threshold_passed:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
