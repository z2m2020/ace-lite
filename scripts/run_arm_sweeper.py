from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from ace_lite.benchmark_ops import (
    read_benchmark_retrieval_control_plane_gate_summary,
)
from ace_lite.config_pack import CONFIG_PACK_SCHEMA_VERSION

ARM_CATALOG_SCHEMA_VERSION = "ace-lite-arm-catalog-v1"


@dataclass(slots=True)
class CommandResult:
    cmd: list[str]
    cwd: str | None
    returncode: int
    stdout: str
    stderr: str


def _run_command(*, cmd: list[str], cwd: Path | None = None) -> CommandResult:
    completed = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=False,
        capture_output=True,
        text=True,
    )
    return CommandResult(
        cmd=list(cmd),
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


def _normalize_overrides(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, Any] = {}
    for key, value in raw.items():
        name = str(key or "").strip()
        if name:
            normalized[name] = value
    return normalized


def load_arm_catalog(path: str | Path) -> dict[str, Any]:
    catalog_path = Path(path)
    payload = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("arm catalog payload must be an object")

    schema_version = str(payload.get("schema_version") or "").strip()
    if schema_version != ARM_CATALOG_SCHEMA_VERSION:
        raise ValueError(
            f"arm catalog schema mismatch: expected {ARM_CATALOG_SCHEMA_VERSION}, got {schema_version or '(missing)'}"
        )

    arms_raw = payload.get("arms")
    if not isinstance(arms_raw, list) or not arms_raw:
        raise ValueError("arm catalog must define a non-empty arms list")

    shared_overrides = _normalize_overrides(payload.get("shared_overrides"))
    seen: set[str] = set()
    arms: list[dict[str, Any]] = []
    for item in arms_raw:
        if not isinstance(item, dict):
            continue
        arm_id = str(item.get("arm_id") or "").strip()
        if not arm_id:
            raise ValueError("arm catalog entry missing arm_id")
        if arm_id in seen:
            raise ValueError(f"duplicate arm_id in catalog: {arm_id}")
        seen.add(arm_id)
        arms.append(
            {
                "arm_id": arm_id,
                "label": str(item.get("label") or arm_id).strip() or arm_id,
                "description": str(item.get("description") or "").strip(),
                "overrides": _normalize_overrides(item.get("overrides")),
            }
        )

    return {
        "schema_version": schema_version,
        "name": str(payload.get("name") or catalog_path.stem).strip() or catalog_path.stem,
        "description": str(payload.get("description") or "").strip(),
        "shared_overrides": shared_overrides,
        "arms": arms,
        "path": str(catalog_path),
    }


def _load_cases(path: Path) -> list[dict[str, Any]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        rows = payload.get("cases")
        if isinstance(rows, list):
            return [item for item in rows if isinstance(item, dict)]
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _write_config_pack(
    *,
    output_path: Path,
    catalog_name: str,
    arm: dict[str, Any],
    shared_overrides: dict[str, Any],
) -> Path:
    payload = {
        "schema_version": CONFIG_PACK_SCHEMA_VERSION,
        "name": f"{catalog_name}:{arm['arm_id']}",
        "overrides": {**shared_overrides, **dict(arm.get("overrides", {}))},
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def _build_benchmark_command(
    *,
    python_exe: str,
    cases_path: Path,
    repo: str,
    root: Path,
    skills_dir: Path,
    output_dir: Path,
    config_pack_path: Path,
    warmup_runs: int,
    memory_primary: str,
    memory_secondary: str,
) -> list[str]:
    return [
        python_exe,
        "-m",
        "ace_lite.cli",
        "benchmark",
        "run",
        "--cases",
        str(cases_path),
        "--repo",
        str(repo),
        "--root",
        str(root),
        "--skills-dir",
        str(skills_dir),
        "--config-pack",
        str(config_pack_path),
        "--memory-primary",
        str(memory_primary),
        "--memory-secondary",
        str(memory_secondary),
        "--warmup-runs",
        str(max(0, int(warmup_runs))),
        "--no-include-plans",
        "--no-include-case-details",
        "--output",
        str(output_dir),
    ]


def _load_json_file(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _overall_sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
    metrics = item.get("metrics")
    task_success_summary = item.get("task_success_summary")
    metrics_map = metrics if isinstance(metrics, dict) else {}
    task_success_map = task_success_summary if isinstance(task_success_summary, dict) else {}
    return (
        -float(
            task_success_map.get(
                "task_success_rate",
                metrics_map.get("task_success_rate", 0.0),
            )
            or 0.0
        ),
        -float(metrics_map.get("precision_at_k", 0.0) or 0.0),
        float(metrics_map.get("noise_rate", 1.0) or 1.0),
        float(metrics_map.get("latency_p95_ms", 0.0) or 0.0),
        str(item.get("arm_id") or ""),
    )


def _case_sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -float(item.get("task_success_hit", 0.0) or 0.0),
        -float(item.get("recall_hit", 0.0) or 0.0),
        -float(item.get("precision_at_k", 0.0) or 0.0),
        -float(item.get("dependency_recall", 0.0) or 0.0),
        float(item.get("noise_rate", 1.0) or 1.0),
        float(item.get("latency_ms", 0.0) or 0.0),
        str(item.get("arm_id") or ""),
    )


def build_oracle_relabel(
    *,
    cases: list[dict[str, Any]],
    arm_results: list[dict[str, Any]],
) -> dict[str, Any]:
    case_meta = {
        str(item.get("case_id") or "").strip(): item
        for item in cases
        if isinstance(item, dict) and str(item.get("case_id") or "").strip()
    }

    by_case: dict[str, list[dict[str, Any]]] = {}
    for arm in arm_results:
        for row in arm.get("cases", []):
            if not isinstance(row, dict):
                continue
            case_id = str(row.get("case_id") or "").strip()
            if not case_id:
                continue
            by_case.setdefault(case_id, []).append(
                {
                    "arm_id": str(arm.get("arm_id") or ""),
                    "label": str(arm.get("label") or ""),
                    "task_success_hit": float(row.get("task_success_hit", 0.0) or 0.0),
                    "recall_hit": float(row.get("recall_hit", 0.0) or 0.0),
                    "precision_at_k": float(row.get("precision_at_k", 0.0) or 0.0),
                    "dependency_recall": float(row.get("dependency_recall", 0.0) or 0.0),
                    "noise_rate": float(row.get("noise_rate", 0.0) or 0.0),
                    "latency_ms": float(row.get("latency_ms", 0.0) or 0.0),
                }
            )

    labels: list[dict[str, Any]] = []
    for case_id in sorted(by_case):
        ranked = sorted(by_case[case_id], key=_case_sort_key)
        winner = ranked[0]
        source = case_meta.get(case_id, {})
        task_success = source.get("task_success")
        task_success_map = task_success if isinstance(task_success, dict) else {}
        labels.append(
            {
                "case_id": case_id,
                "query": str(source.get("query") or ""),
                "expected_keys": [
                    str(item).strip()
                    for item in source.get("expected_keys", [])
                    if str(item).strip()
                ]
                if isinstance(source.get("expected_keys"), list)
                else [],
                "task_success_mode": str(task_success_map.get("mode", "positive")),
                "comparison_lane": str(source.get("comparison_lane") or ""),
                "oracle_arm_id": str(winner.get("arm_id") or ""),
                "oracle_label": str(winner.get("label") or ""),
                "winner_metrics": {
                    "task_success_hit": float(
                        winner.get("task_success_hit", 0.0) or 0.0
                    ),
                    "recall_hit": float(winner.get("recall_hit", 0.0) or 0.0),
                    "precision_at_k": float(winner.get("precision_at_k", 0.0) or 0.0),
                    "dependency_recall": float(
                        winner.get("dependency_recall", 0.0) or 0.0
                    ),
                    "noise_rate": float(winner.get("noise_rate", 0.0) or 0.0),
                    "latency_ms": float(winner.get("latency_ms", 0.0) or 0.0),
                },
                "arm_rankings": ranked,
            }
        )

    distribution: dict[str, int] = {}
    for item in labels:
        arm_id = str(item.get("oracle_arm_id") or "").strip()
        if arm_id:
            distribution[arm_id] = distribution.get(arm_id, 0) + 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(labels),
        "oracle_distribution": dict(sorted(distribution.items())),
        "labels": labels,
    }


def build_summary(
    *,
    catalog: dict[str, Any],
    cases_path: Path,
    arm_results: list[dict[str, Any]],
    oracle_relabel: dict[str, Any],
) -> dict[str, Any]:
    leaderboard = sorted(
        [
            {
                "arm_id": str(item.get("arm_id") or ""),
                "label": str(item.get("label") or ""),
                "regressed": bool(item.get("regressed", False)),
                "failed_checks": list(item.get("failed_checks", [])),
                "metrics": dict(item.get("metrics", {})),
                "task_success_summary": dict(item.get("task_success_summary", {})),
                "decision_observability_summary": dict(
                    item.get("decision_observability_summary", {})
                ),
                "retrieval_control_plane_gate_summary": dict(
                    item.get("retrieval_control_plane_gate_summary", {})
                ),
                "results_json": str(item.get("results_json") or ""),
                "summary_json": str(item.get("summary_json") or ""),
                "report_md": str(item.get("report_md") or ""),
            }
            for item in arm_results
        ],
        key=_overall_sort_key,
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "catalog": {
            "name": str(catalog.get("name") or ""),
            "path": str(catalog.get("path") or ""),
            "arm_count": len(catalog.get("arms", [])),
        },
        "cases_path": str(cases_path),
        "best_arm_id": str(leaderboard[0]["arm_id"]) if leaderboard else "",
        "leaderboard": leaderboard,
        "oracle_relabel": {
            "case_count": int(oracle_relabel.get("case_count", 0) or 0),
            "oracle_distribution": dict(oracle_relabel.get("oracle_distribution", {})),
        },
    }


def render_summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# ACE-Lite Arm Sweeper Summary",
        "",
        f"- Generated: {summary.get('generated_at', '')}",
        f"- Catalog: {summary.get('catalog', {}).get('name', '')}",
        f"- Cases: {Path(str(summary.get('cases_path', ''))).name}",
        f"- Best arm: {summary.get('best_arm_id', '') or '(none)'}",
        "",
        "## Leaderboard",
        "",
        "| Arm | task_success_rate | precision_at_k | noise_rate | latency_p95_ms | regressed | q2_gate |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for item in summary.get("leaderboard", []):
        if not isinstance(item, dict):
            continue
        metrics = item.get("metrics")
        task_success_summary = item.get("task_success_summary")
        gate_summary = item.get("retrieval_control_plane_gate_summary")
        metrics_map = metrics if isinstance(metrics, dict) else {}
        task_success_map = task_success_summary if isinstance(task_success_summary, dict) else {}
        gate_map = gate_summary if isinstance(gate_summary, dict) else {}
        gate_label = "n/a"
        if gate_map:
            gate_label = "pass" if bool(gate_map.get("gate_passed", False)) else "fail"
        lines.append(
            "| {arm} | {task_success:.4f} | {precision:.4f} | {noise:.4f} | {latency:.2f} | {regressed} | {gate} |".format(
                arm=str(item.get("arm_id") or ""),
                task_success=float(
                    task_success_map.get(
                        "task_success_rate",
                        metrics_map.get("task_success_rate", 0.0),
                    )
                    or 0.0
                ),
                precision=float(metrics_map.get("precision_at_k", 0.0) or 0.0),
                noise=float(metrics_map.get("noise_rate", 0.0) or 0.0),
                latency=float(metrics_map.get("latency_p95_ms", 0.0) or 0.0),
                regressed="yes" if bool(item.get("regressed", False)) else "no",
                gate=gate_label,
            )
        )
    lines.extend(
        [
            "",
            "## Oracle Relabel",
            "",
            f"- Case count: {int(summary.get('oracle_relabel', {}).get('case_count', 0) or 0)}",
        ]
    )
    distribution = summary.get("oracle_relabel", {}).get("oracle_distribution", {})
    if isinstance(distribution, dict) and distribution:
        for arm_id, count in sorted(distribution.items()):
            lines.append(f"- {arm_id}: {int(count or 0)}")
    else:
        lines.append("- (none)")
    lines.append("")
    return "\n".join(lines)


def run_arm_sweeper(
    *,
    catalog_path: Path,
    cases_path: Path,
    repo: str,
    root: Path,
    output_dir: Path,
    python_exe: str,
    skills_dir: Path | None = None,
    warmup_runs: int = 0,
    memory_primary: str = "none",
    memory_secondary: str = "none",
) -> dict[str, Any]:
    catalog = load_arm_catalog(catalog_path)
    cases = _load_cases(cases_path)
    resolved_skills_dir = skills_dir if skills_dir is not None else root / "skills"
    output_dir.mkdir(parents=True, exist_ok=True)

    arm_results: list[dict[str, Any]] = []
    for arm in catalog["arms"]:
        arm_output_dir = output_dir / "arms" / str(arm["arm_id"])
        config_pack_path = _write_config_pack(
            output_path=arm_output_dir / "config_pack.json",
            catalog_name=str(catalog["name"]),
            arm=arm,
            shared_overrides=dict(catalog["shared_overrides"]),
        )
        cmd = _build_benchmark_command(
            python_exe=python_exe,
            cases_path=cases_path,
            repo=repo,
            root=root,
            skills_dir=resolved_skills_dir,
            output_dir=arm_output_dir,
            config_pack_path=config_pack_path,
            warmup_runs=warmup_runs,
            memory_primary=memory_primary,
            memory_secondary=memory_secondary,
        )
        result = _run_command(cmd=cmd, cwd=root)
        _require_success(result, label=f"benchmark arm {arm['arm_id']}")

        results_json = arm_output_dir / "results.json"
        summary_json = arm_output_dir / "summary.json"
        report_md = arm_output_dir / "report.md"
        results_payload = _load_json_file(results_json)
        summary_payload = _load_json_file(summary_json)
        arm_results.append(
            {
                "arm_id": str(arm["arm_id"]),
                "label": str(arm["label"]),
                "results_json": str(results_json),
                "summary_json": str(summary_json),
                "report_md": str(report_md),
                "metrics": dict(summary_payload.get("metrics", {})),
                "task_success_summary": dict(
                    summary_payload.get("task_success_summary", {})
                ),
                "decision_observability_summary": dict(
                    summary_payload.get("decision_observability_summary", {})
                ),
                "retrieval_control_plane_gate_summary": (
                    read_benchmark_retrieval_control_plane_gate_summary(summary_json)
                ),
                "regressed": bool(summary_payload.get("regressed", False)),
                "failed_checks": list(summary_payload.get("failed_checks", [])),
                "cases": list(results_payload.get("cases", [])),
            }
        )

    oracle_relabel = build_oracle_relabel(cases=cases, arm_results=arm_results)
    summary = build_summary(
        catalog=catalog,
        cases_path=cases_path,
        arm_results=arm_results,
        oracle_relabel=oracle_relabel,
    )

    summary_path = output_dir / "summary.json"
    summary_md_path = output_dir / "summary.md"
    oracle_json_path = output_dir / "oracle_relabel.json"
    oracle_jsonl_path = output_dir / "oracle_relabel.jsonl"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_md_path.write_text(render_summary_markdown(summary), encoding="utf-8")
    oracle_json_path.write_text(
        json.dumps(oracle_relabel, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    oracle_jsonl_path.write_text(
        "\n".join(
            json.dumps(item, ensure_ascii=False)
            for item in oracle_relabel.get("labels", [])
            if isinstance(item, dict)
        ),
        encoding="utf-8",
    )

    return {
        "summary_json": str(summary_path),
        "summary_md": str(summary_md_path),
        "oracle_relabel_json": str(oracle_json_path),
        "oracle_relabel_jsonl": str(oracle_jsonl_path),
        "arm_count": len(arm_results),
        "best_arm_id": str(summary.get("best_arm_id") or ""),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a bounded benchmark arm sweep and emit aggregate/oracle artifacts."
    )
    parser.add_argument(
        "--catalog",
        default="benchmark/arms/default_v1.yaml",
        help="Arm catalog YAML path.",
    )
    parser.add_argument("--cases", required=True, help="Benchmark cases YAML/JSON path.")
    parser.add_argument("--repo", required=True, help="Repository label for benchmark runs.")
    parser.add_argument("--root", required=True, help="Repository root for benchmark runs.")
    parser.add_argument(
        "--skills-dir",
        default="",
        help="Optional skills directory. Defaults to <root>/skills.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Output directory for per-arm and aggregate artifacts.",
    )
    parser.add_argument(
        "--python-exe",
        default=sys.executable,
        help="Python executable used to invoke `python -m ace_lite.cli benchmark run`.",
    )
    parser.add_argument(
        "--warmup-runs",
        type=int,
        default=0,
        help="Warmup runs to forward to each benchmark arm.",
    )
    parser.add_argument(
        "--memory-primary",
        default="none",
        help="Memory primary option forwarded to benchmark run.",
    )
    parser.add_argument(
        "--memory-secondary",
        default="none",
        help="Memory secondary option forwarded to benchmark run.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    outputs = run_arm_sweeper(
        catalog_path=Path(args.catalog),
        cases_path=Path(args.cases),
        repo=str(args.repo),
        root=Path(args.root),
        skills_dir=Path(args.skills_dir) if str(args.skills_dir).strip() else None,
        output_dir=Path(args.output_dir),
        python_exe=str(args.python_exe),
        warmup_runs=max(0, int(args.warmup_runs)),
        memory_primary=str(args.memory_primary),
        memory_secondary=str(args.memory_secondary),
    )
    print(json.dumps(outputs, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
