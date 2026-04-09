from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _cli_command(*, root: Path) -> list[str]:
    candidates = (
        (root / ".venv" / "bin" / "ace-lite").resolve(),
        (root / ".venv" / "Scripts" / "ace-lite").resolve(),
        (root / ".venv" / "Scripts" / "ace-lite.exe").resolve(),
        (root / ".venv" / "Scripts" / "ace-lite.cmd").resolve(),
        (root / ".venv" / "Scripts" / "ace-lite.bat").resolve(),
    )
    for console_script in candidates:
        if console_script.exists() and console_script.is_file():
            return [str(console_script)]
    return [
        sys.executable,
        "-c",
        "from ace_lite.cli import main; import sys; sys.exit(main())",
    ]


def _default_paths(*, root: Path, output_dir: str | None = None) -> dict[str, Path]:
    resolved_output = (
        Path(output_dir).expanduser().resolve()
        if output_dir
        else (
            root
            / "artifacts"
            / "benchmark"
            / "workspace_summary"
            / "latest"
        ).resolve()
    )
    fixture_root = (resolved_output / "fixture").resolve()
    manifest_path = (fixture_root / "workspace.yaml").resolve()
    summary_index_path = (
        fixture_root / "context-map" / "workspace" / "summary-index.v1.json"
    ).resolve()
    return {
        "root": root.resolve(),
        "output": resolved_output,
        "fixture_root": fixture_root,
        "manifest": manifest_path,
        "summary_index": summary_index_path,
        "cases": (
            root / "benchmark" / "workspace" / "cases" / "summary_routing_cases.json"
        ).resolve(),
        "baseline": (
            root / "benchmark" / "workspace" / "baseline" / "summary_routing.json"
        ).resolve(),
        "without_summary": (resolved_output / "without_summary.json").resolve(),
        "with_summary": (resolved_output / "with_summary.json").resolve(),
        "comparison_json": (resolved_output / "comparison.json").resolve(),
        "comparison_md": (resolved_output / "comparison.md").resolve(),
    }


def _write_fixture_workspace(*, fixture_root: Path) -> Path:
    if fixture_root.exists():
        shutil.rmtree(fixture_root)
    repos_root = fixture_root / "repos"
    workspace_manifest = fixture_root / "workspace.yaml"
    repo_bodies = {
        "alpha-core": {
            "description": "backend services",
            "files": {
                "src/runtime_engine.py": (
                    "def serve_backend_request() -> str:\n"
                    "    return 'backend-services'\n"
                ),
            },
        },
        "mango-ui": {
            "description": "frontend client",
            "files": {
                "src/checkout_widget_renderer.py": (
                    "def render_checkout_widget() -> str:\n"
                    "    return 'checkout-widget-renderer'\n"
                ),
            },
        },
        "zulu-ops": {
            "description": "operations automation",
            "files": {
                "src/pager_alert_router.py": (
                    "def route_pager_alert() -> str:\n"
                    "    return 'pager-alert-router'\n"
                ),
            },
        },
    }

    for repo_name, repo_payload in repo_bodies.items():
        for relative_path, body in repo_payload["files"].items():
            target = repos_root / repo_name / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body, encoding="utf-8")

    manifest_lines = [
        "workspace:",
        "  name: Workspace Summary Benchmark",
        "repos:",
    ]
    for repo_name, repo_payload in repo_bodies.items():
        manifest_lines.extend(
            [
                f"  - name: {repo_name}",
                f"    path: repos/{repo_name}",
                f"    description: {repo_payload['description']}",
            ]
        )
    workspace_manifest.parent.mkdir(parents=True, exist_ok=True)
    workspace_manifest.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
    return workspace_manifest


def _run_json_command(*, cmd: list[str], cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(
        cmd,
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)
    payload = json.loads(completed.stdout)
    return payload if isinstance(payload, dict) else {}


def _build_summarize_command(*, paths: dict[str, Path]) -> list[str]:
    return [
        *_cli_command(root=paths["root"]),
        "workspace",
        "summarize",
        "--manifest",
        str(paths["manifest"]),
        "--languages",
        "python",
    ]


def _build_benchmark_command(
    *,
    paths: dict[str, Path],
    summary_routing: bool,
) -> list[str]:
    cmd = [
        *_cli_command(root=paths["root"]),
        "workspace",
        "benchmark",
        "--manifest",
        str(paths["manifest"]),
        "--cases-json",
        str(paths["cases"]),
        "--top-k-repos",
        "1",
    ]
    cmd.append("--summary-routing" if summary_routing else "--no-summary-routing")
    if summary_routing:
        cmd.extend(
            [
                "--baseline-json",
                str(paths["baseline"]),
            ]
        )
    return cmd


def _build_comparison(
    *,
    without_summary: dict[str, Any],
    with_summary: dict[str, Any],
) -> dict[str, Any]:
    without_metrics = (
        without_summary.get("metrics") if isinstance(without_summary.get("metrics"), dict) else {}
    )
    with_metrics = (
        with_summary.get("metrics") if isinstance(with_summary.get("metrics"), dict) else {}
    )
    tracked_metrics = (
        "hit_at_k",
        "mrr",
        "avg_latency_ms",
        "summary_match_case_rate",
        "summary_promoted_case_rate",
    )
    metric_delta: dict[str, dict[str, float]] = {}
    for metric in tracked_metrics:
        without_value = float(without_metrics.get(metric, 0.0) or 0.0)
        with_value = float(with_metrics.get(metric, 0.0) or 0.0)
        metric_delta[metric] = {
            "without_summary": without_value,
            "with_summary": with_value,
            "delta": with_value - without_value,
        }

    without_cases = {
        str(item.get("id") or "").strip(): item
        for item in without_summary.get("cases", [])
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }
    with_cases = {
        str(item.get("id") or "").strip(): item
        for item in with_summary.get("cases", [])
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }
    case_comparison: list[dict[str, Any]] = []
    for case_id in sorted(set(without_cases) | set(with_cases)):
        before = without_cases.get(case_id, {})
        after = with_cases.get(case_id, {})
        after_summary_routing = (
            after.get("summary_routing") if isinstance(after.get("summary_routing"), dict) else {}
        )
        case_comparison.append(
            {
                "id": case_id,
                "query": str(after.get("query") or before.get("query") or ""),
                "expected_repos": list(after.get("expected_repos") or before.get("expected_repos") or []),
                "without_summary_predicted_repos": list(before.get("predicted_repos") or []),
                "with_summary_predicted_repos": list(after.get("predicted_repos") or []),
                "without_summary_hit": bool(before.get("hit", False)),
                "with_summary_hit": bool(after.get("hit", False)),
                "expected_repo_promoted": bool(
                    after_summary_routing.get("promoted_expected_repo", False)
                ),
                "matched_summary_repos": list(
                    after_summary_routing.get("matched_repos", [])
                    if isinstance(after_summary_routing.get("matched_repos"), list)
                    else []
                ),
            }
        )

    baseline_check = (
        with_summary.get("baseline_check")
        if isinstance(with_summary.get("baseline_check"), dict)
        else {}
    )
    return {
        "metric_delta": metric_delta,
        "case_comparison": case_comparison,
        "baseline_check": baseline_check,
    }


def _build_comparison_markdown(*, comparison: dict[str, Any]) -> str:
    lines = [
        "# Workspace Summary Benchmark Comparison",
        "",
        "## Metrics",
        "",
        "| Metric | Without Summary | With Summary | Delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    metric_delta = comparison.get("metric_delta", {})
    for metric in (
        "hit_at_k",
        "mrr",
        "avg_latency_ms",
        "summary_match_case_rate",
        "summary_promoted_case_rate",
    ):
        item = metric_delta.get(metric, {}) if isinstance(metric_delta, dict) else {}
        lines.append(
            "| {metric} | {without_summary:.6f} | {with_summary:.6f} | {delta:+.6f} |".format(
                metric=metric,
                without_summary=float(item.get("without_summary", 0.0) or 0.0),
                with_summary=float(item.get("with_summary", 0.0) or 0.0),
                delta=float(item.get("delta", 0.0) or 0.0),
            )
        )

    lines.extend(
        [
            "",
            "## Cases",
            "",
            "| Case | Expected | Without Summary | With Summary | Promoted | Summary Matches |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in comparison.get("case_comparison", []):
        lines.append(
            "| {case_id} | {expected} | {before} | {after} | {promoted} | {matches} |".format(
                case_id=str(item.get("id") or ""),
                expected=", ".join(item.get("expected_repos", [])) or "(none)",
                before=", ".join(item.get("without_summary_predicted_repos", [])) or "(none)",
                after=", ".join(item.get("with_summary_predicted_repos", [])) or "(none)",
                promoted="yes" if bool(item.get("expected_repo_promoted", False)) else "no",
                matches=", ".join(item.get("matched_summary_repos", [])) or "(none)",
            )
        )

    baseline_check = comparison.get("baseline_check", {})
    if isinstance(baseline_check, dict) and baseline_check:
        lines.extend(
            [
                "",
                "## Baseline Check",
                "",
                "- ok: {ok}".format(ok=bool(baseline_check.get("ok", False))),
                "- checked_metrics: {metrics}".format(
                    metrics=", ".join(baseline_check.get("checked_metrics", [])) or "(none)"
                ),
            ]
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the workspace summary routing benchmark on a synthetic workspace fixture."
    )
    parser.add_argument("--root", default=str(_repo_root()))
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args(argv)

    root = Path(str(args.root)).expanduser().resolve()
    paths = _default_paths(root=root, output_dir=args.output_dir)
    paths["output"].mkdir(parents=True, exist_ok=True)
    _write_fixture_workspace(fixture_root=paths["fixture_root"])

    summarize_payload = _run_json_command(
        cmd=_build_summarize_command(paths=paths),
        cwd=root,
    )
    without_summary_payload = _run_json_command(
        cmd=_build_benchmark_command(paths=paths, summary_routing=False),
        cwd=root,
    )
    with_summary_payload = _run_json_command(
        cmd=_build_benchmark_command(paths=paths, summary_routing=True),
        cwd=root,
    )

    comparison = _build_comparison(
        without_summary=without_summary_payload,
        with_summary=with_summary_payload,
    )
    comparison_markdown = _build_comparison_markdown(comparison=comparison)

    paths["without_summary"].write_text(
        json.dumps(without_summary_payload, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    paths["with_summary"].write_text(
        json.dumps(with_summary_payload, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    paths["comparison_json"].write_text(
        json.dumps(comparison, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    paths["comparison_md"].write_text(comparison_markdown, encoding="utf-8")

    print(
        json.dumps(
            {
                "manifest": str(paths["manifest"]),
                "summary_index": str(paths["summary_index"]),
                "cases_json": str(paths["cases"]),
                "baseline_json": str(paths["baseline"]),
                "summary_summarize_payload": summarize_payload,
                "without_summary_json": str(paths["without_summary"]),
                "with_summary_json": str(paths["with_summary"]),
                "comparison_json": str(paths["comparison_json"]),
                "comparison_md": str(paths["comparison_md"]),
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
