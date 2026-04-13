# Skill Metadata Guard Enhancement Summary

**Status**: Phase 1 - Largely Complete
**Created**: 2026-04-12
**Based on**: GitNexus + Rowboat borrowing studies

---

## Current Implementation

The skill metadata guard is already implemented in `src/ace_lite/skills.py`:

### 1. Blocklisted Error Keywords

**Location**: `_ERROR_KEYWORD_BLOCKLIST` (L19-33)

```python
_ERROR_KEYWORD_BLOCKLIST = {
    "benchmark", "cleanup", "context", "freeze", "handoff",
    "implement", "plan", "planning", "refactor", "release",
    "rename", "review", "scope",
}
```

**Purpose**: Prevent workflow labels from leaking into `error_keywords` field.

### 2. Suspicious Codepoint Detection

**Location**: `_SUSPICIOUS_METADATA_CODEPOINTS` (L35-51)

Detects mojibake-like Unicode characters in metadata fields.

### 3. Missing Frontmatter Tracking

**Location**: `_missing_frontmatter` in `build_skill_manifest()` (L70-74)

Records which required fields are missing **before** backfill.

### 4. Lint Function

**Location**: `lint_skill_manifest()` (L218-222) + `_lint_skill_entry()` (L410+)

Checks:
- [x] Workflow keywords in error_keywords field
- [x] Missing `token_estimate` and `default_sections`
- [x] Suspicious mojibake Unicode in any metadata field
- [x] Overlap between error_keywords and intents/modules/topics

---

## Existing Test Coverage

| Test | Coverage |
|---|---|
| `test_lint_skill_manifest_flags_workflow_error_keywords` | Blocklist enforcement |
| `test_lint_skill_manifest_flags_missing_frontmatter_before_backfill` | Missing field detection |
| `test_lint_skill_manifest_flags_mojibake_metadata_terms` | Unicode suspicious detection |
| `test_repo_skills_pass_frontmatter_lint` | Repository skills validation |

**Run**: `pytest -q tests/unit/test_skills.py -k lint`

---

## Potential Enhancements (Future)

### E1: Illegal Default Sections Detection

Detect if `default_sections` references non-existent headings.

### E2: Token Estimate Bounds Check

Warn if `token_estimate` is suspiciously low or high for a given skill.

### E3: Intent/Module Overlap Warning

Warn if a skill has intents/modules that overlap too much (low discriminative power).

---

## Verification

```bash
# Run all skill tests
pytest -q tests/unit/test_skills.py

# Run lint-specific tests
pytest -q tests/unit/test_skills.py -k lint
```

---

## Relationship to Borrowing Studies

| Source | Borrowing | Status |
|---|---|---|
| GitNexus | Explicit config parser + defaults | Adopted in normalization layer |
| Rowboat | Frontmatter/schema guard | Adopted in `lint_skill_manifest()` |

---

## Rollback

```bash
git restore -- src/ace_lite/skills.py tests/unit/test_skills.py
```

---

## References

- `src/ace_lite/skills.py` - Full implementation
- `tests/unit/test_skills.py` - Test coverage
- `docs/maintainers/REPORT_LAYER_GOVERNANCE.md` - Layer classification
