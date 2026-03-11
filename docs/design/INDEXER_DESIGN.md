# Indexer Design (P3)

## Goals

`ace_lite.indexer` provides deterministic multi-language repository indexing using Tree-sitter.

Supported profile:
- `python`
- `typescript` (`.ts`, `.tsx`)
- `javascript` (`.js`, `.jsx`)
- `go`

## Public APIs

### `build_index(root_dir, include_globs=None, exclude_dirs=None, languages=None)`

Builds a full index from `root_dir`.

Main fields:
- `root_dir`
- `file_count`
- `files`
- `languages_covered`
- `indexed_at`
- `parser.engine`
- `parser.version`
- `configured_languages`

Per file entry retains backward-compatible fields plus Tree-sitter fields:
- `language`
- `module`
- `symbols[]`
- `imports[]`
- `classes[]`
- `functions[]`
- `sha256`
- `parse_error` (optional)

### `update_index(existing_index, root_dir, changed_files, languages=None)`

Incremental update semantics:
- re-index changed source files
- remove deleted files
- remove files outside configured language profile
- refresh metadata (`file_count`, `languages_covered`, `indexed_at`)

## Cache integration (`index_cache.py`)

`build_or_refresh_index(...)` provides orchestrator-friendly behavior:

- cache miss -> full build (`mode=full_build`)
- cache hit + no incremental or no changed files -> reuse cache (`mode=cache_only`)
- cache hit + changed files -> apply incremental update (`mode=incremental_update`)

Cache payload compatibility checks:
- root directory must match
- configured language profile must match

## RepoMap relationship

Indexer outputs machine-structured `context-map/index.json`.

RepoMap (`ace_lite.repomap`) consumes this index and emits:
- `context-map/repo_map.json`
- `context-map/repo_map.md`

with deterministic token budget controls.
