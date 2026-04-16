"""Builder seams for case-evaluation row and detail payload inputs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from ace_lite.benchmark.case_evaluation_output import build_case_detail_payload
from ace_lite.benchmark.case_evaluation_payload_builder_facade import (
    build_namespace_kwargs,
)
from ace_lite.benchmark.case_evaluation_payload_support import (
    DETAIL_ARGUMENT_NAMES,
    ROW_ARGUMENT_NAMES,
)
from ace_lite.benchmark.case_evaluation_row import build_case_evaluation_row


def build_case_evaluation_row_from_namespace(
    *,
    namespace: Mapping[str, Any],
) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        build_case_evaluation_row(
            **build_namespace_kwargs(namespace=namespace, argument_names=ROW_ARGUMENT_NAMES)
        ),
    )


def build_case_detail_payload_from_namespace(
    *,
    namespace: Mapping[str, Any],
) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        build_case_detail_payload(
            **build_namespace_kwargs(namespace=namespace, argument_names=DETAIL_ARGUMENT_NAMES)
        ),
    )


_ROW_ARGUMENT_NAMES = ROW_ARGUMENT_NAMES
_DETAIL_ARGUMENT_NAMES = DETAIL_ARGUMENT_NAMES

__all__ = [
    "build_case_detail_payload_from_namespace",
    "build_case_evaluation_row_from_namespace",
]
