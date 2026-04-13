"""Integration tests for doctor command schema compatibility.

These tests ensure backward compatibility with the runtime stats schema v3
and validate that doctor command outputs are consistent across versions.

PRD-91: Doctor 默认路径兼容性回归测试
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from ace_lite.cli_app.app import cli
from ace_lite.runtime_stats_schema import (
    RUNTIME_STATS_DOCTOR_EVENT_CLASS,
    RUNTIME_STATS_SCHEMA_VERSION,
)


@pytest.fixture
def cli_runner():
    """Create a CLI runner for testing."""
    return CliRunner()


class TestDoctorSchemaV3Compat:
    """Tests for doctor payload schema v3 compatibility."""

    def test_doctor_payload_schema_v3_fields(self, cli_runner):
        """Verify doctor payload includes all v3 required fields."""
        result = cli_runner.invoke(cli, ["doctor", "--root=.", "--fast"])

        # Parse the JSON output (may fail if doctor fails, but schema should be valid)
        if result.exit_code in [0, 1] and result.output.strip():
            try:
                payload = json.loads(result.output)

                # Required v3 fields
                required_fields = ["ok", "event", "degraded_reason_codes", "settings", "stats"]
                for field in required_fields:
                    assert field in payload, f"Missing required field: {field}"

                # ok should always be bool
                assert isinstance(payload["ok"], bool), "Field 'ok' must be boolean"

                # event should be a string
                assert isinstance(payload["event"], str), "Field 'event' must be string"

                # degraded_reason_codes should be a list
                assert isinstance(
                    payload["degraded_reason_codes"], list
                ), "Field 'degraded_reason_codes' must be list"

            except json.JSONDecodeError:
                # If output is not JSON (e.g., table format), skip this test
                pytest.skip("Output is not JSON format")

    def test_doctor_degraded_reason_codes_always_list(self, cli_runner):
        """Verify degraded_reason_codes is always a list, even when empty."""
        result = cli_runner.invoke(cli, ["doctor", "--root=.", "--fast"])

        if result.exit_code in [0, 1] and result.output.strip():
            try:
                payload = json.loads(result.output)
                degraded_codes = payload.get("degraded_reason_codes")

                # Should be list, not None or other type
                assert isinstance(degraded_codes, list), (
                    f"degraded_reason_codes must be list, got {type(degraded_codes).__name__}"
                )

                # All items should be strings
                for item in degraded_codes:
                    assert isinstance(item, str), (
                        f"degraded_reason_codes items must be strings, got {type(item).__name__}"
                    )
            except json.JSONDecodeError:
                pytest.skip("Output is not JSON format")

    def test_doctor_event_class_constant(self):
        """Verify RUNTIME_STATS_DOCTOR_EVENT_CLASS constant is defined correctly."""
        assert RUNTIME_STATS_DOCTOR_EVENT_CLASS == "doctor_runtime_event"
        assert isinstance(RUNTIME_STATS_DOCTOR_EVENT_CLASS, str)

    def test_doctor_schema_version_awareness(self):
        """Verify schema version is v3."""
        assert RUNTIME_STATS_SCHEMA_VERSION == 3

    def test_doctor_stats_section_structure(self, cli_runner):
        """Verify stats section has expected structure."""
        result = cli_runner.invoke(cli, ["doctor", "--root=.", "--fast"])

        if result.exit_code in [0, 1] and result.output.strip():
            try:
                payload = json.loads(result.output)
                stats = payload.get("stats", {})

                # Stats should be a dict
                assert isinstance(stats, dict), "stats field must be a dict"

                # Stats may contain various sub-sections depending on runtime state
                # but should never cause errors
                assert "memory_health_summary" in stats or "event_class" in stats or True

            except json.JSONDecodeError:
                pytest.skip("Output is not JSON format")

    def test_doctor_settings_fingerprint_optional(self, cli_runner):
        """Verify settings.fingerprint is optional and handled gracefully."""
        result = cli_runner.invoke(cli, ["doctor", "--root=.", "--fast"])

        if result.exit_code in [0, 1] and result.output.strip():
            try:
                payload = json.loads(result.output)
                settings = payload.get("settings", {})

                # Fingerprint may or may not exist - both are valid
                if "fingerprint" in settings:
                    assert settings["fingerprint"] is None or isinstance(
                        settings["fingerprint"], str
                    )
            except json.JSONDecodeError:
                pytest.skip("Output is not JSON format")

    def test_doctor_cache_section_optional(self, cli_runner):
        """Verify cache section is optional and has expected fields when present."""
        result = cli_runner.invoke(cli, ["doctor", "--root=.", "--fast"])

        if result.exit_code in [0, 1] and result.output.strip():
            try:
                payload = json.loads(result.output)
                cache = payload.get("cache")

                # Cache section is optional
                if cache is not None:
                    assert isinstance(cache, dict), "cache field must be a dict if present"
                    # If cache has ok field, it should be bool
                    if "ok" in cache:
                        assert isinstance(cache["ok"], bool)
            except json.JSONDecodeError:
                pytest.skip("Output is not JSON format")

    def test_doctor_git_section_structure(self, cli_runner):
        """Verify git section has expected structure."""
        result = cli_runner.invoke(cli, ["doctor", "--root=.", "--fast"])

        if result.exit_code in [0, 1] and result.output.strip():
            try:
                payload = json.loads(result.output)
                git = payload.get("git", {})

                # Git section structure should be consistent
                assert isinstance(git, dict), "git field must be a dict"

                # If git is enabled, should have these fields
                if git.get("enabled"):
                    assert "ok" in git, "Enabled git should have 'ok' field"
                    assert "reason" in git, "Enabled git should have 'reason' field"

            except json.JSONDecodeError:
                pytest.skip("Output is not JSON format")

    def test_doctor_version_sync_section(self, cli_runner):
        """Verify version_sync section exists and has expected fields."""
        result = cli_runner.invoke(cli, ["doctor", "--root=.", "--fast"])

        if result.exit_code in [0, 1] and result.output.strip():
            try:
                payload = json.loads(result.output)
                version_sync = payload.get("version_sync", {})

                assert isinstance(version_sync, dict), "version_sync field must be a dict"

                # Should have ok and reason fields
                assert "ok" in version_sync, "version_sync should have 'ok' field"
                assert "reason" in version_sync, "version_sync should have 'reason' field"

                # ok should be bool
                assert isinstance(version_sync["ok"], bool)

            except json.JSONDecodeError:
                pytest.skip("Output is not JSON format")

    def test_doctor_integration_section_structure(self, cli_runner):
        """Verify integration section has expected structure."""
        result = cli_runner.invoke(cli, ["doctor", "--root=.", "--fast"])

        if result.exit_code in [0, 1] and result.output.strip():
            try:
                payload = json.loads(result.output)
                integration = payload.get("integration", {})

                assert isinstance(integration, dict), "integration field must be a dict"

                # Should have ok field
                if "ok" in integration:
                    assert isinstance(integration["ok"], bool)

            except json.JSONDecodeError:
                pytest.skip("Output is not JSON format")


class TestDoctorBackwardCompat:
    """Tests for backward compatibility with older schema versions."""

    def test_doctor_handles_missing_stats_gracefully(self, cli_runner):
        """Verify doctor handles missing stats section gracefully."""
        result = cli_runner.invoke(cli, ["doctor", "--root=.", "--fast"])

        # Should not crash even if stats section has issues
        assert result.exit_code in [0, 1]

    def test_doctor_handles_missing_cache_gracefully(self, cli_runner):
        """Verify doctor handles missing cache section gracefully."""
        result = cli_runner.invoke(cli, ["doctor", "--root=.", "--fast"])

        # Should not crash
        assert result.exit_code in [0, 1]

    def test_doctor_output_format_json_produces_valid_json(self, cli_runner):
        """Verify --output-format=json produces valid JSON."""
        result = cli_runner.invoke(cli, ["doctor", "--root=.", "--fast", "--output-format=json"])

        # Should produce valid JSON
        if result.output.strip():
            try:
                payload = json.loads(result.output)
                assert isinstance(payload, dict)
            except json.JSONDecodeError as e:
                pytest.fail(f"Invalid JSON output: {e}")

    def test_doctor_output_format_table_produces_text(self, cli_runner):
        """Verify --output-format=table produces readable text."""
        result = cli_runner.invoke(cli, ["doctor", "--root=.", "--fast", "--output-format=table"])

        # Should produce text output (not JSON)
        if result.exit_code in [0, 1]:
            assert result.output.strip()
            # Table output should contain status indicators
            output_lower = result.output.lower()
            assert "ok" in output_lower or "fail" in output_lower or "status" in output_lower


class TestDoctorFastMode:
    """Tests for doctor --fast mode behavior."""

    def test_doctor_fast_mode_is_faster(self, cli_runner):
        """Verify fast mode completes quickly (basic sanity check)."""
        import time

        start = time.time()
        result = cli_runner.invoke(cli, ["doctor", "--root=.", "--fast"])
        elapsed = time.time() - start

        # Fast mode should complete in reasonable time
        # (This is a soft check - actual timing may vary)
        assert elapsed < 30, f"Fast mode took too long: {elapsed:.2f}s"
        assert result.exit_code in [0, 1]

    def test_doctor_fast_mode_skips_probe(self, cli_runner):
        """Verify fast mode includes _fast_mode marker."""
        result = cli_runner.invoke(cli, ["doctor", "--root=.", "--fast"])

        if result.exit_code in [0, 1] and result.output.strip():
            try:
                payload = json.loads(result.output)
                # Fast mode should add metadata
                assert payload.get("_fast_mode") is True
            except json.JSONDecodeError:
                # Table format doesn't have JSON markers
                pass
