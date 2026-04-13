from __future__ import annotations

from ace_lite.config_runtime_projection import (
    build_orchestrator_runtime_projection,
    dump_orchestrator_runtime_projection,
    dump_runtime_boundary_projection,
    normalize_orchestrator_runtime_projection,
)


def test_normalize_orchestrator_runtime_projection_parses_csv_and_lsp_commands() -> None:
    normalized = normalize_orchestrator_runtime_projection(
        {
            "index": {
                "languages": "python, go",
                "conventions_files": "AGENTS.md,docs/README.md",
            },
            "lsp": {
                "commands": {"python": "pylsp --stdio"},
                "xref_commands": {"python": ["pyright-xref"]},
            },
        }
    )

    assert normalized["index"]["languages"] == ["python", "go"]
    assert normalized["index"]["conventions_files"] == [
        "AGENTS.md",
        "docs/README.md",
    ]
    assert normalized["lsp"]["commands"] == {"python": ["pylsp", "--stdio"]}
    assert normalized["lsp"]["xref_commands"] == {"python": ["pyright-xref"]}


def test_build_orchestrator_runtime_projection_returns_runtime_model() -> None:
    config = build_orchestrator_runtime_projection(
        {
            "index": {"languages": "python,go"},
            "lsp": {"commands": {"python": "pylsp --stdio"}},
        }
    )

    assert config.index.languages == ["python", "go"]
    assert config.lsp.commands == {"python": ["pylsp", "--stdio"]}


def test_dump_orchestrator_runtime_projection_is_stable_for_runtime_settings() -> None:
    dumped = dump_orchestrator_runtime_projection(
        {
            "index": {"languages": "python,go"},
            "lsp": {"commands": {"python": "pylsp --stdio"}},
        },
        exclude_none=False,
        by_alias=True,
    )

    assert dumped["index"]["languages"] == ["python", "go"]
    assert dumped["lsp"]["commands"] == {"python": ["pylsp", "--stdio"]}


def test_dump_runtime_boundary_projection_validates_runtime_settings_payload() -> None:
    dumped = dump_runtime_boundary_projection(
        {
            "hot_reload": {
                "enabled": True,
                "config_file": ".ace-lite.yml",
                "poll_interval_seconds": 2.5,
                "debounce_ms": 50,
            }
        },
        exclude_none=False,
        by_alias=True,
    )

    assert dumped["hot_reload"]["enabled"] is True
    assert dumped["hot_reload"]["config_file"] == ".ace-lite.yml"
    assert dumped["hot_reload"]["poll_interval_seconds"] == 2.5
    assert dumped["hot_reload"]["debounce_ms"] == 50
