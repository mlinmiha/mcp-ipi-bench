"""Tasks: one representation for user tasks and injection tasks, with their ground truth as tool calls."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel


class TaskDifficulty(Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass(frozen=True)
class ToolCall:
    """One tool call: the tool's name and its keyword arguments, without the component."""

    tool: str
    args: dict[str, Any]


@dataclass(frozen=True)
class Task[E: BaseModel]:
    """A user task or an injection task; which one is decided by the suite tuple it is in.

    Attributes:
        id: `user_task_N` or `injection_task_N`.
        prompt: The user task's prompt, or the injection task's goal.
        domain: Name of the domain the user task is about, or the injection task's target domain.
        difficulty: How hard the task is.
        ground_truth_output: The expected final answer, or `""` when the task asks for none.
        ground_truth: Returns the tool calls of a reference solution.
        check: Called as `check(model_output, pre_environment, post_environment)`; `True` when the task was done.
            For a user task this is its utility, for an injection task its security (`True` is bad).
    """

    id: str
    prompt: str
    domain: str
    difficulty: TaskDifficulty
    ground_truth_output: str
    ground_truth: Callable[[], list[ToolCall]]
    check: Callable[[str, E, E], bool]
