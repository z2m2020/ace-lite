from __future__ import annotations

import argparse
import sys

from ace_lite.run_manifest import append_run_manifest_entry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Append a run_manifest_v1 entry to a JSONL manifest file."
    )
    parser.add_argument("--unit-id", required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--priority", required=True)
    parser.add_argument("--owner-role", required=True)
    parser.add_argument("--status", required=True)
    parser.add_argument("--depends-on", default="")
    parser.add_argument("--path-set", default="")
    parser.add_argument("--forbidden-paths", default="")
    parser.add_argument("--goal", required=True)
    parser.add_argument("--deliverable", required=True)
    parser.add_argument("--input-contracts", default="")
    parser.add_argument("--output-contracts", default="")
    parser.add_argument("--metrics-touched", default="")
    parser.add_argument("--verification-commands", default="")
    parser.add_argument("--artifacts-emitted", default="")
    parser.add_argument("--rollback-steps", default="")
    parser.add_argument("--done-definition", default="")
    parser.add_argument("--failure-signals", default="")
    parser.add_argument(
        "--manifest-path",
        default="context-map/run_manifest.jsonl",
        help="Path to output JSONL manifest (default: context-map/run_manifest.jsonl)",
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    def _split(value: str) -> list[str]:
        return [v.strip() for v in value.split(",") if v.strip()] if value else []

    entry = {
        "unit_id": args.unit_id,
        "phase": args.phase,
        "priority": args.priority,
        "owner_role": args.owner_role,
        "status": args.status,
        "depends_on": _split(args.depends_on),
        "path_set": _split(args.path_set),
        "forbidden_paths": _split(args.forbidden_paths),
        "goal": args.goal,
        "deliverable": args.deliverable,
        "input_contracts": _split(args.input_contracts),
        "output_contracts": _split(args.output_contracts),
        "metrics_touched": _split(args.metrics_touched),
        "verification_commands": _split(args.verification_commands),
        "artifacts_emitted": _split(args.artifacts_emitted),
        "rollback_steps": _split(args.rollback_steps),
        "done_definition": _split(args.done_definition),
        "failure_signals": _split(args.failure_signals),
    }

    try:
        append_run_manifest_entry(manifest_path=args.manifest_path, entry=entry)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
