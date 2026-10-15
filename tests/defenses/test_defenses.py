"""Tests for `DEFENSES`: the structure of the pipeline each of the five configurations builds."""

from collections.abc import Mapping, Sequence
from typing import Any

import pytest

from mcp_ipi.agent import (
    DEFAULT_SYSTEM_MESSAGE,
    InitQuery,
    Message,
    SelectTools,
    State,
    SystemMessage,
    ToolsExecutionLoop,
    ToolsExecutor,
)
from mcp_ipi.defenses import DEFENSES
from mcp_ipi.defenses.spotlighting import SPOTLIGHTING_PROMPT
from mcp_ipi.mcp import MCPRuntime
from mcp_ipi.suites.workspace import WORKSPACE


class FakeLLM:
    """Never queried: only its identity in the pipeline is checked."""

    async def query(
        self, query: str, runtime: MCPRuntime, messages: Sequence[Message] = [], extra_args: Mapping[str, Any] = {}
    ) -> State:
        raise AssertionError("not queried")


def test_defenses_are_the_five_configurations_in_order() -> None:
    assert list(DEFENSES) == ["none", "spotlighting", "sanitizer", "tool-filter", "security-policy"]


@pytest.mark.parametrize("name", list(DEFENSES))
def test_each_defense_builds_the_baseline_structure_with_its_hook(name: str) -> None:
    llm = FakeLLM()
    elements = DEFENSES[name](llm, WORKSPACE.security_policy).elements

    system, init, *selects, agent, loop = elements
    assert isinstance(system, SystemMessage)
    assert isinstance(init, InitQuery)
    assert [type(select) for select in selects] == ([SelectTools] if name == "tool-filter" else [])
    assert agent is llm
    assert isinstance(loop, ToolsExecutionLoop)
    executor, loop_llm = loop.pipeline.elements
    assert isinstance(executor, ToolsExecutor)
    assert loop_llm is llm

    if name == "spotlighting":
        assert system.text == f"{DEFAULT_SYSTEM_MESSAGE} {SPOTLIGHTING_PROMPT}"
    else:
        assert system.text == DEFAULT_SYSTEM_MESSAGE
    assert (executor.process_result is not None) == (name in ("spotlighting", "sanitizer"))
    assert (executor.check_call is not None) == (name == "security-policy")
