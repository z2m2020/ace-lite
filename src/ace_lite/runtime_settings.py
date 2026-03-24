from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from collections.abc import Mapping

import yaml

from ace_lite.cli_app.config_resolve_defaults import (
    PLAN_MEMORY_CAPTURE_DEFAULTS,
    PLAN_MEMORY_FEEDBACK_DEFAULTS,
    PLAN_MEMORY_GATE_DEFAULTS,
    PLAN_MEMORY_LONG_TERM_DEFAULTS,
    PLAN_MEMORY_NOTES_DEFAULTS,
    PLAN_MEMORY_POSTPROCESS_DEFAULTS,
    PLAN_MEMORY_PROFILE_DEFAULTS,
)
from ace_lite.cli_app.params import parse_lsp_commands_from_config
from ace_lite.config import DEFAULT_CONFIG_FILE
from ace_lite.config_models import RuntimeConfig, validate_cli_config
from ace_lite.config_pack import load_config_pack
from ace_lite.orchestrator_config import OrchestratorConfig
from ace_lite.runtime_profiles import RUNTIME_PROFILE_NAMES, get_runtime_profile
from ace_lite.scoring_config import (
    BM25_B,
    BM25_K1,
    BM25_PATH_PRIOR_FACTOR,
    BM25_SCORE_SCALE,
    BM25_SHORTLIST_FACTOR,
    BM25_SHORTLIST_MIN,
    CHUNK_FILE_PRIOR_WEIGHT,
    CHUNK_MODULE_MATCH,
    CHUNK_PATH_MATCH,
    CHUNK_REFERENCE_CAP,
    CHUNK_REFERENCE_FACTOR,
    CHUNK_SIGNATURE_MATCH,
    CHUNK_SYMBOL_EXACT,
    CHUNK_SYMBOL_PARTIAL,
    HEUR_CONTENT_CAP,
    HEUR_CONTENT_IMPORT_FACTOR,
    HEUR_CONTENT_SYMBOL_FACTOR,
    HEUR_DEPTH_BASE,
    HEUR_DEPTH_FACTOR,
    HEUR_IMPORT_CAP,
    HEUR_IMPORT_FACTOR,
    HEUR_MODULE_CONTAINS,
    HEUR_MODULE_EXACT,
    HEUR_MODULE_TAIL,
    HEUR_PATH_CONTAINS,
    HEUR_PATH_EXACT,
    HEUR_SYMBOL_EXACT,
    HEUR_SYMBOL_PARTIAL_CAP,
    HEUR_SYMBOL_PARTIAL_FACTOR,
    HYBRID_SHORTLIST_FACTOR,
    HYBRID_SHORTLIST_MIN,
    SCIP_BASE_WEIGHT,
)
from ace_lite.runtime_settings_store import (
    RUNTIME_SETTINGS_SCHEMA_VERSION,
    build_runtime_settings_fingerprint,
)

_MISSING = object()
_DEFAULT_LANGUAGE_PROFILE = (
    "python,typescript,javascript,go,solidity,rust,java,c,cpp,c_sharp,ruby,php,markdown"
)


@dataclass(frozen=True)
class _FieldSpec:
    output_path: tuple[str, ...]
    default: Any
    candidate_paths: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class RuntimeSettingsSnapshot:
    snapshot: dict[str, Any]
    provenance: dict[str, Any]
    fingerprint: str
    metadata: dict[str, Any]
    schema_version: int = RUNTIME_SETTINGS_SCHEMA_VERSION

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": int(self.schema_version),
            "snapshot": self.snapshot,
            "provenance": self.provenance,
            "fingerprint": self.fingerprint,
            "metadata": self.metadata,
        }


def _spec(output_path: tuple[str, ...], default: Any, *candidate_paths: tuple[str, ...]) -> _FieldSpec:
    return _FieldSpec(output_path=output_path, default=default, candidate_paths=tuple(candidate_paths))


def _read_config_file(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists() or not path.is_file():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _deep_merge(target: dict[str, Any], source: Mapping[str, Any]) -> None:
    for key, value in source.items():
        normalized_key = str(key)
        if isinstance(value, Mapping) and isinstance(target.get(normalized_key), dict):
            _deep_merge(target[normalized_key], value)
        elif isinstance(value, Mapping):
            child: dict[str, Any] = {}
            _deep_merge(child, value)
            target[normalized_key] = child
        else:
            target[normalized_key] = value


def _normalize_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    payload: dict[str, Any] = {}
    _deep_merge(payload, value)
    return payload


def _extract_path(payload: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return _MISSING
        current = current[key]
    return current


def _set_nested(target: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    current = target
    for key in path[:-1]:
        child = current.get(key)
        if not isinstance(child, dict):
            child = {}
            current[key] = child
        current = child
    current[path[-1]] = value


def _split_csv(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        values = [item.strip() for item in value.split(",") if item.strip()]
        return values or None
    if isinstance(value, (list, tuple)):
        values = [str(item).strip() for item in value if str(item).strip()]
        return values or None
    return None


def _build_payload_and_provenance(
    *,
    specs: tuple[_FieldSpec, ...],
    layers: list[tuple[str, dict[str, Any]]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload: dict[str, Any] = {}
    provenance: dict[str, Any] = {}
    for spec in specs:
        source = "default"
        value = spec.default
        for label, layer in layers:
            for candidate_path in spec.candidate_paths:
                candidate = _extract_path(layer, candidate_path)
                if candidate is _MISSING:
                    continue
                value = candidate
                source = label
                break
            if source != "default":
                break
        _set_nested(payload, spec.output_path, value)
        _set_nested(provenance, spec.output_path, source)
    return payload, provenance


def _layer_paths(*, root: str | Path, cwd: str | Path | None, filename: str) -> tuple[Path, Path, Path | None]:
    root_path = Path(root).resolve()
    cwd_path = Path(cwd).resolve() if cwd is not None else Path.cwd().resolve()
    home_path = (Path.home() / filename).resolve()
    repo_path = (root_path / filename).resolve()
    within_root = cwd_path == root_path or root_path in cwd_path.parents
    active_path = (cwd_path / filename).resolve() if within_root else None
    return home_path, repo_path, active_path


def _load_layer_sources(
    *,
    root: str | Path,
    cwd: str | Path | None,
    filename: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[str]]:
    home_path, repo_path, cwd_path = _layer_paths(root=root, cwd=cwd, filename=filename)
    user_root = _read_config_file(home_path)
    repo_root = _read_config_file(repo_path)
    cwd_root = _read_config_file(cwd_path)
    loaded_files: list[str] = []
    for path, payload in ((home_path, user_root), (repo_path, repo_root), (cwd_path, cwd_root)):
        if path is None or not payload:
            continue
        resolved = str(path.resolve())
        if resolved not in loaded_files:
            loaded_files.append(resolved)
    return user_root, repo_root, cwd_root, loaded_files


_PLAN_SPECS: tuple[_FieldSpec, ...] = (
    _spec(("memory", "disclosure_mode"), "compact", ("memory", "disclosure_mode"), ("memory_disclosure_mode",)),
    _spec(("memory", "preview_max_chars"), 280, ("memory", "preview_max_chars"), ("memory_preview_max_chars",)),
    _spec(("memory", "strategy"), "hybrid", ("memory", "strategy"), ("memory_strategy",)),
    _spec(("memory", "timeline_enabled"), True, ("memory", "timeline", "enabled"), ("memory_timeline_enabled",)),
    _spec(("memory", "namespace", "container_tag"), None, ("memory", "namespace", "container_tag"), ("memory_container_tag",)),
    _spec(("memory", "namespace", "auto_tag_mode"), None, ("memory", "namespace", "auto_tag_mode"), ("memory_auto_tag_mode",)),
    _spec(("memory", "gate", "enabled"), bool(PLAN_MEMORY_GATE_DEFAULTS["memory_gate_enabled"]), ("memory", "gate", "enabled"), ("memory_gate_enabled",)),
    _spec(("memory", "gate", "mode"), str(PLAN_MEMORY_GATE_DEFAULTS["memory_gate_mode"]), ("memory", "gate", "mode"), ("memory_gate_mode",)),
    _spec(("memory", "profile", "enabled"), bool(PLAN_MEMORY_PROFILE_DEFAULTS["memory_profile_enabled"]), ("memory", "profile", "enabled"), ("memory_profile_enabled",)),
    _spec(("memory", "profile", "path"), str(PLAN_MEMORY_PROFILE_DEFAULTS["memory_profile_path"]), ("memory", "profile", "path"), ("memory_profile_path",)),
    _spec(("memory", "profile", "top_n"), int(PLAN_MEMORY_PROFILE_DEFAULTS["memory_profile_top_n"]), ("memory", "profile", "top_n"), ("memory_profile_top_n",)),
    _spec(("memory", "profile", "token_budget"), int(PLAN_MEMORY_PROFILE_DEFAULTS["memory_profile_token_budget"]), ("memory", "profile", "token_budget"), ("memory_profile_token_budget",)),
    _spec(("memory", "profile", "expiry_enabled"), bool(PLAN_MEMORY_PROFILE_DEFAULTS["memory_profile_expiry_enabled"]), ("memory", "profile", "expiry_enabled"), ("memory_profile_expiry_enabled",)),
    _spec(("memory", "profile", "ttl_days"), int(PLAN_MEMORY_PROFILE_DEFAULTS["memory_profile_ttl_days"]), ("memory", "profile", "ttl_days"), ("memory_profile_ttl_days",)),
    _spec(("memory", "profile", "max_age_days"), int(PLAN_MEMORY_PROFILE_DEFAULTS["memory_profile_max_age_days"]), ("memory", "profile", "max_age_days"), ("memory_profile_max_age_days",)),
    _spec(("memory", "feedback", "enabled"), bool(PLAN_MEMORY_FEEDBACK_DEFAULTS["memory_feedback_enabled"]), ("memory", "feedback", "enabled"), ("memory_feedback_enabled",)),
    _spec(("memory", "feedback", "path"), str(PLAN_MEMORY_FEEDBACK_DEFAULTS["memory_feedback_path"]), ("memory", "feedback", "path"), ("memory_feedback_path",)),
    _spec(("memory", "feedback", "max_entries"), int(PLAN_MEMORY_FEEDBACK_DEFAULTS["memory_feedback_max_entries"]), ("memory", "feedback", "max_entries"), ("memory_feedback_max_entries",)),
    _spec(("memory", "feedback", "boost_per_select"), float(PLAN_MEMORY_FEEDBACK_DEFAULTS["memory_feedback_boost_per_select"]), ("memory", "feedback", "boost_per_select"), ("memory_feedback_boost_per_select",)),
    _spec(("memory", "feedback", "max_boost"), float(PLAN_MEMORY_FEEDBACK_DEFAULTS["memory_feedback_max_boost"]), ("memory", "feedback", "max_boost"), ("memory_feedback_max_boost",)),
    _spec(("memory", "feedback", "decay_days"), float(PLAN_MEMORY_FEEDBACK_DEFAULTS["memory_feedback_decay_days"]), ("memory", "feedback", "decay_days"), ("memory_feedback_decay_days",)),
    _spec(("memory", "long_term", "enabled"), bool(PLAN_MEMORY_LONG_TERM_DEFAULTS["memory_long_term_enabled"]), ("memory", "long_term", "enabled"), ("memory_long_term_enabled",)),
    _spec(("memory", "long_term", "path"), str(PLAN_MEMORY_LONG_TERM_DEFAULTS["memory_long_term_path"]), ("memory", "long_term", "path"), ("memory_long_term_path",)),
    _spec(("memory", "long_term", "top_n"), int(PLAN_MEMORY_LONG_TERM_DEFAULTS["memory_long_term_top_n"]), ("memory", "long_term", "top_n"), ("memory_long_term_top_n",)),
    _spec(("memory", "long_term", "token_budget"), int(PLAN_MEMORY_LONG_TERM_DEFAULTS["memory_long_term_token_budget"]), ("memory", "long_term", "token_budget"), ("memory_long_term_token_budget",)),
    _spec(("memory", "long_term", "write_enabled"), bool(PLAN_MEMORY_LONG_TERM_DEFAULTS["memory_long_term_write_enabled"]), ("memory", "long_term", "write_enabled"), ("memory_long_term_write_enabled",)),
    _spec(("memory", "long_term", "as_of_enabled"), bool(PLAN_MEMORY_LONG_TERM_DEFAULTS["memory_long_term_as_of_enabled"]), ("memory", "long_term", "as_of_enabled"), ("memory_long_term_as_of_enabled",)),
    _spec(("memory", "capture", "enabled"), bool(PLAN_MEMORY_CAPTURE_DEFAULTS["memory_capture_enabled"]), ("memory", "capture", "enabled"), ("memory_capture_enabled",)),
    _spec(("memory", "capture", "notes_path"), str(PLAN_MEMORY_CAPTURE_DEFAULTS["memory_capture_notes_path"]), ("memory", "capture", "notes_path"), ("memory_capture_notes_path",)),
    _spec(("memory", "capture", "min_query_length"), int(PLAN_MEMORY_CAPTURE_DEFAULTS["memory_capture_min_query_length"]), ("memory", "capture", "min_query_length"), ("memory_capture_min_query_length",)),
    _spec(("memory", "capture", "keywords"), tuple(PLAN_MEMORY_CAPTURE_DEFAULTS["memory_capture_keywords"]), ("memory", "capture", "keywords"), ("memory_capture_keywords",)),
    _spec(("memory", "notes", "enabled"), bool(PLAN_MEMORY_NOTES_DEFAULTS["memory_notes_enabled"]), ("memory", "notes", "enabled"), ("memory_notes_enabled",)),
    _spec(("memory", "notes", "path"), str(PLAN_MEMORY_NOTES_DEFAULTS["memory_notes_path"]), ("memory", "notes", "path"), ("memory_notes_path",)),
    _spec(("memory", "notes", "limit"), int(PLAN_MEMORY_NOTES_DEFAULTS["memory_notes_limit"]), ("memory", "notes", "limit"), ("memory_notes_limit",)),
    _spec(("memory", "notes", "mode"), str(PLAN_MEMORY_NOTES_DEFAULTS["memory_notes_mode"]), ("memory", "notes", "mode"), ("memory_notes_mode",)),
    _spec(("memory", "notes", "expiry_enabled"), bool(PLAN_MEMORY_NOTES_DEFAULTS["memory_notes_expiry_enabled"]), ("memory", "notes", "expiry_enabled"), ("memory_notes_expiry_enabled",)),
    _spec(("memory", "notes", "ttl_days"), int(PLAN_MEMORY_NOTES_DEFAULTS["memory_notes_ttl_days"]), ("memory", "notes", "ttl_days"), ("memory_notes_ttl_days",)),
    _spec(("memory", "notes", "max_age_days"), int(PLAN_MEMORY_NOTES_DEFAULTS["memory_notes_max_age_days"]), ("memory", "notes", "max_age_days"), ("memory_notes_max_age_days",)),
    _spec(("memory", "temporal", "enabled"), True, ("memory", "temporal", "enabled")),
    _spec(("memory", "temporal", "recency_boost_enabled"), False, ("memory", "temporal", "recency_boost_enabled")),
    _spec(("memory", "temporal", "recency_boost_max"), 0.15, ("memory", "temporal", "recency_boost_max")),
    _spec(("memory", "temporal", "timezone_mode"), "utc", ("memory", "temporal", "timezone_mode")),
    _spec(("memory", "postprocess", "enabled"), bool(PLAN_MEMORY_POSTPROCESS_DEFAULTS["memory_postprocess_enabled"]), ("memory", "postprocess", "enabled"), ("memory_postprocess_enabled",)),
    _spec(("memory", "postprocess", "noise_filter_enabled"), bool(PLAN_MEMORY_POSTPROCESS_DEFAULTS["memory_postprocess_noise_filter_enabled"]), ("memory", "postprocess", "noise_filter_enabled"), ("memory_postprocess_noise_filter_enabled",)),
    _spec(("memory", "postprocess", "length_norm_anchor_chars"), int(PLAN_MEMORY_POSTPROCESS_DEFAULTS["memory_postprocess_length_norm_anchor_chars"]), ("memory", "postprocess", "length_norm_anchor_chars"), ("memory_postprocess_length_norm_anchor_chars",)),
    _spec(("memory", "postprocess", "time_decay_half_life_days"), float(PLAN_MEMORY_POSTPROCESS_DEFAULTS["memory_postprocess_time_decay_half_life_days"]), ("memory", "postprocess", "time_decay_half_life_days"), ("memory_postprocess_time_decay_half_life_days",)),
    _spec(("memory", "postprocess", "hard_min_score"), float(PLAN_MEMORY_POSTPROCESS_DEFAULTS["memory_postprocess_hard_min_score"]), ("memory", "postprocess", "hard_min_score"), ("memory_postprocess_hard_min_score",)),
    _spec(("memory", "postprocess", "diversity_enabled"), bool(PLAN_MEMORY_POSTPROCESS_DEFAULTS["memory_postprocess_diversity_enabled"]), ("memory", "postprocess", "diversity_enabled"), ("memory_postprocess_diversity_enabled",)),
    _spec(("memory", "postprocess", "diversity_similarity_threshold"), float(PLAN_MEMORY_POSTPROCESS_DEFAULTS["memory_postprocess_diversity_similarity_threshold"]), ("memory", "postprocess", "diversity_similarity_threshold"), ("memory_postprocess_diversity_similarity_threshold",)),
    _spec(("skills", "dir"), "skills", ("skills", "dir"), ("skills_dir",)),
    _spec(("skills", "manifest"), None, ("skills", "manifest")),
    _spec(("skills", "precomputed_routing_enabled"), True, ("skills", "precomputed_routing_enabled"), ("precomputed_skills_routing_enabled",)),
    _spec(("skills", "top_n"), 3, ("skills", "top_n")),
    _spec(("skills", "token_budget"), 1200, ("skills", "token_budget")),
    _spec(("retrieval", "top_k_files"), 8, ("retrieval", "top_k_files"), ("top_k_files",)),
    _spec(("retrieval", "min_candidate_score"), 2, ("retrieval", "min_candidate_score"), ("min_candidate_score",)),
    _spec(("retrieval", "candidate_relative_threshold"), 0.0, ("retrieval", "candidate_relative_threshold"), ("candidate_relative_threshold",)),
    _spec(("retrieval", "candidate_ranker"), "heuristic", ("retrieval", "candidate_ranker"), ("candidate_ranker",)),
    _spec(("retrieval", "exact_search_enabled"), False, ("retrieval", "exact_search_enabled"), ("exact_search_enabled",)),
    _spec(("retrieval", "deterministic_refine_enabled"), True, ("retrieval", "deterministic_refine_enabled"), ("deterministic_refine_enabled",)),
    _spec(("retrieval", "exact_search_time_budget_ms"), 40, ("retrieval", "exact_search_time_budget_ms"), ("exact_search_time_budget_ms",)),
    _spec(("retrieval", "exact_search_max_paths"), 24, ("retrieval", "exact_search_max_paths"), ("exact_search_max_paths",)),
    _spec(("retrieval", "hybrid_re2_fusion_mode"), "linear", ("retrieval", "hybrid_re2_fusion_mode"), ("hybrid_re2_fusion_mode",)),
    _spec(("retrieval", "hybrid_re2_rrf_k"), 60, ("retrieval", "hybrid_re2_rrf_k"), ("hybrid_re2_rrf_k",)),
    _spec(("retrieval", "hybrid_re2_shortlist_min"), HYBRID_SHORTLIST_MIN, ("retrieval", "hybrid_re2_shortlist_min")),
    _spec(("retrieval", "hybrid_re2_shortlist_factor"), HYBRID_SHORTLIST_FACTOR, ("retrieval", "hybrid_re2_shortlist_factor")),
    _spec(("retrieval", "hybrid_re2_bm25_weight"), 0.0, ("retrieval", "hybrid_re2_bm25_weight"), ("hybrid_re2_bm25_weight",)),
    _spec(("retrieval", "hybrid_re2_heuristic_weight"), 0.0, ("retrieval", "hybrid_re2_heuristic_weight"), ("hybrid_re2_heuristic_weight",)),
    _spec(("retrieval", "hybrid_re2_coverage_weight"), 0.0, ("retrieval", "hybrid_re2_coverage_weight"), ("hybrid_re2_coverage_weight",)),
    _spec(("retrieval", "hybrid_re2_combined_scale"), 0.0, ("retrieval", "hybrid_re2_combined_scale"), ("hybrid_re2_combined_scale",)),
    _spec(("retrieval", "bm25_k1"), BM25_K1, ("retrieval", "bm25_k1")),
    _spec(("retrieval", "bm25_b"), BM25_B, ("retrieval", "bm25_b")),
    _spec(("retrieval", "bm25_score_scale"), BM25_SCORE_SCALE, ("retrieval", "bm25_score_scale")),
    _spec(("retrieval", "bm25_path_prior_factor"), BM25_PATH_PRIOR_FACTOR, ("retrieval", "bm25_path_prior_factor")),
    _spec(("retrieval", "bm25_shortlist_min"), BM25_SHORTLIST_MIN, ("retrieval", "bm25_shortlist_min")),
    _spec(("retrieval", "bm25_shortlist_factor"), BM25_SHORTLIST_FACTOR, ("retrieval", "bm25_shortlist_factor")),
    _spec(("retrieval", "heur_path_exact"), HEUR_PATH_EXACT, ("retrieval", "heur_path_exact")),
    _spec(("retrieval", "heur_path_contains"), HEUR_PATH_CONTAINS, ("retrieval", "heur_path_contains")),
    _spec(("retrieval", "heur_module_exact"), HEUR_MODULE_EXACT, ("retrieval", "heur_module_exact")),
    _spec(("retrieval", "heur_module_tail"), HEUR_MODULE_TAIL, ("retrieval", "heur_module_tail")),
    _spec(("retrieval", "heur_module_contains"), HEUR_MODULE_CONTAINS, ("retrieval", "heur_module_contains")),
    _spec(("retrieval", "heur_symbol_exact"), HEUR_SYMBOL_EXACT, ("retrieval", "heur_symbol_exact")),
    _spec(("retrieval", "heur_symbol_partial_factor"), HEUR_SYMBOL_PARTIAL_FACTOR, ("retrieval", "heur_symbol_partial_factor")),
    _spec(("retrieval", "heur_symbol_partial_cap"), HEUR_SYMBOL_PARTIAL_CAP, ("retrieval", "heur_symbol_partial_cap")),
    _spec(("retrieval", "heur_import_factor"), HEUR_IMPORT_FACTOR, ("retrieval", "heur_import_factor")),
    _spec(("retrieval", "heur_import_cap"), HEUR_IMPORT_CAP, ("retrieval", "heur_import_cap")),
    _spec(("retrieval", "heur_content_symbol_factor"), HEUR_CONTENT_SYMBOL_FACTOR, ("retrieval", "heur_content_symbol_factor")),
    _spec(("retrieval", "heur_content_import_factor"), HEUR_CONTENT_IMPORT_FACTOR, ("retrieval", "heur_content_import_factor")),
    _spec(("retrieval", "heur_content_cap"), HEUR_CONTENT_CAP, ("retrieval", "heur_content_cap")),
    _spec(("retrieval", "heur_depth_base"), HEUR_DEPTH_BASE, ("retrieval", "heur_depth_base")),
    _spec(("retrieval", "heur_depth_factor"), HEUR_DEPTH_FACTOR, ("retrieval", "heur_depth_factor")),
    _spec(("retrieval", "retrieval_policy"), "auto", ("retrieval", "retrieval_policy"), ("retrieval_policy",)),
    _spec(("retrieval", "policy_version"), "v1", ("retrieval", "policy_version"), ("policy_version",)),
    _spec(("retrieval", "adaptive_router_enabled"), False, ("adaptive_router", "enabled"), ("adaptive_router_enabled",)),
    _spec(("retrieval", "adaptive_router_mode"), "observe", ("adaptive_router", "mode"), ("adaptive_router_mode",)),
    _spec(("retrieval", "adaptive_router_model_path"), "context-map/router/model.json", ("adaptive_router", "model_path"), ("adaptive_router_model_path",)),
    _spec(("retrieval", "adaptive_router_state_path"), "context-map/router/state.json", ("adaptive_router", "state_path"), ("adaptive_router_state_path",)),
    _spec(("retrieval", "adaptive_router_arm_set"), "retrieval_policy_v1", ("adaptive_router", "arm_set"), ("adaptive_router_arm_set",)),
    _spec(("retrieval", "adaptive_router_online_bandit_enabled"), False, ("adaptive_router", "online_bandit", "enabled"), ("adaptive_router_online_bandit_enabled",)),
    _spec(("retrieval", "adaptive_router_online_bandit_experiment_enabled"), False, ("adaptive_router", "online_bandit", "experiment_enabled"), ("adaptive_router_online_bandit_experiment_enabled",)),
    _spec(("index", "languages"), None, ("index", "languages"), ("languages",)),
    _spec(("index", "cache_path"), "context-map/index.json", ("index", "cache_path"), ("index_cache_path",)),
    _spec(("index", "incremental"), True, ("index", "incremental"), ("index_incremental",)),
    _spec(("index", "conventions_files"), None, ("index", "conventions_files"), ("conventions_files",)),
    _spec(("repomap", "enabled"), True, ("repomap", "enabled"), ("repomap_enabled",)),
    _spec(("repomap", "top_k"), 8, ("repomap", "top_k"), ("repomap_top_k",)),
    _spec(("repomap", "neighbor_limit"), 20, ("repomap", "neighbor_limit"), ("repomap_neighbor_limit",)),
    _spec(("repomap", "budget_tokens"), 800, ("repomap", "budget_tokens"), ("repomap_budget_tokens",)),
    _spec(("repomap", "ranking_profile"), "graph", ("repomap", "ranking_profile"), ("repomap_ranking_profile",)),
    _spec(("repomap", "signal_weights"), None, ("repomap", "signal_weights"), ("repomap_signal_weights",)),
)


_PLAN_SPECS += (
    _spec(("lsp", "enabled"), False, ("lsp", "enabled"), ("lsp_enabled",)),
    _spec(("lsp", "top_n"), 5, ("lsp", "top_n"), ("lsp_top_n",)),
    _spec(("lsp", "commands"), None, ("lsp", "commands"), ("lsp_commands",)),
    _spec(("lsp", "xref_enabled"), False, ("lsp", "xref_enabled"), ("lsp_xref_enabled",)),
    _spec(("lsp", "xref_top_n"), 3, ("lsp", "xref_top_n"), ("lsp_xref_top_n",)),
    _spec(("lsp", "time_budget_ms"), 1500, ("lsp", "time_budget_ms"), ("lsp_time_budget_ms",)),
    _spec(("lsp", "xref_commands"), None, ("lsp", "xref_commands"), ("lsp_xref_commands",)),
    _spec(("plugins", "enabled"), True, ("plugins", "enabled"), ("plugins_enabled",)),
    _spec(("plugins", "remote_slot_policy_mode"), "strict", ("plugins", "remote_slot_policy_mode"), ("remote_slot_policy_mode",)),
    _spec(("plugins", "remote_slot_allowlist"), None, ("plugins", "remote_slot_allowlist"), ("remote_slot_allowlist",)),
    _spec(("chunking", "top_k"), 24, ("chunk", "top_k"), ("chunk_top_k",)),
    _spec(("chunking", "per_file_limit"), 3, ("chunk", "per_file_limit"), ("chunk_per_file_limit",)),
    _spec(("chunking", "disclosure"), "refs", ("chunk", "disclosure"), ("chunk_disclosure",)),
    _spec(("chunking", "signature"), False, ("chunk", "signature"), ("chunk_signature",)),
    _spec(("chunking", "snippet_max_lines"), 18, ("chunk", "snippet", "max_lines"), ("chunk_snippet_max_lines",)),
    _spec(("chunking", "snippet_max_chars"), 1200, ("chunk", "snippet", "max_chars"), ("chunk_snippet_max_chars",)),
    _spec(("chunking", "token_budget"), 1200, ("chunk", "token_budget"), ("chunk_token_budget",)),
    _spec(("chunking", "topological_shield", "enabled"), False, ("chunk", "topological_shield", "enabled")),
    _spec(("chunking", "topological_shield", "mode"), "off", ("chunk", "topological_shield", "mode")),
    _spec(("chunking", "topological_shield", "max_attenuation"), 0.6, ("chunk", "topological_shield", "max_attenuation")),
    _spec(("chunking", "topological_shield", "shared_parent_attenuation"), 0.2, ("chunk", "topological_shield", "shared_parent_attenuation")),
    _spec(("chunking", "topological_shield", "adjacency_attenuation"), 0.5, ("chunk", "topological_shield", "adjacency_attenuation")),
    _spec(("chunking", "guard", "enabled"), False, ("chunk", "guard", "enabled"), ("chunk_guard_enabled",)),
    _spec(("chunking", "guard", "mode"), "off", ("chunk", "guard", "mode"), ("chunk_guard_mode",)),
    _spec(("chunking", "guard", "lambda_penalty"), 0.8, ("chunk", "guard", "lambda_penalty"), ("chunk_guard_lambda_penalty",)),
    _spec(("chunking", "guard", "min_pool"), 4, ("chunk", "guard", "min_pool"), ("chunk_guard_min_pool",)),
    _spec(("chunking", "guard", "max_pool"), 32, ("chunk", "guard", "max_pool"), ("chunk_guard_max_pool",)),
    _spec(("chunking", "guard", "min_marginal_utility"), 0.0, ("chunk", "guard", "min_marginal_utility"), ("chunk_guard_min_marginal_utility",)),
    _spec(("chunking", "guard", "compatibility_min_overlap"), 0.3, ("chunk", "guard", "compatibility_min_overlap"), ("chunk_guard_compatibility_min_overlap",)),
    _spec(("chunking", "diversity_enabled"), True, ("chunk", "diversity_enabled"), ("chunk_diversity_enabled",)),
    _spec(("chunking", "diversity_path_penalty"), 0.20, ("chunk", "diversity_path_penalty"), ("chunk_diversity_path_penalty",)),
    _spec(("chunking", "diversity_symbol_family_penalty"), 0.30, ("chunk", "diversity_symbol_family_penalty"), ("chunk_diversity_symbol_family_penalty",)),
    _spec(("chunking", "diversity_kind_penalty"), 0.10, ("chunk", "diversity_kind_penalty"), ("chunk_diversity_kind_penalty",)),
    _spec(("chunking", "diversity_locality_penalty"), 0.15, ("chunk", "diversity_locality_penalty"), ("chunk_diversity_locality_penalty",)),
    _spec(("chunking", "diversity_locality_window"), 24, ("chunk", "diversity_locality_window"), ("chunk_diversity_locality_window",)),
    _spec(("chunking", "file_prior_weight"), CHUNK_FILE_PRIOR_WEIGHT, ("chunk", "file_prior_weight"), ("chunk_file_prior_weight",)),
    _spec(("chunking", "path_match"), CHUNK_PATH_MATCH, ("chunk", "path_match"), ("chunk_path_match",)),
    _spec(("chunking", "module_match"), CHUNK_MODULE_MATCH, ("chunk", "module_match"), ("chunk_module_match",)),
    _spec(("chunking", "symbol_exact"), CHUNK_SYMBOL_EXACT, ("chunk", "symbol_exact"), ("chunk_symbol_exact",)),
    _spec(("chunking", "symbol_partial"), CHUNK_SYMBOL_PARTIAL, ("chunk", "symbol_partial"), ("chunk_symbol_partial",)),
    _spec(("chunking", "signature_match"), CHUNK_SIGNATURE_MATCH, ("chunk", "signature_match"), ("chunk_signature_match",)),
    _spec(("chunking", "reference_factor"), CHUNK_REFERENCE_FACTOR, ("chunk", "reference_factor"), ("chunk_reference_factor",)),
    _spec(("chunking", "reference_cap"), CHUNK_REFERENCE_CAP, ("chunk", "reference_cap"), ("chunk_reference_cap",)),
    _spec(("tokenizer", "model"), "gpt-4o-mini", ("tokenizer", "model"), ("tokenizer_model",)),
    _spec(("cochange", "enabled"), True, ("cochange", "enabled"), ("cochange_enabled",)),
    _spec(("cochange", "cache_path"), "context-map/cochange.json", ("cochange", "cache_path"), ("cochange_cache_path",)),
    _spec(("cochange", "lookback_commits"), 400, ("cochange", "lookback_commits"), ("cochange_lookback_commits",)),
    _spec(("cochange", "half_life_days"), 60.0, ("cochange", "half_life_days"), ("cochange_half_life_days",)),
    _spec(("cochange", "top_neighbors"), 12, ("cochange", "top_neighbors"), ("cochange_top_neighbors",)),
    _spec(("cochange", "boost_weight"), 1.5, ("cochange", "boost_weight"), ("cochange_boost_weight",)),
    _spec(("tests", "junit_xml"), None, ("tests", "junit_xml"), ("junit_xml",)),
    _spec(("tests", "coverage_json"), None, ("tests", "coverage_json"), ("coverage_json",)),
    _spec(("tests", "sbfl_json"), None, ("tests", "sbfl_json"), ("tests", "sbfl", "json_path"), ("tests", "sbfl", "json"), ("sbfl_json",)),
    _spec(("tests", "sbfl_metric"), "ochiai", ("tests", "sbfl_metric"), ("tests", "sbfl", "metric"), ("sbfl_metric",)),
    _spec(("scip", "enabled"), False, ("scip", "enabled"), ("scip_enabled",)),
    _spec(("scip", "index_path"), "context-map/scip/index.json", ("scip", "index_path"), ("scip_index_path",)),
    _spec(("scip", "provider"), "auto", ("scip", "provider"), ("scip_provider",)),
    _spec(("scip", "generate_fallback"), True, ("scip", "generate_fallback"), ("scip_generate_fallback",)),
    _spec(("scip", "base_weight"), SCIP_BASE_WEIGHT, ("scip", "base_weight"), ("scip_base_weight",)),
    _spec(("embeddings", "enabled"), False, ("embeddings", "enabled"), ("embedding_enabled",)),
    _spec(("embeddings", "provider"), "hash", ("embeddings", "provider"), ("embedding_provider",)),
    _spec(("embeddings", "model"), "hash-v1", ("embeddings", "model"), ("embedding_model",)),
    _spec(("embeddings", "dimension"), 256, ("embeddings", "dimension"), ("embedding_dimension",)),
    _spec(("embeddings", "index_path"), "context-map/embeddings/index.json", ("embeddings", "index_path"), ("embedding_index_path",)),
    _spec(("embeddings", "rerank_pool"), 24, ("embeddings", "rerank_pool"), ("embedding_rerank_pool",)),
    _spec(("embeddings", "lexical_weight"), 0.7, ("embeddings", "lexical_weight"), ("embedding_lexical_weight",)),
    _spec(("embeddings", "semantic_weight"), 0.3, ("embeddings", "semantic_weight"), ("embedding_semantic_weight",)),
    _spec(("embeddings", "min_similarity"), 0.0, ("embeddings", "min_similarity"), ("embedding_min_similarity",)),
    _spec(("embeddings", "fail_open"), True, ("embeddings", "fail_open"), ("embedding_fail_open",)),
    _spec(("trace", "export_enabled"), False, ("trace", "export_enabled"), ("trace_export_enabled",)),
    _spec(("trace", "export_path"), "context-map/traces/stage_spans.jsonl", ("trace", "export_path"), ("trace_export_path",)),
    _spec(("trace", "otlp_enabled"), False, ("trace", "otlp_enabled"), ("trace_otlp_enabled",)),
    _spec(("trace", "otlp_endpoint"), "", ("trace", "otlp_endpoint"), ("trace_otlp_endpoint",)),
    _spec(("trace", "otlp_timeout_seconds"), 1.5, ("trace", "otlp_timeout_seconds"), ("trace_otlp_timeout_seconds",)),
    _spec(("plan_replay_cache", "enabled"), False, ("plan_replay_cache", "enabled"), ("plan_replay_cache_enabled",)),
    _spec(("plan_replay_cache", "cache_path"), "context-map/plan-replay/cache.json", ("plan_replay_cache", "cache_path"), ("plan_replay_cache_path",)),
)


_RUNTIME_SPECS: tuple[_FieldSpec, ...] = (
    _spec(("hot_reload", "enabled"), None, ("hot_reload", "enabled")),
    _spec(("hot_reload", "config_file"), None, ("hot_reload", "config_file")),
    _spec(("hot_reload", "poll_interval_seconds"), None, ("hot_reload", "poll_interval_seconds")),
    _spec(("hot_reload", "debounce_ms"), None, ("hot_reload", "debounce_ms")),
    _spec(("scheduler", "enabled"), None, ("scheduler", "enabled")),
    _spec(("scheduler", "heartbeat", "enabled"), None, ("scheduler", "heartbeat", "enabled")),
    _spec(("scheduler", "heartbeat", "interval_seconds"), None, ("scheduler", "heartbeat", "interval_seconds")),
    _spec(("scheduler", "heartbeat", "run_on_start"), None, ("scheduler", "heartbeat", "run_on_start")),
    _spec(("scheduler", "cron"), None, ("scheduler", "cron")),
)


def _prepare_retrieval_preset_payload(
    retrieval_preset: str | Mapping[str, Any] | None,
) -> dict[str, Any]:
    if retrieval_preset is None:
        return {}
    if isinstance(retrieval_preset, Mapping):
        return _normalize_mapping(retrieval_preset)
    normalized = str(retrieval_preset or "").strip().lower()
    if not normalized or normalized == "none":
        return {}
    from ace_lite.cli_app.params import _resolve_retrieval_preset

    return _normalize_mapping(_resolve_retrieval_preset(normalized) or {})


def _prepare_config_pack_overrides(
    *,
    config_pack_path: str | Path | None,
    config_pack_overrides: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if isinstance(config_pack_overrides, Mapping):
        return _normalize_mapping(config_pack_overrides)
    if config_pack_path is None:
        return {}
    result = load_config_pack(path=config_pack_path)
    if not result.enabled:
        return {}
    return _normalize_mapping(result.overrides)


def _normalize_runtime_profile_name(value: Any) -> str | None:
    normalized = str(value or "").strip().lower()
    return normalized or None


def _resolve_runtime_profile_metadata(
    *,
    explicit_profile: str | None,
    user_root: dict[str, Any],
    repo_root: dict[str, Any],
    cwd_root: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    requested_profile: str | None = None
    selected_source = "default"
    for label, raw in (
        ("cli", explicit_profile),
        ("cwd_config", _extract_path(_normalize_mapping(cwd_root.get("plan")), ("runtime_profile",))),
        ("repo_config", _extract_path(_normalize_mapping(repo_root.get("plan")), ("runtime_profile",))),
        ("user_config", _extract_path(_normalize_mapping(user_root.get("plan")), ("runtime_profile",))),
    ):
        if raw is _MISSING:
            continue
        normalized = _normalize_runtime_profile_name(raw)
        if normalized is None:
            continue
        requested_profile = normalized
        selected_source = label
        break

    if requested_profile is None:
        return {}, {}

    resolved_profile = get_runtime_profile(requested_profile)
    metadata = {
        "requested_profile": requested_profile,
        "selected_profile_source": selected_source,
        "available_profiles": list(RUNTIME_PROFILE_NAMES),
    }
    if resolved_profile is None:
        metadata["profile_resolution"] = "unknown_profile"
        return {}, metadata

    metadata.update(
        {
            "selected_profile": resolved_profile.name,
            "selected_profile_summary": resolved_profile.summary,
            "profile_resolution": "selected",
            "profile_knob_paths": {
                key: list(value)
                for key, value in resolved_profile.knob_paths().items()
                if value
            },
            "stats_tags": {
                "profile_key": resolved_profile.name,
            },
        }
    )
    return resolved_profile.plan_overrides(), metadata


def _normalize_plan_payload(payload: dict[str, Any]) -> dict[str, Any]:
    index_payload = payload.get("index")
    if isinstance(index_payload, dict):
        languages = _split_csv(index_payload.get("languages"))
        if languages is not None:
            index_payload["languages"] = languages
        conventions = _split_csv(index_payload.get("conventions_files"))
        if conventions is not None:
            index_payload["conventions_files"] = conventions
    lsp_payload = payload.get("lsp")
    if isinstance(lsp_payload, dict):
        for key in ("commands", "xref_commands"):
            value = lsp_payload.get(key)
            if value is not None:
                lsp_payload[key] = parse_lsp_commands_from_config(value)
    return payload


def _validate_root_payload(payload: dict[str, Any]) -> dict[str, Any]:
    meta = payload.get("_meta")
    candidate = dict(payload)
    candidate.pop("_meta", None)
    validated = validate_cli_config(candidate)
    if meta is not None:
        validated["_meta"] = meta
    return validated


def _build_plan_snapshot(
    *,
    user_root: dict[str, Any],
    repo_root: dict[str, Any],
    cwd_root: dict[str, Any],
    cli_overrides: Mapping[str, Any] | None,
    runtime_profile: str | None,
    retrieval_preset: str | Mapping[str, Any] | None,
    config_pack_path: str | Path | None,
    config_pack_overrides: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    user_plan = _normalize_mapping(user_root.get("plan"))
    repo_plan = _normalize_mapping(repo_root.get("plan"))
    cwd_plan = _normalize_mapping(cwd_root.get("plan"))
    preset_plan = _prepare_retrieval_preset_payload(retrieval_preset)
    pack_plan = _prepare_config_pack_overrides(
        config_pack_path=config_pack_path,
        config_pack_overrides=config_pack_overrides,
    )
    cli_plan = _normalize_mapping(cli_overrides)

    merged_root: dict[str, Any] = {}
    for payload in (user_root, repo_root, cwd_root):
        _deep_merge(merged_root, payload)
    validated_root = _validate_root_payload(merged_root)
    profile_plan, profile_metadata = _resolve_runtime_profile_metadata(
        explicit_profile=runtime_profile,
        user_root=user_root,
        repo_root=repo_root,
        cwd_root=cwd_root,
    )
    merged_plan = _normalize_mapping(validated_root.get("plan"))
    for payload in (profile_plan, preset_plan, pack_plan, cli_plan):
        _deep_merge(merged_plan, payload)
    layers = [
        ("cli", cli_plan),
        ("config_pack", pack_plan),
        ("retrieval_preset", preset_plan),
        ("runtime_profile", profile_plan),
        ("cwd_config", cwd_plan),
        ("repo_config", repo_plan),
        ("user_config", user_plan),
    ]
    payload, provenance = _build_payload_and_provenance(specs=_PLAN_SPECS, layers=layers)
    normalized = OrchestratorConfig.model_validate(
        _normalize_plan_payload(payload)
    ).model_dump(exclude_none=False, by_alias=True)
    return normalized, provenance, validated_root, profile_metadata


def _build_runtime_snapshot(
    *,
    user_root: dict[str, Any],
    repo_root: dict[str, Any],
    cwd_root: dict[str, Any],
    cli_overrides: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    layers = [
        ("cli", _normalize_mapping(cli_overrides)),
        ("cwd_config", _normalize_mapping(cwd_root.get("runtime"))),
        ("repo_config", _normalize_mapping(repo_root.get("runtime"))),
        ("user_config", _normalize_mapping(user_root.get("runtime"))),
    ]
    payload, provenance = _build_payload_and_provenance(specs=_RUNTIME_SPECS, layers=layers)
    normalized = RuntimeConfig.model_validate(payload).model_dump(
        exclude_none=False,
        by_alias=True,
    )
    return normalized, provenance


def _env_source(
    *,
    key: str,
    explicit_overrides: Mapping[str, Any],
    env: Mapping[str, Any],
    snapshot_env: Mapping[str, Any],
) -> str | None:
    if key in explicit_overrides:
        return "explicit_override"
    if key in env:
        return "env"
    if key in snapshot_env:
        return "snapshot_env"
    return None


def _build_mcp_snapshot(
    *,
    root: str | Path,
    env: Mapping[str, Any] | None,
    snapshot_env: Mapping[str, Any] | None,
    explicit_overrides: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    live_env = {str(key): str(value) for key, value in dict(env or {}).items()}
    saved_env = {str(key): str(value) for key, value in dict(snapshot_env or {}).items()}
    merged_env = dict(saved_env)
    merged_env.update(live_env)
    overrides = _normalize_mapping(explicit_overrides)

    def _get_str(key: str, default: str = "") -> str:
        return str(merged_env.get(key, default) or default).strip()

    def _get_bool(key: str, default: bool) -> bool:
        raw = _get_str(key)
        if not raw:
            return bool(default)
        normalized = raw.lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
        return bool(default)

    def _get_int(key: str, default: int) -> int:
        raw = _get_str(key)
        if not raw:
            return int(default)
        try:
            return int(raw)
        except Exception:
            return int(default)

    def _get_float(key: str, default: float) -> float:
        raw = _get_str(key)
        if not raw:
            return float(default)
        try:
            return float(raw)
        except Exception:
            return float(default)

    override_root = overrides.get("default_root")
    override_skills = overrides.get("default_skills_dir")

    resolved_root = (
        Path(str(override_root)).expanduser()
        if override_root is not None
        else Path(_get_str("ACE_LITE_DEFAULT_ROOT", ".")).expanduser()
    ).resolve()
    resolved_skills = (
        Path(str(override_skills)).expanduser()
        if override_skills is not None
        else Path(_get_str("ACE_LITE_DEFAULT_SKILLS_DIR", str(resolved_root / "skills"))).expanduser()
    )
    if not resolved_skills.is_absolute():
        resolved_skills = (resolved_root / resolved_skills).resolve()
    else:
        resolved_skills = resolved_skills.resolve()

    user_id_source = _env_source(
        key="ACE_LITE_USER_ID",
        explicit_overrides=overrides,
        env=live_env,
        snapshot_env=saved_env,
    )
    resolved_user_id = _get_str("ACE_LITE_USER_ID") or _get_str("USERNAME") or _get_str("USER") or None
    if user_id_source is None and resolved_user_id is not None:
        user_id_source = "identity_fallback"
    elif user_id_source is None:
        user_id_source = "default"

    snapshot = {
        "default_root": str(resolved_root),
        "default_repo": _get_str("ACE_LITE_DEFAULT_REPO", resolved_root.name or "repo"),
        "default_skills_dir": str(resolved_skills),
        "default_languages": _get_str("ACE_LITE_DEFAULT_LANGUAGES", _DEFAULT_LANGUAGE_PROFILE),
        "config_pack": _get_str("ACE_LITE_CONFIG_PACK"),
        "tokenizer_model": _get_str("ACE_LITE_TOKENIZER_MODEL", "gpt-4o-mini"),
        "memory_primary": _get_str("ACE_LITE_MEMORY_PRIMARY", "none").lower(),
        "memory_secondary": _get_str("ACE_LITE_MEMORY_SECONDARY", "none").lower(),
        "memory_timeout": max(0.1, _get_float("ACE_LITE_MEMORY_TIMEOUT", 3.0)),
        "memory_limit": max(1, _get_int("ACE_LITE_MEMORY_LIMIT", 8)),
        "plan_timeout_seconds": max(1.0, _get_float("ACE_LITE_PLAN_TIMEOUT_SECONDS", 25.0)),
        "mcp_base_url": _get_str("ACE_LITE_MCP_BASE_URL", "http://localhost:8765"),
        "rest_base_url": _get_str("ACE_LITE_REST_BASE_URL", "http://localhost:8765"),
        "embedding_enabled": _get_bool("ACE_LITE_EMBEDDING_ENABLED", False),
        "embedding_provider": _get_str("ACE_LITE_EMBEDDING_PROVIDER", "hash").lower(),
        "embedding_model": _get_str("ACE_LITE_EMBEDDING_MODEL", "hash-v1"),
        "embedding_dimension": max(8, _get_int("ACE_LITE_EMBEDDING_DIMENSION", 256)),
        "embedding_index_path": _get_str("ACE_LITE_EMBEDDING_INDEX_PATH", "context-map/embeddings/index.json"),
        "embedding_rerank_pool": max(1, _get_int("ACE_LITE_EMBEDDING_RERANK_POOL", 24)),
        "embedding_lexical_weight": max(0.0, _get_float("ACE_LITE_EMBEDDING_LEXICAL_WEIGHT", 0.7)),
        "embedding_semantic_weight": max(0.0, _get_float("ACE_LITE_EMBEDDING_SEMANTIC_WEIGHT", 0.3)),
        "embedding_min_similarity": _get_float("ACE_LITE_EMBEDDING_MIN_SIMILARITY", 0.0),
        "embedding_fail_open": _get_bool("ACE_LITE_EMBEDDING_FAIL_OPEN", True),
        "ollama_base_url": _get_str("ACE_LITE_OLLAMA_BASE_URL", "http://localhost:11434"),
        "user_id": resolved_user_id,
        "app": _get_str("ACE_LITE_APP", "codex"),
        "notes_path": _get_str("ACE_LITE_NOTES_PATH", "context-map/memory_notes.jsonl"),
        "server_name": "ACE-Lite MCP Server",
    }
    provenance = {
        "default_root": "explicit_override" if override_root is not None else (_env_source(key="ACE_LITE_DEFAULT_ROOT", explicit_overrides=overrides, env=live_env, snapshot_env=saved_env) or "default"),
        "default_repo": _env_source(key="ACE_LITE_DEFAULT_REPO", explicit_overrides=overrides, env=live_env, snapshot_env=saved_env) or "default",
        "default_skills_dir": "explicit_override" if override_skills is not None else (_env_source(key="ACE_LITE_DEFAULT_SKILLS_DIR", explicit_overrides=overrides, env=live_env, snapshot_env=saved_env) or "default"),
        "default_languages": _env_source(key="ACE_LITE_DEFAULT_LANGUAGES", explicit_overrides=overrides, env=live_env, snapshot_env=saved_env) or "default",
        "config_pack": _env_source(key="ACE_LITE_CONFIG_PACK", explicit_overrides=overrides, env=live_env, snapshot_env=saved_env) or "default",
        "tokenizer_model": _env_source(key="ACE_LITE_TOKENIZER_MODEL", explicit_overrides=overrides, env=live_env, snapshot_env=saved_env) or "default",
        "memory_primary": _env_source(key="ACE_LITE_MEMORY_PRIMARY", explicit_overrides=overrides, env=live_env, snapshot_env=saved_env) or "default",
        "memory_secondary": _env_source(key="ACE_LITE_MEMORY_SECONDARY", explicit_overrides=overrides, env=live_env, snapshot_env=saved_env) or "default",
        "memory_timeout": _env_source(key="ACE_LITE_MEMORY_TIMEOUT", explicit_overrides=overrides, env=live_env, snapshot_env=saved_env) or "default",
        "memory_limit": _env_source(key="ACE_LITE_MEMORY_LIMIT", explicit_overrides=overrides, env=live_env, snapshot_env=saved_env) or "default",
        "plan_timeout_seconds": _env_source(key="ACE_LITE_PLAN_TIMEOUT_SECONDS", explicit_overrides=overrides, env=live_env, snapshot_env=saved_env) or "default",
        "mcp_base_url": _env_source(key="ACE_LITE_MCP_BASE_URL", explicit_overrides=overrides, env=live_env, snapshot_env=saved_env) or "default",
        "rest_base_url": _env_source(key="ACE_LITE_REST_BASE_URL", explicit_overrides=overrides, env=live_env, snapshot_env=saved_env) or "default",
        "embedding_enabled": _env_source(key="ACE_LITE_EMBEDDING_ENABLED", explicit_overrides=overrides, env=live_env, snapshot_env=saved_env) or "default",
        "embedding_provider": _env_source(key="ACE_LITE_EMBEDDING_PROVIDER", explicit_overrides=overrides, env=live_env, snapshot_env=saved_env) or "default",
        "embedding_model": _env_source(key="ACE_LITE_EMBEDDING_MODEL", explicit_overrides=overrides, env=live_env, snapshot_env=saved_env) or "default",
        "embedding_dimension": _env_source(key="ACE_LITE_EMBEDDING_DIMENSION", explicit_overrides=overrides, env=live_env, snapshot_env=saved_env) or "default",
        "embedding_index_path": _env_source(key="ACE_LITE_EMBEDDING_INDEX_PATH", explicit_overrides=overrides, env=live_env, snapshot_env=saved_env) or "default",
        "embedding_rerank_pool": _env_source(key="ACE_LITE_EMBEDDING_RERANK_POOL", explicit_overrides=overrides, env=live_env, snapshot_env=saved_env) or "default",
        "embedding_lexical_weight": _env_source(key="ACE_LITE_EMBEDDING_LEXICAL_WEIGHT", explicit_overrides=overrides, env=live_env, snapshot_env=saved_env) or "default",
        "embedding_semantic_weight": _env_source(key="ACE_LITE_EMBEDDING_SEMANTIC_WEIGHT", explicit_overrides=overrides, env=live_env, snapshot_env=saved_env) or "default",
        "embedding_min_similarity": _env_source(key="ACE_LITE_EMBEDDING_MIN_SIMILARITY", explicit_overrides=overrides, env=live_env, snapshot_env=saved_env) or "default",
        "embedding_fail_open": _env_source(key="ACE_LITE_EMBEDDING_FAIL_OPEN", explicit_overrides=overrides, env=live_env, snapshot_env=saved_env) or "default",
        "ollama_base_url": _env_source(key="ACE_LITE_OLLAMA_BASE_URL", explicit_overrides=overrides, env=live_env, snapshot_env=saved_env) or "default",
        "user_id": user_id_source,
        "app": _env_source(key="ACE_LITE_APP", explicit_overrides=overrides, env=live_env, snapshot_env=saved_env) or "default",
        "notes_path": _env_source(key="ACE_LITE_NOTES_PATH", explicit_overrides=overrides, env=live_env, snapshot_env=saved_env) or "default",
        "server_name": "default",
    }
    return snapshot, provenance


class RuntimeSettingsManager:
    def resolve(
        self,
        *,
        root: str | Path,
        cwd: str | Path | None = None,
        config_file: str = DEFAULT_CONFIG_FILE,
        plan_cli_overrides: Mapping[str, Any] | None = None,
        plan_runtime_profile: str | None = None,
        plan_retrieval_preset: str | Mapping[str, Any] | None = None,
        plan_config_pack_path: str | Path | None = None,
        plan_config_pack_overrides: Mapping[str, Any] | None = None,
        runtime_cli_overrides: Mapping[str, Any] | None = None,
        mcp_env: Mapping[str, Any] | None = None,
        mcp_snapshot_env: Mapping[str, Any] | None = None,
        mcp_explicit_overrides: Mapping[str, Any] | None = None,
    ) -> RuntimeSettingsSnapshot:
        user_root, repo_root, cwd_root, loaded_files = _load_layer_sources(
            root=root,
            cwd=cwd,
            filename=config_file,
        )
        plan_snapshot, plan_provenance, validated_root, plan_metadata = _build_plan_snapshot(
            user_root=user_root,
            repo_root=repo_root,
            cwd_root=cwd_root,
            cli_overrides=plan_cli_overrides,
            runtime_profile=plan_runtime_profile,
            retrieval_preset=plan_retrieval_preset,
            config_pack_path=plan_config_pack_path,
            config_pack_overrides=plan_config_pack_overrides,
        )
        runtime_snapshot, runtime_provenance = _build_runtime_snapshot(
            user_root=user_root,
            repo_root=repo_root,
            cwd_root=cwd_root,
            cli_overrides=runtime_cli_overrides,
        )
        mcp_snapshot, mcp_provenance = _build_mcp_snapshot(
            root=root,
            env=mcp_env,
            snapshot_env=mcp_snapshot_env,
            explicit_overrides=mcp_explicit_overrides,
        )
        snapshot = {
            "plan": plan_snapshot,
            "runtime": runtime_snapshot,
            "mcp": mcp_snapshot,
        }
        provenance = {
            "plan": plan_provenance,
            "runtime": runtime_provenance,
            "mcp": mcp_provenance,
        }
        metadata = {
            "root": str(Path(root).resolve()),
            "cwd": str(Path(cwd).resolve() if cwd is not None else Path.cwd().resolve()),
            "config_file": str(config_file),
            "loaded_files": loaded_files,
            "validated_meta": validated_root.get("_meta", {}),
        }
        metadata.update(plan_metadata)
        fingerprint = build_runtime_settings_fingerprint(snapshot)
        stats_tags = (
            dict(metadata.get("stats_tags", {}))
            if isinstance(metadata.get("stats_tags"), dict)
            else {}
        )
        if metadata.get("selected_profile"):
            stats_tags.setdefault(
                "profile_key",
                str(metadata.get("selected_profile")).strip().lower(),
            )
        stats_tags["settings_fingerprint"] = fingerprint
        metadata["stats_tags"] = stats_tags
        return RuntimeSettingsSnapshot(
            snapshot=snapshot,
            provenance=provenance,
            fingerprint=fingerprint,
            metadata=metadata,
        )


__all__ = [
    "RuntimeSettingsManager",
    "RuntimeSettingsSnapshot",
]
