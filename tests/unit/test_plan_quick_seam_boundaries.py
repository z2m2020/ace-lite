from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read_repo_text(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_plan_quick_uses_ranking_helper_seam() -> None:
    plan_quick_text = _read_repo_text("src/ace_lite/plan_quick.py")

    expected_tokens = (
        "from ace_lite.plan_quick_ranking import (",
        "build_candidate_details",
        "build_history_summary",
        "build_mixed_top_k_candidates",
        "build_onboarding_view",
        "build_upgrade_guidance",
    )
    for token in expected_tokens:
        assert token in plan_quick_text

    forbidden_local_helpers = (
        "def _build_candidate_details(",
        "def _build_history_summary(",
        "def _build_mixed_top_k_candidates(",
        "def _build_onboarding_view(",
        "def _build_upgrade_guidance(",
    )
    for token in forbidden_local_helpers:
        assert token not in plan_quick_text
