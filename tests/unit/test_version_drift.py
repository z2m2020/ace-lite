from __future__ import annotations

import pytest

from ace_lite import version as version_module


def test_get_version_info_no_drift(monkeypatch) -> None:
    monkeypatch.setattr(version_module, "_read_pyproject_version", lambda: "1.2.3")
    monkeypatch.setattr(version_module, "dist_version", lambda _name: "1.2.3")
    info = version_module.get_version_info(dist_name="ace-lite-engine")
    assert info["version"] == "1.2.3"
    assert info["drifted"] is False
    assert info["source"] == "pyproject"


def test_get_version_info_detects_drift(monkeypatch) -> None:
    monkeypatch.setattr(version_module, "_read_pyproject_version", lambda: "1.2.3")
    monkeypatch.setattr(version_module, "dist_version", lambda _name: "0.9.9")
    info = version_module.get_version_info(dist_name="ace-lite-engine")
    assert info["version"] == "1.2.3"
    assert info["installed_version"] == "0.9.9"
    assert info["drifted"] is True


def test_get_version_info_metadata_missing(monkeypatch) -> None:
    monkeypatch.setattr(version_module, "_read_pyproject_version", lambda: "1.2.3")

    def raise_not_found(_name: str) -> str:
        raise version_module.PackageNotFoundError

    monkeypatch.setattr(version_module, "dist_version", raise_not_found)
    info = version_module.get_version_info(dist_name="ace-lite-engine")
    assert info["version"] == "1.2.3"
    assert info["installed_version"] is None
    assert info["drifted"] is False


def test_verify_version_install_sync_returns_info_when_aligned(monkeypatch) -> None:
    monkeypatch.setattr(version_module, "_read_pyproject_version", lambda: "1.2.3")
    monkeypatch.setattr(version_module, "dist_version", lambda _name: "1.2.3")

    info = version_module.verify_version_install_sync(dist_name="ace-lite-engine")

    assert info["version"] == "1.2.3"
    assert info["drifted"] is False


def test_verify_version_install_sync_raises_on_drift(monkeypatch) -> None:
    monkeypatch.setattr(version_module, "_read_pyproject_version", lambda: "1.2.3")
    monkeypatch.setattr(version_module, "dist_version", lambda _name: "0.9.9")

    with pytest.raises(RuntimeError, match="Installed metadata drift detected"):
        version_module.verify_version_install_sync(dist_name="ace-lite-engine")


def test_verify_version_install_sync_raises_when_installed_metadata_missing(monkeypatch) -> None:
    monkeypatch.setattr(version_module, "_read_pyproject_version", lambda: "1.2.3")

    def raise_not_found(_name: str) -> str:
        raise version_module.PackageNotFoundError

    monkeypatch.setattr(version_module, "dist_version", raise_not_found)

    with pytest.raises(RuntimeError, match="Installed metadata is missing"):
        version_module.verify_version_install_sync(dist_name="ace-lite-engine")
