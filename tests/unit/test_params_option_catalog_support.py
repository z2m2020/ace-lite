from ace_lite.cli_app import params_option_catalog
from ace_lite.cli_app.params_option_groups import (
    CANDIDATE_RANKER_CHOICES,
    HYBRID_FUSION_CHOICES,
    CHUNK_GUARD_MODE_CHOICES,
    MEMORY_STRATEGY_CHOICES,
    RETRIEVAL_PRESETS,
    RETRIEVAL_PRESET_CHOICES,
    SBFL_METRIC_CHOICES,
    SCIP_PROVIDER_CHOICES,
)


def test_params_option_groups_facade_reexports_catalog_constants() -> None:
    assert CANDIDATE_RANKER_CHOICES is params_option_catalog.CANDIDATE_RANKER_CHOICES
    assert CHUNK_GUARD_MODE_CHOICES is params_option_catalog.CHUNK_GUARD_MODE_CHOICES
    assert HYBRID_FUSION_CHOICES is params_option_catalog.HYBRID_FUSION_CHOICES
    assert MEMORY_STRATEGY_CHOICES is params_option_catalog.MEMORY_STRATEGY_CHOICES
    assert RETRIEVAL_PRESETS is params_option_catalog.RETRIEVAL_PRESETS
    assert RETRIEVAL_PRESET_CHOICES is params_option_catalog.RETRIEVAL_PRESET_CHOICES
    assert SBFL_METRIC_CHOICES is params_option_catalog.SBFL_METRIC_CHOICES
    assert SCIP_PROVIDER_CHOICES is params_option_catalog.SCIP_PROVIDER_CHOICES
