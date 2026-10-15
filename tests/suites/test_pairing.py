"""Tests for the balanced pairing: its rule on hand-built tasks and its invariants over the Workspace tasks."""

from collections import Counter

from mcp_ipi.suites import Task, TaskDifficulty, balanced_pairs
from mcp_ipi.suites.workspace import WORKSPACE

PAIRS = balanced_pairs(WORKSPACE.user_tasks, WORKSPACE.injection_tasks)


def test_each_user_task_is_paired_once_with_each_target_domain():
    assert len(PAIRS) == 250
    assert Counter((user_task.id, injection_task.domain) for user_task, injection_task in PAIRS) == {
        (user_task.id, domain.name): 1 for user_task in WORKSPACE.user_tasks for domain in WORKSPACE.domains
    }


def test_each_injection_task_is_used_10_times():
    assert Counter(injection_task.id for _, injection_task in PAIRS) == {
        injection_task.id: 10 for injection_task in WORKSPACE.injection_tasks
    }


def test_each_source_and_target_domain_combination_has_10_pairs():
    names = [domain.name for domain in WORKSPACE.domains]

    assert Counter((user_task.domain, injection_task.domain) for user_task, injection_task in PAIRS) == {
        (source, target): 10 for source in names for target in names
    }


def test_the_kth_user_task_of_a_domain_gets_injection_task_k_mod_5():
    pairs = {(user_task.id, injection_task.domain): injection_task.id for user_task, injection_task in PAIRS}

    assert pairs["email_user_task_0", "email"] == "email_injection_task_0"
    assert pairs["email_user_task_5", "email"] == "email_injection_task_0"
    assert pairs["calendar_user_task_7", "web"] == "web_injection_task_2"


def make_task(task_id: str, domain: str) -> Task:
    return Task(
        id=task_id,
        prompt="Do it.",
        domain=domain,
        difficulty=TaskDifficulty.EASY,
        ground_truth_output="",
        ground_truth=list,
        check=lambda model_output, pre_environment, post_environment: True,
    )


def test_k_counts_within_the_source_domain_and_wraps_at_each_target_domains_size():
    user_tasks = [make_task(task_id, task_id[0]) for task_id in ("a0", "b0", "a1", "a2")]
    injection_tasks = [make_task(task_id, task_id[1]) for task_id in ("ia0", "ia1", "ib0", "ib1", "ib2")]

    assert [(u.id, i.id) for u, i in balanced_pairs(user_tasks, injection_tasks)] == [
        ("a0", "ia0"),
        ("a0", "ib0"),
        ("b0", "ia0"),
        ("b0", "ib0"),
        ("a1", "ia1"),
        ("a1", "ib1"),
        ("a2", "ia0"),
        ("a2", "ib2"),
    ]
