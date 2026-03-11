from __future__ import annotations

import os
import subprocess
from pathlib import Path

from ace_lite.lsp.broker import LspDiagnosticsBroker
from ace_lite.pipeline.stages.augment import run_diagnostics_augment


def test_run_diagnostics_augment_disabled() -> None:
    payload = run_diagnostics_augment(
        root=".",
        query="q",
        index_stage={},
        enabled=False,
        top_n=5,
        broker=None,
        xref_enabled=False,
        xref_top_n=2,
        xref_time_budget_ms=100,
    )

    assert payload["enabled"] is False
    assert payload["reason"] == "disabled"
    assert payload["count"] == 0


def test_run_diagnostics_augment_broker_unavailable() -> None:
    payload = run_diagnostics_augment(
        root=".",
        query="q",
        index_stage={},
        enabled=True,
        top_n=5,
        broker=None,
        xref_enabled=True,
        xref_top_n=2,
        xref_time_budget_ms=100,
    )

    assert payload["enabled"] is False
    assert payload["reason"] == "broker_unavailable"


def test_run_diagnostics_augment_uses_broker() -> None:
    class _Broker:
        def collect(self, *, root, candidate_files, top_n):
            return {
                "count": 1,
                "diagnostics": [
                    {
                        "path": "src/app.py",
                        "language": "python",
                        "severity": "error",
                        "message": "boom",
                    }
                ],
                "errors": [],
            }

        def collect_xref(self, *, root, query, candidate_files, top_n, time_budget_ms):
            return {
                "count": 1,
                "results": [{"path": "src/app.py", "query": query}],
                "errors": [],
                "budget_exhausted": False,
                "elapsed_ms": 1.0,
                "time_budget_ms": time_budget_ms,
            }

    payload = run_diagnostics_augment(
        root=".",
        query="hello",
        index_stage={"candidate_files": [{"path": "src/app.py", "language": "python"}]},
        enabled=True,
        top_n=1,
        broker=_Broker(),
        xref_enabled=True,
        xref_top_n=1,
        xref_time_budget_ms=120,
    )

    assert payload["enabled"] is True
    assert payload["count"] == 1
    assert payload["diagnostics"][0]["path"] == "src/app.py"
    assert payload["xref"]["count"] == 1


def test_lsp_broker_collect_error_diagnostic(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "app.py").write_text("print('x')\n", encoding="utf-8")

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="E999")

    monkeypatch.setattr("ace_lite.lsp.broker.subprocess.run", fake_run)

    broker = LspDiagnosticsBroker(commands={"python": ["fake-lint"]}, timeout_seconds=1.0)
    payload = broker.collect(
        root=tmp_path,
        candidate_files=[{"path": "src/app.py", "language": "python"}],
        top_n=1,
    )

    assert payload["count"] == 1
    assert payload["diagnostics"][0]["message"] == "E999"


def test_lsp_broker_collect_handles_timeout(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "app.py").write_text("print('x')\n", encoding="utf-8")

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["fake"], timeout=1)

    monkeypatch.setattr("ace_lite.lsp.broker.subprocess.run", fake_run)

    broker = LspDiagnosticsBroker(commands={"python": ["fake-lint"]}, timeout_seconds=1.0)
    payload = broker.collect(
        root=tmp_path,
        candidate_files=[{"path": "src/app.py", "language": "python"}],
        top_n=1,
    )

    assert payload["count"] == 0
    assert payload["errors"]
    assert "timed out" in payload["errors"][0]


def test_lsp_broker_collect_xref(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "app.py").write_text("print('x')\n", encoding="utf-8")

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="xref-hit", stderr="")

    monkeypatch.setattr("ace_lite.lsp.broker.subprocess.run", fake_run)

    broker = LspDiagnosticsBroker(
        commands={"python": ["fake-lint"]},
        xref_commands={"python": ["xref", "{file}", "{query}"]},
        timeout_seconds=1.0,
    )
    payload = broker.collect_xref(
        root=tmp_path,
        query="token",
        candidate_files=[{"path": "src/app.py", "language": "python"}],
        top_n=1,
        time_budget_ms=100,
    )

    assert payload["count"] == 1
    assert payload["results"][0]["message"] == "xref-hit"


def test_lsp_broker_collect_reuses_cache(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "app.py").write_text("print('x')\n", encoding="utf-8")

    calls = {"count": 0}

    def fake_run(*args, **kwargs):
        calls["count"] += 1
        return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="E999")

    monkeypatch.setattr("ace_lite.lsp.broker.subprocess.run", fake_run)

    broker = LspDiagnosticsBroker(
        commands={"python": ["fake-lint"]},
        timeout_seconds=1.0,
        cache_ttl_seconds=60.0,
    )
    first = broker.collect(
        root=tmp_path,
        candidate_files=[{"path": "src/app.py", "language": "python"}],
        top_n=1,
    )
    second = broker.collect(
        root=tmp_path,
        candidate_files=[{"path": "src/app.py", "language": "python"}],
        top_n=1,
    )

    assert calls["count"] == 1
    assert first["cache_hits"] == 0
    assert second["cache_hits"] == 1
    assert second["count"] == 1


def test_lsp_broker_collect_invalidates_cache_on_file_change(
    monkeypatch, tmp_path: Path
) -> None:
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    target = tmp_path / "src" / "app.py"
    target.write_text("print('x')\n", encoding="utf-8")

    calls = {"count": 0}

    def fake_run(*args, **kwargs):
        calls["count"] += 1
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("ace_lite.lsp.broker.subprocess.run", fake_run)

    broker = LspDiagnosticsBroker(
        commands={"python": ["fake-lint"]},
        timeout_seconds=1.0,
        cache_ttl_seconds=60.0,
    )
    broker.collect(
        root=tmp_path,
        candidate_files=[{"path": "src/app.py", "language": "python"}],
        top_n=1,
    )

    previous_mtime = target.stat().st_mtime_ns
    target.write_text("print('y')\n", encoding="utf-8")
    os.utime(
        target,
        ns=(previous_mtime + 1_000_000_000, previous_mtime + 1_000_000_000),
    )

    broker.collect(
        root=tmp_path,
        candidate_files=[{"path": "src/app.py", "language": "python"}],
        top_n=1,
    )

    assert calls["count"] == 2
