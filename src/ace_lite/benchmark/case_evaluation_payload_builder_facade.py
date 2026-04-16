"""Tiny lookup facade for case-evaluation payload builders."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ace_lite.benchmark.case_evaluation_payload_support import (
    lookup_case_evaluation_payload_value,
)


def build_namespace_kwargs(
    *,
    namespace: Mapping[str, Any],
    argument_names: tuple[str, ...],
) -> dict[str, Any]:
    return {key: lookup_case_evaluation_payload_value(namespace, key) for key in argument_names}


__all__ = ["build_namespace_kwargs"]
