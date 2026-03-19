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

## 0.3.16

### Added

- Feature-flagged ripgrep exact-search boost/injection (`--exact-search*`).

### Notes

- Default behavior is unchanged unless `--exact-search` is enabled.
