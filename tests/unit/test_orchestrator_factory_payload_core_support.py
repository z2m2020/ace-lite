from ace_lite.cli_app import orchestrator_factory_payload_core
from ace_lite.cli_app.orchestrator_factory_support import (
    CanonicalFieldSpec,
    build_canonical_payload,
    resolve_grouped_value,
)


def test_orchestrator_factory_support_reexports_payload_core_helpers() -> None:
    assert CanonicalFieldSpec is orchestrator_factory_payload_core.CanonicalFieldSpec
    assert build_canonical_payload is orchestrator_factory_payload_core.build_canonical_payload
    assert resolve_grouped_value is orchestrator_factory_payload_core.resolve_grouped_value
