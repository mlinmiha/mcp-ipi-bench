"""Tests for `load_sweep` and `expand_sweep`: the run specs of small hand-written sweeps over the real Workspace suite."""

from pathlib import Path
from typing import Any

import pytest

from mcp_ipi.attacks import ATTACKS, DIRECT_INSTRUCTION
from mcp_ipi.runner import RunSpec, Sweep, expand_sweep, load_sweep, run_specs
from mcp_ipi.suites.workspace import WORKSPACE, WorkspaceEnvironment

MINI = "openai/gpt-5.4-mini"
DEEPSEEK = "deepseek/deepseek-v4.1-flash"
USER_TASK_IDS = ["email_user_task_0", "email_user_task_1"]
INJECTION_TASK_IDS = ["email_injection_task_2", "web_injection_task_0", "email_injection_task_0"]


def make_sweep(**changes: Any) -> Sweep:
    fields: dict[str, Any] = {
        "suite": "workspace",
        "logdir": "runs",
        "temperature": 0.0,
        "models": [MINI],
        "defenses": ["none"],
        "attacks": ["direct-instruction"],
        "user_tasks": USER_TASK_IDS,
        "injection_tasks": INJECTION_TASK_IDS,
        "run_types": {"utility": {}},
    }
    return Sweep.model_validate(fields | changes)


def spec_keys(specs: list[RunSpec[WorkspaceEnvironment]]) -> list[tuple[str, str, str | None, str, str | None]]:
    return [
        (
            spec.model,
            spec.defense,
            spec.attack.name if spec.attack else None,
            spec.task.id,
            spec.injection_task.id if spec.injection_task else None,
        )
        for spec in specs
    ]


def paths(specs: list[RunSpec[WorkspaceEnvironment]]) -> list[Path]:
    return [spec.path(Path("runs"), WORKSPACE.name) for spec in specs]


def test_run_types_come_in_the_fixed_order_and_only_those_in_the_file():
    sweep = make_sweep(run_types={"subset_validation": {}, "injection_task_checks": {}, "utility": {}})

    assert list(expand_sweep(WORKSPACE, sweep)) == ["utility", "injection_task_checks", "subset_validation"]


def test_an_absent_run_type_gives_nothing():
    assert list(expand_sweep(WORKSPACE, make_sweep(run_types={}))) == []


def test_utility_runs_go_models_then_defenses_then_tasks_without_an_attack():
    sweep = make_sweep(models=[MINI, DEEPSEEK], defenses=["none", "spotlighting"], attacks=["tool-notice"])

    assert spec_keys(expand_sweep(WORKSPACE, sweep)["utility"]) == [
        (model, defense, None, task_id, None)
        for model in [MINI, DEEPSEEK]
        for defense in ["none", "spotlighting"]
        for task_id in USER_TASK_IDS
    ]


def test_security_runs_go_models_then_defenses_then_attacks_then_pairs():
    models, defenses, attacks = [DEEPSEEK, MINI], ["sanitizer", "none"], ["tool-notice", "direct-instruction"]
    sweep = make_sweep(models=models, defenses=defenses, attacks=attacks, run_types={"security": {"pairs": "full"}})

    assert spec_keys(expand_sweep(WORKSPACE, sweep)["security"]) == [
        (model, defense, attack, task_id, injection_task_id)
        for model in models
        for defense in defenses
        for attack in attacks
        for task_id in USER_TASK_IDS
        for injection_task_id in INJECTION_TASK_IDS
    ]


def test_security_runs_default_to_the_subset_narrowed_by_the_task_lists():
    sweep = make_sweep(run_types={"security": {}})

    assert spec_keys(expand_sweep(WORKSPACE, sweep)["security"]) == [
        (MINI, "none", "direct-instruction", "email_user_task_0", "web_injection_task_0"),
        (MINI, "none", "direct-instruction", "email_user_task_0", "email_injection_task_0"),
    ]


def test_without_task_lists_a_run_type_covers_every_task():
    sweep = make_sweep(user_tasks=None, injection_tasks=None, run_types={"security": {}, "injection_task_checks": {}})

    expanded = expand_sweep(WORKSPACE, sweep)

    assert len(expanded["security"]) == 250
    assert len(expanded["injection_task_checks"]) == 25


def test_injection_task_checks_use_the_baseline_without_an_attack_whatever_the_defenses_and_attacks():
    sweep = make_sweep(
        models=[MINI, DEEPSEEK],
        defenses=["spotlighting", "sanitizer"],
        attacks=["tool-notice", "fake-completion"],
        run_types={"injection_task_checks": {}},
    )

    assert spec_keys(expand_sweep(WORKSPACE, sweep)["injection_task_checks"]) == [
        (model, "none", None, task_id, None) for model in [MINI, DEEPSEEK] for task_id in INJECTION_TASK_IDS
    ]


def test_a_run_types_lists_replace_the_top_level_ones_for_that_run_type_only():
    sweep = make_sweep(
        models=[MINI, DEEPSEEK],
        defenses=["none", "spotlighting"],
        attacks=["tool-notice", "fake-completion"],
        run_types={
            "utility": {},
            "subset_validation": {
                "models": [DEEPSEEK],
                "defenses": ["sanitizer"],
                "attacks": ["direct-instruction"],
                "pairs": "full",
            },
        },
    )

    expanded = expand_sweep(WORKSPACE, sweep)

    assert {(model, defense) for model, defense, *_ in spec_keys(expanded["utility"])} == {
        (MINI, "none"),
        (MINI, "spotlighting"),
        (DEEPSEEK, "none"),
        (DEEPSEEK, "spotlighting"),
    }
    assert spec_keys(expanded["subset_validation"]) == [
        (DEEPSEEK, "sanitizer", "direct-instruction", task_id, injection_task_id)
        for task_id in USER_TASK_IDS
        for injection_task_id in INJECTION_TASK_IDS
    ]


def test_a_sweeps_specs_have_the_paths_of_the_shared_spec_building():
    sweep = make_sweep(
        models=[MINI], defenses=["spotlighting"], run_types={"utility": {}, "security": {}, "injection_task_checks": {}}
    )
    user_tasks = [WORKSPACE.get_user_task_by_id(task_id) for task_id in USER_TASK_IDS]
    injection_tasks = [WORKSPACE.get_injection_task_by_id(task_id) for task_id in INJECTION_TASK_IDS]

    def shared(**kwargs: Any) -> list[RunSpec[WorkspaceEnvironment]]:
        return run_specs(WORKSPACE, model=MINI, user_tasks=user_tasks, injection_tasks=injection_tasks, **kwargs)

    expanded = expand_sweep(WORKSPACE, sweep)

    assert paths(expanded["utility"]) == paths(shared(defense="spotlighting"))
    assert paths(expanded["security"]) == paths(shared(defense="spotlighting", attack=DIRECT_INSTRUCTION))
    assert paths(expanded["injection_task_checks"]) == paths(shared(defense="none", injection_task_checks=True))


def test_two_expansions_of_one_file_are_equal(tmp_path: Path):
    path = tmp_path / "sweep.yaml"
    path.write_text(
        "suite: workspace\nlogdir: runs\ntemperature: 0.0\n"
        f"models: [{MINI}, {DEEPSEEK}]\ndefenses: [none, tool-filter]\nattacks: [{', '.join(ATTACKS)}]\n"
        "run_types: {utility: {}, security: {}, injection_task_checks: {}}\n"
        "concurrency: {openai: 16, openrouter: 8}\n"
    )

    def expanded_paths() -> dict[str, list[Path]]:
        return {name: paths(specs) for name, specs in expand_sweep(WORKSPACE, load_sweep(path)).items()}

    assert expanded_paths() == expanded_paths()


@pytest.mark.parametrize(
    "changes",
    [
        {"models": ["acme/unknown-model"]},
        {"defenses": ["firewall"]},
        {"attacks": ["jailbreak"]},
        {"user_tasks": ["email_user_task_99"]},
        {"injection_tasks": ["email_injection_task_99"]},
        {"run_types": {"utility": {"models": ["acme/unknown-model"]}}},
    ],
)
def test_an_unknown_name_raises_key_error(changes: dict[str, Any]):
    with pytest.raises(KeyError):
        expand_sweep(WORKSPACE, make_sweep(**changes))


def test_an_empty_task_list_gives_no_runs():
    sweep = make_sweep(user_tasks=[], run_types={"utility": {}, "injection_task_checks": {}})

    expanded = expand_sweep(WORKSPACE, sweep)

    assert expanded["utility"] == []
    assert len(expanded["injection_task_checks"]) == len(INJECTION_TASK_IDS)


def test_a_run_types_empty_list_replaces_the_top_level_one():
    sweep = make_sweep(run_types={"utility": {"defenses": []}, "security": {}})

    expanded = expand_sweep(WORKSPACE, sweep)

    assert expanded["utility"] == []
    assert len(expanded["security"]) == 2
