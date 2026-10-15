"""Tests for `MCPRuntime` over the email and web domains: tool list, routing, results and errors."""

from datetime import UTC, datetime

import pytest
import yaml
from pydantic import BaseModel

from mcp_ipi.domains import EMAIL, WEB
from mcp_ipi.domains.email import Email, Inbox
from mcp_ipi.domains.email.tools import search_emails
from mcp_ipi.domains.web import Page, Web
from mcp_ipi.mcp import MCPRuntime

pytestmark = pytest.mark.anyio


class EmailWebEnvironment(BaseModel):
    inbox: Inbox
    web: Web


def make_environment() -> EmailWebEnvironment:
    return EmailWebEnvironment(
        inbox=Inbox(
            account_email="me@corp.com",
            current_datetime=datetime(2026, 5, 14, 9, 30, tzinfo=UTC),
            received=[
                Email(
                    id="0",
                    sender="alice@corp.com",
                    recipients=["me@corp.com"],
                    subject="Invoice",
                    body="Please pay the invoice.",
                    timestamp=datetime(2026, 5, 13, 16, 0, tzinfo=UTC),
                ),
            ],
        ),
        web=Web(pages=[Page(url="www.example.com", title="Example", content="Hello from the web.")]),
    )


async def test_runtime_over_one_domain_lists_its_tools_in_order():
    async with MCPRuntime.connect((EMAIL,), make_environment()) as runtime:
        assert [tool.name for tool in runtime.tools] == [tool.__name__ for tool in EMAIL.tools]


async def test_runtime_over_two_domains_lists_tools_in_domain_order():
    async with MCPRuntime.connect((EMAIL, WEB), make_environment()) as runtime:
        assert [tool.name for tool in runtime.tools] == [tool.__name__ for tool in EMAIL.tools + WEB.tools]


async def test_tool_schema_has_the_tool_arguments_without_the_component():
    async with MCPRuntime.connect((EMAIL,), make_environment()) as runtime:
        tool = next(tool for tool in runtime.tools if tool.name == "search_emails")

    assert set(tool.input_schema["properties"]) == {"query", "sender"}
    assert tool.input_schema["required"] == ["query"]
    assert tool.description == search_emails.__doc__


async def test_calls_change_the_environment_passed_in_through_the_owning_server():
    environment = make_environment()
    before = environment.model_copy(deep=True)

    async with MCPRuntime.connect((EMAIL, WEB), environment) as runtime:
        await runtime.call_tool("send_email", {"recipients": ["bob@corp.com"], "subject": "Hi", "body": "Hello."})
        assert environment.web == before.web

        after_email = environment.inbox.model_copy(deep=True)
        await runtime.call_tool("post_webpage", {"url": "www.new.com", "title": "New", "content": "Fresh."})
        assert environment.inbox == after_email

    assert [email.subject for email in environment.inbox.sent] == ["Hi"]
    assert [page.url for page in environment.web.pages] == ["www.example.com", "www.new.com"]


async def test_records_come_back_as_one_yaml_text():
    environment = make_environment()

    async with MCPRuntime.connect((EMAIL,), environment) as runtime:
        text = await runtime.call_tool("search_emails", {"query": "invoice"})

    assert yaml.safe_load(text) == [
        email.model_dump(mode="json", exclude={"body"}) for email in environment.inbox.received
    ]


async def test_no_matches_come_back_as_empty_list_text():
    async with MCPRuntime.connect((EMAIL,), make_environment()) as runtime:
        assert await runtime.call_tool("search_emails", {"query": "nothing like this"}) == "[]"


async def test_string_result_comes_back_unchanged():
    async with MCPRuntime.connect((WEB,), make_environment()) as runtime:
        assert await runtime.call_tool("get_webpage", {"url": "www.example.com"}) == "Hello from the web."


async def test_raising_tool_comes_back_as_error_type_and_message():
    environment = make_environment()
    before = environment.model_copy(deep=True)

    async with MCPRuntime.connect((EMAIL,), environment) as runtime:
        text = await runtime.call_tool("delete_email", {"email_id": "99"})

    assert text == "ValueError: Email with ID '99' not found"
    assert environment == before


async def test_missing_required_argument_comes_back_as_error_text():
    environment = make_environment()
    before = environment.model_copy(deep=True)

    async with MCPRuntime.connect((EMAIL,), environment) as runtime:
        text = await runtime.call_tool("send_email", {"subject": "Hi", "body": "Hello."})

    assert "recipients" in text
    assert environment == before


async def test_unknown_tool_raises_key_error():
    async with MCPRuntime.connect((EMAIL,), make_environment()) as runtime:
        with pytest.raises(KeyError, match="no_such_tool"):
            await runtime.call_tool("no_such_tool", {})


async def test_error_in_body_propagates_out_of_the_runtime_inside_the_sdk_exception_group():
    with pytest.RaisesGroup(pytest.RaisesExc(RuntimeError, match="boom"), flatten_subgroups=True):
        async with MCPRuntime.connect((EMAIL, WEB), make_environment()):
            raise RuntimeError("boom")
