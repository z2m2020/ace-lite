"""Tests for scripts/smoke_summary.py (ALH1-0204.T1)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest


def _load_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "smoke_summary.py"
    spec = importlib.util.spec_from_file_location("smoke_summary_script", script_path)
    if spec is None or spec.loader is None:
        raise AssertionError("failed to load smoke_summary.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# extract_smoke_record
# ---------------------------------------------------------------------------


class TestExtractSmokeRecord:
    def _rec(self, payload: dict) -> dict:
        module = _load_module()
        return module.extract_smoke_record(payload)

    def test_normal_run(self) -> None:
        payload = {
            "elapsed_ms": 1243.5,
            "_plan_timeout_fallback": False,
            "source_plan": {
                "candidate_files": ["a.py", "b.py"],
                "steps": [{"id": "s1"}, {"id": "s2"}],
                "validation": {"passed": True},
            },
            "quick_plan": {"hit": True},
        }
        rec = self._rec(payload)
        assert rec["timed_out"] is False
        assert rec["is_quick"] is True
        assert rec["elapsed_ms"] == 1243.5
        assert rec["file_count"] == 2
        assert rec["step_count"] == 2
        assert rec["has_validation"] is True
        assert rec["validation_passed"] is True

    def test_timeout_fallback(self) -> None:
        payload = {
            "_plan_timeout_fallback": True,
            "source_plan": {"candidate_files": [], "steps": []},
        }
        rec = self._rec(payload)
        assert rec["timed_out"] is True
        assert rec["file_count"] == 0
        assert rec["step_count"] == 0

    def test_no_candidate_files(self) -> None:
        payload = {
            "_plan_timeout_fallback": False,
            "source_plan": {"candidate_files": None, "steps": [{"id": "s1"}]},
        }
        rec = self._rec(payload)
        assert rec["file_count"] == 0
        assert rec["step_count"] == 1

    def test_no_validation(self) -> None:
        payload = {
            "_plan_timeout_fallback": False,
            "source_plan": {"candidate_files": ["a.py"], "steps": [], "validation": None},
        }
        rec = self._rec(payload)
        assert rec["has_validation"] is False
        assert rec["validation_passed"] is False

    def test_validation_failed(self) -> None:
        payload = {
            "_plan_timeout_fallback": False,
            "source_plan": {
                "candidate_files": ["a.py"],
                "steps": [],
                "validation": {"passed": False},
            },
        }
        rec = self._rec(payload)
        assert rec["has_validation"] is True
        assert rec["validation_passed"] is False

    def test_elapsed_ms_from_observability(self) -> None:
        payload = {
            "_plan_timeout_fallback": False,
            "observability": {"elapsed_ms": 987.6},
            "source_plan": {"candidate_files": ["a.py"], "steps": []},
        }
        rec = self._rec(payload)
        assert rec["elapsed_ms"] == 987.6

    def test_elapsed_ms_from_stages(self) -> None:
        payload = {
            "_plan_timeout_fallback": False,
            "stages": [
                {"name": "retrieve", "elapsed_ms": 100.0},
                {"name": "rank", "elapsed_ms": 50.0},
            ],
            "source_plan": {"candidate_files": ["a.py"], "steps": []},
        }
        rec = self._rec(payload)
        assert rec["elapsed_ms"] == 150.0

    def test_outcome_label(self) -> None:
        payload = {
            "_plan_timeout_fallback": False,
            "outcome_label": "plan_quick_success",
            "source_plan": {"candidate_files": ["a.py"], "steps": []},
        }
        rec = self._rec(payload)
        assert rec["outcome_label"] == "plan_quick_success"


# ---------------------------------------------------------------------------
# _is_healthy
# ---------------------------------------------------------------------------


class TestIsHealthy:
    def _healthy(self, record: dict) -> bool:
        module = _load_module()
        return module._is_healthy(record)

    def test_healthy(self) -> None:
        record = {
            "timed_out": False,
            "file_count": 3,
            "step_count": 2,
            "has_validation": True,
            "validation_passed": True,
        }
        assert self._healthy(record) is True

    def test_timed_out_is_unhealthy(self) -> None:
        record = {
            "timed_out": True,
            "file_count": 3,
            "step_count": 2,
        }
        assert self._healthy(record) is False

    def test_no_files_is_unhealthy(self) -> None:
        record = {
            "timed_out": False,
            "file_count": 0,
            "step_count": 2,
        }
        assert self._healthy(record) is False

    def test_no_steps_is_unhealthy(self) -> None:
        record = {
            "timed_out": False,
            "file_count": 3,
            "step_count": 0,
        }
        assert self._healthy(record) is False


# ---------------------------------------------------------------------------
# build_smoke_summary
# ---------------------------------------------------------------------------


class TestBuildSmokeSummary:
    def _summary(self, tmp_path: Path) -> dict:
        module = _load_module()
        plan_file = tmp_path / "plan.json"
        _write_json(
            plan_file,
            {
                "elapsed_ms": 1243.5,
                "_plan_timeout_fallback": False,
                "source_plan": {
                    "candidate_files": ["a.py", "b.py"],
                    "steps": [{"id": "s1"}],
                    "validation": {"passed": True},
                },
            },
        )
        return module.build_smoke_summary(plan_file)

    def test_build_smoke_summary_schema(self, tmp_path: Path) -> None:
        summary = self._summary(tmp_path)
        assert summary["schema_version"] == "smoke_summary_v1"
        assert "generated_at" in summary
        assert "plan_input" in summary
        assert "smoke" in summary
        assert "healthy" in summary

    def test_build_smoke_summary_healthy(self, tmp_path: Path) -> None:
        summary = self._summary(tmp_path)
        assert summary["healthy"] is True
        assert summary["smoke"]["timed_out"] is False
        assert summary["smoke"]["file_count"] == 2

    def test_build_smoke_summary_unhealthy_on_timeout(self, tmp_path: Path) -> None:
        module = _load_module()
        plan_file = tmp_path / "plan.json"
        _write_json(
            plan_file,
            {"_plan_timeout_fallback": True, "source_plan": {"candidate_files": [], "steps": []}},
        )
        summary = module.build_smoke_summary(plan_file)
        assert summary["healthy"] is False
        assert summary["smoke"]["timed_out"] is True
