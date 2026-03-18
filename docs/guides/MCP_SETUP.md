# MCP Setup (ACE-Lite)

ACE-Lite runs as an MCP server over **stdio**. Most MCP clients need:

- A command to start the server (`python -m ace_lite.mcp_server ...` or `ace-lite-mcp ...`)
- A working directory (`--root` and `--skills-dir`)
- Optional environment variables (memory + embeddings providers)

## Verify locally first

```bash
ace-lite doctor
ace-lite runtime doctor-mcp --root . --probe-endpoints
```

Use `--no-probe-endpoints` if you only want local checks.

## Generic MCP registration template

If your client supports JSON-based MCP server registration, the shape typically looks like:

```json
{
  "mcpServers": {
    "ace-lite": {
      "command": "python",
      "args": ["-m", "ace_lite.mcp_server", "--transport", "stdio", "--root", ".", "--skills-dir", "skills"]
    }
  }
}
```

Notes:
- Prefer absolute paths when the client does not run from your repo root.
- If you installed ACE-Lite as a package, you can use `ace-lite-mcp` as the command instead of `python -m ...`.

## Codex CLI quick registration

If you use Codex CLI, verify the MCP commands first:

```bash
codex mcp --help
codex mcp add --help
```

Minimal local registration:

```bash
codex mcp add ace-lite \
  --env ACE_LITE_DEFAULT_ROOT=. \
  --env ACE_LITE_DEFAULT_SKILLS_DIR=skills \
  -- python -m ace_lite.mcp_server --transport stdio
```

Memory-enabled registration:

```bash
codex mcp add ace-lite \
  --env ACE_LITE_DEFAULT_ROOT=. \
  --env ACE_LITE_DEFAULT_SKILLS_DIR=skills \
  --env ACE_LITE_MEMORY_PRIMARY=rest \
  --env ACE_LITE_MEMORY_SECONDARY=none \
  --env ACE_LITE_MCP_BASE_URL=http://localhost:8765 \
  --env ACE_LITE_REST_BASE_URL=http://localhost:8765 \
  --env ACE_LITE_USER_ID=<your-openmemory-user-id> \
  --env ACE_LITE_APP=ace-lite \
  -- python -m ace_lite.mcp_server --transport stdio
```

You can also let ACE-Lite generate the Codex MCP config:

```bash
ace-lite runtime setup-codex-mcp --root . --skills-dir skills --enable-memory --user-id <your-openmemory-user-id> --dry-run
ace-lite runtime setup-codex-mcp --root . --skills-dir skills --enable-memory --user-id <your-openmemory-user-id> --apply
```

For a higher-performance local setup, point the MCP env at a config pack and enable embeddings in the generated registration:

```bash
ace-lite runtime setup-codex-mcp \
  --root . \
  --skills-dir skills \
  --enable-memory \
  --memory-primary rest \
  --memory-secondary none \
  --enable-embeddings \
  --embedding-provider ollama \
  --embedding-model dengcao/Qwen3-Embedding-4B:Q4_K_M \
  --embedding-dimension 2560 \
  --config-pack C:\Users\bdxx2\.codex\ace-lite-mcp-performance.json \
  --user-id <your-openmemory-user-id> \
  --dry-run
```

Recommended: store the config pack under your global Codex home so the same MCP defaults can be reused across repos, for example `C:\Users\<you>\.codex\ace-lite-mcp-performance.json`.

## Practical example (Windows + OpenMemory REST + Ollama embeddings)

This is a Windows example using:

- OpenMemory / Memory Bridge via REST (`ACE_LITE_MEMORY_PRIMARY=rest`, `ACE_LITE_REST_BASE_URL=http://localhost:8765`)
- Ollama embeddings (`ACE_LITE_EMBEDDING_PROVIDER=ollama`)

```toml
# TOML-style MCP client config example.
# Your MCP client may use a different schema (JSON/YAML/CLI flags).
args = ["-m", "ace_lite.mcp_server", "--transport", "stdio"]

[mcp_servers.ace-lite.env]
ACE_LITE_APP = "ace-lite"
ACE_LITE_DEFAULT_ROOT = 'C:\path\to\ace-lite-engine'
ACE_LITE_DEFAULT_SKILLS_DIR = 'C:\path\to\ace-lite-engine\skills'
ACE_LITE_MCP_BASE_URL = "http://localhost:8765"
ACE_LITE_EMBEDDING_ENABLED = "1"
ACE_LITE_EMBEDDING_PROVIDER = "ollama"
ACE_LITE_EMBEDDING_MODEL = "dengcao/Qwen3-Embedding-4B:Q4_K_M"
ACE_LITE_EMBEDDING_DIMENSION = "2560"
ACE_LITE_OLLAMA_BASE_URL = "http://localhost:11434"
ACE_LITE_MEMORY_PRIMARY = "rest"
ACE_LITE_MEMORY_SECONDARY = "none"
ACE_LITE_REST_BASE_URL = "http://localhost:8765"
ACE_LITE_USER_ID = "your-user-id"
```

Notes:
- `ACE_LITE_EMBEDDING_DIMENSION` must match your embedding model dimension.
- `ACE_LITE_MCP_BASE_URL` / `ACE_LITE_REST_BASE_URL` refer to the OpenMemory service endpoints (not the ACE-Lite MCP server).
- Some config formats require escaping backslashes (`\\`) for Windows paths.

## Feedback store guidance for MCP hosts

Selection feedback is stored in the local durable feedback store, not in the MCP transport layer. Keep these rules explicit:

- Use one feedback store path per repo or workspace if you want reproducible offline replay.
- Share the same feedback store across plan-time usage and benchmark replay only when that coupling is intentional.
- Prefer a canonical SQLite path such as `~/.ace-lite/preference_capture.db`; legacy `profile.json` paths remain compatible but are no longer the primary storage format.
- If your MCP client returns absolute file paths, call `ace_feedback_record` with the same `root` that the ACE-Lite server uses so paths are stored repo-relative.

Typical lifecycle:

1. The host calls `ace_feedback_record` after the user confirms the correct file.
2. The durable feedback store accumulates deterministic feedback events.
3. You export the feedback events with `ace-lite feedback export`.
4. You replay that snapshot into a clean feedback store with `ace-lite feedback replay --reset` for offline evaluation.

## WSL + Claude Code (reuse Windows-hosted services)

Recommended: run the MCP server inside WSL over stdio so Claude gets Linux-style paths (`/mnt/f/...`).

Assuming the repo is at `C:\path\to\ace-lite-engine` (WSL: `/mnt/c/path/to/ace-lite-engine`), and Windows Docker exposes:
- Ollama: `http://localhost:11434`
- OpenMemory: `http://localhost:8765`

Quick checks from WSL:

```bash
curl -sS http://localhost:11434/api/tags > /dev/null && echo "Ollama OK"
curl -sS http://localhost:8765/openapi.json > /dev/null && echo "OpenMemory OK"
```

Then register (project-scoped) in Claude Code:

```bash
cd /mnt/c/path/to/ace-lite-engine

claude mcp add -s project \
  -e ACE_LITE_APP=ace-lite \
  -e ACE_LITE_MEMORY_PRIMARY=rest \
  -e ACE_LITE_MEMORY_SECONDARY=none \
  -e ACE_LITE_REST_BASE_URL=http://localhost:8765 \
  -e ACE_LITE_MCP_BASE_URL=http://localhost:8765 \
  -e ACE_LITE_USER_ID=$(whoami) \
  -e ACE_LITE_EMBEDDING_ENABLED=1 \
  -e ACE_LITE_EMBEDDING_PROVIDER=ollama \
  -e ACE_LITE_OLLAMA_BASE_URL=http://localhost:11434 \
  ace-lite -- \
  /mnt/c/path/to/ace-lite-engine/.venv/bin/python -m ace_lite.mcp_server \
  --transport stdio \
  --root /mnt/c/path/to/ace-lite-engine \
  --skills-dir /mnt/c/path/to/ace-lite-engine/skills
```

If `localhost` is not reachable from WSL, try `host.docker.internal` or the Windows host IP.
