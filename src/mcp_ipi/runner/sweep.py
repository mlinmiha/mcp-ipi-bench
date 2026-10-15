"""Sweeps: a sweep file describing a whole experiment (`Sweep`), its expansion into run specs per run type
(`expand_sweep`), the dry run's counts (`format_dry_run`) and the runs (`sweep_runs`)."""

import asyncio
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from mcp_ipi.agent import LLM
from mcp_ipi.attacks import ATTACKS
from mcp_ipi.defenses import DEFENSES
from mcp_ipi.environment import load_yaml
from mcp_ipi.suites import Suite

from .run_file import RunResult, should_run
from .runner import MODEL_NAMES, MODEL_PROVIDERS, RunSpec, run, run_specs

type RunTypeName = Literal["utility", "security", "injection_task_checks", "subset_validation"]

RUN_TYPES: dict[RunTypeName, str] = {
    "utility": "utility",
    "security": "security",
    "injection_task_checks": "injection checks",
    "subset_validation": "subset validation",
}
"""The dry run's label per run type, in run order."""


class RunType(BaseModel):
    """A run type's settings: lists that replace the sweep's for this run type, and its pairs.

    `pairs` applies to `security` and `subset_validation` only.
    """

    models: list[str] | None = None
    defenses: list[str] | None = None
    attacks: list[str] | None = None
    pairs: Literal["subset", "full"] = "subset"


class Sweep(BaseModel):
    """A sweep file: a whole experiment over one suite.

    Attributes:
        suite: A key of `SUITES`.
        logdir: Where the run files are written.
        temperature: The sampling temperature of every model.
        models: OpenRouter IDs, keys of `MODEL_NAMES`.
        defenses: Keys of `DEFENSES`.
        attacks: Keys of `ATTACKS`.
        user_tasks: User task IDs; `None` for every user task of the suite.
        injection_tasks: Injection task IDs; `None` for every injection task of the suite.
        run_types: The run types to do and their settings; an absent run type is not done.
        concurrency: The runs in flight at once per provider, a model's OpenRouter ID up to the first `/`; the models
            of a provider without a key share the `openrouter` limit, 1 if that key is absent.
    """

    suite: str
    logdir: Path
    temperature: float
    models: list[str]
    defenses: list[str]
    attacks: list[str]
    user_tasks: list[str] | None = None
    injection_tasks: list[str] | None = None
    run_types: dict[RunTypeName, RunType]
    concurrency: dict[str, int] = {}


def load_sweep(path: Path) -> Sweep:
    """Load a sweep file."""
    return Sweep.model_validate(load_yaml(path))


def expand_sweep[E: BaseModel](suite: Suite[E], sweep: Sweep) -> dict[RunTypeName, list[RunSpec[E]]]:
    """Return the run specs of each run type in the sweep, in the order of `RUN_TYPES`, making no model call.

    Within a run type the specs go models, defenses and attacks in file order, then the tasks in `run_specs`'s order:
    - utility: each model with each defense, without an attack;
    - security and subset validation: each model with each defense and each attack, over the run type's pairs;
    - injection task checks: each model with defense `none` and no attack.

    Raises:
        KeyError: A model, defense, attack or task ID is unknown.
    """
    user_tasks = (
        suite.user_tasks
        if sweep.user_tasks is None
        else [suite.get_user_task_by_id(task_id) for task_id in sweep.user_tasks]
    )
    injection_tasks = (
        suite.injection_tasks
        if sweep.injection_tasks is None
        else [suite.get_injection_task_by_id(task_id) for task_id in sweep.injection_tasks]
    )
    expanded: dict[RunTypeName, list[RunSpec[E]]] = {}
    for name in RUN_TYPES:
        if name not in sweep.run_types:
            continue
        run_type = sweep.run_types[name]
        models = sweep.models if run_type.models is None else run_type.models
        defenses = sweep.defenses if run_type.defenses is None else run_type.defenses
        attacks = [ATTACKS[attack] for attack in (sweep.attacks if run_type.attacks is None else run_type.attacks)]
        # An unknown model or defense raises `KeyError` here, whatever the run type.
        for model in models:
            MODEL_NAMES[model]
        for defense in defenses:
            DEFENSES[defense]
        if name == "utility":
            configurations = [(model, defense, None) for model in models for defense in defenses]
        elif name == "injection_task_checks":
            configurations = [(model, "none", None) for model in models]
        else:
            configurations = [
                (model, defense, attack) for model in models for defense in defenses for attack in attacks
            ]
        expanded[name] = [
            spec
            for model, defense, attack in configurations
            for spec in run_specs(
                suite,
                model=model,
                defense=defense,
                attack=attack,
                user_tasks=user_tasks,
                injection_tasks=injection_tasks,
                pairs=run_type.pairs,
                injection_task_checks=name == "injection_task_checks",
            )
        ]
    return expanded


def format_dry_run[E: BaseModel](expanded: dict[RunTypeName, list[RunSpec[E]]], logdir: Path, suite_name: str) -> str:
    """Return one line per run type and a total line, each with its runs in total, done and still to do.

    A run is done when its run file exists without an error. The counts are per run type, so a run file shared by two
    run types counts under both.
    """
    lines = []
    total = done = 0
    for name, specs in expanded.items():
        run_type_done = sum(not should_run(spec.path(logdir, suite_name), False) for spec in specs)
        lines.append(count_line(RUN_TYPES[name], len(specs), run_type_done))
        total, done = total + len(specs), done + run_type_done
    lines.append(count_line("total", total, done))
    return "\n".join(lines)


def count_line(label: str, total: int, done: int) -> str:
    """Return a dry run's line: the label, then `total=`, `done=` and `todo=` in aligned columns."""
    return f"{label:<19}{f'total={total}':<13}{f'done={done}':<13}todo={total - done}"


async def sweep_runs[E: BaseModel](
    suite: Suite[E],
    specs: Sequence[RunSpec[E]],
    *,
    temperature: float,
    logdir: Path,
    force_rerun: bool = False,
    concurrency: Mapping[str, int] = {},
) -> list[RunResult]:
    """Do each spec's run with `run`, in one worker pool per provider with the limits in `concurrency`.

    A spec whose run file path an earlier spec already has is dropped, so a run shared by two run types is done once,
    also with `force_rerun`. A model is in its provider's pool if `concurrency` has that provider (see `pool`), and in
    the shared `openrouter` pool otherwise. A pool with limit N has N workers, each owning one `LLM(model, temperature)`
    per model of the pool, pinned to the model's provider in `MODEL_PROVIDERS`, so a model object does one run at a
    time and `run` counts each run's usage and providers alone. Each worker takes the next spec of its pool not yet
    taken; the pools run at once.

    Lines are printed as runs finish; the results come back in spec order. An exception that escapes a run cancels the
    other runs and propagates, unwrapped from the task group. Every model's client is closed at the end, also then.
    Without `concurrency`, the runs go one after another in order.
    """
    unique: dict[Path, RunSpec[E]] = {}
    for spec in specs:
        unique.setdefault(spec.path(logdir, suite.name), spec)
    pools: dict[str, list[tuple[int, RunSpec[E]]]] = {}
    for index, spec in enumerate(unique.values()):
        pools.setdefault(pool(spec.model, concurrency), []).append((index, spec))
    workers: list[tuple[Iterator[tuple[int, RunSpec[E]]], dict[str, LLM]]] = []
    for name, pool_specs in pools.items():
        next_specs = iter(pool_specs)
        models = dict.fromkeys(spec.model for _, spec in pool_specs)
        for _ in range(concurrency.get(name, 1)):
            workers.append(
                (next_specs, {model: LLM(model, temperature, provider=MODEL_PROVIDERS[model]) for model in models})
            )
    results: dict[int, RunResult] = {}

    async def worker(next_specs: Iterator[tuple[int, RunSpec[E]]], llms: dict[str, LLM]) -> None:
        for index, spec in next_specs:
            results[index] = await run(
                suite, llms[spec.model], spec, temperature=temperature, logdir=logdir, force_rerun=force_rerun
            )

    try:
        async with asyncio.TaskGroup() as group:
            for next_specs, llms in workers:
                group.create_task(worker(next_specs, llms))
    except ExceptionGroup as error:
        raise error.exceptions[0] from None
    finally:
        for _, llms in workers:
            for llm in llms.values():
                await llm.client.close()
    return [results[index] for index in range(len(unique))]


def pool(model: str, concurrency: Mapping[str, int]) -> str:
    """Return the pool of a model: its provider, its OpenRouter ID up to the first `/`, if that is a key of
    `concurrency`, and `openrouter` otherwise."""
    provider = model.split("/")[0]
    return provider if provider in concurrency else "openrouter"
