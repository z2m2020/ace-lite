from ace_lite.cli_app import params_option_registry
from ace_lite.cli_app.params_option_groups import (
    OptionDescriptor,
    OptionGroupDescriptor,
    _build_option_decorators,
)


def test_params_option_groups_facade_reexports_registry_primitives() -> None:
    assert OptionDescriptor is params_option_registry.OptionDescriptor
    assert OptionGroupDescriptor is params_option_registry.OptionGroupDescriptor
    assert _build_option_decorators is params_option_registry.build_option_decorators
