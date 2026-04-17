from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

LONG_TERM_OBSERVATION_SCHEMA_VERSION = "long_term_observation_v1"
LONG_TERM_FACT_SCHEMA_VERSION = "long_term_fact_v1"
LONG_TERM_ABSTRACTION_LEVELS = ("abstract", "overview", "detail")
LONG_TERM_FRESHNESS_STATES = ("fresh", "stale", "unknown")
LONG_TERM_CONTRADICTION_STATES = ("consistent", "contradicted", "unknown")


def _normalize_required_text(*, value: Any, context: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{context} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{context} cannot be empty")
    return normalized


def _normalize_optional_text(*, value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _normalize_timestamp(*, value: Any, context: str) -> str:
    normalized = _normalize_required_text(value=value, context=context)
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{context} must be an ISO-8601 timestamp") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _normalize_payload_mapping(*, value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a mapping")
    return dict(value)


def _normalize_confidence(*, value: Any) -> float:
    try:
        normalized = float(value)
    except Exception as exc:
        raise ValueError("confidence must be a float") from exc
    if normalized < 0.0:
        return 0.0
    if normalized > 1.0:
        return 1.0
    return float(normalized)


def _normalize_positive_int(*, value: Any, default: int = 1) -> int:
    try:
        normalized = int(value)
    except Exception:
        normalized = int(default)
    return max(1, normalized)


def _normalize_enum_text(
    *,
    value: Any,
    allowed: tuple[str, ...],
    default: str,
) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in allowed:
        return normalized
    return default


def _normalize_memory_metadata(
    *,
    entry_kind: str,
    metadata: dict[str, Any] | None,
    reference_timestamp: str,
) -> dict[str, Any]:
    normalized = dict(metadata) if isinstance(metadata, dict) else {}
    default_abstraction = "abstract" if entry_kind == "observation" else "detail"
    normalized["abstraction_level"] = _normalize_enum_text(
        value=normalized.get("abstraction_level"),
        allowed=LONG_TERM_ABSTRACTION_LEVELS,
        default=default_abstraction,
    )
    normalized["support_count"] = _normalize_positive_int(
        value=normalized.get("support_count"),
        default=1,
    )
    normalized["freshness_state"] = _normalize_enum_text(
        value=normalized.get("freshness_state"),
        allowed=LONG_TERM_FRESHNESS_STATES,
        default="unknown",
    )
    normalized["contradiction_state"] = _normalize_enum_text(
        value=normalized.get("contradiction_state"),
        allowed=LONG_TERM_CONTRADICTION_STATES,
        default="unknown",
    )
    last_confirmed_at = str(normalized.get("last_confirmed_at") or "").strip()
    if last_confirmed_at:
        normalized["last_confirmed_at"] = _normalize_timestamp(
            value=last_confirmed_at,
            context="last_confirmed_at",
        )
    elif reference_timestamp and normalized["freshness_state"] != "unknown":
        normalized["last_confirmed_at"] = reference_timestamp
    else:
        normalized["last_confirmed_at"] = ""
    return normalized


@dataclass(frozen=True, slots=True)
class LongTermObservationContractV1:
    observation_id: str
    kind: str
    repo: str
    root: str
    namespace: str
    user_id: str
    profile_key: str
    query: str
    payload: dict[str, Any]
    observed_at: str
    as_of: str
    source_run_id: str
    severity: str
    status: str
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": LONG_TERM_OBSERVATION_SCHEMA_VERSION,
            "id": self.observation_id,
            "kind": self.kind,
            "repo": self.repo,
            "root": self.root,
            "namespace": self.namespace,
            "user_id": self.user_id,
            "profile_key": self.profile_key,
            "query": self.query,
            "payload": dict(self.payload),
            "observed_at": self.observed_at,
            "as_of": self.as_of,
            "source_run_id": self.source_run_id,
            "severity": self.severity,
            "status": self.status,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class LongTermFactContractV1:
    fact_id: str
    fact_type: str
    subject: str
    predicate: str
    object_value: str
    repo: str
    root: str
    namespace: str
    user_id: str
    profile_key: str
    as_of: str
    confidence: float
    valid_from: str
    valid_to: str
    superseded_by: str
    derived_from_observation_id: str
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": LONG_TERM_FACT_SCHEMA_VERSION,
            "id": self.fact_id,
            "fact_type": self.fact_type,
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object_value,
            "repo": self.repo,
            "root": self.root,
            "namespace": self.namespace,
            "user_id": self.user_id,
            "profile_key": self.profile_key,
            "as_of": self.as_of,
            "confidence": self.confidence,
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
            "superseded_by": self.superseded_by,
            "derived_from_observation_id": self.derived_from_observation_id,
            "metadata": dict(self.metadata),
        }


def build_long_term_observation_contract_v1(
    *,
    kind: str,
    repo: str,
    payload: dict[str, Any],
    observed_at: str,
    as_of: str,
    observation_id: str | None = None,
    root: str = "",
    namespace: str = "",
    user_id: str = "",
    profile_key: str = "",
    query: str = "",
    source_run_id: str = "",
    severity: str = "info",
    status: str = "observed",
    metadata: dict[str, Any] | None = None,
) -> LongTermObservationContractV1:
    normalized_observed_at = _normalize_timestamp(value=observed_at, context="observed_at")
    normalized_as_of = _normalize_timestamp(value=as_of, context="as_of")
    return LongTermObservationContractV1(
        observation_id=_normalize_optional_text(value=observation_id) or str(uuid4()),
        kind=_normalize_required_text(value=kind, context="kind"),
        repo=_normalize_required_text(value=repo, context="repo"),
        root=_normalize_optional_text(value=root),
        namespace=_normalize_optional_text(value=namespace),
        user_id=_normalize_optional_text(value=user_id),
        profile_key=_normalize_optional_text(value=profile_key),
        query=_normalize_optional_text(value=query),
        payload=_normalize_payload_mapping(value=payload, context="payload"),
        observed_at=normalized_observed_at,
        as_of=normalized_as_of,
        source_run_id=_normalize_optional_text(value=source_run_id),
        severity=_normalize_optional_text(value=severity, default="info") or "info",
        status=_normalize_optional_text(value=status, default="observed") or "observed",
        metadata=_normalize_memory_metadata(
            entry_kind="observation",
            metadata=dict(metadata) if isinstance(metadata, dict) else {},
            reference_timestamp=normalized_observed_at or normalized_as_of,
        ),
    )


def build_long_term_fact_contract_v1(
    *,
    fact_type: str,
    subject: str,
    predicate: str,
    object_value: str,
    repo: str,
    as_of: str,
    derived_from_observation_id: str,
    fact_id: str | None = None,
    root: str = "",
    namespace: str = "",
    user_id: str = "",
    profile_key: str = "",
    confidence: float = 1.0,
    valid_from: str = "",
    valid_to: str = "",
    superseded_by: str = "",
    metadata: dict[str, Any] | None = None,
) -> LongTermFactContractV1:
    normalized_as_of = _normalize_timestamp(value=as_of, context="as_of")
    normalized_valid_from = (
        _normalize_timestamp(value=valid_from, context="valid_from")
        if str(valid_from or "").strip()
        else ""
    )
    normalized_valid_to = (
        _normalize_timestamp(value=valid_to, context="valid_to")
        if str(valid_to or "").strip()
        else ""
    )
    reference_timestamp = normalized_valid_from or normalized_as_of
    return LongTermFactContractV1(
        fact_id=_normalize_optional_text(value=fact_id) or str(uuid4()),
        fact_type=_normalize_required_text(value=fact_type, context="fact_type"),
        subject=_normalize_required_text(value=subject, context="subject"),
        predicate=_normalize_required_text(value=predicate, context="predicate"),
        object_value=_normalize_required_text(value=object_value, context="object"),
        repo=_normalize_required_text(value=repo, context="repo"),
        root=_normalize_optional_text(value=root),
        namespace=_normalize_optional_text(value=namespace),
        user_id=_normalize_optional_text(value=user_id),
        profile_key=_normalize_optional_text(value=profile_key),
        as_of=normalized_as_of,
        confidence=_normalize_confidence(value=confidence),
        valid_from=normalized_valid_from,
        valid_to=normalized_valid_to,
        superseded_by=_normalize_optional_text(value=superseded_by),
        derived_from_observation_id=_normalize_required_text(
            value=derived_from_observation_id,
            context="derived_from_observation_id",
        ),
        metadata=_normalize_memory_metadata(
            entry_kind="fact",
            metadata=dict(metadata) if isinstance(metadata, dict) else {},
            reference_timestamp=reference_timestamp,
        ),
    )


def _validate_contract_payload(
    *,
    contract: LongTermObservationContractV1 | LongTermFactContractV1 | dict[str, Any],
    expected_schema_version: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = (
        contract.as_dict()
        if isinstance(contract, (LongTermObservationContractV1, LongTermFactContractV1))
        else contract
    )
    if not isinstance(payload, dict):
        raise ValueError("contract must be a mapping or supported contract object")

    violation_details: list[dict[str, Any]] = []
    if str(payload.get("schema_version") or "").strip() != expected_schema_version:
        violation_details.append(
            {
                "code": "schema_version_invalid",
                "severity": "error",
                "field": "schema_version",
                "message": f"schema_version must match {expected_schema_version}",
                "context": {},
            }
        )
    return payload, violation_details


def validate_long_term_observation_contract_v1(
    *,
    contract: LongTermObservationContractV1 | dict[str, Any],
    fail_closed: bool = True,
) -> dict[str, Any]:
    payload, violation_details = _validate_contract_payload(
        contract=contract,
        expected_schema_version=LONG_TERM_OBSERVATION_SCHEMA_VERSION,
    )
    try:
        normalized = build_long_term_observation_contract_v1(
            observation_id=payload.get("id"),
            kind=_normalize_required_text(value=payload.get("kind"), context="kind"),
            repo=_normalize_required_text(value=payload.get("repo"), context="repo"),
            root=str(payload.get("root") or ""),
            namespace=str(payload.get("namespace") or ""),
            user_id=str(payload.get("user_id") or ""),
            profile_key=str(payload.get("profile_key") or ""),
            query=str(payload.get("query") or ""),
            payload=_normalize_payload_mapping(
                value=payload.get("payload"),
                context="payload",
            ),
            observed_at=_normalize_timestamp(
                value=payload.get("observed_at"),
                context="observed_at",
            ),
            as_of=_normalize_timestamp(value=payload.get("as_of"), context="as_of"),
            source_run_id=str(payload.get("source_run_id") or ""),
            severity=str(payload.get("severity") or "info"),
            status=str(payload.get("status") or "observed"),
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        )
    except ValueError as exc:
        violation_details.append(
            {
                "code": "observation_contract_invalid",
                "severity": "error",
                "field": "contract",
                "message": str(exc),
                "context": {},
            }
        )
        normalized = None
    return {
        "ok": not violation_details,
        "schema_version": LONG_TERM_OBSERVATION_SCHEMA_VERSION,
        "normalized_contract": normalized.as_dict() if normalized is not None else None,
        "violation_count": len(violation_details),
        "violation_details": violation_details,
        "fail_closed": bool(fail_closed),
    }


def validate_long_term_fact_contract_v1(
    *,
    contract: LongTermFactContractV1 | dict[str, Any],
    fail_closed: bool = True,
) -> dict[str, Any]:
    payload, violation_details = _validate_contract_payload(
        contract=contract,
        expected_schema_version=LONG_TERM_FACT_SCHEMA_VERSION,
    )
    try:
        normalized = build_long_term_fact_contract_v1(
            fact_id=payload.get("id"),
            fact_type=_normalize_required_text(
                value=payload.get("fact_type"),
                context="fact_type",
            ),
            subject=_normalize_required_text(value=payload.get("subject"), context="subject"),
            predicate=_normalize_required_text(
                value=payload.get("predicate"),
                context="predicate",
            ),
            object_value=_normalize_required_text(
                value=payload.get("object"),
                context="object",
            ),
            repo=_normalize_required_text(value=payload.get("repo"), context="repo"),
            root=str(payload.get("root") or ""),
            namespace=str(payload.get("namespace") or ""),
            user_id=str(payload.get("user_id") or ""),
            profile_key=str(payload.get("profile_key") or ""),
            as_of=_normalize_timestamp(value=payload.get("as_of"), context="as_of"),
            confidence=payload.get("confidence", 1.0),
            valid_from=str(payload.get("valid_from") or ""),
            valid_to=str(payload.get("valid_to") or ""),
            superseded_by=str(payload.get("superseded_by") or ""),
            derived_from_observation_id=_normalize_required_text(
                value=payload.get("derived_from_observation_id"),
                context="derived_from_observation_id",
            ),
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        )
    except ValueError as exc:
        violation_details.append(
            {
                "code": "fact_contract_invalid",
                "severity": "error",
                "field": "contract",
                "message": str(exc),
                "context": {},
            }
        )
        normalized = None
    return {
        "ok": not violation_details,
        "schema_version": LONG_TERM_FACT_SCHEMA_VERSION,
        "normalized_contract": normalized.as_dict() if normalized is not None else None,
        "violation_count": len(violation_details),
        "violation_details": violation_details,
        "fail_closed": bool(fail_closed),
    }


__all__ = [
    "LONG_TERM_ABSTRACTION_LEVELS",
    "LONG_TERM_CONTRADICTION_STATES",
    "LONG_TERM_FACT_SCHEMA_VERSION",
    "LONG_TERM_FRESHNESS_STATES",
    "LONG_TERM_OBSERVATION_SCHEMA_VERSION",
    "LongTermFactContractV1",
    "LongTermObservationContractV1",
    "build_long_term_fact_contract_v1",
    "build_long_term_observation_contract_v1",
    "validate_long_term_fact_contract_v1",
    "validate_long_term_observation_contract_v1",
]
