"""Tests for `run_specs`: the run specs of one run type, over the real Workspace suite."""

import pytest

from mcp_ipi.attacks import DIRECT_INSTRUCTION
from mcp_ipi.runner import RunSpec, run_specs
from mcp_ipi.suites.workspace import WORKSPACE, WorkspaceEnvironment

MODEL = "openai/gpt-5.4-mini"
USER_TASKS = [WORKSPACE.get_user_task_by_id(f"email_user_task_{n}") for n in (0, 1)]
INJECTION_TASKS = [
    WORKSPACE.get_injection_task_by_id(task_id)
    for task_id in ["email_injection_task_2", "web_injection_task_0", "email_injection_task_0"]
]


def spec_keys(specs: list[RunSpec[WorkspaceEnvironment]]) -> list[tuple[str, str | None, str | None]]:
    return [
        (
            spec.task.id,
            spec.injection_task.id if spec.injection_task else None,
            spec.attack.name if spec.attack else None,
        )
        for spec in specs
    ]


def test_utility_specs_are_each_user_task_without_an_attack():
    specs = run_specs(
        WORKSPACE, model=MODEL, defense="spotlighting", user_tasks=USER_TASKS, injection_tasks=INJECTION_TASKS
    )

    assert spec_keys(specs) == [("email_user_task_0", None, None), ("email_user_task_1", None, None)]
    assert {(spec.model, spec.defense) for spec in specs} == {(MODEL, "spotlighting")}


def test_injection_task_check_specs_have_the_injection_task_as_their_task():
    specs = run_specs(
        WORKSPACE,
        model=MODEL,
        defense="none",
        user_tasks=USER_TASKS,
        injection_tasks=INJECTION_TASKS,
        injection_task_checks=True,
    )

    assert spec_keys(specs) == [
        ("email_injection_task_2", None, None),
        ("web_injection_task_0", None, None),
        ("email_injection_task_0", None, None),
    ]


def test_subset_security_specs_are_only_the_selected_balanced_pairs():
    specs = run_specs(
        WORKSPACE,
        model=MODEL,
        defense="none",
        attack=DIRECT_INSTRUCTION,
        user_tasks=USER_TASKS,
        injection_tasks=INJECTION_TASKS,
    )

    assert spec_keys(specs) == [
        ("email_user_task_0", "web_injection_task_0", "direct-instruction"),
        ("email_user_task_0", "email_injection_task_0", "direct-instruction"),
    ]


def test_full_security_specs_are_every_selected_pair_user_task_first():
    specs = run_specs(
        WORKSPACE,
        model=MODEL,
        defense="none",
        attack=DIRECT_INSTRUCTION,
        user_tasks=USER_TASKS,
        injection_tasks=INJECTION_TASKS,
        pairs="full",
    )

    assert spec_keys(specs) == [
        (user_task.id, injection_task.id, "direct-instruction")
        for user_task in USER_TASKS
        for injection_task in INJECTION_TASKS
    ]


def test_a_security_run_with_an_unknown_model_raises_key_error():
    with pytest.raises(KeyError):
        run_specs(
            WORKSPACE,
            model="acme/unknown-model",
            defense="none",
            attack=DIRECT_INSTRUCTION,
            user_tasks=USER_TASKS,
            injection_tasks=INJECTION_TASKS,
        )
