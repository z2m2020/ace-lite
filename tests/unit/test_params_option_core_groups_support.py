from ace_lite.cli_app import params_option_core_groups
from ace_lite.cli_app.params_option_groups import (
    SHARED_ADAPTIVE_ROUTER_OPTION_DESCRIPTORS,
    SHARED_MEMORY_OPTION_DESCRIPTORS,
    SHARED_PLAN_REPLAY_OPTION_DESCRIPTORS,
    SHARED_SKILLS_OPTION_DESCRIPTORS,
    SHARED_TARGET_OPTION_DESCRIPTORS,
)


def test_params_option_groups_facade_reexports_core_group_descriptors() -> None:
    assert (
        SHARED_MEMORY_OPTION_DESCRIPTORS
        is params_option_core_groups.SHARED_MEMORY_OPTION_DESCRIPTORS
    )
    assert (
        SHARED_SKILLS_OPTION_DESCRIPTORS
        is params_option_core_groups.SHARED_SKILLS_OPTION_DESCRIPTORS
    )
    assert (
        SHARED_TARGET_OPTION_DESCRIPTORS
        is params_option_core_groups.SHARED_TARGET_OPTION_DESCRIPTORS
    )
    assert (
        SHARED_ADAPTIVE_ROUTER_OPTION_DESCRIPTORS
        is params_option_core_groups.SHARED_ADAPTIVE_ROUTER_OPTION_DESCRIPTORS
    )
    assert (
        SHARED_PLAN_REPLAY_OPTION_DESCRIPTORS
        is params_option_core_groups.SHARED_PLAN_REPLAY_OPTION_DESCRIPTORS
    )
