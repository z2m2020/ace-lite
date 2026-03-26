from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_paths(*, root: Path, output_dir: str | None = None) -> dict[str, Path]:
    return _default_paths_for_lane(root=root, lane="baseline", output_dir=output_dir)


def _default_paths_for_lane(
    *, root: Path, lane: str, output_dir: str | None = None
) -> dict[str, Path]:
    normalized_lane = str(lane or "baseline").strip().lower() or "baseline"
    resolved_output = (
        Path(output_dir).expanduser().resolve()
        if output_dir
        else (
            root
            / "artifacts"
            / "benchmark"
            / "academic_optimization"
            / normalized_lane
            / "latest"
        ).resolve()
    )
    return {
        "root": root.resolve(),
        "skills_dir": (root / "skills").resolve(),
        "cases": (root / "benchmark" / "cases" / "academic_optimization.yaml").resolve(),
        "index": (root / "context-map" / "index.json").resolve(),
        "output": resolved_output,
        "results": (resolved_output / "results.json").resolve(),
        "summary": (resolved_output / "summary.json").resolve(),
        "report": (resolved_output / "report.md").resolve(),
    }


def _candidate_cache_path(*, root: Path) -> Path:
    return (root / "context-map" / "index_candidates" / "cache.json").resolve()


def _clear_candidate_cache(*, root: Path) -> bool:
    cache_path = _candidate_cache_path(root=root)
    if not cache_path.exists() or not cache_path.is_file():
        return False
    cache_path.unlink()
    return True


def _cli_command(*, root: Path) -> list[str]:
    console_script = (root / ".venv" / "bin" / "ace-lite").resolve()
    if console_script.exists() and console_script.is_file():
        return [str(console_script)]
    return [
        sys.executable,
        "-c",
        "from ace_lite.cli import main; import sys; sys.exit(main())",
    ]


def _build_index_command(*, paths: dict[str, Path], languages: str) -> list[str]:
    return [
        *_cli_command(root=paths["root"]),
        "index",
        "--root",
        str(paths["root"]),
        "--languages",
        str(languages),
        "--output",
        str(paths["index"]),
    ]


def _build_benchmark_command(
    *,
    paths: dict[str, Path],
    repo: str,
    languages: str,
    warmup_runs: int,
    embedding_enabled: bool = False,
    embedding_provider: str = "hash",
    embedding_model: str | None = None,
    embedding_rerank_pool: int = 24,
) -> list[str]:
    cmd = [
        *_cli_command(root=paths["root"]),
        "benchmark",
        "run",
        "--cases",
        str(paths["cases"]),
        "--repo",
        str(repo),
        "--root",
        str(paths["root"]),
        "--skills-dir",
        str(paths["skills_dir"]),
        "--languages",
        str(languages),
        "--warmup-runs",
        str(max(0, int(warmup_runs))),
        "--memory-primary",
        "none",
        "--memory-secondary",
        "none",
        "--output",
        str(paths["output"]),
    ]
    if embedding_enabled:
        cmd.extend(
            [
                "--embedding-enabled",
                "--embedding-provider",
                str(embedding_provider),
                "--embedding-rerank-pool",
                str(max(1, int(embedding_rerank_pool))),
            ]
        )
        if embedding_model:
            cmd.extend(["--embedding-model", str(embedding_model)])
    return cmd


def _build_report_command(*, paths: dict[str, Path]) -> list[str]:
    cmd = [
        sys.executable,
        str((paths["root"] / "scripts" / "build_academic_optimization_report.py").resolve()),
        "--results",
        str(paths["results"]),
        "--cases",
        str(paths["cases"]),
        "--output-dir",
        str(paths["output"]),
    ]
    baseline_summary = paths.get("baseline_summary")
    if isinstance(baseline_summary, Path):
        cmd.extend(["--baseline-summary", str(baseline_summary)])
    if "query_expansion_enabled" in paths:
        cmd.extend(
            [
                "--query-expansion-enabled",
                "true" if bool(paths["query_expansion_enabled"]) else "false",
            ]
        )
    return cmd


def _resolve_existing_baseline_summary(*, root: Path) -> Path | None:
    candidates = (
        (
            root
            / "artifacts"
            / "benchmark"
            / "academic_optimization"
            / "baseline"
            / "latest"
            / "academic_summary.json"
        ).resolve(),
        (
            root
            / "artifacts"
            / "benchmark"
            / "academic_optimization"
            / "latest"
            / "academic_summary.json"
        ).resolve(),
    )
    for path in candidates:
        if path.exists() and path.is_file():
            return path
    return None


def _default_query_expansion_enabled(*, lane: str) -> bool:
    return str(lane or "").strip().lower() != "query_expansion_experiment"


def _benchmark_env(*, query_expansion_enabled: bool) -> dict[str, str]:
    env = dict(os.environ)
    env["ACE_LITE_QUERY_EXPANSION_ENABLED"] = "1" if query_expansion_enabled else "0"
    return env


def _run_command(*, cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
    completed = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        check=False,
        capture_output=False,
        text=True,
    )
    if completed.returncode != 0:
        raise SystemExit(int(completed.returncode))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run academic optimization benchmark lanes with optional baseline comparison."
    )
    parser.add_argument("--root", default=str(_repo_root()))
    parser.add_argument(
        "--lane",
        default="baseline",
        choices=("baseline", "query_expansion_experiment", "semantic_experiment"),
    )
    parser.add_argument("--repo", default="ace-lite")
    parser.add_argument("--languages", default="python,typescript,javascript,go,markdown")
    parser.add_argument("--warmup-runs", type=int, default=1)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--embedding-enabled", action="store_true")
    parser.add_argument("--embedding-provider", default="hash_cross")
    parser.add_argument("--embedding-model", default=None)
    parser.add_argument("--embedding-rerank-pool", type=int, default=24)
    parser.add_argument(
        "--query-expansion-enabled",
        default=None,
        choices=("true", "false"),
        help="Optional override for deterministic query expansion during benchmark execution.",
    )
    parser.add_argument(
        "--skip-index",
        action="store_true",
        help="Skip index refresh and reuse the existing context-map/index.json.",
    )
    args = parser.parse_args(argv)

    root = Path(str(args.root)).expanduser().resolve()
    paths = _default_paths_for_lane(
        root=root,
        lane=str(args.lane),
        output_dir=args.output_dir,
    )
    query_expansion_enabled = _default_query_expansion_enabled(lane=str(args.lane))
    if args.query_expansion_enabled is not None:
        query_expansion_enabled = str(args.query_expansion_enabled).strip().lower() == "true"
    paths["query_expansion_enabled"] = bool(query_expansion_enabled)
    if str(args.lane) != "baseline":
        baseline_summary = _resolve_existing_baseline_summary(root=root)
        if baseline_summary is not None:
            paths["baseline_summary"] = baseline_summary
    paths["output"].mkdir(parents=True, exist_ok=True)
    benchmark_env = _benchmark_env(query_expansion_enabled=bool(query_expansion_enabled))

    if not args.skip_index:
        _run_command(
            cmd=_build_index_command(paths=paths, languages=str(args.languages)),
            cwd=root,
            env=benchmark_env,
        )

    _clear_candidate_cache(root=root)

    _run_command(
        cmd=_build_benchmark_command(
            paths=paths,
            repo=str(args.repo),
            languages=str(args.languages),
            warmup_runs=int(args.warmup_runs),
            embedding_enabled=bool(args.embedding_enabled),
            embedding_provider=str(args.embedding_provider),
            embedding_model=(
                str(args.embedding_model).strip() if args.embedding_model else None
            ),
            embedding_rerank_pool=int(args.embedding_rerank_pool),
        ),
        cwd=root,
        env=benchmark_env,
    )
    _run_command(
        cmd=_build_report_command(paths=paths),
        cwd=root,
    )

    payload: dict[str, Any] = {
        "cases": str(paths["cases"]),
        "output_dir": str(paths["output"]),
        "results_json": str(paths["results"]),
        "summary_json": str(paths["summary"]),
        "report_md": str(paths["report"]),
        "academic_summary_json": str((paths["output"] / "academic_summary.json").resolve()),
        "academic_report_md": str((paths["output"] / "academic_report.md").resolve()),
        "index_json": str(paths["index"]),
        "index_refreshed": not bool(args.skip_index),
        "lane": str(args.lane),
        "query_expansion_enabled": bool(query_expansion_enabled),
        "embedding_enabled": bool(args.embedding_enabled),
        "embedding_provider": str(args.embedding_provider),
        "comparison_json": str((paths["output"] / "academic_comparison.json").resolve()),
        "comparison_md": str((paths["output"] / "academic_comparison.md").resolve()),
        "baseline_summary": str(paths["baseline_summary"]) if "baseline_summary" in paths else "",
    }
    print(json.dumps(payload, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
