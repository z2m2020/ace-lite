"""Protocol placeholders for future team memory synchronization."""

from __future__ import annotations

from typing import Any, Protocol, TypedDict


class TeamFact(TypedDict, total=False):
    handle: str
    content: str
    namespace: str
    updated_at: str
    metadata: dict[str, Any]


class TeamSyncBackend(Protocol):
    """Abstract sync backend for cross-user memory sharing.

    Current codebase does not call this protocol at runtime; it is a reserved
    extension point for future team-shared memory workflows.
    """

    def push(self, facts: list[TeamFact], container_tag: str) -> None: ...

    def pull(self, container_tag: str) -> list[TeamFact]: ...

    def resolve_conflicts(
        self,
        *,
        local: list[TeamFact],
        remote: list[TeamFact],
    ) -> list[TeamFact]: ...
