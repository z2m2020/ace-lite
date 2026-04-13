from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from ace_lite.subprocess_utils import run_capture_output

_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_./-]+")


def tokenize_query_for_exact_search(query: str) -> list[str]:
    text = str(query or "").strip()
    if not text:
        return []

    raw_tokens = [token for token in _TOKEN_PATTERN.findall(text) if token]
    tokens: list[str] = []
    seen: set[str] = set()
    for token in raw_tokens:
        normalized = token.strip()
        if not normalized:
            continue
        if len(normalized) < 2:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        tokens.append(normalized)

    return tokens[:12]


def _build_rg_pattern(tokens: list[str]) -> str:
    escaped: list[str] = []
    for token in tokens:
        value = str(token or "").strip()
        if not value:
            continue
        if re.fullmatch(r"[A-Za-z0-9_]+", value):
            escaped.append(rf"\b{re.escape(value)}\b")
        else:
            escaped.append(re.escape(value))
    return "|".join(escaped)


@dataclass(frozen=True, slots=True)
class ExactSearchResult:
    hits_by_path: dict[str, int]
    reason: str
    timed_out: bool
    returncode: int
    elapsed_ms: float
    stderr: str = ""

    def to_payload(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "backend": "ripgrep",
            "reason": self.reason,
            "timed_out": bool(self.timed_out),
            "returncode": int(self.returncode),
            "elapsed_ms": float(self.elapsed_ms),
            "hit_paths": len(self.hits_by_path),
            "stderr": str(self.stderr or "")[:240],
        }


def run_exact_search_ripgrep(
    *,
    root: str | Path,
    query: str,
    include_globs: list[str],
    timeout_ms: int,
) -> ExactSearchResult:
    started = perf_counter()
    tokens = tokenize_query_for_exact_search(query)
    if not tokens:
        return ExactSearchResult(
            hits_by_path={},
            reason="empty_query",
            timed_out=False,
            returncode=0,
            elapsed_ms=0.0,
            stderr="",
        )

    pattern = _build_rg_pattern(tokens)
    if not pattern:
        return ExactSearchResult(
            hits_by_path={},
            reason="empty_pattern",
            timed_out=False,
            returncode=0,
            elapsed_ms=0.0,
            stderr="",
        )

    root_path = Path(root).expanduser().resolve()
    timeout_seconds = max(0.05, float(max(0, int(timeout_ms))) / 1000.0)

    cmd = [
        "rg",
        "--count-matches",
        "--no-messages",
        "--hidden",
        "--follow",
        "--ignore-case",
    ]
    for glob in include_globs:
        normalized = str(glob or "").strip()
        if normalized:
            cmd.append(f"--glob={normalized}")
    cmd.extend([pattern, "."])

    returncode, stdout, stderr, timed_out = run_capture_output(
        cmd,
        cwd=root_path,
        timeout_seconds=timeout_seconds,
        env_overrides={"GIT_TERMINAL_PROMPT": "0"},
    )

    elapsed_ms = (perf_counter() - started) * 1000.0
    if timed_out:
        return ExactSearchResult(
            hits_by_path={},
            reason="timeout",
            timed_out=True,
            returncode=int(returncode),
            elapsed_ms=float(elapsed_ms),
            stderr=str(stderr or ""),
        )

    if returncode not in (0, 1):
        # ripgrep returns 1 when there are no matches; treat that as ok.
        reason = "command_error"
        if "No such file" in str(stderr or "") or "not found" in str(stderr or "").lower():
            reason = "rg_unavailable"
        return ExactSearchResult(
            hits_by_path={},
            reason=reason,
            timed_out=False,
            returncode=int(returncode),
            elapsed_ms=float(elapsed_ms),
            stderr=str(stderr or ""),
        )

    hits_by_path: dict[str, int] = {}
    for line in str(stdout or "").splitlines():
        text = line.strip()
        if not text:
            continue
        if ":" not in text:
            continue
        path_raw, count_raw = text.rsplit(":", 1)
        path = path_raw.strip().replace("\\", "/")
        if not path:
            continue
        try:
            count = int(count_raw.strip())
        except ValueError:
            continue
        if count <= 0:
            continue
        hits_by_path[path] = int(count)

    reason = "ok" if hits_by_path else "no_matches"
    return ExactSearchResult(
        hits_by_path=hits_by_path,
        reason=reason,
        timed_out=False,
        returncode=int(returncode),
        elapsed_ms=float(elapsed_ms),
        stderr=str(stderr or ""),
    )


def score_exact_search_hits(*, hits_by_path: dict[str, int]) -> dict[str, float]:
    if not hits_by_path:
        return {}
    max_hits = max(int(value) for value in hits_by_path.values() if int(value) > 0)
    if max_hits <= 0:
        return {path: 0.0 for path in hits_by_path}

    denom = math.log1p(float(max_hits))
    if denom <= 0:
        return {path: 0.0 for path in hits_by_path}

    scored: dict[str, float] = {}
    for path, hits in hits_by_path.items():
        value = max(0, int(hits))
        scored[path] = min(1.0, math.log1p(float(value)) / denom)
    return scored


__all__ = [
    "ExactSearchResult",
    "run_exact_search_ripgrep",
    "score_exact_search_hits",
    "tokenize_query_for_exact_search",
]

