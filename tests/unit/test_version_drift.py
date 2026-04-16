from __future__ import annotations

import pytest

from ace_lite import version as version_module


def test_get_version_info_no_drift(monkeypatch) -> None:
    monkeypatch.setattr(version_module, "_read_pyproject_version", lambda: "1.2.3")
    monkeypatch.setattr(version_module, "_find_pyproject_path", lambda: None)
    monkeypatch.setattr(version_module, "dist_version", lambda _name: "1.2.3")
    info = version_module.get_version_info(dist_name="ace-lite-engine")
    assert info["version"] == "1.2.3"
    assert info["drifted"] is False
    assert info["source"] == "pyproject"
    assert info["reason_code"] == "ok"
    assert info["repair_steps"] == []


def test_get_version_info_detects_drift(monkeypatch) -> None:
    monkeypatch.setattr(version_module, "_read_pyproject_version", lambda: "1.2.3")
    monkeypatch.setattr(version_module, "_find_pyproject_path", lambda: None)
    monkeypatch.setattr(version_module, "dist_version", lambda _name: "0.9.9")
    info = version_module.get_version_info(dist_name="ace-lite-engine")
    assert info["version"] == "1.2.3"
    assert info["installed_version"] == "0.9.9"
    assert info["drifted"] is True
    assert info["reason_code"] == "install_drift"
    assert info["repair_steps"] == ["python -m pip install -e .[dev]"]


def test_get_version_info_metadata_missing(monkeypatch) -> None:
    monkeypatch.setattr(version_module, "_read_pyproject_version", lambda: "1.2.3")
    monkeypatch.setattr(version_module, "_find_pyproject_path", lambda: None)

    def raise_not_found(_name: str) -> str:
        raise version_module.PackageNotFoundError

    monkeypatch.setattr(version_module, "dist_version", raise_not_found)
    info = version_module.get_version_info(dist_name="ace-lite-engine")
    assert info["version"] == "1.2.3"
    assert info["installed_version"] is None
    assert info["drifted"] is False
    assert info["reason_code"] == "missing_installed_metadata"
    assert info["repair_steps"] == ["python -m pip install -e .[dev]"]


def test_verify_version_install_sync_returns_info_when_aligned(monkeypatch) -> None:
    monkeypatch.setattr(version_module, "_read_pyproject_version", lambda: "1.2.3")
    monkeypatch.setattr(version_module, "_find_pyproject_path", lambda: None)
    monkeypatch.setattr(version_module, "dist_version", lambda _name: "1.2.3")

    info = version_module.verify_version_install_sync(dist_name="ace-lite-engine")

    assert info["version"] == "1.2.3"
    assert info["drifted"] is False


def test_verify_version_install_sync_raises_on_drift(monkeypatch) -> None:
    monkeypatch.setattr(version_module, "_read_pyproject_version", lambda: "1.2.3")
    monkeypatch.setattr(version_module, "_find_pyproject_path", lambda: None)
    monkeypatch.setattr(version_module, "dist_version", lambda _name: "0.9.9")

    with pytest.raises(RuntimeError, match="Installed metadata drift detected"):
        version_module.verify_version_install_sync(dist_name="ace-lite-engine")


def test_verify_version_install_sync_raises_when_installed_metadata_missing(monkeypatch) -> None:
    monkeypatch.setattr(version_module, "_read_pyproject_version", lambda: "1.2.3")
    monkeypatch.setattr(version_module, "_find_pyproject_path", lambda: None)

    def raise_not_found(_name: str) -> str:
        raise version_module.PackageNotFoundError

    monkeypatch.setattr(version_module, "dist_version", raise_not_found)

    with pytest.raises(RuntimeError, match="Installed metadata is missing"):
        version_module.verify_version_install_sync(dist_name="ace-lite-engine")


def test_get_update_status_prefers_source_update_script_for_editable_install(
    monkeypatch, tmp_path
) -> None:
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text("[project]\nversion='1.2.3'\n", encoding="utf-8")
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "update.py").write_text("print('ok')\n", encoding="utf-8")

    class _FakeDistribution:
        @staticmethod
        def read_text(name: str) -> str | None:
            if name != "direct_url.json":
                return None
            return (
                '{"url":"'
                + tmp_path.resolve().as_uri()
                + '","dir_info":{"editable":true}}'
            )

    monkeypatch.setattr(version_module, "_find_pyproject_path", lambda: pyproject_path)
    monkeypatch.setattr(version_module, "_read_pyproject_version", lambda: "1.2.3")
    monkeypatch.setattr(version_module, "dist_version", lambda _name: "1.2.3")
    monkeypatch.setattr(version_module, "distribution", lambda _name: _FakeDistribution())

    status = version_module.get_update_status(
        version_info=version_module.get_version_info(),
        include_latest_release=False,
    )

    assert status["install_mode"] == "editable"
    assert status["install_sync_required"] is False
    assert "update.py --root" in str(status["recommended_update_command"])


def test_get_update_status_detects_newer_published_release(monkeypatch) -> None:
    monkeypatch.setattr(version_module, "_find_pyproject_path", lambda: None)
    monkeypatch.setattr(version_module, "_read_pyproject_version", lambda: None)
    monkeypatch.setattr(version_module, "dist_version", lambda _name: "1.2.3")

    def _raise_package_not_found(_name: str):
        raise version_module.PackageNotFoundError

    monkeypatch.setattr(version_module, "distribution", _raise_package_not_found)

    status = version_module.get_update_status(
        version_info=version_module.get_version_info(),
        pypi_lookup_fn=lambda *_args, **_kwargs: {
            "ok": True,
            "source": "pypi",
            "latest_version": "1.2.4",
            "error": "",
        },
    )

    assert status["install_mode"] == "installed_package"
    assert status["latest_published_version"] == "1.2.4"
    assert status["release_update_available"] is True
    assert status["update_available"] is True
    assert status["recommended_update_command"] == "python -m pip install -U ace-lite-engine"
