from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from ace_lite.workspace.common import ensure_non_empty_str as _ensure_non_empty_str
from ace_lite.workspace.manifest import WorkspaceManifest, load_workspace_manifest
from ace_lite.workspace.planner import build_workspace_plan, route_workspace_repos


def _normalize_expected_repos(*, value: Any, context: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{context} must be a non-empty list of repo names")

    normalized: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise ValueError(f"{context}[{index}] must be a string")
        name = item.strip()
        if not name:
            raise ValueError(f"{context}[{index}] cannot be empty")
        if name in seen:
            continue
        seen.add(name)
        normalized.append(name)

    if not normalized:
        raise ValueError(f"{context} resolved to an empty repo list")

    return tuple(sorted(normalized))


def _normalize_case(*, payload: Any, index: int) -> "WorkspaceBenchmarkCase":
    context = f"cases[{index}]"
    if not isinstance(payload, dict):
        raise ValueError(f"{context} must be a mapping")

    if "id" in payload:
        case_id = _ensure_non_empty_str(value=payload.get("id"), context=f"{context}.id")
    else:
        case_id = _ensure_non_empty_str(value=payload.get("case_id"), context=f"{context}.case_id")
    query = _ensure_non_empty_str(value=payload.get("query"), context=f"{context}.query")
    expected_repos = _normalize_expected_repos(
        value=payload.get("expected_repos"),
        context=f"{context}.expected_repos",
    )
    return WorkspaceBenchmarkCase(id=case_id, query=query, expected_repos=expected_repos)


def _coerce_confidence(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return max(0.0, min(1.0, float(value)))
    return 0.0


def _ensure_manifest(manifest: WorkspaceManifest | str | Path) -> WorkspaceManifest:
    if isinstance(manifest, WorkspaceManifest):
        return manifest
    return load_workspace_manifest(manifest)


def _coerce_metric_value(*, value: Any, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{context} must be a number")
    return float(value)


def _default_threshold_bound(metric: str) -> str:
    normalized = str(metric).strip().lower()
    if "latency" in normalized or normalized.endswith("_ms"):
        return "max"
    return "min"


def _coerce_metric_or_zero(*, metrics: dict[str, Any], metric: str) -> float:
    value = metrics.get(metric, 0.0)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return float(value)


def _coerce_metric_or_none(*, metrics: dict[str, Any], metric: str) -> float | None:
    if metric not in metrics:
        return None
    value = metrics.get(metric)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _reciprocal_rank(*, ranked_repos: tuple[str, ...], expected_repos: tuple[str, ...]) -> float:
    expected = set(expected_repos)
    for position, name in enumerate(ranked_repos, start=1):
        if name in expected:
            return 1.0 / float(position)
    return 0.0


def _candidate_value(candidate: Any, field: str, default: Any = None) -> Any:
    if isinstance(candidate, dict):
        return candidate.get(field, default)
    return getattr(candidate, field, default)


def _candidate_name(candidate: Any) -> str:
    return str(_candidate_value(candidate, "name", "") or "").strip()


def _candidate_matched_summary_terms(candidate: Any) -> tuple[str, ...]:
    value = _candidate_value(candidate, "matched_summary_terms", ())
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(
        str(item).strip()
        for item in value
        if isinstance(item, str) and str(item).strip()
    )


@dataclass(frozen=True, slots=True)
class WorkspaceBenchmarkCase:
    id: str
    query: str
    expected_repos: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "query": self.query,
            "expected_repos": list(self.expected_repos),
        }


def load_workspace_benchmark_baseline(
    baseline_json: str | Path | dict[str, Any],
) -> dict[str, Any]:
    raw_payload: Any
    if isinstance(baseline_json, dict):
        raw_payload = baseline_json
    else:
        source = Path(baseline_json).expanduser().resolve()
        if not source.exists() or not source.is_file():
            raise ValueError(f"benchmark baseline JSON not found: {source}")
        try:
            raw_payload = json.loads(source.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ValueError(f"failed to read benchmark baseline JSON: {source}") from exc
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid benchmark baseline JSON: {source}") from exc

    if not isinstance(raw_payload, dict):
        raise ValueError("benchmark baseline must be a JSON object")

    metrics_candidate: Any
    if "metrics" in raw_payload:
        metrics_candidate = raw_payload.get("metrics")
    else:
        metrics_candidate = {
            key: value
            for key, value in raw_payload.items()
            if key not in {"checks", "thresholds"}
        }
    if not isinstance(metrics_candidate, dict):
        raise ValueError("benchmark baseline field 'metrics' must be an object")

    normalized_metrics: dict[str, float] = {}
    for metric, value in metrics_candidate.items():
        metric_name = str(metric).strip()
        if not metric_name:
            raise ValueError("benchmark baseline metrics contains an empty metric name")
        normalized_metrics[metric_name] = _coerce_metric_value(
            value=value,
            context=f"benchmark baseline metrics.{metric_name}",
        )

    checks_candidate = raw_payload.get("checks", raw_payload.get("thresholds"))
    normalized_checks: dict[str, dict[str, float]] = {}

    if checks_candidate is None:
        for metric, value in normalized_metrics.items():
            normalized_checks[metric] = {_default_threshold_bound(metric): value}
    else:
        if not isinstance(checks_candidate, dict):
            raise ValueError("benchmark baseline field 'checks' must be an object")

        for metric, rule_payload in checks_candidate.items():
            metric_name = str(metric).strip()
            if not metric_name:
                raise ValueError("benchmark baseline checks contains an empty metric name")

            if isinstance(rule_payload, dict):
                min_value: float | None = None
                max_value: float | None = None
                if "min" in rule_payload and rule_payload.get("min") is not None:
                    min_value = _coerce_metric_value(
                        value=rule_payload.get("min"),
                        context=f"benchmark baseline checks.{metric_name}.min",
                    )
                if "max" in rule_payload and rule_payload.get("max") is not None:
                    max_value = _coerce_metric_value(
                        value=rule_payload.get("max"),
                        context=f"benchmark baseline checks.{metric_name}.max",
                    )
                if min_value is None and max_value is None:
                    raise ValueError(
                        f"benchmark baseline checks.{metric_name} must define min and/or max"
                    )
                normalized_checks[metric_name] = {}
                if min_value is not None:
                    normalized_checks[metric_name]["min"] = min_value
                if max_value is not None:
                    normalized_checks[metric_name]["max"] = max_value
                continue

            scalar_threshold = _coerce_metric_value(
                value=rule_payload,
                context=f"benchmark baseline checks.{metric_name}",
            )
            normalized_checks[metric_name] = {
                _default_threshold_bound(metric_name): scalar_threshold
            }

    if not normalized_checks:
        raise ValueError("benchmark baseline checks resolved to empty thresholds")

    return {"metrics": normalized_metrics, "checks": normalized_checks}


def compare_workspace_benchmark_metrics(
    *,
    current: dict[str, Any],
    baseline: dict[str, float],
) -> dict[str, float]:
    return {
        metric: (
            _coerce_metric_or_zero(metrics=current, metric=metric)
            - _coerce_metric_or_zero(metrics=baseline, metric=metric)
        )
        for metric in baseline
    }


def evaluate_workspace_benchmark_against_baseline(
    *,
    current_metrics: dict[str, Any],
    baseline_metrics: dict[str, float],
    checks: dict[str, dict[str, float]],
) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    for metric in checks:
        rule = checks.get(metric, {})
        current_value = _coerce_metric_or_none(metrics=current_metrics, metric=metric)
        if current_value is None:
            violations.append(
                {
                    "metric": metric,
                    "operator": "present_numeric",
                    "current": None,
                    "threshold": "required",
                }
            )
            continue
        if "min" in rule and current_value < float(rule["min"]):
            violations.append(
                {
                    "metric": metric,
                    "operator": ">=",
                    "current": current_value,
                    "threshold": float(rule["min"]),
                }
            )
        if "max" in rule and current_value > float(rule["max"]):
            violations.append(
                {
                    "metric": metric,
                    "operator": "<=",
                    "current": current_value,
                    "threshold": float(rule["max"]),
                }
            )

    return {
        "ok": not violations,
        "checked_metrics": sorted(checks),
        "violations": violations,
        "thresholds": checks,
        "baseline_metrics": baseline_metrics,
        "delta": compare_workspace_benchmark_metrics(
            current=current_metrics, baseline=baseline_metrics
        ),
    }


def load_workspace_benchmark_cases(
    cases_json: str | Path | list[dict[str, Any]] | dict[str, Any],
) -> list[WorkspaceBenchmarkCase]:
    raw_payload: Any
    if isinstance(cases_json, (list, dict)):
        raw_payload = cases_json
    else:
        source = Path(cases_json).expanduser().resolve()
        if not source.exists() or not source.is_file():
            raise ValueError(f"benchmark cases JSON not found: {source}")
        try:
            raw_payload = json.loads(source.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ValueError(f"failed to read benchmark cases JSON: {source}") from exc
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid benchmark cases JSON: {source}") from exc

    raw_cases: Any = raw_payload
    if isinstance(raw_payload, dict):
        if "cases" not in raw_payload:
            raise ValueError("benchmark cases JSON object must contain a 'cases' field")
        raw_cases = raw_payload.get("cases")
        if not isinstance(raw_cases, list) or not raw_cases:
            raise ValueError("benchmark cases JSON field 'cases' must be a non-empty list")
    elif not isinstance(raw_payload, list) or not raw_payload:
        raise ValueError("benchmark cases must be a non-empty JSON list or {'cases': [...]} object")

    cases = [_normalize_case(payload=item, index=index) for index, item in enumerate(raw_cases)]

    seen_ids: set[str] = set()
    for case in cases:
        if case.id in seen_ids:
            raise ValueError(f"duplicate benchmark case id: {case.id}")
        seen_ids.add(case.id)

    return cases


def run_workspace_benchmark(
    *,
    manifest: WorkspaceManifest | str | Path,
    cases_json: str | Path | list[dict[str, Any]] | dict[str, Any],
    top_k_repos: int = 3,
    repo_scope: list[str] | tuple[str, ...] | None = None,
    summary_score_enabled: bool = False,
    full_plan: bool = False,
    baseline_json: str | Path | dict[str, Any] | None = None,
    fail_on_baseline: bool = False,
) -> dict[str, Any]:
    if top_k_repos <= 0:
        raise ValueError("top_k_repos must be > 0")
    if fail_on_baseline and baseline_json is None:
        raise ValueError("fail_on_baseline requires baseline_json")

    manifest_payload = _ensure_manifest(manifest)
    cases = load_workspace_benchmark_cases(cases_json)

    hit_count = 0
    reciprocal_rank_sum = 0.0
    latency_sum_ms = 0.0
    evidence_completeness_sum = 0.0
    summary_match_case_count = 0
    summary_promoted_case_count = 0
    case_rows: list[dict[str, Any]] = []

    for case in cases:
        started = perf_counter()
        routed = route_workspace_repos(
            query=case.query,
            manifest=manifest_payload,
            top_k=int(top_k_repos),
            repo_scope=repo_scope,
            summary_score_enabled=bool(summary_score_enabled),
        )
        latency_ms = (perf_counter() - started) * 1000.0
        ranked_repos = tuple(_candidate_name(candidate) for candidate in routed if _candidate_name(candidate))

        hit = bool(set(case.expected_repos) & set(ranked_repos))
        reciprocal_rank = _reciprocal_rank(
            ranked_repos=ranked_repos,
            expected_repos=case.expected_repos,
        )

        hit_count += int(hit)
        reciprocal_rank_sum += reciprocal_rank
        latency_sum_ms += latency_ms

        row: dict[str, Any] = {
            "id": case.id,
            "query": case.query,
            "expected_repos": list(case.expected_repos),
            "predicted_repos": list(ranked_repos),
            "hit": bool(hit),
            "reciprocal_rank": round(float(reciprocal_rank), 6),
            "latency_ms": round(float(latency_ms), 3),
        }

        if summary_score_enabled:
            baseline_routed = route_workspace_repos(
                query=case.query,
                manifest=manifest_payload,
                top_k=int(top_k_repos),
                repo_scope=repo_scope,
                summary_score_enabled=False,
            )
            baseline_ranked_repos = tuple(
                _candidate_name(candidate)
                for candidate in baseline_routed
                if _candidate_name(candidate)
            )
            matched_summary_repos = [
                _candidate_name(candidate)
                for candidate in routed
                if _candidate_matched_summary_terms(candidate)
            ]
            expected_before = _reciprocal_rank(
                ranked_repos=baseline_ranked_repos,
                expected_repos=case.expected_repos,
            )
            expected_after = reciprocal_rank
            summary_promoted = bool(expected_after > expected_before)
            summary_matched = bool(matched_summary_repos)
            if summary_matched:
                summary_match_case_count += 1
            if summary_promoted:
                summary_promoted_case_count += 1
            row["summary_routing"] = {
                "matched_repos": matched_summary_repos,
                "matched": summary_matched,
                "baseline_predicted_repos": list(baseline_ranked_repos),
                "expected_reciprocal_rank_before": round(float(expected_before), 6),
                "expected_reciprocal_rank_after": round(float(expected_after), 6),
                "promoted_expected_repo": summary_promoted,
            }

        if full_plan:
            plan_payload = build_workspace_plan(
                query=case.query,
                manifest=manifest_payload,
                top_k_repos=int(top_k_repos),
                repo_scope=repo_scope,
                summary_score_enabled=bool(summary_score_enabled),
            )
            evidence_raw = plan_payload.get("evidence_contract")
            evidence = evidence_raw if isinstance(evidence_raw, dict) else {}
            completeness = _coerce_confidence(evidence.get("confidence"))
            evidence_completeness_sum += completeness
            row["evidence_completeness"] = round(completeness, 6)

        case_rows.append(row)

    cases_total = len(cases)
    metrics: dict[str, Any] = {
        "cases_total": int(cases_total),
        "hit_at_k": round(float(hit_count) / float(cases_total), 6),
        "mrr": round(float(reciprocal_rank_sum) / float(cases_total), 6),
        "avg_latency_ms": round(float(latency_sum_ms) / float(cases_total), 3),
    }

    if full_plan:
        metrics["evidence_completeness"] = round(
            float(evidence_completeness_sum) / float(cases_total),
            6,
        )
    if summary_score_enabled:
        metrics["summary_match_case_rate"] = round(
            float(summary_match_case_count) / float(cases_total),
            6,
        )
        metrics["summary_promoted_case_rate"] = round(
            float(summary_promoted_case_count) / float(cases_total),
            6,
        )

    normalized_scope = [str(name).strip() for name in (repo_scope or ()) if str(name).strip()]

    payload = {
        "workspace": {
            "name": manifest_payload.workspace_name,
            "manifest_path": manifest_payload.manifest_path,
            "repo_count": len(manifest_payload.repos),
        },
        "top_k_repos": int(top_k_repos),
        "repo_scope": normalized_scope,
        "summary_score_enabled": bool(summary_score_enabled),
        "full_plan": bool(full_plan),
        "metrics": metrics,
        "cases": case_rows,
    }

    if baseline_json is not None:
        baseline = load_workspace_benchmark_baseline(baseline_json)
        baseline_check = evaluate_workspace_benchmark_against_baseline(
            current_metrics=metrics,
            baseline_metrics=baseline["metrics"],
            checks=baseline["checks"],
        )
        payload["baseline_check"] = baseline_check
        if fail_on_baseline and not bool(baseline_check.get("ok")):
            violations = baseline_check.get("violations")
            count = len(violations) if isinstance(violations, list) else 0
            raise ValueError(f"workspace benchmark baseline check failed ({count} violation(s))")

    return payload


__all__ = [
    "WorkspaceBenchmarkCase",
    "compare_workspace_benchmark_metrics",
    "evaluate_workspace_benchmark_against_baseline",
    "load_workspace_benchmark_baseline",
    "load_workspace_benchmark_cases",
    "run_workspace_benchmark",
]
