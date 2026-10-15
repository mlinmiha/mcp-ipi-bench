"""Covered pairs: the pairs each action-level defense covers by design, from the ground truths of a suite's tasks."""

from collections.abc import Callable

from mcp_ipi.suites import Suite, Task


def tool_filter_covers(suite: Suite, user_task: Task, injection_task: Task) -> bool:
    """Whether the injection task's ground truth calls a tool that the user task's ground truth does not call, so
    that a filter that keeps only the user task's tools removes it."""
    user_tools = {call.tool for call in user_task.ground_truth()}
    return any(call.tool not in user_tools for call in injection_task.ground_truth())


def security_policy_covers(suite: Suite, user_task: Task, injection_task: Task) -> bool:
    """Whether the suite's security policy blocks a call of the injection task's ground truth."""
    return any(suite.security_policy(call.tool, call.args) for call in injection_task.ground_truth())


COVERS: dict[str, Callable[[Suite, Task, Task], bool]] = {
    "tool-filter": tool_filter_covers,
    "security-policy": security_policy_covers,
}
"""Each action-level defense with its rule `(suite, user task, injection task) -> whether it covers the pair`. No
model and no run file is read, so the covered pairs are known before any run."""
