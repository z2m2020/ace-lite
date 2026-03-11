from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


from ace_lite.benchmark.runner import load_cases  # noqa: E402
from ace_lite.benchmark.scoring import aggregate_metrics, evaluate_case_result  # noqa: E402
from ace_lite.config_pack import CONFIG_PACK_SCHEMA_VERSION  # noqa: E402
from ace_lite.memory import NullMemoryProvider  # noqa: E402
from ace_lite.orchestrator import AceOrchestrator  # noqa: E402
from ace_lite.orchestrator_config import OrchestratorConfig  # noqa: E402


@dataclass(frozen=True)
class IterationParams:
    top_k_files: int
    min_candidate_score: int
    candidate_relative_threshold: float
    candidate_ranker: str
    hybrid_re2_fusion_mode: str
    hybrid_re2_rrf_k: int
    repomap_signal_weights: dict[str, float] | None
    retrieval_policy: str = "auto"


@dataclass
class IterationResult:
    iteration: int
    mode: str
    params: IterationParams
    metrics: dict[str, float]
    objective: float
    candidate_count_mean: float
    missed_cases: list[str]


def _parse_languages(value: str) -> list[str]:
    return [item.strip().lower() for item in (value or "").split(",") if item.strip()]


def _parse_candidate_rankers(value: str) -> list[str]:
    allowed = {"heuristic", "bm25_lite", "hybrid_re2", "rrf_hybrid"}
    parsed: list[str] = []
    for item in (value or "").split(","):
        normalized = item.strip().lower()
        if not normalized or normalized not in allowed or normalized in parsed:
            continue
        parsed.append(normalized)
    if parsed:
        return parsed
    return ["heuristic", "bm25_lite", "hybrid_re2", "rrf_hybrid"]


def _parse_hybrid_fusion_modes(value: str) -> list[str]:
    allowed = {"linear", "rrf"}
    parsed: list[str] = []
    for item in (value or "").split(","):
        normalized = item.strip().lower()
        if not normalized or normalized not in allowed or normalized in parsed:
            continue
        parsed.append(normalized)
    if parsed:
        return parsed
    return ["linear", "rrf"]


def _parse_hybrid_rrf_ks(value: str) -> list[int]:
    parsed: list[int] = []
    for item in (value or "").split(","):
        normalized = str(item).strip()
        if not normalized:
            continue
        try:
            parsed_value = max(1, int(normalized))
        except ValueError:
            continue
        if parsed_value in parsed:
            continue
        parsed.append(parsed_value)
    if parsed:
        return parsed
    return [30, 45, 60, 75, 90]


def _parse_retrieval_policies(value: str) -> list[str]:
    allowed = {"auto", "general", "bugfix_test", "feature", "refactor"}
    parsed: list[str] = []
    for item in (value or "").split(","):
        normalized = item.strip().lower()
        if not normalized or normalized not in allowed or normalized in parsed:
            continue
        parsed.append(normalized)
    if parsed:
        return parsed
    return ["auto", "bugfix_test", "feature", "refactor", "general"]


DEFAULT_REPOMAP_SIGNAL_WEIGHT_SETS: list[dict[str, float] | None] = [
    None,
    {"base": 0.75, "graph": 0.20, "import_depth": 0.05},
    {"base": 0.70, "graph": 0.25, "import_depth": 0.05},
    {"base": 0.60, "graph": 0.30, "import_depth": 0.10},
]


def _parse_repomap_signal_weight_sets(value: str) -> list[dict[str, float] | None]:
    raw = str(value or "").strip()
    if not raw:
        return [dict(item) if isinstance(item, dict) else None for item in DEFAULT_REPOMAP_SIGNAL_WEIGHT_SETS]

    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise ValueError("repomap signal weight sets must be a JSON list")

    resolved: list[dict[str, float] | None] = []
    for item in parsed:
        if item is None:
            resolved.append(None)
            continue
        if not isinstance(item, dict):
            continue

        weights: dict[str, float] = {}
        for key, weight in item.items():
            key_name = str(key).strip().lower()
            if not key_name:
                continue
            if not isinstance(weight, (int, float)):
                continue
            weights[key_name] = float(weight)

        if weights:
            resolved.append(weights)

    if not resolved:
        return [dict(item) if isinstance(item, dict) else None for item in DEFAULT_REPOMAP_SIGNAL_WEIGHT_SETS]
    return resolved


def _objective(metrics: dict[str, float], *, recall_floor: float = 0.95) -> float:
    precision = float(metrics.get("precision_at_k", 0.0))
    recall = float(metrics.get("recall_at_k", 0.0))
    penalty = max(0.0, recall_floor - recall) * 5.0
    return precision - penalty


def _choice_near(values: list[Any], current: Any, *, rng: random.Random, radius: int = 1) -> Any:
    idx = values.index(current) if current in values else 0
    lo = max(0, idx - radius)
    hi = min(len(values) - 1, idx + radius)
    return values[rng.randint(lo, hi)]


def _pick_next_params(
    *,
    iteration: int,
    rng: random.Random,
    best_params: IterationParams,
    last_metrics: dict[str, float] | None,
    recall_floor: float,
    explore_rate: float,
    candidate_ranker_choices: list[str],
    repomap_signal_weight_choices: list[dict[str, float] | None],
    retrieval_policy_choices: list[str],
    hybrid_fusion_mode_choices: list[str],
    hybrid_rrf_k_choices: list[int],
) -> tuple[str, IterationParams]:
    top_k_choices = [2, 3, 4, 5, 6, 8]
    min_score_choices = [0, 1, 2, 3, 4]
    relative_threshold_choices = [0.0, 0.2, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6]

    ranker_choices = candidate_ranker_choices or ["heuristic"]
    signal_weight_choices = repomap_signal_weight_choices or [None]
    policy_choices = retrieval_policy_choices or ["auto"]
    fusion_mode_choices = hybrid_fusion_mode_choices or ["linear"]
    rrf_k_choices = hybrid_rrf_k_choices or [60]

    if iteration == 1:
        return "baseline", IterationParams(
            top_k_files=8,
            min_candidate_score=2,
            candidate_relative_threshold=0.0,
            candidate_ranker="heuristic",
            hybrid_re2_fusion_mode="linear",
            hybrid_re2_rrf_k=60,
            repomap_signal_weights=None,
            retrieval_policy="auto",
        )

    if iteration % 10 == 0:
        return "restart", IterationParams(
            top_k_files=rng.choice(top_k_choices),
            min_candidate_score=rng.choice(min_score_choices),
            candidate_relative_threshold=rng.choice(relative_threshold_choices),
            candidate_ranker=rng.choice(ranker_choices),
            hybrid_re2_fusion_mode=rng.choice(fusion_mode_choices),
            hybrid_re2_rrf_k=rng.choice(rrf_k_choices),
            repomap_signal_weights=rng.choice(signal_weight_choices),
            retrieval_policy=rng.choice(policy_choices),
        )

    if rng.random() < explore_rate:
        return "explore", IterationParams(
            top_k_files=rng.choice(top_k_choices),
            min_candidate_score=rng.choice(min_score_choices),
            candidate_relative_threshold=rng.choice(relative_threshold_choices),
            candidate_ranker=rng.choice(ranker_choices),
            hybrid_re2_fusion_mode=rng.choice(fusion_mode_choices),
            hybrid_re2_rrf_k=rng.choice(rrf_k_choices),
            repomap_signal_weights=rng.choice(signal_weight_choices),
            retrieval_policy=rng.choice(policy_choices),
        )

    mode = "exploit"
    base = best_params

    if last_metrics is not None and float(last_metrics.get("recall_at_k", 0.0)) < recall_floor:
        mode = "relax"
        return mode, IterationParams(
            top_k_files=_choice_near(top_k_choices, base.top_k_files, rng=rng, radius=2),
            min_candidate_score=_choice_near(min_score_choices, base.min_candidate_score, rng=rng, radius=2),
            candidate_relative_threshold=_choice_near(
                relative_threshold_choices,
                base.candidate_relative_threshold,
                rng=rng,
                radius=2,
            ),
            candidate_ranker=_choice_near(ranker_choices, base.candidate_ranker, rng=rng, radius=1),
            hybrid_re2_fusion_mode=_choice_near(
                fusion_mode_choices,
                base.hybrid_re2_fusion_mode,
                rng=rng,
                radius=1,
            ),
            hybrid_re2_rrf_k=_choice_near(
                rrf_k_choices,
                base.hybrid_re2_rrf_k,
                rng=rng,
                radius=1,
            ),
            repomap_signal_weights=_choice_near(
                signal_weight_choices,
                base.repomap_signal_weights,
                rng=rng,
                radius=1,
            ),
            retrieval_policy=_choice_near(
                policy_choices,
                base.retrieval_policy,
                rng=rng,
                radius=1,
            ),
        )

    return mode, IterationParams(
        top_k_files=_choice_near(top_k_choices, base.top_k_files, rng=rng, radius=1),
        min_candidate_score=_choice_near(min_score_choices, base.min_candidate_score, rng=rng, radius=1),
        candidate_relative_threshold=_choice_near(
            relative_threshold_choices,
            base.candidate_relative_threshold,
            rng=rng,
            radius=1,
        ),
        candidate_ranker=_choice_near(ranker_choices, base.candidate_ranker, rng=rng, radius=1),
        hybrid_re2_fusion_mode=_choice_near(
            fusion_mode_choices,
            base.hybrid_re2_fusion_mode,
            rng=rng,
            radius=1,
        ),
        hybrid_re2_rrf_k=_choice_near(
            rrf_k_choices,
            base.hybrid_re2_rrf_k,
            rng=rng,
            radius=1,
        ),
        repomap_signal_weights=_choice_near(
            signal_weight_choices,
            base.repomap_signal_weights,
            rng=rng,
            radius=1,
        ),
        retrieval_policy=_choice_near(
            policy_choices,
            base.retrieval_policy,
            rng=rng,
            radius=1,
        ),
    )


def _run_iteration(

    *,
    params: IterationParams,
    cases: list[dict[str, Any]],
    repo: str,
    root: str,
    skills_dir: str,
    languages: list[str],
    index_cache_path: str,
    repomap_enabled: bool,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    config = OrchestratorConfig(
        skills={
            "dir": skills_dir,
        },
        retrieval={
            "top_k_files": params.top_k_files,
            "min_candidate_score": params.min_candidate_score,
            "candidate_relative_threshold": params.candidate_relative_threshold,
            "candidate_ranker": params.candidate_ranker,
            "hybrid_re2_fusion_mode": params.hybrid_re2_fusion_mode,
            "hybrid_re2_rrf_k": max(1, int(params.hybrid_re2_rrf_k)),
            "retrieval_policy": str(params.retrieval_policy),
        },
        index={
            "languages": languages,
            "cache_path": index_cache_path,
            "incremental": False,
        },
        repomap={
            "enabled": repomap_enabled,
            "signal_weights": dict(params.repomap_signal_weights)
            if isinstance(params.repomap_signal_weights, dict)
            else None,
        },
        lsp={
            "enabled": False,
        },
        plugins={
            "enabled": False,
        },
    )
    orchestrator = AceOrchestrator(memory_provider=NullMemoryProvider(), config=config)

    case_results: list[dict[str, Any]] = []
    for case in cases:
        query = str(case.get("query", "")).strip()
        if not query:
            continue

        started = perf_counter()
        payload = orchestrator.plan(query=query, repo=repo, root=root)
        latency_ms = (perf_counter() - started) * 1000.0

        case_result = evaluate_case_result(case=case, plan_payload=payload, latency_ms=latency_ms)
        case_results.append(case_result)

    metrics = aggregate_metrics(case_results)
    return metrics, case_results


def _build_policy_summary(iteration_results: list[IterationResult]) -> list[dict[str, float | int | str]]:
    policy_groups: dict[str, list[IterationResult]] = {}
    for item in iteration_results:
        policy_groups.setdefault(item.params.retrieval_policy, []).append(item)

    summary_rows: list[dict[str, float | int | str]] = []
    for policy in sorted(policy_groups):
        rows = policy_groups[policy]
        precision_values = [float(entry.metrics.get("precision_at_k", 0.0)) for entry in rows]
        recall_values = [float(entry.metrics.get("recall_at_k", 0.0)) for entry in rows]
        noise_values = [float(entry.metrics.get("noise_rate", 0.0)) for entry in rows]
        objective_values = [float(entry.objective) for entry in rows]

        summary_rows.append(
            {
                "retrieval_policy": policy,
                "runs": len(rows),
                "mean_objective": float(mean(objective_values)) if objective_values else 0.0,
                "best_objective": float(max(objective_values)) if objective_values else 0.0,
                "mean_recall_at_k": float(mean(recall_values)) if recall_values else 0.0,
                "mean_precision_at_k": float(mean(precision_values)) if precision_values else 0.0,
                "mean_noise_rate": float(mean(noise_values)) if noise_values else 0.0,
            }
        )

    return summary_rows


def _write_markdown_report(
    *,
    output_path: Path,
    generated_at: str,
    repo: str,
    root: str,
    cases_path: str,
    recall_floor: float,
    iteration_results: list[IterationResult],
    best_result: IterationResult,
) -> None:
    lines: list[str] = []
    lines.append("# Ralph-Wiggum Iteration Log")
    lines.append("")
    lines.append(f"- Generated: {generated_at}")
    lines.append(f"- Repo: {repo}")
    lines.append(f"- Root: {root}")
    lines.append(f"- Cases: {cases_path}")
    lines.append(f"- Iterations: {len(iteration_results)}")
    lines.append(f"- Objective: precision_at_k - 5 * max(0, {recall_floor:.2f} - recall_at_k)")
    lines.append("")

    lines.append("## Best")
    lines.append("")
    best_metrics = best_result.metrics
    lines.append(
        "| Param | Value |\n| --- | ---: |\n"
        f"| top_k_files | {best_result.params.top_k_files} |\n"
        f"| min_candidate_score | {best_result.params.min_candidate_score} |\n"
        f"| candidate_relative_threshold | {best_result.params.candidate_relative_threshold:.2f} |\n"
        f"| candidate_ranker | {best_result.params.candidate_ranker} |\n"
        f"| hybrid_re2_fusion_mode | {best_result.params.hybrid_re2_fusion_mode} |\n"
        f"| hybrid_re2_rrf_k | {int(best_result.params.hybrid_re2_rrf_k)} |\n"
        f"| retrieval_policy | {best_result.params.retrieval_policy} |\n"
        f"| repomap_signal_weights | {json.dumps(best_result.params.repomap_signal_weights, sort_keys=True) if best_result.params.repomap_signal_weights else 'none'} |\n"
    )
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | ---: |")
    for key in ("recall_at_k", "precision_at_k", "noise_rate", "dependency_recall", "latency_p95_ms"):
        value = float(best_metrics.get(key, 0.0))
        if key == "latency_p95_ms":
            lines.append(f"| {key} | {value:.2f} |")
        else:
            lines.append(f"| {key} | {value:.4f} |")
    lines.append("")

    lines.append("## Policy Summary")
    lines.append("")
    lines.append("| Policy | Runs | Mean Obj | Best Obj | Mean Recall | Mean Precision | Mean Noise |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for policy_row in _build_policy_summary(iteration_results):
        lines.append(
            "| {policy} | {runs} | {mean_obj:.4f} | {best_obj:.4f} | {recall:.4f} | {precision:.4f} | {noise:.4f} |".format(
                policy=str(policy_row.get("retrieval_policy", "auto")),
                runs=int(policy_row.get("runs", 0)),
                mean_obj=float(policy_row.get("mean_objective", 0.0)),
                best_obj=float(policy_row.get("best_objective", 0.0)),
                recall=float(policy_row.get("mean_recall_at_k", 0.0)),
                precision=float(policy_row.get("mean_precision_at_k", 0.0)),
                noise=float(policy_row.get("mean_noise_rate", 0.0)),
            )
        )
    lines.append("")

    lines.append("## Iterations")
    lines.append("")
    lines.append(
        "| Iter | Mode | ranker | fusion | rrf_k | policy | weights | top_k | min_score | rel_th | recall | precision | noise | latency_p95_ms | obj | missed |"
    )
    lines.append("| ---: | --- | --- | --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for item in iteration_results:
        metrics = item.metrics
        lines.append(
            "| {iter} | {mode} | {ranker} | {fusion} | {rrf_k} | {policy} | {weights} | {top_k} | {min_score} | {rel:.2f} | {recall:.4f} | {precision:.4f} | {noise:.4f} | {latency:.2f} | {obj:.4f} | {missed} |".format(
                iter=item.iteration,
                mode=item.mode,
                ranker=item.params.candidate_ranker,
                fusion=item.params.hybrid_re2_fusion_mode,
                rrf_k=int(item.params.hybrid_re2_rrf_k),
                policy=item.params.retrieval_policy,
                weights=(json.dumps(item.params.repomap_signal_weights, sort_keys=True) if item.params.repomap_signal_weights else "none"),
                top_k=item.params.top_k_files,
                min_score=item.params.min_candidate_score,
                rel=item.params.candidate_relative_threshold,
                recall=float(metrics.get("recall_at_k", 0.0)),
                precision=float(metrics.get("precision_at_k", 0.0)),
                noise=float(metrics.get("noise_rate", 0.0)),
                latency=float(metrics.get("latency_p95_ms", 0.0)),
                obj=item.objective,
                missed=len(item.missed_cases),
            )
        )
    lines.append("")

    lines.append("## Misses")
    lines.append("")
    misses = [item for item in iteration_results if item.missed_cases]
    if not misses:
        lines.append("(none)")
    else:
        for item in misses:
            lines.append(f"### Iteration {item.iteration}")
            lines.append(f"- params: {asdict(item.params)}")
            lines.append(f"- missed_cases: {', '.join(item.missed_cases)}")
            lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a 50-iteration benchmark tuning loop (ralph-wiggum style).")
    parser.add_argument("--cases", default="benchmark/cases/ace_lite_engine.yaml", help="Benchmark cases path.")
    parser.add_argument("--repo", default="ace-lite-engine", help="Repository identifier.")
    parser.add_argument("--root", default=".", help="Repository root directory.")
    parser.add_argument("--skills-dir", default="skills", help="Skills directory.")
    parser.add_argument("--languages", default="python,typescript,javascript,go", help="Comma-separated language list.")
    parser.add_argument("--index-cache-path", default="context-map/index.json", help="Index cache path.")
    parser.add_argument("--iterations", type=int, default=50, help="Number of iterations to run.")
    parser.add_argument("--seed", type=int, default=20260209, help="Random seed.")
    parser.add_argument("--recall-floor", type=float, default=0.95, help="Recall floor used in objective penalty.")
    parser.add_argument("--explore-rate", type=float, default=0.3, help="Chance of random exploration each step.")
    parser.add_argument(
        "--candidate-rankers",
        default="heuristic,bm25_lite,hybrid_re2,rrf_hybrid",
        help="Comma-separated candidate ranker search space.",
    )
    parser.add_argument(
        "--hybrid-fusion-modes",
        default="linear,rrf",
        help="Comma-separated hybrid fusion mode search space.",
    )
    parser.add_argument(
        "--hybrid-rrf-ks",
        default="30,45,60,75,90",
        help="Comma-separated hybrid RRF k search space.",
    )
    parser.add_argument(
        "--repomap-signal-weight-sets",
        default="",
        help="Optional JSON list of repomap signal weight maps (include null for default).",
    )
    parser.add_argument(
        "--retrieval-policies",
        default="auto,bugfix_test,feature,refactor,general",
        help="Comma-separated retrieval policy search space.",
    )
    parser.add_argument("--repomap/--no-repomap", dest="repomap_enabled", default=True, help="Toggle repomap stage.")
    parser.add_argument(
        "--output-dir",
        default="artifacts/tuning/latest",
        help="Output directory for iteration artifacts.",
    )
    parser.add_argument(
        "--markdown-out",
        default="artifacts/tuning/latest/ralph_wiggum_iterations.md",
        help="Markdown output path for the iteration log.",
    )
    args = parser.parse_args()

    cases_path = str(args.cases)
    cases = load_cases(cases_path)
    if not cases:
        raise SystemExit(f"No cases loaded from: {cases_path}")

    repo = str(args.repo)
    root = str(Path(args.root).resolve())
    skills_dir = str(Path(args.skills_dir).resolve())
    languages = _parse_languages(args.languages)
    candidate_ranker_choices = _parse_candidate_rankers(args.candidate_rankers)
    hybrid_fusion_mode_choices = _parse_hybrid_fusion_modes(args.hybrid_fusion_modes)
    hybrid_rrf_k_choices = _parse_hybrid_rrf_ks(args.hybrid_rrf_ks)
    retrieval_policy_choices = _parse_retrieval_policies(args.retrieval_policies)
    try:
        repomap_signal_weight_choices = _parse_repomap_signal_weight_sets(args.repomap_signal_weight_sets)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    index_cache_path = str(args.index_cache_path)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(int(args.seed))
    recall_floor = float(args.recall_floor)
    explore_rate = float(args.explore_rate)
    generated_at = datetime.now(timezone.utc).isoformat()

    best_params = IterationParams(
        top_k_files=8,
        min_candidate_score=2,
        candidate_relative_threshold=0.0,
        candidate_ranker="heuristic",
        hybrid_re2_fusion_mode="linear",
        hybrid_re2_rrf_k=60,
        repomap_signal_weights=None,
        retrieval_policy="auto",
    )
    best_result: IterationResult | None = None

    last_metrics: dict[str, float] | None = None
    iteration_results: list[IterationResult] = []

    for iteration in range(1, max(1, int(args.iterations)) + 1):
        mode, params = _pick_next_params(
            iteration=iteration,
            rng=rng,
            best_params=best_params,
            last_metrics=last_metrics,
            recall_floor=recall_floor,
            explore_rate=explore_rate,
            candidate_ranker_choices=candidate_ranker_choices,
            repomap_signal_weight_choices=repomap_signal_weight_choices,
            retrieval_policy_choices=retrieval_policy_choices,
            hybrid_fusion_mode_choices=hybrid_fusion_mode_choices,
            hybrid_rrf_k_choices=hybrid_rrf_k_choices,
        )

        metrics, case_results = _run_iteration(
            params=params,
            cases=cases,
            repo=repo,
            root=root,
            skills_dir=skills_dir,
            languages=languages,
            index_cache_path=index_cache_path,
            repomap_enabled=bool(args.repomap_enabled),
        )

        objective = _objective(metrics, recall_floor=recall_floor)
        candidate_counts = [len(item.get("candidate_paths") or []) for item in case_results]
        candidate_count_mean = mean(candidate_counts) if candidate_counts else 0.0
        missed_cases = [item.get("case_id", "unknown") for item in case_results if float(item.get("recall_hit", 0.0)) <= 0.0]

        result = IterationResult(
            iteration=iteration,
            mode=mode,
            params=params,
            metrics={str(k): float(v) for k, v in metrics.items()},
            objective=float(objective),
            candidate_count_mean=float(candidate_count_mean),
            missed_cases=[str(item) for item in missed_cases],
        )
        iteration_results.append(result)
        last_metrics = metrics

        if best_result is None or result.objective > best_result.objective:
            best_params = params
            best_result = result

        iteration_path = output_dir / f"iter-{iteration:03d}.json"
        iteration_payload = {
            "generated_at": generated_at,
            "iteration": iteration,
            "mode": mode,
            "params": asdict(params),
            "metrics": metrics,
            "objective": float(objective),
            "candidate_count_mean": float(candidate_count_mean),
            "missed_cases": missed_cases,
            "cases": case_results,
        }
        iteration_path.write_text(json.dumps(iteration_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    assert best_result is not None

    policy_summary = _build_policy_summary(iteration_results)

    config_pack_path = output_dir / "config_pack.json"
    config_pack_payload = {
        "schema_version": CONFIG_PACK_SCHEMA_VERSION,
        "name": f"tuning-{generated_at}",
        "generated_at": generated_at,
        "source": "scripts/ralph_wiggum_iterate.py",
        "overrides": {
            "top_k_files": int(best_result.params.top_k_files),
            "min_candidate_score": int(best_result.params.min_candidate_score),
            "candidate_relative_threshold": float(
                best_result.params.candidate_relative_threshold
            ),
            "candidate_ranker": str(best_result.params.candidate_ranker),
            "hybrid_re2_fusion_mode": str(best_result.params.hybrid_re2_fusion_mode),
            "hybrid_re2_rrf_k": int(best_result.params.hybrid_re2_rrf_k),
            "repomap_signal_weights": best_result.params.repomap_signal_weights,
            "retrieval_policy": str(best_result.params.retrieval_policy),
        },
        "best": {
            "iteration": int(best_result.iteration),
            "mode": str(best_result.mode),
            "metrics": dict(best_result.metrics),
            "objective": float(best_result.objective),
        },
    }
    config_pack_path.write_text(
        json.dumps(config_pack_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary_path = output_dir / "summary.json"
    summary_payload = {
        "generated_at": generated_at,
        "repo": repo,
        "root": root,
        "cases": cases_path,
        "iterations": len(iteration_results),
        "policy_summary": policy_summary,
        "best": {
            "iteration": best_result.iteration,
            "mode": best_result.mode,
            "params": asdict(best_result.params),
            "metrics": best_result.metrics,
            "objective": best_result.objective,
            "candidate_count_mean": best_result.candidate_count_mean,
            "missed_cases": best_result.missed_cases,
        },
        "config_pack": str(config_pack_path),
        "runs": [
            {
                "iteration": item.iteration,
                "mode": item.mode,
                "params": asdict(item.params),
                "metrics": item.metrics,
                "objective": item.objective,
                "candidate_count_mean": item.candidate_count_mean,
                "missed_cases": item.missed_cases,
            }
            for item in iteration_results
        ],
    }
    summary_path.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    markdown_out = Path(args.markdown_out)
    _write_markdown_report(
        output_path=markdown_out,
        generated_at=generated_at,
        repo=repo,
        root=root,
        cases_path=cases_path,
        recall_floor=recall_floor,
        iteration_results=iteration_results,
        best_result=best_result,
    )

    print(json.dumps({"output_dir": str(output_dir), "summary": str(summary_path), "markdown": str(markdown_out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

