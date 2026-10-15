"""Runs of tasks with an agent pipeline: one scored run (`run_task`), one run written to its run file (`run`), the run
specs of one run type (`run_specs`) and its runs (`benchmark`, or `benchmark_model` with the model built from its
name)."""

import asyncio
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from mcp_ipi.agent import LLM, CountingLLM, Message, PipelineElement, Usage
from mcp_ipi.attacks import Attack
from mcp_ipi.defenses import DEFENSES
from mcp_ipi.mcp import MCPRuntime
from mcp_ipi.suites import Suite, Task, balanced_pairs

from .run_file import BENCHMARK_VERSION, RunResult, load_run, pipeline_name, run_path, save_run, should_run
from .show import format_cost

MODEL_NAMES = {
    "openai/gpt-5.4-mini": "GPT-5.4 mini",
    "google/gemini-3.5-flash-lite": "Gemini 3.5 Flash Lite",
    "deepseek/deepseek-v4.1-flash": "DeepSeek V4.1 Flash",
    "qwen/qwen3.7-flash": "Qwen3.7 Flash",
    "mistralai/mistral-medium-3": "Mistral Medium 3",
}
"""A readable name per benchmark model's OpenRouter ID, for the attacks' `{model}` field."""

MODEL_PROVIDERS = {
    "openai/gpt-5.4-mini": "openai",
    "google/gemini-3.5-flash-lite": "google-vertex",
    "deepseek/deepseek-v4.1-flash": "relace",
    "qwen/qwen3.7-flash": "alibaba",
    "mistralai/mistral-medium-3": "mistral",
}
"""The OpenRouter provider every call of a benchmark model goes to, by OpenRouter ID; the same keys as `MODEL_NAMES`."""


@dataclass(frozen=True)
class TaskRun:
    """The result of one run of a task.

    Attributes:
        messages: The full conversation.
        model_output: The last message's text, or `""` if it has none.
        utility: Whether the task's check passed; `None` after an error.
        injections: The attack text per injection vector; `{}` without an attack.
        security: Whether the attack succeeded; `None` without an injection task or after an error.
        hit_iteration_limit: Whether the agent stopped at the tool-loop limit.
        error: `"<ExceptionType>: <message>"` if the agent run raised, else `None`.
    """

    messages: list[Message]
    model_output: str
    utility: bool | None
    injections: dict[str, str]
    security: bool | None
    hit_iteration_limit: bool
    error: str | None


def attack_tools[E: BaseModel](injection_task: Task[E]) -> str:
    """Return the attacks' `{tools}` field: the names of the tools in the injection task's ground truth, each once,
    in order of first use, e.g. `` `search_emails`, then `send_email` ``."""
    names = dict.fromkeys(call.tool for call in injection_task.ground_truth())
    return ", then ".join(f"`{name}`" for name in names)


async def run_task[E: BaseModel](
    suite: Suite[E],
    task: Task[E],
    pipeline: PipelineElement,
    *,
    injection_task: Task[E] | None = None,
    attack: Attack | None = None,
    model_name: str = "",
) -> TaskRun:
    """Run a task through the pipeline in a fresh environment and score the result.

    Security runs apply the attack to injection vectors in the task's domain and score
    both utility and security. Pipeline errors are recorded as run errors; environment
    and scoring errors are allowed to propagate.
    """
    injections = {}
    if attack and injection_task:
        text = attack.build(injection_task.prompt, suite.user_name, model_name, attack_tools(injection_task))
        vectors = [vector for vector in suite.injection_vectors_read(task) if vector.startswith(f"{task.domain}_")]
        injections = dict.fromkeys(vectors, text)
    pre_environment, environment = suite.load_environment(injections), suite.load_environment(injections)

    async with MCPRuntime.connect(suite.domains, environment) as runtime:
        try:
            _, _, messages, _ = await pipeline.query(task.prompt, runtime)
        except Exception as error:
            # Caught inside the runtime's block, so it is not wrapped in the MCP SDK's `ExceptionGroup`.
            return TaskRun(
                [], "", None, injections, None, hit_iteration_limit=False, error=f"{type(error).__name__}: {error}"
            )

    last = messages[-1]
    hit_iteration_limit = bool(last.get("tool_calls"))
    model_output = last["content"] or ""
    utility = task.check(model_output, pre_environment, environment)
    security = injection_task.check(model_output, pre_environment, environment) if injection_task else None
    return TaskRun(
        list(messages), model_output, utility, injections, security, hit_iteration_limit=hit_iteration_limit, error=None
    )


@dataclass(frozen=True)
class RunSpec[E: BaseModel]:
    """One run: a model with a defense on a task, under an attack for a security run.

    An injection task check is a spec whose `task` is the injection task, without an injection task or an attack.

    Attributes:
        model: The model's OpenRouter ID.
        defense: A key of `DEFENSES`.
        task: The task given to the agent.
        injection_task: The injection task of a security run, else `None`.
        attack: The attack of a security run, else `None`.
    """

    model: str
    defense: str
    task: Task[E]
    injection_task: Task[E] | None = None
    attack: Attack | None = None

    def path(self, logdir: Path, suite_name: str) -> Path:
        """Return the spec's run file."""
        attack_name = self.attack.name if self.attack else "none"
        injection_task_id = self.injection_task.id if self.injection_task else None
        name = pipeline_name(self.model, self.defense)
        return run_path(logdir, name, suite_name, self.task.id, attack_name, injection_task_id)


async def run[E: BaseModel](
    suite: Suite[E],
    llm: CountingLLM,
    spec: RunSpec[E],
    *,
    temperature: float,
    logdir: Path,
    force_rerun: bool = False,
) -> RunResult:
    """Do one run, write its run file and print its line; a completed run is skipped and its result read back.

    The pipeline is built from `DEFENSES[spec.defense]` around `llm`, whose usage, providers and finish reasons are
    reset first, so the run file records only this run's calls.
    """
    path = spec.path(logdir, suite.name)
    if not should_run(path, force_rerun):
        result = load_run(path)
        print_run(result, path.relative_to(logdir), "skipped")
        return result
    pipeline = DEFENSES[spec.defense](llm, suite.security_policy)
    llm.usage, llm.providers, llm.finish_reasons = Usage(), [], []
    model_name = MODEL_NAMES[spec.model] if spec.attack else ""
    start = time.perf_counter()
    task_run = await run_task(
        suite, spec.task, pipeline, injection_task=spec.injection_task, attack=spec.attack, model_name=model_name
    )
    duration = round(time.perf_counter() - start, 3)
    result = RunResult(
        suite_name=suite.name,
        pipeline_name=pipeline_name(spec.model, spec.defense),
        model=spec.model,
        provider=llm.providers[0] if len(llm.providers) == 1 else llm.providers or None,
        finish_reasons=llm.finish_reasons,
        defense=spec.defense,
        user_task_id=spec.task.id,
        injection_task_id=spec.injection_task.id if spec.injection_task else None,
        attack=spec.attack.name if spec.attack else "none",
        user_task_difficulty=spec.task.difficulty,
        injection_task_difficulty=spec.injection_task.difficulty if spec.injection_task else None,
        injections=task_run.injections,
        messages=task_run.messages,
        utility=task_run.utility,
        security=task_run.security,
        hit_iteration_limit=task_run.hit_iteration_limit,
        usage=llm.usage,
        error=task_run.error,
        temperature=temperature,
        benchmark_version=BENCHMARK_VERSION,
        duration=duration,
        evaluation_timestamp=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    save_run(result, path)
    print_run(result, path.relative_to(logdir), "done")
    return result


def run_specs[E: BaseModel](
    suite: Suite[E],
    *,
    model: str,
    defense: str,
    attack: Attack | None = None,
    user_tasks: Sequence[Task[E]],
    injection_tasks: Sequence[Task[E]],
    pairs: Literal["subset", "full"] = "subset",
    injection_task_checks: bool = False,
) -> list[RunSpec[E]]:
    """Return the run specs of one run type for a model/defense combination, in run order.

    The run type is determined by `attack` and `injection_task_checks`:
    - utility: each user task without an attack;
    - security: each user task against each injection task, user task first; with `pairs="subset"` only the pairs of
      the whole suite's balanced subset, matched by task ID, so the selected tasks narrow the subset but never change it;
    - injection-task check: each injection task's goal as the user prompt.

    A security run's model must be in `MODEL_NAMES`; an unknown one raises `KeyError`.
    """
    if injection_task_checks:
        return [RunSpec(model, defense, task) for task in injection_tasks]
    if attack:
        MODEL_NAMES[model]  # an unknown model raises `KeyError` before any spec is built
        subset = {
            (task.id, injection_task.id)
            for task, injection_task in balanced_pairs(suite.user_tasks, suite.injection_tasks)
        }
        return [
            RunSpec(model, defense, task, injection_task, attack)
            for task in user_tasks
            for injection_task in injection_tasks
            if pairs == "full" or (task.id, injection_task.id) in subset
        ]
    return [RunSpec(model, defense, task) for task in user_tasks]


async def benchmark[E: BaseModel](
    suite: Suite[E],
    llms: Sequence[CountingLLM],
    *,
    model: str,
    defense: str,
    attack: Attack | None = None,
    user_tasks: Sequence[Task[E]],
    injection_tasks: Sequence[Task[E]],
    pairs: Literal["subset", "full"] = "subset",
    injection_task_checks: bool = False,
    temperature: float,
    logdir: Path,
    force_rerun: bool = False,
) -> list[RunResult]:
    """Do the runs of one run type for a model/defense combination with `run`, one worker per model object in `llms`.

    Each worker takes the next run not yet taken and does it with its own model object, so a model object does one
    run at a time and `run` counts each run's usage and providers alone. Lines are printed as runs finish; the results
    come back in run order. An exception that escapes a run cancels the other runs and propagates, unwrapped from the
    task group. With one model object, the runs go one after another in order.

    The runs are the specs of `run_specs`, so a security run's model must be in `MODEL_NAMES`; an unknown one raises
    `KeyError` before any run.
    """
    specs = run_specs(
        suite,
        model=model,
        defense=defense,
        attack=attack,
        user_tasks=user_tasks,
        injection_tasks=injection_tasks,
        pairs=pairs,
        injection_task_checks=injection_task_checks,
    )

    numbered_specs = iter(enumerate(specs))
    results: dict[int, RunResult] = {}

    async def worker(llm: CountingLLM) -> None:
        for index, spec in numbered_specs:
            results[index] = await run(
                suite, llm, spec, temperature=temperature, logdir=logdir, force_rerun=force_rerun
            )

    try:
        async with asyncio.TaskGroup() as group:
            for llm in llms:
                group.create_task(worker(llm))
    except ExceptionGroup as error:
        raise error.exceptions[0] from None
    return [results[index] for index in range(len(specs))]


async def benchmark_model[E: BaseModel](
    suite: Suite[E],
    *,
    model: str,
    defense: str,
    attack: Attack | None = None,
    user_tasks: Sequence[Task[E]],
    injection_tasks: Sequence[Task[E]],
    pairs: Literal["subset", "full"] = "subset",
    injection_task_checks: bool = False,
    max_workers: int = 1,
    temperature: float,
    logdir: Path,
    force_rerun: bool = False,
) -> list[RunResult]:
    """Build `max_workers` `LLM(model, temperature)` pinned to the model's provider in `MODEL_PROVIDERS`, do
    `benchmark` with them and close every model's client."""
    llms = [LLM(model, temperature, provider=MODEL_PROVIDERS[model]) for _ in range(max_workers)]
    try:
        return await benchmark(
            suite,
            llms,
            model=model,
            defense=defense,
            attack=attack,
            user_tasks=user_tasks,
            injection_tasks=injection_tasks,
            pairs=pairs,
            injection_task_checks=injection_task_checks,
            temperature=temperature,
            logdir=logdir,
            force_rerun=force_rerun,
        )
    finally:
        for llm in llms:
            await llm.client.close()


def print_run(result: RunResult, path: Path, status: str) -> None:
    """Print one line for a run: `done` or `skipped`, its scores, duration, calls, cost and path, then its error if any.

    The columns before the path have fixed widths, so the lines of a sweep line up. The cost is `$?` when it is unknown.
    """
    line = (
        f"{status:<7}  utility={result.utility!s:<5}  security={result.security!s:<5}  {result.duration:5.1f}s  "
        f"{result.usage.llm_calls:>2} calls  {format_cost(result.usage.cost):<7}  {path}"
    )
    print(f"{line}  error={result.error}" if result.error else line)
