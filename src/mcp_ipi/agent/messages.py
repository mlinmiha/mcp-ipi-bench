"""Chat messages as plain dicts in OpenAI chat-completions format."""

from typing import Any, Literal, NotRequired, TypedDict


class FunctionCall(TypedDict):
    name: str
    arguments: str  # The model's JSON string, sometimes empty for argument-less tools.


class AssistantToolCall(TypedDict):
    id: str
    type: Literal["function"]
    function: FunctionCall


class ChatSystemMessage(TypedDict):
    role: Literal["system"]
    content: str


class ChatUserMessage(TypedDict):
    role: Literal["user"]
    content: str


class ChatAssistantMessage(TypedDict):
    role: Literal["assistant"]
    content: str | None
    tool_calls: NotRequired[list[AssistantToolCall]]
    reasoning_details: NotRequired[list[dict[str, Any]]]  # OpenRouter's, kept opaque and sent back unchanged.


class ChatToolMessage(TypedDict):
    role: Literal["tool"]
    tool_call_id: str
    content: str


Message = ChatSystemMessage | ChatUserMessage | ChatAssistantMessage | ChatToolMessage
