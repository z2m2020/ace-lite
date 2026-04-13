# Runtime Setup Normalization Status

**Status**: Phase 1 - Complete
**Created**: 2026-04-12
**Updated**: 2026-04-13
**Based on**: GitNexus + Rowboat borrowing studies

---

## Current Implementation

Runtime setup normalization is implemented in `src/ace_lite/cli_app/runtime_setup_support.py`.

### Normalization Entry Points

| Function | Purpose |
|---|---|
| `_format_setup_error()` | Normalize runtime setup failure messages by operation |
| `_require_non_empty_setup_value()` | Fail early when normalized setup inputs are empty |
| `_resolve_codex_mcp_setup_identity()` | Normalize name, root, skills_dir, config_pack, and user_id |
| `_build_codex_mcp_env_items()` | Build normalized environment variable entries |
| `_build_codex_mcp_self_test_env()` | Build normalized self-test environment |
| `build_codex_mcp_setup_plan()` | Orchestrate normalization and return a setup plan |
| `execute_codex_mcp_setup_plan()` | Execute the normalized plan through subprocess calls |

### Normalization Patterns Applied

#### 1. String Normalization

```python
normalized_name = str(name or "").strip() or "ace-lite"
normalized_root = resolve_cli_path_fn(root)
normalized_skills = resolve_cli_path_fn(skills_dir)
```

#### 2. Conditional Path Resolution

```python
normalized_config_pack = str(config_pack or "").strip()
if normalized_config_pack:
    normalized_config_pack = resolve_cli_path_fn(normalized_config_pack)
```

#### 3. Fallback Chains

```python
resolved_user_id = (
    str(user_id or "").strip()
    or str(env_get_fn("ACE_LITE_USER_ID", "")).strip()
    or str(env_get_fn("USERNAME", "")).strip()
    or str(env_get_fn("USER", "")).strip()
    or "codex"
)
```

#### 4. Numeric Bounds Clamping

```python
f"ACE_LITE_EMBEDDING_DIMENSION={max(8, int(embedding_dimension))}"
f"ACE_LITE_EMBEDDING_RERANK_POOL={max(1, int(embedding_rerank_pool))}"
f"ACE_LITE_EMBEDDING_LEXICAL_WEIGHT={max(0.0, float(embedding_lexical_weight))}"
```

#### 5. Boolean Normalization

```python
"ok": True,
"apply": bool(apply),
"replace": bool(replace),
"verify": bool(verify),
```

#### 6. Fail-Early Required Input Validation

```python
normalized_codex_executable = _require_non_empty_setup_value(
    field_name="codex_executable",
    value=str(codex_executable),
    operation="normalize_inputs",
)
```

#### 7. Structured Setup Error Formatting

```python
raise click.ClickException(
    _format_setup_error("add_mcp_server", "codex add failed")
)
```

---

## Test Coverage

| Test File | Coverage |
|---|---|
| `tests/unit/test_runtime_setup_support.py` | Facade re-exports and basic structure |
| `tests/unit/test_runtime_command_support.py` | Full plan building, validation, and error surfacing |
| `tests/integration/test_cli_runtime.py` | CLI setup integration, dry run, apply, and verify paths |

Primary verification:

- `pytest -q tests/unit/test_runtime_setup_support.py`
- `pytest -q tests/unit/test_runtime_command_support.py`
- `pytest -q tests/integration/test_cli_runtime.py -k setup`

Known unrelated failure in the broader runtime doctor suite:

- `pytest -q tests/integration/test_cli_runtime.py`
- Current environment still reports `install_drift` in `runtime doctor`, so doctor assertions expecting `exit_code == 0` fail independently of setup normalization.

---

## Relationship to Borrowing Studies

| Source | Borrowing | Status |
|---|---|---|
| GitNexus | Explicit config parser plus defaults | Adopted in `_resolve_codex_mcp_setup_identity()` |
| GitNexus | Fail-early validation and formatted failures | Adopted via `_require_non_empty_setup_value()` and `_format_setup_error()` |
| Rowboat | Guardrail-style normalization discipline | Extended to env construction and self-test setup |

---

## Identified Normalization Points

From GitNexus config-parser inspiration:

1. Done: `normalized_name` is always stripped and defaults to `ace-lite`
2. Done: `normalized_root` is always resolved via `resolve_cli_path_fn`
3. Done: `normalized_skills` is always resolved via `resolve_cli_path_fn`
4. Done: `normalized_config_pack` is conditionally resolved
5. Done: `resolved_user_id` follows the environment fallback chain
6. Done: `embedding_dimension` is clamped to `max(8, ...)`
7. Done: `embedding_rerank_pool` is clamped to `max(1, ...)`
8. Done: `codex_executable`, `python_executable`, `root`, and `skills_dir` fail early when normalization produces empty values
9. Done: subprocess failures now use operation-scoped error messages

---

## Future Enhancement Candidates

### E1: Centralized Validation Helper

Extract setup validation into a shared helper if more runtime domains need the same contract:

```python
def validate_setup_input(**kwargs) -> list[str]:
    warnings = []
    if not kwargs.get("root"):
        warnings.append("root is required for MCP setup")
    return warnings
```

### E2: Integration with Config Resolution

Consider merging runtime setup normalization with `cli_app/config_resolve.py` patterns so other CLI entrypoints reuse the same validation contract.

---

## Verification

```bash
pytest -q tests/unit/test_runtime_setup_support.py
pytest -q tests/unit/test_runtime_command_support.py
pytest -q tests/integration/test_cli_runtime.py -k setup
```

---

## Rollback

```bash
git restore -- src/ace_lite/cli_app/runtime_setup_support.py tests/unit/test_runtime_command_support.py tests/integration/test_cli_runtime.py docs/design/RUNTIME_SETUP_NORMALIZATION_STATUS.md
```

---

## References

- `src/ace_lite/cli_app/runtime_setup_support.py`
- `tests/unit/test_runtime_setup_support.py`
- `tests/unit/test_runtime_command_support.py`
- `tests/integration/test_cli_runtime.py`
