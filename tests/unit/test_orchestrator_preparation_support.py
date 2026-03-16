from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from ace_lite.orchestrator_runtime_support import run_orchestrator_preparation


def test_run_orchestrator_preparation_builds_runtime_inputs(tmp_path: Path) -> None:
    calls: list[str] = []
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "README.md").write_text("# demo\n", encoding="utf-8")

    class _RuntimeState:
        def update_conventions_hashes(self, file_hashes: dict[str, str]) -> None:
            calls.append(f"update:{len(file_hashes)}")

    orchestrator = SimpleNamespace(
        _conventions_files=None,
        _conventions_hashes={},
        _runtime_state=_RuntimeState(),
        _load_plugins=lambda *, root: (SimpleNamespace(name="hook_bus"), ["plugin-a"]),
        _build_registry=lambda: SimpleNamespace(name="registry"),
    )

    result = run_orchestrator_preparation(
        orchestrator=orchestrator,
        query="refactor orchestrator shell",
        repo="demo",
        root=str(repo_root),
        time_range="last_30_days",
        start_date="2026-03-01",
        end_date="2026-03-16",
        filters={"include_paths": ["src/ace_lite/orchestrator.py"]},
    )

    assert result.root_path == str(repo_root.resolve())
    assert result.hook_bus.name == "hook_bus"
    assert result.plugins_loaded == ["plugin-a"]
    assert result.registry.name == "registry"
    assert result.temporal_input == {
        "time_range": "last_30_days",
        "start_date": "2026-03-01",
        "end_date": "2026-03-16",
    }
    assert result.ctx.query == "refactor orchestrator shell"
    assert result.ctx.repo == "demo"
    assert result.ctx.root == str(repo_root.resolve())
    assert result.ctx.state["conventions"] == result.conventions
    assert result.ctx.state["temporal"] == result.temporal_input
    assert result.ctx.state["benchmark_filters"] == {
        "include_paths": ["src/ace_lite/orchestrator.py"]
    }
    assert calls == ["update:0"]
