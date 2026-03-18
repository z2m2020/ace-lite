from ace_lite.cli_app import runtime_setup_support
from ace_lite.cli_app.runtime_command_support import (
    build_codex_mcp_setup_plan,
    execute_codex_mcp_setup_plan,
)


def test_runtime_setup_support_facade_reexports_setup_helpers() -> None:
    assert build_codex_mcp_setup_plan is runtime_setup_support.build_codex_mcp_setup_plan
    assert (
        execute_codex_mcp_setup_plan
        is runtime_setup_support.execute_codex_mcp_setup_plan
    )
