from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

_APP_DISPLAY_NAMES: dict[str, str] = {
    "codex": "Codex",
    "opencode": "OpenCode",
    "claude-code": "Claude Code",
    "claude_code": "Claude Code",
    "claude": "Claude",
}


@dataclass
class CommandResult:
    cmd: list[str]
    cwd: str | None
    returncode: int
    stdout: str
    stderr: str


def _run_command(*, cmd: list[str], cwd: Path | None = None) -> CommandResult:
    completed = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=False,
        capture_output=True,
        text=True,
    )
    return CommandResult(
        cmd=cmd,
        cwd=str(cwd) if cwd else None,
        returncode=int(completed.returncode),
        stdout=str(completed.stdout or ""),
        stderr=str(completed.stderr or ""),
    )


def _require_success(result: CommandResult, *, label: str) -> None:
    if result.returncode == 0:
        return

    details = [
        f"{label} failed with exit code {result.returncode}",
        f"cmd: {' '.join(result.cmd)}",
    ]
    if result.cwd:
        details.append(f"cwd: {result.cwd}")
    if result.stdout.strip():
        details.append(f"stdout:\n{result.stdout.strip()}")
    if result.stderr.strip():
        details.append(f"stderr:\n{result.stderr.strip()}")
    raise RuntimeError("\n".join(details))


def _resolve_path(*, project_root: Path, value: str) -> Path:
    candidate = Path(str(value).strip())
    if candidate.is_absolute():
        return candidate
    return project_root / candidate


def _ensure_checkout(
    *, workspace: Path, repo_name: str, repo_url: str, repo_ref: str
) -> dict[str, str]:
    target = workspace / repo_name
    target.parent.mkdir(parents=True, exist_ok=True)

    if not (target / ".git").exists():
        if target.exists():
            raise ValueError(f"checkout target exists without .git: {target}")
        clone = _run_command(
            cmd=[
                "git",
                "clone",
                "--depth",
                "1",
                "--branch",
                repo_ref,
                repo_url,
                str(target),
            ]
        )
        _require_success(clone, label=f"clone {repo_name}")
    else:
        fetch = _run_command(
            cmd=["git", "-C", str(target), "fetch", "--depth", "1", "origin", repo_ref]
        )
        _require_success(fetch, label=f"fetch {repo_name}")
        checkout = _run_command(
            cmd=["git", "-C", str(target), "checkout", "--force", "FETCH_HEAD"]
        )
        _require_success(checkout, label=f"checkout {repo_name}")

    rev = _run_command(cmd=["git", "-C", str(target), "rev-parse", "HEAD"])
    _require_success(rev, label=f"resolve head {repo_name}")

    return {
        "name": repo_name,
        "root": str(target.resolve()),
        "ref": repo_ref,
        "url": repo_url,
        "resolved_commit": str(rev.stdout or "").strip(),
    }


def _default_cases() -> list[dict[str, str]]:
    return [
        {
            "id": "intake",
            "expected": "cross-agent-intake-and-scope",
            "query_template": "Before coding in {agent_name}, define scope, constraints, and validation plan for frontend router cleanup.",
        },
        {
            "id": "bugfix",
            "expected": "cross-agent-bugfix-and-regression",
            "query_template": "In {agent_name}, fix failing frontend test with exception and regression in transaction details route and provide rollback plan.",
        },
        {
            "id": "refactor",
            "expected": "cross-agent-refactor-safeguards",
            "query_template": "Use {agent_name} to refactor duplicated wallet table formatting code for maintainability without changing API behavior.",
        },
        {
            "id": "release",
            "expected": "cross-agent-release-readiness",
            "query_template": "Run release readiness review in {agent_name} for frontend RC with freeze gates, benchmark thresholds, and compatibility checks.",
        },
        {
            "id": "benchmark",
            "expected": "cross-agent-benchmark-tuning-loop",
            "query_template": "In {agent_name}, review benchmark tuning loop to improve precision and noise while keeping latency threshold stable.",
        },
        {
            "id": "handoff",
            "expected": "cross-agent-handoff-and-context-sync",
            "query_template": "Create handoff context sync for {agent_name} workflow to avoid stale drift and mismatch next session.",
        },
    ]


def _load_cases(*, cases_json_path: Path | None) -> list[dict[str, str]]:
    if cases_json_path is None:
        return _default_cases()

    payload = json.loads(cases_json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("cases json must be a list")

    cases: list[dict[str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        case_id = str(item.get("id") or "").strip()
        expected = str(item.get("expected") or "").strip()
        query = str(item.get("query") or "").strip()
        query_template = str(item.get("query_template") or "").strip()
        if not query_template and query:
            query_template = query
        if not case_id or not expected or not query_template:
            continue
        cases.append(
            {
                "id": case_id,
                "expected": expected,
                "query_template": query_template,
            }
        )

    if not cases:
        raise ValueError("cases json has no valid cases")

    return cases


def _display_app_name(app: str) -> str:
    key = str(app or "").strip().lower()
    if key in _APP_DISPLAY_NAMES:
        return _APP_DISPLAY_NAMES[key]
    return key or "app"


def _parse_apps(*, app: str, apps: str) -> list[str]:
    if str(app).strip():
        raw = [str(app).strip()]
    else:
        raw = [token.strip() for token in str(apps).split(",") if token.strip()]

    normalized: list[str] = []
    seen: set[str] = set()
    for token in raw:
        value = token.lower()
        if value in {"claude code", "claude_code"}:
            value = "claude-code"
        if value in seen:
            continue
        seen.add(value)
        normalized.append(value)

    return normalized


def _render_query(*, case: dict[str, str], app: str) -> str:
    template = str(case.get("query_template") or "").strip()
    if not template:
        return ""
    return template.format(
        app=app,
        app_name=app,
        agent=app,
        agent_name=_display_app_name(app),
    )


def _run_case(
    *,
    cli_bin: str,
    repo: dict[str, str],
    skills_dir: Path,
    index_cache_path: Path,
    languages: str,
    app: str,
    top_k_files: int,
    candidate_ranker: str,
    case: dict[str, str],
    query: str,
) -> dict[str, Any]:
    command = [
        cli_bin,
        "plan",
        "--query",
        query,
        "--repo",
        repo["name"],
        "--root",
        repo["root"],
        "--skills-dir",
        str(skills_dir),
        "--index-cache-path",
        str(index_cache_path),
        "--languages",
        str(languages),
        "--memory-primary",
        "none",
        "--memory-secondary",
        "none",
        "--no-plugins",
        "--no-lsp",
        "--no-repomap",
        "--no-cochange",
        "--candidate-ranker",
        str(candidate_ranker),
        "--top-k-files",
        str(max(1, int(top_k_files))),
        "--app",
        str(app),
    ]

    started = perf_counter()
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    elapsed = perf_counter() - started

    if completed.returncode != 0:
        return {
            "id": case["id"],
            "app": app,
            "expected": case["expected"],
            "ok": False,
            "query": query,
            "elapsed_s": round(elapsed, 3),
            "error": str(completed.stderr or completed.stdout or "").strip(),
            "command": command,
        }

    try:
        payload = json.loads(str(completed.stdout or "").strip())
    except Exception as exc:
        return {
            "id": case["id"],
            "app": app,
            "expected": case["expected"],
            "ok": False,
            "query": query,
            "elapsed_s": round(elapsed, 3),
            "error": f"json_parse_error: {exc}",
            "command": command,
        }

    selected = payload.get("skills", {}).get("selected", [])
    selected_names = [
        str(item.get("name", ""))
        for item in selected
        if isinstance(item, dict) and str(item.get("name", "")).strip()
    ]
    expected_hit = case["expected"] in selected_names

    return {
        "id": case["id"],
        "app": app,
        "expected": case["expected"],
        "ok": expected_hit,
        "query": query,
        "elapsed_s": round(elapsed, 3),
        "selected": selected_names,
        "scores": {
            str(item.get("name", "")): item.get("score")
            for item in selected
            if isinstance(item, dict) and str(item.get("name", "")).strip()
        },
        "matched": {
            str(item.get("name", "")): item.get("matched", [])
            for item in selected
            if isinstance(item, dict) and str(item.get("name", "")).strip()
        },
        "command": command,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate cross-agent skill routing with ace-lite plan."
    )
    parser.add_argument(
        "--repo-url",
        default="https://github.com/blockscout/frontend.git",
        help="Target repository URL used for skill routing validation.",
    )
    parser.add_argument(
        "--repo-ref",
        default="main",
        help="Git ref to checkout for the target repository.",
    )
    parser.add_argument(
        "--repo-name",
        default="blockscout-frontend",
        help="Repository identifier used in plan output and checkout folder.",
    )
    parser.add_argument(
        "--repo-dir",
        default="artifacts/repos-workdir/skill-validation",
        help="Workspace directory where the target repository is cloned/fetched.",
    )
    parser.add_argument(
        "--skills-dir",
        default="skills",
        help="Skills directory used by ace-lite plan.",
    )
    parser.add_argument(
        "--index-cache-path",
        default="artifacts/skill-eval/blockscout-index.json",
        help="Index cache path reused across skill validation cases.",
    )
    parser.add_argument(
        "--output-path",
        default="artifacts/skill-eval/blockscout_skill_validation_matrix.json",
        help="Output json report path.",
    )
    parser.add_argument(
        "--languages",
        default="typescript,javascript",
        help="Comma-separated language profile for index stage.",
    )
    parser.add_argument(
        "--app",
        default="",
        help="Legacy single app scope; when set it overrides --apps.",
    )
    parser.add_argument(
        "--apps",
        default="codex,opencode,claude-code",
        help="Comma-separated app scopes validated in one run.",
    )
    parser.add_argument(
        "--top-k-files",
        type=int,
        default=6,
        help="Top ranked candidate files retained in each run.",
    )
    parser.add_argument(
        "--candidate-ranker",
        default="heuristic",
        help="Candidate ranker used during validation.",
    )
    parser.add_argument(
        "--cases-json",
        default="",
        help="Optional json file that overrides default validation cases.",
    )
    parser.add_argument(
        "--cli-bin",
        default="ace-lite",
        help="CLI binary name/path.",
    )
    parser.add_argument(
        "--min-pass-rate",
        type=float,
        default=1.0,
        help="Minimum pass rate required when --fail-on-miss is enabled.",
    )
    parser.add_argument(
        "--fail-on-miss",
        action="store_true",
        help="Exit non-zero when any app pass rate is below --min-pass-rate.",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    repo_workspace = _resolve_path(project_root=project_root, value=str(args.repo_dir))
    skills_dir = _resolve_path(project_root=project_root, value=str(args.skills_dir))
    index_cache_path = _resolve_path(
        project_root=project_root, value=str(args.index_cache_path)
    )
    output_path = _resolve_path(project_root=project_root, value=str(args.output_path))
    cases_json_path = (
        _resolve_path(project_root=project_root, value=str(args.cases_json))
        if str(args.cases_json).strip()
        else None
    )

    apps = _parse_apps(app=str(args.app), apps=str(args.apps))
    if not apps:
        raise ValueError("no app scopes provided; use --app or --apps")

    if not skills_dir.exists() or not skills_dir.is_dir():
        raise FileNotFoundError(f"skills dir not found: {skills_dir}")

    index_cache_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    checkout = _ensure_checkout(
        workspace=repo_workspace,
        repo_name=str(args.repo_name),
        repo_url=str(args.repo_url),
        repo_ref=str(args.repo_ref),
    )

    cases = _load_cases(cases_json_path=cases_json_path)

    started = perf_counter()
    all_case_results: list[dict[str, Any]] = []
    app_summaries: list[dict[str, Any]] = []

    for app in apps:
        app_case_results: list[dict[str, Any]] = []
        for case in cases:
            query = _render_query(case=case, app=app)
            result = _run_case(
                cli_bin=str(args.cli_bin),
                repo=checkout,
                skills_dir=skills_dir,
                index_cache_path=index_cache_path,
                languages=str(args.languages),
                app=str(app),
                top_k_files=int(args.top_k_files),
                candidate_ranker=str(args.candidate_ranker),
                case=case,
                query=query,
            )
            app_case_results.append(result)
            all_case_results.append(result)

        app_total = len(app_case_results)
        app_pass_count = sum(1 for item in app_case_results if bool(item.get("ok", False)))
        app_pass_rate = (float(app_pass_count) / float(app_total)) if app_total else 0.0
        app_summaries.append(
            {
                "app": app,
                "display_name": _display_app_name(app),
                "pass_count": app_pass_count,
                "total": app_total,
                "pass_rate": round(app_pass_rate, 4),
                "cases": app_case_results,
            }
        )

    elapsed = perf_counter() - started
    total = len(all_case_results)
    pass_count = sum(1 for item in all_case_results if bool(item.get("ok", False)))
    pass_rate = (float(pass_count) / float(total)) if total else 0.0

    min_pass_rate = float(args.min_pass_rate)
    failed_apps = [
        item["app"] for item in app_summaries if float(item.get("pass_rate", 0.0)) < min_pass_rate
    ]

    summary: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(project_root),
        "repo": {
            "name": checkout["name"],
            "root": checkout["root"],
            "url": checkout["url"],
            "ref": checkout["ref"],
            "resolved_commit": checkout["resolved_commit"],
        },
        "settings": {
            "skills_dir": str(skills_dir),
            "index_cache_path": str(index_cache_path),
            "languages": str(args.languages),
            "apps": apps,
            "top_k_files": int(args.top_k_files),
            "candidate_ranker": str(args.candidate_ranker),
            "min_pass_rate": min_pass_rate,
            "fail_on_miss": bool(args.fail_on_miss),
        },
        "elapsed_seconds": round(elapsed, 3),
        "pass_count": pass_count,
        "total": total,
        "pass_rate": round(pass_rate, 4),
        "failed_apps": failed_apps,
        "apps": app_summaries,
    }

    output_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"[skills] report json: {output_path}")
    print(
        f"[skills] overall pass rate: {pass_count}/{total} ({pass_rate:.2%})"
    )
    for app_summary in app_summaries:
        print(
            "[skills] app={app} pass rate: {pass_count}/{total} ({rate:.2%})".format(
                app=app_summary.get("app", ""),
                pass_count=int(app_summary.get("pass_count", 0) or 0),
                total=int(app_summary.get("total", 0) or 0),
                rate=float(app_summary.get("pass_rate", 0.0) or 0.0),
            )
        )

    if args.fail_on_miss and failed_apps:
        print(
            "[skills] validation failed: app pass rate below required {required:.2%}: {apps}".format(
                required=min_pass_rate,
                apps=", ".join(failed_apps),
            ),
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
