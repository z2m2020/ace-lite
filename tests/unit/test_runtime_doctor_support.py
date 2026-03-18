from __future__ import annotations

from ace_lite.cli_app import runtime_doctor_support
from ace_lite.cli_app.runtime_command_support import (
    build_runtime_cache_doctor_payload,
    build_runtime_cache_vacuum_payload,
    build_runtime_doctor_payload,
)


def test_runtime_doctor_support_facade_reexports_doctor_helpers() -> None:
    assert build_runtime_cache_doctor_payload is runtime_doctor_support.build_runtime_cache_doctor_payload
    assert build_runtime_cache_vacuum_payload is runtime_doctor_support.build_runtime_cache_vacuum_payload
    assert build_runtime_doctor_payload is runtime_doctor_support.build_runtime_doctor_payload
