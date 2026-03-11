from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request

import click

from ace_lite.http_utils import safe_urlopen


def run_mcp_self_test(
    *,
    root: str,
    skills_dir: str,
    python_executable: str,
    timeout_seconds: float,
    env_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    timeout = max(1.0, float(timeout_seconds))
    command = [
        str(python_executable),
        "-m",
        "ace_lite.mcp_server",
        "--self-test",
        "--root",
        str(root),
    ]
    if str(skills_dir).strip():
        command.extend(["--skills-dir", str(skills_dir).strip()])

    try:
        env = dict(os.environ)
        if isinstance(env_overrides, dict):
            for key, value in env_overrides.items():
                normalized_key = str(key or "").strip()
                if not normalized_key:
                    continue
                env[normalized_key] = str(value)
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise click.ClickException(
            f"MCP self-test timed out after {timeout:.1f}s"
        ) from exc
    except OSError as exc:
        raise click.ClickException(f"Failed to start MCP self-test: {exc}") from exc

    stdout = str(completed.stdout or "").strip()
    stderr = str(completed.stderr or "").strip()
    if completed.returncode != 0:
        message = (
            f"MCP self-test failed with exit code {completed.returncode}"
            + (f": {stderr}" if stderr else "")
        )
        raise click.ClickException(message)
    if not stdout:
        raise click.ClickException("MCP self-test returned empty stdout")

    lines = [line for line in stdout.splitlines() if line.strip()]
    payload_raw = lines[-1] if lines else ""
    try:
        payload = json.loads(payload_raw)
    except json.JSONDecodeError as exc:
        raise click.ClickException(
            f"MCP self-test returned non-JSON payload: {payload_raw}"
        ) from exc
    if not isinstance(payload, dict) or not bool(payload.get("ok")):
        raise click.ClickException("MCP self-test returned unhealthy payload")
    return payload


def extract_memory_channels(payload: dict[str, Any]) -> tuple[str, str]:
    primary = str(payload.get("memory_primary") or "none").strip().lower() or "none"
    secondary = (
        str(payload.get("memory_secondary") or "none").strip().lower() or "none"
    )
    return primary, secondary


def memory_channels_disabled(*, primary: str, secondary: str) -> bool:
    return primary == "none" and secondary == "none"


def probe_post_json(
    *,
    url: str,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        url=url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with safe_urlopen(
            request,
            timeout=max(0.2, float(timeout_seconds)),
        ) as response:
            status = int(getattr(response, "status", 200) or 200)
            raw = response.read().decode("utf-8", errors="replace")
        return {
            "ok": 200 <= status < 300,
            "status": status,
            "url": url,
            "body_preview": raw[:200],
        }
    except (HTTPError, URLError, OSError, TimeoutError, ValueError) as exc:
        return {
            "ok": False,
            "url": url,
            "error": str(exc),
        }


def probe_mcp_memory_endpoint(*, base_url: str, timeout_seconds: float) -> dict[str, Any]:
    base = str(base_url or "").strip().rstrip("/")
    if not base:
        return {"ok": False, "error": "empty base URL"}

    primary_url = f"{base}/mcp/tools/search_memory"
    primary_payload = {"query": "health", "limit": 1}
    primary_result = probe_post_json(
        url=primary_url,
        payload=primary_payload,
        timeout_seconds=timeout_seconds,
    )
    if primary_result.get("ok"):
        return {
            "ok": True,
            "endpoint": primary_url,
            "route": "/mcp/tools/search_memory",
            "fallback_used": False,
        }

    fallback_url = f"{base}/mcp"
    fallback_payload = {
        "jsonrpc": "2.0",
        "id": "ace-lite-runtime-doctor",
        "method": "tools/call",
        "params": {
            "name": "search_memory",
            "arguments": {"query": "health", "limit": 1},
        },
    }
    fallback_result = probe_post_json(
        url=fallback_url,
        payload=fallback_payload,
        timeout_seconds=timeout_seconds,
    )
    if fallback_result.get("ok"):
        return {
            "ok": True,
            "endpoint": fallback_url,
            "route": "/mcp",
            "fallback_used": True,
            "primary_error": primary_result.get("error")
            or primary_result.get("status"),
        }
    return {
        "ok": False,
        "route": "/mcp/tools/search_memory -> /mcp",
        "primary_error": primary_result.get("error") or primary_result.get("status"),
        "fallback_error": fallback_result.get("error") or fallback_result.get("status"),
    }


def probe_rest_memory_endpoint(
    *,
    base_url: str,
    timeout_seconds: float,
    user_id: str,
    app: str,
) -> dict[str, Any]:
    base = str(base_url or "").strip().rstrip("/")
    if not base:
        return {"ok": False, "error": "empty base URL"}

    endpoints = (
        "/api/v1/memories/search",
        "/api/v1/memory/search",
        "/api/v1/search",
        "/api/v1/memories/filter",
    )
    for endpoint in endpoints:
        url = f"{base}{endpoint}"
        payload: dict[str, Any] = {"query": "health", "limit": 1}
        if endpoint.endswith("memories/filter"):
            payload = {
                "user_id": user_id,
                "search_query": "health",
                "size": 1,
                "page": 1,
            }
        else:
            payload["user_id"] = user_id
            payload["app"] = app
        probe = probe_post_json(
            url=url,
            payload=payload,
            timeout_seconds=timeout_seconds,
        )
        if probe.get("ok"):
            return {
                "ok": True,
                "endpoint": url,
                "route": endpoint,
            }
    return {
        "ok": False,
        "route": ",".join(endpoints),
        "error": "all REST endpoints failed",
    }


def memory_config_recommendations(*, root: str, skills_dir: str) -> list[str]:
    resolved_root = str(root or ".")
    resolved_skills = str(skills_dir or "skills")
    default_user_id = (
        str(os.getenv("ACE_LITE_USER_ID", "")).strip()
        or str(os.getenv("USERNAME", "")).strip()
        or str(os.getenv("USER", "")).strip()
        or "codex"
    )
    return [
        "codex mcp remove ace-lite",
        "codex mcp add ace-lite "
        + "--env ACE_LITE_DEFAULT_ROOT="
        + resolved_root
        + " --env ACE_LITE_DEFAULT_SKILLS_DIR="
        + resolved_skills
        + " --env ACE_LITE_MEMORY_PRIMARY=rest --env ACE_LITE_MEMORY_SECONDARY=none "
        + "--env ACE_LITE_MCP_BASE_URL=http://localhost:8765 "
        + "--env ACE_LITE_REST_BASE_URL=http://localhost:8765 "
        + "--env ACE_LITE_USER_ID="
        + default_user_id
        + " --env ACE_LITE_APP=ace-lite "
        + "-- python -m ace_lite.mcp_server --transport stdio",
    ]


def resolve_cli_path(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "."
    return str(Path(raw).expanduser().resolve())


def normalize_mcp_name(value: str) -> str:
    raw = str(value or "").strip() or "ace-lite"
    normalized = "".join(ch if (ch.isalnum() or ch in {"-", "_"}) else "_" for ch in raw)
    return normalized or "ace-lite"


def mcp_env_snapshot_path(*, root: str, mcp_name: str) -> Path:
    root_path = Path(root).resolve()
    safe_name = normalize_mcp_name(mcp_name)
    return (root_path / "context-map" / "mcp" / f"{safe_name}.env.json").resolve()


def env_items_to_mapping(env_items: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for item in env_items:
        raw = str(item or "").strip()
        if "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        normalized_key = key.strip()
        if not normalized_key:
            continue
        mapping[normalized_key] = value
    return mapping


def write_mcp_env_snapshot(*, root: str, mcp_name: str, env_items: list[str]) -> Path:
    path = mcp_env_snapshot_path(root=root, mcp_name=mcp_name)
    payload = {
        "name": str(mcp_name or "").strip() or "ace-lite",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "env": env_items_to_mapping(env_items),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_mcp_env_snapshot(*, root: str, mcp_name: str) -> tuple[dict[str, str], Path]:
    path = mcp_env_snapshot_path(root=root, mcp_name=mcp_name)
    if not path.exists() or not path.is_file():
        return {}, path
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, path
    if not isinstance(payload, dict):
        return {}, path
    env_payload = payload.get("env", {})
    if not isinstance(env_payload, dict):
        return {}, path
    mapping: dict[str, str] = {}
    for key, value in env_payload.items():
        normalized_key = str(key or "").strip()
        if not normalized_key:
            continue
        mapping[normalized_key] = str(value)
    return mapping, path


__all__ = [
    "env_items_to_mapping",
    "extract_memory_channels",
    "load_mcp_env_snapshot",
    "mcp_env_snapshot_path",
    "memory_channels_disabled",
    "memory_config_recommendations",
    "normalize_mcp_name",
    "probe_mcp_memory_endpoint",
    "probe_post_json",
    "probe_rest_memory_endpoint",
    "resolve_cli_path",
    "run_mcp_self_test",
    "write_mcp_env_snapshot",
]
