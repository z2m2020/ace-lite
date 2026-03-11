"""Team collaboration contracts (protocol-only placeholders)."""

from .filesync import FileBasedTeamSync
from .sync import TeamFact, TeamSyncBackend

__all__ = ["FileBasedTeamSync", "TeamFact", "TeamSyncBackend"]
