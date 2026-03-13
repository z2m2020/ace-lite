from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _resolve_path(*, root: Path, value: str) -> Path:
    candidate = Path(str(value).strip())
    if candidate.is_absolute():
        return candidate
    return (root / candidate).resolve()


def _copy_file(*, source: Path, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return str(destination)


def _copy_tree_if_exists(*, source: Path, destination: Path) -> list[str]:
    if not source.exists() or not source.is_dir():
        return []
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    copied: list[str] = []
    for path in destination.rglob("*"):
        if path.is_file():
            copied.append(str(path))
    return copied


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _render_next_cycle_todo(*, payload: dict[str, Any]) -> str:
    archived_raw = payload.get("archived_files")
    archived_files = archived_raw if isinstance(archived_raw, list) else []
    decision_raw = payload.get("promotion_decision")
    decision = decision_raw if isinstance(decision_raw, dict) else {}
    reasons_raw = decision.get("reasons")
    reasons = reasons_raw if isinstance(reasons_raw, list) else []

    lines = [
        "# Validation-Rich Next Cycle Todo",
        "",
        f"- Archive date: {payload.get('archive_date', '')}",
        f"- Promotion recommendation: {decision.get('recommendation', 'stay_report_only')}",
        "",
        "## Archived Files",
        "",
    ]
    if archived_files:
        for item in archived_files:
            lines.append(f"- `{item}`")
    else:
        lines.append("- None")

    lines.extend(["", "## Follow-ups", ""])
    if reasons:
        for reason in reasons:
            lines.append(f"- Resolve: {reason}")
    else:
        lines.append("- Review whether `validation_rich_gate.mode` can move beyond `report_only`.")
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Archive validation-rich evidence into a dated directory and seed the next cycle todo."
    )
    parser.add_argument("--date", required=True, help="Archive date in YYYY-MM-DD format.")
    parser.add_argument("--summary", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--trend-dir", default="")
    parser.add_argument("--stability-dir", default="")
    parser.add_argument("--comparison-dir", default="")
    parser.add_argument("--promotion-decision", default="")
    parser.add_argument("--output-root", default="artifacts/benchmark/validation_rich/archive")
    args = parser.parse_args(sys.argv[1:])

    root = Path(__file__).resolve().parents[1]
    archive_date = str(args.date).strip()
    if not archive_date:
        print("[validation-rich-archive] missing archive date", file=sys.stderr)
        return 2

    output_root = _resolve_path(root=root, value=str(args.output_root))
    dated_root = output_root / archive_date
    dated_root.mkdir(parents=True, exist_ok=True)

    archived_files: list[str] = []
    for name, value in (
        ("summary.json", args.summary),
        ("results.json", args.results),
        ("report.md", args.report),
    ):
        source = _resolve_path(root=root, value=str(value))
        if not source.exists():
            print(f"[validation-rich-archive] missing required file: {source}", file=sys.stderr)
            return 2
        archived_files.append(_copy_file(source=source, destination=dated_root / name))

    for folder_name, value in (
        ("trend", args.trend_dir),
        ("stability", args.stability_dir),
        ("comparison", args.comparison_dir),
    ):
        if not str(value).strip():
            continue
        archived_files.extend(
            _copy_tree_if_exists(
                source=_resolve_path(root=root, value=str(value)),
                destination=dated_root / folder_name,
            )
        )

    promotion_decision = {}
    if str(args.promotion_decision).strip():
        decision_path = _resolve_path(root=root, value=str(args.promotion_decision))
        promotion_decision = _load_json(decision_path)
        if decision_path.exists():
            archived_files.append(
                _copy_file(
                    source=decision_path,
                    destination=dated_root / "promotion_decision.json",
                )
            )
            md_path = decision_path.with_suffix(".md")
            if md_path.exists():
                archived_files.append(
                    _copy_file(
                        source=md_path,
                        destination=dated_root / "promotion_decision.md",
                    )
                )

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "archive_date": archive_date,
        "dated_root": str(dated_root),
        "archived_files": archived_files,
        "promotion_decision": promotion_decision,
    }
    manifest_path = dated_root / "archive_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    todo_path = dated_root / "next_cycle_todo.md"
    todo_path.write_text(_render_next_cycle_todo(payload=manifest), encoding="utf-8")

    print(f"[validation-rich-archive] dated root: {dated_root}")
    print(f"[validation-rich-archive] manifest:   {manifest_path}")
    print(f"[validation-rich-archive] next todo:  {todo_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
