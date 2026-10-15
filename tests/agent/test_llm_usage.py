"""Tests for `LLM` with a faked OpenAI completion: its counters (tokens, calls, cost, the providers OpenRouter reports
and the finish reasons), the errors on an empty reply, on a completion without choices and on a call over the time
limit, and the reasoning details kept on the reply."""

import asyncio
from types import SimpleNamespace
from typing import Any, cast

import pytest
from openai.types.chat import ChatCompletion

from mcp_ipi.agent import LLM, EmptyReplyError, ModelCallTimeoutError, NoChoicesError, Usage
from mcp_ipi.mcp import MCPRuntime

pytestmark = pytest.mark.anyio

TOKENS = {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110}


def completion(
    usage: dict[str, Any] | None,
    provider: str | None = None,
    finish_reason: str | None = "stop",
    content: str | None = "Hello.",
    tool_calls: list[dict[str, Any]] | None = None,
    choice_error: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
    reasoning_details: list[dict[str, Any]] | None = None,
) -> ChatCompletion:
    """A completion with one choice; `choice_error` and `error` are OpenRouter's error details on the choice and on the
    completion, `reasoning_details` the reply's, left out when `None`."""
    message = {"role": "assistant", "content": content, "tool_calls": tool_calls}
    if reasoning_details is not None:
        message["reasoning_details"] = reasoning_details
    choice = {"index": 0, "finish_reason": "stop", "message": message}
    result = ChatCompletion.model_validate(
        {
            "id": "gen-1",
            "provider": provider,
            "object": "chat.completion",
            "created": 0,
            "model": "openai/gpt-5.4-mini",
            "choices": [{**choice, "error": choice_error} if choice_error else choice],
            "usage": usage,
            **({"error": error} if error else {}),
        }
    )
    # Set after validation: the SDK's type forbids a missing finish reason, but it parses responses without validating.
    result.choices[0].finish_reason = cast(Any, finish_reason)
    return result


def without_choices(result: ChatCompletion, choices: list[Any] | None) -> ChatCompletion:
    """`result` with its choices missing (`None`) or empty, as OpenRouter sometimes returns them."""
    result.choices = cast(Any, choices)
    return result


class FakeClient:
    """Stands in for `openai.AsyncOpenAI`: `chat.completions.create` returns the preset completions in turn, each
    after the next of `delays` in seconds while there are any."""

    def __init__(self, completions: list[ChatCompletion]) -> None:
        self.replies = completions
        self.delays: list[float] = []
        self.chat = self.completions = self

    async def create(self, **_: Any) -> ChatCompletion:
        if self.delays:
            await asyncio.sleep(self.delays.pop(0))
        return self.replies.pop(0)


def faked_llm(monkeypatch: pytest.MonkeyPatch, *completions: ChatCompletion) -> LLM:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    llm = LLM("openai/gpt-5.4-mini", provider="openai")
    llm.client = cast(Any, FakeClient(list(completions)))
    return llm


async def query_times(llm: LLM, times: int) -> None:
    runtime = cast(MCPRuntime, SimpleNamespace(tools=[]))
    for _ in range(times):
        await llm.query("Hi", runtime, [{"role": "user", "content": "Hi"}])


def test_adding_an_unknown_cost_gives_an_unknown_cost():
    known, unknown = Usage(llm_calls=1, cost=0.25), Usage(llm_calls=1, cost=None)

    assert (known + unknown).cost is None
    assert (unknown + known).cost is None
    assert (known + known).cost == 0.5


async def test_the_cost_of_each_completion_is_added(monkeypatch: pytest.MonkeyPatch):
    llm = faked_llm(monkeypatch, completion({**TOKENS, "cost": 0.25}), completion({**TOKENS, "cost": 0.5}))

    await query_times(llm, 2)

    assert llm.usage == Usage(input_tokens=200, output_tokens=20, llm_calls=2, cost=0.75)


async def test_a_completion_without_a_cost_gives_an_unknown_cost(monkeypatch: pytest.MonkeyPatch):
    llm = faked_llm(monkeypatch, completion({**TOKENS, "cost": 0.25}), completion(TOKENS))

    await query_times(llm, 2)

    assert llm.usage == Usage(input_tokens=200, output_tokens=20, llm_calls=2, cost=None)


async def test_a_completion_without_usage_counts_no_tokens_and_an_unknown_cost(monkeypatch: pytest.MonkeyPatch):
    llm = faked_llm(monkeypatch, completion(None))

    await query_times(llm, 1)

    assert llm.usage == Usage(input_tokens=0, output_tokens=0, llm_calls=1, cost=None)


async def test_the_providers_are_read_distinct_and_in_order_of_first_completion(monkeypatch: pytest.MonkeyPatch):
    llm = faked_llm(
        monkeypatch,
        completion(TOKENS, provider="Azure"),
        completion(TOKENS, provider="OpenAI"),
        completion(TOKENS, provider="Azure"),
    )

    await query_times(llm, 3)

    assert llm.providers == ["Azure", "OpenAI"]


async def test_the_finish_reasons_are_listed_in_order_with_repeats_and_none_for_a_missing_one(
    monkeypatch: pytest.MonkeyPatch,
):
    llm = faked_llm(
        monkeypatch,
        completion(TOKENS, finish_reason="tool_calls"),
        completion(TOKENS, finish_reason="tool_calls"),
        completion(TOKENS, finish_reason=None),
        completion(TOKENS, finish_reason="stop"),
    )

    await query_times(llm, 4)

    assert llm.finish_reasons == ["tool_calls", "tool_calls", None, "stop"]


SEARCH_CALL = {"id": "call_1", "type": "function", "function": {"name": "search_emails", "arguments": "{}"}}


@pytest.mark.parametrize("content", [None, "", " \n"])
async def test_a_reply_without_text_or_tool_calls_raises(monkeypatch: pytest.MonkeyPatch, content: str | None):
    llm = faked_llm(monkeypatch, completion(TOKENS, provider="DeepInfra", content=content))

    with pytest.raises(EmptyReplyError, match=r"finish reason stop, provider DeepInfra"):
        await query_times(llm, 1)


async def test_an_empty_reply_is_counted_before_it_raises(monkeypatch: pytest.MonkeyPatch):
    llm = faked_llm(
        monkeypatch, completion({**TOKENS, "cost": 0.0}, provider="DeepInfra", finish_reason="length", content=None)
    )

    with pytest.raises(EmptyReplyError, match="finish reason length, provider DeepInfra"):
        await query_times(llm, 1)

    assert llm.usage == Usage(input_tokens=100, output_tokens=10, llm_calls=1, cost=0.0)
    assert llm.providers == ["DeepInfra"]
    assert llm.finish_reasons == ["length"]


async def test_a_reply_with_tool_calls_and_no_text_is_returned(monkeypatch: pytest.MonkeyPatch):
    llm = faked_llm(monkeypatch, completion(TOKENS, finish_reason="tool_calls", content=None, tool_calls=[SEARCH_CALL]))
    runtime = cast(MCPRuntime, SimpleNamespace(tools=[]))

    _, _, messages, _ = await llm.query("Hi", runtime, [{"role": "user", "content": "Hi"}])

    assert messages[-1] == {"role": "assistant", "content": None, "tool_calls": [SEARCH_CALL]}


async def test_a_reply_with_text_and_no_tool_calls_is_returned(monkeypatch: pytest.MonkeyPatch):
    llm = faked_llm(monkeypatch, completion(TOKENS))
    runtime = cast(MCPRuntime, SimpleNamespace(tools=[]))

    _, _, messages, _ = await llm.query("Hi", runtime, [{"role": "user", "content": "Hi"}])

    assert messages[-1] == {"role": "assistant", "content": "Hello."}


async def test_an_empty_reply_without_error_details_keeps_its_message(monkeypatch: pytest.MonkeyPatch):
    llm = faked_llm(monkeypatch, completion(TOKENS, provider="Google", finish_reason="error", content=None))

    with pytest.raises(EmptyReplyError) as error:
        await query_times(llm, 1)

    assert str(error.value) == "no text and no tool calls, finish reason error, provider Google"


@pytest.mark.parametrize("on_choice", [True, False])
async def test_an_empty_reply_gives_openrouters_error_details(monkeypatch: pytest.MonkeyPatch, on_choice: bool):
    details = {"code": 502, "message": "Upstream error from Google: overloaded"}
    choice_error, completion_error = (details, None) if on_choice else (None, details)
    llm = faked_llm(
        monkeypatch,
        completion(TOKENS, "Google", "error", content=None, choice_error=choice_error, error=completion_error),
    )

    with pytest.raises(EmptyReplyError) as error:
        await query_times(llm, 1)

    assert str(error.value) == (
        "no text and no tool calls, finish reason error, provider Google, "
        "error 502: Upstream error from Google: overloaded"
    )


async def test_long_error_details_are_shortened(monkeypatch: pytest.MonkeyPatch):
    details = {"code": 400, "message": "x" * 1000}
    llm = faked_llm(
        monkeypatch, completion(TOKENS, provider="Google", finish_reason="error", content=None, choice_error=details)
    )

    with pytest.raises(EmptyReplyError) as error:
        await query_times(llm, 1)

    # "400: " and 295 x's fill the 300 characters kept.
    assert str(error.value).endswith("error 400: " + "x" * 295 + "…")


@pytest.mark.parametrize("choices", [None, []])
async def test_a_completion_without_choices_raises_after_it_is_counted(
    monkeypatch: pytest.MonkeyPatch, choices: list[Any] | None
):
    llm = faked_llm(monkeypatch, without_choices(completion({**TOKENS, "cost": 0.01}, provider="Google"), choices))

    with pytest.raises(NoChoicesError) as error:
        await query_times(llm, 1)

    assert str(error.value) == "completion without choices, provider Google"
    assert llm.usage == Usage(input_tokens=100, output_tokens=10, llm_calls=1, cost=0.01)
    assert llm.providers == ["Google"]
    assert llm.finish_reasons == [None]


async def test_a_completion_without_choices_gives_openrouters_error_details(monkeypatch: pytest.MonkeyPatch):
    details = {"code": "server_error", "message": "Provider returned error"}
    llm = faked_llm(monkeypatch, without_choices(completion(None, provider="Google", error=details), None))

    with pytest.raises(NoChoicesError) as error:
        await query_times(llm, 1)

    assert (
        str(error.value) == "completion without choices, provider Google, error server_error: Provider returned error"
    )


async def test_a_completion_over_the_time_limit_raises_naming_the_limit_and_the_provider(
    monkeypatch: pytest.MonkeyPatch,
):
    llm = faked_llm(monkeypatch, completion(TOKENS, provider="OpenAI"))
    cast(Any, llm.client).delays = [1]
    monkeypatch.setattr("mcp_ipi.agent.llm.MODEL_CALL_TIME_LIMIT", 0.01)

    with pytest.raises(ModelCallTimeoutError) as error:
        await query_times(llm, 1)

    assert str(error.value) == "no completion within 0.01 s, provider openai"


async def test_a_completion_inside_the_time_limit_is_returned_and_counted(monkeypatch: pytest.MonkeyPatch):
    llm = faked_llm(monkeypatch, completion({**TOKENS, "cost": 0.25}, provider="OpenAI"))
    cast(Any, llm.client).delays = [0.01]
    monkeypatch.setattr("mcp_ipi.agent.llm.MODEL_CALL_TIME_LIMIT", 1)
    runtime = cast(MCPRuntime, SimpleNamespace(tools=[]))

    _, _, messages, _ = await llm.query("Hi", runtime, [{"role": "user", "content": "Hi"}])

    assert messages[-1] == {"role": "assistant", "content": "Hello."}
    assert llm.usage == Usage(input_tokens=100, output_tokens=10, llm_calls=1, cost=0.25)
    assert llm.providers == ["OpenAI"]
    assert llm.finish_reasons == ["stop"]


async def test_a_completion_over_the_time_limit_is_not_counted(monkeypatch: pytest.MonkeyPatch):
    llm = faked_llm(
        monkeypatch,
        completion({**TOKENS, "cost": 0.25}, provider="OpenAI", finish_reason="tool_calls"),
        completion({**TOKENS, "cost": 0.5}, provider="Azure"),
    )
    cast(Any, llm.client).delays = [0, 1]
    monkeypatch.setattr("mcp_ipi.agent.llm.MODEL_CALL_TIME_LIMIT", 0.01)

    with pytest.raises(ModelCallTimeoutError):
        await query_times(llm, 2)

    assert llm.usage == Usage(input_tokens=100, output_tokens=10, llm_calls=1, cost=0.25)
    assert llm.providers == ["OpenAI"]
    assert llm.finish_reasons == ["tool_calls"]


REASONING_DETAILS = [
    {"type": "reasoning.text", "text": "Search the inbox first.", "format": "google-gemini-v1", "index": 0},
    {"type": "reasoning.encrypted", "data": "c2lnbmF0dXJl", "id": "call_1", "format": "google-gemini-v1", "index": 1},
]


@pytest.mark.parametrize(
    ("content", "tool_calls", "expected"),
    [(None, [SEARCH_CALL], {"content": None, "tool_calls": [SEARCH_CALL]}), ("Hello.", None, {"content": "Hello."})],
)
async def test_the_reasoning_details_are_kept_unchanged_on_the_reply(
    monkeypatch: pytest.MonkeyPatch, content: str | None, tool_calls: list[dict[str, Any]] | None, expected: dict
):
    llm = faked_llm(
        monkeypatch,
        completion(TOKENS, content=content, tool_calls=tool_calls, reasoning_details=REASONING_DETAILS),
    )
    runtime = cast(MCPRuntime, SimpleNamespace(tools=[]))

    _, _, messages, _ = await llm.query("Hi", runtime, [{"role": "user", "content": "Hi"}])

    assert messages[-1] == {"role": "assistant", **expected, "reasoning_details": REASONING_DETAILS}


@pytest.mark.parametrize("reasoning_details", [None, []])
async def test_a_reply_without_reasoning_details_has_no_reasoning_details(
    monkeypatch: pytest.MonkeyPatch, reasoning_details: list[dict[str, Any]] | None
):
    llm = faked_llm(monkeypatch, completion(TOKENS, reasoning_details=reasoning_details))
    runtime = cast(MCPRuntime, SimpleNamespace(tools=[]))

    _, _, messages, _ = await llm.query("Hi", runtime, [{"role": "user", "content": "Hi"}])

    assert messages[-1] == {"role": "assistant", "content": "Hello."}
