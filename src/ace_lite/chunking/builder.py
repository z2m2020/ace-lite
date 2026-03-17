"""Chunk candidate builder for the index stage.

This module turns file-level candidates plus indexed symbols into a ranked,
budget-aware list of "chunk references" (function/class/method definitions).
"""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Any

from ace_lite.chunking.diversity import calculate_diversity_penalty, chunk_symbol_family
from ace_lite.chunking.disclosure_policy import (
    CHUNK_DISCLOSURE_CHOICES,
    is_skeleton_disclosure,
    normalize_chunk_disclosure,
    resolve_chunk_disclosure,
)
from ace_lite.chunking.graph_closure import apply_graph_closure_bonus
from ace_lite.chunking.graph_prior import apply_query_aware_graph_prior
from ace_lite.chunking.robust_signature import (
    build_robust_signature_lite,
    summarize_robust_signature,
)
from ace_lite.chunking.scoring import score_chunk_candidate
from ace_lite.chunking.skeleton import build_chunk_skeleton
from ace_lite.chunking.topological_shield import compute_topological_shield
from ace_lite.chunking.types import ChunkMetrics
from ace_lite.token_estimator import estimate_tokens

_REFERENCE_HITS_CACHE: OrderedDict[str, dict[str, int]] = OrderedDict()
_REFERENCE_HITS_CACHE_CAP = 8
_TOKEN_ESTIMATE_CACHE: OrderedDict[tuple[str, str, str, str, str], int] = OrderedDict()
_TOKEN_ESTIMATE_CACHE_CAP = 4096


def _build_reference_hits(files_map: dict[str, dict[str, Any]]) -> dict[str, int]:
    reference_hits: dict[str, int] = {}
    for entry in files_map.values():
        if not isinstance(entry, dict):
            continue
        references = entry.get("references", [])
        if not isinstance(references, list):
            continue
        for item in references:
            if not isinstance(item, dict):
                continue
            qualified_name = str(item.get("qualified_name") or "").strip().lstrip(".")
            name = str(item.get("name") or "").strip().lstrip(".")
            for key in (qualified_name, name):
                if not key:
                    continue
                reference_hits[key] = int(reference_hits.get(key, 0)) + 1
    return reference_hits


def _get_reference_hits(
    *,
    files_map: dict[str, dict[str, Any]],
    cache_key: str,
) -> dict[str, int]:
    normalized_key = str(cache_key or "").strip()
    if normalized_key:
        cached = _REFERENCE_HITS_CACHE.get(normalized_key)
        if isinstance(cached, dict):
            _REFERENCE_HITS_CACHE.move_to_end(normalized_key)
            return cached

    hits = _build_reference_hits(files_map)
    if normalized_key:
        _REFERENCE_HITS_CACHE[normalized_key] = hits
        _REFERENCE_HITS_CACHE.move_to_end(normalized_key)
        while len(_REFERENCE_HITS_CACHE) > _REFERENCE_HITS_CACHE_CAP:
            _REFERENCE_HITS_CACHE.popitem(last=False)
    return hits


def read_signature_line(*, root: str, path: str, lineno: int) -> str:
    """Read a single signature line from the given file and line number."""
    try:
        source = (Path(root) / Path(path)).resolve()
        lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
        index = max(0, int(lineno) - 1)
        if index >= len(lines):
            return ""
        return lines[index].strip()[:240]
    except Exception:
        return ""


def normalize_chunk_disclosure(value: str) -> str:
    from ace_lite.chunking.disclosure_policy import normalize_chunk_disclosure as _normalize

    return _normalize(value)


def _read_file_lines(*, root: str, path: str) -> list[str]:
    try:
        source = (Path(root) / Path(path)).resolve()
        return source.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []


def _extract_signature(*, lines: list[str], lineno: int) -> str:
    index = max(0, int(lineno) - 1)
    if index >= len(lines):
        return ""
    return lines[index].strip()[:240]


def _resolve_parent_class_signature(
    *,
    lines: list[str],
    start_line: int,
    symbol: dict[str, Any] | None,
    all_symbols: list[Any] | None,
) -> str:
    if not symbol or not all_symbols:
        return ""

    qualified_name = str(symbol.get("qualified_name") or "").strip()
    if "." not in qualified_name:
        return ""

    parent_name = qualified_name.rsplit(".", 1)[0]
    for item in all_symbols:
        if not isinstance(item, dict):
            continue
        item_kind = str(item.get("kind") or "").strip().lower()
        item_name = str(item.get("qualified_name") or item.get("name") or "").strip()
        if item_kind != "class" or item_name != parent_name:
            continue
        parent_lineno = int(item.get("lineno") or 0)
        if 0 < parent_lineno < start_line:
            return _extract_signature(lines=lines, lineno=parent_lineno)
        return ""
    return ""


def _format_import_entry(item: Any) -> str:
    if isinstance(item, str):
        return str(item).strip()
    if not isinstance(item, dict):
        return ""

    import_type = str(item.get("type") or "").strip().lower()
    module = str(item.get("module") or "").strip()
    name = str(item.get("name") or "").strip()
    alias = str(item.get("alias") or "").strip()

    if import_type == "from" and module and name:
        rendered = f"from {module} import {name}"
    elif module:
        rendered = f"import {module}"
    elif name:
        rendered = name
    else:
        return ""

    if alias:
        rendered = f"{rendered} as {alias}"
    return rendered


def _extract_snippet(
    *,
    lines: list[str],
    lineno: int,
    end_lineno: int,
    max_lines: int,
    max_chars: int,
    symbol: dict[str, Any] | None = None,
    all_symbols: list[Any] | None = None,
    file_entry: dict[str, Any] | None = None,
) -> str:
    if not lines:
        return ""

    start_line = max(1, int(lineno))
    end_line = max(start_line, int(end_lineno) or start_line)
    limit_lines = max(1, int(max_lines))
    limit_chars = max(0, int(max_chars))

    context_prefix: list[str] = []

    class_sig = _resolve_parent_class_signature(
        lines=lines,
        start_line=start_line,
        symbol=symbol,
        all_symbols=all_symbols,
    )
    if class_sig:
        context_prefix.append(f"# Context: {class_sig}")

    if file_entry and isinstance(file_entry.get("imports"), list):
        imports = [
            rendered
            for rendered in (_format_import_entry(imp) for imp in file_entry["imports"])
            if rendered
        ]
        if imports:
            import_str = ", ".join(imports[:3])
            if len(imports) > 3:
                import_str += ", ..."
            context_prefix.append(f"# Imports: {import_str}")

    prefix_lines: list[str] = []
    if context_prefix and limit_lines > 1:
        max_prefix_lines = max(0, limit_lines - 1)
        if max_prefix_lines >= len(context_prefix):
            prefix_lines = list(context_prefix)
            if limit_lines >= len(context_prefix) + 2:
                prefix_lines.append("...")
        else:
            prefix_lines = list(context_prefix[:max_prefix_lines])

    body_line_budget = max(1, limit_lines - len(prefix_lines))
    end_line = min(end_line, start_line + body_line_budget - 1)

    start_index = start_line - 1
    end_exclusive = min(len(lines), end_line)
    if end_exclusive <= start_index:
        return ""

    snippet_lines = lines[start_index:end_exclusive]
    snippet_parts = [*prefix_lines, *snippet_lines]
    snippet = "\n".join(snippet_parts).strip()
    if limit_chars and len(snippet) > limit_chars:
        return snippet[:limit_chars]
    return snippet


def _build_retrieval_context(
    *,
    path: str,
    qualified_name: str,
    kind: str,
    signature: str,
    lines: list[str],
    start_line: int,
    symbol: dict[str, Any] | None,
    all_symbols: list[Any] | None,
    file_entry: dict[str, Any] | None,
) -> str:
    context_parts: list[str] = []

    module = str((file_entry or {}).get("module") or "").strip()
    language = str((file_entry or {}).get("language") or "").strip().lower()
    if module:
        context_parts.append(f"module={module}")
    if language:
        context_parts.append(f"language={language}")
    if kind:
        context_parts.append(f"kind={kind}")
    if path:
        context_parts.append(f"path={path}")
    if qualified_name:
        context_parts.append(f"symbol={qualified_name}")
    if signature:
        context_parts.append(f"signature={signature[:240]}")

    class_sig = _resolve_parent_class_signature(
        lines=lines,
        start_line=start_line,
        symbol=symbol,
        all_symbols=all_symbols,
    )
    if class_sig:
        context_parts.append(f"parent={class_sig[:240]}")

    imports = (
        file_entry.get("imports", [])
        if isinstance(file_entry, dict) and isinstance(file_entry.get("imports"), list)
        else []
    )
    import_values = [
        rendered for rendered in (_format_import_entry(item) for item in imports) if rendered
    ]
    if import_values:
        joined = ", ".join(import_values[:3])
        if len(import_values) > 3:
            joined += ", ..."
        context_parts.append(f"imports={joined}")

    return "\n".join(context_parts).strip()


def estimate_chunk_tokens(
    *,
    path: str,
    qualified_name: str,
    signature: str,
    snippet: str = "",
    tokenizer_model: str = "gpt-4o",
) -> int:
    """Estimate tokens for a chunk reference payload."""
    cache_key = (
        str(tokenizer_model or ""),
        str(path or ""),
        str(qualified_name or ""),
        str(signature or ""),
        str(snippet or ""),
    )
    cached = _TOKEN_ESTIMATE_CACHE.get(cache_key)
    if cached is not None:
        _TOKEN_ESTIMATE_CACHE.move_to_end(cache_key)
        return int(cached)

    text = f"{path} {qualified_name} {signature} {snippet}".strip()
    if not text:
        return 12
    estimated = max(12, estimate_tokens(text, model=tokenizer_model) + 8)
    _TOKEN_ESTIMATE_CACHE[cache_key] = int(estimated)
    _TOKEN_ESTIMATE_CACHE.move_to_end(cache_key)
    while len(_TOKEN_ESTIMATE_CACHE) > _TOKEN_ESTIMATE_CACHE_CAP:
        _TOKEN_ESTIMATE_CACHE.popitem(last=False)
    return int(estimated)


def build_candidate_chunks(
    *,
    root: str,
    files_map: dict[str, dict[str, Any]],
    candidates: list[dict[str, Any]],
    terms: list[str],
    top_k_files: int,
    top_k_chunks: int,
    per_file_limit: int,
    token_budget: int,
    disclosure_mode: str,
    snippet_max_lines: int,
    snippet_max_chars: int,
    policy: dict[str, Any],
    tokenizer_model: str,
    diversity_enabled: bool,
    diversity_path_penalty: float,
    diversity_symbol_family_penalty: float,
    diversity_kind_penalty: float,
    diversity_locality_penalty: float,
    diversity_locality_window: int,
    topological_shield_enabled: bool = False,
    topological_shield_mode: str = "off",
    topological_shield_max_attenuation: float = 0.6,
    topological_shield_shared_parent_attenuation: float = 0.2,
    topological_shield_adjacency_attenuation: float = 0.5,
    reference_hits_cache_key: str = "",
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    """Build chunk candidates for the index stage.

    Args:
        root: Repository root.
        files_map: Index file map.
        candidates: Ranked file candidates.
        terms: Query terms.
        top_k_files: Number of top files to mine for symbols.
        top_k_chunks: Number of chunks to return.
        per_file_limit: Per-file chunk cap.
        token_budget: Token budget for selected chunks.
        include_signature: Whether to read a signature line from disk.
        policy: Retrieval policy dict for weight adjustments.
        tokenizer_model: Token estimator model name.
        diversity_enabled: Whether diversity penalties are enabled.
        diversity_*: Diversity penalty configuration values.

    Returns:
        Tuple of (selected_chunks, metrics_dict).
    """
    if not isinstance(files_map, dict):
        normalized_topological_mode = (
            str(topological_shield_mode or "off").strip().lower() or "off"
        )
        metrics = ChunkMetrics()
        metrics.diversity_enabled = bool(diversity_enabled)
        metrics.topological_shield_enabled = bool(topological_shield_enabled)
        metrics.topological_shield_report_only = (
            bool(topological_shield_enabled)
            and normalized_topological_mode == "report_only"
        )
        return [], metrics.to_dict()

    reference_hits = _get_reference_hits(
        files_map=files_map,
        cache_key=reference_hits_cache_key,
    )

    raw_chunk_candidates: list[dict[str, Any]] = []
    policy_chunk_weight = max(0.1, float(policy.get("chunk_weight", 1.0) or 1.0))
    disclosure = normalize_chunk_disclosure(disclosure_mode)
    needs_source_lines = True
    snippet_lines_limit = max(1, int(snippet_max_lines))
    snippet_chars_limit = max(0, int(snippet_max_chars))

    ranked_files = [item for item in candidates if isinstance(item, dict)]
    for file_candidate in ranked_files[: max(1, int(top_k_files))]:
        path = str(file_candidate.get("path") or "").strip()
        if not path:
            continue
        file_entry = files_map.get(path)
        if not isinstance(file_entry, dict):
            continue

        symbols = file_entry.get("symbols", [])
        if not isinstance(symbols, list):
            continue

        file_lines: list[str] = []
        if needs_source_lines:
            file_lines = _read_file_lines(root=root, path=path)

        language = str(file_entry.get("language") or "").strip().lower()
        imports = (
            file_entry.get("imports", [])
            if isinstance(file_entry.get("imports"), list)
            else []
        )
        references = (
            file_entry.get("references", [])
            if isinstance(file_entry.get("references"), list)
            else []
        )

        for symbol in symbols:
            if not isinstance(symbol, dict):
                continue

            kind = str(symbol.get("kind") or "").strip().lower()
            if kind not in {"function", "async_function", "method", "class", "type", "section"}:
                continue

            lineno = int(symbol.get("lineno") or 0)
            end_lineno = int(symbol.get("end_lineno") or lineno)
            if lineno <= 0:
                continue
            if end_lineno < lineno:
                end_lineno = lineno

            qualified_name = str(
                symbol.get("qualified_name") or symbol.get("name") or ""
            ).strip()
            name = str(symbol.get("name") or "").strip()
            if not qualified_name and not name:
                continue

            resolved_disclosure, fallback_reason = resolve_chunk_disclosure(
                requested_mode=disclosure,
                path=path,
                file_entry=file_entry,
            )
            signature = _extract_signature(lines=file_lines, lineno=lineno) if file_lines else ""
            snippet = ""
            if resolved_disclosure == "snippet" and file_lines:
                snippet = _extract_snippet(
                    lines=file_lines,
                    lineno=lineno,
                    end_lineno=end_lineno,
                    max_lines=snippet_lines_limit,
                    max_chars=snippet_chars_limit,
                    symbol=symbol,
                    all_symbols=symbols,
                    file_entry=file_entry,
                )
            retrieval_context = _build_retrieval_context(
                path=path,
                qualified_name=qualified_name or name,
                kind=kind,
                signature=signature,
                lines=file_lines,
                start_line=lineno,
                symbol=symbol,
                all_symbols=symbols,
                file_entry=file_entry,
            )
            score, breakdown = score_chunk_candidate(
                path=path,
                module=str(file_entry.get("module") or ""),
                qualified_name=qualified_name,
                name=name,
                signature=signature,
                terms=terms,
                file_score=float(file_candidate.get("score") or 0.0),
                reference_hits=reference_hits,
            )
            score *= policy_chunk_weight
            breakdown["policy_chunk_weight"] = round(policy_chunk_weight, 6)

            raw_chunk_candidates.append(
                {
                    "path": path,
                    "name": name,
                    "qualified_name": qualified_name or name,
                    "kind": kind,
                    "lineno": lineno,
                    "end_lineno": end_lineno,
                    "language": language,
                    "module": str(file_entry.get("module") or ""),
                    "sha256": str(file_entry.get("sha256") or ""),
                    "size_bytes": int(file_entry.get("size_bytes") or 0),
                    "generated": bool(file_entry.get("generated", False)),
                    "imports_count": len(imports),
                    "references_count": len(references),
                    "signature": signature,
                    "snippet": snippet,
                    "_retrieval_context": retrieval_context,
                    "_requested_disclosure": disclosure,
                    "_resolved_disclosure": resolved_disclosure,
                    "_disclosure_fallback_reason": fallback_reason,
                    "_robust_signature_lite": build_robust_signature_lite(
                        path=path,
                        qualified_name=qualified_name or name,
                        name=name,
                        kind=kind,
                        signature=signature,
                        imports=imports,
                        references=references,
                    ),
                    "score": round(float(score), 6),
                    "score_breakdown": dict(breakdown),
                }
            )

    total_candidates = len(raw_chunk_candidates)
    if total_candidates <= 0:
        normalized_topological_mode = (
            str(topological_shield_mode or "off").strip().lower() or "off"
        )
        metrics = ChunkMetrics(
            diversity_enabled=bool(diversity_enabled),
            topological_shield_enabled=bool(topological_shield_enabled),
            topological_shield_report_only=(
                bool(topological_shield_enabled)
                and normalized_topological_mode == "report_only"
            ),
        )
        return [], metrics.to_dict()

    raw_chunk_candidates, graph_prior_payload = apply_query_aware_graph_prior(
        candidate_chunks=raw_chunk_candidates,
        files_map=files_map,
        policy=policy,
        cache_key=reference_hits_cache_key,
    )
    raw_chunk_candidates, graph_closure_payload = apply_graph_closure_bonus(
        candidate_chunks=raw_chunk_candidates,
        files_map=files_map,
        policy=policy,
        cache_key=reference_hits_cache_key,
    )

    raw_chunk_candidates.sort(
        key=lambda item: (
            -float(item.get("score") or 0.0),
            str(item.get("path") or ""),
            int(item.get("lineno") or 0),
            str(item.get("qualified_name") or ""),
        )
    )
    preselect_limit = max(
        16,
        int(top_k_chunks) * 6,
        int(top_k_files) * int(per_file_limit) * 8,
    )
    preselected = raw_chunk_candidates[:preselect_limit]

    remaining: list[dict[str, Any]] = []
    for item in preselected:
        path = str(item.get("path") or "")
        qualified_name = str(item.get("qualified_name") or "")
        signature = str(item.get("signature") or "")
        snippet = str(item.get("snippet") or "")
        resolved_disclosure = normalize_chunk_disclosure(
            str(item.get("_resolved_disclosure") or disclosure)
        )
        requested_disclosure = normalize_chunk_disclosure(
            str(item.get("_requested_disclosure") or disclosure)
        )
        estimated_tokens = estimate_chunk_tokens(
            path=path,
            qualified_name=qualified_name,
            signature=signature,
            snippet=snippet,
            tokenizer_model=tokenizer_model,
        )
        score_breakdown = item.get("score_breakdown")
        if not isinstance(score_breakdown, dict):
            score_breakdown = {}
        robust_signature = (
            item.get("_robust_signature_lite")
            if isinstance(item.get("_robust_signature_lite"), dict)
            else None
        )
        robust_signature_summary = summarize_robust_signature(robust_signature)
        payload: dict[str, Any] = {
            "path": path,
            "qualified_name": qualified_name,
            "kind": str(item.get("kind") or ""),
            "lineno": int(item.get("lineno") or 0),
            "end_lineno": int(item.get("end_lineno") or int(item.get("lineno") or 0)),
            "score": round(float(item.get("score") or 0.0), 6),
            "disclosure": resolved_disclosure,
            "score_breakdown": {
                **score_breakdown,
                "estimated_tokens": estimated_tokens,
            },
        }
        if requested_disclosure != resolved_disclosure:
            payload["disclosure_requested"] = requested_disclosure
        fallback_reason = str(item.get("_disclosure_fallback_reason") or "").strip()
        if fallback_reason:
            payload["disclosure_fallback_reason"] = fallback_reason
        if robust_signature_summary.get("available", False):
            payload["robust_signature_summary"] = robust_signature_summary
            payload["_robust_signature_lite"] = robust_signature
        retrieval_context = str(item.get("_retrieval_context") or "").strip()
        if retrieval_context:
            payload["_retrieval_context"] = retrieval_context
        if is_skeleton_disclosure(resolved_disclosure):
            payload["skeleton"] = build_chunk_skeleton(
                chunk=item,
                disclosure_mode=resolved_disclosure,
                robust_signature=robust_signature,
            )
        if resolved_disclosure in {"signature", "snippet"}:
            payload["signature"] = signature
        if resolved_disclosure == "snippet":
            payload["snippet"] = snippet
        remaining.append(payload)
    remaining.sort(
        key=lambda item: (
            -float(item.get("score") or 0.0),
            str(item.get("path") or ""),
            int(item.get("lineno") or 0),
            str(item.get("qualified_name") or ""),
        )
    )

    selected: list[dict[str, Any]] = []
    per_file_counter: dict[str, int] = {}
    used_tokens = 0
    limit_top_k = max(1, int(top_k_chunks))
    limit_per_file = max(1, int(per_file_limit))
    limit_budget = max(1, int(token_budget))
    normalized_topological_mode = (
        str(topological_shield_mode or "off").strip().lower() or "off"
    )

    while remaining and len(selected) < limit_top_k:
        best_index = -1
        best_sort_key: tuple[float, str, int, str] | None = None
        best_adjusted = 0.0
        best_penalty = 0.0
        best_topological_shield: dict[str, Any] | None = None

        for index, item in enumerate(remaining):
            path = str(item.get("path") or "")
            if not path:
                continue

            current_count = int(per_file_counter.get(path, 0))
            if current_count >= limit_per_file:
                continue

            estimated_tokens = int(
                item.get("score_breakdown", {}).get("estimated_tokens", 0) or 0
            )
            if used_tokens + estimated_tokens > limit_budget:
                continue

            base_score = max(0.0, float(item.get("score") or 0.0))
            penalty = calculate_diversity_penalty(
                candidate=item,
                selected=selected,
                diversity_enabled=diversity_enabled,
                path_penalty=diversity_path_penalty,
                symbol_family_penalty=diversity_symbol_family_penalty,
                kind_penalty=diversity_kind_penalty,
                locality_penalty=diversity_locality_penalty,
                locality_window=diversity_locality_window,
            )
            adjusted_score = max(0.0, base_score - penalty)
            topological_shield = compute_topological_shield(
                candidate=item,
                selected=selected,
                files_map=files_map,
                cache_key=reference_hits_cache_key,
                base_penalty=penalty,
                base_score=base_score,
                enabled=bool(topological_shield_enabled),
                mode=normalized_topological_mode,
                max_attenuation=float(topological_shield_max_attenuation),
                shared_parent_attenuation=float(
                    topological_shield_shared_parent_attenuation
                ),
                adjacency_attenuation=float(
                    topological_shield_adjacency_attenuation
                ),
            )

            sort_key = (
                -adjusted_score,
                path,
                int(item.get("lineno") or 0),
                str(item.get("qualified_name") or ""),
            )
            if best_sort_key is None or sort_key < best_sort_key:
                best_sort_key = sort_key
                best_index = index
                best_adjusted = adjusted_score
                best_penalty = penalty
                best_topological_shield = dict(topological_shield)

        if best_index < 0:
            break

        chosen = remaining.pop(best_index)
        chosen["score"] = round(best_adjusted, 6)
        chosen_breakdown = chosen.get("score_breakdown")
        if not isinstance(chosen_breakdown, dict):
            chosen_breakdown = {}
            chosen["score_breakdown"] = chosen_breakdown
        chosen_breakdown["diversity_penalty"] = round(best_penalty, 6)
        chosen_breakdown["diversity_adjusted_score"] = round(best_adjusted, 6)
        chosen_breakdown["diversity_selected"] = 1.0
        if isinstance(best_topological_shield, dict):
            chosen["_topological_shield"] = dict(best_topological_shield)
            chosen_breakdown["topological_shield_enabled"] = (
                1.0 if best_topological_shield.get("enabled", False) else 0.0
            )
            chosen_breakdown["topological_shield_report_only"] = (
                1.0 if best_topological_shield.get("report_only", False) else 0.0
            )
            chosen_breakdown["topological_shield_base_diversity_penalty"] = float(
                best_topological_shield.get("base_penalty", 0.0) or 0.0
            )
            chosen_breakdown["topological_shield_attenuation"] = float(
                best_topological_shield.get("attenuation", 0.0) or 0.0
            )
            chosen_breakdown["topological_shield_penalty_delta"] = float(
                best_topological_shield.get("penalty_delta", 0.0) or 0.0
            )
            chosen_breakdown["topological_shield_adjusted_penalty"] = float(
                best_topological_shield.get("adjusted_penalty", 0.0) or 0.0
            )
            chosen_breakdown["topological_shield_adjusted_score"] = float(
                best_topological_shield.get("adjusted_score", 0.0) or 0.0
            )
            chosen_breakdown["topological_shield_evidence_count"] = float(
                best_topological_shield.get("evidence_count", 0) or 0
            )
            chosen_breakdown["topological_shield_adjacency_evidence_count"] = float(
                best_topological_shield.get("adjacency_evidence_count", 0) or 0
            )
            chosen_breakdown[
                "topological_shield_shared_parent_evidence_count"
            ] = float(
                best_topological_shield.get("shared_parent_evidence_count", 0) or 0
            )
            chosen_breakdown["topological_shield_graph_attested"] = (
                1.0 if best_topological_shield.get("graph_attested", False) else 0.0
            )

        selected.append(chosen)
        chosen_path = str(chosen.get("path") or "").strip()
        per_file_counter[chosen_path] = int(per_file_counter.get(chosen_path, 0)) + 1
        used_tokens += int(chosen_breakdown.get("estimated_tokens", 0) or 0)

    file_counts = [count for count in per_file_counter.values() if count > 0]
    chunks_per_file_mean = (sum(file_counts) / len(file_counts)) if file_counts else 0.0
    unique_files = {
        str(item.get("path") or "").strip()
        for item in selected
        if str(item.get("path") or "").strip()
    }
    unique_families = {
        chunk_symbol_family(str(item.get("qualified_name") or ""))
        for item in selected
        if chunk_symbol_family(str(item.get("qualified_name") or ""))
    }
    retrieval_context_lengths = [
        len(str(item.get("_retrieval_context") or "").strip())
        for item in selected
        if isinstance(item, dict) and str(item.get("_retrieval_context") or "").strip()
    ]
    retrieval_context_chunk_count = len(retrieval_context_lengths)
    robust_signature_count = sum(
        1
        for item in selected
        if isinstance(item, dict)
        and isinstance(item.get("robust_signature_summary"), dict)
        and bool(item["robust_signature_summary"].get("available", False))
    )
    graph_prior_chunk_count = 0
    graph_seeded_chunk_count = 0
    graph_transfer_count = 0
    graph_hub_suppressed_chunk_count = 0
    graph_prior_total = 0.0
    graph_hub_penalty_total = 0.0
    graph_closure_boosted_chunk_count = 0
    graph_closure_total = 0.0
    topological_shield_attenuated_chunk_count = 0
    topological_shield_adjacency_evidence_count = 0
    topological_shield_shared_parent_evidence_count = 0
    topological_shield_graph_attested_chunk_count = 0
    topological_shield_attenuation_total = 0.0
    for item in selected:
        if not isinstance(item, dict):
            continue
        breakdown = (
            item.get("score_breakdown")
            if isinstance(item.get("score_breakdown"), dict)
            else {}
        )
        graph_prior = float(breakdown.get("graph_prior", 0.0) or 0.0)
        if graph_prior > 0.0:
            graph_prior_chunk_count += 1
            graph_prior_total += graph_prior
        graph_seeded = float(breakdown.get("graph_seeded", 0.0) or 0.0)
        if graph_seeded > 0.0:
            graph_seeded_chunk_count += 1
        graph_transfer_count += int(breakdown.get("graph_transfer_count", 0) or 0)
        graph_hub_penalty = abs(float(breakdown.get("graph_hub_penalty", 0.0) or 0.0))
        if graph_hub_penalty > 0.0:
            graph_hub_suppressed_chunk_count += 1
            graph_hub_penalty_total += graph_hub_penalty
        graph_closure_bonus = float(breakdown.get("graph_closure_bonus", 0.0) or 0.0)
        if graph_closure_bonus > 0.0:
            graph_closure_boosted_chunk_count += 1
            graph_closure_total += graph_closure_bonus
        topological_shield_attenuation = float(
            breakdown.get("topological_shield_attenuation", 0.0) or 0.0
        )
        if topological_shield_attenuation > 0.0:
            topological_shield_attenuated_chunk_count += 1
            topological_shield_attenuation_total += topological_shield_attenuation
        topological_shield_adjacency_evidence_count += int(
            breakdown.get("topological_shield_adjacency_evidence_count", 0) or 0
        )
        topological_shield_shared_parent_evidence_count += int(
            breakdown.get("topological_shield_shared_parent_evidence_count", 0) or 0
        )
        if float(breakdown.get("topological_shield_graph_attested", 0.0) or 0.0) > 0.0:
            topological_shield_graph_attested_chunk_count += 1

    selected_count = len(selected)
    dedup_ratio = (
        max(0.0, 1.0 - (selected_count / total_candidates))
        if total_candidates > 0
        else 0.0
    )

    metrics = ChunkMetrics(
        candidate_chunk_count=selected_count,
        candidate_chunks_total=total_candidates,
        candidate_chunks_selected=selected_count,
        chunks_per_file_mean=float(chunks_per_file_mean),
        chunk_budget_used=int(used_tokens),
        dedup_ratio=float(dedup_ratio),
        unique_files_in_chunks=len(unique_files),
        unique_symbol_families_in_chunks=len(unique_families),
        retrieval_context_chunk_count=int(retrieval_context_chunk_count),
        retrieval_context_coverage_ratio=(
            float(retrieval_context_chunk_count) / float(selected_count)
            if selected_count > 0
            else 0.0
        ),
        retrieval_context_char_count_mean=(
            round(
                float(sum(retrieval_context_lengths))
                / float(retrieval_context_chunk_count),
                6,
            )
            if retrieval_context_chunk_count > 0
            else 0.0
        ),
        robust_signature_count=int(robust_signature_count),
        robust_signature_coverage_ratio=(
            float(robust_signature_count) / float(selected_count)
            if selected_count > 0
            else 0.0
        ),
        graph_prior_chunk_count=int(
            graph_prior_chunk_count
            if selected_count > 0
            else int(graph_prior_payload.get("boosted_chunk_count", 0) or 0)
        ),
        graph_prior_coverage_ratio=(
            float(
                graph_prior_chunk_count
                if selected_count > 0
                else int(graph_prior_payload.get("boosted_chunk_count", 0) or 0)
            )
            / float(selected_count)
            if selected_count > 0
            else 0.0
        ),
        graph_prior_total=round(
            float(graph_prior_total)
            if selected_count > 0
            else float(graph_prior_payload.get("graph_prior_total", 0.0) or 0.0),
            6,
        ),
        graph_seeded_chunk_count=int(
            graph_seeded_chunk_count
            if selected_count > 0
            else int(graph_prior_payload.get("seeded_chunk_count", 0) or 0)
        ),
        graph_transfer_count=int(
            graph_transfer_count
            if selected_count > 0
            else int(graph_prior_payload.get("graph_transfer_count", 0) or 0)
        ),
        graph_hub_suppressed_chunk_count=int(
            graph_hub_suppressed_chunk_count
            if selected_count > 0
            else int(graph_prior_payload.get("hub_suppressed_chunk_count", 0) or 0)
        ),
        graph_hub_penalty_total=round(
            float(graph_hub_penalty_total)
            if selected_count > 0
            else float(graph_prior_payload.get("graph_hub_penalty_total", 0.0) or 0.0),
            6,
        ),
        graph_closure_enabled=bool(graph_closure_payload.get("enabled", False)),
        graph_closure_boosted_chunk_count=int(
            graph_closure_boosted_chunk_count
            if selected_count > 0
            else int(graph_closure_payload.get("boosted_chunk_count", 0) or 0)
        ),
        graph_closure_coverage_ratio=(
            float(
                graph_closure_boosted_chunk_count
                if selected_count > 0
                else int(graph_closure_payload.get("boosted_chunk_count", 0) or 0)
            )
            / float(selected_count)
            if selected_count > 0
            else 0.0
        ),
        graph_closure_anchor_count=int(
            graph_closure_payload.get("anchor_count", 0) or 0
        ),
        graph_closure_support_edge_count=int(
            graph_closure_payload.get("support_edge_count", 0) or 0
        ),
        graph_closure_total=round(
            float(graph_closure_total)
            if selected_count > 0
            else float(graph_closure_payload.get("graph_closure_total", 0.0) or 0.0),
            6,
        ),
        diversity_enabled=bool(diversity_enabled),
        topological_shield_enabled=bool(topological_shield_enabled),
        topological_shield_report_only=(
            bool(topological_shield_enabled)
            and normalized_topological_mode == "report_only"
        ),
        topological_shield_attenuated_chunk_count=int(
            topological_shield_attenuated_chunk_count
        ),
        topological_shield_coverage_ratio=(
            float(topological_shield_attenuated_chunk_count) / float(selected_count)
            if selected_count > 0
            else 0.0
        ),
        topological_shield_adjacency_evidence_count=int(
            topological_shield_adjacency_evidence_count
        ),
        topological_shield_shared_parent_evidence_count=int(
            topological_shield_shared_parent_evidence_count
        ),
        topological_shield_graph_attested_chunk_count=int(
            topological_shield_graph_attested_chunk_count
        ),
        topological_shield_attenuation_total=round(
            float(topological_shield_attenuation_total), 6
        ),
    )

    return selected, metrics.to_dict()


__all__ = [
    "build_candidate_chunks",
    "estimate_chunk_tokens",
    "normalize_chunk_disclosure",
    "read_signature_line",
]
