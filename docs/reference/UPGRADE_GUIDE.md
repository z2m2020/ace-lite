# Upgrade Guide (ACE-Lite)

This project follows Semantic Versioning. Most releases are backwards-compatible within a minor series.

## Editable install drift (important)

If you `git pull` but do not rerun an editable install, the installed pip metadata can drift (entry points / dependencies may
remain stale). ACE-Lite now detects this and reports it via `ace_health` warnings.

To resync:

- Cross-platform: `python scripts/update.py`
- Windows (PowerShell): `./scripts/update.ps1`
- Make: `make update`
- Manual: `python -m pip install -e ".[dev]"`

`./scripts/update.ps1` now fails if the installed distribution metadata still
does not match `pyproject.toml`, so release/update maintenance no longer only
prints the drift and keeps going.

`python scripts/update.py` provides the same editable-install sync flow without
depending on PowerShell. If your repo is already up to date but local `git`
launch fails, rerun it with `--skip-git-pull`.

## Recommended install and upgrade paths

Use the channel that matches how you run ACE-Lite:

- Source checkout / editable install: `ace-lite self-update` or `python scripts/update.py`
- Plain `pip` install: `ace-lite self-update` or `python -m pip install -U ace-lite-engine`
- `pipx` install: `pipx upgrade ace-lite-engine`
- `uv tool` install: `uv tool upgrade ace-lite-engine`

`ace-lite self-update --check` prints the resolved plan first, including the
detected install mode and recommended command.

On Windows, `ace-lite self-update` may hand off the actual reinstall to a
background helper so the current `ace-lite.exe` process can exit before pip
replaces console scripts.

## 0.3.16

### Added

- Feature-flagged ripgrep exact-search boost/injection (`--exact-search*`).

### Notes

- Default behavior is unchanged unless `--exact-search` is enabled.
