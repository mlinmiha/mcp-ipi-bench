"""Tests for `sweep_runs`: a sweep's runs and their run files, over the real Workspace suite with `LLM` replaced by a
scripted fake."""

import asyncio
import dataclasses
import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, ClassVar

import pytest

from mcp_ipi.agent import Message, State, Usage
from mcp_ipi.attacks import DIRECT_INSTRUCTION
from mcp_ipi.mcp import MCPRuntime
from mcp_ipi.runner import RunResult, RunSpec, sweep_runs
from mcp_ipi.suites.workspace import WORKSPACE, WorkspaceEnvironment
from mcp_ipi.suites.workspace.injection_tasks.web import web_injection_task_0
from mcp_ipi.suites.workspace.user_tasks.email import email_user_task_0

pytestmark = pytest.mark.anyio

MINI = "openai/gpt-5.4-mini"
DEEPSEEK = "deepseek/deepseek-v4.1-flash"
QWEN = "qwen/qwen3.7-flash"
REPLY_USAGE = Usage(input_tokens=100, output_tokens=10, llm_calls=1, cost=0.001)
PROVIDERS = {MINI: "OpenAI", DEEPSEEK: "GMICloud", QWEN: "Novita"}
WAIT_TIMEOUT = 5

UTILITY = RunSpec(MINI, "none", email_user_task_0)
SECURITY = RunSpec(MINI, "none", email_user_task_0, web_injection_task_0, DIRECT_INSTRUCTION)
CHECK = RunSpec(MINI, "none", web_injection_task_0)
DEEPSEEK_UTILITY = RunSpec(DEEPSEEK, "none", email_user_task_0)
DEEPSEEK_CHECK = RunSpec(DEEPSEEK, "none", web_injection_task_0)
QWEN_UTILITY = RunSpec(QWEN, "none", email_user_task_0)


class FakeClient:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class FakeLLM:
    """Stands in for `LLM(model, temperature)`: answers `Done.` to every call, or raises its model's error in `errors`.

    A call of a model in `waits` first awaits its wait; after `WAIT_TIMEOUT` seconds the call raises.
    """

    errors: ClassVar[dict[str, Exception]] = {}
    waits: ClassVar[dict[str, Callable[[], Awaitable[object]]]] = {}

    def __init__(self, model: str, temperature: float) -> None:
        self.model = model
        self.temperature = temperature
        self.client = FakeClient()
        self.calls = 0
        self.usage = Usage()
        self.providers: list[str] = []
        self.finish_reasons: list[str | None] = []

    async def query(
        self, query: str, runtime: MCPRuntime, messages: Sequence[Message] = [], extra_args: Mapping[str, Any] = {}
    ) -> State:
        self.calls += 1
        if self.model in self.waits:
            await asyncio.wait_for(self.waits[self.model](), WAIT_TIMEOUT)
        if self.model in self.errors:
            raise self.errors[self.model]
        self.usage += REPLY_USAGE
        self.providers.append(PROVIDERS[self.model])
        self.finish_reasons.append("stop")
        return query, runtime, [*messages, {"role": "assistant", "content": "Done."}], extra_args


@pytest.fixture
def built(monkeypatch: pytest.MonkeyPatch) -> list[FakeLLM]:
    """The fake models `sweep_runs` builds, in order."""
    models: list[FakeLLM] = []

    def build(model: str, temperature: float, *, provider: str) -> FakeLLM:
        models.append(FakeLLM(model, temperature))
        return models[-1]

    monkeypatch.setattr("mcp_ipi.runner.sweep.LLM", build)
    return models


async def sweep(
    specs: list[RunSpec[WorkspaceEnvironment]],
    logdir: Path,
    force_rerun: bool = False,
    concurrency: Mapping[str, int] = {},
) -> list[RunResult]:
    return await sweep_runs(
        WORKSPACE, specs, temperature=0.5, logdir=logdir, force_rerun=force_rerun, concurrency=concurrency
    )


def read_run(spec: RunSpec[WorkspaceEnvironment], logdir: Path) -> dict[str, Any]:
    return json.loads(spec.path(logdir, WORKSPACE.name).read_text())


def run_files(logdir: Path) -> list[Path]:
    return sorted(logdir.rglob("*.json"))


async def test_every_spec_runs_once_in_order_and_writes_its_run_file(tmp_path: Path, built: list[FakeLLM]):
    specs = [UTILITY, SECURITY, CHECK, DEEPSEEK_UTILITY]

    results = await sweep(specs, tmp_path)

    assert [(result.model, result.user_task_id, result.injection_task_id) for result in results] == [
        (MINI, "email_user_task_0", None),
        (MINI, "email_user_task_0", "web_injection_task_0"),
        (MINI, "web_injection_task_0", None),
        (DEEPSEEK, "email_user_task_0", None),
    ]
    assert run_files(tmp_path) == sorted(spec.path(tmp_path, WORKSPACE.name) for spec in specs)
    assert [read_run(spec, tmp_path) for spec in specs] == [result.model_dump(mode="json") for result in results]
    assert [read_run(spec, tmp_path)["temperature"] for spec in specs] == [0.5] * 4


@pytest.mark.parametrize("force_rerun", [False, True])
async def test_a_spec_whose_path_repeats_runs_once(tmp_path: Path, built: list[FakeLLM], force_rerun: bool):
    results = await sweep([SECURITY, UTILITY, dataclasses.replace(SECURITY)], tmp_path, force_rerun=force_rerun)

    assert [result.injection_task_id for result in results] == ["web_injection_task_0", None]
    assert sum(llm.calls for llm in built) == 2


async def test_a_run_error_is_recorded_and_the_sweep_goes_on(
    tmp_path: Path, built: list[FakeLLM], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(FakeLLM, "errors", {DEEPSEEK: TimeoutError("timed out")})

    results = await sweep([DEEPSEEK_UTILITY, UTILITY], tmp_path)

    assert [result.error for result in results] == ["TimeoutError: timed out", None]
    assert read_run(DEEPSEEK_UTILITY, tmp_path)["error"] == "TimeoutError: timed out"


async def test_a_completed_run_is_skipped_and_a_run_with_an_error_runs_again(
    tmp_path: Path, built: list[FakeLLM], monkeypatch: pytest.MonkeyPatch
):
    with monkeypatch.context() as patch:
        patch.setattr(FakeLLM, "errors", {MINI: TimeoutError("timed out")})
        await sweep([UTILITY], tmp_path)
    await sweep([SECURITY], tmp_path)
    built.clear()

    results = await sweep([UTILITY, SECURITY], tmp_path)

    assert [result.error for result in results] == [None, None]
    assert [llm.calls for llm in built] == [1]


async def test_force_rerun_runs_a_completed_run_again(tmp_path: Path, built: list[FakeLLM]):
    await sweep([UTILITY], tmp_path)
    built.clear()

    await sweep([UTILITY], tmp_path, force_rerun=True)

    assert [llm.calls for llm in built] == [1]


async def test_each_run_file_records_only_its_own_usage_and_provider(tmp_path: Path, built: list[FakeLLM]):
    await sweep([UTILITY, CHECK, DEEPSEEK_UTILITY], tmp_path)

    assert [
        (read_run(spec, tmp_path)["usage"], read_run(spec, tmp_path)["provider"])
        for spec in [UTILITY, CHECK, DEEPSEEK_UTILITY]
    ] == [
        (REPLY_USAGE.model_dump(), "OpenAI"),
        (REPLY_USAGE.model_dump(), "OpenAI"),
        (REPLY_USAGE.model_dump(), "GMICloud"),
    ]


async def test_one_model_is_built_per_distinct_model_and_all_are_closed_when_a_run_raises(
    tmp_path: Path, built: list[FakeLLM]
):
    def broken_check(*args: object) -> bool:
        raise ValueError("broken check")

    broken = RunSpec(
        DEEPSEEK, "none", dataclasses.replace(email_user_task_0, id="email_user_task_1", check=broken_check)
    )

    with pytest.raises(ValueError, match="broken check"):
        await sweep([UTILITY, SECURITY, broken, CHECK], tmp_path)

    assert [(llm.model, llm.temperature, llm.client.closed) for llm in built] == [
        (MINI, 0.5, True),
        (DEEPSEEK, 0.5, True),
    ]
    assert run_files(tmp_path) == sorted(spec.path(tmp_path, WORKSPACE.name) for spec in [UTILITY, SECURITY])


class InFlight:
    """A wait that counts the calls in flight at once and records the most there ever were."""

    def __init__(self) -> None:
        self.now = 0
        self.most = 0

    async def __call__(self) -> None:
        self.now += 1
        self.most = max(self.most, self.now)
        await asyncio.sleep(0.01)
        self.now -= 1


def waiting(monkeypatch: pytest.MonkeyPatch, wait: Callable[[], Awaitable[object]], *models: str) -> None:
    monkeypatch.setattr(FakeLLM, "waits", dict.fromkeys(models, wait))


async def test_two_runs_of_a_pool_with_limit_two_are_in_flight_at_once(
    tmp_path: Path, built: list[FakeLLM], monkeypatch: pytest.MonkeyPatch
):
    barrier = asyncio.Barrier(2)
    waiting(monkeypatch, barrier.wait, MINI)

    results = await sweep([UTILITY, CHECK], tmp_path, concurrency={"openai": 2})

    assert [result.error for result in results] == [None, None]
    assert [llm.calls for llm in built] == [1, 1]


async def test_runs_of_two_pools_are_in_flight_at_once(
    tmp_path: Path, built: list[FakeLLM], monkeypatch: pytest.MonkeyPatch
):
    barrier = asyncio.Barrier(2)
    waiting(monkeypatch, barrier.wait, MINI, DEEPSEEK)

    results = await sweep([UTILITY, DEEPSEEK_UTILITY], tmp_path, concurrency={"openai": 1, "deepseek": 1})

    assert [result.error for result in results] == [None, None]


async def test_a_pool_never_has_more_runs_in_flight_than_its_limit(
    tmp_path: Path, built: list[FakeLLM], monkeypatch: pytest.MonkeyPatch
):
    in_flight = InFlight()
    waiting(monkeypatch, in_flight, MINI)

    results = await sweep([UTILITY, SECURITY, CHECK], tmp_path, concurrency={"openai": 2})

    assert [result.error for result in results] == [None, None, None]
    assert in_flight.most == 2


async def test_models_without_their_own_key_share_the_openrouter_pool(
    tmp_path: Path, built: list[FakeLLM], monkeypatch: pytest.MonkeyPatch
):
    in_flight = InFlight()
    waiting(monkeypatch, in_flight, DEEPSEEK, QWEN)

    results = await sweep([DEEPSEEK_UTILITY, QWEN_UTILITY, DEEPSEEK_CHECK], tmp_path, concurrency={"openrouter": 1})

    assert [result.error for result in results] == [None, None, None]
    assert in_flight.most == 1


async def test_without_an_openrouter_key_the_shared_pool_has_one_worker(
    tmp_path: Path, built: list[FakeLLM], monkeypatch: pytest.MonkeyPatch
):
    in_flight = InFlight()
    waiting(monkeypatch, in_flight, DEEPSEEK, QWEN)

    results = await sweep([DEEPSEEK_UTILITY, QWEN_UTILITY, DEEPSEEK_CHECK], tmp_path, concurrency={"openai": 2})

    assert [result.error for result in results] == [None, None, None]
    assert in_flight.most == 1


async def test_results_come_in_spec_order_when_a_later_run_finishes_first(
    tmp_path: Path, built: list[FakeLLM], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    deepseek_run_file = DEEPSEEK_UTILITY.path(tmp_path, WORKSPACE.name)

    async def deepseek_run_written() -> None:
        while not deepseek_run_file.exists():
            await asyncio.sleep(0.01)

    waiting(monkeypatch, deepseek_run_written, MINI)

    results = await sweep([UTILITY, DEEPSEEK_UTILITY], tmp_path, concurrency={"openai": 1, "deepseek": 1})

    assert [(result.model, result.error) for result in results] == [(MINI, None), (DEEPSEEK, None)]
    lines = capsys.readouterr().out.splitlines()
    assert [line.split()[-1].split("/")[0] for line in lines] == [
        "deepseek_deepseek-v4.1-flash",
        "openai_gpt-5.4-mini",
    ]


async def test_each_run_file_of_two_runs_in_flight_records_only_its_own_usage_and_provider(
    tmp_path: Path, built: list[FakeLLM], monkeypatch: pytest.MonkeyPatch
):
    barrier = asyncio.Barrier(2)
    waiting(monkeypatch, barrier.wait, MINI)

    await sweep([UTILITY, CHECK], tmp_path, concurrency={"openai": 2})

    runs = [read_run(spec, tmp_path) for spec in [UTILITY, CHECK]]
    assert [(run["usage"], run["provider"]) for run in runs] == [(REPLY_USAGE.model_dump(), "OpenAI")] * 2


async def test_a_spec_whose_path_repeats_runs_once_with_workers(tmp_path: Path, built: list[FakeLLM]):
    results = await sweep([SECURITY, UTILITY, dataclasses.replace(SECURITY)], tmp_path, concurrency={"openai": 3})

    assert [result.injection_task_id for result in results] == ["web_injection_task_0", None]
    assert sum(llm.calls for llm in built) == 2


async def test_workers_skip_a_completed_run_and_redo_a_run_with_an_error(
    tmp_path: Path, built: list[FakeLLM], monkeypatch: pytest.MonkeyPatch
):
    with monkeypatch.context() as patch:
        patch.setattr(FakeLLM, "errors", {MINI: TimeoutError("timed out")})
        await sweep([UTILITY], tmp_path)
    await sweep([SECURITY], tmp_path)
    built.clear()

    results = await sweep([UTILITY, SECURITY], tmp_path, concurrency={"openai": 2})

    assert [result.error for result in results] == [None, None]
    assert sum(llm.calls for llm in built) == 1


async def test_every_worker_model_is_closed_and_an_escaping_exception_cancels_the_other_runs(
    tmp_path: Path, built: list[FakeLLM], monkeypatch: pytest.MonkeyPatch
):
    def broken_check(*args: object) -> bool:
        raise ValueError("broken check")

    never = asyncio.Event()
    waiting(monkeypatch, never.wait, MINI)
    broken = RunSpec(DEEPSEEK, "none", dataclasses.replace(email_user_task_0, check=broken_check))

    with pytest.raises(ValueError, match="broken check"):
        await sweep([UTILITY, broken], tmp_path, concurrency={"openai": 2, "deepseek": 1})

    assert sorted((llm.model, llm.client.closed) for llm in built) == [(DEEPSEEK, True), (MINI, True), (MINI, True)]
    assert run_files(tmp_path) == []
