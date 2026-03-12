from __future__ import annotations

from pathlib import Path

from ace_lite.cli_app.orchestrator_factory import create_orchestrator
from ace_lite.memory import NullMemoryProvider
from ace_lite.orchestrator_config import OrchestratorConfig
from ace_lite.runtime_manager import RuntimeManager


def test_runtime_manager_startup_reuses_shared_service_bundle(
    fake_skill_manifest: list[dict[str, object]],
    tmp_path: Path,
) -> None:
    provider = NullMemoryProvider()
    config = OrchestratorConfig(
        skills={"manifest": fake_skill_manifest},
        index={
            "languages": ["python"],
            "cache_path": tmp_path / "context-map" / "index.json",
            "conventions_files": ["AGENTS.md"],
        },
    )
    manager = RuntimeManager(config=config, memory_provider=provider)

    first = manager.startup()
    second = manager.startup()

    assert first is second
    assert first.config is config
    assert first.services.memory_provider is provider
    assert first.services.plugin_integration_manager is not None
    assert first.services.skill_manifest == fake_skill_manifest
    assert first.conventions_files == ["AGENTS.md"]
    assert first.durable_stats_session_id.startswith("session-")


def test_runtime_manager_shutdown_runs_registered_hooks_once(
    fake_skill_manifest: list[dict[str, object]],
) -> None:
    manager = RuntimeManager(
        config=OrchestratorConfig(skills={"manifest": fake_skill_manifest})
    )
    state = manager.startup()
    calls: list[str] = []

    def first_hook(current_state: object) -> None:
        assert current_state is state
        calls.append("first")

    def second_hook(current_state: object) -> None:
        assert current_state is state
        calls.append("second")

    manager.register_shutdown_hook(first_hook)
    manager.register_shutdown_hook(second_hook)

    first_summary = manager.shutdown()
    second_summary = manager.shutdown()

    assert calls == ["second", "first"]
    assert first_summary["executed_count"] == 2
    assert first_summary["errors"] == []
    assert second_summary == first_summary


def test_create_orchestrator_uses_runtime_manager_path() -> None:
    orchestrator = create_orchestrator()

    assert orchestrator._runtime_manager is not None
    assert orchestrator._runtime_state is not None
    assert orchestrator._runtime_manager.startup() is orchestrator._runtime_state
