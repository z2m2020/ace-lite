from __future__ import annotations

import re
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Finding:
    doc_path: str
    line_no: int
    snippet: str
    message: str


_CODE_FENCE_START = re.compile(r"^\s*```(\w+)?\s*$")
_CODE_FENCE_END = re.compile(r"^\s*```\s*$")
_ACE_LITE_CMD = re.compile(r"^\s*ace-lite(\s+.+)?$")
_FLAG = re.compile(r"--[A-Za-z0-9][A-Za-z0-9_-]*")
_ALWAYS_ALLOWED_FLAGS = {"--help", "--version"}


def _iter_code_blocks(lines: list[str]) -> list[tuple[int, list[str]]]:
    blocks: list[tuple[int, list[str]]] = []
    in_block = False
    start_line = 0
    buf: list[str] = []
    for idx, line in enumerate(lines, start=1):
        if not in_block and _CODE_FENCE_START.match(line):
            in_block = True
            start_line = idx + 1
            buf = []
            continue
        if in_block and _CODE_FENCE_END.match(line):
            in_block = False
            blocks.append((start_line, buf))
            buf = []
            continue
        if in_block:
            buf.append(line)
    return blocks


def _join_continuations(cmd_lines: list[str]) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    current: list[str] = []
    current_start = 0
    for i, raw in enumerate(cmd_lines):
        line_no = i
        line = raw.rstrip()
        if not line.strip():
            continue
        if not current:
            current_start = line_no
        if line.endswith("\\"):
            current.append(line[:-1].rstrip())
            continue
        current.append(line)
        out.append((current_start, " ".join(part.strip() for part in current if part.strip())))
        current = []
        current_start = 0
    if current:
        out.append((current_start, " ".join(part.strip() for part in current if part.strip())))
    return out


def _resolve_click_command(cli, path: list[str]):
    cmd = cli
    for seg in path:
        if not hasattr(cmd, "commands"):
            raise KeyError(f"not a command group: {' '.join(path)}")
        commands = cmd.commands or {}
        if seg not in commands:
            raise KeyError(f"unknown command segment: {seg}")
        cmd = commands[seg]
    return cmd


def _valid_flags_for_command(cmd) -> set[str]:
    flags: set[str] = set()
    for param in getattr(cmd, "params", []) or []:
        opts = getattr(param, "opts", None) or []
        secondary = getattr(param, "secondary_opts", None) or []
        for opt in list(opts) + list(secondary):
            if isinstance(opt, str) and opt.startswith("--"):
                flags.add(opt)
    return flags


def _command_path_from_invocation(invocation: str) -> list[str]:
    try:
        tokens = shlex.split(invocation.strip(), posix=True)
    except Exception:
        tokens = invocation.strip().split()
    if not tokens or tokens[0] != "ace-lite":
        return []
    return tokens[1:]


def _flags_from_invocation(invocation: str) -> set[str]:
    return set(_FLAG.findall(invocation))


def validate_docs(*, docs_root: Path) -> list[Finding]:
    sys.path.insert(0, str(docs_root.parent / "src"))
    import ace_lite.cli as cli_module  # type: ignore

    findings: list[Finding] = []

    for md_path in sorted(docs_root.rglob("*.md")):
        text = md_path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        for block_start, block_lines in _iter_code_blocks(lines):
            joined = _join_continuations(block_lines)
            for rel_line_no, cmd in joined:
                if not _ACE_LITE_CMD.match(cmd):
                    continue
                tail = _command_path_from_invocation(cmd)

                click_cmd = cli_module.cli
                command_path: list[str] = []
                remaining = list(tail)
                while remaining and hasattr(click_cmd, "commands"):
                    next_seg = remaining[0]
                    commands = click_cmd.commands or {}
                    if next_seg not in commands:
                        break
                    command_path.append(next_seg)
                    click_cmd = commands[next_seg]
                    remaining = remaining[1:]

                if not command_path:
                    # Root command invocation, e.g. `ace-lite --help`
                    click_cmd = cli_module.cli

                valid = _valid_flags_for_command(click_cmd)
                used = _flags_from_invocation(cmd)
                unknown = sorted(
                    flag for flag in used if flag not in valid and flag not in _ALWAYS_ALLOWED_FLAGS
                )
                if unknown:
                    findings.append(
                        Finding(
                            doc_path=str(md_path),
                            line_no=block_start + rel_line_no,
                            snippet=cmd,
                            message=(
                                "Unknown flags for "
                                + " ".join(["ace-lite", *command_path]).strip()
                                + f": {', '.join(unknown)}"
                            ),
                        )
                    )
    return findings


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    docs_root = repo_root / "docs"
    findings = validate_docs(docs_root=docs_root)
    if not findings:
        print("OK: no unknown ace-lite commands/flags found in docs/*.md")
        return
    print(f"Found {len(findings)} issue(s) in docs CLI snippets:\n")
    for item in findings:
        print(f"- {item.doc_path}:{item.line_no}: {item.message}")
        print(f"  {item.snippet}")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
