from __future__ import annotations

from pathlib import Path

from ace_lite.entrypoint_runtime import (
    EMBEDDING_RUNTIME_KWARGS_KEYS,
    MEMORY_GATE_POSTPROCESS_RUNTIME_KWARGS_KEYS,
    RETRIEVAL_POLICY_RUNTIME_KWARGS_KEYS,
)
from ace_lite.mcp_server.config import AceLiteMcpConfig
from ace_lite.mcp_server.plan_request import (
    PLAN_REQUEST_RUN_PLAN_KWARGS_KEYS,
    resolve_plan_request_options,
)


def _make_config(tmp_path: Path) -> AceLiteMcpConfig:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    return AceLiteMcpConfig.from_env(
        default_root=tmp_path,
        default_skills_dir=skills_dir,
    )


def test_plan_request_options_apply_config_pack_defaults(tmp_path: Path) -> None:
    config = _make_config(tmp_path)

    options = resolve_plan_request_options(
        config=config,
        top_k_files=8,
        min_candidate_score=2,
        retrieval_policy="auto",
        lsp_enabled=False,
        plugins_enabled=False,
        config_pack_overrides={
            "top_k_files": 3,
            "min_candidate_score": 0,
            "candidate_ranker": "bm25_lite",
            "policy_version": "v2",
            "embedding_enabled": True,
            "embedding_provider": "ollama",
            "embedding_model": "nomic-embed-text",
            "embedding_dimension": 768,
            "embedding_rerank_pool": 12,
            "embedding_lexical_weight": 0.55,
            "embedding_semantic_weight": 0.45,
            "embedding_min_similarity": 0.05,
            "embedding_fail_open": False,
        },
    )

    assert options.top_k_files == 3
    assert options.min_candidate_score == 0
    assert options.candidate_ranker == "bm25_lite"
    assert options.deterministic_refine_enabled is True
    assert options.policy_version == "v2"
    assert options.embedding_enabled is True
    assert options.embedding_provider == "ollama"
    assert options.embedding_model == "nomic-embed-text"
    assert options.embedding_dimension == 768
    assert options.embedding_rerank_pool == 12
    assert options.embedding_lexical_weight == 0.55
    assert options.embedding_semantic_weight == 0.45
    assert options.embedding_min_similarity == 0.05
    assert options.embedding_fail_open is False


def test_plan_request_options_explicit_args_override_config_pack(tmp_path: Path) -> None:
    config = _make_config(tmp_path)

    options = resolve_plan_request_options(
        config=config,
        top_k_files=5,
        min_candidate_score=4,
        retrieval_policy="auto",
        lsp_enabled=False,
        plugins_enabled=False,
        config_pack_overrides={
            "top_k_files": 2,
            "min_candidate_score": 1,
            "deterministic_refine_enabled": False,
        },
    )

    kwargs = options.to_run_plan_kwargs()

    assert options.top_k_files == 5
    assert options.min_candidate_score == 4
    assert options.deterministic_refine_enabled is False
    assert kwargs["deterministic_refine_enabled"] is False
    assert kwargs["plugins_enabled"] is False


def test_plan_request_options_run_plan_kwargs_match_declared_contract(
    tmp_path: Path,
) -> None:
    config = _make_config(tmp_path)

    options = resolve_plan_request_options(
        config=config,
        top_k_files=6,
        min_candidate_score=1,
        retrieval_policy="feature",
        lsp_enabled=True,
        plugins_enabled=False,
        config_pack_overrides={
            "policy_version": "v2",
            "embedding_enabled": True,
            "memory_gate_enabled": True,
        },
    )

    kwargs = options.to_run_plan_kwargs()

    assert set(kwargs.keys()) == set(PLAN_REQUEST_RUN_PLAN_KWARGS_KEYS)
    assert kwargs["top_k_files"] == 6
    assert kwargs["min_candidate_score"] == 1
    assert kwargs["retrieval_policy"] == "feature"
    assert kwargs["policy_version"] == "v2"
    assert kwargs["lsp_enabled"] is True
    assert kwargs["plugins_enabled"] is False
    assert kwargs["embedding_enabled"] is True
    assert kwargs["memory_auto_tag_mode"] == "repo"
    assert kwargs["memory_gate_enabled"] is True


def test_plan_request_run_plan_kwargs_reuses_shared_runtime_contract_groups(
    tmp_path: Path,
) -> None:
    config = _make_config(tmp_path)
    options = resolve_plan_request_options(
        config=config,
        top_k_files=8,
        min_candidate_score=2,
        retrieval_policy="auto",
        lsp_enabled=False,
        plugins_enabled=False,
        config_pack_overrides=None,
    )

    kwargs = options.to_run_plan_kwargs()
    keys = set(kwargs.keys())

    assert set(EMBEDDING_RUNTIME_KWARGS_KEYS).issubset(keys)
    assert set(MEMORY_GATE_POSTPROCESS_RUNTIME_KWARGS_KEYS).issubset(keys)
    assert set(RETRIEVAL_POLICY_RUNTIME_KWARGS_KEYS).issubset(keys)
