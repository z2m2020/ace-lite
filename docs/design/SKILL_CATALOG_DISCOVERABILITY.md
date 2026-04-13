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

The gap: **there is no CLI or MCP entry point to expose the catalog**.

---

## Design Goals

1. Provide a **read-only** entry point for skill discoverability
2. Keep skills as manifest-driven (no hardcoded registry)
3. Keep catalog output consistent with `build_skill_catalog()` output
4. Do NOT route pipeline through catalog (Layer 2 artifact per `REPORT_LAYER_GOVERNANCE.md`)

---

## Option A: CLI `--catalog` Flag (Recommended)

### Implementation

Add a `--catalog` flag to the `ace-lite plan` command:

```python
# In cli_app/commands/plan.py or cli_enhancements.py

@click.option(
    "--catalog",
    is_flag=True,
    help="Output skill catalog and exit (read-only, does not run pipeline)",
)
```

### Behavior

```bash
# Show skill catalog
ace-lite plan --catalog --repo ace-lite --root .

# Current output format (from build_skill_catalog):
# # ACE-Lite Skill Catalog
# 
# ## ace-dev
# - Description: ...
# - Intents: ...
# - Token estimate: ...
# - Default sections: ...
```

### Pros
- Minimal implementation (just flag + output)
- Single responsibility
- Fits existing CLI patterns

### Cons
- Requires knowing to use `--catalog` flag

---

## Option B: CLI `ace-lite skills` Subcommand

### Implementation

Create a new command group:

```python
# In src/ace_lite/cli_app/commands/skills.py (new file)

@click.group("skills", help="Skill management and discovery.")
def skills_group() -> None:
    pass


@skills_group.command("catalog", help="Show available skills as markdown catalog.")
@click.option("--repo", default=".", help="Repository identifier.")
@click.option("--root", default=".", help="Repository root path.")
@click.option("--skills-dir", default=None, help="Skills directory override.")
def catalog_command(repo: str, root: str, skills_dir: str | None) -> None:
    from ace_lite.skills import build_skill_manifest, build_skill_catalog
    from ace_lite.cli_app.params import resolve_cli_path
    
    skills_path = resolve_cli_path(skills_dir or "skills")
    manifest = build_skill_manifest(skills_path)
    catalog = build_skill_catalog(manifest)
    click.echo(catalog)
```

### Usage

```bash
ace-lite skills catalog --repo ace-lite --root .
```

### Pros
- Self-documenting command structure
- Easier discovery
- Room for future `skills validate`, `skills lint` subcommands

### Cons
- More implementation than Option A
- Requires new file

---

## Option C: MCP Tool `skills_catalog`

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

## Recommended Approach

**Option A (CLI `--catalog` flag)** as the immediate implementation, with **Option C (MCP tool)** as a future enhancement.

### Rationale

1. `build_skill_catalog()` already exists - minimal delta
2. CLI is the primary interface for local development
3. MCP can be added later without breaking CLI
4. Keeps catalog as a Layer 2 read-only artifact (not a routing mechanism)

---

## Implementation Sketch (Option A)

### File: `src/ace_lite/cli_app/cli_enhancements.py`

```python
# Add to existing plan command or create minimal wrapper

def add_catalog_flag(parser: Any) -> None:
    parser.add_argument(
        "--catalog",
        action="store_true",
        help="Show skill catalog and exit (read-only)",
    )

# In plan command handler:
if catalog:
    from ace_lite.skills import build_skill_manifest, build_skill_catalog
    from ace_lite.cli_app.params import resolve_cli_path
    
    skills_dir = resolve_cli_path(skills_dir_override or "skills")
    manifest = build_skill_manifest(skills_dir)
    catalog_md = build_skill_catalog(manifest)
    click.echo(catalog_md)
    return
```

---

## Testing

```bash
# Unit test
pytest -q tests/unit/test_skills.py -k catalog

# Integration test
ace-lite plan --catalog --repo ace-lite --root . | head -20
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
git restore -- src/ace_lite/cli_app/cli_enhancements.py
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
- `docs/maintainers/REPORT_LAYER_GOVERNANCE.md` - Layer 2 artifact rules
- `.context/TEMPLATE_RESEARCH_REPORT.md` - Template used for borrowing reports
