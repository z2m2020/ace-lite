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


def _pip_payload(*, vuln_id: str) -> str:
    payload = {
        "dependencies": [
            {
                "name": "pip",
                "version": "25.3",
                "vulns": [{"id": vuln_id, "fix_versions": ["26.0"]}],
            }
        ]
    }
    return "Found 1 known vulnerabilities in 1 packages\n" + json.dumps(payload)


def test_extract_json_payload_with_prefix_noise() -> None:
    module = _load_script("run_quality_gate.py")
    payload = module._extract_json_payload(_pip_payload(vuln_id="CVE-2026-1703"))

    assert isinstance(payload, dict)
    deps = payload.get("dependencies")
    assert isinstance(deps, list)
    assert deps and deps[0]["name"] == "pip"


def test_run_quality_gate_passes_when_no_new_vulns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_quality_gate.py")
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps(
            {
                "findings": [
                    {
                        "package": "pip",
                        "id": "CVE-2026-1703",
                        "fix_versions": ["26.0"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"

    def fake_run_command(*, name: str, command: list[str], cwd: Path):
        _ = (command, cwd)
        if name == "pip_audit":
            return module.CommandResult(
                name=name,
                command=["pip-audit"],
                returncode=1,
                stdout=_pip_payload(vuln_id="CVE-2026-1703"),
                stderr="",
                elapsed_ms=12.0,
            )
        return module.CommandResult(
            name=name,
            command=[name],
            returncode=0,
            stdout="ok",
            stderr="",
            elapsed_ms=8.0,
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    summary = module.run_quality_gate(
        root=tmp_path,
        output_dir=output_dir,
        baseline_path=baseline_path,
        fail_on_new_vulns=True,
        python_exe=sys.executable,
    )

    assert summary["passed"] is True
    assert summary["pip_audit"]["new_count"] == 0
    assert (output_dir / "logs" / "ruff.stdout.txt").exists()
    assert (output_dir / "logs" / "skills_lint.stdout.txt").exists()
    assert (output_dir / "logs" / "pip_audit.stdout.txt").exists()


def test_main_fails_on_new_vulnerability(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_quality_gate.py")
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps({"findings": []}), encoding="utf-8")
    output_dir = tmp_path / "out"

    def fake_run_command(*, name: str, command: list[str], cwd: Path):
        _ = (command, cwd)
        if name == "pip_audit":
            return module.CommandResult(
                name=name,
                command=["pip-audit"],
                returncode=1,
                stdout=_pip_payload(vuln_id="CVE-2099-0001"),
                stderr="",
                elapsed_ms=11.0,
            )
        return module.CommandResult(
            name=name,
            command=[name],
            returncode=0,
            stdout="ok",
            stderr="",
            elapsed_ms=5.0,
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "run_quality_gate.py",
            "--root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
            "--pip-audit-baseline",
            str(baseline_path),
            "--fail-on-new-vulns",
        ],
    )

    exit_code = module.main()

    assert exit_code == 1
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["passed"] is False
    assert summary["pip_audit"]["new_count"] == 1


def test_run_quality_gate_captures_friction_on_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_quality_gate.py")
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps({"findings": []}), encoding="utf-8")
    output_dir = tmp_path / "out"
    friction_path = tmp_path / "friction.jsonl"

    def fake_run_command(*, name: str, command: list[str], cwd: Path):
        _ = (command, cwd)
        if name == "ruff":
            return module.CommandResult(
                name=name,
                command=[name],
                returncode=1,
                stdout="",
                stderr="lint failed",
                elapsed_ms=50.0,
            )
        if name == "pip_audit":
            return module.CommandResult(
                name=name,
                command=[name],
                returncode=1,
                stdout=_pip_payload(vuln_id="CVE-2099-0002"),
                stderr="",
                elapsed_ms=20.0,
            )
        return module.CommandResult(
            name=name,
            command=[name],
            returncode=0,
            stdout="ok",
            stderr="",
            elapsed_ms=5.0,
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    summary = module.run_quality_gate(
        root=tmp_path,
        output_dir=output_dir,
        baseline_path=baseline_path,
        fail_on_new_vulns=True,
        python_exe=sys.executable,
        friction_log_path=friction_path,
        capture_friction=True,
    )

    assert summary["passed"] is False
    assert summary["friction"]["events_logged"] >= 2
    rows = [
        json.loads(line)
        for line in friction_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows
    assert any(item["root_cause"] == "quality_gate_command_failure" for item in rows)
    assert any(item["root_cause"] == "dependency_vulnerability_regression" for item in rows)


def test_run_quality_gate_emits_report_only_hotspot_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_quality_gate.py")
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps({"findings": []}), encoding="utf-8")
    hotspot_baseline_path = tmp_path / "hotspot-baseline.json"
    hotspot_baseline_path.write_text(
        json.dumps(
            {
                "mode": "report_only",
                "hotspots": [
                    {
                        "path": "src/ace_lite/orchestrator.py",
                        "coverage_percent": 80.0,
                        "complexity_score": 4,
                        "complexity_ceiling": 6,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"
    coverage_path = output_dir / "coverage.json"
    coverage_path.parent.mkdir(parents=True, exist_ok=True)
    coverage_path.write_text(
        json.dumps(
            {
                "files": {
                    "src/ace_lite/orchestrator.py": {
                        "summary": {
                            "covered_lines": 10,
                            "missing_lines": 2,
                            "num_statements": 12,
                            "percent_covered": 83.33,
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    hotspot_path = tmp_path / "src" / "ace_lite" / "orchestrator.py"
    hotspot_path.parent.mkdir(parents=True, exist_ok=True)
    hotspot_path.write_text(
        (
            "def plan(flag: bool) -> int:\n"
            "    if flag:\n"
            "        return 1\n"
            "    return 0\n"
        ),
        encoding="utf-8",
    )

    def fake_run_command(*, name: str, command: list[str], cwd: Path):
        _ = (command, cwd)
        if name == "pip_audit":
            return module.CommandResult(
                name=name,
                command=["pip-audit"],
                returncode=0,
                stdout=json.dumps({"dependencies": []}),
                stderr="",
                elapsed_ms=7.0,
            )
        return module.CommandResult(
            name=name,
            command=[name],
            returncode=0,
            stdout="ok",
            stderr="",
            elapsed_ms=5.0,
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    summary = module.run_quality_gate(
        root=tmp_path,
        output_dir=output_dir,
        baseline_path=baseline_path,
        hotspot_baseline_path=hotspot_baseline_path,
        fail_on_new_vulns=True,
        python_exe=sys.executable,
    )

    hotspot_summary = summary["hotspot_summary"]
    assert hotspot_summary["report_only"] is True
    assert hotspot_summary["baseline_path"] == str(hotspot_baseline_path)
    hotspot_rows = hotspot_summary["hotspots"]
    orchestrator_row = next(
        item for item in hotspot_rows if item["path"] == "src/ace_lite/orchestrator.py"
    )
    assert orchestrator_row["coverage"]["percent"] == pytest.approx(83.33)
    assert orchestrator_row["coverage"]["baseline_percent"] == pytest.approx(80.0)
    assert orchestrator_row["complexity"]["metric"] == "ast_decision_score"
    assert orchestrator_row["complexity"]["score"] >= 2


def test_hotspot_baseline_matches_current_targets() -> None:
    module = _load_script("run_quality_gate.py")
    baseline_path = SCRIPTS_DIR.parent / "benchmark" / "quality" / "hotspot_baseline.json"
    payload = json.loads(baseline_path.read_text(encoding="utf-8"))

    hotspots = payload.get("hotspots")
    assert isinstance(hotspots, list)
    assert [item.get("path") for item in hotspots if isinstance(item, dict)] == module.HOTSPOT_TARGETS
    keyed = {
        item["path"]: item
        for item in hotspots
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    for target in (
        "src/ace_lite/orchestrator.py",
        "src/ace_lite/plan_quick.py",
        "src/ace_lite/benchmark/report.py",
        "src/ace_lite/context_report.py",
    ):
        row = keyed[target]
        assert isinstance(row.get("coverage_percent"), (int, float))
        assert isinstance(row.get("complexity_score"), int)
        assert isinstance(row.get("complexity_ceiling"), int)
        assert int(row["complexity_ceiling"]) >= int(row["complexity_score"])


def test_run_quality_gate_can_refresh_hotspot_baseline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_quality_gate.py")
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps({"findings": []}), encoding="utf-8")
    hotspot_baseline_path = tmp_path / "hotspot-baseline.json"
    output_dir = tmp_path / "out"
    coverage_path = output_dir / "coverage.json"
    coverage_path.parent.mkdir(parents=True, exist_ok=True)
    coverage_path.write_text(
        json.dumps(
            {
                "files": {
                    "src/ace_lite/orchestrator.py": {
                        "summary": {
                            "covered_lines": 10,
                            "missing_lines": 2,
                            "num_statements": 12,
                            "percent_covered": 83.33,
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    hotspot_path = tmp_path / "src" / "ace_lite" / "orchestrator.py"
    hotspot_path.parent.mkdir(parents=True, exist_ok=True)
    hotspot_path.write_text(
        (
            "def plan(flag: bool) -> int:\n"
            "    if flag:\n"
            "        return 1\n"
            "    return 0\n"
        ),
        encoding="utf-8",
    )

    def fake_run_command(*, name: str, command: list[str], cwd: Path):
        _ = (command, cwd)
        if name == "pip_audit":
            return module.CommandResult(
                name=name,
                command=["pip-audit"],
                returncode=0,
                stdout=json.dumps({"dependencies": []}),
                stderr="",
                elapsed_ms=7.0,
            )
        return module.CommandResult(
            name=name,
            command=[name],
            returncode=0,
            stdout="ok",
            stderr="",
            elapsed_ms=5.0,
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    summary = module.run_quality_gate(
        root=tmp_path,
        output_dir=output_dir,
        baseline_path=baseline_path,
        hotspot_baseline_path=hotspot_baseline_path,
        fail_on_new_vulns=True,
        python_exe=sys.executable,
        hotspot_paths=["src/ace_lite/orchestrator.py"],
        refresh_hotspot_baseline=True,
    )

    assert summary["passed"] is True
    payload = json.loads(hotspot_baseline_path.read_text(encoding="utf-8"))
    assert payload["mode"] == "report_only"
    assert payload["hotspots"] == [
        {
            "path": "src/ace_lite/orchestrator.py",
            "coverage_percent": pytest.approx(83.33),
            "complexity_score": 2,
            "complexity_ceiling": 4,
        }
    ]


def test_run_quality_gate_reports_hotspot_checks_without_failing_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_quality_gate.py")
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps({"findings": []}), encoding="utf-8")
    output_dir = tmp_path / "out"

    def fake_run_command(*, name: str, command: list[str], cwd: Path):
        _ = (command, cwd)
        if name == "pip_audit":
            return module.CommandResult(
                name=name,
                command=["pip-audit"],
                returncode=0,
                stdout=json.dumps({"dependencies": []}),
                stderr="",
                elapsed_ms=7.0,
            )
        if name == "ruff_hotspots":
            return module.CommandResult(
                name=name,
                command=["ruff"],
                returncode=1,
                stdout="",
                stderr="hotspot lint failed",
                elapsed_ms=9.0,
            )
        return module.CommandResult(
            name=name,
            command=[name],
            returncode=0,
            stdout="ok",
            stderr="",
            elapsed_ms=5.0,
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    summary = module.run_quality_gate(
        root=tmp_path,
        output_dir=output_dir,
        baseline_path=baseline_path,
        fail_on_new_vulns=True,
        python_exe=sys.executable,
        hotspot_paths=["src/ace_lite/orchestrator.py"],
    )

    assert summary["passed"] is True
    hotspot_checks = summary["hotspot_checks"]
    assert isinstance(hotspot_checks, list)
    assert [item["name"] for item in hotspot_checks] == list(module.HOTSPOT_CHECK_NAMES)
    assert hotspot_checks[0]["report_only"] is True
    assert hotspot_checks[0]["passed"] is False
    assert hotspot_checks[1]["passed"] is True


def test_quality_commands_include_skills_lint_before_mypy(tmp_path: Path) -> None:
    module = _load_script("run_quality_gate.py")
    commands = module._quality_commands(
        python_exe=sys.executable,
        coverage_json_path=tmp_path / "coverage.json",
    )

    names = [name for name, _command in commands]
    assert "skills_lint" in names
    assert names.index("skills_lint") < names.index("mypy")


def test_hotspot_mypy_commands_use_module_targets() -> None:
    module = _load_script("run_quality_gate.py")

    commands = module._quality_hotspot_commands(
        python_exe=sys.executable,
        hotspot_paths=["src/ace_lite/orchestrator.py"],
    )

    assert commands[0][0] == "ruff_hotspots"
    assert commands[0][1][-1] == "src/ace_lite/orchestrator.py"
    assert commands[1][0] == "mypy_hotspots"
    assert commands[1][1][3:] == [
        "ace_lite.orchestrator",
        "ace_lite.orchestrator_runtime_support_types",
        "ace_lite.orchestrator_runtime_finalization",
        "ace_lite.orchestrator_runtime_support",
        "ace_lite.cli_app.orchestrator_factory_support",
        "ace_lite.cli_app.orchestrator_factory",
    ]


def test_main_accepts_hotspot_path_arguments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_quality_gate.py")
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps({"findings": []}), encoding="utf-8")
    hotspot_baseline_path = tmp_path / "hotspot-baseline.json"
    hotspot_baseline_path.write_text(
        json.dumps(
            {
                "mode": "report_only",
                "hotspots": [
                    {"path": "src/ace_lite/orchestrator.py"},
                    {"path": "src/ace_lite/plan_quick.py"},
                ],
            }
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"

    def fake_run_command(*, name: str, command: list[str], cwd: Path):
        _ = cwd
        if name == "pip_audit":
            return module.CommandResult(
                name=name,
                command=command,
                returncode=0,
                stdout=json.dumps({"dependencies": []}),
                stderr="",
                elapsed_ms=7.0,
            )
        return module.CommandResult(
            name=name,
            command=command,
            returncode=0,
            stdout="ok",
            stderr="",
            elapsed_ms=5.0,
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "run_quality_gate.py",
            "--root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
            "--pip-audit-baseline",
            str(baseline_path),
            "--hotspot-baseline",
            str(hotspot_baseline_path),
            "--hotspot-path",
            "src/ace_lite/orchestrator.py",
            "--hotspot-path",
            "src/ace_lite/plan_quick.py",
        ],
    )

    exit_code = module.main()

    assert exit_code == 0
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    hotspot_checks = summary["hotspot_checks"]
    assert hotspot_checks[0]["command"][-2:] == [
        "src/ace_lite/orchestrator.py",
        "src/ace_lite/plan_quick.py",
    ]
    assert hotspot_checks[1]["command"][3:] == [
        "ace_lite.orchestrator",
        "ace_lite.plan_quick",
        "ace_lite.orchestrator_runtime_support_types",
        "ace_lite.orchestrator_runtime_finalization",
        "ace_lite.orchestrator_runtime_support",
        "ace_lite.cli_app.orchestrator_factory_support",
        "ace_lite.cli_app.orchestrator_factory",
    ]
    hotspot_paths = [item["path"] for item in summary["hotspot_summary"]["hotspots"]]
    assert hotspot_paths[:2] == [
        "src/ace_lite/orchestrator.py",
        "src/ace_lite/plan_quick.py",
    ]
