from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request

from ace_lite.http_utils import safe_urlopen


class OpenMemoryMcpClient:
    def __init__(
        self,
        *,
        base_url: str = "http://localhost:8765",
        endpoints: list[str] | tuple[str, ...] | None = None,
        timeout_seconds: float = 3.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self.last_container_tag_fallback: str | None = None
        self._endpoints = tuple(
            endpoints
            or (
                "/mcp/tools/search_memory",
                "/mcp",
            )
        )

    def search(
        self,
        *,
        query: str,
        user_id: str | None = None,
        app: str | None = None,
        container_tag: str | None = None,
        limit: int = 5,
    ) -> Any:
        self.last_container_tag_fallback = None
        base_args: dict[str, Any] = {
            "query": query,
            "limit": limit,
        }
        if user_id:
            base_args["user_id"] = user_id
        if app:
            base_args["app"] = app

        errors: list[str] = []
        for endpoint in self._endpoints:
            url = f"{self._base_url}{endpoint}"
            tag_variants: list[tuple[str, dict[str, Any]]] = [("none", {})]
            if container_tag:
                tag_variants = [
                    ("containerTag", {"containerTag": container_tag}),
                    ("container_tag", {"container_tag": container_tag}),
                    ("none", {}),
                ]

            tagged_attempt_failed = False
            for tag_label, extras in tag_variants:
                args = {**base_args, **extras}
                payload = self._payload_for_endpoint(endpoint=endpoint, args=args)
                try:
                    response = self._post_json(url, payload)
                    if (
                        container_tag
                        and tag_label == "none"
                        and tagged_attempt_failed
                    ):
                        self.last_container_tag_fallback = (
                            "backend_unsupported_container_tag"
                        )
                    return self._normalize_mcp_response(response)
                except (HTTPError, URLError, OSError, TimeoutError, ValueError) as exc:
                    if container_tag and tag_label != "none":
                        tagged_attempt_failed = True
                    errors.append(f"{endpoint} ({tag_label}): {exc}")

        raise RuntimeError(
            "OpenMemory MCP search failed across all endpoints: " + "; ".join(errors)
        )

    def _post_json(self, url: str, payload: dict[str, Any]) -> Any:
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            url=url,
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with safe_urlopen(request, timeout=self._timeout_seconds) as response:
            raw = response.read().decode("utf-8", errors="replace")

        if not raw.strip():
            return {}
        return json.loads(raw)

    @staticmethod
    def _payload_for_endpoint(endpoint: str, args: dict[str, Any]) -> dict[str, Any]:
        if endpoint.endswith("search_memory"):
            return args

        return {
            "jsonrpc": "2.0",
            "id": "ace-lite",
            "method": "tools/call",
            "params": {
                "name": "search_memory",
                "arguments": args,
            },
        }

    @staticmethod
    def _normalize_mcp_response(payload: Any) -> Any:
        if not isinstance(payload, dict):
            return payload

        if "results" in payload:
            return payload

        result = payload.get("result")
        if isinstance(result, dict):
            if "results" in result:
                return result

            content = result.get("content")
            if isinstance(content, list):
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    text = item.get("text")
                    if not isinstance(text, str):
                        continue
                    try:
                        decoded = json.loads(text)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(decoded, dict) and "results" in decoded:
                        return decoded

        return payload


__all__ = ["OpenMemoryMcpClient"]
