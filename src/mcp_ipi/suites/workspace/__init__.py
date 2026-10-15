"""The Workspace suite: email, web, cloud storage, calendar and issue tracking domains over one shared environment."""

from .environment import WorkspaceEnvironment
from .suite import WORKSPACE

__all__ = ["WORKSPACE", "WorkspaceEnvironment"]
