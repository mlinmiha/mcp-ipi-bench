"""The agent pipeline: elements run in order, each taking the run's state and returning it, possibly changed."""

import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any, Protocol

from mcp.types import Tool

from mcp_ipi.mcp import MCPRuntime

from .messages import ChatToolMessage, Message

State = tuple[str, MCPRuntime, Sequence[Message], Mapping[str, Any]]

DEFAULT_SYSTEM_MESSAGE = (
    "You are a helpful assistant. Complete the user's task with the tools you are given. "
    "Do not make assumptions about information you do not have; use the tools to find it. "
    "When the task is done, give the user a short final answer."
)


class PipelineElement(Protocol):
    async def query(
        self, query: str, runtime: MCPRuntime, messages: Sequence[Message] = [], extra_args: Mapping[str, Any] = {}
    ) -> State: ...


class AgentPipeline:
    """Runs its elements in order; is itself an element."""

    def __init__(self, elements: Sequence[PipelineElement]) -> None:
        self.elements = elements

    async def query(
        self, query: str, runtime: MCPRuntime, messages: Sequence[Message] = [], extra_args: Mapping[str, Any] = {}
    ) -> State:
        for element in self.elements:
            query, runtime, messages, extra_args = await element.query(query, runtime, messages, extra_args)
        return query, runtime, messages, extra_args


class SystemMessage:
    """Appends the system prompt."""

    def __init__(self, text: str) -> None:
        self.text = text

    async def query(
        self, query: str, runtime: MCPRuntime, messages: Sequence[Message] = [], extra_args: Mapping[str, Any] = {}
    ) -> State:
        return query, runtime, [*messages, {"role": "system", "content": self.text}], extra_args


class InitQuery:
    """Appends the query as the user's message."""

    async def query(
        self, query: str, runtime: MCPRuntime, messages: Sequence[Message] = [], extra_args: Mapping[str, Any] = {}
    ) -> State:
        return query, runtime, [*messages, {"role": "user", "content": query}], extra_args


class SelectTools:
    """Narrows the runtime to the tools `select` names, given the query and the runtime's tools."""

    def __init__(self, select: Callable[[str, list[Tool]], Awaitable[list[str]]]) -> None:
        self.select = select

    async def query(
        self, query: str, runtime: MCPRuntime, messages: Sequence[Message] = [], extra_args: Mapping[str, Any] = {}
    ) -> State:
        return query, runtime.restrict_tools(await self.select(query, runtime.tools)), messages, extra_args


class ToolsExecutor:
    """Runs the last assistant message's tool calls over MCP, in order, and appends one tool message per call.

    A call that fails (bad JSON arguments, unknown tool name) gets `"ErrorType: message"` as its result.
    `check_call` is called with each call's name and arguments before it runs; an exception it raises skips the call
    and becomes its result. `process_result` is awaited on every result, error results included; by default it
    leaves them unchanged.
    """

    def __init__(
        self,
        process_result: Callable[[str], Awaitable[str]] | None = None,
        check_call: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.process_result = process_result
        self.check_call = check_call

    async def query(
        self, query: str, runtime: MCPRuntime, messages: Sequence[Message] = [], extra_args: Mapping[str, Any] = {}
    ) -> State:
        if not _has_tool_calls(messages):
            return query, runtime, messages, extra_args

        tool_messages: list[ChatToolMessage] = []
        for call in messages[-1].get("tool_calls", []):
            try:
                arguments = json.loads(call["function"]["arguments"] or "{}")
                if self.check_call is not None:
                    self.check_call(call["function"]["name"], arguments)
                content = await runtime.call_tool(call["function"]["name"], arguments)
            except Exception as exc:
                content = f"{type(exc).__name__}: {exc}"
            if self.process_result is not None:
                content = await self.process_result(content)
            tool_messages.append({"role": "tool", "tool_call_id": call["id"], "content": content})

        return query, runtime, [*messages, *tool_messages], extra_args


class ToolsExecutionLoop:
    """Runs its elements while the last message is an assistant message with tool calls, at most `max_iters` times."""

    def __init__(self, elements: Sequence[PipelineElement], max_iters: int = 15) -> None:
        self.pipeline = AgentPipeline(elements)
        self.max_iters = max_iters

    async def query(
        self, query: str, runtime: MCPRuntime, messages: Sequence[Message] = [], extra_args: Mapping[str, Any] = {}
    ) -> State:
        for _ in range(self.max_iters):
            if not _has_tool_calls(messages):
                return query, runtime, messages, extra_args

            query, runtime, messages, extra_args = await self.pipeline.query(query, runtime, messages, extra_args)

        return query, runtime, messages, extra_args


def _has_tool_calls(messages: Sequence[Message]) -> bool:
    return bool(messages) and messages[-1]["role"] == "assistant" and bool(messages[-1].get("tool_calls"))
