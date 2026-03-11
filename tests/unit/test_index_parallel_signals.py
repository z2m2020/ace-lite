from __future__ import annotations

from ace_lite.index_stage.parallel_signals import collect_parallel_signals


def test_collect_parallel_signals_runs_sequentially_when_parallel_disabled() -> None:
    def fake_collect_docs(*, root, query, terms, enabled, intent_weight, max_sections):  # type: ignore[no-untyped-def]
        assert enabled is True
        return {"enabled": True, "elapsed_ms": 1.5, "section_count": 1}

    def fake_collect_worktree(*, root, files_map, max_seed_paths):  # type: ignore[no-untyped-def]
        return {"enabled": True, "changed_count": 2, "seed_paths": ["src/a.py"]}

    def fake_disabled_docs_payload(*, reason, elapsed_ms):  # type: ignore[no-untyped-def]
        return {"enabled": False, "reason": reason, "elapsed_ms": elapsed_ms}

    def fake_disabled_worktree_prior(*, reason):  # type: ignore[no-untyped-def]
        return {"enabled": False, "reason": reason}

    result = collect_parallel_signals(
        root=".",
        query="needle",
        terms=["needle"],
        files_map={"src/a.py": {"module": "src.a"}},
        top_k_files=4,
        docs_policy_enabled=True,
        worktree_prior_enabled=True,
        cochange_enabled=True,
        docs_intent_weight=1.0,
        parallel_requested=False,
        parallel_time_budget_ms=0,
        collect_docs=fake_collect_docs,
        collect_worktree=fake_collect_worktree,
        disabled_docs_payload=fake_disabled_docs_payload,
        disabled_worktree_prior=fake_disabled_worktree_prior,
        get_executor=lambda: None,  # type: ignore[arg-type]
        resolve_future=lambda **kwargs: None,  # type: ignore[arg-type]
    )

    assert result.parallel_payload["requested"] is False
    assert result.parallel_payload["enabled"] is False
    assert result.docs_payload["enabled"] is True
    assert result.worktree_prior["enabled"] is True
    assert result.docs_elapsed_ms >= 0.0
    assert result.worktree_elapsed_ms >= 0.0


def test_collect_parallel_signals_uses_timeout_fallbacks() -> None:
    class _FakeExecutor:
        def submit(self, fn):  # type: ignore[no-untyped-def]
            return object()

    def fake_collect_docs(*, root, query, terms, enabled, intent_weight, max_sections):  # type: ignore[no-untyped-def]
        raise AssertionError("should not run directly in timeout test")

    def fake_collect_worktree(*, root, files_map, max_seed_paths):  # type: ignore[no-untyped-def]
        raise AssertionError("should not run directly in timeout test")

    def fake_disabled_docs_payload(*, reason, elapsed_ms):  # type: ignore[no-untyped-def]
        return {"enabled": False, "reason": reason, "elapsed_ms": elapsed_ms}

    def fake_disabled_worktree_prior(*, reason):  # type: ignore[no-untyped-def]
        return {"enabled": False, "reason": reason}

    def fake_resolve_future(*, future, timeout_seconds, fallback):  # type: ignore[no-untyped-def]
        return fallback, True, "timeout"

    result = collect_parallel_signals(
        root=".",
        query="needle",
        terms=["needle"],
        files_map={"src/a.py": {"module": "src.a"}},
        top_k_files=4,
        docs_policy_enabled=True,
        worktree_prior_enabled=True,
        cochange_enabled=True,
        docs_intent_weight=1.0,
        parallel_requested=True,
        parallel_time_budget_ms=20,
        collect_docs=fake_collect_docs,
        collect_worktree=fake_collect_worktree,
        disabled_docs_payload=fake_disabled_docs_payload,
        disabled_worktree_prior=fake_disabled_worktree_prior,
        get_executor=_FakeExecutor,
        resolve_future=fake_resolve_future,
    )

    assert result.parallel_payload["requested"] is True
    assert result.parallel_payload["enabled"] is True
    assert result.parallel_payload["docs"]["started"] is True
    assert result.parallel_payload["docs"]["timed_out"] is True
    assert result.parallel_payload["worktree"]["started"] is True
    assert result.parallel_payload["worktree"]["timed_out"] is True
    assert result.docs_payload["reason"] == "timeout"
    assert result.worktree_prior["reason"] == "timeout"
