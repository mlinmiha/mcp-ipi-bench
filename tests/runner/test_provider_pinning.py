"""Tests for pinning each model's OpenRouter provider: `MODEL_PROVIDERS` and the provider preference every completion
request of `benchmark_model` and `sweep_runs` carries, with the OpenAI client faked."""

import json
from pathlib import Path
from typing import Any, ClassVar

import httpx2
import openai
import pytest
from openai.types.chat import ChatCompletion

from mcp_ipi.runner import MODEL_NAMES, MODEL_PROVIDERS, RunSpec, benchmark_model, sweep_runs
from mcp_ipi.suites.workspace import WORKSPACE
from mcp_ipi.suites.workspace.injection_tasks.web import web_injection_task_0
from mcp_ipi.suites.workspace.user_tasks.email import email_user_task_0

pytestmark = pytest.mark.anyio

MINI = "openai/gpt-5.4-mini"
QWEN = "qwen/qwen3.7-flash"


def completion(content: str | None, tool_calls: list[dict[str, Any]] | None = None) -> ChatCompletion:
    message = {"role": "assistant", "content": content, "tool_calls": tool_calls}
    return ChatCompletion.model_validate(
        {
            "id": "gen-1",
            "object": "chat.completion",
            "created": 0,
            "model": MINI,
            "choices": [{"index": 0, "finish_reason": "stop", "message": message}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110, "cost": 0.001},
        }
    )


def searching_emails() -> ChatCompletion:
    call = {"id": "call_1", "type": "function", "function": {"name": "search_emails", "arguments": '{"query": "x"}'}}
    return completion(None, [call])


class FakeClient:
    """Stands in for `openai.AsyncOpenAI`: records each request's model and provider preference in `requests` and
    returns the preset replies in turn, or raises `error`; `Done.` once they run out."""

    replies: ClassVar[list[ChatCompletion]] = []
    error: ClassVar[Exception | None] = None
    requests: ClassVar[list[tuple[str, Any]]] = []

    def __init__(self, **_: Any) -> None:
        self.chat = self.completions = self

    async def create(self, *, model: str, extra_body: dict[str, Any] | None = None, **_: Any) -> ChatCompletion:
        self.requests.append((model, (extra_body or {}).get("provider")))
        if self.error:
            raise self.error
        return self.replies.pop(0) if self.replies else completion("Done.")

    async def close(self) -> None:
        pass


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> type[FakeClient]:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(FakeClient, "replies", [])
    monkeypatch.setattr(FakeClient, "error", None)
    monkeypatch.setattr(FakeClient, "requests", [])
    monkeypatch.setattr("mcp_ipi.agent.llm.openai.AsyncOpenAI", FakeClient)
    return FakeClient


def pinned(model: str) -> dict[str, Any]:
    return {"order": [MODEL_PROVIDERS[model]], "allow_fallbacks": False}


async def one_run(model: str, defense: str, logdir: Path) -> list[Any]:
    return await benchmark_model(
        WORKSPACE,
        model=model,
        defense=defense,
        user_tasks=[email_user_task_0],
        injection_tasks=[web_injection_task_0],
        temperature=0.0,
        logdir=logdir,
    )


def test_every_benchmark_model_has_a_pinned_provider():
    assert MODEL_PROVIDERS.keys() == MODEL_NAMES.keys()


@pytest.mark.parametrize("model", MODEL_PROVIDERS)
async def test_each_models_request_asks_for_its_pinned_provider_without_fallbacks(
    client: type[FakeClient], tmp_path: Path, model: str
):
    await one_run(model, "none", tmp_path)

    assert client.requests == [(model, pinned(model))]


@pytest.mark.parametrize(
    ("defense", "replies"),
    [
        ("tool-filter", [completion("search_emails"), searching_emails()]),
        ("sanitizer", [searching_emails(), completion("Cleaned result.")]),
    ],
)
async def test_the_defenses_own_calls_ask_for_the_pinned_provider_too(
    client: type[FakeClient], tmp_path: Path, defense: str, replies: list[ChatCompletion]
):
    client.replies = replies

    [result] = await one_run(QWEN, defense, tmp_path)

    assert result.error is None
    assert result.usage.llm_calls == 3
    assert client.requests == [(QWEN, pinned(QWEN))] * 3


async def test_a_sweeps_requests_ask_for_each_models_pinned_provider(client: type[FakeClient], tmp_path: Path):
    specs = [RunSpec(MINI, "none", email_user_task_0), RunSpec(QWEN, "none", email_user_task_0)]

    await sweep_runs(WORKSPACE, specs, temperature=0.0, logdir=tmp_path)

    assert client.requests == [(MINI, pinned(MINI)), (QWEN, pinned(QWEN))]


async def test_an_unavailable_pinned_provider_makes_a_run_error(client: type[FakeClient], tmp_path: Path):
    request = httpx2.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    client.error = openai.NotFoundError(
        "No endpoints found matching your provider preferences",
        response=httpx2.Response(404, request=request),
        body=None,
    )

    [result] = await one_run(QWEN, "none", tmp_path)

    assert result.error == "NotFoundError: No endpoints found matching your provider preferences"
    assert (result.utility, result.security) == (None, None)
    [path] = tmp_path.rglob("*.json")
    assert json.loads(path.read_text())["error"] == result.error
