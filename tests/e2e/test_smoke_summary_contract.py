"""E2E smoke_summary contract test (ALH1-0204.T3).

Verifies that the smoke_summary_v1 artifact is produced when running the
smoke pipeline and conforms to the expected schema.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


class TestSmokeSummaryContract:
    """E2E contract test for smoke_summary_v1 artifact."""

    def test_smoke_script_produces_smoke_summary(self, tmp_path: Path) -> None:
        """Run smoke_summary.py on a fixture plan JSON and verify schema."""
        # Locate fixture
        fixtures_dir = Path(__file__).resolve().parents[1] / "fixtures" / "smoke"
        plan_fixture = fixtures_dir / "plan_success.json"
        if not plan_fixture.exists():
            pytest.skip(f"fixture not found: {plan_fixture}")

        output_dir = tmp_path / "smoke"
        output_path = output_dir / "smoke_summary.json"

        # Run smoke_summary.py
        result = subprocess.run(
            [
                sys.executable,
                "scripts/smoke_summary.py",
                "--input",
                str(plan_fixture),
                "--output",
                str(output_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"smoke_summary.py failed: {result.stderr}"
        assert output_path.exists(), "smoke_summary.json was not written"

        # Validate schema
        summary = json.loads(output_path.read_text(encoding="utf-8"))
        assert summary["schema_version"] == "smoke_summary_v1"
        assert "generated_at" in summary
        assert "smoke" in summary
        assert "healthy" in summary

        smoke = summary["smoke"]
        assert isinstance(smoke["timed_out"], bool)
        assert isinstance(smoke["is_quick"], bool)
        assert isinstance(smoke["elapsed_ms"], (float, int)) or smoke["elapsed_ms"] is None
        assert isinstance(smoke["file_count"], int)
        assert isinstance(smoke["step_count"], int)
        assert isinstance(smoke["has_validation"], bool)
        assert isinstance(smoke["validation_passed"], bool)

    def test_smoke_summary_rejects_missing_input(self, tmp_path: Path) -> None:
        """Missing input file should exit with an error, not crash."""
        bad_input = tmp_path / "nonexistent.json"
        output_path = tmp_path / "out.json"
        result = subprocess.run(
            [
                sys.executable,
                "scripts/smoke_summary.py",
                "--input",
                str(bad_input),
                "--output",
                str(output_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "not found" in result.stderr

    def test_smoke_summary_timeout_record(self, tmp_path: Path) -> None:
        """Timeout fixture should produce a smoke_summary with healthy=False."""
        fixtures_dir = Path(__file__).resolve().parents[1] / "fixtures" / "smoke"
        plan_fixture = fixtures_dir / "plan_timeout.json"
        if not plan_fixture.exists():
            pytest.skip(f"fixture not found: {plan_fixture}")

        output_dir = tmp_path / "smoke"
        output_path = output_dir / "smoke_summary.json"

        result = subprocess.run(
            [
                sys.executable,
                "scripts/smoke_summary.py",
                "--input",
                str(plan_fixture),
                "--output",
                str(output_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        summary = json.loads(output_path.read_text(encoding="utf-8"))
        assert summary["healthy"] is False
        assert summary["smoke"]["timed_out"] is True
        assert summary["smoke"]["file_count"] == 0
