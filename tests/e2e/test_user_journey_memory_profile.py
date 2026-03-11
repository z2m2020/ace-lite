from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ace_lite.memory import LocalNotesProvider
from ace_lite.orchestrator import AceOrchestrator
from ace_lite.orchestrator_config import OrchestratorConfig
from ace_lite.profile_store import ProfileStore


class _EmptyMemoryProvider:
    strategy = "semantic"
    fallback_reason: str | None = None
    last_channel_used = "none"
    last_container_tag_fallback: str | None = None

    def search_compact(
        self,
        query: str,
        *,
        limit: int | None = None,
        container_tag: str | None = None,
    ) -> list[Any]:
        _ = (query, limit, container_tag)
        return []

    def fetch(self, handles: list[str]) -> list[Any]:
        _ = handles
        return []


def _bootstrap_repo(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "repo"
    src_dir = root / "src"
    skills_dir = root / "skills"
    context_dir = root / "context-map"
    src_dir.mkdir(parents=True, exist_ok=True)
    skills_dir.mkdir(parents=True, exist_ok=True)
    context_dir.mkdir(parents=True, exist_ok=True)

    (src_dir / "auth.py").write_text(
        "def validate_token(token: str | None) -> bool:\n"
        "    if token is None:\n"
        "        return False\n"
        "    return len(token) > 0\n",
        encoding="utf-8",
    )
    (skills_dir / "sample.md").write_text(
        "---\nname: sample\nintents: [implement, troubleshoot]\n---\n# Intro\nA\n",
        encoding="utf-8",
    )
    return root, skills_dir, context_dir


def _base_config(
    *,
    skills_dir: Path,
    context_dir: Path,
    **overrides: Any,
) -> OrchestratorConfig:
    return OrchestratorConfig(
        skills={
            "dir": str(skills_dir),
        },
        index={
            "languages": ["python"],
            "cache_path": str(context_dir / "index.json"),
        },
        repomap={
            "enabled": False,
        },
        cochange={
            "enabled": False,
        },
        lsp={
            "enabled": False,
            "xref_enabled": False,
        },
        plugins={
            "enabled": False,
        },
        scip={
            "enabled": False,
        },
        trace={
            "export_enabled": False,
            "otlp_enabled": False,
        },
        **overrides,
    )


def test_user_journey_profile_injection_affects_plan_payload(tmp_path: Path) -> None:
    root, skills_dir, context_dir = _bootstrap_repo(tmp_path)
    profile_path = context_dir / "profile.json"
    store = ProfileStore(path=profile_path)
    store.add_fact(
        "Prefer explicit token refresh and nullable token guards.",
        confidence=0.95,
        source="manual",
    )

    config = _base_config(
        skills_dir=skills_dir,
        context_dir=context_dir,
        memory={
            "profile": {
                "enabled": True,
                "path": str(profile_path),
                "top_n": 3,
                "token_budget": 128,
            }
        },
    )
    orchestrator = AceOrchestrator(config=config)

    payload = orchestrator.plan(
        query="add token refresh handling for auth flow",
        repo="demo",
        root=str(root),
    )
    profile = payload.get("memory", {}).get("profile", {})
    facts = profile.get("facts", []) if isinstance(profile, dict) else []

    assert profile.get("enabled") is True
    assert int(profile.get("selected_count", 0) or 0) >= 1
    assert any("token refresh" in str(item.get("text", "")).lower() for item in facts)


def test_user_journey_memory_capture_and_recall_cycle(tmp_path: Path) -> None:
    root, skills_dir, context_dir = _bootstrap_repo(tmp_path)
    notes_path = context_dir / "memory_notes.jsonl"

    provider = LocalNotesProvider(
        _EmptyMemoryProvider(),
        notes_path=str(notes_path),
        default_limit=5,
        mode="local_only",
        expiry_enabled=False,
    )
    config = _base_config(
        skills_dir=skills_dir,
        context_dir=context_dir,
        memory={
            "capture": {
                "enabled": True,
                "notes_path": str(notes_path),
                "min_query_length": 8,
                "keywords": ["fix", "405", "error"],
            },
            "notes": {
                "enabled": True,
                "path": str(notes_path),
                "mode": "local_only",
                "limit": 5,
                "expiry_enabled": False,
            },
        },
    )
    orchestrator = AceOrchestrator(memory_provider=provider, config=config)

    first = orchestrator.plan(
        query="fix 405 error in API endpoint post method",
        repo="demo",
        root=str(root),
    )
    capture = first.get("memory", {}).get("capture", {})
    assert capture.get("enabled") is True
    assert capture.get("triggered") is True
    assert int(capture.get("captured_items", 0) or 0) >= 1
    assert notes_path.exists()

    second = orchestrator.plan(
        query="api endpoint 405 post method",
        repo="demo",
        root=str(root),
    )
    memory = second.get("memory", {})
    hits_preview = memory.get("hits_preview", []) if isinstance(memory, dict) else []

    assert int(memory.get("count", 0) or 0) >= 1
    assert hits_preview
    assert any("405" in str(item.get("preview", "")).lower() for item in hits_preview)


def test_user_journey_namespace_isolation_for_local_notes(tmp_path: Path) -> None:
    root, skills_dir, context_dir = _bootstrap_repo(tmp_path)
    notes_path = context_dir / "memory_notes.jsonl"
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    notes_payload = [
        {
            "text": "shared auth regression note for project a",
            "namespace": "project-a",
            "captured_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "text": "shared auth regression note for project b",
            "namespace": "project-b",
            "captured_at": datetime.now(timezone.utc).isoformat(),
        },
    ]
    with notes_path.open("w", encoding="utf-8") as fh:
        for row in notes_payload:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    provider_a = LocalNotesProvider(
        _EmptyMemoryProvider(),
        notes_path=str(notes_path),
        default_limit=5,
        mode="local_only",
        expiry_enabled=False,
    )
    config_a = _base_config(
        skills_dir=skills_dir,
        context_dir=context_dir,
        memory={
            "namespace": {
                "container_tag": "project-a",
            },
            "notes": {
                "enabled": True,
                "path": str(notes_path),
                "mode": "local_only",
                "limit": 5,
                "expiry_enabled": False,
            },
        },
    )
    orchestrator_a = AceOrchestrator(memory_provider=provider_a, config=config_a)
    payload_a = orchestrator_a.plan(
        query="shared auth regression note",
        repo="demo",
        root=str(root),
    )
    previews_a = payload_a.get("memory", {}).get("hits_preview", [])
    text_a = " ".join(str(item.get("preview", "")) for item in previews_a).lower()
    assert "project a" in text_a
    assert "project b" not in text_a

    provider_b = LocalNotesProvider(
        _EmptyMemoryProvider(),
        notes_path=str(notes_path),
        default_limit=5,
        mode="local_only",
        expiry_enabled=False,
    )
    config_b = _base_config(
        skills_dir=skills_dir,
        context_dir=context_dir,
        memory={
            "namespace": {
                "container_tag": "project-b",
            },
            "notes": {
                "enabled": True,
                "path": str(notes_path),
                "mode": "local_only",
                "limit": 5,
                "expiry_enabled": False,
            },
        },
    )
    orchestrator_b = AceOrchestrator(memory_provider=provider_b, config=config_b)
    payload_b = orchestrator_b.plan(
        query="shared auth regression note",
        repo="demo",
        root=str(root),
    )
    previews_b = payload_b.get("memory", {}).get("hits_preview", [])
    text_b = " ".join(str(item.get("preview", "")) for item in previews_b).lower()
    assert "project b" in text_b
    assert "project a" not in text_b
