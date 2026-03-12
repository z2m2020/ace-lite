"""Minimal prompt rendering boundary skeleton."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping

from ace_lite.prompt_rendering.segments import (
    PromptSegment,
    SEGMENT_HASH_ALGORITHM,
    SEGMENT_ORDERING,
    canonicalize_segments,
)

PROMPT_RENDERER_BOUNDARY_VERSION = "prompt_rendering_boundary_v1"


def _render_segment_text(segment: PromptSegment) -> str:
    if segment.heading:
        return f"## {segment.heading}\n{segment.body}".strip()
    return segment.body


def build_render_manifest(
    values: Iterable[PromptSegment | Mapping[str, Any]],
) -> dict[str, Any]:
    ordered = canonicalize_segments(values)
    hashes = [segment.segment_hash for segment in ordered]
    payload = json.dumps(
        hashes,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    prompt_hash = sha256(payload.encode("utf-8")).hexdigest()
    return {
        "boundary_version": PROMPT_RENDERER_BOUNDARY_VERSION,
        "ordering": SEGMENT_ORDERING,
        "hash_algorithm": SEGMENT_HASH_ALGORITHM,
        "segment_count": len(ordered),
        "segment_hashes": hashes,
        "prompt_hash": prompt_hash,
    }


def build_prompt_rendering_boundary() -> dict[str, Any]:
    return {
        "status": "frozen",
        "renderer_module": "ace_lite.prompt_rendering.renderer",
        "segments_module": "ace_lite.prompt_rendering.segments",
        "boundary_version": PROMPT_RENDERER_BOUNDARY_VERSION,
        "ordering": SEGMENT_ORDERING,
        "segment_hash_algorithm": SEGMENT_HASH_ALGORITHM,
    }


@dataclass(frozen=True, slots=True)
class RenderedPrompt:
    text: str
    segments: tuple[PromptSegment, ...]
    prompt_hash: str
    manifest: dict[str, Any]


def render_prompt(
    values: Iterable[PromptSegment | Mapping[str, Any]],
) -> RenderedPrompt:
    ordered = tuple(canonicalize_segments(values))
    manifest = build_render_manifest(ordered)
    text = "\n\n".join(
        block for block in (_render_segment_text(segment) for segment in ordered) if block
    ).strip()
    return RenderedPrompt(
        text=text,
        segments=ordered,
        prompt_hash=str(manifest.get("prompt_hash") or ""),
        manifest=manifest,
    )


__all__ = [
    "PROMPT_RENDERER_BOUNDARY_VERSION",
    "RenderedPrompt",
    "build_prompt_rendering_boundary",
    "build_render_manifest",
    "render_prompt",
]
