"""Knowledge package — workspace management and entity extraction."""

from backend.knowledge.workspace_service import WorkspaceNotFound, WorkspaceService

__all__ = ["WorkspaceService", "WorkspaceNotFound"]
