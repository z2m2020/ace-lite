# Skill Lazy Load Design

## Goal

Provide low-token, high-signal loading of Markdown skills.

1. Build a lightweight manifest from skill frontmatter.
2. Select top skills with query-context scoring.
3. Load only required heading sections.

## Public APIs

### `build_skill_manifest(skills_dir)`
Scans `*.md` files and extracts:
- `name`, `description`, `path`
- `intents`, `modules`, `error_keywords`, `topics`
- `default_sections`, `priority`, `token_estimate`
- heading list from markdown body

If `token_estimate` is missing, the manifest builder derives a fallback estimate from
the default sections (or the first two headings).

### `select_skills(query_ctx, manifest, top_n=3)`
Scores each manifest row by:
- intent match
- module match
- error keyword match
- query token overlap with module fields
- query token overlap with topic fields
- skill name and description token overlap

Admission rules:
- `priority` is only a tie-break after real query matches exist.
- A skill must have at least one non-intent signal before it is admitted.
- Topic scoring only uses the `topics` field; `intents` and `modules` are scored separately to avoid double-counting.
- Skill-specific `error_keywords` are matched against the raw query text directly; runtime does not rely on one global manifest keyword union.
- `token_estimate` is used as a late tie-break so lighter skills win when score, match richness, and priority are otherwise equal.

Returns ranked top-N skills with score and match reasons.

### `route_skills(query, module_hint, skill_manifest, top_n=3)`
Builds the cheap routing payload only:
- `query_ctx`
- ranked manifest matches
- `routing_mode = metadata_only`
- `route_latency_ms`
- `selected_manifest_token_estimate_total`
- no markdown hydration

This is the compatibility seam for `route early, hydrate later` experiments without changing the public pipeline order.
The orchestrator can now precompute this payload before the `skills` stage and
reuse it later for hydration.

### `load_sections(skill_path, headings)`
Loads markdown sections by heading title.
If headings are omitted, returns all sections.
If no heading exists, returns full document body as one section.

### `run_skills(ctx, skill_manifest, top_n=3, token_budget=...)`
Hydrates the matched skills and reports:
- `routing_source`
- `routing_mode`
- `metadata_only_routing`
- `route_latency_ms`
- `hydration_latency_ms`
- `selected[*].estimated_tokens`
- `selected_token_estimate_total`
- `selected_manifest_token_estimate_total`
- `hydrated_skill_count`
- `hydrated_sections_count`
- `token_budget`
- `token_budget_used`
- `budget_exhausted`
- `skipped_for_budget`

This keeps skill loading observable and now enforces a hard hydration budget without changing the public stage contract shape.

## Why this works

This implements hierarchical context injection:
- metadata first (cheap)
- section text second (targeted)
- source code last (expensive)

This ordering is the core of low-cost ACE-Lite behavior.

## Experiment Policy

- The default runtime remains one `skills` stage in the public pipeline.
- The current runtime now precomputes metadata-only skills routing before the
  `skills` stage and delays markdown hydration until the final selected items.
- Any future promotion of earlier routing must be benchmark-gated through the existing feature-slice / benchmark evidence lane before it becomes a default behavior change.
