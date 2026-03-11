from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request

from ace_lite.http_utils import safe_urlopen


class OpenMemoryRestClient:
    def __init__(
        self,
        *,
        base_url: str = "http://localhost:8765",
        endpoints: list[str] | tuple[str, ...] | None = None,
        timeout_seconds: float = 2.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self.last_container_tag_fallback: str | None = None
        self._endpoints = tuple(
            endpoints
            or (
                "GET /api/v1/memories/",
                "POST /api/v1/memories/filter",
                "/api/v1/memories/search",
                "/api/v1/memory/search",
                "/api/v1/search",
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
        errors: list[str] = []
        self.last_container_tag_fallback = None

        for endpoint in self._endpoints:
            method, path = self._parse_endpoint(endpoint)
            url = f"{self._base_url}{path}"
            tags_to_try = [container_tag, None] if container_tag else [None]
            tagged_attempt_failed = False
            for tag in tags_to_try:
                try:
                    if method == "GET":
                        params = self._query_params_for_endpoint(
                            path=path,
                            query=query,
                            user_id=user_id,
                            app=app,
                            container_tag=tag,
                            limit=limit,
                        )
                        response = self._get_json(url, params)
                    else:
                        payload = self._payload_for_endpoint(
                            path=path,
                            query=query,
                            user_id=user_id,
                            app=app,
                            container_tag=tag,
                            limit=limit,
                        )
                        response = self._post_json(url, payload)
                    if container_tag and tag is None and tagged_attempt_failed:
                        self.last_container_tag_fallback = (
                            "backend_unsupported_container_tag"
                        )
                    return self._normalize_response(response, query=query, limit=limit)
                except (HTTPError, URLError, OSError, TimeoutError, ValueError) as exc:
                    suffix = " (containerTag)" if tag else ""
                    if container_tag and tag is not None:
                        tagged_attempt_failed = True
                    errors.append(f"{method} {path}{suffix}: {exc}")

        if app:
            try:
                response = self._search_by_app(app=app, query=query, limit=limit)
                return self._normalize_response(response, query=query, limit=limit)
            except (HTTPError, URLError, OSError, TimeoutError, ValueError) as exc:
                errors.append(f"app_fallback:{exc}")

        raise RuntimeError(
            "OpenMemory REST search failed across all endpoints: " + "; ".join(errors)
        )

    def _search_by_app(self, *, app: str, query: str, limit: int) -> dict[str, Any]:
        app_name = str(app or "").strip()
        if not app_name:
            raise ValueError("app is required for app fallback search")

        apps_url = f"{self._base_url}/api/v1/apps/"
        apps_payload = self._get_json(apps_url, {"page": 1, "page_size": 100})
        if not isinstance(apps_payload, dict):
            raise ValueError("invalid apps payload")

        app_rows = apps_payload.get("apps", [])
        if not isinstance(app_rows, list):
            app_rows = []

        app_id = ""
        for item in app_rows:
            if not isinstance(item, dict):
                continue
            if str(item.get("name", "")).strip().lower() != app_name.lower():
                continue
            candidate = str(item.get("id", "")).strip()
            if not candidate:
                continue
            app_id = candidate
            if bool(item.get("is_active", True)):
                break

        if not app_id:
            raise ValueError(f"app not found: {app_name}")

        page_size = max(10, min(100, int(limit) * 10))
        memories_url = f"{self._base_url}/api/v1/apps/{app_id}/memories"
        memories_payload = self._get_json(memories_url, {"page": 1, "page_size": page_size})
        if not isinstance(memories_payload, dict):
            raise ValueError("invalid app memories payload")

        memories = memories_payload.get("memories", [])
        if not isinstance(memories, list):
            memories = []

        query_tokens = self._tokenize_query(query)

        scored: list[tuple[float, dict[str, Any]]] = []
        for item in memories:
            if not isinstance(item, dict):
                continue
            text = str(item.get("content") or "").strip()
            if not text:
                continue

            if not query_tokens:
                score = 1.0
            else:
                text_lower = text.lower()
                hit_count = sum(1 for token in query_tokens if token in text_lower)
                if hit_count <= 0:
                    continue
                score = hit_count / len(query_tokens)

            row = dict(item)
            row["score"] = round(float(score), 6)
            scored.append((score, row))

        scored.sort(key=lambda entry: entry[0], reverse=True)
        rows = [row for _, row in scored[: max(1, int(limit))]]

        return {
            "items": rows,
            "total": len(rows),
            "page": 1,
            "size": max(1, int(limit)),
            "pages": 1,
        }

    def _get_json(self, url: str, params: dict[str, Any]) -> Any:
        query_params = {key: value for key, value in params.items() if value is not None and str(key).strip()}
        full_url = f"{url}?{urlencode(query_params, doseq=True)}" if query_params else url
        request = Request(
            url=full_url,
            headers={"Accept": "application/json"},
            method="GET",
        )

        with safe_urlopen(request, timeout=self._timeout_seconds) as response:
            raw = response.read().decode("utf-8", errors="replace")

        if not raw.strip():
            return {}
        return json.loads(raw)

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
    def _parse_endpoint(endpoint: str) -> tuple[str, str]:
        value = str(endpoint or "").strip()
        if not value:
            raise ValueError("empty endpoint")

        parts = value.split(" ", 1)
        if len(parts) == 2 and parts[0].upper() in {"GET", "POST"}:
            return parts[0].upper(), parts[1].strip()
        return "POST", value

    @staticmethod
    def _query_params_for_endpoint(
        *,
        path: str,
        query: str,
        user_id: str | None,
        app: str | None,
        container_tag: str | None,
        limit: int,
    ) -> dict[str, Any]:
        if path.rstrip("/").endswith("/api/v1/memories"):
            if not user_id:
                raise ValueError("user_id required for GET /api/v1/memories/")
            params: dict[str, Any] = {
                "user_id": user_id,
                "search_query": query,
                "size": max(1, int(limit)),
                "page": 1,
            }
            if app:
                params["app_name"] = app
            if container_tag:
                params["containerTag"] = container_tag
            return params

        params = {
            "query": query,
            "user_id": user_id,
            "app": app,
            "limit": max(1, int(limit)),
        }
        if container_tag:
            params["containerTag"] = container_tag
        return params

    @staticmethod
    def _payload_for_endpoint(
        *,
        path: str,
        query: str,
        user_id: str | None,
        app: str | None,
        container_tag: str | None,
        limit: int,
    ) -> dict[str, Any]:
        if path.rstrip("/").endswith("/api/v1/memories/filter"):
            if not user_id:
                raise ValueError("user_id required for POST /api/v1/memories/filter")
            payload: dict[str, Any] = {
                "user_id": user_id,
                "search_query": query,
                "size": max(1, int(limit)),
                "page": 1,
            }
            if container_tag:
                payload["containerTag"] = container_tag
            return payload

        payload = {
            "query": query,
            "limit": max(1, int(limit)),
        }
        if user_id:
            payload["user_id"] = user_id
        if app:
            payload["app"] = app
        if container_tag:
            payload["containerTag"] = container_tag
        return payload

    @classmethod
    def _normalize_response(cls, payload: Any, *, query: str, limit: int) -> Any:
        if isinstance(payload, dict) and "result" in payload and isinstance(payload["result"], dict):
            result = payload["result"]
            if "results" in result:
                return result

        if isinstance(payload, dict) and "results" in payload:
            return payload

        if isinstance(payload, dict) and isinstance(payload.get("items"), list):
            rows = cls._normalize_rows(payload.get("items", []))
            return {
                "results": rows[: max(1, int(limit))],
                "total": payload.get("total", len(rows)),
            }

        if isinstance(payload, dict) and isinstance(payload.get("memories"), list):
            rows = cls._normalize_rows(payload.get("memories", []))
            filtered = cls._filter_rows(rows=rows, query=query, limit=limit)
            return {
                "results": filtered,
                "total": payload.get("total", len(filtered)),
            }

        return payload

    @staticmethod
    def _normalize_rows(rows: Any) -> list[dict[str, Any]]:
        if not isinstance(rows, list):
            return []

        normalized: list[dict[str, Any]] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            text = str(item.get("memory") or item.get("text") or item.get("content") or "").strip()
            if not text:
                continue

            metadata_raw = item.get("metadata")
            if not isinstance(metadata_raw, dict):
                metadata_raw = item.get("metadata_")
            metadata = dict(metadata_raw) if isinstance(metadata_raw, dict) else {}

            for key in ("id", "created_at", "state", "app_id", "app_name", "categories"):
                if key in item and item[key] is not None and key not in metadata:
                    metadata[key] = item[key]

            row: dict[str, Any] = {
                "memory": text,
                "metadata": metadata,
            }
            score = item.get("score")
            if isinstance(score, (int, float)):
                row["score"] = float(score)

            normalized.append(row)

        return normalized

    @classmethod
    def _filter_rows(cls, *, rows: list[dict[str, Any]], query: str, limit: int) -> list[dict[str, Any]]:
        tokens = cls._tokenize_query(query)
        if not tokens:
            return rows[: max(1, int(limit))]

        scored: list[tuple[float, dict[str, Any]]] = []
        for row in rows:
            text = str(row.get("memory") or "").lower()
            if not text:
                continue
            hit_count = sum(1 for token in tokens if token in text)
            if hit_count <= 0:
                continue
            score = hit_count / len(tokens)
            candidate = dict(row)
            if not isinstance(candidate.get("score"), (int, float)):
                candidate["score"] = round(float(score), 6)
            scored.append((score, candidate))

        scored.sort(key=lambda entry: entry[0], reverse=True)
        return [row for _, row in scored[: max(1, int(limit))]]

    @staticmethod
    def _tokenize_query(query: str) -> list[str]:
        parts = [item.strip().lower() for item in str(query or "").replace("/", " ").replace(".", " ").split()]
        return [item for item in parts if len(item) >= 2]


__all__ = ["OpenMemoryRestClient"]
