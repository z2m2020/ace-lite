from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

import yaml

from ace_lite.feedback_store import SelectionFeedbackStore


@dataclass
class CommandResult:
    cmd: list[str]
    cwd: str | None
    returncode: int
    stdout: str
    stderr: str


def _run_command(
    *,
    cmd: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> CommandResult:
    completed = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    return CommandResult(
        cmd=cmd,
        cwd=str(cwd) if cwd else None,
        returncode=int(completed.returncode),
        stdout=str(completed.stdout or ""),
        stderr=str(completed.stderr or ""),
    )


def _require_success(result: CommandResult, *, label: str) -> None:
    if result.returncode == 0:
        return
    details = [
        f"{label} failed with exit code {result.returncode}",
        f"cmd: {' '.join(result.cmd)}",
    ]
    if result.cwd:
        details.append(f"cwd: {result.cwd}")
    if result.stdout.strip():
        details.append(f"stdout:\n{result.stdout.strip()}")
    if result.stderr.strip():
        details.append(f"stderr:\n{result.stderr.strip()}")
    raise RuntimeError("\n".join(details))


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _extract_thresholds(config: dict[str, Any], *, slice_name: str) -> dict[str, float]:
    slices = config.get("slices") if isinstance(config.get("slices"), dict) else {}
    entry = slices.get(slice_name) if isinstance(slices.get(slice_name), dict) else {}
    raw = entry.get("thresholds") if isinstance(entry.get("thresholds"), dict) else {}
    thresholds: dict[str, float] = {}
    for key, value in raw.items():
        name = str(key).strip()
        if not name:
            continue
        try:
            thresholds[name] = float(value)
        except Exception:
            continue
    return thresholds


def _coerce_bool(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _extract_slice_config(config: dict[str, Any], *, slice_name: str, key: str) -> dict[str, Any]:
    slices = config.get("slices") if isinstance(config.get("slices"), dict) else {}
    entry = slices.get(slice_name) if isinstance(slices.get(slice_name), dict) else {}
    raw = entry.get(key) if isinstance(entry.get(key), dict) else {}
    return raw


def _read_benchmark_metrics(results_path: Path) -> dict[str, float]:
    if not results_path.exists() or not results_path.is_file():
        return {}
    try:
        payload = json.loads(results_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    metrics_raw = payload.get("metrics")
    metrics = metrics_raw if isinstance(metrics_raw, dict) else {}
    task_success_rate = float(
        metrics.get("task_success_rate", metrics.get("utility_rate", 0.0)) or 0.0
    )
    return {
        key: (
            task_success_rate
            if key == "task_success_rate"
            else float(value or 0.0)
        )
        for key, value in metrics.items()
        if isinstance(key, str)
    } | {"task_success_rate": task_success_rate}


def _read_benchmark_results(results_path: Path) -> dict[str, Any]:
    if not results_path.exists() or not results_path.is_file():
        return {}
    try:
        payload = json.loads(results_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_benchmark_case_rows(results_path: Path) -> dict[str, dict[str, float]]:
    payload = _read_benchmark_results(results_path)
    cases_raw = payload.get("cases")
    cases = cases_raw if isinstance(cases_raw, list) else []
    rows: dict[str, dict[str, float]] = {}
    for item in cases:
        if not isinstance(item, dict):
            continue
        case_id = str(item.get("case_id") or "").strip()
        if not case_id:
            continue
        rows[case_id] = {
            "task_success_hit": float(
                item.get("task_success_hit", item.get("utility_hit", 0.0)) or 0.0
            ),
            "precision_at_k": float(item.get("precision_at_k", 0.0) or 0.0),
            "noise_rate": float(item.get("noise_rate", 0.0) or 0.0),
            "recall_hit": float(item.get("recall_hit", 0.0) or 0.0),
            "dependency_recall": float(item.get("dependency_recall", 0.0) or 0.0),
        }
    return rows


def _is_volatile_case_key(key: str) -> bool:
    normalized = str(key or "").strip()
    if not normalized:
        return False
    return normalized == "latency_ms" or normalized.endswith("_latency_ms")


def _normalize_case_value(value: Any) -> Any:
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key in sorted(value):
            name = str(key or "")
            if _is_volatile_case_key(name):
                continue
            normalized[name] = _normalize_case_value(value[key])
        return normalized
    if isinstance(value, list):
        return [_normalize_case_value(item) for item in value]
    if isinstance(value, float):
        return round(float(value), 6)
    return value


def _read_benchmark_case_fingerprints(results_path: Path) -> dict[str, Any]:
    payload = _read_benchmark_results(results_path)
    cases_raw = payload.get("cases")
    cases = cases_raw if isinstance(cases_raw, list) else []
    fingerprints: dict[str, Any] = {}
    for item in cases:
        if not isinstance(item, dict):
            continue
        case_id = str(item.get("case_id") or "").strip()
        if not case_id:
            continue
        fingerprints[case_id] = _normalize_case_value(item)
    return fingerprints


def _read_benchmark_case_routing_source(results_path: Path) -> str:
    payload = _read_benchmark_results(results_path)
    cases_raw = payload.get("cases")
    cases = cases_raw if isinstance(cases_raw, list) else []
    sources: list[str] = []
    for item in cases:
        if not isinstance(item, dict):
            continue
        plan = item.get("plan")
        if not isinstance(plan, dict):
            continue
        skills = plan.get("skills")
        if not isinstance(skills, dict):
            continue
        source = str(skills.get("routing_source") or "").strip()
        if source and source not in sources:
            sources.append(source)
    if len(sources) == 1:
        return sources[0]
    if not sources:
        return ""
    return ",".join(sources)


def _read_benchmark_comparison_lane_metrics(
    results_path: Path,
    *,
    lane: str,
) -> dict[str, float]:
    payload = _read_benchmark_results(results_path)
    summary_raw = payload.get("comparison_lane_summary")
    summary = summary_raw if isinstance(summary_raw, dict) else {}
    lanes_raw = summary.get("lanes")
    lanes = lanes_raw if isinstance(lanes_raw, list) else []
    for item in lanes:
        if not isinstance(item, dict):
            continue
        if str(item.get("comparison_lane") or "").strip() != lane:
            continue
        metrics: dict[str, float] = {}
        for key, value in item.items():
            if not isinstance(key, str) or key == "comparison_lane":
                continue
            try:
                metrics[key] = float(value or 0.0)
            except Exception:
                continue
        return metrics
    return {}


def _evaluate_delta_thresholds(
    *,
    off_metrics: dict[str, float],
    on_metrics: dict[str, float],
    thresholds: dict[str, float],
    name: str,
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    precision_off = float(off_metrics.get("precision_at_k", 0.0) or 0.0)
    precision_on = float(on_metrics.get("precision_at_k", 0.0) or 0.0)
    noise_off = float(off_metrics.get("noise_rate", 0.0) or 0.0)
    noise_on = float(on_metrics.get("noise_rate", 0.0) or 0.0)

    deltas = {
        "precision_delta": precision_on - precision_off,
        "noise_delta": noise_off - noise_on,
    }
    failures: list[dict[str, Any]] = []

    precision_delta_min = float(thresholds.get("precision_delta_min", 0.0) or 0.0)
    if deltas["precision_delta"] < precision_delta_min:
        failures.append(
            {
                "slice": name,
                "metric": "precision_delta",
                "actual": deltas["precision_delta"],
                "operator": ">=",
                "expected": precision_delta_min,
            }
        )

    noise_delta_min = float(thresholds.get("noise_delta_min", 0.0) or 0.0)
    if deltas["noise_delta"] < noise_delta_min:
        failures.append(
            {
                "slice": name,
                "metric": "noise_delta",
                "actual": deltas["noise_delta"],
                "operator": ">=",
                "expected": noise_delta_min,
            }
        )

    return failures, deltas


def _evaluate_perturbation_pair(
    *,
    perturbation: str,
    baseline_case: dict[str, float] | None,
    perturbed_case: dict[str, float] | None,
    thresholds: dict[str, float],
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    failures: list[dict[str, Any]] = []
    if baseline_case is None or perturbed_case is None:
        failures.append(
            {
                "slice": "perturbation",
                "perturbation": perturbation,
                "metric": "case_pair_present",
                "actual": False,
                "operator": "==",
                "expected": True,
            }
        )
        return failures, {
            "task_success_delta": 0.0,
            "precision_delta": 0.0,
            "noise_increase": 0.0,
        }

    task_success_delta = float(perturbed_case.get("task_success_hit", 0.0)) - float(
        baseline_case.get("task_success_hit", 0.0)
    )
    precision_delta = float(perturbed_case.get("precision_at_k", 0.0)) - float(
        baseline_case.get("precision_at_k", 0.0)
    )
    noise_increase = float(perturbed_case.get("noise_rate", 0.0)) - float(
        baseline_case.get("noise_rate", 0.0)
    )
    dependency_recall_delta = float(
        perturbed_case.get("dependency_recall", 0.0)
    ) - float(baseline_case.get("dependency_recall", 0.0))

    task_success_min = float(thresholds.get("task_success_min", 1.0) or 1.0)
    if float(perturbed_case.get("task_success_hit", 0.0)) < task_success_min:
        failures.append(
            {
                "slice": "perturbation",
                "perturbation": perturbation,
                "metric": "task_success_hit",
                "actual": float(perturbed_case.get("task_success_hit", 0.0)),
                "operator": ">=",
                "expected": task_success_min,
            }
        )

    task_success_delta_min = float(
        thresholds.get("task_success_delta_min", 0.0) or 0.0
    )
    if task_success_delta < task_success_delta_min:
        failures.append(
            {
                "slice": "perturbation",
                "perturbation": perturbation,
                "metric": "task_success_delta",
                "actual": task_success_delta,
                "operator": ">=",
                "expected": task_success_delta_min,
            }
        )

    precision_delta_min = float(thresholds.get("precision_delta_min", 0.0) or 0.0)
    if precision_delta < precision_delta_min:
        failures.append(
            {
                "slice": "perturbation",
                "perturbation": perturbation,
                "metric": "precision_delta",
                "actual": precision_delta,
                "operator": ">=",
                "expected": precision_delta_min,
            }
        )

    noise_increase_max = float(thresholds.get("noise_increase_max", 0.0) or 0.0)
    if noise_increase > noise_increase_max:
        failures.append(
            {
                "slice": "perturbation",
                "perturbation": perturbation,
                "metric": "noise_increase",
                "actual": noise_increase,
                "operator": "<=",
                "expected": noise_increase_max,
            }
        )

    deltas = {
        "task_success_delta": task_success_delta,
        "precision_delta": precision_delta,
        "noise_increase": noise_increase,
    }
    has_dependency_thresholds = any(
        key in thresholds
        for key in ("dependency_recall_min", "dependency_recall_delta_min")
    )
    if (
        has_dependency_thresholds
        or "dependency_recall" in baseline_case
        or "dependency_recall" in perturbed_case
    ):
        deltas["dependency_recall_delta"] = dependency_recall_delta

        dependency_recall_min = float(
            thresholds.get("dependency_recall_min", 0.0) or 0.0
        )
        if float(perturbed_case.get("dependency_recall", 0.0)) < dependency_recall_min:
            failures.append(
                {
                    "slice": "perturbation",
                    "perturbation": perturbation,
                    "metric": "dependency_recall",
                    "actual": float(perturbed_case.get("dependency_recall", 0.0)),
                    "operator": ">=",
                    "expected": dependency_recall_min,
                }
            )

        dependency_recall_delta_min = float(
            thresholds.get("dependency_recall_delta_min", 0.0) or 0.0
        )
        if dependency_recall_delta < dependency_recall_delta_min:
            failures.append(
                {
                    "slice": "perturbation",
                    "perturbation": perturbation,
                    "metric": "dependency_recall_delta",
                    "actual": dependency_recall_delta,
                    "operator": ">=",
                    "expected": dependency_recall_delta_min,
                }
            )

    return failures, deltas


def _write_cases(path: Path, *, cases: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump({"cases": cases}, sort_keys=False),
        encoding="utf-8",
    )
    return path


def _seed_feedback_repo(root: Path) -> Path:
    (root / "src" / "app").mkdir(parents=True, exist_ok=True)
    (root / "benchmark" / "cases").mkdir(parents=True, exist_ok=True)

    (root / "src" / "app" / "alpha.py").write_text(
        "def validate_token(raw: str) -> bool:\n    return bool(raw)\n",
        encoding="utf-8",
    )
    (root / "src" / "app" / "beta.py").write_text(
        "def validate_token(raw: str) -> bool:\n    return bool(raw)\n",
        encoding="utf-8",
    )

    cases_path = root / "benchmark" / "cases" / "feedback_slice.yaml"
    cases_path.write_text(
        "cases:\n  - case_id: feedback-01\n    query: validate token\n    expected_keys: [beta]\n    top_k: 1\n",
        encoding="utf-8",
    )
    return cases_path


def _run_feedback_slice(
    *,
    cli_bin: str,
    project_root: Path,
    output_dir: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    workdir = output_dir / "workdir" / "feedback"
    cases_path = _seed_feedback_repo(workdir)
    thresholds = _extract_thresholds(config, slice_name="feedback")
    feedback_cfg = _extract_slice_config(config, slice_name="feedback", key="feedback")

    env = {"HOME": str(workdir), "USERPROFILE": str(workdir)}
    off_dir = output_dir / "feedback-off"
    on_dir = output_dir / "feedback-on"
    off_dir.mkdir(parents=True, exist_ok=True)
    on_dir.mkdir(parents=True, exist_ok=True)

    common = [
        cli_bin,
        "benchmark",
        "run",
        "--cases",
        str(cases_path),
        "--repo",
        "demo",
        "--root",
        str(workdir),
        "--skills-dir",
        str((project_root / "skills").resolve()),
        "--languages",
        "python",
        "--candidate-ranker",
        "heuristic",
        "--min-candidate-score",
        "0",
        "--top-k-files",
        "1",
        "--memory-primary",
        "none",
        "--memory-secondary",
        "none",
        "--no-repomap",
        "--no-plugins",
        "--no-lsp",
        "--no-lsp-xref",
        "--no-cochange",
        "--no-scip",
        "--no-trace-export",
        "--no-trace-otlp",
        "--no-include-plans",
        "--no-include-case-details",
    ]

    _require_success(
        _run_command(cmd=[*common, "--output", str(off_dir)], env=env),
        label="feedback slice off",
    )
    off_metrics = _read_benchmark_metrics(off_dir / "results.json")

    profile_path = workdir / "profile.json"
    SelectionFeedbackStore(profile_path=profile_path, max_entries=32).record(
        query="validate token",
        repo="demo",
        selected_path="src/app/beta.py",
        position=1,
        captured_at="2026-02-14T00:00:00+00:00",
    )

    boost_per_select = float(feedback_cfg.get("boost_per_select", 0.8) or 0.8)
    max_boost = float(feedback_cfg.get("max_boost", 0.8) or 0.8)
    decay_days = float(feedback_cfg.get("decay_days", 60.0) or 60.0)
    (workdir / ".ace-lite.yml").write_text(
        f"""
benchmark:
  memory:
    feedback:
      enabled: true
      path: {profile_path.as_posix()}
      boost_per_select: {boost_per_select}
      max_boost: {max_boost}
      decay_days: {decay_days}
""".lstrip(),
        encoding="utf-8",
    )

    _require_success(
        _run_command(cmd=[*common, "--output", str(on_dir)], env=env),
        label="feedback slice on",
    )
    on_metrics = _read_benchmark_metrics(on_dir / "results.json")

    failures, deltas = _evaluate_delta_thresholds(
        off_metrics=off_metrics,
        on_metrics=on_metrics,
        thresholds=thresholds,
        name="feedback",
    )
    return {
        "name": "feedback",
        "passed": len(failures) == 0,
        "thresholds": thresholds,
        "off": {"output_dir": str(off_dir), "metrics": off_metrics},
        "on": {"output_dir": str(on_dir), "metrics": on_metrics},
        "deltas": deltas,
        "failures": failures,
    }


def _seed_temporal_repo(root: Path) -> Path:
    (root / "src" / "app").mkdir(parents=True, exist_ok=True)
    (root / "benchmark" / "cases").mkdir(parents=True, exist_ok=True)
    (root / "context-map").mkdir(parents=True, exist_ok=True)

    (root / "src" / "app" / "legacy_validator.py").write_text(
        "def validate_token(raw: str) -> bool:\n    return bool(raw)\n",
        encoding="utf-8",
    )
    (root / "src" / "app" / "modern_validator.py").write_text(
        "def validate_token(raw: str) -> bool:\n    return bool(raw)\n",
        encoding="utf-8",
    )

    notes_path = root / "context-map" / "memory_notes.jsonl"
    notes_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "text": "validate token legacy_validator",
                        "repo": "demo",
                        "captured_at": "2026-01-01T00:00:00+00:00",
                        "created_at": "2026-01-01T00:00:00+00:00",
                        "source": "local_notes",
                    }
                ),
                json.dumps(
                    {
                        "text": "validate modern_validator token",
                        "repo": "demo",
                        "captured_at": "2026-02-14T00:00:00+00:00",
                        "created_at": "2026-02-14T00:00:00+00:00",
                        "source": "local_notes",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    (root / ".ace-lite.yml").write_text(
        f"""
benchmark:
  memory:
    notes:
      enabled: true
      path: {notes_path.as_posix()}
      mode: local_only
      expiry_enabled: false
""".lstrip(),
        encoding="utf-8",
    )

    cases_path = root / "benchmark" / "cases" / "temporal_slice.yaml"
    cases_path.write_text(
        "cases:\n  - case_id: temporal-01\n    query: validate token\n    expected_keys: [modern_validator]\n    top_k: 1\n",
        encoding="utf-8",
    )
    return cases_path


def _run_temporal_slice(
    *,
    cli_bin: str,
    project_root: Path,
    output_dir: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    workdir = output_dir / "workdir" / "temporal"
    cases_path = _seed_temporal_repo(workdir)
    thresholds = _extract_thresholds(config, slice_name="temporal")
    time_cfg = _extract_slice_config(config, slice_name="temporal", key="time")
    start_date = str(time_cfg.get("start_date", "2026-02-10") or "2026-02-10").strip()
    end_date = str(time_cfg.get("end_date", "2026-02-15") or "2026-02-15").strip()

    env = {"HOME": str(workdir), "USERPROFILE": str(workdir)}
    off_dir = output_dir / "temporal-off"
    on_dir = output_dir / "temporal-on"
    off_dir.mkdir(parents=True, exist_ok=True)
    on_dir.mkdir(parents=True, exist_ok=True)

    common = [
        cli_bin,
        "benchmark",
        "run",
        "--cases",
        str(cases_path),
        "--repo",
        "demo",
        "--root",
        str(workdir),
        "--skills-dir",
        str((project_root / "skills").resolve()),
        "--languages",
        "python",
        "--candidate-ranker",
        "heuristic",
        "--min-candidate-score",
        "0",
        "--top-k-files",
        "1",
        "--memory-primary",
        "rest",
        "--memory-secondary",
        "none",
        "--memory-timeout",
        "0.2",
        "--no-repomap",
        "--no-plugins",
        "--no-lsp",
        "--no-lsp-xref",
        "--no-cochange",
        "--no-scip",
        "--no-trace-export",
        "--no-trace-otlp",
        "--no-include-plans",
        "--no-include-case-details",
    ]

    _require_success(
        _run_command(cmd=[*common, "--output", str(off_dir)], env=env),
        label="temporal slice off",
    )
    off_metrics = _read_benchmark_metrics(off_dir / "results.json")

    _require_success(
        _run_command(
            cmd=[
                *common,
                "--start-date",
                start_date,
                "--end-date",
                end_date,
                "--output",
                str(on_dir),
            ],
            env=env,
        ),
        label="temporal slice on",
    )
    on_metrics = _read_benchmark_metrics(on_dir / "results.json")

    failures, deltas = _evaluate_delta_thresholds(
        off_metrics=off_metrics,
        on_metrics=on_metrics,
        thresholds=thresholds,
        name="temporal",
    )

    return {
        "name": "temporal",
        "passed": len(failures) == 0,
        "thresholds": thresholds,
        "off": {"output_dir": str(off_dir), "metrics": off_metrics},
        "on": {"output_dir": str(on_dir), "metrics": on_metrics},
        "deltas": deltas,
        "failures": failures,
    }


def _seed_late_interaction_repo(root: Path) -> Path:
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "benchmark" / "cases").mkdir(parents=True, exist_ok=True)

    (root / "src" / "late_interaction.py").write_text(
        (
            "def late_interaction_score(query: str, text: str) -> float:\n"
            "    \"\"\"ColBERT-style late interaction scoring stub.\"\"\"\n"
            "    return float(len(query) + len(text))\n"
        ),
        encoding="utf-8",
    )
    (root / "src" / "baseline.py").write_text(
        "def baseline_score(query: str, text: str) -> float:\n    return 0.0\n",
        encoding="utf-8",
    )

    cases_path = root / "benchmark" / "cases" / "late_interaction_slice.yaml"
    cases_path.write_text(
        "cases:\n  - case_id: late-interaction-01\n    query: late interaction colbert score\n    expected_keys: [late_interaction_score]\n    top_k: 1\n",
        encoding="utf-8",
    )
    return cases_path


def _run_late_interaction_slice(
    *,
    cli_bin: str,
    project_root: Path,
    output_dir: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    workdir = output_dir / "workdir" / "late_interaction"
    cases_path = _seed_late_interaction_repo(workdir)
    thresholds = _extract_thresholds(config, slice_name="late_interaction")
    late_cfg = _extract_slice_config(config, slice_name="late_interaction", key="late_interaction")
    off_provider = str(late_cfg.get("off_provider", "hash_cross") or "hash_cross").strip().lower()
    on_provider = str(late_cfg.get("on_provider", "hash_colbert") or "hash_colbert").strip().lower()

    env = {"HOME": str(workdir), "USERPROFILE": str(workdir)}
    off_dir = output_dir / "late-interaction-off"
    on_dir = output_dir / "late-interaction-on"
    off_dir.mkdir(parents=True, exist_ok=True)
    on_dir.mkdir(parents=True, exist_ok=True)

    common = [
        cli_bin,
        "benchmark",
        "run",
        "--cases",
        str(cases_path),
        "--repo",
        "demo",
        "--root",
        str(workdir),
        "--skills-dir",
        str((project_root / "skills").resolve()),
        "--languages",
        "python",
        "--candidate-ranker",
        "heuristic",
        "--min-candidate-score",
        "0",
        "--top-k-files",
        "1",
        "--retrieval-policy",
        "general",
        "--memory-primary",
        "none",
        "--memory-secondary",
        "none",
        "--embedding-enabled",
        "--embedding-dimension",
        "1",
        "--embedding-lexical-weight",
        "0.0",
        "--embedding-semantic-weight",
        "1.0",
        "--no-repomap",
        "--no-plugins",
        "--no-lsp",
        "--no-lsp-xref",
        "--no-cochange",
        "--no-scip",
        "--no-trace-export",
        "--no-trace-otlp",
        "--no-include-plans",
        "--no-include-case-details",
    ]

    _require_success(
        _run_command(
            cmd=[
                *common,
                "--embedding-provider",
                off_provider,
                "--embedding-model",
                "hash-cross-v1",
                "--output",
                str(off_dir),
            ],
            env=env,
        ),
        label="late interaction slice off",
    )
    off_metrics = _read_benchmark_metrics(off_dir / "results.json")

    _require_success(
        _run_command(
            cmd=[
                *common,
                "--embedding-provider",
                on_provider,
                "--embedding-model",
                "hash-colbert-v1",
                "--output",
                str(on_dir),
            ],
            env=env,
        ),
        label="late interaction slice on",
    )
    on_metrics = _read_benchmark_metrics(on_dir / "results.json")

    failures, deltas = _evaluate_delta_thresholds(
        off_metrics=off_metrics,
        on_metrics=on_metrics,
        thresholds=thresholds,
        name="late_interaction",
    )

    return {
        "name": "late_interaction",
        "passed": len(failures) == 0,
        "thresholds": thresholds,
        "providers": {"off": off_provider, "on": on_provider},
        "off": {"output_dir": str(off_dir), "metrics": off_metrics},
        "on": {"output_dir": str(on_dir), "metrics": on_metrics},
        "deltas": deltas,
        "failures": failures,
    }


def _seed_dependency_recall_repo(root: Path) -> Path:
    (root / "src" / "app" / "dependencies").mkdir(parents=True, exist_ok=True)
    (root / "src" / "app" / "validators").mkdir(parents=True, exist_ok=True)
    (root / "benchmark" / "cases").mkdir(parents=True, exist_ok=True)

    (root / "src" / "app" / "gateway.py").write_text(
        (
            "from app.dependencies.request_context import build_request_context\n"
            "from app.validators.token_validator import validate_token\n\n"
            "def authorize_request(raw_token: str) -> bool:\n"
            "    ctx = build_request_context(raw_token)\n"
            "    return validate_token(ctx['token'])\n"
        ),
        encoding="utf-8",
    )
    (root / "src" / "app" / "dependencies" / "request_context.py").write_text(
        (
            "def build_request_context(raw_token: str) -> dict[str, str]:\n"
            "    return {'token': raw_token.strip()}\n"
        ),
        encoding="utf-8",
    )
    (root / "src" / "app" / "validators" / "token_validator.py").write_text(
        (
            "def validate_token(raw_token: str) -> bool:\n"
            "    return bool(raw_token)\n"
        ),
        encoding="utf-8",
    )
    (root / "src" / "app" / "fallback.py").write_text(
        "def authorize_request(raw_token: str) -> bool:\n    return False\n",
        encoding="utf-8",
    )

    cases_path = root / "benchmark" / "cases" / "dependency_recall_slice.yaml"
    cases_path.write_text(
        (
            "cases:\n"
            "  - case_id: dependency-recall-01\n"
            "    query: where request auth gateway validates token\n"
            "    expected_keys: [gateway, validate_token]\n"
            "    top_k: 1\n"
        ),
        encoding="utf-8",
    )
    return cases_path


def _seed_perf_routing_repo(root: Path) -> Path:
    (root / "src" / "runtime").mkdir(parents=True, exist_ok=True)
    (root / "src" / "indexing").mkdir(parents=True, exist_ok=True)
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "benchmark" / "cases").mkdir(parents=True, exist_ok=True)

    (root / "src" / "runtime" / "hotspot_ranker.py").write_text(
        (
            "def rank_latency_hotspots(samples: list[tuple[str, float]]) -> list[str]:\n"
            "    \"\"\"Rank hotspot paths by descending latency pressure.\"\"\"\n"
            "    return [path for path, _ in sorted(samples, key=lambda item: (-item[1], item[0]))]\n"
        ),
        encoding="utf-8",
    )
    (root / "src" / "runtime" / "slo_budget.py").write_text(
        (
            "def enforce_slo_budget(latency_ms: float, budget_ms: float) -> bool:\n"
            "    \"\"\"Return whether a latency observation stays inside the SLO budget.\"\"\"\n"
            "    return float(latency_ms) <= float(budget_ms)\n"
        ),
        encoding="utf-8",
    )
    (root / "src" / "indexing" / "stage_profiler.py").write_text(
        (
            "def profile_index_stage(samples: list[float]) -> float:\n"
            "    \"\"\"Profile index-stage latency to surface hotspot regressions.\"\"\"\n"
            "    if not samples:\n"
            "        return 0.0\n"
            "    return max(float(value) for value in samples)\n"
        ),
        encoding="utf-8",
    )
    (root / "src" / "indexing" / "context_budget.py").write_text(
        (
            "def trim_context_for_latency(lines: list[str], max_items: int) -> list[str]:\n"
            "    \"\"\"Trim context packing when latency or budget pressure is high.\"\"\"\n"
            "    return list(lines[: max(0, int(max_items))])\n"
        ),
        encoding="utf-8",
    )
    (root / "docs" / "performance.md").write_text(
        (
            "# Performance Hotspots\n"
            "The performance tuning flow profiles `src/indexing/stage_profiler.py`,\n"
            "`src/runtime/slo_budget.py`, and `src/runtime/hotspot_ranker.py` when\n"
            "latency budgets or SLO downgrade behavior need investigation.\n"
            "Context trimming happens in `src/indexing/context_budget.py`.\n"
        ),
        encoding="utf-8",
    )

    cases_path = root / "benchmark" / "cases" / "perf_routing.yaml"
    cases_path.write_text(
        (
            "cases:\n"
            "  - case_id: perf-routing-01\n"
            "    query: optimize index latency hotspot budget and profile slowdown paths\n"
            "    expected_keys: [profile_index_stage, enforce_slo_budget]\n"
            "    top_k: 2\n"
            "  - case_id: perf-routing-02\n"
            "    query: trim context budget for hotspot ranking when latency exceeds the SLO\n"
            "    expected_keys: [trim_context_for_latency, rank_latency_hotspots]\n"
            "    top_k: 2\n"
        ),
        encoding="utf-8",
    )
    return cases_path


def _seed_stale_majority_repo(root: Path) -> Path:
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "benchmark" / "cases").mkdir(parents=True, exist_ok=True)
    (root / "docs").mkdir(parents=True, exist_ok=True)

    (root / "src" / "auth_service.py").write_text(
        (
            "class AuthService:\n"
            "    def validate_current_token(self, token: str) -> bool:\n"
            "        \"\"\"Current auth token validator for active sessions.\"\"\"\n"
            "        current_mode = True\n"
            "        return bool(token) and current_mode\n\n"
            "    def validate_legacy_token(self, token: str, *, strict: bool = False) -> bool:\n"
            "        \"\"\"Legacy auth token validator kept for stale compatibility mode.\"\"\"\n"
            "        legacy_mode = strict\n"
            "        return bool(token) and legacy_mode\n"
        ),
        encoding="utf-8",
    )
    (root / "src" / "auth_runtime.py").write_text(
        (
            "from auth_service import AuthService\n\n"
            "def validate_active_session(token: str) -> bool:\n"
            "    service = AuthService()\n"
            "    return service.validate_current_token(token)\n"
        ),
        encoding="utf-8",
    )
    (root / "docs" / "auth_migration.md").write_text(
        (
            "# Auth Migration\n"
            "Current active sessions use `AuthService.validate_current_token`.\n"
            "Legacy strict mode remains available via `AuthService.validate_legacy_token`.\n"
        ),
        encoding="utf-8",
    )

    cases_path = root / "benchmark" / "cases" / "stale_majority_slice.yaml"
    cases_path.write_text(
        (
            "cases:\n"
            "  - case_id: stale-majority-01\n"
            "    query: where current auth token validator handles active sessions without legacy strict mode\n"
            "    expected_keys: [auth_service]\n"
            "    top_k: 8\n"
            "    comparison_lane: stale_majority\n"
            "    chunk_guard_expectation:\n"
            "      scenario: stale_majority\n"
            "      expected_retained_refs: [AuthService.validate_current_token]\n"
        ),
        encoding="utf-8",
    )
    return cases_path


def _seed_topological_shield_repo(root: Path) -> Path:
    (root / "src" / "defs").mkdir(parents=True, exist_ok=True)
    (root / "benchmark" / "cases").mkdir(parents=True, exist_ok=True)

    (root / "src" / "service.py").write_text(
        (
            "from defs.helper import resolve_helper\n"
            "from defs.logger import shared_logger\n\n"
            "class Service:\n"
            "    def handle_request(self, token: str) -> str:\n"
            "        value = self.resolve_token(token)\n"
            "        shared_logger(value)\n"
            "        return value\n\n"
            "    def resolve_token(self, token: str) -> str:\n"
            "        return resolve_helper(token)\n\n"
            "    def audit_request(self, token: str) -> None:\n"
            "        shared_logger(token)\n"
        ),
        encoding="utf-8",
    )
    (root / "src" / "use_a.py").write_text(
        (
            "from defs.helper import resolve_helper\n"
            "from defs.logger import shared_logger\n\n"
            "def handle_a(token: str) -> str:\n"
            "    value = resolve_helper(token)\n"
            "    shared_logger(value)\n"
            "    return value\n"
        ),
        encoding="utf-8",
    )
    (root / "src" / "use_b.py").write_text(
        (
            "from defs.helper import resolve_helper\n"
            "from defs.logger import shared_logger\n\n"
            "def handle_b(token: str) -> str:\n"
            "    value = resolve_helper(token)\n"
            "    shared_logger(value)\n"
            "    return value\n"
        ),
        encoding="utf-8",
    )
    (root / "src" / "noise_x.py").write_text(
        (
            "from defs.logger import shared_logger\n\n"
            "def noise_x(token: str) -> None:\n"
            "    shared_logger(token)\n"
        ),
        encoding="utf-8",
    )
    (root / "src" / "noise_y.py").write_text(
        (
            "from defs.logger import shared_logger\n\n"
            "def noise_y(token: str) -> None:\n"
            "    shared_logger(token)\n"
        ),
        encoding="utf-8",
    )
    (root / "src" / "defs" / "helper.py").write_text(
        (
            "def resolve_helper(token: str) -> str:\n"
            "    return token.strip()\n"
        ),
        encoding="utf-8",
    )
    (root / "src" / "defs" / "logger.py").write_text(
        (
            "def shared_logger(token: str) -> None:\n"
            "    _ = token\n"
        ),
        encoding="utf-8",
    )

    cases_path = root / "benchmark" / "cases" / "topological_shield_slice.yaml"
    cases_path.write_text(
        (
            "cases:\n"
            "  - case_id: topological-shield-sibling-01\n"
            "    query: where service handle request resolves token through a graph-near sibling helper\n"
            "    expected_keys: [resolve_token]\n"
            "    top_k: 8\n"
            "    comparison_lane: topological_shield\n"
            "  - case_id: topological-shield-hub-heavy-02\n"
            "    query: where request handlers use resolve helper without overvaluing the shared logger utility hub\n"
            "    expected_keys: [resolve_helper]\n"
            "    top_k: 8\n"
            "    comparison_lane: topological_shield\n"
        ),
        encoding="utf-8",
    )
    return cases_path


def _run_perf_routing_slice(
    *,
    cli_bin: str,
    project_root: Path,
    output_dir: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    workdir = output_dir / "workdir" / "perf_routing"
    cases_path = _seed_perf_routing_repo(workdir)
    thresholds = _extract_thresholds(config, slice_name="perf_routing")
    perf_cfg = _extract_slice_config(
        config,
        slice_name="perf_routing",
        key="perf_routing",
    )
    routing_policy = str(
        perf_cfg.get("retrieval_policy", "general") or "general"
    ).strip().lower()
    off_precomputed = _coerce_bool(
        perf_cfg.get("off_precomputed_skills_routing"),
        default=False,
    )
    on_precomputed = _coerce_bool(
        perf_cfg.get("on_precomputed_skills_routing"),
        default=True,
    )
    top_k_files = max(1, int(perf_cfg.get("top_k_files", 2) or 2))
    chunk_top_k = max(1, int(perf_cfg.get("chunk_top_k", 8) or 8))
    repomap_top_k = max(1, int(perf_cfg.get("repomap_top_k", 2) or 2))
    repomap_neighbor_limit = max(1, int(perf_cfg.get("repomap_neighbor_limit", 4) or 4))
    repomap_budget_tokens = max(64, int(perf_cfg.get("repomap_budget_tokens", 384) or 384))

    env = {"HOME": str(workdir), "USERPROFILE": str(workdir)}
    off_dir = output_dir / "perf-routing-off"
    on_dir = output_dir / "perf-routing-on"
    off_dir.mkdir(parents=True, exist_ok=True)
    on_dir.mkdir(parents=True, exist_ok=True)

    common = [
        cli_bin,
        "benchmark",
        "run",
        "--cases",
        str(cases_path),
        "--repo",
        "demo",
        "--root",
        str(workdir),
        "--skills-dir",
        str((project_root / "skills").resolve()),
        "--languages",
        "python",
        "--candidate-ranker",
        "heuristic",
        "--min-candidate-score",
        "0",
        "--retrieval-policy",
        routing_policy,
        "--top-k-files",
        str(top_k_files),
        "--chunk-top-k",
        str(chunk_top_k),
        "--memory-primary",
        "none",
        "--memory-secondary",
        "none",
        "--repomap",
        "--repomap-top-k",
        str(repomap_top_k),
        "--repomap-neighbor-limit",
        str(repomap_neighbor_limit),
        "--repomap-budget-tokens",
        str(repomap_budget_tokens),
        "--no-plugins",
        "--no-lsp",
        "--no-lsp-xref",
        "--no-trace-export",
        "--no-trace-otlp",
        "--no-include-case-details",
    ]

    _require_success(
        _run_command(
            cmd=[
                *common,
                "--precomputed-skills-routing"
                if off_precomputed
                else "--no-precomputed-skills-routing",
                "--output",
                str(off_dir),
            ],
            env=env,
        ),
        label="perf routing slice off",
    )
    off_metrics = _read_benchmark_metrics(off_dir / "results.json")
    off_routing_source = _read_benchmark_case_routing_source(off_dir / "results.json")

    _require_success(
        _run_command(
            cmd=[
                *common,
                "--precomputed-skills-routing"
                if on_precomputed
                else "--no-precomputed-skills-routing",
                "--output",
                str(on_dir),
            ],
            env=env,
        ),
        label="perf routing slice on",
    )
    on_metrics = _read_benchmark_metrics(on_dir / "results.json")
    on_routing_source = _read_benchmark_case_routing_source(on_dir / "results.json")

    off_task_success = float(off_metrics.get("task_success_rate", 0.0) or 0.0)
    on_task_success = float(on_metrics.get("task_success_rate", 0.0) or 0.0)
    off_precision = float(off_metrics.get("precision_at_k", 0.0) or 0.0)
    on_precision = float(on_metrics.get("precision_at_k", 0.0) or 0.0)
    off_noise = float(off_metrics.get("noise_rate", 0.0) or 0.0)
    on_noise = float(on_metrics.get("noise_rate", 0.0) or 0.0)
    off_latency = float(off_metrics.get("latency_p95_ms", 0.0) or 0.0)
    on_latency = float(on_metrics.get("latency_p95_ms", 0.0) or 0.0)
    off_skills_latency = float(off_metrics.get("skills_latency_p95_ms", 0.0) or 0.0)
    on_skills_latency = float(on_metrics.get("skills_latency_p95_ms", 0.0) or 0.0)
    off_skills_budget_used = float(
        off_metrics.get("skills_token_budget_used_mean", 0.0) or 0.0
    )
    on_skills_budget_used = float(
        on_metrics.get("skills_token_budget_used_mean", 0.0) or 0.0
    )
    off_skills_budget_exhausted = float(
        off_metrics.get("skills_budget_exhausted_ratio", 0.0) or 0.0
    )
    on_skills_budget_exhausted = float(
        on_metrics.get("skills_budget_exhausted_ratio", 0.0) or 0.0
    )

    deltas = {
        "task_success_delta": on_task_success - off_task_success,
        "precision_delta": on_precision - off_precision,
        "noise_increase": on_noise - off_noise,
        "latency_growth_factor": (
            (on_latency / off_latency)
            if off_latency > 0.0
            else (1.0 if on_latency <= 0.0 else float("inf"))
        ),
        "skills_latency_growth_factor": (
            (on_skills_latency / off_skills_latency)
            if off_skills_latency > 0.0
            else (1.0 if on_skills_latency <= 0.0 else float("inf"))
        ),
        "skills_token_budget_used_increase": on_skills_budget_used - off_skills_budget_used,
        "skills_budget_exhausted_increase": (
            on_skills_budget_exhausted - off_skills_budget_exhausted
        ),
    }
    failures: list[dict[str, Any]] = []
    expected_off_routing_source = "precomputed" if off_precomputed else "same_stage"
    expected_on_routing_source = "precomputed" if on_precomputed else "same_stage"

    if off_routing_source != expected_off_routing_source:
        failures.append(
            {
                "slice": "perf_routing",
                "metric": "off_routing_source",
                "actual": off_routing_source or "(missing)",
                "operator": "==",
                "expected": expected_off_routing_source,
            }
        )

    if on_routing_source != expected_on_routing_source:
        failures.append(
            {
                "slice": "perf_routing",
                "metric": "on_routing_source",
                "actual": on_routing_source or "(missing)",
                "operator": "==",
                "expected": expected_on_routing_source,
            }
        )

    task_success_min = float(thresholds.get("task_success_min", 1.0) or 1.0)
    if on_task_success < task_success_min:
        failures.append(
            {
                "slice": "perf_routing",
                "metric": "task_success_rate",
                "actual": on_task_success,
                "operator": ">=",
                "expected": task_success_min,
            }
        )

    task_success_delta_min = float(
        thresholds.get("task_success_delta_min", 0.0) or 0.0
    )
    if deltas["task_success_delta"] < task_success_delta_min:
        failures.append(
            {
                "slice": "perf_routing",
                "metric": "task_success_delta",
                "actual": deltas["task_success_delta"],
                "operator": ">=",
                "expected": task_success_delta_min,
            }
        )

    precision_delta_min = float(thresholds.get("precision_delta_min", 0.0) or 0.0)
    if deltas["precision_delta"] < precision_delta_min:
        failures.append(
            {
                "slice": "perf_routing",
                "metric": "precision_delta",
                "actual": deltas["precision_delta"],
                "operator": ">=",
                "expected": precision_delta_min,
            }
        )

    noise_increase_max = float(thresholds.get("noise_increase_max", 0.0) or 0.0)
    if deltas["noise_increase"] > noise_increase_max:
        failures.append(
            {
                "slice": "perf_routing",
                "metric": "noise_increase",
                "actual": deltas["noise_increase"],
                "operator": "<=",
                "expected": noise_increase_max,
            }
        )

    if "latency_growth_factor_max" in thresholds and (
        deltas["latency_growth_factor"]
        > float(thresholds.get("latency_growth_factor_max", 1.0) or 1.0)
    ):
        failures.append(
            {
                "slice": "perf_routing",
                "metric": "latency_growth_factor",
                "actual": deltas["latency_growth_factor"],
                "operator": "<=",
                "expected": float(thresholds.get("latency_growth_factor_max", 1.0) or 1.0),
            }
        )

    if "skills_latency_growth_factor_max" in thresholds and (
        deltas["skills_latency_growth_factor"]
        > float(thresholds.get("skills_latency_growth_factor_max", 1.0) or 1.0)
    ):
        failures.append(
            {
                "slice": "perf_routing",
                "metric": "skills_latency_growth_factor",
                "actual": deltas["skills_latency_growth_factor"],
                "operator": "<=",
                "expected": float(
                    thresholds.get("skills_latency_growth_factor_max", 1.0) or 1.0
                ),
            }
        )

    if "skills_token_budget_used_increase_max" in thresholds and (
        deltas["skills_token_budget_used_increase"]
        > float(thresholds.get("skills_token_budget_used_increase_max", 0.0) or 0.0)
    ):
        failures.append(
            {
                "slice": "perf_routing",
                "metric": "skills_token_budget_used_increase",
                "actual": deltas["skills_token_budget_used_increase"],
                "operator": "<=",
                "expected": float(
                    thresholds.get("skills_token_budget_used_increase_max", 0.0) or 0.0
                ),
            }
        )

    if "skills_budget_exhausted_increase_max" in thresholds and (
        deltas["skills_budget_exhausted_increase"]
        > float(thresholds.get("skills_budget_exhausted_increase_max", 0.0) or 0.0)
    ):
        failures.append(
            {
                "slice": "perf_routing",
                "metric": "skills_budget_exhausted_increase",
                "actual": deltas["skills_budget_exhausted_increase"],
                "operator": "<=",
                "expected": float(
                    thresholds.get("skills_budget_exhausted_increase_max", 0.0) or 0.0
                ),
            }
        )

    return {
        "name": "perf_routing",
        "passed": len(failures) == 0,
        "thresholds": thresholds,
        "policy": routing_policy,
        "routing_sources": {
            "off": off_routing_source,
            "on": on_routing_source,
        },
        "precomputed_routing_enabled": {
            "off": off_precomputed,
            "on": on_precomputed,
        },
        "off": {"output_dir": str(off_dir), "metrics": off_metrics},
        "on": {"output_dir": str(on_dir), "metrics": on_metrics},
        "deltas": deltas,
        "failures": failures,
    }


def _run_stale_majority_slice(
    *,
    cli_bin: str,
    project_root: Path,
    output_dir: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    lane = "stale_majority"
    workdir = output_dir / "workdir" / lane
    cases_path = _seed_stale_majority_repo(workdir)
    thresholds = _extract_thresholds(config, slice_name=lane)
    stale_cfg = _extract_slice_config(config, slice_name=lane, key=lane)

    routing_policy = str(
        stale_cfg.get("retrieval_policy", "general") or "general"
    ).strip().lower()
    top_k_files = max(1, int(stale_cfg.get("top_k_files", 1) or 1))
    chunk_top_k = max(1, int(stale_cfg.get("chunk_top_k", 8) or 8))
    chunk_guard_mode = str(
        stale_cfg.get("chunk_guard_mode", "report_only") or "report_only"
    ).strip().lower()
    chunk_guard_lambda_penalty = float(
        stale_cfg.get("chunk_guard_lambda_penalty", 4.0) or 4.0
    )
    chunk_guard_min_pool = max(1, int(stale_cfg.get("chunk_guard_min_pool", 1) or 1))
    chunk_guard_min_marginal_utility = float(
        stale_cfg.get("chunk_guard_min_marginal_utility", 0.2) or 0.2
    )

    env = {"HOME": str(workdir), "USERPROFILE": str(workdir)}
    off_dir = output_dir / "stale-majority-off"
    on_dir = output_dir / "stale-majority-on"
    off_dir.mkdir(parents=True, exist_ok=True)
    on_dir.mkdir(parents=True, exist_ok=True)

    common = [
        cli_bin,
        "benchmark",
        "run",
        "--cases",
        str(cases_path),
        "--repo",
        "demo",
        "--root",
        str(workdir),
        "--skills-dir",
        str((project_root / "skills").resolve()),
        "--languages",
        "python",
        "--candidate-ranker",
        "heuristic",
        "--min-candidate-score",
        "0",
        "--retrieval-policy",
        routing_policy,
        "--top-k-files",
        str(top_k_files),
        "--chunk-top-k",
        str(chunk_top_k),
        "--memory-primary",
        "none",
        "--memory-secondary",
        "none",
        "--no-repomap",
        "--no-plugins",
        "--no-lsp",
        "--no-lsp-xref",
        "--no-cochange",
        "--no-scip",
        "--no-trace-export",
        "--no-trace-otlp",
        "--no-include-plans",
        "--no-include-case-details",
    ]

    _require_success(
        _run_command(
            cmd=[*common, "--no-chunk-guard", "--output", str(off_dir)],
            env=env,
        ),
        label="stale majority slice off",
    )
    off_metrics = _read_benchmark_metrics(off_dir / "results.json")
    off_lane_metrics = _read_benchmark_comparison_lane_metrics(
        off_dir / "results.json",
        lane=lane,
    )

    _require_success(
        _run_command(
            cmd=[
                *common,
                "--chunk-guard",
                "--chunk-guard-mode",
                chunk_guard_mode,
                "--chunk-guard-lambda-penalty",
                str(chunk_guard_lambda_penalty),
                "--chunk-guard-min-pool",
                str(chunk_guard_min_pool),
                "--chunk-guard-min-marginal-utility",
                str(chunk_guard_min_marginal_utility),
                "--output",
                str(on_dir),
            ],
            env=env,
        ),
        label="stale majority slice on",
    )
    on_metrics = _read_benchmark_metrics(on_dir / "results.json")
    on_lane_metrics = _read_benchmark_comparison_lane_metrics(
        on_dir / "results.json",
        lane=lane,
    )

    off_task_success = float(
        off_lane_metrics.get(
            "task_success_rate",
            off_metrics.get("task_success_rate", 0.0),
        )
        or 0.0
    )
    on_task_success = float(
        on_lane_metrics.get(
            "task_success_rate",
            on_metrics.get("task_success_rate", 0.0),
        )
        or 0.0
    )
    off_precision = float(off_metrics.get("precision_at_k", 0.0) or 0.0)
    on_precision = float(on_metrics.get("precision_at_k", 0.0) or 0.0)
    off_noise = float(off_metrics.get("noise_rate", 0.0) or 0.0)
    on_noise = float(on_metrics.get("noise_rate", 0.0) or 0.0)
    off_latency = float(off_metrics.get("latency_p95_ms", 0.0) or 0.0)
    on_latency = float(on_metrics.get("latency_p95_ms", 0.0) or 0.0)
    on_pairwise_conflict_count = float(
        on_lane_metrics.get("chunk_guard_pairwise_conflict_count_mean", 0.0) or 0.0
    )
    on_expected_retained_hit_rate = float(
        on_lane_metrics.get("chunk_guard_expected_retained_hit_rate_mean", 0.0) or 0.0
    )
    on_report_only_improved_rate = float(
        on_lane_metrics.get("chunk_guard_report_only_improved_rate", 0.0) or 0.0
    )

    deltas = {
        "task_success_delta": on_task_success - off_task_success,
        "precision_delta": on_precision - off_precision,
        "noise_increase": on_noise - off_noise,
        "latency_growth_factor": (
            (on_latency / off_latency)
            if off_latency > 0.0
            else (1.0 if on_latency <= 0.0 else float("inf"))
        ),
        "pairwise_conflict_count_delta": on_pairwise_conflict_count
        - float(
            off_lane_metrics.get("chunk_guard_pairwise_conflict_count_mean", 0.0) or 0.0
        ),
        "expected_retained_hit_rate_delta": on_expected_retained_hit_rate
        - float(
            off_lane_metrics.get("chunk_guard_expected_retained_hit_rate_mean", 0.0)
            or 0.0
        ),
        "report_only_improved_rate_delta": on_report_only_improved_rate
        - float(
            off_lane_metrics.get("chunk_guard_report_only_improved_rate", 0.0) or 0.0
        ),
    }

    failures: list[dict[str, Any]] = []
    if not off_lane_metrics:
        failures.append(
            {
                "slice": lane,
                "metric": "off_comparison_lane_present",
                "actual": False,
                "operator": "==",
                "expected": True,
            }
        )
    if not on_lane_metrics:
        failures.append(
            {
                "slice": lane,
                "metric": "on_comparison_lane_present",
                "actual": False,
                "operator": "==",
                "expected": True,
            }
        )

    task_success_min = float(thresholds.get("task_success_min", 1.0) or 1.0)
    if on_task_success < task_success_min:
        failures.append(
            {
                "slice": lane,
                "metric": "task_success_rate",
                "actual": on_task_success,
                "operator": ">=",
                "expected": task_success_min,
            }
        )

    task_success_delta_min = float(
        thresholds.get("task_success_delta_min", 0.0) or 0.0
    )
    if deltas["task_success_delta"] < task_success_delta_min:
        failures.append(
            {
                "slice": lane,
                "metric": "task_success_delta",
                "actual": deltas["task_success_delta"],
                "operator": ">=",
                "expected": task_success_delta_min,
            }
        )

    precision_delta_min = float(thresholds.get("precision_delta_min", 0.0) or 0.0)
    if deltas["precision_delta"] < precision_delta_min:
        failures.append(
            {
                "slice": lane,
                "metric": "precision_delta",
                "actual": deltas["precision_delta"],
                "operator": ">=",
                "expected": precision_delta_min,
            }
        )

    noise_increase_max = float(thresholds.get("noise_increase_max", 0.0) or 0.0)
    if deltas["noise_increase"] > noise_increase_max:
        failures.append(
            {
                "slice": lane,
                "metric": "noise_increase",
                "actual": deltas["noise_increase"],
                "operator": "<=",
                "expected": noise_increase_max,
            }
        )

    latency_growth_factor_max = float(
        thresholds.get("latency_growth_factor_max", 2.0) or 2.0
    )
    if deltas["latency_growth_factor"] > latency_growth_factor_max:
        failures.append(
            {
                "slice": lane,
                "metric": "latency_growth_factor",
                "actual": deltas["latency_growth_factor"],
                "operator": "<=",
                "expected": latency_growth_factor_max,
            }
        )

    pairwise_conflict_count_mean_min = float(
        thresholds.get("pairwise_conflict_count_mean_min", 0.0) or 0.0
    )
    if on_pairwise_conflict_count < pairwise_conflict_count_mean_min:
        failures.append(
            {
                "slice": lane,
                "metric": "pairwise_conflict_count_mean",
                "actual": on_pairwise_conflict_count,
                "operator": ">=",
                "expected": pairwise_conflict_count_mean_min,
            }
        )

    expected_retained_hit_rate_min = float(
        thresholds.get("expected_retained_hit_rate_min", 0.0) or 0.0
    )
    if on_expected_retained_hit_rate < expected_retained_hit_rate_min:
        failures.append(
            {
                "slice": lane,
                "metric": "expected_retained_hit_rate",
                "actual": on_expected_retained_hit_rate,
                "operator": ">=",
                "expected": expected_retained_hit_rate_min,
            }
        )

    report_only_improved_rate_min = float(
        thresholds.get("report_only_improved_rate_min", 0.0) or 0.0
    )
    if on_report_only_improved_rate < report_only_improved_rate_min:
        failures.append(
            {
                "slice": lane,
                "metric": "report_only_improved_rate",
                "actual": on_report_only_improved_rate,
                "operator": ">=",
                "expected": report_only_improved_rate_min,
            }
        )

    return {
        "name": lane,
        "passed": len(failures) == 0,
        "thresholds": thresholds,
        "lane": lane,
        "policy": routing_policy,
        "chunk_guard": {
            "mode": chunk_guard_mode,
            "lambda_penalty": chunk_guard_lambda_penalty,
            "min_pool": chunk_guard_min_pool,
            "min_marginal_utility": chunk_guard_min_marginal_utility,
        },
        "off": {
            "output_dir": str(off_dir),
            "metrics": off_metrics,
            "lane_metrics": off_lane_metrics,
        },
        "on": {
            "output_dir": str(on_dir),
            "metrics": on_metrics,
            "lane_metrics": on_lane_metrics,
        },
        "deltas": deltas,
        "failures": failures,
    }


def _run_topological_shield_slice(
    *,
    cli_bin: str,
    project_root: Path,
    output_dir: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    lane = "topological_shield"
    workdir = output_dir / "workdir" / lane
    cases_path = _seed_topological_shield_repo(workdir)
    thresholds = _extract_thresholds(config, slice_name=lane)
    shield_cfg = _extract_slice_config(config, slice_name=lane, key=lane)

    routing_policy = str(
        shield_cfg.get("retrieval_policy", "general") or "general"
    ).strip().lower()
    top_k_files = max(1, int(shield_cfg.get("top_k_files", 4) or 4))
    chunk_top_k = max(1, int(shield_cfg.get("chunk_top_k", 8) or 8))
    shield_mode = str(
        shield_cfg.get("mode", "report_only") or "report_only"
    ).strip().lower()
    max_attenuation = float(shield_cfg.get("max_attenuation", 0.6) or 0.6)
    shared_parent_attenuation = float(
        shield_cfg.get("shared_parent_attenuation", 0.2) or 0.2
    )
    adjacency_attenuation = float(
        shield_cfg.get("adjacency_attenuation", 0.5) or 0.5
    )

    env = {"HOME": str(workdir), "USERPROFILE": str(workdir)}
    off_dir = output_dir / "topological-shield-off"
    on_dir = output_dir / "topological-shield-on"
    repeat_dir = output_dir / "topological-shield-repeat"
    off_dir.mkdir(parents=True, exist_ok=True)
    on_dir.mkdir(parents=True, exist_ok=True)
    repeat_dir.mkdir(parents=True, exist_ok=True)

    common = [
        cli_bin,
        "benchmark",
        "run",
        "--cases",
        str(cases_path),
        "--repo",
        "demo",
        "--root",
        str(workdir),
        "--skills-dir",
        str((project_root / "skills").resolve()),
        "--languages",
        "python",
        "--candidate-ranker",
        "heuristic",
        "--min-candidate-score",
        "0",
        "--retrieval-policy",
        routing_policy,
        "--top-k-files",
        str(top_k_files),
        "--chunk-top-k",
        str(chunk_top_k),
        "--memory-primary",
        "none",
        "--memory-secondary",
        "none",
        "--no-repomap",
        "--no-plugins",
        "--no-lsp",
        "--no-lsp-xref",
        "--no-cochange",
        "--no-scip",
        "--no-trace-export",
        "--no-trace-otlp",
        "--no-include-plans",
    ]

    _require_success(
        _run_command(cmd=[*common, "--output", str(off_dir)], env=env),
        label="topological shield slice off",
    )
    off_metrics = _read_benchmark_metrics(off_dir / "results.json")
    off_lane_metrics = _read_benchmark_comparison_lane_metrics(
        off_dir / "results.json",
        lane=lane,
    )

    config_path = workdir / ".ace-lite.yml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "benchmark": {
                    "chunk": {
                        "topological_shield": {
                            "enabled": True,
                            "mode": shield_mode,
                            "max_attenuation": max_attenuation,
                            "shared_parent_attenuation": shared_parent_attenuation,
                            "adjacency_attenuation": adjacency_attenuation,
                        }
                    }
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    _require_success(
        _run_command(cmd=[*common, "--output", str(on_dir)], env=env),
        label="topological shield slice on",
    )
    _require_success(
        _run_command(cmd=[*common, "--output", str(repeat_dir)], env=env),
        label="topological shield slice repeat",
    )

    on_metrics = _read_benchmark_metrics(on_dir / "results.json")
    on_lane_metrics = _read_benchmark_comparison_lane_metrics(
        on_dir / "results.json",
        lane=lane,
    )
    repeat_lane_metrics = _read_benchmark_comparison_lane_metrics(
        repeat_dir / "results.json",
        lane=lane,
    )
    on_case_fingerprints = _read_benchmark_case_fingerprints(on_dir / "results.json")
    repeat_case_fingerprints = _read_benchmark_case_fingerprints(
        repeat_dir / "results.json"
    )
    repeat_case_fingerprints_equal = on_case_fingerprints == repeat_case_fingerprints
    repeat_lane_metrics_equal = on_lane_metrics == repeat_lane_metrics

    off_task_success = float(
        off_lane_metrics.get(
            "task_success_rate",
            off_metrics.get("task_success_rate", 0.0),
        )
        or 0.0
    )
    on_task_success = float(
        on_lane_metrics.get(
            "task_success_rate",
            on_metrics.get("task_success_rate", 0.0),
        )
        or 0.0
    )
    off_precision = float(off_metrics.get("precision_at_k", 0.0) or 0.0)
    on_precision = float(on_metrics.get("precision_at_k", 0.0) or 0.0)
    off_noise = float(off_metrics.get("noise_rate", 0.0) or 0.0)
    on_noise = float(on_metrics.get("noise_rate", 0.0) or 0.0)
    off_latency = float(off_metrics.get("latency_p95_ms", 0.0) or 0.0)
    on_latency = float(on_metrics.get("latency_p95_ms", 0.0) or 0.0)
    on_attenuated_chunk_count = float(
        on_lane_metrics.get("topological_shield_attenuated_chunk_count_mean", 0.0)
        or 0.0
    )
    on_attenuation_total = float(
        on_lane_metrics.get("topological_shield_attenuation_total_mean", 0.0) or 0.0
    )

    deltas = {
        "task_success_delta": on_task_success - off_task_success,
        "precision_delta": on_precision - off_precision,
        "noise_increase": on_noise - off_noise,
        "latency_growth_factor": (
            (on_latency / off_latency)
            if off_latency > 0.0
            else (1.0 if on_latency <= 0.0 else float("inf"))
        ),
        "attenuated_chunk_count_delta": on_attenuated_chunk_count
        - float(
            off_lane_metrics.get("topological_shield_attenuated_chunk_count_mean", 0.0)
            or 0.0
        ),
        "attenuation_total_delta": on_attenuation_total
        - float(
            off_lane_metrics.get("topological_shield_attenuation_total_mean", 0.0)
            or 0.0
        ),
    }

    failures: list[dict[str, Any]] = []
    if not off_lane_metrics:
        failures.append(
            {
                "slice": lane,
                "metric": "off_comparison_lane_present",
                "actual": False,
                "operator": "==",
                "expected": True,
            }
        )
    if not on_lane_metrics:
        failures.append(
            {
                "slice": lane,
                "metric": "on_comparison_lane_present",
                "actual": False,
                "operator": "==",
                "expected": True,
            }
        )

    task_success_min = float(thresholds.get("task_success_min", 1.0) or 1.0)
    if on_task_success < task_success_min:
        failures.append(
            {
                "slice": lane,
                "metric": "task_success_rate",
                "actual": on_task_success,
                "operator": ">=",
                "expected": task_success_min,
            }
        )

    task_success_delta_min = float(
        thresholds.get("task_success_delta_min", 0.0) or 0.0
    )
    if deltas["task_success_delta"] < task_success_delta_min:
        failures.append(
            {
                "slice": lane,
                "metric": "task_success_delta",
                "actual": deltas["task_success_delta"],
                "operator": ">=",
                "expected": task_success_delta_min,
            }
        )

    precision_delta_min = float(thresholds.get("precision_delta_min", 0.0) or 0.0)
    if deltas["precision_delta"] < precision_delta_min:
        failures.append(
            {
                "slice": lane,
                "metric": "precision_delta",
                "actual": deltas["precision_delta"],
                "operator": ">=",
                "expected": precision_delta_min,
            }
        )

    noise_increase_max = float(thresholds.get("noise_increase_max", 0.0) or 0.0)
    if deltas["noise_increase"] > noise_increase_max:
        failures.append(
            {
                "slice": lane,
                "metric": "noise_increase",
                "actual": deltas["noise_increase"],
                "operator": "<=",
                "expected": noise_increase_max,
            }
        )

    latency_growth_factor_max = float(
        thresholds.get("latency_growth_factor_max", 2.0) or 2.0
    )
    if deltas["latency_growth_factor"] > latency_growth_factor_max:
        failures.append(
            {
                "slice": lane,
                "metric": "latency_growth_factor",
                "actual": deltas["latency_growth_factor"],
                "operator": "<=",
                "expected": latency_growth_factor_max,
            }
        )

    attenuated_chunk_count_mean_min = float(
        thresholds.get("attenuated_chunk_count_mean_min", 0.0) or 0.0
    )
    if on_attenuated_chunk_count < attenuated_chunk_count_mean_min:
        failures.append(
            {
                "slice": lane,
                "metric": "topological_shield_attenuated_chunk_count_mean",
                "actual": on_attenuated_chunk_count,
                "operator": ">=",
                "expected": attenuated_chunk_count_mean_min,
            }
        )

    attenuation_total_mean_min = float(
        thresholds.get("attenuation_total_mean_min", 0.0) or 0.0
    )
    if on_attenuation_total < attenuation_total_mean_min:
        failures.append(
            {
                "slice": lane,
                "metric": "topological_shield_attenuation_total_mean",
                "actual": on_attenuation_total,
                "operator": ">=",
                "expected": attenuation_total_mean_min,
            }
        )

    require_repeat_fingerprints_equal = bool(
        thresholds.get("require_repeat_fingerprints_equal", 1.0)
    )
    if require_repeat_fingerprints_equal and not repeat_case_fingerprints_equal:
        failures.append(
            {
                "slice": lane,
                "metric": "repeat_case_fingerprints_equal",
                "actual": False,
                "operator": "==",
                "expected": True,
            }
        )

    require_repeat_lane_metrics_equal = bool(
        thresholds.get("require_repeat_lane_metrics_equal", 1.0)
    )
    if require_repeat_lane_metrics_equal and not repeat_lane_metrics_equal:
        failures.append(
            {
                "slice": lane,
                "metric": "repeat_lane_metrics_equal",
                "actual": False,
                "operator": "==",
                "expected": True,
            }
        )

    return {
        "name": lane,
        "passed": len(failures) == 0,
        "thresholds": thresholds,
        "lane": lane,
        "policy": routing_policy,
        "topological_shield": {
            "mode": shield_mode,
            "max_attenuation": max_attenuation,
            "shared_parent_attenuation": shared_parent_attenuation,
            "adjacency_attenuation": adjacency_attenuation,
        },
        "off": {
            "output_dir": str(off_dir),
            "metrics": off_metrics,
            "lane_metrics": off_lane_metrics,
        },
        "on": {
            "output_dir": str(on_dir),
            "metrics": on_metrics,
            "lane_metrics": on_lane_metrics,
            "case_fingerprints": on_case_fingerprints,
        },
        "repeat": {
            "output_dir": str(repeat_dir),
            "lane_metrics": repeat_lane_metrics,
            "case_fingerprints_equal": repeat_case_fingerprints_equal,
            "lane_metrics_equal": repeat_lane_metrics_equal,
        },
        "deltas": deltas,
        "failures": failures,
    }


def _run_dependency_recall_slice(
    *,
    cli_bin: str,
    project_root: Path,
    output_dir: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    workdir = output_dir / "workdir" / "dependency_recall"
    cases_path = _seed_dependency_recall_repo(workdir)
    thresholds = _extract_thresholds(config, slice_name="dependency_recall")
    dep_cfg = _extract_slice_config(
        config,
        slice_name="dependency_recall",
        key="dependency_recall",
    )
    off_profile = str(
        dep_cfg.get("off_repomap_ranking_profile", "heuristic") or "heuristic"
    ).strip().lower()
    on_profile = str(
        dep_cfg.get("on_repomap_ranking_profile", "graph_seeded") or "graph_seeded"
    ).strip().lower()
    repomap_top_k = max(1, int(dep_cfg.get("repomap_top_k", 1) or 1))
    repomap_neighbor_limit = max(1, int(dep_cfg.get("repomap_neighbor_limit", 2) or 2))
    repomap_budget_tokens = max(64, int(dep_cfg.get("repomap_budget_tokens", 256) or 256))

    env = {"HOME": str(workdir), "USERPROFILE": str(workdir)}
    off_dir = output_dir / "dependency-recall-off"
    on_dir = output_dir / "dependency-recall-on"
    off_dir.mkdir(parents=True, exist_ok=True)
    on_dir.mkdir(parents=True, exist_ok=True)

    common = [
        cli_bin,
        "benchmark",
        "run",
        "--cases",
        str(cases_path),
        "--repo",
        "demo",
        "--root",
        str(workdir),
        "--skills-dir",
        str((project_root / "skills").resolve()),
        "--languages",
        "python",
        "--candidate-ranker",
        "heuristic",
        "--min-candidate-score",
        "0",
        "--top-k-files",
        "1",
        "--retrieval-policy",
        "general",
        "--memory-primary",
        "none",
        "--memory-secondary",
        "none",
        "--repomap",
        "--repomap-top-k",
        str(repomap_top_k),
        "--repomap-neighbor-limit",
        str(repomap_neighbor_limit),
        "--repomap-budget-tokens",
        str(repomap_budget_tokens),
        "--no-plugins",
        "--no-lsp",
        "--no-lsp-xref",
        "--no-cochange",
        "--no-scip",
        "--no-trace-export",
        "--no-trace-otlp",
        "--no-include-plans",
        "--no-include-case-details",
    ]

    _require_success(
        _run_command(
            cmd=[
                *common,
                "--repomap-ranking-profile",
                off_profile,
                "--output",
                str(off_dir),
            ],
            env=env,
        ),
        label="dependency recall slice off",
    )
    off_metrics = _read_benchmark_metrics(off_dir / "results.json")

    _require_success(
        _run_command(
            cmd=[
                *common,
                "--repomap-ranking-profile",
                on_profile,
                "--output",
                str(on_dir),
            ],
            env=env,
        ),
        label="dependency recall slice on",
    )
    on_metrics = _read_benchmark_metrics(on_dir / "results.json")

    off_dependency = float(off_metrics.get("dependency_recall", 0.0) or 0.0)
    on_dependency = float(on_metrics.get("dependency_recall", 0.0) or 0.0)
    off_precision = float(off_metrics.get("precision_at_k", 0.0) or 0.0)
    on_precision = float(on_metrics.get("precision_at_k", 0.0) or 0.0)
    off_noise = float(off_metrics.get("noise_rate", 0.0) or 0.0)
    on_noise = float(on_metrics.get("noise_rate", 0.0) or 0.0)
    off_latency = float(off_metrics.get("latency_p95_ms", 0.0) or 0.0)
    on_latency = float(on_metrics.get("latency_p95_ms", 0.0) or 0.0)

    deltas = {
        "dependency_recall_delta": on_dependency - off_dependency,
        "precision_delta": on_precision - off_precision,
        "noise_increase": on_noise - off_noise,
        "latency_growth_factor": (
            (on_latency / off_latency)
            if off_latency > 0.0
            else (1.0 if on_latency <= 0.0 else float("inf"))
        ),
    }
    failures: list[dict[str, Any]] = []

    dependency_recall_min = float(thresholds.get("dependency_recall_min", 0.8) or 0.8)
    if on_dependency < dependency_recall_min:
        failures.append(
            {
                "slice": "dependency_recall",
                "metric": "dependency_recall",
                "actual": on_dependency,
                "operator": ">=",
                "expected": dependency_recall_min,
            }
        )

    dependency_recall_delta_min = float(
        thresholds.get("dependency_recall_delta_min", 0.0) or 0.0
    )
    if deltas["dependency_recall_delta"] < dependency_recall_delta_min:
        failures.append(
            {
                "slice": "dependency_recall",
                "metric": "dependency_recall_delta",
                "actual": deltas["dependency_recall_delta"],
                "operator": ">=",
                "expected": dependency_recall_delta_min,
            }
        )

    precision_delta_min = float(thresholds.get("precision_delta_min", 0.0) or 0.0)
    if deltas["precision_delta"] < precision_delta_min:
        failures.append(
            {
                "slice": "dependency_recall",
                "metric": "precision_delta",
                "actual": deltas["precision_delta"],
                "operator": ">=",
                "expected": precision_delta_min,
            }
        )

    noise_increase_max = float(thresholds.get("noise_increase_max", 0.0) or 0.0)
    if deltas["noise_increase"] > noise_increase_max:
        failures.append(
            {
                "slice": "dependency_recall",
                "metric": "noise_increase",
                "actual": deltas["noise_increase"],
                "operator": "<=",
                "expected": noise_increase_max,
            }
        )

    latency_growth_factor_max = float(
        thresholds.get("latency_growth_factor_max", 2.0) or 2.0
    )
    if deltas["latency_growth_factor"] > latency_growth_factor_max:
        failures.append(
            {
                "slice": "dependency_recall",
                "metric": "latency_growth_factor",
                "actual": deltas["latency_growth_factor"],
                "operator": "<=",
                "expected": latency_growth_factor_max,
            }
        )

    return {
        "name": "dependency_recall",
        "passed": len(failures) == 0,
        "thresholds": thresholds,
        "profiles": {"off": off_profile, "on": on_profile},
        "off": {"output_dir": str(off_dir), "metrics": off_metrics},
        "on": {"output_dir": str(on_dir), "metrics": on_metrics},
        "deltas": deltas,
        "failures": failures,
    }


def _seed_perturbation_baseline_repo(root: Path) -> Path:
    (root / "src" / "auth").mkdir(parents=True, exist_ok=True)
    (root / "src" / "pipeline").mkdir(parents=True, exist_ok=True)
    (root / "src" / "benchmarking").mkdir(parents=True, exist_ok=True)
    (root / "src" / "retrieval").mkdir(parents=True, exist_ok=True)
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "benchmark" / "cases").mkdir(parents=True, exist_ok=True)

    (root / "src" / "auth" / "token_validator.py").write_text(
        (
            "def validate_token(token: str) -> bool:\n"
            "    \"\"\"Auth token validator guard for session checks.\"\"\"\n"
            "    return bool(token)\n"
        ),
        encoding="utf-8",
    )
    (root / "src" / "pipeline" / "source_plan_builder.py").write_text(
        (
            "def build_source_plan() -> list[str]:\n"
            "    \"\"\"Pipeline source plan builder for stage assembly.\"\"\"\n"
            "    return ['memory', 'index', 'repomap']\n"
        ),
        encoding="utf-8",
    )
    (root / "src" / "benchmarking" / "matrix_summary.py").write_text(
        (
            "def build_matrix_summary() -> dict[str, float]:\n"
            "    \"\"\"Build benchmark matrix summary artifacts.\"\"\"\n"
            "    return {'precision_at_k': 1.0}\n"
        ),
        encoding="utf-8",
    )
    (root / "src" / "retrieval" / "candidate_ranker.py").write_text(
        (
            "def rank_candidates(query: str) -> list[str]:\n"
            "    \"\"\"Candidate ranking heuristics for retrieval ordering.\"\"\"\n"
            "    return [query]\n"
        ),
        encoding="utf-8",
    )
    (root / "src" / "retrieval" / "context_packer.py").write_text(
        (
            "def pack_context_window(lines: list[str], budget: int) -> list[str]:\n"
            "    \"\"\"Apply a retrieval context packing budget to the chosen lines.\"\"\"\n"
            "    return list(lines[: max(0, budget)])\n"
        ),
        encoding="utf-8",
    )
    (root / "docs" / "overview.md").write_text(
        "# Overview\nThis repo contains baseline benchmark fixtures.\n",
        encoding="utf-8",
    )

    return _write_cases(
        root / "benchmark" / "cases" / "perturbation_baseline.yaml",
        cases=[
            {
                "case_id": "rename-base",
                "query": "where auth token validation guard is implemented",
                "expected_keys": ["auth", "token_validator"],
                "top_k": 1,
            },
            {
                "case_id": "path-move-base",
                "query": "where source plan builder stages are assembled",
                "expected_keys": ["pipeline", "source_plan_builder"],
                "top_k": 1,
            },
            {
                "case_id": "doc-noise-base",
                "query": "where benchmark matrix summary artifacts are built",
                "expected_keys": ["benchmarking", "matrix_summary"],
                "top_k": 1,
            },
            {
                "case_id": "query-paraphrase-base",
                "query": "where candidate ranking heuristics are applied",
                "expected_keys": ["retrieval", "candidate_ranker"],
                "top_k": 1,
            },
            {
                "case_id": "file-growth-base",
                "query": "where retrieval context packing budget is applied",
                "expected_keys": ["retrieval", "context_packer"],
                "top_k": 1,
            },
        ],
    )


def _seed_perturbation_perturbed_repo(root: Path) -> Path:
    (root / "src" / "auth").mkdir(parents=True, exist_ok=True)
    (root / "src" / "planning").mkdir(parents=True, exist_ok=True)
    (root / "src" / "benchmarking").mkdir(parents=True, exist_ok=True)
    (root / "src" / "retrieval").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "noise").mkdir(parents=True, exist_ok=True)
    (root / "benchmark" / "cases").mkdir(parents=True, exist_ok=True)

    (root / "src" / "auth" / "token_guard.py").write_text(
        (
            "def validate_token(token: str) -> bool:\n"
            "    \"\"\"Auth token validation guard after rename.\"\"\"\n"
            "    return bool(token)\n"
        ),
        encoding="utf-8",
    )
    (root / "src" / "planning" / "source_plan_builder.py").write_text(
        (
            "def build_source_plan() -> list[str]:\n"
            "    \"\"\"Planning source plan builder after path move.\"\"\"\n"
            "    return ['memory', 'index', 'repomap']\n"
        ),
        encoding="utf-8",
    )
    (root / "src" / "benchmarking" / "matrix_summary.py").write_text(
        (
            "def build_matrix_summary() -> dict[str, float]:\n"
            "    \"\"\"Build benchmark matrix summary artifacts.\"\"\"\n"
            "    return {'precision_at_k': 1.0}\n"
        ),
        encoding="utf-8",
    )
    (root / "src" / "retrieval" / "candidate_ranker.py").write_text(
        (
            "def rank_candidates(query: str) -> list[str]:\n"
            "    \"\"\"Module that orders candidate files during retrieval.\"\"\"\n"
            "    return [query]\n"
        ),
        encoding="utf-8",
    )
    (root / "src" / "retrieval" / "context_packer.py").write_text(
        (
            "def _summarize_budget_usage(lines: list[str]) -> int:\n"
            "    return sum(len(line.strip()) for line in lines)\n\n"
            "def _emit_chunk_snapshot(lines: list[str]) -> list[str]:\n"
            "    return [line.strip() for line in lines if line.strip()]\n\n"
            "def _drop_debug_headers(lines: list[str]) -> list[str]:\n"
            "    return [line for line in lines if not line.startswith('# debug')]\n\n"
            "def _score_candidate_pressure(lines: list[str], budget: int) -> float:\n"
            "    used = min(len(lines), max(0, budget))\n"
            "    return float(used) / float(max(1, budget))\n\n"
            "def pack_context_window(lines: list[str], budget: int) -> list[str]:\n"
            "    \"\"\"Apply a retrieval context packing budget to the chosen lines.\"\"\"\n"
            "    cleaned = _drop_debug_headers(lines)\n"
            "    snapshot = _emit_chunk_snapshot(cleaned)\n"
            "    _ = _score_candidate_pressure(snapshot, budget)\n"
            "    _ = _summarize_budget_usage(snapshot)\n"
            "    return list(snapshot[: max(0, budget)])\n"
        ),
        encoding="utf-8",
    )
    for index in range(1, 4):
        (root / "docs" / "noise" / f"operator_manual_{index}.md").write_text(
            (
                "# Operator Manual\n"
                "This note mentions benchmark matrix summary artifacts repeatedly.\n"
                "It is documentation noise and should not outrank source code.\n"
            ),
            encoding="utf-8",
        )

    return _write_cases(
        root / "benchmark" / "cases" / "perturbation_perturbed.yaml",
        cases=[
            {
                "case_id": "rename-perturbed",
                "query": "where auth token validation guard is implemented",
                "expected_keys": ["auth", "token_guard"],
                "top_k": 1,
            },
            {
                "case_id": "path-move-perturbed",
                "query": "where source plan builder stages are assembled",
                "expected_keys": ["planning", "source_plan_builder"],
                "top_k": 1,
            },
            {
                "case_id": "doc-noise-perturbed",
                "query": "where benchmark matrix summary artifacts are built",
                "expected_keys": ["benchmarking", "matrix_summary"],
                "top_k": 1,
            },
            {
                "case_id": "query-paraphrase-perturbed",
                "query": "which module orders candidate files during retrieval",
                "expected_keys": ["retrieval", "candidate_ranker"],
                "top_k": 1,
            },
            {
                "case_id": "file-growth-perturbed",
                "query": "where retrieval context packing budget is applied",
                "expected_keys": ["retrieval", "context_packer"],
                "top_k": 1,
            },
        ],
    )


def _run_perturbation_slice(
    *,
    cli_bin: str,
    project_root: Path,
    output_dir: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    workdir = output_dir / "workdir" / "perturbation"
    baseline_root = workdir / "baseline"
    perturbed_root = workdir / "perturbed"
    baseline_cases_path = _seed_perturbation_baseline_repo(baseline_root)
    perturbed_cases_path = _seed_perturbation_perturbed_repo(perturbed_root)
    thresholds = _extract_thresholds(config, slice_name="perturbation")
    perturbation_cfg = _extract_slice_config(
        config,
        slice_name="perturbation",
        key="perturbation",
    )
    chunk_guard_mode = str(
        perturbation_cfg.get("chunk_guard_mode", "off") or "off"
    ).strip().lower()
    if chunk_guard_mode not in {"off", "report_only", "enforce"}:
        chunk_guard_mode = "off"
    chunk_guard_lambda_penalty = float(
        perturbation_cfg.get("chunk_guard_lambda_penalty", 4.0) or 4.0
    )
    chunk_guard_min_pool = max(
        1,
        int(perturbation_cfg.get("chunk_guard_min_pool", 1) or 1),
    )
    chunk_guard_min_marginal_utility = float(
        perturbation_cfg.get("chunk_guard_min_marginal_utility", 0.2) or 0.2
    )
    chunk_guard_args: list[str] = []
    chunk_guard_payload: dict[str, Any] = {}
    if chunk_guard_mode != "off":
        chunk_guard_args = [
            "--chunk-guard",
            "--chunk-guard-mode",
            chunk_guard_mode,
            "--chunk-guard-lambda-penalty",
            str(chunk_guard_lambda_penalty),
            "--chunk-guard-min-pool",
            str(chunk_guard_min_pool),
            "--chunk-guard-min-marginal-utility",
            str(chunk_guard_min_marginal_utility),
        ]
        chunk_guard_payload = {
            "mode": chunk_guard_mode,
            "lambda_penalty": chunk_guard_lambda_penalty,
            "min_pool": chunk_guard_min_pool,
            "min_marginal_utility": chunk_guard_min_marginal_utility,
        }

    baseline_output = output_dir / "perturbation-baseline"
    perturbed_output = output_dir / "perturbation-perturbed"
    baseline_output.mkdir(parents=True, exist_ok=True)
    perturbed_output.mkdir(parents=True, exist_ok=True)

    common = [
        cli_bin,
        "benchmark",
        "run",
        "--repo",
        "demo",
        "--skills-dir",
        str((project_root / "skills").resolve()),
        "--languages",
        "python,markdown",
        "--candidate-ranker",
        "heuristic",
        "--min-candidate-score",
        "0",
        "--top-k-files",
        "1",
        "--memory-primary",
        "none",
        "--memory-secondary",
        "none",
        "--no-repomap",
        "--no-plugins",
        "--no-lsp",
        "--no-lsp-xref",
        "--no-cochange",
        "--no-scip",
        "--no-trace-export",
        "--no-trace-otlp",
        "--no-include-plans",
        "--no-include-case-details",
    ]

    baseline_env = {"HOME": str(baseline_root), "USERPROFILE": str(baseline_root)}
    perturbed_env = {"HOME": str(perturbed_root), "USERPROFILE": str(perturbed_root)}

    _require_success(
        _run_command(
            cmd=[
                *common,
                "--cases",
                str(baseline_cases_path),
                "--root",
                str(baseline_root),
                *chunk_guard_args,
                "--output",
                str(baseline_output),
            ],
            env=baseline_env,
        ),
        label="perturbation baseline",
    )
    _require_success(
        _run_command(
            cmd=[
                *common,
                "--cases",
                str(perturbed_cases_path),
                "--root",
                str(perturbed_root),
                *chunk_guard_args,
                "--output",
                str(perturbed_output),
            ],
            env=perturbed_env,
        ),
        label="perturbation perturbed",
    )

    baseline_metrics = _read_benchmark_metrics(baseline_output / "results.json")
    perturbed_metrics = _read_benchmark_metrics(perturbed_output / "results.json")
    baseline_rows = _read_benchmark_case_rows(baseline_output / "results.json")
    perturbed_rows = _read_benchmark_case_rows(perturbed_output / "results.json")

    pair_specs = [
        ("rename", "rename-base", "rename-perturbed"),
        ("path_move", "path-move-base", "path-move-perturbed"),
        ("doc_noise", "doc-noise-base", "doc-noise-perturbed"),
        ("file_growth", "file-growth-base", "file-growth-perturbed"),
        ("query_paraphrase", "query-paraphrase-base", "query-paraphrase-perturbed"),
    ]

    perturbations: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for name, baseline_id, perturbed_id in pair_specs:
        pair_failures, deltas = _evaluate_perturbation_pair(
            perturbation=name,
            baseline_case=baseline_rows.get(baseline_id),
            perturbed_case=perturbed_rows.get(perturbed_id),
            thresholds=thresholds,
        )
        perturbations.append(
            {
                "name": name,
                "baseline_case_id": baseline_id,
                "perturbed_case_id": perturbed_id,
                "passed": len(pair_failures) == 0,
                "baseline": baseline_rows.get(baseline_id, {}),
                "perturbed": perturbed_rows.get(perturbed_id, {}),
                "deltas": deltas,
                "failures": pair_failures,
            }
        )
        failures.extend(pair_failures)

    aggregate_deltas = {
        "task_success_delta": float(
            perturbed_metrics.get("task_success_rate", 0.0)
            - baseline_metrics.get("task_success_rate", 0.0)
        ),
        "precision_delta": float(
            perturbed_metrics.get("precision_at_k", 0.0)
            - baseline_metrics.get("precision_at_k", 0.0)
        ),
        "noise_increase": float(
            perturbed_metrics.get("noise_rate", 0.0)
            - baseline_metrics.get("noise_rate", 0.0)
        ),
    }

    return {
        "name": "perturbation",
        "passed": len(failures) == 0,
        "thresholds": thresholds,
        "chunk_guard": chunk_guard_payload,
        "baseline": {"output_dir": str(baseline_output), "metrics": baseline_metrics},
        "perturbed": {
            "output_dir": str(perturbed_output),
            "metrics": perturbed_metrics,
        },
        "deltas": aggregate_deltas,
        "perturbations": perturbations,
        "failures": failures,
    }


def _seed_repomap_perturbation_baseline_repo(root: Path) -> Path:
    (root / "src" / "app" / "security").mkdir(parents=True, exist_ok=True)
    (root / "src" / "app" / "validation").mkdir(parents=True, exist_ok=True)
    (root / "benchmark" / "cases").mkdir(parents=True, exist_ok=True)

    (root / "src" / "app" / "gateway.py").write_text(
        (
            "from app.security.session_context import build_session_context\n"
            "from app.validation.token_policy import token_allowed\n\n"
            "def authorize_request(raw_token: str) -> bool:\n"
            "    ctx = build_session_context(raw_token)\n"
            "    return token_allowed(ctx['token'])\n"
        ),
        encoding="utf-8",
    )
    (root / "src" / "app" / "security" / "session_context.py").write_text(
        (
            "def build_session_context(raw_token: str) -> dict[str, str]:\n"
            "    return {'token': raw_token.strip()}\n"
        ),
        encoding="utf-8",
    )
    (root / "src" / "app" / "validation" / "token_policy.py").write_text(
        (
            "def token_allowed(token: str) -> bool:\n"
            "    return bool(token)\n"
        ),
        encoding="utf-8",
    )
    (root / "src" / "app" / "fallback.py").write_text(
        "def authorize_request(raw_token: str) -> bool:\n    return False\n",
        encoding="utf-8",
    )

    return _write_cases(
        root / "benchmark" / "cases" / "repomap_perturbation_baseline.yaml",
        cases=[
            {
                "case_id": "graph-rename-base",
                "query": "where authorize_request turns the raw token into a session payload",
                "expected_keys": ["gateway", "session_context"],
                "top_k": 1,
            },
            {
                "case_id": "graph-path-move-base",
                "query": "which dependency policy authorize_request uses to allow the session token",
                "expected_keys": ["gateway", "token_policy"],
                "top_k": 1,
            },
        ],
    )


def _seed_repomap_perturbation_perturbed_repo(root: Path) -> Path:
    (root / "src" / "app" / "security").mkdir(parents=True, exist_ok=True)
    (root / "src" / "app" / "access" / "policies").mkdir(parents=True, exist_ok=True)
    (root / "benchmark" / "cases").mkdir(parents=True, exist_ok=True)

    (root / "src" / "app" / "gateway.py").write_text(
        (
            "from app.security.session_state import build_session_context\n"
            "from app.access.policies.token_policy import token_allowed\n\n"
            "def authorize_request(raw_token: str) -> bool:\n"
            "    ctx = build_session_context(raw_token)\n"
            "    return token_allowed(ctx['token'])\n"
        ),
        encoding="utf-8",
    )
    (root / "src" / "app" / "security" / "session_state.py").write_text(
        (
            "def build_session_context(raw_token: str) -> dict[str, str]:\n"
            "    return {'token': raw_token.strip()}\n"
        ),
        encoding="utf-8",
    )
    (root / "src" / "app" / "access" / "policies" / "token_policy.py").write_text(
        (
            "def token_allowed(token: str) -> bool:\n"
            "    return bool(token)\n"
        ),
        encoding="utf-8",
    )
    (root / "src" / "app" / "fallback.py").write_text(
        "def authorize_request(raw_token: str) -> bool:\n    return False\n",
        encoding="utf-8",
    )

    return _write_cases(
        root / "benchmark" / "cases" / "repomap_perturbation_perturbed.yaml",
        cases=[
            {
                "case_id": "graph-rename-perturbed",
                "query": "where authorize_request turns the raw token into a session payload",
                "expected_keys": ["gateway", "session_state"],
                "top_k": 1,
            },
            {
                "case_id": "graph-path-move-perturbed",
                "query": "which dependency policy authorize_request uses to allow the session token",
                "expected_keys": ["gateway", "access", "token_policy"],
                "top_k": 1,
            },
        ],
    )


def _run_repomap_perturbation_slice(
    *,
    cli_bin: str,
    project_root: Path,
    output_dir: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    workdir = output_dir / "workdir" / "repomap_perturbation"
    baseline_root = workdir / "baseline"
    perturbed_root = workdir / "perturbed"
    baseline_cases_path = _seed_repomap_perturbation_baseline_repo(baseline_root)
    perturbed_cases_path = _seed_repomap_perturbation_perturbed_repo(perturbed_root)
    thresholds = _extract_thresholds(config, slice_name="repomap_perturbation")
    repomap_cfg = _extract_slice_config(
        config,
        slice_name="repomap_perturbation",
        key="repomap_perturbation",
    )
    ranking_profile = str(
        repomap_cfg.get("repomap_ranking_profile", "graph_seeded") or "graph_seeded"
    ).strip().lower()
    repomap_top_k = max(1, int(repomap_cfg.get("repomap_top_k", 1) or 1))
    repomap_neighbor_limit = max(
        1, int(repomap_cfg.get("repomap_neighbor_limit", 2) or 2)
    )
    repomap_budget_tokens = max(
        64, int(repomap_cfg.get("repomap_budget_tokens", 256) or 256)
    )

    baseline_output = output_dir / "repomap-perturbation-baseline"
    perturbed_output = output_dir / "repomap-perturbation-perturbed"
    baseline_output.mkdir(parents=True, exist_ok=True)
    perturbed_output.mkdir(parents=True, exist_ok=True)

    common = [
        cli_bin,
        "benchmark",
        "run",
        "--repo",
        "demo",
        "--skills-dir",
        str((project_root / "skills").resolve()),
        "--languages",
        "python",
        "--candidate-ranker",
        "heuristic",
        "--min-candidate-score",
        "0",
        "--top-k-files",
        "1",
        "--retrieval-policy",
        "general",
        "--memory-primary",
        "none",
        "--memory-secondary",
        "none",
        "--repomap",
        "--repomap-ranking-profile",
        ranking_profile,
        "--repomap-top-k",
        str(repomap_top_k),
        "--repomap-neighbor-limit",
        str(repomap_neighbor_limit),
        "--repomap-budget-tokens",
        str(repomap_budget_tokens),
        "--no-plugins",
        "--no-lsp",
        "--no-lsp-xref",
        "--no-cochange",
        "--no-scip",
        "--no-trace-export",
        "--no-trace-otlp",
        "--no-include-plans",
        "--no-include-case-details",
    ]

    baseline_env = {"HOME": str(baseline_root), "USERPROFILE": str(baseline_root)}
    perturbed_env = {"HOME": str(perturbed_root), "USERPROFILE": str(perturbed_root)}

    _require_success(
        _run_command(
            cmd=[
                *common,
                "--cases",
                str(baseline_cases_path),
                "--root",
                str(baseline_root),
                "--output",
                str(baseline_output),
            ],
            env=baseline_env,
        ),
        label="repomap perturbation baseline",
    )
    _require_success(
        _run_command(
            cmd=[
                *common,
                "--cases",
                str(perturbed_cases_path),
                "--root",
                str(perturbed_root),
                "--output",
                str(perturbed_output),
            ],
            env=perturbed_env,
        ),
        label="repomap perturbation perturbed",
    )

    baseline_metrics = _read_benchmark_metrics(baseline_output / "results.json")
    perturbed_metrics = _read_benchmark_metrics(perturbed_output / "results.json")
    baseline_rows = _read_benchmark_case_rows(baseline_output / "results.json")
    perturbed_rows = _read_benchmark_case_rows(perturbed_output / "results.json")

    pair_specs = [
        ("dependency_rename", "graph-rename-base", "graph-rename-perturbed"),
        ("dependency_path_move", "graph-path-move-base", "graph-path-move-perturbed"),
    ]

    perturbations: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for name, baseline_id, perturbed_id in pair_specs:
        pair_failures, deltas = _evaluate_perturbation_pair(
            perturbation=name,
            baseline_case=baseline_rows.get(baseline_id),
            perturbed_case=perturbed_rows.get(perturbed_id),
            thresholds=thresholds,
        )
        perturbations.append(
            {
                "name": name,
                "baseline_case_id": baseline_id,
                "perturbed_case_id": perturbed_id,
                "passed": len(pair_failures) == 0,
                "baseline": baseline_rows.get(baseline_id, {}),
                "perturbed": perturbed_rows.get(perturbed_id, {}),
                "deltas": deltas,
                "failures": pair_failures,
            }
        )
        failures.extend(pair_failures)

    aggregate_deltas = {
        "task_success_delta": float(
            perturbed_metrics.get("task_success_rate", 0.0)
            - baseline_metrics.get("task_success_rate", 0.0)
        ),
        "precision_delta": float(
            perturbed_metrics.get("precision_at_k", 0.0)
            - baseline_metrics.get("precision_at_k", 0.0)
        ),
        "noise_increase": float(
            perturbed_metrics.get("noise_rate", 0.0)
            - baseline_metrics.get("noise_rate", 0.0)
        ),
        "dependency_recall_delta": float(
            perturbed_metrics.get("dependency_recall", 0.0)
            - baseline_metrics.get("dependency_recall", 0.0)
        ),
    }

    return {
        "name": "repomap_perturbation",
        "passed": len(failures) == 0,
        "thresholds": thresholds,
        "profiles": {"repomap": ranking_profile},
        "baseline": {"output_dir": str(baseline_output), "metrics": baseline_metrics},
        "perturbed": {
            "output_dir": str(perturbed_output),
            "metrics": perturbed_metrics,
        },
        "deltas": aggregate_deltas,
        "perturbations": perturbations,
        "failures": failures,
    }


def _seed_index_repo(root: Path) -> None:
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "alpha.py").write_text(
        "def alpha() -> int:\n    return 1\n", encoding="utf-8"
    )
    (root / "src" / "beta.py").write_text("def beta() -> int:\n    return 2\n", encoding="utf-8")


def _load_index_files(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    files = payload.get("files")
    return files if isinstance(files, dict) else {}


def _run_index_batch_slice(
    *,
    cli_bin: str,
    output_dir: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    workdir = output_dir / "workdir" / "index-batch"
    _seed_index_repo(workdir)

    thresholds = _extract_thresholds(config, slice_name="index_batch")
    indexing_cfg = _extract_slice_config(config, slice_name="index_batch", key="indexing")
    batch_size = int(indexing_cfg.get("batch_size", 1) or 1)
    timeout_per_file = float(indexing_cfg.get("timeout_per_file", 0.05) or 0.05)
    retry_timeouts = bool(indexing_cfg.get("retry_timeouts", True))
    subprocess_batch = bool(indexing_cfg.get("subprocess_batch", True))

    env = {"HOME": str(workdir), "USERPROFILE": str(workdir)}

    baseline_path = output_dir / "index.baseline.json"
    batch_path = output_dir / "index.batch.json"
    batch_resume_path = output_dir / "index.batch.resume.json"
    resume_state = workdir / "context-map" / "index.resume.gate.json"

    _require_success(
        _run_command(
            cmd=[
                cli_bin,
                "index",
                "--root",
                str(workdir),
                "--languages",
                "python",
                "--output",
                str(baseline_path),
            ],
            env=env,
        ),
        label="index baseline",
    )

    batch_cmd = [
        cli_bin,
        "index",
        "--root",
        str(workdir),
        "--languages",
        "python",
        "--output",
        str(batch_path),
        "--batch-mode",
        "--batch-size",
        str(batch_size),
        "--timeout-per-file",
        str(timeout_per_file),
        "--resume-state",
        str(resume_state),
    ]
    if retry_timeouts:
        batch_cmd.append("--retry-timeouts")
    if subprocess_batch:
        batch_cmd.append("--subprocess-batch")

    _require_success(_run_command(cmd=batch_cmd, env=env), label="index batch")

    _require_success(
        _run_command(
            cmd=[*batch_cmd, "--resume", "--output", str(batch_resume_path)],
            env=env,
        ),
        label="index batch resume",
    )

    baseline_files = _load_index_files(baseline_path)
    batch_files = _load_index_files(batch_path)
    resume_files = _load_index_files(batch_resume_path)

    failures: list[dict[str, Any]] = []
    require_equal = bool(thresholds.get("require_files_equal", True))
    if require_equal:
        if set(baseline_files.keys()) != set(batch_files.keys()):
            failures.append(
                {
                    "slice": "index_batch",
                    "metric": "files_keys_equal",
                    "actual": False,
                    "operator": "==",
                    "expected": True,
                }
            )
        else:
            for path in sorted(baseline_files.keys()):
                left = baseline_files.get(path)
                right = batch_files.get(path)
                if left != right:
                    failures.append(
                        {
                            "slice": "index_batch",
                            "metric": "entry_equal",
                            "path": path,
                            "actual": False,
                            "operator": "==",
                            "expected": True,
                        }
                    )
                    break

        if batch_files != resume_files:
            failures.append(
                {
                    "slice": "index_batch",
                    "metric": "resume_matches_batch",
                    "actual": False,
                    "operator": "==",
                    "expected": True,
                }
            )

    return {
        "name": "index_batch",
        "passed": len(failures) == 0,
        "thresholds": thresholds,
        "outputs": {
            "baseline": str(baseline_path),
            "batch": str(batch_path),
            "batch_resume": str(batch_resume_path),
            "resume_state": str(resume_state),
        },
        "failures": failures,
    }


def _render_markdown(summary: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Feature Slice Matrix Summary")
    lines.append("")
    lines.append(f"- generated_at: {summary.get('generated_at', '')}")
    lines.append(f"- passed: {bool(summary.get('passed', False))}")
    lines.append("")

    slices = summary.get("slices")
    items = slices if isinstance(slices, list) else []
    if items:
        lines.append("| Slice | Passed | Notes |")
        lines.append("| --- | --- | --- |")
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "") or "")
            passed = "PASS" if bool(item.get("passed", False)) else "FAIL"
            failures = item.get("failures")
            note = "-"
            if isinstance(failures, list) and failures:
                first_failure = failures[0]
                perturbation = str(first_failure.get("perturbation", "") or "").strip()
                if perturbation:
                    note = f"{perturbation}:{first_failure.get('metric', 'failed')}"
                else:
                    note = str(first_failure.get("metric", "failed"))
            lines.append(f"| {name} | {passed} | {note} |")
        lines.append("")

    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("name") or "").strip() == "perf_routing":
            lines.append("## Skills Routing Details")
            lines.append("")
            policy = str(item.get("policy") or "").strip()
            if policy:
                lines.append(f"- Retrieval policy: {policy}")
                lines.append("")
            lines.append(
                "| Route | Task Success | Precision | Noise | Latency p95 (ms) | Skills Latency p95 (ms) | Skills Token Budget Used | Skills Budget Exhausted |"
            )
            lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
            off_raw = item.get("off")
            on_raw = item.get("on")
            routing_sources_raw = item.get("routing_sources")
            off = off_raw if isinstance(off_raw, dict) else {}
            on = on_raw if isinstance(on_raw, dict) else {}
            routing_sources = (
                routing_sources_raw if isinstance(routing_sources_raw, dict) else {}
            )
            off_metrics = off.get("metrics") if isinstance(off.get("metrics"), dict) else {}
            on_metrics = on.get("metrics") if isinstance(on.get("metrics"), dict) else {}
            lines.append(
                "| {route} | {task_success:.4f} | {precision:.4f} | {noise:.4f} | {latency:.2f} | {skills_latency:.2f} | {skills_budget:.2f} | {skills_exhausted:.4f} |".format(
                    route=str(routing_sources.get("off") or "off"),
                    task_success=float(off_metrics.get("task_success_rate", 0.0) or 0.0),
                    precision=float(off_metrics.get("precision_at_k", 0.0) or 0.0),
                    noise=float(off_metrics.get("noise_rate", 0.0) or 0.0),
                    latency=float(off_metrics.get("latency_p95_ms", 0.0) or 0.0),
                    skills_latency=float(
                        off_metrics.get("skills_latency_p95_ms", 0.0) or 0.0
                    ),
                    skills_budget=float(
                        off_metrics.get("skills_token_budget_used_mean", 0.0) or 0.0
                    ),
                    skills_exhausted=float(
                        off_metrics.get("skills_budget_exhausted_ratio", 0.0) or 0.0
                    ),
                )
            )
            lines.append(
                "| {route} | {task_success:.4f} | {precision:.4f} | {noise:.4f} | {latency:.2f} | {skills_latency:.2f} | {skills_budget:.2f} | {skills_exhausted:.4f} |".format(
                    route=str(routing_sources.get("on") or "on"),
                    task_success=float(on_metrics.get("task_success_rate", 0.0) or 0.0),
                    precision=float(on_metrics.get("precision_at_k", 0.0) or 0.0),
                    noise=float(on_metrics.get("noise_rate", 0.0) or 0.0),
                    latency=float(on_metrics.get("latency_p95_ms", 0.0) or 0.0),
                    skills_latency=float(
                        on_metrics.get("skills_latency_p95_ms", 0.0) or 0.0
                    ),
                    skills_budget=float(
                        on_metrics.get("skills_token_budget_used_mean", 0.0) or 0.0
                    ),
                    skills_exhausted=float(
                        on_metrics.get("skills_budget_exhausted_ratio", 0.0) or 0.0
                    ),
                )
            )
            lines.append("")
            continue
        if str(item.get("name") or "").strip() == "dependency_recall":
            lines.append("## Dependency Recall Details")
            lines.append("")
            lines.append("| Profile | Dependency Recall | Precision | Noise | Latency p95 (ms) |")
            lines.append("| --- | ---: | ---: | ---: | ---: |")
            off_raw = item.get("off")
            on_raw = item.get("on")
            profiles_raw = item.get("profiles")
            off = off_raw if isinstance(off_raw, dict) else {}
            on = on_raw if isinstance(on_raw, dict) else {}
            profiles = profiles_raw if isinstance(profiles_raw, dict) else {}
            off_metrics = off.get("metrics") if isinstance(off.get("metrics"), dict) else {}
            on_metrics = on.get("metrics") if isinstance(on.get("metrics"), dict) else {}
            lines.append(
                "| {profile} | {dependency:.4f} | {precision:.4f} | {noise:.4f} | {latency:.2f} |".format(
                    profile=str(profiles.get("off") or "off"),
                    dependency=float(off_metrics.get("dependency_recall", 0.0) or 0.0),
                    precision=float(off_metrics.get("precision_at_k", 0.0) or 0.0),
                    noise=float(off_metrics.get("noise_rate", 0.0) or 0.0),
                    latency=float(off_metrics.get("latency_p95_ms", 0.0) or 0.0),
                )
            )
            lines.append(
                "| {profile} | {dependency:.4f} | {precision:.4f} | {noise:.4f} | {latency:.2f} |".format(
                    profile=str(profiles.get("on") or "on"),
                    dependency=float(on_metrics.get("dependency_recall", 0.0) or 0.0),
                    precision=float(on_metrics.get("precision_at_k", 0.0) or 0.0),
                    noise=float(on_metrics.get("noise_rate", 0.0) or 0.0),
                    latency=float(on_metrics.get("latency_p95_ms", 0.0) or 0.0),
                )
            )
            lines.append("")
            continue
        if str(item.get("name") or "").strip() == "stale_majority":
            lines.append("## Stale Majority Details")
            lines.append("")
            lane = str(item.get("lane") or "stale_majority").strip()
            if lane:
                lines.append(f"- Comparison lane: {lane}")
            chunk_guard_raw = item.get("chunk_guard")
            chunk_guard = chunk_guard_raw if isinstance(chunk_guard_raw, dict) else {}
            if chunk_guard:
                lines.append(
                    "- Chunk guard: mode={mode}, lambda_penalty={penalty:.2f}, min_pool={min_pool}, min_marginal_utility={utility:.2f}".format(
                        mode=str(chunk_guard.get("mode") or "report_only"),
                        penalty=float(
                            chunk_guard.get("lambda_penalty", 0.0) or 0.0
                        ),
                        min_pool=int(chunk_guard.get("min_pool", 0) or 0),
                        utility=float(
                            chunk_guard.get("min_marginal_utility", 0.0) or 0.0
                        ),
                    )
                )
            lines.append("")
            lines.append(
                "| Profile | Task Success | Precision | Noise | Retained Hit | Improved | Conflict Mean | Latency p95 (ms) |"
            )
            lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
            off_raw = item.get("off")
            on_raw = item.get("on")
            off = off_raw if isinstance(off_raw, dict) else {}
            on = on_raw if isinstance(on_raw, dict) else {}
            off_metrics = off.get("metrics") if isinstance(off.get("metrics"), dict) else {}
            on_metrics = on.get("metrics") if isinstance(on.get("metrics"), dict) else {}
            off_lane_metrics = (
                off.get("lane_metrics") if isinstance(off.get("lane_metrics"), dict) else {}
            )
            on_lane_metrics = (
                on.get("lane_metrics") if isinstance(on.get("lane_metrics"), dict) else {}
            )
            lines.append(
                "| off | {task_success:.4f} | {precision:.4f} | {noise:.4f} | {retained:.4f} | {improved:.4f} | {conflicts:.4f} | {latency:.2f} |".format(
                    task_success=float(
                        off_lane_metrics.get(
                            "task_success_rate",
                            off_metrics.get("task_success_rate", 0.0),
                        )
                        or 0.0
                    ),
                    precision=float(off_metrics.get("precision_at_k", 0.0) or 0.0),
                    noise=float(off_metrics.get("noise_rate", 0.0) or 0.0),
                    retained=float(
                        off_lane_metrics.get(
                            "chunk_guard_expected_retained_hit_rate_mean",
                            0.0,
                        )
                        or 0.0
                    ),
                    improved=float(
                        off_lane_metrics.get("chunk_guard_report_only_improved_rate", 0.0)
                        or 0.0
                    ),
                    conflicts=float(
                        off_lane_metrics.get(
                            "chunk_guard_pairwise_conflict_count_mean",
                            0.0,
                        )
                        or 0.0
                    ),
                    latency=float(off_metrics.get("latency_p95_ms", 0.0) or 0.0),
                )
            )
            lines.append(
                "| on | {task_success:.4f} | {precision:.4f} | {noise:.4f} | {retained:.4f} | {improved:.4f} | {conflicts:.4f} | {latency:.2f} |".format(
                    task_success=float(
                        on_lane_metrics.get(
                            "task_success_rate",
                            on_metrics.get("task_success_rate", 0.0),
                        )
                        or 0.0
                    ),
                    precision=float(on_metrics.get("precision_at_k", 0.0) or 0.0),
                    noise=float(on_metrics.get("noise_rate", 0.0) or 0.0),
                    retained=float(
                        on_lane_metrics.get(
                            "chunk_guard_expected_retained_hit_rate_mean",
                            0.0,
                        )
                        or 0.0
                    ),
                    improved=float(
                        on_lane_metrics.get("chunk_guard_report_only_improved_rate", 0.0)
                        or 0.0
                    ),
                    conflicts=float(
                        on_lane_metrics.get(
                            "chunk_guard_pairwise_conflict_count_mean",
                            0.0,
                        )
                        or 0.0
                    ),
                    latency=float(on_metrics.get("latency_p95_ms", 0.0) or 0.0),
                )
            )
            lines.append("")
            continue
        if str(item.get("name") or "").strip() == "topological_shield":
            lines.append("## Topological Shield Details")
            lines.append("")
            lane = str(item.get("lane") or "topological_shield").strip()
            if lane:
                lines.append(f"- Comparison lane: {lane}")
            shield_raw = item.get("topological_shield")
            shield = shield_raw if isinstance(shield_raw, dict) else {}
            if shield:
                lines.append(
                    "- Topological shield: mode={mode}, max_attenuation={max_attenuation:.2f}, shared_parent_attenuation={shared_parent:.2f}, adjacency_attenuation={adjacency:.2f}".format(
                        mode=str(shield.get("mode") or "report_only"),
                        max_attenuation=float(
                            shield.get("max_attenuation", 0.0) or 0.0
                        ),
                        shared_parent=float(
                            shield.get("shared_parent_attenuation", 0.0) or 0.0
                        ),
                        adjacency=float(
                            shield.get("adjacency_attenuation", 0.0) or 0.0
                        ),
                    )
                )
            lines.append("")
            lines.append(
                "| Profile | Task Success | Precision | Noise | Attenuated Chunks Mean | Attenuation Total Mean | Hub Penalty Mean | Latency p95 (ms) | Deterministic Repeat |"
            )
            lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
            off_raw = item.get("off")
            on_raw = item.get("on")
            repeat_raw = item.get("repeat")
            off = off_raw if isinstance(off_raw, dict) else {}
            on = on_raw if isinstance(on_raw, dict) else {}
            repeat = repeat_raw if isinstance(repeat_raw, dict) else {}
            off_metrics = off.get("metrics") if isinstance(off.get("metrics"), dict) else {}
            on_metrics = on.get("metrics") if isinstance(on.get("metrics"), dict) else {}
            off_lane_metrics = (
                off.get("lane_metrics") if isinstance(off.get("lane_metrics"), dict) else {}
            )
            on_lane_metrics = (
                on.get("lane_metrics") if isinstance(on.get("lane_metrics"), dict) else {}
            )
            lines.append(
                "| off | {task_success:.4f} | {precision:.4f} | {noise:.4f} | {attenuated:.4f} | {attenuation_total:.4f} | {hub_penalty:.4f} | {latency:.2f} | - |".format(
                    task_success=float(
                        off_lane_metrics.get(
                            "task_success_rate",
                            off_metrics.get("task_success_rate", 0.0),
                        )
                        or 0.0
                    ),
                    precision=float(off_metrics.get("precision_at_k", 0.0) or 0.0),
                    noise=float(off_metrics.get("noise_rate", 0.0) or 0.0),
                    attenuated=float(
                        off_lane_metrics.get(
                            "topological_shield_attenuated_chunk_count_mean",
                            0.0,
                        )
                        or 0.0
                    ),
                    attenuation_total=float(
                        off_lane_metrics.get(
                            "topological_shield_attenuation_total_mean",
                            0.0,
                        )
                        or 0.0
                    ),
                    hub_penalty=float(
                        off_lane_metrics.get("graph_hub_penalty_total_mean", 0.0) or 0.0
                    ),
                    latency=float(off_metrics.get("latency_p95_ms", 0.0) or 0.0),
                )
            )
            lines.append(
                "| on | {task_success:.4f} | {precision:.4f} | {noise:.4f} | {attenuated:.4f} | {attenuation_total:.4f} | {hub_penalty:.4f} | {latency:.2f} | {repeat_status} |".format(
                    task_success=float(
                        on_lane_metrics.get(
                            "task_success_rate",
                            on_metrics.get("task_success_rate", 0.0),
                        )
                        or 0.0
                    ),
                    precision=float(on_metrics.get("precision_at_k", 0.0) or 0.0),
                    noise=float(on_metrics.get("noise_rate", 0.0) or 0.0),
                    attenuated=float(
                        on_lane_metrics.get(
                            "topological_shield_attenuated_chunk_count_mean",
                            0.0,
                        )
                        or 0.0
                    ),
                    attenuation_total=float(
                        on_lane_metrics.get(
                            "topological_shield_attenuation_total_mean",
                            0.0,
                        )
                        or 0.0
                    ),
                    hub_penalty=float(
                        on_lane_metrics.get("graph_hub_penalty_total_mean", 0.0) or 0.0
                    ),
                    latency=float(on_metrics.get("latency_p95_ms", 0.0) or 0.0),
                    repeat_status=(
                        "PASS"
                        if bool(repeat.get("case_fingerprints_equal", False))
                        and bool(repeat.get("lane_metrics_equal", False))
                        else "FAIL"
                    ),
                )
            )
            lines.append("")
            continue
        name = str(item.get("name") or "").strip()
        if name not in {"perturbation", "repomap_perturbation"}:
            continue
        perturbations_raw = item.get("perturbations")
        perturbations = perturbations_raw if isinstance(perturbations_raw, list) else []
        if not perturbations:
            continue
        include_dependency_delta = any(
            isinstance(perturbation, dict)
            and isinstance(perturbation.get("deltas"), dict)
            and "dependency_recall_delta" in perturbation.get("deltas", {})
            for perturbation in perturbations
        )
        lines.append(
            "## Repomap Perturbation Details"
            if name == "repomap_perturbation"
            else "## Perturbation Details"
        )
        lines.append("")
        chunk_guard_raw = item.get("chunk_guard")
        chunk_guard = chunk_guard_raw if isinstance(chunk_guard_raw, dict) else {}
        if chunk_guard:
            lines.append(
                "- Chunk guard: mode={mode}, lambda_penalty={penalty:.2f}, min_pool={min_pool}, min_marginal_utility={utility:.2f}".format(
                    mode=str(chunk_guard.get("mode") or "report_only"),
                    penalty=float(chunk_guard.get("lambda_penalty", 0.0) or 0.0),
                    min_pool=int(chunk_guard.get("min_pool", 0) or 0),
                    utility=float(
                        chunk_guard.get("min_marginal_utility", 0.0) or 0.0
                    ),
                )
            )
            lines.append("")
        if include_dependency_delta:
            lines.append(
                "| Perturbation | Passed | Task Success Delta | Precision Delta | Noise Increase | Dependency Recall Delta |"
            )
            lines.append("| --- | --- | ---: | ---: | ---: | ---: |")
        else:
            lines.append(
                "| Perturbation | Passed | Task Success Delta | Precision Delta | Noise Increase |"
            )
            lines.append("| --- | --- | ---: | ---: | ---: |")
        for perturbation in perturbations:
            if not isinstance(perturbation, dict):
                continue
            deltas_raw = perturbation.get("deltas")
            deltas = deltas_raw if isinstance(deltas_raw, dict) else {}
            if include_dependency_delta:
                lines.append(
                    "| {name} | {passed} | {task_success:+.4f} | {precision:+.4f} | {noise:+.4f} | {dependency:+.4f} |".format(
                        name=str(perturbation.get("name") or "(unknown)"),
                        passed="PASS" if bool(perturbation.get("passed", False)) else "FAIL",
                        task_success=float(deltas.get("task_success_delta", 0.0) or 0.0),
                        precision=float(deltas.get("precision_delta", 0.0) or 0.0),
                        noise=float(deltas.get("noise_increase", 0.0) or 0.0),
                        dependency=float(
                            deltas.get("dependency_recall_delta", 0.0) or 0.0
                        ),
                    )
                )
            else:
                lines.append(
                    "| {name} | {passed} | {task_success:+.4f} | {precision:+.4f} | {noise:+.4f} |".format(
                        name=str(perturbation.get("name") or "(unknown)"),
                        passed="PASS" if bool(perturbation.get("passed", False)) else "FAIL",
                        task_success=float(deltas.get("task_success_delta", 0.0) or 0.0),
                        precision=float(deltas.get("precision_delta", 0.0) or 0.0),
                        noise=float(deltas.get("noise_increase", 0.0) or 0.0),
                    )
                )
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ACE-Lite feature slice matrix gates.")
    parser.add_argument(
        "--config",
        default="benchmark/matrix/feature_slices.yaml",
        help="Feature slice config YAML path.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/benchmark/slices/feature_slices/latest",
        help="Output directory for slice artifacts.",
    )
    parser.add_argument("--cli-bin", default="ace-lite", help="CLI binary name/path.")
    parser.add_argument(
        "--fail-on-thresholds",
        action="store_true",
        help="Exit non-zero if any slice fails thresholds.",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = project_root / config_path

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = project_root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    config = _load_yaml(config_path)

    started = perf_counter()
    slices: list[dict[str, Any]] = []
    slices.append(
        _run_feedback_slice(
            cli_bin=str(args.cli_bin),
            project_root=project_root,
            output_dir=output_dir,
            config=config,
        )
    )
    slices.append(
        _run_temporal_slice(
            cli_bin=str(args.cli_bin),
            project_root=project_root,
            output_dir=output_dir,
            config=config,
        )
    )
    slices.append(
        _run_index_batch_slice(
            cli_bin=str(args.cli_bin),
            output_dir=output_dir,
            config=config,
        )
    )
    slices.append(
        _run_late_interaction_slice(
            cli_bin=str(args.cli_bin),
            project_root=project_root,
            output_dir=output_dir,
            config=config,
        )
    )
    slices.append(
        _run_perf_routing_slice(
            cli_bin=str(args.cli_bin),
            project_root=project_root,
            output_dir=output_dir,
            config=config,
        )
    )
    slices.append(
        _run_stale_majority_slice(
            cli_bin=str(args.cli_bin),
            project_root=project_root,
            output_dir=output_dir,
            config=config,
        )
    )
    slices.append(
        _run_topological_shield_slice(
            cli_bin=str(args.cli_bin),
            project_root=project_root,
            output_dir=output_dir,
            config=config,
        )
    )
    slices.append(
        _run_dependency_recall_slice(
            cli_bin=str(args.cli_bin),
            project_root=project_root,
            output_dir=output_dir,
            config=config,
        )
    )
    slices.append(
        _run_perturbation_slice(
            cli_bin=str(args.cli_bin),
            project_root=project_root,
            output_dir=output_dir,
            config=config,
        )
    )
    slices.append(
        _run_repomap_perturbation_slice(
            cli_bin=str(args.cli_bin),
            project_root=project_root,
            output_dir=output_dir,
            config=config,
        )
    )

    passed = all(bool(item.get("passed", False)) for item in slices)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": str(config_path),
        "passed": passed,
        "elapsed_seconds": round(perf_counter() - started, 3),
        "slices": slices,
    }

    summary_json = output_dir / "feature_slices_summary.json"
    summary_md = output_dir / "feature_slices_summary.md"
    summary_json.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    summary_md.write_text(_render_markdown(summary), encoding="utf-8")

    if args.fail_on_thresholds and not passed:
        print("[feature-slices] threshold checks failed", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
