from ace_lite.cli_app import params_option_observability_groups
from ace_lite.cli_app.params_option_groups import (
    SHARED_COCHANGE_OPTION_DESCRIPTORS,
    SHARED_LSP_OPTION_DESCRIPTORS,
    SHARED_POLICY_OPTION_DESCRIPTORS,
    SHARED_SCIP_OPTION_DESCRIPTORS,
    SHARED_TEST_SIGNAL_OPTION_DESCRIPTORS,
    SHARED_TRACE_OPTION_DESCRIPTORS,
)


def test_params_option_groups_facade_reexports_observability_group_descriptors() -> None:
    assert (
        SHARED_LSP_OPTION_DESCRIPTORS
        is params_option_observability_groups.SHARED_LSP_OPTION_DESCRIPTORS
    )
    assert (
        SHARED_COCHANGE_OPTION_DESCRIPTORS
        is params_option_observability_groups.SHARED_COCHANGE_OPTION_DESCRIPTORS
    )
    assert (
        SHARED_POLICY_OPTION_DESCRIPTORS
        is params_option_observability_groups.SHARED_POLICY_OPTION_DESCRIPTORS
    )
    assert (
        SHARED_TEST_SIGNAL_OPTION_DESCRIPTORS
        is params_option_observability_groups.SHARED_TEST_SIGNAL_OPTION_DESCRIPTORS
    )
    assert (
        SHARED_SCIP_OPTION_DESCRIPTORS
        is params_option_observability_groups.SHARED_SCIP_OPTION_DESCRIPTORS
    )
    assert (
        SHARED_TRACE_OPTION_DESCRIPTORS
        is params_option_observability_groups.SHARED_TRACE_OPTION_DESCRIPTORS
    )
