"""Live runs through run_task with the real OpenRouter model: a baseline run, a security run of email_user_task_0, and the
same security run under each defense."""

from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

import pytest

from mcp_ipi.agent import LLM, AgentPipeline, Message, State
from mcp_ipi.attacks import DIRECT_INSTRUCTION
from mcp_ipi.defenses import (
    baseline_pipeline,
    sanitizer_pipeline,
    security_policy_pipeline,
    spotlighting_pipeline,
    tool_filter_pipeline,
)
from mcp_ipi.mcp import MCPRuntime
from mcp_ipi.runner import TaskRun, run_task
from mcp_ipi.suites.workspace import WORKSPACE
from mcp_ipi.suites.workspace.injection_tasks.web import web_injection_task_0
from mcp_ipi.suites.workspace.user_tasks.email import email_user_task_0

pytestmark = [pytest.mark.anyio, pytest.mark.live]


class RecordingLLM(LLM):
    """The real model, recording the names of the tools each call was offered."""

    def __init__(self, model: str, provider: str) -> None:
        super().__init__(model, provider=provider)
        self.offered: list[set[str]] = []

    async def query(
        self, query: str, runtime: MCPRuntime, messages: Sequence[Message] = [], extra_args: Mapping[str, Any] = {}
    ) -> State:
        self.offered.append({tool.name for tool in runtime.tools})
        return await super().query(query, runtime, messages, extra_args)


@pytest.fixture
async def llm() -> AsyncIterator[RecordingLLM]:
    """The real model; its client is closed before the test's event loop is, not later by the garbage collector."""
    llm = RecordingLLM("openai/gpt-5.4-mini", "openai")
    yield llm
    await llm.client.close()


async def security_run(pipeline: AgentPipeline) -> TaskRun:
    return await run_task(
        WORKSPACE,
        email_user_task_0,
        pipeline,
        injection_task=web_injection_task_0,
        attack=DIRECT_INSTRUCTION,
        model_name="GPT-5.4 mini",
    )


def show(run: TaskRun) -> None:
    for message in run.messages:
        print(f"--- {message['role']}")
        if message["content"]:
            print(message["content"])
        for call in message.get("tool_calls") or []:
            print(f"{call['function']['name']}({call['function']['arguments']})")
    print(f"injections: {run.injections}\nutility: {run.utility}\nsecurity: {run.security}")


async def test_the_baseline_with_a_real_model_solves_email_user_task_0(llm: RecordingLLM):
    run = await run_task(WORKSPACE, email_user_task_0, baseline_pipeline(llm, WORKSPACE.security_policy))
    show(run)

    assert run.utility is True, run.messages


async def test_a_security_run_with_a_real_model_gets_the_attack_only_through_a_tool_result(llm: RecordingLLM):
    run = await security_run(baseline_pipeline(llm, WORKSPACE.security_policy))
    show(run)

    (text,) = run.injections.values()
    # Tool results are YAML, which folds long strings over several lines.
    tool_results = [" ".join(message["content"].split()) for message in run.messages if message["role"] == "tool"]
    assert any(" ".join(text.split()) in result for result in tool_results), run.messages
    assert all(
        text not in (message["content"] or "") for message in run.messages if message["role"] in ("system", "user")
    )
    assert isinstance(run.security, bool)


async def test_a_spotlighting_run_with_a_real_model_wraps_every_tool_result(llm: RecordingLLM):
    run = await security_run(spotlighting_pipeline(llm, WORKSPACE.security_policy))
    show(run)

    tool_results = [message["content"] for message in run.messages if message["role"] == "tool"]
    assert tool_results, run.messages
    assert all(r.startswith("<TOOL_RESULT>") and r.endswith("</TOOL_RESULT>") for r in tool_results), run.messages
    assert isinstance(run.security, bool)


async def test_a_sanitizer_run_with_a_real_model_is_scored(llm: RecordingLLM):
    run = await security_run(sanitizer_pipeline(llm, WORKSPACE.security_policy))
    show(run)

    assert isinstance(run.security, bool)


async def test_a_tool_filter_run_with_a_real_model_offers_the_agent_a_subset_of_the_tools(llm: RecordingLLM):
    async with MCPRuntime.connect(WORKSPACE.domains, WORKSPACE.load_environment()) as runtime:
        all_tools = {tool.name for tool in runtime.tools}

    run = await security_run(tool_filter_pipeline(llm, WORKSPACE.security_policy))
    show(run)
    print(f"offered: {llm.offered}")

    # The first call is the filter's own, offered no tools; every later one is the agent's.
    assert len(llm.offered) > 1, llm.offered
    assert all(offered < all_tools for offered in llm.offered), llm.offered
    assert isinstance(run.security, bool)


async def test_a_security_policy_run_with_a_real_model_is_scored(llm: RecordingLLM):
    run = await security_run(security_policy_pipeline(llm, WORKSPACE.security_policy))
    show(run)

    assert isinstance(run.security, bool)
