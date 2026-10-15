"""Tests shared by all domains; each new domain adds itself to the tables below."""

import subprocess
import sys
from collections.abc import Callable
from typing import Any

import pytest
from pydantic import BaseModel

from mcp_ipi.domains import CALENDAR, CLOUD_STORAGE, EMAIL, ISSUE_TRACKING, WEB, Domain
from mcp_ipi.domains.calendar.tools import (
    add_calendar_event_participants,
    cancel_calendar_event,
    create_calendar_event,
    get_day_calendar_events,
    reschedule_calendar_event,
)
from mcp_ipi.domains.cloud_storage.tools import append_to_file, create_file, delete_file, list_files, share_file
from mcp_ipi.domains.email.tools import delete_email, get_unread_emails, send_email
from mcp_ipi.domains.issue_tracking.tools import add_comment, create_issue, get_issue, update_issue
from mcp_ipi.domains.web.tools import append_to_webpage, delete_webpage, get_webpage, post_webpage

from .test_calendar import make_calendar
from .test_cloud_storage import make_drive
from .test_email import make_inbox
from .test_issue_tracking import make_jira
from .test_web import make_web

# Expected spec per domain: (domain, name, component, tool names).
EXPECTED_DOMAINS = [
    (
        EMAIL,
        "email",
        "inbox",
        [
            "get_received_emails",
            "get_read_emails",
            "get_unread_emails",
            "search_emails",
            "get_email_by_id",
            "send_email",
            "delete_email",
        ],
    ),
    (
        CALENDAR,
        "calendar",
        "calendar",
        [
            "get_day_calendar_events",
            "search_calendar_events",
            "get_calendar_event_by_id",
            "create_calendar_event",
            "reschedule_calendar_event",
            "cancel_calendar_event",
            "add_calendar_event_participants",
        ],
    ),
    (
        CLOUD_STORAGE,
        "cloud_storage",
        "cloud_drive",
        [
            "list_files",
            "search_files",
            "get_file_by_id",
            "create_file",
            "append_to_file",
            "share_file",
            "delete_file",
        ],
    ),
    (
        WEB,
        "web",
        "web",
        ["search_web", "get_webpage", "post_webpage", "append_to_webpage", "delete_webpage"],
    ),
    (
        ISSUE_TRACKING,
        "issue_tracking",
        "jira",
        ["search_issues", "get_issue", "create_issue", "update_issue", "add_comment"],
    ),
]

# Per domain: a populated component factory and a sequence of tool calls (tool, kwargs) that change state.
CALL_SEQUENCES: list[tuple[Domain, Callable[[], BaseModel], list[tuple[Callable, dict[str, Any]]]]] = [
    (
        EMAIL,
        make_inbox,
        [
            (get_unread_emails, {}),
            (send_email, {"recipients": ["bob@partner.org"], "subject": "Lunch", "body": "Friday works."}),
            (delete_email, {"email_id": "0"}),
            (
                send_email,
                {
                    "recipients": ["alice@corp.com"],
                    "subject": "Report",
                    "body": "Sent again.",
                    "cc": ["bob@partner.org"],
                    "bcc": ["boss@corp.com"],
                },
            ),
        ],
    ),
    (
        CALENDAR,
        make_calendar,
        [
            (get_day_calendar_events, {"day": "2026-05-14"}),
            (
                create_calendar_event,
                {"title": "Sync", "start_time": "2026-05-18 09:00", "end_time": "2026-05-18 09:30"},
            ),
            (reschedule_calendar_event, {"event_id": "3", "new_start_time": "2026-05-18 10:00"}),
            (add_calendar_event_participants, {"event_id": "3", "participants": ["bob@partner.org"]}),
            (cancel_calendar_event, {"event_id": "0"}),
        ],
    ),
    (
        CLOUD_STORAGE,
        make_drive,
        [
            (list_files, {}),
            (create_file, {"filename": "todo.txt", "content": "Book the venue."}),
            (append_to_file, {"file_id": "2", "content": " And the catering."}),
            (share_file, {"file_id": "2", "email": "bob@partner.org", "permission": "rw"}),
            (delete_file, {"file_id": "0"}),
        ],
    ),
    (
        WEB,
        make_web,
        [
            (get_webpage, {"url": "https://www.travel-deals.com/"}),
            (post_webpage, {"url": "blog.me.com/post", "title": "My post", "content": "Hello."}),
            (append_to_webpage, {"url": "blog.me.com/post", "content": " More."}),
            (delete_webpage, {"url": "www.northline.com/menu"}),
        ],
    ),
    (
        ISSUE_TRACKING,
        make_jira,
        [
            (get_issue, {"key": "NL-1"}),
            (create_issue, {"summary": "Fix login", "description": "Users are logged out."}),
            (update_issue, {"key": "NL-11", "status": "in_progress", "assignee": "bob@corp.com"}),
            (add_comment, {"key": "NL-11", "body": "On it."}),
        ],
    ),
]

# Modules that importing `mcp_ipi.domains` must not load (checked in a fresh interpreter).
# Domains are the bottom layer: they may not depend on higher layers of this project
FORBIDDEN_IMPORTS = [
    "mcp_ipi.environment",
    "mcp_ipi.suites",
    "mcp_ipi.mcp",
    "mcp_ipi.agent",
    "mcp_ipi.runner",
    "mcp_ipi.attacks",
    "mcp_ipi.defenses",
    "mcp_ipi.analysis",
    "mcp_ipi.cli",
    "mcp",
]


@pytest.mark.parametrize(("domain", "name", "component", "tool_names"), EXPECTED_DOMAINS)
def test_exported_domain_has_expected_name_component_and_tools(
    domain: Domain, name: str, component: str, tool_names: list[str]
):
    assert domain.name == name
    assert domain.component == component
    assert sorted(tool.__name__ for tool in domain.tools) == sorted(tool_names)


@pytest.mark.parametrize("domain", [domain for domain, _, _, _ in EXPECTED_DOMAINS])
def test_domain_has_between_five_and_ten_tools(domain: Domain):
    assert 5 <= len(domain.tools) <= 10


def test_tool_names_are_unique_across_domains():
    names = [tool.__name__ for domain, _, _, _ in EXPECTED_DOMAINS for tool in domain.tools]

    assert len(names) == len(set(names))


@pytest.mark.parametrize(("domain", "make_component", "calls"), CALL_SEQUENCES)
def test_same_calls_on_equal_components_give_equal_results(
    domain: Domain, make_component: Callable[[], BaseModel], calls: list[tuple[Callable, dict[str, Any]]]
):
    first, second = make_component(), make_component()

    first_results = [tool(first, **kwargs) for tool, kwargs in calls]
    second_results = [tool(second, **kwargs) for tool, kwargs in calls]

    assert all(tool in domain.tools for tool, _ in calls)
    assert first_results == second_results
    assert first == second
    assert first != make_component()


def test_importing_domains_does_not_load_higher_layers_or_mcp_sdk():
    code = f"import sys, mcp_ipi.domains; print(*(m for m in {FORBIDDEN_IMPORTS!r} if m in sys.modules))"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)

    assert result.stdout.split() == []
