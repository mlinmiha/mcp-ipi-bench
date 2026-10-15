"""Tests for the baseline agent pipeline over the Workspace suite, with a scripted model in the LLM position."""

import json
from collections.abc import Mapping, Sequence
from typing import Any

import pytest
from mcp.types import Tool

from mcp_ipi.agent import (
    DEFAULT_SYSTEM_MESSAGE,
    AgentPipeline,
    AssistantToolCall,
    ChatAssistantMessage,
    InitQuery,
    Message,
    State,
    SystemMessage,
    ToolsExecutionLoop,
    ToolsExecutor,
)
from mcp_ipi.mcp import MCPRuntime
from mcp_ipi.suites.workspace import WORKSPACE, WorkspaceEnvironment

pytestmark = pytest.mark.anyio

QUERY = "Please pay my CloudHost invoice."


class ScriptedLLM:
    """Appends one preset assistant message per call (or raises a preset exception) and records what it was given."""

    def __init__(self, replies: list[ChatAssistantMessage | Exception]) -> None:
        self.replies = replies
        self.calls: list[tuple[list[Tool], list[Message]]] = []

    async def query(
        self, query: str, runtime: MCPRuntime, messages: Sequence[Message] = [], extra_args: Mapping[str, Any] = {}
    ) -> State:
        self.calls.append((runtime.tools, list(messages)))
        reply = self.replies[len(self.calls) - 1]
        if isinstance(reply, Exception):
            raise reply
        return query, runtime, [*messages, reply], extra_args


def tool_call(call_id: str, name: str, **arguments: Any) -> AssistantToolCall:
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}


def calling_tools(*calls: AssistantToolCall) -> ChatAssistantMessage:
    return {"role": "assistant", "content": None, "tool_calls": list(calls)}


def answer(text: str) -> ChatAssistantMessage:
    return {"role": "assistant", "content": text}


def baseline(llm: ScriptedLLM) -> AgentPipeline:
    return AgentPipeline(
        [SystemMessage(DEFAULT_SYSTEM_MESSAGE), InitQuery(), llm, ToolsExecutionLoop([ToolsExecutor(), llm])]
    )


async def run(
    llm: ScriptedLLM, environment: WorkspaceEnvironment, extra_args: Mapping[str, Any] = {}
) -> tuple[MCPRuntime, State]:
    async with MCPRuntime.connect(WORKSPACE.domains, environment) as runtime:
        result = await baseline(llm).query(QUERY, runtime, extra_args=extra_args)
    return runtime, result


async def test_no_tool_calls_gives_system_user_and_answer_and_leaves_the_environment_unchanged():
    environment = WORKSPACE.load_environment()
    before = environment.model_copy(deep=True)

    _, (_, _, messages, _) = await run(ScriptedLLM([answer("Nothing to do.")]), environment)

    assert messages == [
        {"role": "system", "content": DEFAULT_SYSTEM_MESSAGE},
        {"role": "user", "content": QUERY},
        {"role": "assistant", "content": "Nothing to do."},
    ]
    assert environment == before


async def test_one_tool_call_gives_one_tool_message_with_the_invoice_vector():
    default = WORKSPACE.load_injection_defaults()["email_invoice_body"]
    llm = ScriptedLLM([calling_tools(tool_call("call_1", "get_email_by_id", email_id="1")), answer("It is 49.00 EUR.")])

    _, (_, _, messages, _) = await run(llm, WORKSPACE.load_environment())

    tool_messages = [message for message in messages if message["role"] == "tool"]
    assert len(tool_messages) == 1
    assert tool_messages[0]["tool_call_id"] == "call_1"
    assert default in tool_messages[0]["content"]
    assert messages[-1] == answer("It is 49.00 EUR.")


async def test_several_calls_over_several_turns_run_in_order_and_change_the_environment():
    environment = WORKSPACE.load_environment()
    llm = ScriptedLLM(
        [
            calling_tools(
                tool_call("a", "get_email_by_id", email_id="1"),
                tool_call("b", "send_email", recipients=["billing@cloudhost.io"], subject="Paid", body="Done."),
            ),
            calling_tools(tool_call("c", "post_webpage", url="www.notes.com", title="Notes", content="Invoice paid.")),
            answer("Done."),
        ]
    )

    _, (_, _, messages, _) = await run(llm, environment)

    assert [message["role"] for message in messages] == [
        "system",
        "user",
        "assistant",
        "tool",
        "tool",
        "assistant",
        "tool",
        "assistant",
    ]
    assert [message["tool_call_id"] for message in messages if message["role"] == "tool"] == ["a", "b", "c"]
    assert environment.inbox.sent[-1].subject == "Paid"
    assert any(page.url == "www.notes.com" for page in environment.web.pages)


async def test_model_receives_the_tools_and_the_conversation_and_extra_args_pass_through():
    extra_args = {"key": "value"}
    llm = ScriptedLLM([calling_tools(tool_call("call_1", "get_email_by_id", email_id="1")), answer("Done.")])

    runtime, (query, _, messages, returned_extra_args) = await run(llm, WORKSPACE.load_environment(), extra_args)

    assert query == QUERY
    assert returned_extra_args == extra_args
    assert [tools for tools, _ in llm.calls] == [runtime.tools, runtime.tools]
    assert [received for _, received in llm.calls] == [messages[:2], messages[:4]]


async def test_failed_calls_become_error_tool_messages_and_the_run_goes_on():
    llm = ScriptedLLM(
        [
            calling_tools(
                tool_call("a", "delete_email", email_id="99"),
                tool_call("b", "no_such_tool"),
                {"id": "c", "type": "function", "function": {"name": "search_emails", "arguments": "{not json"}},
            ),
            answer("Sorry, that did not work."),
        ]
    )

    _, (_, _, messages, _) = await run(llm, WORKSPACE.load_environment())

    contents = [message["content"] for message in messages if message["role"] == "tool"]
    assert contents[0] == "ValueError: Email with ID '99' not found"
    assert contents[1] == "KeyError: 'no_such_tool'"
    assert contents[2].startswith("JSONDecodeError: ")
    assert messages[-1] == answer("Sorry, that did not work.")


async def test_a_model_that_never_stops_calling_tools_is_stopped_after_15_rounds():
    llm = ScriptedLLM([calling_tools(tool_call(f"call_{i}", "get_email_by_id", email_id="1")) for i in range(16)])

    _, (_, _, messages, extra_args) = await run(llm, WORKSPACE.load_environment())

    assert len(llm.calls) == 16
    assert len([message for message in messages if message["role"] == "tool"]) == 15
    assert messages[-1] == llm.replies[-1]
    assert extra_args == {}


async def test_a_model_error_leaves_the_pipeline():
    llm = ScriptedLLM(
        [calling_tools(tool_call("call_1", "get_email_by_id", email_id="1")), TimeoutError("model timed out")]
    )

    async with MCPRuntime.connect(WORKSPACE.domains, WORKSPACE.load_environment()) as runtime:
        with pytest.raises(TimeoutError, match="model timed out"):
            await baseline(llm).query(QUERY, runtime)
