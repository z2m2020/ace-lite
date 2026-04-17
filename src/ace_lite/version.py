"""Version helpers for ACE-Lite.

Keep version sourcing consistent across CLI/MCP/runtime. The primary source of
truth is the installed distribution metadata. When unavailable (for example,
running from a source checkout), we fall back to reading `pyproject.toml` so the
CLI/MCP reflect the working tree without requiring a reinstall.
"""

from __future__ import annotations

import json
import time
from importlib.metadata import PackageNotFoundError, distribution
from importlib.metadata import version as dist_version
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname, urlopen

_DIST_NAME = "ace-lite-engine"
_PYPI_RELEASE_CACHE_TTL_SECONDS = 300.0
_PYPI_RELEASE_CACHE: dict[str, tuple[float, dict[str, object]]] = {}


def _find_pyproject_path() -> Path | None:
    current = Path(__file__).resolve().parent
    for _ in range(8):
        candidate = current / "pyproject.toml"
        if candidate.exists() and candidate.is_file():
            return candidate
        if current.parent == current:
            break
        current = current.parent
    return None


def _read_pyproject_version() -> str | None:
    path = _find_pyproject_path()
    if path is None:
        return None

    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None

    in_project = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            in_project = stripped == "[project]"
            continue
        if not in_project:
            continue

        key, sep, value = stripped.partition("=")
        if not sep:
            continue
        if key.strip() != "version":
            continue

        raw = value.strip()
        if raw.startswith('"'):
            end = raw.find('"', 1)
            if end > 1:
                normalized = raw[1:end].strip()
                return normalized or None
        if raw.startswith("'"):
            end = raw.find("'", 1)
            if end > 1:
                normalized = raw[1:end].strip()
                return normalized or None

    return None


def _format_command(parts: list[str]) -> str:
    formatted: list[str] = []
    for part in parts:
        text = str(part).strip()
        if not text:
            continue
        if any(char.isspace() for char in text) or any(char in text for char in "\"'"):
            escaped = text.replace('"', '\\"')
            formatted.append(f'"{escaped}"')
            continue
        formatted.append(text)
    return " ".join(formatted)


def _resolve_python_command(python_executable: str | None = None) -> str:
    resolved = str(python_executable or "").strip()
    return resolved or "python"


def _read_distribution_direct_url(dist_name: str) -> dict[str, Any] | None:
    try:
        dist = distribution(dist_name)
    except PackageNotFoundError:
        return None
    except Exception:
        return None

    try:
        raw = dist.read_text("direct_url.json")
    except Exception:
        return None
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _file_url_to_path(url: str) -> Path | None:
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme != "file":
        return None
    if parsed.netloc and parsed.netloc not in {"", "localhost"}:
        candidate = f"//{parsed.netloc}{parsed.path}"
    else:
        candidate = parsed.path
    resolved = url2pathname(unquote(candidate))
    if not resolved:
        return None
    return Path(resolved).resolve()


def _detect_installation_mode(
    *, dist_name: str, installed_version: str | None, pyproject_path: Path | None
) -> tuple[str, str]:
    direct_url = _read_distribution_direct_url(dist_name)
    if isinstance(direct_url, dict):
        editable = bool((direct_url.get("dir_info") or {}).get("editable"))
        if editable:
            source_root = _file_url_to_path(str(direct_url.get("url") or ""))
            if source_root is None and pyproject_path is not None:
                source_root = pyproject_path.parent.resolve()
            return "editable", str(source_root) if source_root is not None else ""
    if pyproject_path is not None and not installed_version:
        return "source_checkout", str(pyproject_path.parent.resolve())
    if installed_version:
        return "installed_package", ""
    if pyproject_path is not None:
        return "source_checkout", str(pyproject_path.parent.resolve())
    return "unknown", ""


def _version_sort_key(version: str) -> tuple[tuple[int, object], ...]:
    normalized = str(version or "").strip()
    if not normalized:
        return tuple()

    segments: list[tuple[int, object]] = []
    token = ""
    mode = "digit" if normalized[:1].isdigit() else "text"
    for char in normalized:
        if char in ".-_+":
            if token:
                segments.append((0, int(token)) if mode == "digit" else (1, token.lower()))
                token = ""
            mode = "digit"
            continue
        char_mode = "digit" if char.isdigit() else "text"
        if token and char_mode != mode:
            segments.append((0, int(token)) if mode == "digit" else (1, token.lower()))
            token = ""
        token += char
        mode = char_mode
    if token:
        segments.append((0, int(token)) if mode == "digit" else (1, token.lower()))
    return tuple(segments)


def _is_newer_version(candidate: str, current: str) -> bool:
    candidate_key = _version_sort_key(candidate)
    current_key = _version_sort_key(current)
    if candidate_key and current_key:
        return candidate_key > current_key
    return str(candidate or "").strip() > str(current or "").strip()


def _fetch_latest_pypi_release(
    dist_name: str,
    *,
    timeout_seconds: float = 0.75,
) -> dict[str, object]:
    now = time.time()
    cached = _PYPI_RELEASE_CACHE.get(dist_name)
    if cached is not None and (now - cached[0]) <= _PYPI_RELEASE_CACHE_TTL_SECONDS:
        return dict(cached[1])

    payload: dict[str, object]
    url = f"https://pypi.org/pypi/{dist_name}/json"
    try:
        with urlopen(url, timeout=max(0.1, float(timeout_seconds))) as response:
            data = json.loads(response.read().decode("utf-8"))
        info = data.get("info") if isinstance(data, dict) else None
        latest_version = str((info or {}).get("version") or "").strip()
        payload = {
            "ok": bool(latest_version),
            "source": "pypi",
            "latest_version": latest_version or None,
            "error": "" if latest_version else "missing_version",
        }
    except URLError as exc:
        payload = {
            "ok": False,
            "source": "pypi",
            "latest_version": None,
            "error": str(exc.reason or exc),
        }
    except Exception as exc:
        payload = {
            "ok": False,
            "source": "pypi",
            "latest_version": None,
            "error": str(exc),
        }
    _PYPI_RELEASE_CACHE[dist_name] = (now, dict(payload))
    return dict(payload)


def build_repair_steps(
    *,
    dist_name: str = _DIST_NAME,
    install_mode: str | None = None,
    source_root: str | None = None,
    python_executable: str | None = None,
    reason_code: str | None = None,
) -> list[str]:
    normalized_install_mode = str(install_mode or "").strip().lower() or "unknown"
    normalized_reason = str(reason_code or "").strip().lower() or "ok"
    python_command = _resolve_python_command(python_executable)
    resolved_source_root = str(source_root or "").strip()
    repo_root = Path(resolved_source_root).resolve() if resolved_source_root else None
    steps: list[str] = []

    def add(parts: list[str]) -> None:
        command = _format_command(parts)
        if command and command not in steps:
            steps.append(command)

    if normalized_reason in {"install_drift", "missing_installed_metadata"}:
        script_path = repo_root / "scripts" / "update.py" if repo_root is not None else None
        if script_path is not None and script_path.exists():
            add([python_command, str(script_path), "--root", str(repo_root)])
        add([python_command, "-m", "pip", "install", "-e", ".[dev]"])
        return steps

    if normalized_install_mode in {"editable", "source_checkout"}:
        script_path = repo_root / "scripts" / "update.py" if repo_root is not None else None
        if script_path is not None and script_path.exists():
            add([python_command, str(script_path), "--root", str(repo_root)])
        add([python_command, "-m", "pip", "install", "-e", ".[dev]"])
        return steps

    add([python_command, "-m", "pip", "install", "-U", dist_name])
    return steps


def get_update_status(
    *,
    dist_name: str = _DIST_NAME,
    version_info: dict[str, object] | None = None,
    include_latest_release: bool = True,
    timeout_seconds: float = 0.75,
    pypi_lookup_fn: Any = _fetch_latest_pypi_release,
) -> dict[str, object]:
    info = dict(version_info or get_version_info(dist_name=dist_name))
    pyproject_path = _find_pyproject_path()
    installed_version = str(info.get("installed_version") or "").strip() or None
    install_mode, source_root = _detect_installation_mode(
        dist_name=dist_name,
        installed_version=installed_version,
        pyproject_path=pyproject_path,
    )
    effective_version = str(info.get("version") or "").strip()
    install_sync_required = str(info.get("reason_code") or "").strip() in {
        "install_drift",
        "missing_installed_metadata",
    }

    repair_steps = build_repair_steps(
        dist_name=dist_name,
        install_mode=install_mode,
        source_root=source_root,
        reason_code=str(info.get("reason_code") or "").strip() or "ok",
    )
    recommended_command = repair_steps[0] if repair_steps else ""
    alternative_commands: list[str] = []
    for step in repair_steps[1:]:
        if step and step not in alternative_commands:
            alternative_commands.append(step)
    if install_mode == "installed_package":
        for command in (f"pipx upgrade {dist_name}", f"uv tool upgrade {dist_name}"):
            if command not in alternative_commands:
                alternative_commands.append(command)

    latest_version: str | None = None
    release_check_ok = False
    release_check_error = ""
    release_update_available = False
    if include_latest_release:
        release_payload = pypi_lookup_fn(
            dist_name,
            timeout_seconds=max(0.1, float(timeout_seconds)),
        )
        if not isinstance(release_payload, dict):
            release_payload = {
                "ok": False,
                "source": "pypi",
                "latest_version": None,
                "error": "invalid_release_payload",
            }
        release_check_ok = bool(release_payload.get("ok"))
        latest_value = str(release_payload.get("latest_version") or "").strip()
        latest_version = latest_value or None
        release_check_error = str(release_payload.get("error") or "").strip()
        if latest_version and effective_version and effective_version != "unknown":
            release_update_available = _is_newer_version(latest_version, effective_version)

    return {
        "dist_name": dist_name,
        "install_mode": install_mode,
        "source_root": source_root,
        "self_update_supported": True,
        "install_sync_required": install_sync_required,
        "latest_release_checked": include_latest_release,
        "latest_release_source": "pypi" if include_latest_release else "",
        "latest_published_version": latest_version,
        "release_check_ok": release_check_ok,
        "release_check_error": release_check_error,
        "release_update_available": release_update_available,
        "update_available": bool(install_sync_required or release_update_available),
        "recommended_update_command": recommended_command,
        "alternative_update_commands": alternative_commands,
    }


def get_version_info(*, dist_name: str = _DIST_NAME) -> dict[str, object]:
    """Return version details including editable-install drift detection.

    ACE-Lite prefers to *report* the working tree version (pyproject.toml) so
    users see the version they just pulled. However, editable installs can drift
    when pip metadata isn't refreshed (entry points / dependencies may be stale).
    This helper surfaces both values so callers can warn proactively.
    """
    pyproject_path = _find_pyproject_path()
    pyproject_version = _read_pyproject_version()
    installed_version: str | None
    try:
        installed_version = str(dist_version(dist_name))
    except PackageNotFoundError:
        installed_version = None
    except Exception:
        installed_version = None

    effective = pyproject_version or installed_version or "unknown"
    drifted = bool(
        pyproject_version
        and installed_version
        and str(pyproject_version).strip() != str(installed_version).strip()
    )
    source = (
        "pyproject"
        if pyproject_version
        else ("installed_metadata" if installed_version else "unknown")
    )
    if not installed_version:
        reason_code = "missing_installed_metadata"
    elif drifted:
        reason_code = "install_drift"
    else:
        reason_code = "ok"
    install_mode, source_root = _detect_installation_mode(
        dist_name=dist_name,
        installed_version=installed_version,
        pyproject_path=pyproject_path,
    )
    repair_steps = build_repair_steps(
        dist_name=dist_name,
        install_mode=install_mode,
        source_root=source_root,
        reason_code=reason_code,
    )
    return {
        "version": effective,
        "source": source,
        "pyproject_version": pyproject_version,
        "source_tree_version": pyproject_version,
        "installed_version": installed_version,
        "installed_metadata_version": installed_version,
        "dist_name": dist_name,
        "drifted": drifted,
        "reason_code": reason_code,
        "sync_state": "clean" if reason_code == "ok" else reason_code,
        "repair_steps": repair_steps,
        "install_mode": install_mode,
        "source_root": source_root,
    }


def get_version(*, dist_name: str = _DIST_NAME) -> str:
    info = get_version_info(dist_name=dist_name)
    version = str(info.get("version") or "").strip()
    return version or "unknown"


def verify_version_install_sync(*, dist_name: str = _DIST_NAME) -> dict[str, object]:
    """Require installed metadata to match the working-tree version."""

    info = get_version_info(dist_name=dist_name)
    installed_version = str(info.get("installed_version") or "").strip()
    pyproject_version = str(info.get("pyproject_version") or "").strip()

    if not installed_version:
        raise RuntimeError(
            f"Installed metadata is missing for {dist_name}; run: python -m pip install -e .[dev]"
        )
    if pyproject_version and installed_version != pyproject_version:
        raise RuntimeError(
            "Installed metadata drift detected for "
            f"{dist_name}: pyproject.toml={pyproject_version}, installed={installed_version}. "
            "Run: python -m pip install -e .[dev]"
        )
    return info


__all__ = [
    "build_repair_steps",
    "get_update_status",
    "get_version",
    "get_version_info",
    "verify_version_install_sync",
]
