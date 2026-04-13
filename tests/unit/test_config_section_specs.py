from __future__ import annotations

from ace_lite import config_models, orchestrator_config
from ace_lite.config_sections import (
    ChunkCoreSectionSpec,
    ChunkGuardSectionSpec,
    ChunkTopologicalShieldSectionSpec,
    EmbeddingsSectionSpec,
    MemoryCaptureSectionSpec,
    MemoryCoreSectionSpec,
    MemoryFeedbackSectionSpec,
    MemoryGateSectionSpec,
    MemoryNamespaceSectionSpec,
    MemoryNotesSectionSpec,
    MemoryPostprocessSectionSpec,
    MemoryProfileSectionSpec,
    MemoryTemporalSectionSpec,
    PlanReplayCacheSectionSpec,
    PluginsSectionSpec,
    RepomapSectionSpec,
    ScipSectionSpec,
    TokenizerSectionSpec,
    TraceSectionSpec,
)
from ace_lite.config_sections import (
    TestSignalsSectionSpec as _TestSignalsSectionSpec,
)


def _field_names(model_cls: type[object]) -> list[str]:
    return list(getattr(model_cls, "model_fields").keys())


def test_config_section_spec_field_sets_are_single_sourced() -> None:
    assert _field_names(MemoryCoreSectionSpec) == [
        "disclosure_mode",
        "preview_max_chars",
        "strategy",
    ]
    assert _field_names(MemoryNamespaceSectionSpec) == _field_names(
        config_models.MemoryNamespaceConfig
    )
    assert _field_names(MemoryNamespaceSectionSpec) == _field_names(
        orchestrator_config.MemoryNamespaceConfig
    )
    assert _field_names(MemoryProfileSectionSpec) == _field_names(
        config_models.MemoryProfileConfig
    )
    assert _field_names(MemoryProfileSectionSpec) == _field_names(
        orchestrator_config.MemoryProfileConfig
    )
    assert _field_names(MemoryTemporalSectionSpec) == _field_names(
        config_models.MemoryTemporalConfig
    )
    assert _field_names(MemoryTemporalSectionSpec) == _field_names(
        orchestrator_config.MemoryTemporalConfig
    )
    assert _field_names(MemoryFeedbackSectionSpec) == _field_names(
        config_models.MemoryFeedbackConfig
    )
    assert _field_names(MemoryFeedbackSectionSpec) == _field_names(
        orchestrator_config.MemoryFeedbackConfig
    )
    assert _field_names(MemoryCaptureSectionSpec) == [
        "enabled",
        "notes_path",
        "min_query_length",
        "keywords",
    ]
    assert _field_names(config_models.MemoryCaptureConfig) == _field_names(
        MemoryCaptureSectionSpec
    )
    assert _field_names(orchestrator_config.MemoryCaptureConfig) == _field_names(
        MemoryCaptureSectionSpec
    )
    assert _field_names(MemoryNotesSectionSpec) == _field_names(
        config_models.MemoryNotesConfig
    )
    assert _field_names(MemoryNotesSectionSpec) == _field_names(
        orchestrator_config.MemoryNotesConfig
    )
    assert _field_names(MemoryGateSectionSpec) == _field_names(
        config_models.MemoryGateConfig
    )
    assert _field_names(MemoryGateSectionSpec) == _field_names(
        orchestrator_config.MemoryGateConfig
    )
    assert _field_names(MemoryPostprocessSectionSpec) == _field_names(
        config_models.MemoryPostprocessConfig
    )
    assert _field_names(MemoryPostprocessSectionSpec) == _field_names(
        orchestrator_config.MemoryPostprocessConfig
    )
    assert _field_names(PluginsSectionSpec) == _field_names(config_models.PluginsConfig)
    assert _field_names(PluginsSectionSpec) == _field_names(
        orchestrator_config.PluginsConfig
    )
    assert _field_names(RepomapSectionSpec) == _field_names(
        config_models.RepomapConfig
    )
    assert _field_names(RepomapSectionSpec) == _field_names(
        orchestrator_config.RepomapConfig
    )
    assert _field_names(ScipSectionSpec) == _field_names(config_models.ScipCliConfig)
    assert _field_names(ScipSectionSpec) == _field_names(
        orchestrator_config.ScipConfig
    )
    assert _field_names(EmbeddingsSectionSpec) == _field_names(
        config_models.EmbeddingsConfig
    )
    assert _field_names(EmbeddingsSectionSpec) == _field_names(
        orchestrator_config.EmbeddingsConfig
    )
    assert _field_names(TraceSectionSpec) == _field_names(config_models.TraceConfig)
    assert _field_names(TraceSectionSpec) == _field_names(
        orchestrator_config.TraceConfig
    )
    assert _field_names(PlanReplayCacheSectionSpec) == _field_names(
        config_models.PlanReplayCacheConfig
    )
    assert _field_names(PlanReplayCacheSectionSpec) == _field_names(
        orchestrator_config.PlanReplayCacheConfig
    )
    assert _field_names(TokenizerSectionSpec) == _field_names(
        config_models.TokenizerConfig
    )
    assert _field_names(TokenizerSectionSpec) == _field_names(
        orchestrator_config.TokenizerConfig
    )
    assert _field_names(_TestSignalsSectionSpec) == [
        "junit_xml",
        "coverage_json",
        "sbfl_json",
        "sbfl_metric",
    ]
    assert _field_names(config_models.TestsCliConfig)[:4] == _field_names(
        _TestSignalsSectionSpec
    )
    assert _field_names(orchestrator_config.TestSignalsConfig) == _field_names(
        _TestSignalsSectionSpec
    )
    assert _field_names(ChunkGuardSectionSpec) == _field_names(
        config_models.ChunkGuardConfig
    )
    assert _field_names(ChunkGuardSectionSpec) == _field_names(
        orchestrator_config.ChunkingConfig.GuardConfig
    )
    assert _field_names(ChunkTopologicalShieldSectionSpec) == _field_names(
        config_models.ChunkTopologicalShieldConfig
    )
    assert _field_names(ChunkTopologicalShieldSectionSpec) == _field_names(
        orchestrator_config.ChunkingConfig.TopologicalShieldConfig
    )


def test_chunk_core_and_memory_core_specs_cover_shared_top_level_fields() -> None:
    assert _field_names(ChunkCoreSectionSpec) == [
        "top_k",
        "per_file_limit",
        "disclosure",
        "signature",
        "token_budget",
    ]
    assert _field_names(MemoryCoreSectionSpec) == [
        "disclosure_mode",
        "preview_max_chars",
        "strategy",
    ]

    chunk_model_fields = _field_names(config_models.ChunkConfig)
    assert chunk_model_fields[:4] == [
        "top_k",
        "per_file_limit",
        "disclosure",
        "signature",
    ]
    assert "token_budget" in chunk_model_fields

    runtime_chunk_fields = _field_names(orchestrator_config.ChunkingConfig)
    for name in _field_names(ChunkCoreSectionSpec):
        assert name in runtime_chunk_fields

    memory_model_fields = _field_names(config_models.MemoryConfig)
    for name in _field_names(MemoryCoreSectionSpec):
        assert name in memory_model_fields

    runtime_memory_fields = _field_names(orchestrator_config.MemoryConfig)
    for name in _field_names(MemoryCoreSectionSpec):
        assert name in runtime_memory_fields
