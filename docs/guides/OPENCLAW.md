# OpenClaw Plugin (ACE-Lite)

ACE-Lite ships an OpenClaw plugin wrapper under:

- `integrations/openclaw/ace-lite-openclaw-plugin/`

It spawns the ACE-Lite MCP server (stdio transport) and:

- exposes `ace_health`, `ace_index`, `ace_repomap_build`, `ace_plan_quick`, `ace_plan` as OpenClaw tools
- can auto-inject a small, untrusted context block via `before_agent_start` (candidate files + optional repomap)

## Requirements

- Python with ACE-Lite installed (recommended for local dev): `pip install -e .`
- Node.js + npm

## Install

From `integrations/openclaw/ace-lite-openclaw-plugin/`:

```bash
npm install
```

Then configure OpenClaw to load the plugin from that directory (OpenClaw UI/config-specific).

## Suggested config defaults

- `languages`: include `solidity` when working with contract repos (ACE-Lite will keep `node_modules/*.sol` available).
- `autoMode`: `plan_quick_plus_repomap` for general use; switch to `plan_quick` if you want minimal injection.
