# Borrowing Governance Checklist

**Status**: Phase 3 - Initial
**Created**: 2026-04-12
**Based on**: GitNexus + Rowboat borrowing studies

---

## Purpose

This document codifies the governance rules for cross-project borrowing and adaptation, ensuring that borrowed patterns are integrated thoughtfully and do not compromise ACE-Lite's core principles.

---

## Core Principles

1. **Declarative Discovery**: Skills are discovered via manifest, not hardcoded registries
2. **Read-Only Reports**: Report artifacts are never promoted to execution gates
3. **Small, Direct Tests**: Prefer contract tests over large integration tests
4. **Fail-Early Validation**: Validate inputs at boundaries, not deep in pipelines
5. **No Automatic Global Changes**: Never automatically modify user environment configs

---

## Borrowing Decision Matrix

### Category A: Engineering Habits (Preferred)

| Pattern | Examples | Status |
|---|---|---|
| Short, hard contracts | Agent-facing markdown with precise commands | ✅ Adopt |
| Explicit normalization | Centralized config parsing with defaults | ✅ Adopt |
| Small, direct tests | Contract tests for boundaries | ✅ Adopt |
| Template stable output | Consistent report structure | ✅ Adopt |

### Category B: Structural Patterns (Careful)

| Pattern | Examples | Status |
|---|---|---|
| Shared orchestration core | Extract runner from CLI/shell | ⚠️ Design required |
| Layer separation | Split read-only from execution | ⚠️ Case-by-case |
| Service seams | Modular boundaries | ⚠️ Case-by-case |

### Category C: Product Patterns (Rejected)

| Pattern | Examples | Status |
|---|---|---|
| Auto global config writes | Write to `~/.cursor`, `~/.claude` | ❌ Reject |
| Auto hooks injection | Default hook registration | ❌ Reject |
| Auto skill generation | Generate skills from clustering | ❌ Reject |
| Hardcoded registries | `aliasMap`, `resolveSkill()` | ❌ Reject |
| Product takeover flow | Auto-update user AGENTS.md | ❌ Reject |

---

## Before Starting a Borrowing Study

- [ ] Pin source repository to specific commit SHA
- [ ] Identify local mirror for evidence gathering
- [ ] Define comparison surface clearly
- [ ] List explicitly what NOT to borrow

---

## During a Borrowing Study

### Evidence Checklist

- [ ] Read README to understand product intent
- [ ] Read architecture docs if available
- [ ] Examine key implementation files
- [ ] Identify patterns worth borrowing
- [ ] Identify patterns to explicitly reject
- [ ] Assess fit with current architecture

### Output Requirements

Every borrowing report must include:

1. **Source revision**: Pin to specific commit SHA
2. **Comparison surface**: What aspects are being compared
3. **Evidence links**: Point to specific files
4. **Classification**:
   - ACCEPTED: Implemented or analysis-only conclusion
   - REJECTED: Explicitly not borrowed with reason
   - DEFERRED: Worth revisiting later with conditions
5. **Adaptation shape**: How the pattern would be adapted (not how it would be copied)
6. **Non-goals**: What the adaptation does NOT include
7. **Validation**: How to verify the borrowing works
8. **Rollback**: How to undo the borrowing

---

## After a Borrowing Study

### For ACCEPTED Patterns

- [ ] Create or update implementation
- [ ] Add unit/contract tests
- [ ] Update relevant documentation
- [ ] Verify tests pass
- [ ] Update this governance document if new patterns added

### For REJECTED Patterns

- [ ] Document why rejected
- [ ] Add to this governance document's rejection list
- [ ] Ensure tests prevent accidental re-introduction

### For DEFERRED Patterns

- [ ] Document conditions for revisiting
- [ ] Add to future enhancement candidates in relevant design doc
- [ ] Schedule review in project tracking

---

## Report Location Convention

| Report Type | Location |
|---|---|
| Borrowing studies | `.context/{PROJECT}_BORROWING_REPORT_{DATE}.md` |
| Architecture analysis | `.context/ARCHITECTURE_ANALYSIS_AND_OPTIMIZATION.md` |
| Design proposals | `docs/design/{TOPIC}_DESIGN.md` |
| Integration notes | `docs/maintainers/{TOPIC}_STATUS.md` |

---

## Integration with Existing Contracts

### ContextReport

From `docs/maintainers/CONTEXT_REPORT_CONTRACT.md`:
- Do NOT use as execution gate
- Do NOT use for ranking
- Schema version must be stable

### Skill Catalog

From `docs/maintainers/REPORT_LAYER_GOVERNANCE.md`:
- Read-only projection of manifest
- No hardcoded registry
- Discovery via `build_skill_manifest()` + `select_skills()`

### Orchestrator

From `docs/design/ORCHESTRATOR_SEAM_DESIGN.md`:
- No structural changes without contract regression tests
- Pipeline order must remain stable

---

## Validation Commands

```bash
# Skill lint
pytest -q tests/unit/test_skills.py

# ContextReport contract
pytest -q tests/unit/test_context_report.py

# Runtime setup normalization
pytest -q tests/unit/test_runtime_setup_support.py

# Orchestrator regression
pytest -q tests/unit/test_orchestrator.py
```

---

## Change Process

1. File a proposal in `docs/maintainers/` or `docs/design/`
2. Get maintainer review for structural changes
3. Add tests before implementation
4. Update governance documents when patterns change
5. No PR merges without passing validation commands

---

## Rollback

```bash
git restore -- docs/maintainers docs/design .context
```

---

## Related Documents

- `.context/TEMPLATE_RESEARCH_REPORT.md` - Report template
- `docs/maintainers/REPORT_LAYER_GOVERNANCE.md` - Layer classification
- `docs/maintainers/CONTEXT_REPORT_CONTRACT.md` - ContextReport schema
- `docs/design/SKILL_CATALOG_DISCOVERABILITY.md` - Skill catalog design
- `docs/design/ORCHESTRATOR_SEAM_DESIGN.md` - Orchestrator refactor design
