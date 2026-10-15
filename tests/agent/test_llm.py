"""Live test of the baseline pipeline with the real OpenRouter LLM over the Workspace suite."""

import pytest

from mcp_ipi.agent import (
    DEFAULT_SYSTEM_MESSAGE,
    LLM,
    AgentPipeline,
    InitQuery,
    SystemMessage,
    ToolsExecutionLoop,
    ToolsExecutor,
)
from mcp_ipi.mcp import MCPRuntime
from mcp_ipi.suites.workspace import WORKSPACE
from mcp_ipi.suites.workspace.user_tasks.email import email_user_task_0

pytestmark = [pytest.mark.anyio, pytest.mark.live]


async def test_baseline_with_a_real_model_calls_tools_and_ends_with_an_answer():
    llm = LLM("openai/gpt-5.4-mini", provider="openai")
    pipeline = AgentPipeline(
        [SystemMessage(DEFAULT_SYSTEM_MESSAGE), InitQuery(), llm, ToolsExecutionLoop([ToolsExecutor(), llm])]
    )

    async with llm.client, MCPRuntime.connect(WORKSPACE.domains, WORKSPACE.load_environment()) as runtime:
        _, _, messages, _ = await pipeline.query(email_user_task_0.prompt, runtime)

    assert any(message["role"] == "tool" for message in messages)
    assert messages[-1]["role"] == "assistant"
    assert not messages[-1].get("tool_calls")
