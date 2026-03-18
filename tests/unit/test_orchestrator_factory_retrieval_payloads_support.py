from ace_lite.cli_app import orchestrator_factory_retrieval_payloads
from ace_lite.cli_app.orchestrator_factory_support import (
    build_chunking_payload,
    build_retrieval_payload,
)


def test_orchestrator_factory_support_reexports_retrieval_payload_builders() -> None:
    assert (
        build_retrieval_payload
        is orchestrator_factory_retrieval_payloads.build_retrieval_payload
    )
    assert (
        build_chunking_payload
        is orchestrator_factory_retrieval_payloads.build_chunking_payload
    )
