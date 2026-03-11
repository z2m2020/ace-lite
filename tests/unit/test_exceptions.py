from __future__ import annotations

from ace_lite.exceptions import (
    AceLiteException,
    ConfigurationError,
    IndexBuildError,
    MemoryProviderError,
    PipelineError,
    PluginError,
    RankerError,
    StageContractError,
)


def test_ace_lite_exception_string_includes_stage_and_context() -> None:
    err = AceLiteException("boom", stage="index", context={"repo": "demo"})

    text = str(err)

    assert "boom" in text
    assert "stage=index" in text
    assert "context={'repo': 'demo'}" in text


def test_pipeline_error_string_includes_cause() -> None:
    cause = ValueError("bad state")
    err = PipelineError("pipeline failed", stage="augment", cause=cause)

    text = str(err)

    assert "pipeline failed" in text
    assert "stage=augment" in text
    assert "cause=ValueError: bad state" in text


def test_stage_contract_error_string_includes_code_and_reason() -> None:
    err = StageContractError(
        "invalid stage payload",
        stage="index",
        error_code="stage_contract.missing_key",
        reason="index.candidate_files",
        context={"missing_key": "candidate_files"},
    )

    text = str(err)

    assert "invalid stage payload" in text
    assert "error_code=stage_contract.missing_key" in text
    assert "reason=index.candidate_files" in text
    assert "stage=index" in text


def test_configuration_error_includes_key_prefix() -> None:
    err = ConfigurationError("invalid value", key="memory.timeout", value="x")

    text = str(err)

    assert text.startswith("key=memory.timeout | ")
    assert "invalid value" in text


def test_memory_provider_error_includes_channel_and_provider() -> None:
    err = MemoryProviderError("memory down", channel="mcp", provider="openmemory")

    text = str(err)

    assert "memory down" in text
    assert "stage=memory" in text
    assert "channel=mcp" in text
    assert "provider=openmemory" in text


def test_ranker_error_defaults_terms_and_includes_ranker() -> None:
    err = RankerError("rank failed", ranker="hybrid_re2")

    assert err.terms == []
    assert "ranker=hybrid_re2" in str(err)


def test_index_build_error_includes_path_and_language() -> None:
    err = IndexBuildError("parse failed", path="src/a.py", language="python")

    text = str(err)

    assert "parse failed" in text
    assert "path=src/a.py" in text
    assert "language=python" in text


def test_plugin_error_includes_plugin_and_slot() -> None:
    err = PluginError("plugin rejected", plugin_name="demo", slot="source_plan.query")

    text = str(err)

    assert "plugin rejected" in text
    assert "plugin=demo" in text
    assert "slot=source_plan.query" in text
