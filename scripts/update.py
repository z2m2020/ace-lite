from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _run(command: list[str], *, cwd: Path) -> None:
    print(f"==> {' '.join(command)}")
    subprocess.run(command, cwd=str(cwd), check=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync working tree, editable install metadata, and version state."
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Repository root. Defaults to current directory.",
    )
    parser.add_argument(
        "--python-executable",
        default=sys.executable,
        help="Python executable used for editable install and version check.",
    )
    parser.add_argument(
        "--skip-git-pull",
        action="store_true",
        help="Skip `git pull` even when the repository has a .git directory.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not args.skip_git_pull and (root / ".git").exists():
        try:
            _run(["git", "pull"], cwd=root)
        except OSError as exc:
            raise SystemExit(
                "git pull failed to launch. If the working tree is already updated, "
                "rerun with --skip-git-pull. "
                f"Original error: {exc}"
            ) from exc

    _run([args.python_executable, "-m", "pip", "install", "-e", ".[dev]"], cwd=root)
    _run(
        [
            args.python_executable,
            "-c",
            "from ace_lite.version import verify_version_install_sync; print(verify_version_install_sync())",
        ],
        cwd=root,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
