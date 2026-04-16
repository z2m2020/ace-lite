from __future__ import annotations

import json

from ace_lite.index_stage.policy import (
    resolve_online_bandit_gate,
    resolve_retrieval_policy,
    resolve_shadow_router_arm,
)


def test_resolve_retrieval_policy_selects_doc_intent_for_architecture_queries() -> None:
    payload = resolve_retrieval_policy(
        query="how does the architecture and retry mechanism work",
        retrieval_policy="auto",
        policy_version="v1",
        cochange_enabled=True,
        embedding_enabled=True,
    )

    assert payload["name"] == "doc_intent"
    assert payload["docs_enabled"] is True
    assert float(payload["docs_weight"]) > 1.0
    assert payload["cochange_enabled"] is False
    assert payload["worktree_query_guard_enabled"] is True
    assert int(payload["worktree_query_guard_min_overlap"]) >= 1
    assert "graph_lookup_enabled" in payload
    assert int(payload["semantic_rerank_time_budget_ms"]) > 0


def test_resolve_retrieval_policy_keeps_general_for_definition_lookup() -> None:
    payload = resolve_retrieval_policy(
        query="where RequestException class is defined",
        retrieval_policy="auto",
        policy_version="v1",
        cochange_enabled=True,
        embedding_enabled=True,
    )

    assert payload["name"] == "general"
    assert payload["graph_lookup_enabled"] is True
    assert payload["worktree_query_guard_enabled"] is True
    assert int(payload["graph_lookup_max_candidates"]) >= 32


def test_resolve_retrieval_policy_enables_graph_lookup_for_feature_queries() -> None:
    payload = resolve_retrieval_policy(
        query="implement feature to add request trace context",
        retrieval_policy="auto",
        policy_version="v1",
        cochange_enabled=True,
        embedding_enabled=True,
    )

    assert payload["name"] == "feature"
    assert payload["graph_lookup_enabled"] is True
    assert payload["worktree_query_guard_enabled"] is False
    assert int(payload["graph_lookup_pool"]) > 0
    assert float(payload["graph_lookup_symbol_weight"]) >= 0.0
    assert float(payload["graph_lookup_import_weight"]) >= 0.0
    assert float(payload["graph_lookup_coverage_weight"]) >= 0.0
    assert isinstance(payload["graph_lookup_log_norm"], bool)
    assert int(payload["graph_lookup_max_query_terms"]) >= int(
        payload["graph_lookup_min_query_terms"]
    )


def test_resolve_retrieval_policy_selects_doc_intent_for_chinese_architecture_queries() -> None:
    payload = resolve_retrieval_policy(
        query="解释一下重试机制和整体架构如何工作",
        retrieval_policy="auto",
        policy_version="v1",
        cochange_enabled=True,
        embedding_enabled=True,
    )

    assert payload["name"] == "doc_intent"
    assert payload["docs_enabled"] is True
    assert float(payload["docs_weight"]) > 1.0
    assert payload["worktree_query_guard_enabled"] is True


def test_resolve_retrieval_policy_selects_doc_intent_for_doc_sync_queries() -> None:
    payload = resolve_retrieval_policy(
        query="sync docs update latest progress report",
        retrieval_policy="auto",
        policy_version="v1",
        cochange_enabled=True,
        embedding_enabled=True,
    )

    assert payload["name"] == "doc_intent"
    assert payload["docs_enabled"] is True


def test_resolve_retrieval_policy_keeps_general_for_code_queries_with_weak_doc_terms() -> None:
    payload = resolve_retrieval_policy(
        query="shutdown config redis yaml auto phase fallback refresh status controller",
        retrieval_policy="auto",
        policy_version="v1",
        cochange_enabled=True,
        embedding_enabled=True,
    )

    assert payload["name"] == "general"
    assert payload["docs_enabled"] is False


def test_resolve_retrieval_policy_selects_doc_intent_for_lowercase_requirement_ids() -> None:
    payload = resolve_retrieval_policy(
        query="explain expl-01 trace contract behavior",
        retrieval_policy="auto",
        policy_version="v1",
        cochange_enabled=True,
        embedding_enabled=True,
    )

    assert payload["name"] == "doc_intent"
    assert payload["docs_enabled"] is True


def test_resolve_retrieval_policy_keeps_general_for_chinese_definition_lookup() -> None:
    payload = resolve_retrieval_policy(
        query="RequestException 类在哪里定义",
        retrieval_policy="auto",
        policy_version="v1",
        cochange_enabled=True,
        embedding_enabled=True,
    )

    assert payload["name"] == "general"


def test_resolve_retrieval_policy_selects_bugfix_test_for_chinese_bugfix_queries() -> None:
    payload = resolve_retrieval_policy(
        query="修复测试失败导致的错误",
        retrieval_policy="auto",
        policy_version="v1",
        cochange_enabled=True,
        embedding_enabled=True,
    )

    assert payload["name"] == "bugfix_test"


def test_resolve_shadow_router_arm_uses_model_mapping(tmp_path) -> None:
    model_path = tmp_path / "router-model.json"
    model_path.write_text(
        json.dumps(
            {
                "arm_set": "retrieval_policy_shadow",
                "policy_arms": {"feature": {"arm_id": "feature_graph", "confidence": 0.91}},
            }
        ),
        encoding="utf-8",
    )

    payload = resolve_shadow_router_arm(
        enabled=True,
        mode="shadow",
        model_path=model_path,
        arm_set="retrieval_policy_shadow",
        executed_policy_name="feature",
        candidate_ranker="hybrid_re2",
        embedding_enabled=True,
    )

    assert payload == {
        "arm_id": "feature_graph",
        "confidence": 0.91,
        "source": "model",
    }


def test_resolve_shadow_router_arm_falls_back_deterministically_when_model_missing() -> None:
    payload = resolve_shadow_router_arm(
        enabled=True,
        mode="shadow",
        model_path="missing-router-model.json",
        arm_set="retrieval_policy_shadow",
        executed_policy_name="general",
        candidate_ranker="hybrid_re2",
        embedding_enabled=True,
    )

    assert payload == {
        "arm_id": "general_hybrid",
        "confidence": 0.25,
        "source": "fallback",
    }


def test_resolve_shadow_router_arm_is_disabled_outside_shadow_mode() -> None:
    payload = resolve_shadow_router_arm(
        enabled=True,
        mode="observe",
        model_path="missing-router-model.json",
        arm_set="retrieval_policy_shadow",
        executed_policy_name="feature",
        candidate_ranker="hybrid_re2",
        embedding_enabled=True,
    )

    assert payload == {
        "arm_id": "",
        "confidence": 0.0,
        "source": "disabled",
    }


def test_resolve_online_bandit_gate_requires_explicit_enablement() -> None:
    payload = resolve_online_bandit_gate(
        enabled=False,
        experiment_enabled=False,
        state_path="context-map/router/state.json",
    )

    assert payload["requested"] is False
    assert payload["eligible"] is False
    assert payload["active"] is False
    assert payload["reason"] == "disabled"
    assert payload["is_exploration"] is False
    assert payload["exploration_probability"] == 0.0
    assert payload["fallback_applied"] is False
    assert payload["fallback_reason"] == ""
    assert payload["executed_mode"] == "heuristic"
    assert payload["fallback_mode"] == "heuristic"
    assert payload["required_task_ids"] == ["Y18", "Y19", "Y20", "Y21"]


def test_resolve_online_bandit_gate_marks_prerequisites_ready_but_keeps_runtime_off() -> None:
    payload = resolve_online_bandit_gate(
        enabled=True,
        experiment_enabled=True,
        state_path="context-map/router/online-bandit-state.json",
    )

    assert payload["requested"] is True
    assert payload["eligible"] is True
    assert payload["active"] is False
    assert payload["reason"] == "eligible_pending_runtime"
    assert payload["is_exploration"] is False
    assert payload["exploration_probability"] == 0.0
    assert payload["fallback_applied"] is True
    assert payload["fallback_reason"] == "heuristic_default"
    assert payload["executed_mode"] == "heuristic"
    assert payload["state_path"] == "context-map/router/online-bandit-state.json"
    assert [item["task_id"] for item in payload["prerequisites"]] == [
        "Y18",
        "Y19",
        "Y20",
        "Y21",
    ]
    assert all(item["ready"] is True for item in payload["prerequisites"])


def test_resolve_online_bandit_gate_requires_experiment_mode_for_non_default_path() -> None:
    payload = resolve_online_bandit_gate(
        enabled=True,
        experiment_enabled=False,
        state_path="context-map/router/online-bandit-state.json",
    )

    assert payload["requested"] is True
    assert payload["experiment_enabled"] is False
    assert payload["eligible"] is True
    assert payload["active"] is False
    assert payload["reason"] == "experiment_mode_required"
    assert payload["fallback_applied"] is True
    assert payload["fallback_reason"] == "experiment_mode_disabled"
