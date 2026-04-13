# Skill Catalog Discoverability Design

**Status**: Design Phase
**Created**: 2026-04-12
**Based on**: GitNexus + Rowboat borrowing studies

---

## Motivation

From the GitNexus + Rowboat borrowing reports:

- GitNexus provides a "short, hard agent-facing contract" for skill discovery
- Rowboat provides "build_skill_catalog()" for human-readable skill enumeration
- ACE-Lite already has `build_skill_catalog()` in `src/ace_lite/skills.py`

The original gap was that ACE-Lite had `build_skill_catalog()` but no public CLI surface to expose it. That gap is now closed through `ace-lite skills catalog`.

---

## Design Goals

1. Provide a **read-only** entry point for skill discoverability
2. Keep skills as manifest-driven (no hardcoded registry)
3. Keep catalog output consistent with `build_skill_catalog()` output
4. Do NOT route pipeline through catalog (Layer 2 artifact per `REPORT_LAYER_GOVERNANCE.md`)

---

## Current Implementation: CLI `ace-lite skills catalog`

### Behavior

```bash
ace-lite skills catalog --root . --skills-dir skills

# Current output format (from build_skill_catalog):
# # ACE-Lite Skill Catalog
# 
# ## ace-dev
# - Description: ...
# - Intents: ...
# - Token estimate: ...
# - Default sections: ...
```

### Implementation

The implemented command lives in `src/ace_lite/cli_app/commands/skills.py`:

```python
@click.group("skills", help="Skill management and discovery.")
def skills_group() -> None:
    pass


@skills_group.command("catalog", help="Show available skills as markdown catalog.")
@click.option("--root", default=".", help="Repository root path.")
@click.option("--skills-dir", default="skills", help="Skills directory override.")
def catalog_command(root: str, skills_dir: str) -> None:
    from ace_lite.skills import build_skill_manifest, build_skill_catalog
    
    skills_path = _resolve_skills_path(root=root, skills_dir=skills_dir)
    manifest = build_skill_manifest(skills_path)
    catalog = build_skill_catalog(manifest)
    click.echo(catalog)
```

### Pros
- Self-documenting command structure
- Easier discovery
- Room for future `skills validate`, `skills lint` subcommands

### Cons
- More implementation than Option A
- Requires new file

---

## Future Option: MCP Tool `skills_catalog`

### Implementation

Add to `server_tool_registration.py`:

```python
def register_skills_tools(registry: ToolRegistry) -> None:
    registry.register_tool(
        name="skills_catalog",
        description="Show available skills as a markdown catalog (read-only).",
        input_schema={
            "type": "object",
            "properties": {},
            "required": [],
        },
        handler=_handle_skills_catalog,
    )

def _handle_skills_catalog(request: dict) -> dict:
    from ace_lite.skills import build_skill_manifest, build_skill_catalog
    
    manifest = build_skills_dir_from_request(request)
    catalog = build_skill_catalog(manifest)
    return {"content": catalog, "format": "markdown"}
```

### Usage

```
mcp__skills__catalog()
```

### Pros
- Integrates with MCP-first workflows
- Agent-accessible

### Cons
- More implementation effort
- MCP-only (CLI users can't access)

---

## Testing

```bash
# Unit test
pytest -q tests/unit/test_skills.py -k catalog

# Integration test
ace-lite skills catalog --root . --skills-dir skills
```

---

## Integration with Report Layer Governance

Per `docs/maintainers/REPORT_LAYER_GOVERNANCE.md`:

- Skill catalog is **Layer 2: Read-Only Audit Surface**
- Catalog MUST NOT be used for routing or gating
- Only allowed as discovery aid and human-readable output

---

## Rollback

```bash
git restore -- src/ace_lite/cli_app/commands/skills.py
```

---

## Future Enhancements

1. `ace-lite skills validate` - Validate skill manifests
2. `ace-lite skills lint` - Lint frontmatter metadata
3. MCP `skills_catalog` tool for agent-facing discovery
4. `--catalog-format json` for machine-readable output

---

## References

- `src/ace_lite/skills.py` - `build_skill_catalog()` implementation
- `src/ace_lite/cli_app/commands/skills.py` - CLI catalog surface
- `docs/maintainers/REPORT_LAYER_GOVERNANCE.md` - Layer 2 artifact rules
- `.context/TEMPLATE_RESEARCH_REPORT.md` - Template used for borrowing reports
