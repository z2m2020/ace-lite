# Memory Connectivity

## Overview

ACE-Lite memory stage uses a V2 provider contract with progressive disclosure:

- `search_compact(query)` returns compact preview rows (`handle`, `preview`, `metadata`, `est_tokens`)
- `fetch(handles)` returns full text only when needed

Default runtime composition:

1. primary/secondary remote providers (`OpenMemoryMemoryProvider` over MCP/REST)
2. optional strategy layer (`semantic` or `hybrid` via RRF)
3. optional local write-through cache (`LocalCacheProvider`, JSONL + TTL + max_entries)

## Fallback and merge behavior

- `semantic` strategy: primary channel, optional fallback to secondary
- `hybrid` strategy: run semantic + keyword channels and merge by RRF
- stable memory handles: prefer upstream ID, else deterministic `sha256` fingerprint

## Observability fields

Memory stage payload includes:

- `memory.channel_used`
- `memory.fallback_reason`
- `memory.strategy`
- `memory.hits_preview` / `memory.hits` (full mode)
- `memory.timeline` (grouped by `updated_at` / `created_at` when available)
- `memory.cache.{enabled,hit_count,miss_count,evicted_count}`
- `memory.hybrid.{semantic_candidates,keyword_candidates,merged_candidates,rrf_k}`
- `memory.cost.{preview_est_tokens_total,full_est_tokens_total,fetch_est_tokens_total,saved_est_tokens_total}`

## Configuration

CLI options:

- `--memory-primary` (`mcp|rest|none`)
- `--memory-secondary` (`rest|mcp|none`)
- `--memory-strategy` (`semantic|hybrid`)
- `--memory-hybrid-limit`
- `--memory-cache/--no-memory-cache`
- `--memory-cache-path`
- `--memory-cache-ttl-seconds`
- `--memory-cache-max-entries`
- `--memory-timeline/--no-memory-timeline`
- `--mcp-base-url`
- `--rest-base-url`
- `--memory-timeout`
- `--user-id`
- `--app`
- `--memory-limit`
- `--memory-disclosure` (`compact|full`)
- `--memory-preview-max-chars`

Layered config keys (global + `plan.*` / `benchmark.*` namespace overrides):

- `memory.disclosure_mode`
- `memory.preview_max_chars`
- `memory.strategy`
- `memory.cache.enabled`
- `memory.cache.path`
- `memory.cache.ttl_seconds`
- `memory.cache.max_entries`
- `memory.timeline.enabled`
- `memory.hybrid.limit`

Environment variables:

- `ACE_LITE_MCP_BASE_URL`
- `ACE_LITE_REST_BASE_URL`
- `ACE_LITE_USER_ID`
- `ACE_LITE_APP`

## Notes

`MemoryProvider` is now V2-first (`search_compact + fetch`).
Legacy providers that only expose `search()` are rejected at runtime.
