# ACE-Lite Engine — OpenClaw Plugin

This folder contains a minimal OpenClaw plugin that wraps ACE-Lite’s MCP server (stdio transport) and:

- exposes `ace_*` tools to OpenClaw
- optionally injects `ace_plan_quick` candidate files (and a small repo map) via `before_agent_start`

## Prerequisites

- Python environment with ACE-Lite installed (for example: `pip install -e .` from the ACE-Lite repo)
- Node.js + npm

## Install (dev)

From `integrations/openclaw/ace-lite-openclaw-plugin/`:

```bash
npm install
```

Then add this plugin folder to OpenClaw’s plugin config (OpenClaw-specific).

## Notes

- This plugin intentionally treats injected context as **untrusted** and wraps it in a warning block.
- For Solidity repos, ACE-Lite keeps `node_modules/` dependency contracts available (but limits collection to `.sol`).

