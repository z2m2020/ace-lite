from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read_orchestrator_text() -> str:
    return (REPO_ROOT / "src" / "ace_lite" / "orchestrator.py").read_text(
        encoding="utf-8"
    )


def _extract_method_block(method_name: str) -> str:
    source = _read_orchestrator_text()
    pattern = rf"^    def {method_name}\(.*?(?=^    def |\Z)"
    match = re.search(pattern, source, flags=re.MULTILINE | re.DOTALL)
    assert match is not None, f"Method block not found: {method_name}"
    return match.group(0)


class TestOrchestratorSeamBoundaries:
    def test_orchestrator_imports_support_runtime_builders(self) -> None:
        orchestrator_text = _read_orchestrator_text()

        expected_tokens = (
            "build_orchestrator_memory_runtime",
            "build_orchestrator_source_plan_runtime",
            "run_orchestrator_augment_stage",
            "run_orchestrator_index_stage",
            "run_orchestrator_repomap_stage",
            "run_orchestrator_skills_stage",
            "run_orchestrator_validation_stage",
            "precompute_orchestrator_skills_route",
            "load_orchestrator_plugins",
            "apply_post_stage_state_updates",
        )
        for token in expected_tokens:
            assert token in orchestrator_text

    def test_orchestrator_keeps_stage_state_updates_in_shared_support(self) -> None:
        orchestrator_text = _read_orchestrator_text()

        assert "apply_post_stage_state_updates(" in orchestrator_text
        assert (
            "precompute_skills_route_fn=lambda: self._precompute_skills_route(ctx=ctx)"
            in orchestrator_text
        )

    def test_run_memory_delegates_temporal_and_namespace_runtime_building(self) -> None:
        method_block = _extract_method_block("_run_memory")

        assert "runtime = build_orchestrator_memory_runtime(" in method_block
        assert "return _typed_dict(" in method_block
        assert "self._memory_context_service.attach_memory_stage_payloads(" in method_block
        assert "normalize_temporal_input(" not in method_block
        assert "ctx.state.get(" not in method_block
        assert "build_profile_payload(" not in method_block
        assert "build_capture_payload(" not in method_block

    def test_run_augment_does_not_reintroduce_private_candidate_helper(self) -> None:
        orchestrator_text = _read_orchestrator_text()
        method_block = _extract_method_block("_run_augment")

        assert "def _resolve_augment_candidates(" not in orchestrator_text
        assert "return _typed_dict(" in method_block
        assert "run_orchestrator_augment_stage(" in method_block
        assert "config=self._config" in method_block
        assert "lsp_broker=self._lsp_broker" in method_block
        assert "build_orchestrator_augment_runtime(" not in method_block
        assert "resolve_augment_candidates(" not in method_block
        assert "run_diagnostics_augment(" not in method_block
        assert 'ctx.state.get("index"' not in method_block
        assert 'ctx.state.get("repomap"' not in method_block

    def test_skills_stage_uses_support_runtime_instead_of_raw_state_reads(self) -> None:
        run_skills_block = _extract_method_block("_run_skills")
        precompute_block = _extract_method_block("_precompute_skills_route")

        assert "return _typed_dict(" in run_skills_block
        assert "run_orchestrator_skills_stage(" in run_skills_block
        assert "return _typed_dict(" in precompute_block
        assert "precompute_orchestrator_skills_route(" in precompute_block
        assert "build_orchestrator_skills_runtime(" not in run_skills_block
        assert "build_orchestrator_skills_runtime(" not in precompute_block
        assert "return run_skills(" not in run_skills_block
        assert "return route_skills(" not in precompute_block
        assert 'ctx.state["_skills_route"]' not in run_skills_block
        assert 'ctx.state.get("_skills_route"' not in run_skills_block
        assert 'index_stage.get("module_hint"' not in precompute_block

    def test_repomap_stage_uses_stage_runtime_support_shell(self) -> None:
        method_block = _extract_method_block("_run_repomap")

        assert "return _typed_dict(" in method_block
        assert "run_orchestrator_repomap_stage(" in method_block
        assert "config=self._config" in method_block
        assert "tokenizer_model=self._tokenizer_model" in method_block
        assert "return run_repomap(" not in method_block

    def test_index_stage_uses_stage_runtime_support_shell(self) -> None:
        method_block = _extract_method_block("_run_index")

        assert "return _typed_dict(" in method_block
        assert "run_orchestrator_index_stage(" in method_block
        assert "config=self._config" in method_block
        assert "tokenizer_model=self._tokenizer_model" in method_block
        assert "cochange_neighbor_cap=self._COCHANGE_NEIGHBOR_CAP" in method_block
        assert "cochange_min_neighbor_score=self._COCHANGE_MIN_NEIGHBOR_SCORE" in method_block
        assert "cochange_max_boost=self._COCHANGE_MAX_BOOST" in method_block
        assert "return run_index(" not in method_block
        assert "IndexStageConfig.from_orchestrator_config(" not in method_block

    def test_validation_stage_uses_support_runtime_for_state_normalization(self) -> None:
        method_block = _extract_method_block("_run_validation")

        assert "return _typed_dict(" in method_block
        assert "run_orchestrator_validation_stage(" in method_block
        assert "config=self._config" in method_block
        assert "lsp_broker=self._lsp_broker" in method_block
        assert "resolve_validation_preference_capture_store_fn=(" in method_block
        assert "build_orchestrator_validation_runtime(" not in method_block
        assert "run_validation_stage(" not in method_block
        assert 'ctx.state.get("source_plan"' not in method_block
        assert 'ctx.state.get("index"' not in method_block
        assert 'ctx.state.get("_validation_patch_artifact"' not in method_block

    def test_plugin_loading_keeps_enabled_gate_in_plugin_support(self) -> None:
        method_block = _extract_method_block("_load_plugins")

        assert "return _typed_plugin_load_result(" in method_block
        assert "load_orchestrator_plugins(" in method_block
        assert "plugins_enabled=bool(self._config.plugins.enabled)" in method_block
        assert "if not self._config.plugins.enabled" not in method_block
        assert "return HookBus(), []" not in method_block
