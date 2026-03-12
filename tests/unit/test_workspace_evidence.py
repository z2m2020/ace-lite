from __future__ import annotations

import pytest

from ace_lite.workspace.evidence import (
    build_workspace_evidence_contract_v1,
    validate_workspace_evidence_contract_v1,
)
from ace_lite.validation.patch_artifact import build_patch_artifact_contract_v1


def test_workspace_evidence_contract_includes_extended_collections() -> None:
    contract = build_workspace_evidence_contract_v1(
        decision_target="billing rollout risk",
        candidate_repos=[{"name": "billing-api"}],
        selected_repos=[
            {
                "name": "billing-api",
                "matched_terms": ["billing", "rollout"],
                "quick_plan": {"candidate_files": ["src/billing/service.py"]},
            }
        ],
    ).as_dict()

    assert isinstance(contract["impacted_symbols"], list)
    assert isinstance(contract["dependency_chain"], list)
    assert isinstance(contract["rollback_points"], list)


def test_workspace_evidence_contract_populates_extended_fields_when_available() -> None:
    contract = build_workspace_evidence_contract_v1(
        decision_target="billing checkout impact",
        candidate_repos=[{"name": "billing-api"}, {"name": "frontend-ui"}],
        selected_repos=[
            {
                "name": "billing-api",
                "matched_terms": ["billing", "checkout"],
                "quick_plan": {
                    "candidate_files": [
                        "src/billing/service.py",
                        "src/billing/models.py",
                    ],
                    "impacted_symbols": [
                        "billing.service.charge_invoice",
                        "billing.models.Invoice",
                    ],
                    "dependency_chain": [
                        {
                            "from_repo": "frontend-ui",
                            "to_repo": "billing-api",
                            "reason": "checkout calls billing API",
                        }
                    ],
                    "rollback_points": [
                        "feature-flag:checkout_v2",
                        "db:migration:billing_20260305_revert",
                    ],
                },
            }
        ],
    ).as_dict()

    assert contract["impacted_symbols"]
    assert contract["dependency_chain"]
    assert contract["rollback_points"]


def test_validate_workspace_evidence_contract_v1_passes_valid_contract() -> None:
    contract = build_workspace_evidence_contract_v1(
        decision_target="billing checkout impact",
        candidate_repos=[{"name": "billing-api"}, {"name": "frontend-ui"}],
        selected_repos=[
            {
                "name": "billing-api",
                "matched_terms": ["billing"],
                "quick_plan": {
                    "candidate_files": ["src/billing/service.py"],
                    "rows": [{"module": "billing.service", "path": "src/billing/service.py"}],
                    "repomap_stage": {
                        "seed_paths": ["src/billing/service.py"],
                        "neighbor_paths": ["src/billing/models.py"],
                        "focused_files": ["src/billing/service.py"],
                    },
                },
            }
        ],
    )
    result = validate_workspace_evidence_contract_v1(
        contract=contract,
        strict=True,
        min_confidence=0.2,
        fail_closed=True,
    )
    assert result["ok"] is True
    assert result["violations"] == []
    assert result["violation_details"] == []


def test_workspace_evidence_contract_includes_patch_artifacts_when_available() -> None:
    patch_artifact = build_patch_artifact_contract_v1(
        operations=[{"op": "update", "path": "src/billing/service.py", "hunk_count": 1}],
        rollback_anchors=[
            {"path": "src/billing/service.py", "strategy": "git_restore", "anchor": "HEAD"}
        ],
        patch_text="diff --git a/src/billing/service.py b/src/billing/service.py",
    ).as_dict()

    contract = build_workspace_evidence_contract_v1(
        decision_target="billing checkout impact",
        candidate_repos=[{"name": "billing-api"}],
        selected_repos=[
            {
                "name": "billing-api",
                "matched_terms": ["billing"],
                "quick_plan": {
                    "candidate_files": ["src/billing/service.py"],
                    "rows": [{"module": "billing.service", "path": "src/billing/service.py"}],
                    "repomap_stage": {
                        "seed_paths": ["src/billing/service.py"],
                        "neighbor_paths": ["src/billing/models.py"],
                        "focused_files": ["src/billing/service.py"],
                    },
                    "patch_artifacts": [patch_artifact],
                },
            }
        ],
    ).as_dict()

    assert contract["patch_artifacts"] == [patch_artifact]


def test_validate_workspace_evidence_contract_v1_surfaces_invalid_patch_artifact() -> None:
    payload = {
        "decision_target": "billing impact",
        "candidate_repos": ["billing-api"],
        "selected_repos": ["billing-api"],
        "impacted_files_by_repo": {"billing-api": ["src/billing/service.py"]},
        "impacted_symbols": [{"repo": "billing-api", "symbol": "billing.service"}],
        "dependency_chain": [{"repo": "billing-api", "position": 1}],
        "rollback_points": [{"repo": "billing-api", "paths": ["src/billing/service.py"]}],
        "patch_artifacts": [
            {
                "schema_version": "bad",
                "patch_format": "unified_diff",
                "target_file_manifest": ["src/billing/service.py"],
                "operations": [{"op": "update", "path": "src/billing/service.py"}],
                "rollback_anchors": [{"path": "src/billing/service.py"}],
            }
        ],
        "confidence": 0.9,
    }

    result = validate_workspace_evidence_contract_v1(
        contract=payload,
        strict=True,
        min_confidence=0.5,
        fail_closed=True,
    )

    assert result["ok"] is False
    assert "patch_artifact_invalid" in result["violations"]


def test_validate_workspace_evidence_contract_v1_fails_when_required_fields_missing() -> None:
    payload = {
        "decision_target": "",
        "candidate_repos": [],
        "selected_repos": [],
        "impacted_files_by_repo": {},
        "impacted_symbols": [],
        "dependency_chain": [],
        "rollback_points": [],
        "confidence": 0.8,
    }
    result = validate_workspace_evidence_contract_v1(
        contract=payload,
        strict=True,
        min_confidence=0.5,
        fail_closed=True,
    )
    assert result["ok"] is False
    assert "decision_target_empty" in result["violations"]
    assert "candidate_repos_empty" in result["violations"]
    assert "selected_repos_empty" in result["violations"]
    assert isinstance(result["violation_details"], list)
    assert all(
        set(item.keys()) == {"code", "severity", "field", "message", "context"}
        for item in result["violation_details"]
    )
    assert any(item["code"] == "decision_target_empty" for item in result["violation_details"])


def test_validate_workspace_evidence_contract_v1_low_confidence_triggers_fail_closed() -> None:
    payload = {
        "decision_target": "billing impact",
        "candidate_repos": ["billing-api"],
        "selected_repos": ["billing-api"],
        "impacted_files_by_repo": {"billing-api": ["src/billing/service.py"]},
        "impacted_symbols": [{"repo": "billing-api", "symbol": "billing.service"}],
        "dependency_chain": [{"repo": "billing-api", "position": 1}],
        "rollback_points": [{"repo": "billing-api", "paths": ["src/billing/service.py"]}],
        "confidence": 0.3,
    }
    result = validate_workspace_evidence_contract_v1(
        contract=payload,
        strict=True,
        min_confidence=0.5,
        fail_closed=True,
    )
    assert result["ok"] is False
    assert "confidence_below_min_confidence" in result["violations"]
    assert result["fail_closed"] is True
    assert any(
        item["code"] == "confidence_below_min_confidence"
        and item["field"] == "confidence"
        and item["context"].get("min_confidence") == 0.5
        for item in result["violation_details"]
    )


def test_validate_workspace_evidence_contract_v1_uses_stable_codes_and_repo_context() -> None:
    payload = {
        "decision_target": "billing impact",
        "candidate_repos": ["billing-api", "frontend-ui"],
        "selected_repos": ["billing-api", "frontend-ui"],
        "impacted_files_by_repo": {"billing-api": ["src/billing/service.py"]},
        "impacted_symbols": [{"repo": "billing-api", "symbol": "billing.service"}],
        "dependency_chain": [{"repo": "billing-api", "position": 1}],
        "rollback_points": [{"repo": "billing-api", "paths": ["src/billing/service.py"]}],
        "confidence": 0.9,
    }
    result = validate_workspace_evidence_contract_v1(
        contract=payload,
        strict=True,
        min_confidence=0.5,
        fail_closed=True,
    )

    assert result["ok"] is False
    assert "impacted_files_missing_repo" in result["violations"]
    assert not any("frontend-ui" in code for code in result["violations"])
    assert any(
        item["code"] == "impacted_files_missing_repo"
        and item["field"] == "impacted_files_by_repo"
        and item["context"].get("repo") == "frontend-ui"
        for item in result["violation_details"]
    )


def test_validate_workspace_evidence_contract_v1_ok_reflects_violations_even_without_fail_closed() -> None:
    payload = {
        "decision_target": "billing impact",
        "candidate_repos": ["billing-api"],
        "selected_repos": ["billing-api"],
        "impacted_files_by_repo": {"billing-api": ["src/billing/service.py"]},
        "impacted_symbols": [{"repo": "billing-api", "symbol": "billing.service"}],
        "dependency_chain": [{"repo": "billing-api", "position": 1}],
        "rollback_points": [{"repo": "billing-api", "paths": ["src/billing/service.py"]}],
        "confidence": 0.2,
    }
    result = validate_workspace_evidence_contract_v1(
        contract=payload,
        strict=True,
        min_confidence=0.5,
        fail_closed=False,
    )
    assert result["ok"] is False
    assert result["fail_closed"] is False
    assert "confidence_below_min_confidence" in result["violations"]


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_validate_workspace_evidence_contract_v1_rejects_non_finite_min_confidence(
    value: float,
) -> None:
    contract = build_workspace_evidence_contract_v1(
        decision_target="billing impact",
        candidate_repos=[{"name": "billing-api"}],
        selected_repos=[
            {
                "name": "billing-api",
                "matched_terms": ["billing"],
                "quick_plan": {
                    "candidate_files": ["src/billing/service.py"],
                    "rows": [{"module": "billing.service", "path": "src/billing/service.py"}],
                    "repomap_stage": {
                        "seed_paths": ["src/billing/service.py"],
                        "neighbor_paths": ["src/billing/models.py"],
                        "focused_files": ["src/billing/service.py"],
                    },
                },
            }
        ],
    )

    with pytest.raises(ValueError, match=r"min_confidence must be a finite number"):
        validate_workspace_evidence_contract_v1(
            contract=contract,
            strict=True,
            min_confidence=value,
            fail_closed=True,
        )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_validate_workspace_evidence_contract_v1_rejects_non_finite_confidence(
    value: float,
) -> None:
    payload = {
        "decision_target": "billing impact",
        "candidate_repos": ["billing-api"],
        "selected_repos": ["billing-api"],
        "impacted_files_by_repo": {"billing-api": ["src/billing/service.py"]},
        "impacted_symbols": [{"repo": "billing-api", "symbol": "billing.service"}],
        "dependency_chain": [{"repo": "billing-api", "position": 1}],
        "rollback_points": [{"repo": "billing-api", "paths": ["src/billing/service.py"]}],
        "confidence": value,
    }

    result = validate_workspace_evidence_contract_v1(
        contract=payload,
        strict=True,
        min_confidence=0.0,
        fail_closed=True,
    )
    assert result["ok"] is False
    assert "confidence_not_finite" in result["violations"]
