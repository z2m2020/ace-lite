from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _resolve_path(*, root: Path, value: str) -> Path:
    candidate = Path(str(value).strip())
    if candidate.is_absolute():
        return candidate
    return (root / candidate).resolve()


def _git_sha(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(repo_root),
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def _file_artifact_entry(
    *,
    path: Path,
    root: Path,
    schema_version: str,
    notes: str = "",
) -> dict[str, Any]:
    relative = path.relative_to(root) if path.is_absolute() else path
    return {
        "path": str(relative),
        "present": path.exists() and path.is_file(),
        "schema_version": schema_version,
        "notes": notes,
        "status": "present" if (path.exists() and path.is_file()) else "missing",
    }


def create_dated_checkpoint(
    *,
    date: str,
    phase: str,
    output_root: Path,
    repo_root: Path,
    artifact_ledger: Path | None = None,
    artifact_run_manifest: Path | None = None,
    artifact_checkpoint_manifest: Path | None = None,
    artifact_problem_surface: Path | None = None,
) -> dict[str, Any]:
    from ace_lite.checkpoint_manifest import build_checkpoint_manifest_payload

    dated_root = output_root / f"phase{phase}" / date
    dated_root.mkdir(parents=True, exist_ok=True)

    git_sha = _git_sha(repo_root)
    artifacts: list[dict[str, Any]] = []

    if artifact_ledger:
        artifacts.append(
            _file_artifact_entry(
                path=_resolve_path(root=repo_root, value=str(artifact_ledger)),
                root=repo_root,
                schema_version="problem_ledger_v1",
                notes="Phase 0 problem ledger baseline",
            )
        )

    if artifact_run_manifest:
        artifacts.append(
            _file_artifact_entry(
                path=_resolve_path(root=repo_root, value=str(artifact_run_manifest)),
                root=repo_root,
                schema_version="run_manifest_v1",
                notes="Run manifest entries up to checkpoint date",
            )
        )

    if artifact_checkpoint_manifest:
        artifacts.append(
            _file_artifact_entry(
                path=_resolve_path(root=repo_root, value=str(artifact_checkpoint_manifest)),
                root=repo_root,
                schema_version="checkpoint_manifest_v1",
                notes="Checkpoint manifest for this baseline",
            )
        )

    if artifact_problem_surface:
        artifacts.append(
            _file_artifact_entry(
                path=_resolve_path(root=repo_root, value=str(artifact_problem_surface)),
                root=repo_root,
                schema_version="problem_surface_v1",
                notes="Problem surface baseline snapshot",
            )
        )

    payload = build_checkpoint_manifest_payload(
        generated_at=datetime.now(timezone.utc).isoformat(),
        git_sha=git_sha,
        phase=f"phase{phase}",
        included_artifacts=artifacts,
    )

    manifest_path = dated_root / "checkpoint_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return {"dated_root": str(dated_root), "manifest_path": str(manifest_path), "payload": payload}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create a dated checkpoint manifest for a Phase 0 baseline."
    )
    parser.add_argument(
        "--date",
        required=True,
        help="Checkpoint date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--phase",
        required=True,
        help="Phase number (0..5) used to name the checkpoint subdirectory.",
    )
    parser.add_argument(
        "--output-root",
        default="artifacts/checkpoints",
        help="Root directory for checkpoint artifacts (default: artifacts/checkpoints).",
    )
    parser.add_argument(
        "--artifact-ledger",
        default="",
        help="Path to problem_ledger.json artifact (relative to repo root or absolute).",
    )
    parser.add_argument(
        "--artifact-run-manifest",
        default="",
        help="Path to run_manifest.jsonl artifact.",
    )
    parser.add_argument(
        "--artifact-checkpoint-manifest",
        default="",
        help="Path to checkpoint_manifest.json (will be the output of this script).",
    )
    parser.add_argument(
        "--artifact-problem-surface",
        default="",
        help="Path to problem_surface.json artifact.",
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    repo_root = Path(__file__).resolve().parents[1]
    output_root = _resolve_path(root=repo_root, value=str(args.output_root))

    try:
        result = create_dated_checkpoint(
            date=str(args.date).strip(),
            phase=str(args.phase).strip(),
            output_root=output_root,
            repo_root=repo_root,
            artifact_ledger=Path(args.artifact_ledger) if args.artifact_ledger else None,
            artifact_run_manifest=Path(args.artifact_run_manifest)
            if args.artifact_run_manifest
            else None,
            artifact_checkpoint_manifest=Path(args.artifact_checkpoint_manifest)
            if args.artifact_checkpoint_manifest
            else None,
            artifact_problem_surface=Path(args.artifact_problem_surface)
            if args.artifact_problem_surface
            else None,
        )
        print(f"[create-dated-checkpoint] dated_root: {result['dated_root']}")
        print(f"[create-dated-checkpoint] manifest:   {result['manifest_path']}")
        return 0
    except Exception as exc:
        print(f"[create-dated-checkpoint] error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
