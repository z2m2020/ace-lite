from __future__ import annotations

from ace_lite.plan_timeout import (
    build_plan_timeout_fallback_payload,
    resolve_plan_timeout_seconds,
)


def test_resolve_plan_timeout_seconds_prefers_explicit() -> None:
    resolution = resolve_plan_timeout_seconds(
        timeout_seconds=5.0,
        default_timeout_seconds=25.0,
        env={"ACE_LITE_PLAN_TIMEOUT_SECONDS": "99"},
    )

    assert resolution.seconds == 5.0
    assert resolution.source == "explicit"


def test_resolve_plan_timeout_seconds_uses_env() -> None:
    resolution = resolve_plan_timeout_seconds(
        timeout_seconds=None,
        default_timeout_seconds=25.0,
        env={"ACE_LITE_PLAN_TIMEOUT_SECONDS": "7"},
    )

    assert resolution.seconds == 7.0
    assert resolution.source == "env"


def test_build_plan_timeout_fallback_payload_is_schema_compatible(tmp_path) -> None:
    payload = build_plan_timeout_fallback_payload(
        query="timeout case",
        repo="demo",
        root=str(tmp_path),
        candidate_file_paths=["src/app.py"],
        steps=["Inspect candidate files."],
        timeout_seconds=1.0,
        elapsed_ms=1000.0,
        fallback_mode="plan_quick",
        debug_dump_path=None,
    )

    assert payload["schema_version"] == "3.2"
    assert payload["observability"]["error"]["type"] == "plan_timeout"
    assert payload["observability"]["error"]["fallback_mode"] == "plan_quick"

