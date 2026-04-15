from __future__ import annotations

from typing import Any

from ace_lite.benchmark.report_metrics import (
    format_metric as _format_metric,
)
from ace_lite.benchmark.report_metrics import (
    normalize_metrics as _normalize_metrics,
)


def append_validation_branch_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    summary_raw = results.get("validation_branch_summary")
    summary = summary_raw if isinstance(summary_raw, dict) else {}
    metrics = _normalize_metrics(results.get("metrics"))

    case_count = float(
        summary.get("case_count", metrics.get("validation_branch_case_count", 0.0))
        or 0.0
    )
    case_rate = float(
        summary.get("case_rate", metrics.get("validation_branch_case_rate", 0.0))
        or 0.0
    )
    candidate_count_mean = float(
        summary.get(
            "candidate_count_mean",
            metrics.get("validation_branch_candidate_count_mean", 0.0),
        )
        or 0.0
    )
    rejected_count_mean = float(
        summary.get(
            "rejected_count_mean",
            metrics.get("validation_branch_rejected_count_mean", 0.0),
        )
        or 0.0
    )
    selection_present_ratio = float(
        summary.get(
            "selection_present_ratio",
            metrics.get("validation_branch_selection_present_ratio", 0.0),
        )
        or 0.0
    )
    patch_artifact_present_ratio = float(
        summary.get(
            "patch_artifact_present_ratio",
            metrics.get("validation_branch_patch_artifact_present_ratio", 0.0),
        )
        or 0.0
    )
    archive_present_ratio = float(
        summary.get(
            "archive_present_ratio",
            metrics.get("validation_branch_archive_present_ratio", 0.0),
        )
        or 0.0
    )
    parallel_case_rate = float(
        summary.get(
            "parallel_case_rate",
            metrics.get("validation_branch_parallel_case_rate", 0.0),
        )
        or 0.0
    )
    winner_pass_rate = float(
        summary.get(
            "winner_pass_rate",
            metrics.get("validation_branch_winner_pass_rate", 0.0),
        )
        or 0.0
    )
    winner_regressed_rate = float(
        summary.get(
            "winner_regressed_rate",
            metrics.get("validation_branch_winner_regressed_rate", 0.0),
        )
        or 0.0
    )
    winner_score_mean = float(
        summary.get(
            "winner_score_mean",
            metrics.get("validation_branch_winner_score_mean", 0.0),
        )
        or 0.0
    )
    winner_after_issue_count_mean = float(
        summary.get(
            "winner_after_issue_count_mean",
            metrics.get("validation_branch_winner_after_issue_count_mean", 0.0),
        )
        or 0.0
    )
    if (
        case_count <= 0.0
        and case_rate <= 0.0
        and candidate_count_mean <= 0.0
        and rejected_count_mean <= 0.0
        and selection_present_ratio <= 0.0
        and patch_artifact_present_ratio <= 0.0
        and archive_present_ratio <= 0.0
        and parallel_case_rate <= 0.0
        and winner_pass_rate <= 0.0
        and winner_regressed_rate <= 0.0
        and winner_score_mean <= 0.0
        and winner_after_issue_count_mean <= 0.0
    ):
        return

    lines.append("## Validation Branch Summary")
    lines.append("")
    lines.append(
        "- Applicable case count / rate: {count} / {rate}".format(
            count=_format_metric("validation_branch_case_count", case_count),
            rate=_format_metric("validation_branch_case_rate", case_rate),
        )
    )
    lines.append(
        "- Candidate / rejected count mean: {candidates} / {rejected}".format(
            candidates=_format_metric(
                "validation_branch_candidate_count_mean",
                candidate_count_mean,
            ),
            rejected=_format_metric(
                "validation_branch_rejected_count_mean",
                rejected_count_mean,
            ),
        )
    )
    lines.append(
        "- Selection / winner artifact / loser archive ratios: {selection} / {patch} / {archive}".format(
            selection=_format_metric(
                "validation_branch_selection_present_ratio",
                selection_present_ratio,
            ),
            patch=_format_metric(
                "validation_branch_patch_artifact_present_ratio",
                patch_artifact_present_ratio,
            ),
            archive=_format_metric(
                "validation_branch_archive_present_ratio",
                archive_present_ratio,
            ),
        )
    )
    lines.append(
        "- Parallel rate: {parallel}; winner pass / regressed rates: {passed} / {regressed}".format(
            parallel=_format_metric(
                "validation_branch_parallel_case_rate",
                parallel_case_rate,
            ),
            passed=_format_metric(
                "validation_branch_winner_pass_rate",
                winner_pass_rate,
            ),
            regressed=_format_metric(
                "validation_branch_winner_regressed_rate",
                winner_regressed_rate,
            ),
        )
    )
    lines.append(
        "- Winner score mean: {score}; after-issue count mean: {issues}".format(
            score=_format_metric(
                "validation_branch_winner_score_mean",
                winner_score_mean,
            ),
            issues=_format_metric(
                "validation_branch_winner_after_issue_count_mean",
                winner_after_issue_count_mean,
            ),
        )
    )
    lines.append("")


def append_validation_branch_gate_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    summary_raw = results.get("validation_branch_gate_summary")
    summary: dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}
    if not summary:
        return

    lines.append("## Validation Branch Gate Summary")
    lines.append("")
    lines.append(
        "- Gate passed: {value}".format(
            value="yes" if bool(summary.get("gate_passed", False)) else "no"
        )
    )
    lines.append(
        "- Applicable case count / threshold: {count} / {threshold}".format(
            count=_format_metric(
                "validation_branch_case_count",
                summary.get("case_count", 0.0),
            ),
            threshold=_format_metric(
                "validation_branch_case_count",
                summary.get("case_count_threshold", 0.0),
            ),
        )
    )
    lines.append(
        "- Selection / winner artifact / loser archive ratios: {selection} / {patch} / {archive}".format(
            selection=_format_metric(
                "validation_branch_selection_present_ratio",
                summary.get("selection_present_ratio", 0.0),
            ),
            patch=_format_metric(
                "validation_branch_patch_artifact_present_ratio",
                summary.get("patch_artifact_present_ratio", 0.0),
            ),
            archive=_format_metric(
                "validation_branch_archive_present_ratio",
                summary.get("archive_present_ratio", 0.0),
            ),
        )
    )
    lines.append(
        "- Parallel case rate / threshold: {rate} / {threshold}".format(
            rate=_format_metric(
                "validation_branch_parallel_case_rate",
                summary.get("parallel_case_rate", 0.0),
            ),
            threshold=_format_metric(
                "validation_branch_parallel_case_rate",
                summary.get("parallel_case_rate_threshold", 0.0),
            ),
        )
    )
    failed_checks = summary.get("failed_checks", [])
    if isinstance(failed_checks, list):
        lines.append(
            "- Failed checks: "
            + (
                ", ".join(str(item) for item in failed_checks if str(item).strip())
                if failed_checks
                else "(none)"
            )
        )
    lines.append("")


def append_retrieval_frontier_gate_summary(
    lines: list[str], results: dict[str, Any]
) -> None:
    summary_raw = results.get("retrieval_frontier_gate_summary")
    summary: dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}
    if not summary:
        return

    failed_checks_raw = summary.get("failed_checks", [])
    failed_checks = (
        [str(item) for item in failed_checks_raw if str(item).strip()]
        if isinstance(failed_checks_raw, list)
        else []
    )

    lines.append("## Retrieval Frontier Gate Summary")
    lines.append("")
    lines.append(
        f"- Gate passed: {'yes' if bool(summary.get('gate_passed', False)) else 'no'}"
    )
    lines.append(
        "- Deep-symbol recall: {value:.4f} (threshold >= {threshold:.4f}, {status})".format(
            value=float(summary.get("deep_symbol_case_recall", 0.0) or 0.0),
            threshold=float(
                summary.get("deep_symbol_case_recall_threshold", 0.0) or 0.0
            ),
            status="pass"
            if bool(summary.get("deep_symbol_case_recall_passed", False))
            else "fail",
        )
    )
    lines.append(
        "- Native SCIP loaded rate: {value:.4f} (threshold >= {threshold:.4f}, {status})".format(
            value=float(summary.get("native_scip_loaded_rate", 0.0) or 0.0),
            threshold=float(
                summary.get("native_scip_loaded_rate_threshold", 0.0) or 0.0
            ),
            status="pass"
            if bool(summary.get("native_scip_loaded_rate_passed", False))
            else "fail",
        )
    )
    lines.append(
        "- Precision@k: {value:.4f} (threshold >= {threshold:.4f}, {status})".format(
            value=float(summary.get("precision_at_k", 0.0) or 0.0),
            threshold=float(summary.get("precision_at_k_threshold", 0.0) or 0.0),
            status="pass"
            if bool(summary.get("precision_at_k_passed", False))
            else "fail",
        )
    )
    lines.append(
        "- Noise rate: {value:.4f} (threshold <= {threshold:.4f}, {status})".format(
            value=float(summary.get("noise_rate", 0.0) or 0.0),
            threshold=float(summary.get("noise_rate_threshold", 0.0) or 0.0),
            status="pass"
            if bool(summary.get("noise_rate_passed", False))
            else "fail",
        )
    )
    lines.append(
        "- Failed checks: {value}".format(
            value=", ".join(failed_checks) if failed_checks else "(none)"
        )
    )
    lines.append("")
