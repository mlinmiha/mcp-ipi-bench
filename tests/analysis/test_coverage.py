"""Tests for the covered pairs of the action-level defenses: the pairs of the balanced subset of Workspace that each
covers by design."""

from mcp_ipi.analysis.coverage import COVERS
from mcp_ipi.suites import balanced_pairs
from mcp_ipi.suites.workspace import WORKSPACE

PAIRS = balanced_pairs(WORKSPACE.user_tasks, WORKSPACE.injection_tasks)


def test_the_security_policy_covers_the_120_pairs_of_the_12_injection_tasks_with_a_call_it_blocks():
    covered = [
        injection_task.id
        for user_task, injection_task in PAIRS
        if COVERS["security-policy"](WORKSPACE, user_task, injection_task)
    ]

    assert len(covered) == 120
    assert sorted(set(covered)) == [
        "calendar_injection_task_0",
        "calendar_injection_task_1",
        "calendar_injection_task_4",
        "cloud_storage_injection_task_0",
        "cloud_storage_injection_task_4",
        "email_injection_task_0",
        "email_injection_task_1",
        "email_injection_task_4",
        "issue_tracking_injection_task_0",
        "issue_tracking_injection_task_4",
        "web_injection_task_0",
        "web_injection_task_4",
    ]


def test_the_tool_filter_covers_the_240_pairs_whose_injection_task_calls_a_tool_the_user_task_does_not():
    uncovered = [
        (user_task.id, injection_task.id)
        for user_task, injection_task in PAIRS
        if not COVERS["tool-filter"](WORKSPACE, user_task, injection_task)
    ]

    # In each of these the user task's ground truth calls every tool of the injection task's, e.g. the user task
    # sends an email itself, so a filter that keeps the user task's tools keeps those of the goal.
    assert len(PAIRS) - len(uncovered) == 240
    assert uncovered == [
        ("email_user_task_5", "email_injection_task_0"),
        ("email_user_task_8", "email_injection_task_3"),
        ("web_user_task_8", "web_injection_task_3"),
        ("calendar_user_task_5", "calendar_injection_task_0"),
        ("calendar_user_task_8", "calendar_injection_task_3"),
        ("issue_tracking_user_task_4", "issue_tracking_injection_task_4"),
        ("issue_tracking_user_task_5", "issue_tracking_injection_task_0"),
        ("issue_tracking_user_task_7", "issue_tracking_injection_task_2"),
        ("issue_tracking_user_task_8", "issue_tracking_injection_task_3"),
        ("issue_tracking_user_task_9", "issue_tracking_injection_task_4"),
    ]


def test_the_defenses_with_covered_pairs_are_the_two_action_level_ones_in_the_order_of_the_defenses():
    assert list(COVERS) == ["tool-filter", "security-policy"]
