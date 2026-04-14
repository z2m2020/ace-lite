from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from ace_lite.orchestrator_memory_context_service import MemoryContextService
from ace_lite.pipeline.types import StageContext
from ace_lite.profile_store import ProfileStore


def _build_service(
    *,
    root: Path,
    container_tag: str = "",
    auto_tag_mode: str = "disabled",
    feedback_enabled: bool = False,
    long_term_capture_service: object | None = None,
) -> MemoryContextService:
    return MemoryContextService(
        config=SimpleNamespace(
            memory=SimpleNamespace(
                namespace=SimpleNamespace(
                    container_tag=container_tag,
                    auto_tag_mode=auto_tag_mode,
                ),
                profile=SimpleNamespace(
                    enabled=False,
                    path=str(root / "profile.json"),
                    top_n=3,
                    token_budget=128,
                    expiry_enabled=False,
                    ttl_days=30,
                    max_age_days=365,
                ),
                capture=SimpleNamespace(
                    enabled=False,
                    notes_path=str(root / "memory_notes.jsonl"),
                ),
                notes=SimpleNamespace(
                    expiry_enabled=True,
                    ttl_days=90,
                    max_age_days=365,
                ),
                feedback=SimpleNamespace(
                    enabled=feedback_enabled,
                    path=str(root / "feedback.jsonl"),
                    max_entries=50,
                ),
            )
        ),
        long_term_capture_service=long_term_capture_service,
        durable_stats_session_id="session-123",
    )


def test_resolve_memory_namespace_uses_repo_auto_tag(tmp_path: Path) -> None:
    service = _build_service(root=tmp_path, auto_tag_mode="repo")

    container_tag, namespace_mode, namespace_source = service.resolve_memory_namespace(
        repo="Ace Lite Engine",
        root=str(tmp_path),
    )

    assert container_tag == "repo:ace-lite-engine"
    assert namespace_mode == "repo"
    assert namespace_source == "auto"


def test_capture_memory_signal_writes_recent_context_and_notes(tmp_path: Path) -> None:
    service = _build_service(root=tmp_path)

    payload = service.capture_memory_signal(
        query="please fix auth bug",
        repo="demo",
        root=str(tmp_path),
        namespace="repo:demo",
        matched_keywords=["fix", "bug"],
    )

    assert payload["enabled"] is True
    assert payload["triggered"] is True
    assert payload["captured_items"] == 2
    assert payload["warning"] is None

    note_line = (tmp_path / "memory_notes.jsonl").read_text(encoding="utf-8").strip()
    note_payload = json.loads(note_line)
    assert note_payload["repo"] == "demo"
    assert note_payload["namespace"] == "repo:demo"

    stored_profile = ProfileStore(path=tmp_path / "profile.json").load()
    assert stored_profile["recent_contexts"][0]["query"] == "please fix auth bug"


def test_capture_memory_signal_downgrades_notes_append_error(tmp_path: Path) -> None:
    service = _build_service(root=tmp_path)
    notes_dir = tmp_path / "notes_dir"
    notes_dir.mkdir(parents=True, exist_ok=True)
    service.config.memory.capture.notes_path = str(notes_dir)

    payload = service.capture_memory_signal(
        query="fix auth bug now",
        repo="demo",
        root=str(tmp_path),
        namespace="repo:demo",
        matched_keywords=["fix"],
    )

    assert payload["enabled"] is True
    assert payload["triggered"] is True
    assert payload["captured_items"] == 1
    assert "notes_append_error" in str(payload["warning"] or "")


def test_build_profile_payload_injects_facts_deterministically(tmp_path: Path) -> None:
    service = _build_service(root=tmp_path)
    service.config.memory.profile.enabled = True
    service.config.memory.profile.top_n = 2
    service.config.memory.profile.token_budget = 20
    store = ProfileStore(path=tmp_path / "profile.json")
    store.add_fact("beta preference", confidence=0.7)
    store.add_fact("alpha preference", confidence=0.9)
    store.add_fact("gamma preference", confidence=0.4)

    payload = service.build_profile_payload(
        root=str(tmp_path),
        tokenizer_model="gpt-4o-mini",
    )

    assert payload["enabled"] is True
    assert payload["selected_count"] == 2
    assert [fact["text"] for fact in payload["facts"]] == [
        "alpha preference",
        "beta preference",
    ]


def test_build_profile_payload_returns_error_payload_when_store_resolution_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    service = _build_service(root=tmp_path)
    service.config.memory.profile.enabled = True
    monkeypatch.setattr(
        MemoryContextService,
        "resolve_profile_store",
        lambda self, *, root: (_ for _ in ()).throw(RuntimeError("profile-store-boom")),
    )

    payload = service.build_profile_payload(
        root=str(tmp_path),
        tokenizer_model="gpt-4o-mini",
    )

    assert payload["enabled"] is True
    assert payload["error"] == "profile-store-boom"
    assert payload["facts"] == []
    assert payload["selected_count"] == 0
    assert payload["selected_est_tokens_total"] == 0


def test_build_capture_payload_preserves_reason_for_non_triggered_capture(
    tmp_path: Path,
) -> None:
    service = _build_service(root=tmp_path)
    service.config.memory.capture.enabled = True

    payload = service.build_capture_payload(
        query="fix auth bug now",
        repo="demo",
        root=str(tmp_path),
        namespace="repo:demo",
        matched_keywords=["fix"],
        triggered=False,
        reason="min_query_length_guard",
        query_length=16,
    )

    assert payload == {
        "enabled": True,
        "triggered": False,
        "namespace": "repo:demo",
        "matched_keywords": ["fix"],
        "captured_items": 0,
        "reason": "min_query_length_guard",
        "query_length": 16,
        "warning": None,
    }


def test_attach_memory_stage_payloads_combines_profile_and_capture(
    tmp_path: Path,
) -> None:
    service = _build_service(root=tmp_path)
    service.config.memory.profile.enabled = True
    service.config.memory.profile.top_n = 1
    service.config.memory.profile.token_budget = 20
    service.config.memory.capture.enabled = True
    store = ProfileStore(path=tmp_path / "profile.json")
    store.add_fact("alpha preference", confidence=0.9)

    payload = service.attach_memory_stage_payloads(
        payload={"results": []},
        query="fix auth bug now",
        repo="demo",
        root=str(tmp_path),
        namespace="repo:demo",
        matched_keywords=["fix"],
        triggered=False,
        reason="min_query_length_guard",
        query_length=16,
        tokenizer_model="gpt-4o-mini",
    )

    assert payload["profile"]["enabled"] is True
    assert payload["profile"]["selected_count"] == 1
    assert payload["capture"] == {
        "enabled": True,
        "triggered": False,
        "namespace": "repo:demo",
        "matched_keywords": ["fix"],
        "captured_items": 0,
        "reason": "min_query_length_guard",
        "query_length": 16,
        "warning": None,
    }


def test_capture_long_term_stage_observation_passes_session_run_id(tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    class _CaptureService:
        def capture_stage_observation(self, **kwargs: object) -> dict[str, object]:
            captured.update(kwargs)
            return {"ok": True, "stage": str(kwargs["stage_name"])}

    service = _build_service(
        root=tmp_path,
        long_term_capture_service=_CaptureService(),
    )

    payload = service.capture_long_term_stage_observation(
        stage_name="source_plan",
        ctx=StageContext(query="q", repo="demo", root=str(tmp_path)),
        stage_payload={"steps": []},
    )

    assert payload == {"ok": True, "stage": "source_plan"}
    assert captured["source_run_id"] == "session-123"
    assert captured["repo"] == "demo"


def test_capture_long_term_stage_observation_downgrades_capture_error(
    tmp_path: Path,
) -> None:
    class _CaptureService:
        def capture_stage_observation(self, **kwargs: object) -> dict[str, object]:
            raise RuntimeError("ltm-capture-boom")

    service = _build_service(
        root=tmp_path,
        long_term_capture_service=_CaptureService(),
    )

    payload = service.capture_long_term_stage_observation(
        stage_name="validation",
        ctx=StageContext(query="q", repo="demo", root=str(tmp_path)),
        stage_payload={"steps": []},
    )

    assert payload == {
        "ok": False,
        "stage": "validation",
        "reason": "capture_failed:RuntimeError",
        "message": "ltm-capture-boom",
    }
