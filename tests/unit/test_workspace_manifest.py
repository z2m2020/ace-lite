from __future__ import annotations

import copy
import importlib
import inspect
from pathlib import Path
from typing import Any

import pytest
import yaml


def _import_manifest_module():
    for module_name in (
        "ace_lite.workspace.manifest",
        "ace_lite.workspace_manifest",
    ):
        try:
            return importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
    pytest.skip("workspace manifest module is not integrated yet")


def _write_manifest(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def _manifest_payload_variants() -> list[dict[str, Any]]:
    repos = [
        {"name": "repo-alpha", "path": "repos/repo-alpha"},
        {"name": "repo-beta", "path": "repos/repo-beta"},
    ]
    return [
        {"workspace": {"name": "Demo Hub"}, "repos": repos},
        {"workspace": {"id": "demo-hub", "name": "Demo Hub"}, "repos": repos},
        {"workspace_name": "Demo Hub", "repos": repos},
    ]


def _invoke_loader(loader: Any, manifest_path: Path, workspace_root: Path) -> Any:
    signature = inspect.signature(loader)
    kwargs: dict[str, Any] = {}
    for param_name, param in signature.parameters.items():
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        if param_name in {"manifest_path", "path", "file_path", "workspace_manifest"}:
            kwargs[param_name] = manifest_path
            continue
        if param_name in {"root", "workspace_root", "base_dir", "cwd"}:
            kwargs[param_name] = workspace_root
            continue
        if param.default is inspect._empty:
            pytest.skip(f"unsupported required loader parameter: {param_name}")

    if kwargs:
        return loader(**kwargs)
    return loader(manifest_path)


def _load_manifest(module: Any, manifest_path: Path, workspace_root: Path) -> Any:
    for loader_name in (
        "load_workspace_manifest",
        "parse_workspace_manifest",
        "read_workspace_manifest",
        "load_manifest",
        "parse_manifest",
    ):
        loader = getattr(module, loader_name, None)
        if callable(loader):
            return _invoke_loader(loader, manifest_path=manifest_path, workspace_root=workspace_root)
    pytest.skip("workspace manifest loader function is not integrated yet")


def _extract_repos(manifest: Any) -> list[Any]:
    if isinstance(manifest, dict):
        for key in ("repos", "repositories", "repo_registry", "repo_set"):
            value = manifest.get(key)
            if isinstance(value, (list, tuple)):
                return list(value)
    for key in ("repos", "repositories", "repo_registry", "repo_set"):
        value = getattr(manifest, key, None)
        if isinstance(value, (list, tuple)):
            return list(value)
    raise AssertionError("manifest result does not expose a repo list")


def _extract_repo_path(repo: Any) -> Path:
    path_keys = ("resolved_path", "abs_path", "root", "path", "local_path", "dir", "repo_path")
    if isinstance(repo, dict):
        for key in path_keys:
            if key in repo:
                return Path(str(repo[key]))
    for key in path_keys:
        value = getattr(repo, key, None)
        if value is not None:
            return Path(str(value))
    raise AssertionError("repo entry does not expose a path field")


def _load_first_valid_variant(module: Any, tmp_path: Path) -> tuple[dict[str, Any], Any]:
    errors: list[str] = []
    for idx, payload in enumerate(_manifest_payload_variants()):
        manifest_path = _write_manifest(tmp_path / f"workspace.variant{idx}.yaml", payload)
        try:
            parsed = _load_manifest(module, manifest_path=manifest_path, workspace_root=tmp_path)
            return payload, parsed
        except Exception as exc:
            errors.append(f"variant[{idx}] {type(exc).__name__}: {exc}")
    raise AssertionError("no manifest variant parsed successfully\n" + "\n".join(errors))


def test_workspace_manifest_parses_and_resolves_relative_paths(tmp_path: Path) -> None:
    module = _import_manifest_module()
    (tmp_path / "repos" / "repo-alpha").mkdir(parents=True, exist_ok=True)
    (tmp_path / "repos" / "repo-beta").mkdir(parents=True, exist_ok=True)

    _, parsed = _load_first_valid_variant(module, tmp_path)
    repos = _extract_repos(parsed)
    assert repos

    first_repo_path = _extract_repo_path(repos[0])
    assert first_repo_path.is_absolute()
    assert first_repo_path == (tmp_path / "repos" / "repo-alpha").resolve()


def test_workspace_manifest_required_fields_raise_errors(tmp_path: Path) -> None:
    module = _import_manifest_module()
    (tmp_path / "repos" / "repo-alpha").mkdir(parents=True, exist_ok=True)
    (tmp_path / "repos" / "repo-beta").mkdir(parents=True, exist_ok=True)

    valid_payload, _ = _load_first_valid_variant(module, tmp_path)

    missing_repos = copy.deepcopy(valid_payload)
    missing_repos.pop("repos", None)
    missing_repos_path = _write_manifest(tmp_path / "workspace.missing-repos.yaml", missing_repos)
    with pytest.raises(Exception, match=r"(required|missing|repos)"):
        _load_manifest(module, manifest_path=missing_repos_path, workspace_root=tmp_path)

    missing_repo_field = copy.deepcopy(valid_payload)
    repos = missing_repo_field.get("repos")
    if not isinstance(repos, list) or not repos:
        pytest.skip("selected manifest variant does not expose repos as a list")
    first_repo = repos[0]
    if not isinstance(first_repo, dict):
        pytest.skip("selected manifest variant repo entry is not a dict")
    field_to_drop = "name" if "name" in first_repo else "path"
    first_repo.pop(field_to_drop, None)

    missing_repo_field_path = _write_manifest(
        tmp_path / "workspace.missing-repo-field.yaml",
        missing_repo_field,
    )
    with pytest.raises(Exception, match=r"(required|missing|name|path|repo)"):
        _load_manifest(module, manifest_path=missing_repo_field_path, workspace_root=tmp_path)


@pytest.mark.parametrize("weight", [float("nan"), float("inf"), float("-inf")])
def test_workspace_manifest_rejects_non_finite_weight(tmp_path: Path, weight: float) -> None:
    module = _import_manifest_module()
    (tmp_path / "repos" / "repo-alpha").mkdir(parents=True, exist_ok=True)

    payload = {
        "workspace": {"name": "Demo Hub"},
        "repos": [
            {
                "name": "repo-alpha",
                "path": "repos/repo-alpha",
                "weight": weight,
            }
        ],
    }
    manifest_path = _write_manifest(tmp_path / "workspace.weight.yaml", payload)

    with pytest.raises(Exception, match=r"weight must be finite"):
        _load_manifest(module, manifest_path=manifest_path, workspace_root=tmp_path)


def test_workspace_manifest_rejects_bool_for_plan_quick_integer_options(
    tmp_path: Path,
) -> None:
    module = _import_manifest_module()
    (tmp_path / "repos" / "repo-alpha").mkdir(parents=True, exist_ok=True)

    payload = {
        "workspace": {"name": "Demo Hub"},
        "repos": [
            {
                "name": "repo-alpha",
                "path": "repos/repo-alpha",
                "plan_quick": {"top_k_files": True},
            }
        ],
    }
    manifest_path = _write_manifest(tmp_path / "workspace.planquick-bool.yaml", payload)

    with pytest.raises(Exception, match=r"must be an integer"):
        _load_manifest(module, manifest_path=manifest_path, workspace_root=tmp_path)
