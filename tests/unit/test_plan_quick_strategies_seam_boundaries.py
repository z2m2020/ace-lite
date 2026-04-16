from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read_plan_quick_strategies_text() -> str:
    return (REPO_ROOT / "src" / "ace_lite" / "plan_quick_strategies.py").read_text(encoding="utf-8")


def test_plan_quick_strategies_imports_support_modules() -> None:
    text = _read_plan_quick_strategies_text()

    expected_tokens = (
        "from ace_lite.plan_quick_strategies_boost import (",
        "BoostResult",
        "BoostStrategy",
        "BoostStrategyRegistry",
        "from ace_lite.plan_quick_strategies_domain import (",
        "DomainMatch",
        "DomainStrategy",
        "DomainStrategyRegistry",
        "from ace_lite.plan_quick_strategies_intent import (",
        "IntentStrategy",
        "IntentStrategyRegistry",
        "from ace_lite.plan_quick_strategies_shared import (",
        "NormalizationUtils",
        "QueryFlags",
        "_extract_path_date",
        "_extract_req_ids",
    )
    for token in expected_tokens:
        assert token in text


def test_plan_quick_strategies_keeps_moved_clusters_out_of_facade() -> None:
    text = _read_plan_quick_strategies_text()

    forbidden_local_helpers = (
        "class NormalizationUtils",
        "class QueryFlags",
        "def _extract_req_ids(",
        "def _extract_path_date(",
        "class DomainMatch",
        "class DomainStrategy",
        "class PlanningDomainStrategy",
        "class ReposDomainStrategy",
        "class ReportsDomainStrategy",
        "class ResearchDomainStrategy",
        "class ReferenceDomainStrategy",
        "class DocsDomainStrategy",
        "class TestsDomainStrategy",
        "class MarkdownDomainStrategy",
        "class IntentStrategy",
        "class OnboardingIntentStrategy",
        "class DocSyncIntentStrategy",
        "class LatestIntentStrategy",
        "class ReqIdIntentStrategy",
        "class BoostResult",
        "class BoostStrategy",
        "class DocSyncBoostStrategy",
        "class LatestDocBoostStrategy",
    )
    for token in forbidden_local_helpers:
        assert token not in text
