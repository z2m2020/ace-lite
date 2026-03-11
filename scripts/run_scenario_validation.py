from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

import yaml

from ace_lite.cli_app.orchestrator_factory import run_plan
from ace_lite.memory import LocalNotesProvider
from ace_lite.profile_store import ProfileStore


@dataclass
class StepExecution:
    action: str
    passed: bool
    elapsed_ms: float
    checks: list[dict[str, Any]]
    details: dict[str, Any]
    error: str | None = None


@dataclass
class ScenarioExecution:
    name: str
    passed: bool
    elapsed_ms: float
    steps: list[StepExecution]


class _EmptyMemoryProvider:
    strategy = "semantic"
    fallback_reason: str | None = None
    last_channel_used = "none"
    last_container_tag_fallback: str | None = None

    def search_compact(
        self,
        query: str,
        *,
        limit: int | None = None,
        container_tag: str | None = None,
    ) -> list[Any]:
        _ = (query, limit, container_tag)
        return []

    def fetch(self, handles: list[str]) -> list[Any]:
        _ = handles
        return []


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


def _load_scenarios(*, path: Path) -> list[dict[str, Any]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        raw = payload.get("scenarios")
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _append_note(
    *,
    notes_path: Path,
    text: str,
    namespace: str | None,
    repo: str,
    tags: list[str] | None = None,
) -> int:
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    if notes_path.exists() and notes_path.is_file():
        with notes_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    rows.append(payload)
    rows.append(
        {
            "text": text,
            "query": text,
            "repo": repo,
            "namespace": str(namespace or "").strip() or None,
            "tags": [str(item).strip() for item in (tags or []) if str(item).strip()],
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    with notes_path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(rows)


def _wipe_notes(*, notes_path: Path, namespace: str | None) -> int:
    if not notes_path.exists() or not notes_path.is_file():
        return 0
    rows: list[dict[str, Any]] = []
    with notes_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            raw = line.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    keep_rows: list[dict[str, Any]] = []
    removed = 0
    normalized = str(namespace or "").strip() or None
    for row in rows:
        row_namespace = str(row.get("namespace") or "").strip() or None
        if normalized and row_namespace == normalized:
            removed += 1
            continue
        if normalized is None:
            removed += 1
            continue
        keep_rows.append(row)
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    with notes_path.open("w", encoding="utf-8") as fh:
        for row in keep_rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return removed


def _build_notes_provider(
    *,
    enabled: bool,
    notes_path: Path,
    notes_limit: int,
    notes_mode: str,
    notes_expiry_enabled: bool,
    notes_ttl_days: int,
    notes_max_age_days: int,
) -> Any | None:
    if not enabled:
        return None
    return LocalNotesProvider(
        _EmptyMemoryProvider(),
        notes_path=str(notes_path),
        default_limit=max(1, int(notes_limit)),
        mode=str(notes_mode or "supplement").strip().lower() or "supplement",
        expiry_enabled=bool(notes_expiry_enabled),
        ttl_days=max(1, int(notes_ttl_days)),
        max_age_days=max(1, int(notes_max_age_days)),
    )


def _add_bool_check(
    checks: list[dict[str, Any]],
    *,
    metric: str,
    actual: bool,
    expected: bool,
) -> None:
    checks.append(
        {
            "metric": metric,
            "operator": "==",
            "actual": bool(actual),
            "expected": bool(expected),
            "passed": bool(actual) is bool(expected),
        }
    )


def _add_min_check(
    checks: list[dict[str, Any]],
    *,
    metric: str,
    actual: int,
    expected: int,
) -> None:
    checks.append(
        {
            "metric": metric,
            "operator": ">=",
            "actual": int(actual),
            "expected": int(expected),
            "passed": int(actual) >= int(expected),
        }
    )


def _add_max_check(
    checks: list[dict[str, Any]],
    *,
    metric: str,
    actual: float,
    expected: float,
) -> None:
    checks.append(
        {
            "metric": metric,
            "operator": "<=",
            "actual": float(actual),
            "expected": float(expected),
            "passed": float(actual) <= float(expected),
        }
    )


def _evaluate_plan_expectations(
    *,
    payload: dict[str, Any],
    expected: dict[str, Any],
) -> list[dict[str, Any]]:
    index_stage = payload.get("index", {}) if isinstance(payload.get("index"), dict) else {}
    source_plan = (
        payload.get("source_plan", {})
        if isinstance(payload.get("source_plan"), dict)
        else {}
    )
    memory_stage = payload.get("memory", {}) if isinstance(payload.get("memory"), dict) else {}
    repomap_stage = (
        payload.get("repomap", {}) if isinstance(payload.get("repomap"), dict) else {}
    )
    cochange_stage = (
        index_stage.get("cochange", {}) if isinstance(index_stage.get("cochange"), dict) else {}
    )
    profile_stage = (
        memory_stage.get("profile", {}) if isinstance(memory_stage.get("profile"), dict) else {}
    )
    capture_stage = (
        memory_stage.get("capture", {}) if isinstance(memory_stage.get("capture"), dict) else {}
    )

    candidate_files = (
        index_stage.get("candidate_files")
        if isinstance(index_stage.get("candidate_files"), list)
        else []
    )
    candidate_chunks = (
        source_plan.get("candidate_chunks")
        if isinstance(source_plan.get("candidate_chunks"), list)
        else []
    )
    source_steps = (
        source_plan.get("steps") if isinstance(source_plan.get("steps"), list) else []
    )
    chunk_steps = (
        source_plan.get("chunk_steps")
        if isinstance(source_plan.get("chunk_steps"), list)
        else []
    )

    checks: list[dict[str, Any]] = []

    _add_min_check(
        checks,
        metric="candidate_files_count",
        actual=len(candidate_files),
        expected=_coerce_int(expected.get("min_candidate_files", 1), default=1, minimum=0),
    )
    _add_min_check(
        checks,
        metric="candidate_chunks_count",
        actual=len(candidate_chunks),
        expected=_coerce_int(expected.get("min_candidate_chunks", 1), default=1, minimum=0),
    )
    _add_min_check(
        checks,
        metric="source_plan_steps_count",
        actual=len(source_steps),
        expected=_coerce_int(expected.get("min_source_plan_steps", 1), default=1, minimum=0),
    )
    _add_min_check(
        checks,
        metric="chunk_steps_count",
        actual=len(chunk_steps),
        expected=_coerce_int(expected.get("min_chunk_steps", 1), default=1, minimum=0),
    )

    if "expected_policy" in expected:
        expected_policy = str(expected.get("expected_policy") or "").strip().lower()
        actual_policy = str(index_stage.get("policy_name") or "").strip().lower()
        _add_bool_check(
            checks,
            metric="policy_name_matches",
            actual=actual_policy == expected_policy,
            expected=True,
        )

    if "repomap_enabled" in expected:
        _add_bool_check(
            checks,
            metric="repomap_enabled",
            actual=bool(repomap_stage.get("enabled", False)),
            expected=_coerce_bool(expected.get("repomap_enabled"), default=True),
        )

    if "cochange_enabled" in expected:
        _add_bool_check(
            checks,
            metric="cochange_enabled",
            actual=bool(cochange_stage.get("enabled", False)),
            expected=_coerce_bool(expected.get("cochange_enabled"), default=True),
        )

    if "require_memory_hit" in expected:
        _add_bool_check(
            checks,
            metric="memory_hit",
            actual=_coerce_int(memory_stage.get("count", 0), default=0, minimum=0) > 0,
            expected=_coerce_bool(expected.get("require_memory_hit"), default=True),
        )

    if "require_profile_selected" in expected:
        _add_bool_check(
            checks,
            metric="profile_selected",
            actual=_coerce_int(profile_stage.get("selected_count", 0), default=0, minimum=0) > 0,
            expected=_coerce_bool(expected.get("require_profile_selected"), default=True),
        )

    if "require_capture_triggered" in expected:
        _add_bool_check(
            checks,
            metric="capture_triggered",
            actual=bool(capture_stage.get("triggered", False)),
            expected=_coerce_bool(expected.get("require_capture_triggered"), default=True),
        )

    candidate_paths = [
        str(item.get("path") or "")
        for item in candidate_files
        if isinstance(item, dict) and str(item.get("path") or "").strip()
    ]
    required_paths_raw = expected.get("candidate_paths_contains")
    required_paths = required_paths_raw if isinstance(required_paths_raw, list) else []
    for item in required_paths:
        needle = str(item).strip()
        if not needle:
            continue
        matches = [path for path in candidate_paths if needle in path]
        checks.append(
            {
                "metric": f"candidate_path_contains:{needle}",
                "operator": "contains",
                "actual": candidate_paths,
                "expected": needle,
                "passed": bool(matches),
            }
        )

    if "max_chunk_budget_ratio" in expected:
        chunk_budget_used = _coerce_float(source_plan.get("chunk_budget_used", 0.0), default=0.0)
        chunk_budget_limit = _coerce_float(source_plan.get("chunk_budget_limit", 1.0), default=1.0, minimum=1.0)
        ratio = chunk_budget_used / max(1.0, chunk_budget_limit)
        _add_max_check(
            checks,
            metric="chunk_budget_ratio",
            actual=ratio,
            expected=_coerce_float(expected.get("max_chunk_budget_ratio", 1.0), default=1.0, minimum=0.0),
        )

    return checks


def _run_plan_step(
    *,
    scenario_name: str,
    step: dict[str, Any],
    repo: str,
    root: Path,
    skills_dir: Path,
    notes_path: Path,
    profile_path: Path,
    index_cache_path: Path,
    default_top_k_files: int,
    default_chunk_top_k: int,
) -> StepExecution:
    started = perf_counter()
    query = str(step.get("query") or "").strip()
    if not query:
        return StepExecution(
            action="plan",
            passed=False,
            elapsed_ms=0.0,
            checks=[],
            details={},
            error="missing query",
        )

    retrieval_policy = str(step.get("retrieval_policy") or "auto").strip().lower() or "auto"
    top_k_files = _coerce_int(step.get("top_k_files"), default_top_k_files, minimum=1)
    chunk_top_k = _coerce_int(step.get("chunk_top_k"), default_chunk_top_k, minimum=1)

    memory_container_tag = str(step.get("memory_container_tag") or "").strip() or None
    memory_profile_enabled = _coerce_bool(step.get("memory_profile_enabled"), default=False)
    memory_capture_enabled = _coerce_bool(step.get("memory_capture_enabled"), default=False)
    memory_notes_enabled = _coerce_bool(step.get("memory_notes_enabled"), default=False)

    notes_limit = _coerce_int(step.get("memory_notes_limit"), default=8, minimum=1)
    notes_mode = str(step.get("memory_notes_mode") or "supplement").strip().lower() or "supplement"
    notes_expiry_enabled = _coerce_bool(step.get("memory_notes_expiry_enabled"), default=True)
    notes_ttl_days = _coerce_int(step.get("memory_notes_ttl_days"), default=90, minimum=1)
    notes_max_age_days = _coerce_int(step.get("memory_notes_max_age_days"), default=365, minimum=1)

    memory_provider = _build_notes_provider(
        enabled=memory_notes_enabled,
        notes_path=notes_path,
        notes_limit=notes_limit,
        notes_mode=notes_mode,
        notes_expiry_enabled=notes_expiry_enabled,
        notes_ttl_days=notes_ttl_days,
        notes_max_age_days=notes_max_age_days,
    )

    try:
        payload = run_plan(
            query=query,
            repo=repo,
            root=str(root),
            skills_dir=str(skills_dir),
            memory_provider=memory_provider,
            memory_strategy=str(step.get("memory_strategy") or "semantic").strip().lower() or "semantic",
            memory_container_tag=memory_container_tag,
            memory_auto_tag_mode=None,
            memory_profile_enabled=memory_profile_enabled,
            memory_profile_path=str(profile_path),
            memory_profile_top_n=_coerce_int(step.get("memory_profile_top_n"), default=4, minimum=1),
            memory_profile_token_budget=_coerce_int(step.get("memory_profile_token_budget"), default=160, minimum=1),
            memory_capture_enabled=memory_capture_enabled,
            memory_capture_notes_path=str(notes_path),
            memory_capture_min_query_length=_coerce_int(
                step.get("memory_capture_min_query_length"),
                default=24,
                minimum=1,
            ),
            memory_capture_keywords=[
                str(item).strip()
                for item in (step.get("memory_capture_keywords") or [])
                if str(item).strip()
            ],
            memory_notes_enabled=memory_notes_enabled,
            memory_notes_path=str(notes_path),
            memory_notes_limit=notes_limit,
            memory_notes_mode=notes_mode,
            memory_notes_expiry_enabled=notes_expiry_enabled,
            memory_notes_ttl_days=notes_ttl_days,
            memory_notes_max_age_days=notes_max_age_days,
            top_k_files=top_k_files,
            chunk_top_k=chunk_top_k,
            repomap_enabled=_coerce_bool(step.get("repomap_enabled"), default=True),
            cochange_enabled=_coerce_bool(step.get("cochange_enabled"), default=False),
            retrieval_policy=retrieval_policy,
            candidate_ranker=str(step.get("candidate_ranker") or "heuristic").strip().lower() or "heuristic",
            index_cache_path=str(index_cache_path),
            index_incremental=True,
            plugins_enabled=False,
            lsp_enabled=False,
            lsp_xref_enabled=False,
            scip_enabled=False,
            trace_export_enabled=False,
            trace_otlp_enabled=False,
        )
    except Exception as exc:
        elapsed_ms = (perf_counter() - started) * 1000.0
        return StepExecution(
            action="plan",
            passed=False,
            elapsed_ms=elapsed_ms,
            checks=[],
            details={"query": query, "scenario": scenario_name},
            error=f"plan_error:{exc.__class__.__name__}",
        )

    expected_raw = step.get("expected")
    expected = expected_raw if isinstance(expected_raw, dict) else {}
    checks = _evaluate_plan_expectations(payload=payload, expected=expected)
    passed = all(bool(item.get("passed", False)) for item in checks)
    elapsed_ms = (perf_counter() - started) * 1000.0
    return StepExecution(
        action="plan",
        passed=passed,
        elapsed_ms=elapsed_ms,
        checks=checks,
        details={
            "query": query,
            "scenario": scenario_name,
            "retrieval_policy": retrieval_policy,
            "candidate_files_count": len(
                payload.get("index", {}).get("candidate_files", [])
                if isinstance(payload.get("index"), dict)
                else []
            ),
            "candidate_chunks_count": len(
                payload.get("source_plan", {}).get("candidate_chunks", [])
                if isinstance(payload.get("source_plan"), dict)
                else []
            ),
            "memory_count": int(
                payload.get("memory", {}).get("count", 0)
                if isinstance(payload.get("memory"), dict)
                else 0
            ),
            "policy_name": str(
                payload.get("index", {}).get("policy_name", "")
                if isinstance(payload.get("index"), dict)
                else ""
            ),
        },
    )


def _run_memory_store_step(
    *,
    step: dict[str, Any],
    repo: str,
    notes_path: Path,
) -> StepExecution:
    started = perf_counter()
    text = str(step.get("text") or "").strip()
    if not text:
        return StepExecution(
            action="memory_store",
            passed=False,
            elapsed_ms=0.0,
            checks=[],
            details={},
            error="missing text",
        )
    namespace = str(step.get("namespace") or "").strip() or None
    tags = [
        str(item).strip()
        for item in (step.get("tags") or [])
        if str(item).strip()
    ]
    count = _append_note(
        notes_path=notes_path,
        text=text,
        namespace=namespace,
        repo=repo,
        tags=tags,
    )
    elapsed_ms = (perf_counter() - started) * 1000.0
    return StepExecution(
        action="memory_store",
        passed=True,
        elapsed_ms=elapsed_ms,
        checks=[],
        details={
            "namespace": namespace,
            "rows_after": count,
            "notes_path": str(notes_path),
        },
    )


def _run_memory_wipe_step(*, step: dict[str, Any], notes_path: Path) -> StepExecution:
    started = perf_counter()
    namespace = str(step.get("namespace") or "").strip() or None
    removed = _wipe_notes(notes_path=notes_path, namespace=namespace)
    elapsed_ms = (perf_counter() - started) * 1000.0
    return StepExecution(
        action="memory_wipe",
        passed=True,
        elapsed_ms=elapsed_ms,
        checks=[],
        details={
            "namespace": namespace,
            "removed": removed,
            "notes_path": str(notes_path),
        },
    )


def _run_profile_add_fact_step(*, step: dict[str, Any], profile_path: Path) -> StepExecution:
    started = perf_counter()
    text = str(step.get("text") or "").strip()
    if not text:
        return StepExecution(
            action="profile_add_fact",
            passed=False,
            elapsed_ms=0.0,
            checks=[],
            details={},
            error="missing text",
        )
    store = ProfileStore(path=profile_path)
    store.add_fact(
        text,
        confidence=_coerce_float(step.get("confidence"), default=0.7, minimum=0.0),
        source=str(step.get("source") or "scenario").strip() or "scenario",
        metadata=step.get("metadata") if isinstance(step.get("metadata"), dict) else {},
    )
    elapsed_ms = (perf_counter() - started) * 1000.0
    payload = store.load()
    return StepExecution(
        action="profile_add_fact",
        passed=True,
        elapsed_ms=elapsed_ms,
        checks=[],
        details={
            "facts_count": len(payload.get("facts", [])) if isinstance(payload, dict) else 0,
            "profile_path": str(profile_path),
        },
    )


def _run_profile_wipe_step(*, profile_path: Path) -> StepExecution:
    started = perf_counter()
    store = ProfileStore(path=profile_path)
    store.wipe()
    elapsed_ms = (perf_counter() - started) * 1000.0
    return StepExecution(
        action="profile_wipe",
        passed=True,
        elapsed_ms=elapsed_ms,
        checks=[],
        details={"profile_path": str(profile_path)},
    )


def _run_step(
    *,
    scenario_name: str,
    step: dict[str, Any],
    repo: str,
    root: Path,
    skills_dir: Path,
    notes_path: Path,
    profile_path: Path,
    index_cache_path: Path,
    default_top_k_files: int,
    default_chunk_top_k: int,
) -> StepExecution:
    action = str(step.get("action") or "").strip().lower()
    if action == "plan":
        return _run_plan_step(
            scenario_name=scenario_name,
            step=step,
            repo=repo,
            root=root,
            skills_dir=skills_dir,
            notes_path=notes_path,
            profile_path=profile_path,
            index_cache_path=index_cache_path,
            default_top_k_files=default_top_k_files,
            default_chunk_top_k=default_chunk_top_k,
        )
    if action == "memory_store":
        return _run_memory_store_step(step=step, repo=repo, notes_path=notes_path)
    if action == "memory_wipe":
        return _run_memory_wipe_step(step=step, notes_path=notes_path)
    if action == "profile_add_fact":
        return _run_profile_add_fact_step(step=step, profile_path=profile_path)
    if action == "profile_wipe":
        return _run_profile_wipe_step(profile_path=profile_path)
    return StepExecution(
        action=action or "(missing)",
        passed=False,
        elapsed_ms=0.0,
        checks=[],
        details={},
        error=f"unsupported_action:{action or 'missing'}",
    )


def _render_markdown(*, summary: dict[str, Any], scenarios: list[dict[str, Any]]) -> str:
    lines: list[str] = [
        "# ACE-Lite Scenario Validation",
        "",
        f"- Generated: {summary.get('generated_at', '')}",
        f"- Passed: {bool(summary.get('passed', False))}",
        f"- Scenario count: {int(summary.get('scenario_count', 0) or 0)}",
        f"- Passed count: {int(summary.get('passed_count', 0) or 0)}",
        f"- Failed count: {int(summary.get('failed_count', 0) or 0)}",
        "- Pass rate: {value:.4f}".format(value=float(summary.get("pass_rate", 0.0) or 0.0)),
        "- Min pass rate: {value:.4f}".format(value=float(summary.get("min_pass_rate", 0.0) or 0.0)),
        "",
        "## Scenarios",
        "",
        "| Scenario | Passed | Steps | Elapsed (ms) |",
        "| --- | :---: | ---: | ---: |",
    ]
    for item in scenarios:
        if not isinstance(item, dict):
            continue
        lines.append(
            "| {name} | {passed} | {steps} | {elapsed:.2f} |".format(
                name=str(item.get("name") or "(unknown)"),
                passed="PASS" if bool(item.get("passed", False)) else "FAIL",
                steps=len(item.get("steps", [])) if isinstance(item.get("steps"), list) else 0,
                elapsed=float(item.get("elapsed_ms", 0.0) or 0.0),
            )
        )
    lines.append("")
    failed = [item for item in scenarios if isinstance(item, dict) and not bool(item.get("passed", False))]
    if failed:
        lines.append("## Failed Scenarios")
        lines.append("")
        for item in failed:
            lines.append(f"### {item.get('name') or '(unknown)'!s}")
            for step in item.get("steps", []):
                if not isinstance(step, dict):
                    continue
                if bool(step.get("passed", False)):
                    continue
                lines.append(
                    "- action={action}, error={error}".format(
                        action=str(step.get("action") or "(unknown)"),
                        error=str(step.get("error") or "check_failed"),
                    )
                )
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run deterministic scenario validation for ACE-Lite."
    )
    parser.add_argument(
        "--scenarios",
        default="benchmark/cases/scenarios/real_world.yaml",
        help="Scenario YAML file path.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/validation/scenarios/latest",
        help="Output directory for scenario artifacts.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Alias for --output-dir.",
    )
    parser.add_argument("--repo", default="ace-lite-engine", help="Repository id passed to plan.")
    parser.add_argument("--root", default=".", help="Repository root path passed to plan.")
    parser.add_argument("--skills-dir", default="skills", help="Skills directory path.")
    parser.add_argument(
        "--notes-path",
        default="context-map/memory_notes.jsonl",
        help="Notes JSONL path used by scenario memory actions.",
    )
    parser.add_argument(
        "--profile-path",
        default="context-map/profile.json",
        help="Profile JSON path used by scenario profile actions.",
    )
    parser.add_argument(
        "--index-cache-path",
        default="context-map/index.json",
        help="Index cache path used by plan actions.",
    )
    parser.add_argument("--top-k-files", type=int, default=6, help="Default top-k files.")
    parser.add_argument("--chunk-top-k", type=int, default=10, help="Default top-k chunks.")
    parser.add_argument(
        "--min-pass-rate",
        type=float,
        default=1.0,
        help="Scenario pass-rate floor (0-1).",
    )
    parser.add_argument(
        "--fail-on-thresholds",
        action="store_true",
        help="Exit non-zero when pass-rate is below floor.",
    )
    args = parser.parse_args(sys.argv[1:])

    project_root = Path(__file__).resolve().parents[1]
    run_root = _resolve_path(root=project_root, value=str(args.root))
    scenarios_path = _resolve_path(root=project_root, value=str(args.scenarios))
    skills_dir = _resolve_path(root=project_root, value=str(args.skills_dir))
    notes_path = _resolve_path(root=run_root, value=str(args.notes_path))
    profile_path = _resolve_path(root=run_root, value=str(args.profile_path))
    index_cache_path = _resolve_path(root=run_root, value=str(args.index_cache_path))

    output_value = str(args.output).strip() or str(args.output_dir)
    output_dir = _resolve_path(root=project_root, value=output_value)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not scenarios_path.exists() or not scenarios_path.is_file():
        raise FileNotFoundError(f"scenario file not found: {scenarios_path}")
    if not run_root.exists() or not run_root.is_dir():
        raise FileNotFoundError(f"run root not found: {run_root}")
    if not skills_dir.exists() or not skills_dir.is_dir():
        raise FileNotFoundError(f"skills dir not found: {skills_dir}")

    scenarios_raw = _load_scenarios(path=scenarios_path)
    if not scenarios_raw:
        raise ValueError(f"no scenarios found in: {scenarios_path}")

    scenario_payloads: list[dict[str, Any]] = []

    for index, scenario in enumerate(scenarios_raw, start=1):
        name = str(scenario.get("name") or f"scenario-{index}").strip() or f"scenario-{index}"
        steps_raw = scenario.get("steps")
        steps = steps_raw if isinstance(steps_raw, list) else []
        started = perf_counter()
        step_results: list[StepExecution] = []

        for raw_step in steps:
            step = raw_step if isinstance(raw_step, dict) else {}
            result = _run_step(
                scenario_name=name,
                step=step,
                repo=str(scenario.get("repo") or args.repo),
                root=run_root,
                skills_dir=skills_dir,
                notes_path=notes_path,
                profile_path=profile_path,
                index_cache_path=index_cache_path,
                default_top_k_files=max(1, int(args.top_k_files)),
                default_chunk_top_k=max(1, int(args.chunk_top_k)),
            )
            step_results.append(result)

        elapsed_ms = (perf_counter() - started) * 1000.0
        passed = all(result.passed for result in step_results) and bool(step_results)
        scenario_payloads.append(
            {
                "name": name,
                "description": str(scenario.get("description") or "").strip(),
                "passed": passed,
                "elapsed_ms": elapsed_ms,
                "steps": [
                    {
                        "action": item.action,
                        "passed": item.passed,
                        "elapsed_ms": item.elapsed_ms,
                        "checks": item.checks,
                        "details": item.details,
                        "error": item.error,
                    }
                    for item in step_results
                ],
            }
        )

    scenario_count = len(scenario_payloads)
    passed_count = sum(1 for item in scenario_payloads if bool(item.get("passed", False)))
    failed_count = max(0, scenario_count - passed_count)
    pass_rate = float(passed_count) / float(scenario_count) if scenario_count > 0 else 0.0
    min_pass_rate = max(0.0, min(1.0, float(args.min_pass_rate)))
    threshold_passed = pass_rate >= min_pass_rate

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo": str(args.repo),
        "root": str(run_root),
        "scenarios_path": str(scenarios_path),
        "scenario_count": scenario_count,
        "passed_count": passed_count,
        "failed_count": failed_count,
        "pass_rate": pass_rate,
        "min_pass_rate": min_pass_rate,
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
                "scenarios_path": str(scenarios_path),
                "scenarios": scenario_payloads,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report_path.write_text(
        _render_markdown(summary=summary, scenarios=scenario_payloads),
        encoding="utf-8",
    )

    print(f"[scenario] summary: {summary_path}")
    print(f"[scenario] results: {results_path}")
    print(f"[scenario] report:  {report_path}")
    print(
        f"[scenario] scenarios={scenario_count} passed={passed_count} failed={failed_count} pass_rate={pass_rate:.4f}"
    )

    if args.fail_on_thresholds and not threshold_passed:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
