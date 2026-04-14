from __future__ import annotations

from pathlib import Path


def test_index_stage_entry_delegates_runtime_dep_assembly() -> None:
    index_stage_text = Path("src/ace_lite/pipeline/stages/index.py").read_text(
        encoding="utf-8"
    )

    assert "build_index_stage_runtime_deps(" in index_stage_text
    assert "IndexStageRuntimeDeps(" not in index_stage_text
