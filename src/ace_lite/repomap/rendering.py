from __future__ import annotations

from typing import Any

from ace_lite.repomap.tags import extract_code_tags
from ace_lite.token_estimator import estimate_tokens


def _render_skeleton_markdown(
    *,
    files: dict[str, dict[str, Any]],
    seed_paths: list[str],
    neighbor_paths: list[str],
    subgraph_payload: dict[str, Any] | None = None,
    budget_tokens: int,
    neighbor_depth: int,
    tokenizer_model: str | None,
    estimate_tokens_fn: Any = estimate_tokens,
) -> tuple[str, int, list[str], dict[str, int]]:
    header = [
        "# RepoMap Skeleton",
        "",
        "## Focus Seeds",
        "",
    ]
    used_tokens = estimate_tokens_fn("\n".join(header), model=tokenizer_model)
    lines: list[str] = list(header)
    reserved_neighbor_tokens = _estimate_neighbor_reserve_tokens(
        files=files,
        neighbor_paths=neighbor_paths,
        budget_tokens=budget_tokens,
        neighbor_depth=neighbor_depth,
        tokenizer_model=tokenizer_model,
        estimate_tokens_fn=estimate_tokens_fn,
    )
    seed_budget_tokens = max(1, int(budget_tokens) - int(reserved_neighbor_tokens))

    included_seeds: list[str] = []
    render_levels = {"detailed": 0, "compact": 0, "minimal": 0}
    for path in seed_paths:
        entry = files.get(path, {})
        section, level = _select_file_section(
            path=path,
            role="seed",
            entry=entry,
            used_tokens=used_tokens,
            budget_tokens=seed_budget_tokens,
            allow_overflow=not bool(included_seeds),
            tokenizer_model=tokenizer_model,
            estimate_tokens_fn=estimate_tokens_fn,
        )
        if not section:
            if included_seeds:
                break
            continue
        section_tokens = estimate_tokens_fn(section, model=tokenizer_model)
        lines.extend(section.splitlines())
        lines.append("")
        used_tokens += section_tokens
        included_seeds.append(path)
        render_levels[level] = int(render_levels.get(level, 0)) + 1

    graph_context_lines = _build_graph_context_section(
        subgraph_payload=subgraph_payload
    )
    if graph_context_lines:
        graph_context_text = "\n".join(graph_context_lines)
        graph_context_tokens = estimate_tokens_fn(
            graph_context_text,
            model=tokenizer_model,
        )
        if used_tokens + graph_context_tokens <= max(1, int(budget_tokens)):
            lines.extend(graph_context_lines)
            lines.append("")
            used_tokens += graph_context_tokens

    if max(1, int(neighbor_depth)) <= 1:
        neighbor_header = "## One-Hop Neighbors"
    else:
        neighbor_header = f"## Import Neighbors (depth<={max(1, int(neighbor_depth))})"
    lines.extend([neighbor_header, ""])
    used_tokens += estimate_tokens_fn(neighbor_header, model=tokenizer_model)

    included_neighbors: list[str] = []
    for path in neighbor_paths:
        entry = files.get(path, {})
        section, level = _select_file_section(
            path=path,
            role="neighbor",
            entry=entry,
            used_tokens=used_tokens,
            budget_tokens=budget_tokens,
            allow_overflow=False,
            tokenizer_model=tokenizer_model,
            estimate_tokens_fn=estimate_tokens_fn,
        )
        if not section:
            break
        section_tokens = estimate_tokens_fn(section, model=tokenizer_model)
        lines.extend(section.splitlines())
        lines.append("")
        used_tokens += section_tokens
        included_neighbors.append(path)
        render_levels[level] = int(render_levels.get(level, 0)) + 1

    if not included_neighbors and neighbor_paths:
        lines.append("- (token budget reached before neighbor skeleton could be appended)")
        lines.append("")

    markdown = "\n".join(line for line in lines).strip() + "\n"
    return markdown, used_tokens, included_neighbors, render_levels


def _build_graph_context_section(
    *,
    subgraph_payload: dict[str, Any] | None,
) -> list[str]:
    payload = subgraph_payload if isinstance(subgraph_payload, dict) else {}
    if not payload:
        return []

    edge_counts_raw = payload.get("edge_counts")
    edge_counts = (
        {
            str(key).strip(): max(0, int(value or 0))
            for key, value in edge_counts_raw.items()
            if str(key).strip()
        }
        if isinstance(edge_counts_raw, dict)
        else {}
    )
    seed_paths_raw = payload.get("seed_paths")
    seed_paths = (
        [str(item).strip() for item in seed_paths_raw if str(item).strip()]
        if isinstance(seed_paths_raw, list)
        else []
    )
    enabled = bool(payload.get("enabled", False))
    reason = str(payload.get("reason") or "").strip()
    if not enabled and not seed_paths and not edge_counts:
        return []

    edge_total_count = sum(edge_counts.values())
    edge_type_count = len([key for key, value in edge_counts.items() if value > 0])
    lines = [
        "## Graph Context",
        "",
        f"- enabled: {enabled}",
        f"- reason: {reason or '(none)'}",
        f"- seed_paths: {', '.join(seed_paths) if seed_paths else '(none)'}",
        f"- edge_type_count: {edge_type_count}",
        f"- edge_total_count: {edge_total_count}",
    ]
    if edge_counts:
        lines.append(
            "- edge_counts: "
            + ", ".join(f"{key}={value}" for key, value in edge_counts.items())
        )
    else:
        lines.append("- edge_counts: (none)")
    return lines


def _estimate_neighbor_reserve_tokens(
    *,
    files: dict[str, dict[str, Any]],
    neighbor_paths: list[str],
    budget_tokens: int,
    neighbor_depth: int,
    tokenizer_model: str | None,
    estimate_tokens_fn: Any = estimate_tokens,
) -> int:
    if not neighbor_paths:
        return 0

    total_budget = max(1, int(budget_tokens))
    if max(1, int(neighbor_depth)) <= 1:
        neighbor_header = "## One-Hop Neighbors"
    else:
        neighbor_header = f"## Import Neighbors (depth<={max(1, int(neighbor_depth))})"

    header_tokens = estimate_tokens_fn(neighbor_header, model=tokenizer_model)
    reserve_cap = min(
        max(1, total_budget - 1),
        max(header_tokens, round(total_budget * 0.6)),
    )
    reserved = int(header_tokens)
    included_any = False

    for path in neighbor_paths:
        entry = files.get(path, {})
        minimal = str(
            _build_file_section_variants(path=path, role="neighbor", entry=entry).get(
                "minimal", ""
            )
        ).strip()
        if not minimal:
            continue
        tokens = estimate_tokens_fn(minimal, model=tokenizer_model)
        if reserved + tokens <= reserve_cap or not included_any:
            reserved += int(tokens)
            included_any = True
            continue
        break

    return max(0, reserved)


def _select_file_section(
    *,
    path: str,
    role: str,
    entry: dict[str, Any],
    used_tokens: int,
    budget_tokens: int,
    allow_overflow: bool,
    tokenizer_model: str | None,
    estimate_tokens_fn: Any = estimate_tokens,
) -> tuple[str | None, str]:
    variants = _build_file_section_variants(path=path, role=role, entry=entry)
    level_order: tuple[str, ...] = ("detailed", "compact", "minimal")
    if str(role).strip().lower() == "neighbor":
        level_order = ("minimal", "compact")

    for level in level_order:
        section = str(variants.get(level, "")).strip()
        if not section:
            continue
        section_tokens = estimate_tokens_fn(section, model=tokenizer_model)
        if used_tokens + section_tokens <= budget_tokens:
            return section, level
    if allow_overflow:
        section = str(variants.get("minimal", "")).strip()
        if section:
            return section, "minimal"
    return None, "minimal"


def _build_file_section_variants(
    *,
    path: str,
    role: str,
    entry: dict[str, Any],
) -> dict[str, Any]:
    language = str(entry.get("language", "")).strip() if isinstance(entry, dict) else ""
    module = str(entry.get("module", "")).strip() if isinstance(entry, dict) else ""
    imports = _collect_import_modules(entry=entry)
    tags = extract_code_tags(entry, max_tags=24)

    detailed_tag_labels = [
        _format_tag_label(tag=tag, with_signature=True)
        for tag in tags[:12]
        if isinstance(tag, dict)
    ]
    compact_tag_labels = [
        _format_tag_label(tag=tag, with_signature=False)
        for tag in tags[:8]
        if isinstance(tag, dict)
    ]

    detailed_lines = [f"### `{path}` [{role}] ({language or 'unknown'})"]
    detailed_lines.append(f"- module: `{module}`" if module else "- module: `(none)`")
    detailed_lines.append(
        f"- tags ({len(tags)}): {', '.join(detailed_tag_labels)}"
        if detailed_tag_labels
        else "- tags: (none)"
    )
    detailed_lines.append(
        f"- imports: {', '.join(imports[:12])}" if imports else "- imports: (none)"
    )

    compact_lines = [f"### `{path}` [{role}] ({language or 'unknown'})"]
    compact_lines.append(f"- module: `{module}`" if module else "- module: `(none)`")
    compact_lines.append(
        f"- tags: {', '.join(compact_tag_labels)}"
        if compact_tag_labels
        else "- tags: (none)"
    )

    minimal_line = (
        f"- `{path}` [{role}] tags={len(tags)} imports={len(imports)} language={language or 'unknown'}"
    )

    return {
        "detailed": "\n".join(detailed_lines),
        "compact": "\n".join(compact_lines),
        "minimal": minimal_line,
        "tag_count": len(tags),
        "tags": tags,
    }


def _format_tag_label(*, tag: dict[str, Any], with_signature: bool) -> str:
    name = str(tag.get("name") or "").strip()
    if not name:
        return ""
    start_line = int(tag.get("start_line", 1) or 1)
    end_line = int(tag.get("end_line", start_line) or start_line)
    line_suffix = (
        f"@L{start_line}" if start_line == end_line else f"@L{start_line}-{end_line}"
    )
    if with_signature:
        signature = str(tag.get("signature") or "").strip()
        return f"`{signature or name}`{line_suffix}"
    return f"`{name}`{line_suffix}"


def _collect_symbol_names(*, entry: dict[str, Any], kind: str) -> list[str]:
    if not isinstance(entry, dict):
        return []

    candidates = entry.get("classes", []) if kind == "class" else entry.get("functions", [])

    names: list[str] = []
    if isinstance(candidates, list):
        for item in candidates:
            if not isinstance(item, dict):
                continue
            name = str(item.get("qualified_name") or item.get("name") or "").strip()
            if name and name not in names:
                names.append(name)

    if names:
        return names

    symbols = entry.get("symbols", [])
    if not isinstance(symbols, list):
        return names

    for item in symbols:
        if not isinstance(item, dict):
            continue
        symbol_kind = str(item.get("kind", "")).strip().lower()
        if kind == "class" and symbol_kind not in {"class", "type"}:
            continue
        if kind == "function" and symbol_kind not in {"function", "method", "async_function"}:
            continue
        name = str(item.get("qualified_name") or item.get("name") or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def _collect_import_modules(*, entry: dict[str, Any]) -> list[str]:
    if not isinstance(entry, dict):
        return []

    imports = entry.get("imports", [])
    if not isinstance(imports, list):
        return []

    modules: list[str] = []
    for item in imports:
        if not isinstance(item, dict):
            continue
        module = str(item.get("module") or "").strip()
        name = str(item.get("name") or "").strip()
        label = module
        if module and name:
            label = f"{module}.{name}"
        elif not module and name:
            label = name
        if label and label not in modules:
            modules.append(label)
    return modules


def _file_descriptor(*, path: str, role: str, entry: dict[str, Any]) -> dict[str, Any]:
    tags = extract_code_tags(entry, max_tags=8)
    return {
        "path": path,
        "role": role,
        "language": str(entry.get("language", "")) if isinstance(entry, dict) else "",
        "module": str(entry.get("module", "")) if isinstance(entry, dict) else "",
        "tag_count": len(tags),
        "tags": tags,
    }


__all__ = [
    "_file_descriptor",
    "_render_skeleton_markdown",
]
