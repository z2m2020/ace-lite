from ace_lite.cli_app import orchestrator_factory_run_plan_sections
from ace_lite.cli_app.orchestrator_factory_support import (
    GroupedFlatSectionSpec,
    build_adaptive_router_run_plan_section_spec,
    build_chunking_run_plan_section_spec,
    build_memory_run_plan_section_spec,
    build_passthrough_run_plan_section_specs,
    build_retrieval_run_plan_section_spec,
    merge_group_or_flat_sections,
    normalize_group_mapping,
)


def test_orchestrator_factory_support_reexports_run_plan_section_helpers() -> None:
    assert (
        GroupedFlatSectionSpec
        is orchestrator_factory_run_plan_sections.GroupedFlatSectionSpec
    )
    assert (
        normalize_group_mapping
        is orchestrator_factory_run_plan_sections.normalize_group_mapping
    )
    assert (
        merge_group_or_flat_sections
        is orchestrator_factory_run_plan_sections.merge_group_or_flat_sections
    )
    assert (
        build_passthrough_run_plan_section_specs
        is orchestrator_factory_run_plan_sections.build_passthrough_run_plan_section_specs
    )
    assert (
        build_chunking_run_plan_section_spec
        is orchestrator_factory_run_plan_sections.build_chunking_run_plan_section_spec
    )
    assert (
        build_retrieval_run_plan_section_spec
        is orchestrator_factory_run_plan_sections.build_retrieval_run_plan_section_spec
    )
    assert (
        build_adaptive_router_run_plan_section_spec
        is orchestrator_factory_run_plan_sections.build_adaptive_router_run_plan_section_spec
    )
    assert (
        build_memory_run_plan_section_spec
        is orchestrator_factory_run_plan_sections.build_memory_run_plan_section_spec
    )
