"""The LLM element: calls a model on OpenRouter with the openai SDK. The only module that imports `openai`."""

import asyncio
import os
from collections.abc import Mapping, Sequence
from typing import Any, cast

import openai
from openai.types.chat import ChatCompletion, ChatCompletionMessageParam, ChatCompletionToolParam

from mcp_ipi.mcp import MCPRuntime

from .messages import ChatAssistantMessage, Message
from .pipeline import State
from .usage import Usage

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MAX_ERROR_DETAILS = 300
MODEL_CALL_TIME_LIMIT = 120


class EmptyReplyError(Exception):
    """A completion with neither text nor tool calls: a provider fault, not a final answer."""


class NoChoicesError(Exception):
    """A completion with its `choices` missing or empty: a provider fault."""


class ModelCallTimeoutError(Exception):
    """A completion that did not come back within `MODEL_CALL_TIME_LIMIT` seconds: a provider fault."""


def _error_details(completion: ChatCompletion) -> str:
    """`", error <code>: <message>"` from the error OpenRouter sent on the first choice, else on the completion, cut to
    `MAX_ERROR_DETAILS` characters; `""` when it sent none."""
    error = (completion.choices[0].model_extra or {}).get("error") if completion.choices else None
    error = error or (completion.model_extra or {}).get("error")
    if not error:
        return ""
    details = f"{error.get('code')}: {error.get('message')}"
    return ", error " + (details if len(details) <= MAX_ERROR_DETAILS else details[:MAX_ERROR_DETAILS] + "…")


class LLM:
    """Sends the conversation and the runtime's tools to an OpenRouter model and appends its reply.

    Every completion asks OpenRouter for `provider` only (the only entry of `order`, fallbacks off), so when that
    provider is unavailable the call raises instead of going to another provider.

    `usage` sums the tokens, calls and cost of every completion so far; tokens count 0 when the API reports none.
    OpenRouter reports every completion's cost in USD as `usage.cost` without being asked; when a completion has no
    cost, the sum's cost is `None`. `providers` lists the distinct providers OpenRouter routed the completions to
    (its `provider` field), in the order of their first completion. `finish_reasons` lists every completion's
    `finish_reason` in call order, `None` where it is missing. A completion with no choices (missing or empty) raises
    `NoChoicesError`, and one with no tool calls and no text (`None`, empty or whitespace only) `EmptyReplyError`, both
    after it is counted (a completion without choices adds `None` to `finish_reasons`) and naming its provider and the
    error details OpenRouter sent, if any.

    Every completion has `MODEL_CALL_TIME_LIMIT` seconds from request to reply, the SDK's own retries included; the
    SDK's `timeout` limits only the wait for the next bytes. A call over the limit raises `ModelCallTimeoutError`,
    naming the limit and the pinned provider, and is not counted, since no completion came back.

    The reply's `reasoning_details`, when OpenRouter returns a non-empty list, are kept unchanged on the assistant
    message, so they go back to the model with it on every later call; the reply's `reasoning` text is not kept.
    """

    def __init__(self, model: str, temperature: float = 0.0, *, provider: str) -> None:
        self.model = model
        self.temperature = temperature
        self.provider = provider
        self.client = openai.AsyncOpenAI(base_url=OPENROUTER_BASE_URL, api_key=os.environ["OPENROUTER_API_KEY"])
        self.usage = Usage()
        self.providers: list[str] = []
        self.finish_reasons: list[str | None] = []

    async def query(
        self, query: str, runtime: MCPRuntime, messages: Sequence[Message] = [], extra_args: Mapping[str, Any] = {}
    ) -> State:
        tools: list[ChatCompletionToolParam] = [
            {
                "type": "function",
                "function": {"name": tool.name, "description": tool.description or "", "parameters": tool.input_schema},
            }
            for tool in runtime.tools
        ]
        try:
            async with asyncio.timeout(MODEL_CALL_TIME_LIMIT):
                completion = await self.client.chat.completions.create(
                    model=self.model,
                    messages=cast(list[ChatCompletionMessageParam], messages),
                    tools=tools or openai.omit,
                    temperature=self.temperature,
                    extra_body={"provider": {"order": [self.provider], "allow_fallbacks": False}},
                )
        except TimeoutError:
            raise ModelCallTimeoutError(
                f"no completion within {MODEL_CALL_TIME_LIMIT} s, provider {self.provider}"
            ) from None
        tokens = completion.usage
        self.usage += Usage(
            input_tokens=tokens.prompt_tokens if tokens else 0,
            output_tokens=tokens.completion_tokens if tokens else 0,
            llm_calls=1,
            cost=(tokens.model_extra or {}).get("cost") if tokens else None,
        )
        provider = (completion.model_extra or {}).get("provider")
        if provider and provider not in self.providers:
            self.providers.append(provider)
        if not completion.choices:
            self.finish_reasons.append(None)
            raise NoChoicesError(f"completion without choices, provider {provider}{_error_details(completion)}")
        finish_reason = completion.choices[0].finish_reason
        self.finish_reasons.append(finish_reason)

        reply = completion.choices[0].message
        if not reply.tool_calls and not (reply.content or "").strip():
            raise EmptyReplyError(
                f"no text and no tool calls, finish reason {finish_reason}, provider {provider}"
                f"{_error_details(completion)}"
            )
        message: ChatAssistantMessage = {"role": "assistant", "content": reply.content}
        if reply.tool_calls:
            message["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.function.name, "arguments": call.function.arguments},
                }
                for call in reply.tool_calls
                if call.type == "function"
            ]
        if reasoning_details := (reply.model_extra or {}).get("reasoning_details"):
            message["reasoning_details"] = reasoning_details
        return query, runtime, [*messages, message], extra_args
