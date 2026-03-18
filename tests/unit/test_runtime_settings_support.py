from ace_lite.cli_app import runtime_settings_support
from ace_lite.cli_app.runtime_command_support import (
    build_runtime_settings_payload,
    collect_runtime_settings_show_payload,
    evaluate_runtime_memory_state,
    load_runtime_snapshot,
    resolve_effective_runtime_skills_dir,
    resolve_runtime_settings_bundle,
)


def test_runtime_settings_support_facade_reexports_settings_helpers() -> None:
    assert build_runtime_settings_payload is runtime_settings_support.build_runtime_settings_payload
    assert (
        collect_runtime_settings_show_payload
        is runtime_settings_support.collect_runtime_settings_show_payload
    )
    assert evaluate_runtime_memory_state is runtime_settings_support.evaluate_runtime_memory_state
    assert load_runtime_snapshot is runtime_settings_support.load_runtime_snapshot
    assert (
        resolve_effective_runtime_skills_dir
        is runtime_settings_support.resolve_effective_runtime_skills_dir
    )
    assert resolve_runtime_settings_bundle is runtime_settings_support.resolve_runtime_settings_bundle
