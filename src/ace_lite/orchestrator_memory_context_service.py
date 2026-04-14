from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ace_lite.feedback_store import SelectionFeedbackStore
from ace_lite.memory.local_notes import append_capture_note
from ace_lite.memory_long_term import LongTermMemoryCaptureService
from ace_lite.pipeline.types import StageContext
from ace_lite.preference_capture_store import DurablePreferenceCaptureStore
from ace_lite.profile_store import ProfileStore

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class MemoryContextService:
    config: Any
    long_term_capture_service: LongTermMemoryCaptureService | None
    durable_stats_session_id: str

    @staticmethod
    def normalize_namespace_component(*, value: str, fallback: str) -> str:
        normalized = re.sub(r"[^a-z0-9._-]+", "-", str(value or "").strip().lower())
        normalized = normalized.strip("-")
        return normalized or fallback

    @staticmethod
    def _resolve_local_path(*, root: str, configured_path: str) -> Path:
        path = Path(str(configured_path or "").strip()).expanduser()
        if path.is_absolute():
            return path
        return Path(root) / path

    def resolve_memory_namespace(
        self,
        *,
        repo: str,
        root: str,
    ) -> tuple[str | None, str, str]:
        explicit_tag = self.config.memory.namespace.container_tag
        if explicit_tag:
            return explicit_tag, "explicit", "explicit"

        mode = self.config.memory.namespace.auto_tag_mode
        if mode == "repo":
            repo_name = str(repo or "").strip() or Path(root or ".").name
            return (
                f"repo:{self.normalize_namespace_component(value=repo_name, fallback='repo')}",
                "repo",
                "auto",
            )
        if mode == "user":
            import getpass

            try:
                user_name = getpass.getuser()
            except Exception:
                user_name = ""
            return (
                f"user:{self.normalize_namespace_component(value=user_name, fallback='local')}",
                "user",
                "auto",
            )
        if mode == "global":
            return "global", "global", "auto"
        return None, "disabled", "disabled"

    def resolve_profile_store(self, *, root: str) -> ProfileStore:
        return ProfileStore(
            path=self._resolve_local_path(
                root=root,
                configured_path=str(self.config.memory.profile.path or ""),
            ),
            expiry_enabled=self.config.memory.profile.expiry_enabled,
            ttl_days=self.config.memory.profile.ttl_days,
            max_age_days=self.config.memory.profile.max_age_days,
        )

    def resolve_capture_notes_path(self, *, root: str) -> Path:
        return self._resolve_local_path(
            root=root,
            configured_path=str(self.config.memory.capture.notes_path or ""),
        )

    def resolve_validation_preference_capture_store(
        self,
        *,
        root: str,
    ) -> DurablePreferenceCaptureStore | None:
        if not self.config.memory.feedback.enabled:
            return None
        feedback_store = SelectionFeedbackStore(
            profile_path=self._resolve_local_path(
                root=root,
                configured_path=str(self.config.memory.feedback.path or ""),
            ),
            max_entries=self.config.memory.feedback.max_entries,
        )
        return DurablePreferenceCaptureStore(db_path=feedback_store.path)

    def capture_memory_signal(
        self,
        *,
        query: str,
        repo: str,
        root: str,
        namespace: str | None,
        matched_keywords: list[str],
    ) -> dict[str, Any]:
        captured_items = 0
        warnings: list[str] = []
        notes_pruned_expired_count = 0

        try:
            store = self.resolve_profile_store(root=root)
            store.add_recent_context(query=query, repo=repo)
            captured_items += 1
        except Exception as exc:
            warnings.append(f"profile_recent_context_error:{exc.__class__.__name__}")

        try:
            notes_path = self.resolve_capture_notes_path(root=root)
            notes_captured_items, notes_pruned_expired_count = append_capture_note(
                notes_path=notes_path,
                query=query,
                repo=repo,
                namespace=namespace,
                matched_keywords=matched_keywords,
                expiry_enabled=self.config.memory.notes.expiry_enabled,
                ttl_days=self.config.memory.notes.ttl_days,
                max_age_days=self.config.memory.notes.max_age_days,
            )
            captured_items += notes_captured_items
        except Exception as exc:
            warnings.append(f"notes_append_error:{exc.__class__.__name__}")

        return {
            "enabled": True,
            "triggered": bool(matched_keywords),
            "matched_keywords": matched_keywords,
            "captured_items": captured_items,
            "notes_pruned_expired_count": notes_pruned_expired_count,
            "warning": ";".join(warnings) if warnings else None,
        }

    def build_profile_payload(
        self,
        *,
        root: str,
        tokenizer_model: str,
    ) -> dict[str, Any]:
        if not self.config.memory.profile.enabled:
            return {"enabled": False, "facts": [], "selected_count": 0}
        try:
            store = self.resolve_profile_store(root=root)
            return store.build_injection(
                top_n=self.config.memory.profile.top_n,
                token_budget=self.config.memory.profile.token_budget,
                tokenizer_model=tokenizer_model,
            )
        except Exception as exc:
            logger.warning(
                "memory.profile.inject.error",
                extra={"error": str(exc)},
            )
            return {
                "enabled": True,
                "error": str(exc),
                "facts": [],
                "selected_count": 0,
                "selected_est_tokens_total": 0,
            }

    def build_capture_payload(
        self,
        *,
        query: str,
        repo: str,
        root: str,
        namespace: str | None,
        matched_keywords: list[str],
        triggered: bool,
        reason: str,
        query_length: int,
    ) -> dict[str, Any]:
        capture_enabled = bool(self.config.memory.capture.enabled)
        payload: dict[str, Any] = {
            "enabled": capture_enabled,
            "triggered": False,
            "namespace": namespace,
            "matched_keywords": [],
            "captured_items": 0,
            "reason": reason,
            "query_length": query_length,
            "warning": None,
        }
        if capture_enabled and triggered:
            return {
                **payload,
                **self.capture_memory_signal(
                    query=query,
                    repo=repo,
                    root=root,
                    namespace=namespace,
                    matched_keywords=matched_keywords,
                ),
                "reason": reason,
                "query_length": query_length,
            }
        if capture_enabled:
            payload["matched_keywords"] = list(matched_keywords)
        return payload

    def attach_memory_stage_payloads(
        self,
        *,
        payload: dict[str, Any],
        query: str,
        repo: str,
        root: str,
        namespace: str | None,
        matched_keywords: list[str],
        triggered: bool,
        reason: str,
        query_length: int,
        tokenizer_model: str,
    ) -> dict[str, Any]:
        if not self.config.memory.profile.enabled:
            payload["profile"] = {"enabled": False, "facts": [], "selected_count": 0}
        else:
            payload["profile"] = self.build_profile_payload(
                root=root,
                tokenizer_model=tokenizer_model,
            )

        payload["capture"] = self.build_capture_payload(
            query=query,
            repo=repo,
            root=root,
            namespace=namespace,
            matched_keywords=matched_keywords,
            triggered=triggered,
            reason=reason,
            query_length=query_length,
        )
        return payload

    def capture_long_term_stage_observation(
        self,
        *,
        stage_name: str,
        ctx: StageContext,
        stage_payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        if self.long_term_capture_service is None:
            return None
        if stage_name not in {"source_plan", "validation"}:
            return None
        try:
            return self.long_term_capture_service.capture_stage_observation(
                stage_name=stage_name,
                query=ctx.query,
                repo=ctx.repo,
                root=ctx.root,
                profile_key=None,
                source_run_id=self.durable_stats_session_id,
                stage_payload=stage_payload,
            )
        except Exception as exc:
            logger.warning(
                "memory.long_term.capture.error",
                extra={"stage": stage_name, "error": str(exc)},
            )
            return {
                "ok": False,
                "stage": stage_name,
                "reason": f"capture_failed:{exc.__class__.__name__}",
                "message": str(exc),
            }


__all__ = ["MemoryContextService"]
