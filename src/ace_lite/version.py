"""Version helpers for ACE-Lite.

Keep version sourcing consistent across CLI/MCP/runtime. The primary source of
truth is the installed distribution metadata. When unavailable (for example,
running from a source checkout), we fall back to reading `pyproject.toml` so the
CLI/MCP reflect the working tree without requiring a reinstall.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as dist_version
from pathlib import Path

_DIST_NAME = "ace-lite-engine"


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


def get_version_info(*, dist_name: str = _DIST_NAME) -> dict[str, object]:
    """Return version details including editable-install drift detection.

    ACE-Lite prefers to *report* the working tree version (pyproject.toml) so
    users see the version they just pulled. However, editable installs can drift
    when pip metadata isn't refreshed (entry points / dependencies may be stale).
    This helper surfaces both values so callers can warn proactively.
    """
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
        repair_steps = ["python -m pip install -e .[dev]"]
    elif drifted:
        reason_code = "install_drift"
        repair_steps = ["python -m pip install -e .[dev]"]
    else:
        reason_code = "ok"
        repair_steps = []
    return {
        "version": effective,
        "source": source,
        "pyproject_version": pyproject_version,
        "installed_version": installed_version,
        "dist_name": dist_name,
        "drifted": drifted,
        "reason_code": reason_code,
        "repair_steps": repair_steps,
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


__all__ = ["get_version", "get_version_info", "verify_version_install_sync"]
