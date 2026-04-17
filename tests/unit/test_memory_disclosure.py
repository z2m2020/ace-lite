from __future__ import annotations

import json

import pytest

from ace_lite.memory import MemoryRecord, MemoryRecordCompact
from ace_lite.memory_long_term import (
    LongTermMemoryProvider,
    LongTermMemoryStore,
    build_long_term_fact_contract_v1,
)
from ace_lite.orchestrator import AceOrchestrator
from ace_lite.orchestrator_config import OrchestratorConfig
from ace_lite.pipeline.stages import memory as memory_stage
from ace_lite.pipeline.types import StageContext
from ace_lite.profile_store import ProfileStore


class _FakeMemoryProvider:
    last_channel_used = "fake"
    fallback_reason = None
    strategy = "hybrid"

    def __init__(self, records: list[MemoryRecord]) -> None:
        self._records_by_handle = {
            f"m{idx}": record for idx, record in enumerate(records, start=1)
        }
        self.last_container_tag: str | None = None
        self.last_container_tag_fallback: str | None = None

    def search_compact(
        self,
        query: str,
        *,
        limit: int | None = None,
        container_tag: str | None = None,
    ) -> list[MemoryRecordCompact]:
        self.last_container_tag = container_tag
        self.last_container_tag_fallback = None
        rows = [
            MemoryRecordCompact(
                handle=handle,
                preview=record.text,
                score=record.score,
                metadata=dict(record.metadata),
                est_tokens=max(1, len(record.text.split())),
                source="fake",
            )
            for handle, record in self._records_by_handle.items()
        ]
        if isinstance(limit, int) and limit > 0:
            return rows[:limit]
        return rows

    def fetch(self, handles: list[str]) -> list[MemoryRecord]:
        rows: list[MemoryRecord] = []
        for handle in handles:
            record = self._records_by_handle.get(handle)
            if record is None:
                continue
            rows.append(
                MemoryRecord(
                    text=record.text,
                    score=record.score,
                    metadata=dict(record.metadata),
                    handle=handle,
                    source="fake",
                )
            )
        return rows


class _LegacyMemoryProvider:
    def search(self, query: str) -> list[MemoryRecord]:
        return [MemoryRecord(text="legacy")]


def _run_memory_stage(
    orch: AceOrchestrator,
    *,
    query: str,
    repo: str = "",
    root: str = ".",
    time_range: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, object]:
    ctx = StageContext(
        query=query,
        repo=repo,
        root=root,
        state={
            "temporal": {
                "time_range": time_range,
                "start_date": start_date,
                "end_date": end_date,
            }
        },
    )
    return orch._run_memory(ctx=ctx)


def test_run_memory_compact_returns_previews_only() -> None:
    provider = _FakeMemoryProvider(
        [
            MemoryRecord(
                text="A" * 500,
                score=0.7,
                metadata={"id": "m1", "path": "src/app.py"},
            )
        ]
    )
    orch = AceOrchestrator(
        memory_provider=provider,
        config=OrchestratorConfig(memory={"preview_max_chars": 100}),
    )
    payload = _run_memory_stage(orch, query="q")

    assert payload["disclosure"]["mode"] == "compact"
    assert payload["strategy"] == "hybrid"
    assert "hits" not in payload
    assert payload["count"] == 1
    assert payload["hits_preview"][0]["handle"] == "m1"
    assert payload["hits_preview"][0]["preview"].endswith("...")
    assert payload["hits_preview"][0]["est_tokens"] >= 1
    assert payload["cost"]["preview_est_tokens_total"] >= 1
    assert payload["cost"]["full_est_tokens_total"] is None
    assert payload["cost"]["tokenizer_model"] == "gpt-4o-mini"
    assert payload["cost"]["tokenizer_backend"] in {"tiktoken", "whitespace"}
    assert payload["timeline"]["enabled"] is True


def test_run_memory_full_returns_hits_and_previews() -> None:
    provider = _FakeMemoryProvider(
        [
            MemoryRecord(
                text="hello world",
                score=0.5,
                metadata={"id": "m1", "created_at": "2026-02-11T01:00:00+00:00"},
            )
        ]
    )
    orch = AceOrchestrator(
        memory_provider=provider,
        config=OrchestratorConfig(memory={"disclosure_mode": "full"}),
    )
    payload = _run_memory_stage(orch, query="q")

    assert payload["disclosure"]["mode"] == "full"
    assert payload["count"] == 1
    assert payload["hits"][0]["text"] == "hello world"
    assert payload["hits"][0]["handle"] == "m1"
    assert payload["hits_preview"][0]["handle"] == "m1"
    assert payload["cost"]["full_est_tokens_total"] >= 1
    assert payload["cost"]["fetch_est_tokens_total"] >= 1
    assert payload["timeline"]["groups"][0]["date_bucket"] == "2026-02-11"


def test_run_memory_full_reuses_preview_token_estimate_when_preview_matches_text(
    monkeypatch,
) -> None:
    provider = _FakeMemoryProvider(
        [
            MemoryRecord(
                text="hello world",
                score=0.5,
                metadata={"id": "m1"},
            )
        ]
    )
    calls = 0

    def fake_estimate_tokens(text: str, *, model: str) -> int:
        del text, model
        nonlocal calls
        calls += 1
        return 99

    monkeypatch.setattr(memory_stage, "estimate_tokens", fake_estimate_tokens)

    orch = AceOrchestrator(
        memory_provider=provider,
        config=OrchestratorConfig(memory={"disclosure_mode": "full"}),
    )
    payload = _run_memory_stage(orch, query="q")

    assert calls == 0
    assert payload["cost"]["full_est_tokens_total"] == payload["hits_preview"][0]["est_tokens"]
    assert payload["cost"]["fetch_est_tokens_total"] == payload["hits_preview"][0]["est_tokens"]


def test_run_memory_full_still_estimates_full_text_when_preview_differs(
    monkeypatch,
) -> None:
    class _ShortPreviewProvider(_FakeMemoryProvider):
        def search_compact(
            self,
            query: str,
            *,
            limit: int | None = None,
            container_tag: str | None = None,
        ) -> list[MemoryRecordCompact]:
            del query, limit, container_tag
            return [
                MemoryRecordCompact(
                    handle="m1",
                    preview="hello",
                    score=0.5,
                    metadata={"id": "m1"},
                    est_tokens=1,
                    source="fake",
                )
            ]

    provider = _ShortPreviewProvider(
        [
            MemoryRecord(
                text="hello world",
                score=0.5,
                metadata={"id": "m1"},
            )
        ]
    )
    calls = 0

    def fake_estimate_tokens(text: str, *, model: str) -> int:
        assert text == "hello world"
        assert model == "gpt-4o-mini"
        nonlocal calls
        calls += 1
        return 9

    monkeypatch.setattr(memory_stage, "estimate_tokens", fake_estimate_tokens)

    orch = AceOrchestrator(
        memory_provider=provider,
        config=OrchestratorConfig(memory={"disclosure_mode": "full"}),
    )
    payload = _run_memory_stage(orch, query="q")

    assert calls == 1
    assert payload["cost"]["full_est_tokens_total"] == 9
    assert payload["cost"]["fetch_est_tokens_total"] == 9


def test_run_memory_exposes_ltm_selected_and_attribution_in_compact_mode(
    tmp_path,
) -> None:
    store = LongTermMemoryStore(db_path=tmp_path / "context-map" / "long_term_memory.db")
    store.upsert_fact(
        build_long_term_fact_contract_v1(
            fact_id="fact-1",
            fact_type="repo_policy",
            subject="runtime.validation.git",
            predicate="fallback_policy",
            object_value="reuse_checkout_or_skip",
            repo="demo",
            namespace="repo/demo",
            as_of="2026-03-19T09:44:00+08:00",
            valid_from="2026-03-19T09:44:00+08:00",
            derived_from_observation_id="obs-1",
            metadata={
                "feedback_signal": "helpful",
                "attribution_scope": "explicit_selection_only",
            },
        )
    )
    provider = LongTermMemoryProvider(store, limit=3, container_tag="repo/demo")
    orch = AceOrchestrator(
        memory_provider=provider,
        config=OrchestratorConfig(memory={"namespace": {"container_tag": "repo/demo"}}),
    )

    payload = _run_memory_stage(orch, query="fallback policy", repo="demo", root=str(tmp_path))

    assert payload["ltm"]["selected_count"] == 1
    assert payload["ltm"]["attribution_count"] == 1
    assert payload["ltm"]["feedback_signal_counts"] == {
        "helpful": 1,
        "stale": 0,
        "harmful": 0,
    }
    assert payload["ltm"]["attribution_scope_counts"] == {
        "explicit_selection_only": 1
    }
    selected = payload["ltm"]["selected"][0]
    assert selected["memory_kind"] == "fact"
    assert selected["fact_type"] == "repo_policy"
    assert selected["subject"] == "runtime.validation.git"
    assert selected["predicate"] == "fallback_policy"
    assert selected["object"] == "reuse_checkout_or_skip"
    assert selected["feedback_signal"] == "helpful"
    assert selected["attribution_scope"] == "explicit_selection_only"
    attribution = payload["ltm"]["attribution"][0]
    assert attribution["handle"] == selected["handle"]
    assert attribution["signals"] == ["fact", "helpful"]
    assert attribution["feedback_signal"] == "helpful"
    assert attribution["attribution_scope"] == "explicit_selection_only"
    assert attribution["summary"] == "runtime.validation.git fallback_policy reuse_checkout_or_skip"


def test_run_memory_full_exposes_ltm_graph_neighborhood_in_attribution(tmp_path) -> None:
    store = LongTermMemoryStore(db_path=tmp_path / "context-map" / "long_term_memory.db")
    store.upsert_fact(
        build_long_term_fact_contract_v1(
            fact_id="fact-1",
            fact_type="repo_policy",
            subject="runtime.validation.git",
            predicate="fallback_policy",
            object_value="reuse_checkout_or_skip",
            repo="demo",
            namespace="repo/demo",
            as_of="2026-03-19T09:44:00+08:00",
            valid_from="2026-03-19T09:44:00+08:00",
            derived_from_observation_id="obs-1",
        )
    )
    store.upsert_fact(
        build_long_term_fact_contract_v1(
            fact_id="fact-2",
            fact_type="repo_policy",
            subject="reuse_checkout_or_skip",
            predicate="recommended_for",
            object_value="runtime.validation.git",
            repo="demo",
            namespace="repo/demo",
            as_of="2026-03-19T09:43:00+08:00",
            valid_from="2026-03-19T09:43:00+08:00",
            derived_from_observation_id="obs-2",
        )
    )
    provider = LongTermMemoryProvider(
        store,
        limit=3,
        container_tag="repo/demo",
        neighborhood_hops=1,
        neighborhood_limit=4,
    )
    orch = AceOrchestrator(
        memory_provider=provider,
        config=OrchestratorConfig(
            memory={
                "disclosure_mode": "full",
                "namespace": {"container_tag": "repo/demo"},
            }
        ),
    )

    payload = _run_memory_stage(orch, query="fallback policy", repo="demo", root=str(tmp_path))

    attribution = next(
        item
        for item in payload["ltm"]["attribution"]
        if item["summary"] == "runtime.validation.git fallback_policy reuse_checkout_or_skip"
    )
    assert attribution["signals"] == ["fact", "graph_neighborhood"]
    assert attribution["graph_neighborhood"]["triple_count"] == 1
    assert attribution["graph_neighborhood"]["triples"][0]["fact_handle"] == "fact-2"


def test_run_memory_requires_v2_provider() -> None:
    orch = AceOrchestrator(memory_provider=_LegacyMemoryProvider(), config=OrchestratorConfig())
    with pytest.raises(TypeError, match="MemoryProvider"):
        _run_memory_stage(orch, query="q")


def test_run_memory_uses_auto_repo_namespace_tag(tmp_path) -> None:
    provider = _FakeMemoryProvider([MemoryRecord(text="hello world", score=0.5)])
    orch = AceOrchestrator(
        memory_provider=provider,
        config=OrchestratorConfig(memory={"namespace": {"auto_tag_mode": "repo"}}),
    )

    payload = _run_memory_stage(
        orch, query="q", repo="My Demo Repo", root=str(tmp_path)
    )

    assert provider.last_container_tag == "repo:my-demo-repo"
    assert payload["namespace"]["mode"] == "repo"
    assert payload["namespace"]["source"] == "auto"
    assert payload["namespace"]["container_tag_effective"] == "repo:my-demo-repo"
    assert payload["namespace"]["effective_reason"] == "auto_repo_namespace"
    assert payload["namespace"]["repo_identity"]["repo_id"] == "my-demo-repo"
    assert payload["namespace"]["filtered_out_count_by_reason"] == {}
    assert payload["namespace"]["fallback"] is None


def test_run_memory_defaults_to_repo_namespace_tag(tmp_path) -> None:
    provider = _FakeMemoryProvider([MemoryRecord(text="hello world", score=0.5)])
    orch = AceOrchestrator(
        memory_provider=provider,
        config=OrchestratorConfig(),
    )

    payload = _run_memory_stage(
        orch, query="q", repo="My Demo Repo", root=str(tmp_path)
    )

    assert provider.last_container_tag == "repo:my-demo-repo"
    assert payload["namespace"]["mode"] == "repo"
    assert payload["namespace"]["source"] == "auto"
    assert payload["namespace"]["container_tag_effective"] == "repo:my-demo-repo"


def test_run_memory_repo_namespace_uses_git_root_name_for_worktree(tmp_path) -> None:
    repo_root = tmp_path / "tabiapp-backend"
    worktree_root = repo_root / "tabiapp-backend_worktree_aeon_v2"
    (repo_root / ".git").mkdir(parents=True, exist_ok=True)
    worktree_root.mkdir(parents=True, exist_ok=True)
    provider = _FakeMemoryProvider([MemoryRecord(text="hello world", score=0.5)])
    orch = AceOrchestrator(
        memory_provider=provider,
        config=OrchestratorConfig(),
    )

    payload = _run_memory_stage(
        orch,
        query="q",
        repo="tabiapp-backend_worktree_aeon_v2",
        root=str(worktree_root),
    )

    assert provider.last_container_tag == "repo:tabiapp-backend"
    assert payload["namespace"]["repo_identity"]["repo_id"] == "tabiapp-backend"
    assert payload["namespace"]["repo_identity"]["worktree_name"] == "tabiapp-backend_worktree_aeon_v2"


def test_run_memory_explicit_namespace_tag_overrides_auto_mode(tmp_path) -> None:
    provider = _FakeMemoryProvider([MemoryRecord(text="hello world", score=0.5)])
    orch = AceOrchestrator(
        memory_provider=provider,
        config=OrchestratorConfig(
            memory={
                "namespace": {
                    "container_tag": "team-alpha",
                    "auto_tag_mode": "repo",
                }
            }
        ),
    )

    payload = _run_memory_stage(orch, query="q", repo="demo", root=str(tmp_path))

    assert provider.last_container_tag == "team-alpha"
    assert payload["namespace"]["mode"] == "explicit"
    assert payload["namespace"]["source"] == "explicit"
    assert payload["namespace"]["container_tag_effective"] == "team-alpha"


def test_run_memory_annotates_constraint_scope_matches_for_repo_namespace(tmp_path) -> None:
    provider = _FakeMemoryProvider(
        [
            MemoryRecord(
                text="same repo memory",
                score=0.5,
                metadata={"repo": "demo", "namespace": "repo:demo"},
            ),
            MemoryRecord(
                text="other repo memory",
                score=0.4,
                metadata={"repo": "other", "namespace": "repo:other"},
            ),
        ]
    )
    orch = AceOrchestrator(
        memory_provider=provider,
        config=OrchestratorConfig(memory={"namespace": {"auto_tag_mode": "repo"}}),
    )

    payload = _run_memory_stage(orch, query="memory", repo="demo", root=str(tmp_path))

    same_repo = next(item for item in payload["hits_preview"] if item["preview"] == "same repo memory")
    other_repo = next(item for item in payload["hits_preview"] if item["preview"] == "other repo memory")

    assert same_repo["source_kind"] == "memory"
    assert same_repo["namespace_scope_match"] is True
    assert same_repo["repo_scope_match"] is True
    assert same_repo["constraint_eligible"] is True
    assert same_repo["constraint_exclusion_reason"] is None

    assert other_repo["namespace_scope_match"] is False
    assert other_repo["repo_scope_match"] is False
    assert other_repo["constraint_eligible"] is False
    assert other_repo["constraint_exclusion_reason"] == "namespace_mismatch"


def test_run_memory_namespace_fallback_marks_effective_tag_none(tmp_path) -> None:
    class _FallbackProvider(_FakeMemoryProvider):
        def search_compact(
            self,
            query: str,
            *,
            limit: int | None = None,
            container_tag: str | None = None,
        ) -> list[MemoryRecordCompact]:
            rows = super().search_compact(
                query,
                limit=limit,
                container_tag=container_tag,
            )
            if container_tag:
                self.last_container_tag_fallback = "backend_unsupported_container_tag"
            return rows

    provider = _FallbackProvider([MemoryRecord(text="hello world", score=0.5)])
    orch = AceOrchestrator(
        memory_provider=provider,
        config=OrchestratorConfig(memory={"namespace": {"container_tag": "team-alpha"}}),
    )

    payload = _run_memory_stage(orch, query="q", repo="demo", root=str(tmp_path))

    assert payload["namespace"]["container_tag_requested"] == "team-alpha"
    assert payload["namespace"]["container_tag_effective"] is None
    assert payload["namespace"]["fallback"] == "backend_unsupported_container_tag"
    assert payload["namespace"]["effective_reason"] == "fallback:backend_unsupported_container_tag"


def test_run_memory_injects_profile_facts_deterministically(tmp_path) -> None:
    profile_path = tmp_path / "profile.json"
    store = ProfileStore(path=profile_path)
    store.add_fact("beta preference", confidence=0.7)
    store.add_fact("alpha preference", confidence=0.9)
    store.add_fact("gamma preference", confidence=0.4)

    provider = _FakeMemoryProvider([MemoryRecord(text="hello world", score=0.5)])
    orch = AceOrchestrator(
        memory_provider=provider,
        config=OrchestratorConfig(
            memory={
                "profile": {
                    "enabled": True,
                    "path": str(profile_path),
                    "top_n": 2,
                    "token_budget": 20,
                }
            }
        ),
    )

    payload = _run_memory_stage(orch, query="q", repo="demo", root=str(tmp_path))

    assert payload["profile"]["enabled"] is True
    assert payload["profile"]["selected_count"] == 2
    assert [fact["text"] for fact in payload["profile"]["facts"]] == [
        "alpha preference",
        "beta preference",
    ]


def test_run_memory_capture_writes_recent_context_and_notes(tmp_path) -> None:
    profile_path = tmp_path / "profile.json"
    notes_path = tmp_path / "memory_notes.jsonl"
    provider = _FakeMemoryProvider([MemoryRecord(text="hello world", score=0.5)])

    orch = AceOrchestrator(
        memory_provider=provider,
        config=OrchestratorConfig(
            memory={
                "profile": {
                    "path": str(profile_path),
                },
                "capture": {
                    "enabled": True,
                    "notes_path": str(notes_path),
                    "min_query_length": 8,
                    "keywords": ["fix", "bug"],
                },
            }
        ),
    )

    payload = _run_memory_stage(
        orch,
        query="please fix bug in auth stage",
        repo="demo",
        root=str(tmp_path),
    )

    assert payload["capture"]["enabled"] is True
    assert payload["capture"]["triggered"] is True
    assert payload["capture"]["captured_items"] == 2
    assert notes_path.exists()

    note_line = notes_path.read_text(encoding="utf-8").strip()
    note_payload = json.loads(note_line)
    assert note_payload["repo"] == "demo"
    assert "fix" in note_payload["matched_keywords"]

    stored_profile = ProfileStore(path=profile_path).load()
    assert stored_profile["recent_contexts"]
    assert stored_profile["recent_contexts"][0]["query"] == "please fix bug in auth stage"


def test_run_memory_capture_failure_downgrade(tmp_path) -> None:
    profile_path = tmp_path / "profile.json"
    notes_dir = tmp_path / "notes_dir"
    notes_dir.mkdir(parents=True, exist_ok=True)
    provider = _FakeMemoryProvider([MemoryRecord(text="hello world", score=0.5)])

    orch = AceOrchestrator(
        memory_provider=provider,
        config=OrchestratorConfig(
            memory={
                "profile": {
                    "path": str(profile_path),
                },
                "capture": {
                    "enabled": True,
                    "notes_path": str(notes_dir),
                    "min_query_length": 8,
                    "keywords": ["fix"],
                },
            }
        ),
    )

    payload = _run_memory_stage(
        orch,
        query="fix auth bug now please",
        repo="demo",
        root=str(tmp_path),
    )

    assert payload["capture"]["enabled"] is True
    assert payload["capture"]["triggered"] is True
    assert payload["capture"]["captured_items"] == 1
    assert "notes_append_error" in str(payload["capture"]["warning"] or "")


def test_run_memory_capture_prunes_expired_notes_before_append(tmp_path) -> None:
    profile_path = tmp_path / "profile.json"
    notes_path = tmp_path / "memory_notes.jsonl"
    notes_path.write_text(
        '{"query":"old issue","repo":"demo","captured_at":"2020-01-01T00:00:00+00:00"}\n',
        encoding="utf-8",
    )
    provider = _FakeMemoryProvider([MemoryRecord(text="hello world", score=0.5)])

    orch = AceOrchestrator(
        memory_provider=provider,
        config=OrchestratorConfig(
            memory={
                "profile": {
                    "path": str(profile_path),
                },
                "capture": {
                    "enabled": True,
                    "notes_path": str(notes_path),
                    "min_query_length": 4,
                    "keywords": ["fix"],
                },
                "notes": {
                    "expiry_enabled": True,
                    "ttl_days": 90,
                    "max_age_days": 365,
                },
            }
        ),
    )

    payload = _run_memory_stage(
        orch,
        query="fix auth now",
        repo="demo",
        root=str(tmp_path),
    )

    assert payload["capture"]["enabled"] is True
    assert payload["capture"]["triggered"] is True
    assert payload["capture"]["captured_items"] == 2
    assert payload["capture"]["notes_pruned_expired_count"] == 1

    rows = [line for line in notes_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
