from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


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


def _load_matrix_module(*, scripts_dir: Path) -> ModuleType:
    module_name = "script_run_benchmark_matrix_backfill"
    module_path = scripts_dir / "run_benchmark_matrix.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _count_repo_summaries(*, repos: list[dict[str, Any]], key: str) -> int:
    count = 0
    for repo in repos:
        value = repo.get(key)
        if isinstance(value, dict) and value:
            count += 1
    return count


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except Exception:
        return 0


def _resolve_artifact_path(*, matrix_summary_path: Path, value: str) -> Path:
    candidate = Path(str(value).strip())
    if candidate.is_absolute():
        return candidate
    return (matrix_summary_path.parent / candidate).resolve()


def _resolve_repo_output_dir(*, matrix_summary_path: Path, repo: dict[str, Any]) -> Path | None:
    for key in ("summary_json", "results_json", "report_md", "index_json"):
        raw = str(repo.get(key) or "").strip()
        if not raw:
            continue
        return _resolve_artifact_path(matrix_summary_path=matrix_summary_path, value=raw).parent
    return None


def _hydrate_summary(
    *,
    matrix_summary_path: Path,
    summary: dict[str, Any],
    module: ModuleType,
) -> dict[str, Any]:
    repos_raw = summary.get("repos")
    repos = repos_raw if isinstance(repos_raw, list) else []
    hydrated_repos: list[dict[str, Any]] = []

    for item in repos:
        if not isinstance(item, dict):
            continue
        repo = dict(item)
        repo_output_dir = _resolve_repo_output_dir(
            matrix_summary_path=matrix_summary_path,
            repo=repo,
        )
        index_json_raw = str(repo.get("index_json") or "").strip()
        index_path = (
            _resolve_artifact_path(matrix_summary_path=matrix_summary_path, value=index_json_raw)
            if index_json_raw
            else (
                (repo_output_dir / "index.json")
                if isinstance(repo_output_dir, Path)
                else None
            )
        )

        index_file_count = _safe_int(repo.get("index_file_count"))
        if index_file_count <= 0 and isinstance(index_path, Path):
            index_file_count = _safe_int(module._load_index_file_count(index_path=index_path))
        if isinstance(index_path, Path) and index_path.exists():
            repo["index_json"] = str(index_path)
        if index_file_count > 0:
            repo["index_file_count"] = index_file_count

        workload_bucket = str(repo.get("workload_bucket") or "").strip().lower()
        if not workload_bucket:
            retrieval_policy = (
                str(repo.get("retrieval_policy") or "auto").strip().lower() or "auto"
            )
            workload_bucket = str(
                module._resolve_workload_bucket(
                    repo_spec=repo,
                    file_count=index_file_count,
                    retrieval_policy=retrieval_policy,
                )
            )
            if workload_bucket:
                repo["workload_bucket"] = workload_bucket

        hydrated_repos.append(repo)

    hydrated_summary = dict(summary)
    hydrated_summary["repos"] = hydrated_repos
    hydrated_summary["repo_count"] = int(summary.get("repo_count", len(hydrated_repos)) or len(hydrated_repos))
    return hydrated_summary


def _validate_full_fidelity(summary: dict[str, Any]) -> tuple[bool, str]:
    stage_latency_summary_raw = summary.get("stage_latency_summary")
    stage_latency_summary = (
        stage_latency_summary_raw if isinstance(stage_latency_summary_raw, dict) else {}
    )
    slo_budget_summary_raw = summary.get("slo_budget_summary")
    slo_budget_summary = (
        slo_budget_summary_raw if isinstance(slo_budget_summary_raw, dict) else {}
    )
    repos_raw = summary.get("repos")
    repos = repos_raw if isinstance(repos_raw, list) else []
    repo_rows = [item for item in repos if isinstance(item, dict)]

    if not stage_latency_summary:
        return False, "matrix summary is missing top-level stage_latency_summary"
    if not slo_budget_summary:
        return False, "matrix summary is missing top-level slo_budget_summary"
    if not repo_rows:
        return False, "matrix summary is missing repo-level benchmark rows"

    stage_repo_count = _count_repo_summaries(repos=repo_rows, key="stage_latency_summary")
    slo_repo_count = _count_repo_summaries(repos=repo_rows, key="slo_budget_summary")
    if stage_repo_count == 0:
        return False, "matrix summary has no repo-level stage latency summaries"
    if slo_repo_count == 0:
        return False, "matrix summary has no repo-level SLO budget summaries"

    return True, ""


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize latency_slo_summary artifacts from an existing "
            "benchmark matrix_summary.json."
        )
    )
    parser.add_argument(
        "--matrix-summary",
        required=True,
        help="Path to an existing matrix_summary.json artifact.",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Directory to write latency_slo_summary.{json,md}; defaults to the matrix summary directory.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing latency_slo_summary outputs if they already exist.",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    scripts_dir = Path(__file__).resolve().parent
    matrix_summary_path = _resolve_path(root=project_root, value=str(args.matrix_summary))
    output_dir = (
        _resolve_path(root=project_root, value=str(args.output_dir))
        if str(args.output_dir).strip()
        else matrix_summary_path.parent
    )

    summary = _load_json(matrix_summary_path)
    if not summary:
        print(
            f"[backfill-latency-slo] failed to load matrix summary: {matrix_summary_path}",
            file=sys.stderr,
        )
        return 2

    valid, reason = _validate_full_fidelity(summary)
    if not valid:
        print(f"[backfill-latency-slo] {reason}", file=sys.stderr)
        return 2

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "latency_slo_summary.json"
    md_path = output_dir / "latency_slo_summary.md"
    if not args.force and (json_path.exists() or md_path.exists()):
        print(
            "[backfill-latency-slo] output exists; pass --force to overwrite",
            file=sys.stderr,
        )
        return 2

    module = _load_matrix_module(scripts_dir=scripts_dir)
    hydrated_summary = _hydrate_summary(
        matrix_summary_path=matrix_summary_path,
        summary=summary,
        module=module,
    )
    payload = module._build_latency_slo_summary(summary=hydrated_summary)
    markdown = module._build_latency_slo_summary_markdown(payload=payload)

    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(markdown, encoding="utf-8")

    print(f"[backfill-latency-slo] summary json: {json_path}")
    print(f"[backfill-latency-slo] summary md:   {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
