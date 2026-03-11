# Compatibility Matrix (ACE-Lite)

## Runtime

- Python: `>= 3.10`

## Optional dependencies

- Local embeddings (CPU): install extras `local-ai` (uses `sentence-transformers`)

## Embeddings compatibility

When embeddings are enabled, keep these consistent across runs:

- `embedding_provider`
- `embedding_model`
- `embedding_dimension`
- `embedding_index_path` (stored vectors must match the chosen dimension)

## Supported languages (tree-sitter index)

Default language profile:
- Python
- TypeScript / TSX
- JavaScript
- Go
- Rust
- Java
- C / C++
- C#
- Ruby
- PHP
- Solidity

Opt-in (extension-based detection only unless enabled in `--languages`):
- Kotlin (`.kt`, `.kts`)
- Swift (`.swift`)
- Bash (`.sh`, `.bash`)
- Lua (`.lua`)

## External tools (optional)

- `git`: enables incremental index refresh and `ace-lite demo --clone-url ...`
- `rg` (ripgrep): optional exact-search boost when `--exact-search` is enabled
