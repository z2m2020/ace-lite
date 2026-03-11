$ErrorActionPreference = "Stop"

Write-Host "==> git pull" -ForegroundColor Cyan
git pull

Write-Host "==> pip install -e .[dev]" -ForegroundColor Cyan
python -m pip install -e ".[dev]"

Write-Host "==> version check" -ForegroundColor Cyan
python -c "from ace_lite.version import verify_version_install_sync; print(verify_version_install_sync())"
