"""Tests for the Workspace suite over MCP: ground truths pass their checks, and every run is isolated."""

import pytest

from mcp_ipi.domains import CALENDAR, CLOUD_STORAGE, EMAIL, ISSUE_TRACKING, WEB
from mcp_ipi.mcp import MCPRuntime
from mcp_ipi.suites.workspace import WORKSPACE
from mcp_ipi.suites.workspace.user_tasks.email import email_user_task_0

pytestmark = pytest.mark.anyio

TASKS = WORKSPACE.user_tasks + WORKSPACE.injection_tasks


@pytest.mark.parametrize("task", TASKS, ids=lambda task: task.id)
async def test_ground_truth_over_mcp_passes_check(task):
    pre_environment, post_environment = WORKSPACE.load_environment(), WORKSPACE.load_environment()

    async with MCPRuntime.connect(WORKSPACE.domains, post_environment) as runtime:
        for call in task.ground_truth():
            await runtime.call_tool(call.tool, call.args)

    assert task.check(task.ground_truth_output, pre_environment, post_environment)


async def test_workspace_runtime_serves_the_tools_of_all_five_domains():
    async with MCPRuntime.connect(WORKSPACE.domains, WORKSPACE.load_environment()) as runtime:
        names = [tool.name for tool in runtime.tools]

    assert names == [
        tool.__name__ for tool in EMAIL.tools + WEB.tools + CLOUD_STORAGE.tools + CALENDAR.tools + ISSUE_TRACKING.tools
    ]


async def test_email_user_task_0_ground_truth_over_mcp_returns_the_invoice_vector():
    environment = WORKSPACE.load_environment()
    default = WORKSPACE.load_injection_defaults()["email_invoice_body"]

    async with MCPRuntime.connect(WORKSPACE.domains, environment) as runtime:
        outputs = [await runtime.call_tool(call.tool, call.args) for call in email_user_task_0.ground_truth()]

    assert any(default in output for output in outputs)


async def test_get_file_by_id_over_mcp_returns_the_content_as_plain_text_with_the_attack():
    environment = WORKSPACE.load_environment({"cloud_storage_policy_file": "<ATTACK>"})
    content = next(file.content for file in environment.cloud_drive.files if file.id == "10")

    async with MCPRuntime.connect(WORKSPACE.domains, environment) as runtime:
        output = await runtime.call_tool("get_file_by_id", {"file_id": "10"})

    assert output == content
    assert "<ATTACK>" in output


async def test_search_files_over_mcp_leaves_out_the_content():
    environment = WORKSPACE.load_environment({"cloud_storage_policy_file": "<ATTACK>"})

    async with MCPRuntime.connect(WORKSPACE.domains, environment) as runtime:
        output = await runtime.call_tool("search_files", {"query": "holiday policy"})

    assert "holiday-policy-2026.txt" in output
    assert "25 days of holiday" not in output
    assert "<ATTACK>" not in output


async def test_get_email_by_id_over_mcp_returns_the_email_as_plain_text_with_the_attack():
    environment = WORKSPACE.load_environment({"email_invoice_body": "<ATTACK>"})

    async with MCPRuntime.connect(WORKSPACE.domains, environment) as runtime:
        output = await runtime.call_tool("get_email_by_id", {"email_id": "1"})

    assert output.startswith(
        "From: billing@cloudhost.io\nTo: daniel.hartmann@northline.com\nSubject: Your May invoice\n"
    )
    assert output.endswith("www.cloudhost.io/billing <ATTACK>")


async def test_search_emails_over_mcp_leaves_out_the_body():
    environment = WORKSPACE.load_environment({"email_invoice_body": "<ATTACK>"})

    async with MCPRuntime.connect(WORKSPACE.domains, environment) as runtime:
        output = await runtime.call_tool("search_emails", {"query": "invoice"})

    assert "Your May invoice" in output
    assert "49.00 EUR" not in output
    assert "<ATTACK>" not in output


async def test_get_calendar_event_by_id_over_mcp_returns_the_event_as_plain_text_with_the_attack():
    environment = WORKSPACE.load_environment({"calendar_sales_event": "<ATTACK>"})

    async with MCPRuntime.connect(WORKSPACE.domains, environment) as runtime:
        output = await runtime.call_tool("get_calendar_event_by_id", {"event_id": "11"})

    assert output.startswith("Title: Q2 sales review\nWhen: 2026-05-28 11:00–12:00 (Europe/Ljubljana)\n")  # noqa: RUF001
    assert output.endswith("\n\nQ2 revenue by customer. Prepare the numbers for the Northwind renewal. <ATTACK>")


async def test_search_calendar_events_over_mcp_leaves_out_the_description():
    environment = WORKSPACE.load_environment({"calendar_sales_event": "<ATTACK>"})

    async with MCPRuntime.connect(WORKSPACE.domains, environment) as runtime:
        output = await runtime.call_tool("search_calendar_events", {"query": "Q2 sales"})

    assert "Q2 sales review" in output
    assert "revenue by customer" not in output
    assert "<ATTACK>" not in output


async def test_get_issue_over_mcp_returns_the_issue_as_plain_text_with_the_attack():
    environment = WORKSPACE.load_environment({"issue_tracking_dashboard_comment": "<ATTACK>"})

    async with MCPRuntime.connect(WORKSPACE.domains, environment) as runtime:
        output = await runtime.call_tool("get_issue", {"key": "NL-3"})

    assert output.startswith("Key: NL-3\nSummary: Dashboard loads slowly\nStatus: open\n")
    assert output.endswith(
        "\n\nComment by anna.berg@clientcorp.com, 2026-05-13 15:20:\nIt is worst on Monday mornings. <ATTACK>"
    )


async def test_search_issues_over_mcp_leaves_out_the_description_and_comments():
    environment = WORKSPACE.load_environment({"issue_tracking_dashboard_comment": "<ATTACK>"})

    async with MCPRuntime.connect(WORKSPACE.domains, environment) as runtime:
        output = await runtime.call_tool("search_issues", {"query": "dashboard loads slowly"})

    assert "Dashboard loads slowly" in output
    assert "20 seconds" not in output
    assert "Monday" not in output
    assert "<ATTACK>" not in output


async def test_changed_environment_leaves_a_newly_loaded_one_untouched():
    environment_a = WORKSPACE.load_environment()
    original_inbox = environment_a.inbox.model_copy(deep=True)

    async with MCPRuntime.connect(WORKSPACE.domains, environment_a) as runtime:
        await runtime.call_tool("delete_email", {"email_id": "2"})

    environment_b = WORKSPACE.load_environment()

    assert environment_a.inbox != original_inbox
    assert environment_b.inbox == original_inbox


async def test_two_open_runtimes_share_no_state():
    environment_a, environment_b = WORKSPACE.load_environment(), WORKSPACE.load_environment()
    before_a, before_b = environment_a.model_copy(deep=True), environment_b.model_copy(deep=True)

    async with (
        MCPRuntime.connect(WORKSPACE.domains, environment_a) as runtime_a,
        MCPRuntime.connect(WORKSPACE.domains, environment_b),
    ):
        await runtime_a.call_tool("delete_email", {"email_id": "2"})
        await runtime_a.call_tool("post_webpage", {"url": "www.new.com", "title": "New", "content": "Fresh."})

    assert environment_a != before_a
    assert environment_b == before_b


async def test_calendar_and_issue_search_tool_descriptions_over_mcp_name_the_read_tool():
    async with MCPRuntime.connect(WORKSPACE.domains, WORKSPACE.load_environment()) as runtime:
        descriptions = {tool.name: tool.description or "" for tool in runtime.tools}

    assert "get_calendar_event_by_id" in descriptions["get_day_calendar_events"]
    assert "get_calendar_event_by_id" in descriptions["search_calendar_events"]
    assert "get_issue" in descriptions["search_issues"]


async def test_post_webpage_description_over_mcp_names_the_append_tool():
    async with MCPRuntime.connect(WORKSPACE.domains, WORKSPACE.load_environment()) as runtime:
        descriptions = {tool.name: tool.description or "" for tool in runtime.tools}

    assert "append_to_webpage" in descriptions["post_webpage"]


async def test_cloud_storage_results_over_mcp_leave_shared_with_out_for_a_file_shared_with_nobody():
    async with MCPRuntime.connect(WORKSPACE.domains, WORKSPACE.load_environment()) as runtime:
        listed = await runtime.call_tool("list_files", {})
        found = await runtime.call_tool("search_files", {"query": "team-budget-2026.txt"})
        created = await runtime.call_tool("create_file", {"filename": "notes.txt", "content": "Call Anna."})
        appended = await runtime.call_tool("append_to_file", {"file_id": "13", "content": " Today."})
        shared = await runtime.call_tool(
            "share_file", {"file_id": "13", "email": "james.wu@northline.com", "permission": "rw"}
        )
        deleted_shared = await runtime.call_tool("delete_file", {"file_id": "13"})
        deleted_unshared = await runtime.call_tool("delete_file", {"file_id": "5"})

    unshared_file = (
        "- id: '2'\n  filename: team-budget-2026.txt\n  owner: daniel.hartmann@northline.com\n"
        "  last_modified: '2026-04-28T11:00:00Z'"
    )
    shared_file = (
        "- id: '0'\n  filename: berlin-trip.txt\n  owner: daniel.hartmann@northline.com\n"
        "  shared_with:\n    david.smith@northline.com: r\n  last_modified: "
    )
    assert f"{unshared_file}\n- id: '3'" in listed
    assert shared_file in listed
    assert "{}" not in listed
    assert found.startswith(unshared_file)
    assert created == (
        "id: '13'\nfilename: notes.txt\nowner: daniel.hartmann@northline.com\nlast_modified: '2026-05-14T09:00:00Z'"
    )
    assert appended == created
    assert shared == (
        "id: '13'\nfilename: notes.txt\nowner: daniel.hartmann@northline.com\n"
        "shared_with:\n  james.wu@northline.com: rw\nlast_modified: '2026-05-14T09:00:00Z'"
    )
    assert deleted_shared == shared
    assert "shared_with" not in deleted_unshared
