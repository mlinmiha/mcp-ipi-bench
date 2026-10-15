"""Task suites that compose domains, environments and tasks."""

from .check import check_suite
from .pairing import balanced_pairs
from .suite import Policy, Suite
from .task import Task, TaskDifficulty, ToolCall
from .workspace import WORKSPACE

SUITES: dict[str, Suite] = {"workspace": WORKSPACE}
"""Each suite by its name."""

__all__ = ["SUITES", "Policy", "Suite", "Task", "TaskDifficulty", "ToolCall", "balanced_pairs", "check_suite"]
