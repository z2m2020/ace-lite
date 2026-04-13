from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"


def _load_script(name: str):
    module_name = f"script_{name.replace('.', '_')}"
    module_path = SCRIPTS_DIR / name
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_build_baseline_summary_extracts_phase_zero_metrics(tmp_path: Path) -> None:
    module = _load_script("generate_quality_optimization_baseline.py")
    output_dir = tmp_path / "artifacts" / "quality-optimization" / "baseline"
    paths = module._default_paths(
        root=tmp_path,
        output_dir=output_dir,
        snapshot_date=module.date(2026, 4, 13),
    )
    payload = module.build_baseline_summary(
        manifest_payload={
            "metrics": {"a": {}, "b": {}},
            "streams": {"A": {}},
            "phases": {"Phase 0": {}},
        },
        hotspot_payload={
            "scan_summary": {
                "M-ARCH-01": {"total_count": 12},
                "M-CACHE-01": {"total_count": 4},
                "M-REL-01": {"total_count": 9},
            }
        },
        root=tmp_path,
        paths=paths,
        snapshot_date=module.date(2026, 4, 13),
    )

    assert payload["tasks"]["QO-0001"]["status"] == "completed"
    assert payload["metrics"]["dict_fallback_sites"]["count"] == 12
    assert payload["metrics"]["cache_deepcopy_count"]["count"] == 4
    assert payload["metrics"]["broad_exception_sites"]["count"] == 9
    assert payload["snapshot_date"] == "2026-04-13"


def test_run_quality_optimization_baseline_writes_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("generate_quality_optimization_baseline.py")
    repo_root = tmp_path / "repo"
    output_dir = repo_root / "artifacts" / "quality-optimization" / "baseline"
    (repo_root / "scripts").mkdir(parents=True, exist_ok=True)

    def fake_run_command(*, name: str, command: list[str], cwd: Path):
        _ = cwd
        output_path = Path(command[command.index("--output") + 1])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if name == "quality_benchmark_manifest":
            output_path.write_text(
                json.dumps(
                    {
                        "metrics": {"M-ARCH-01": {}, "M-CACHE-01": {}, "M-REL-01": {}},
                        "streams": {"A": {}, "B": {}},
                        "phases": {"Phase 0": {}, "Phase 1": {}},
                    }
                ),
                encoding="utf-8",
            )
        else:
            output_path.write_text(
                json.dumps(
                    {
                        "scan_summary": {
                            "M-ARCH-01": {"total_count": 20},
                            "M-CACHE-01": {"total_count": 5},
                            "M-REL-01": {"total_count": 11},
                        }
                    }
                ),
                encoding="utf-8",
            )
        return module.CommandResult(
            name=name,
            command=command,
            returncode=0,
            stdout="ok",
            stderr="",
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    result = module.run_quality_optimization_baseline(
        root=repo_root,
        output_dir=output_dir,
        snapshot_date="2026-04-13",
    )

    baseline_path = Path(result["baseline_path"])
    dated_path = Path(result["dated_baseline_path"])
    assert baseline_path.exists()
    assert dated_path.exists()

    payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert payload["metrics"]["dict_fallback_sites"]["count"] == 20
    assert payload["metrics"]["cache_deepcopy_count"]["count"] == 5
    assert payload["metrics"]["broad_exception_sites"]["count"] == 11
    assert payload["tasks"]["QO-0003"]["status"] == "completed"
