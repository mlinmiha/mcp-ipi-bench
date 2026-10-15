"""Tests for the generic `Suite`: its tool list, tool-to-domain map, tool-name check and ground truth check."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from mcp_ipi.domains import EMAIL, WEB
from mcp_ipi.domains.email import Inbox
from mcp_ipi.suites import Suite, Task, TaskDifficulty, ToolCall


def allow_all(tool_name: str, arguments: dict[str, Any]) -> str | None:
    return None


def make_suite(*domains) -> Suite:
    return Suite(
        name="test", domains=domains, environment_cls=BaseModel, data_path=Path("unused"), security_policy=allow_all
    )


def test_tools_are_all_domain_tools_in_domain_order():
    assert make_suite(EMAIL, WEB).tools == EMAIL.tools + WEB.tools


def test_tool_name_shared_by_two_domains_raises():
    with pytest.raises(ValueError, match="shared by two domains"):
        make_suite(EMAIL, EMAIL)


class InboxEnvironment(BaseModel):
    inbox: Inbox


INBOX_YAML = """
inbox:
  account_email: emma@example.com
  current_datetime: 2026-05-14T09:00:00Z
"""


def make_inbox_suite(tmp_path: Path) -> Suite[InboxEnvironment]:
    (tmp_path / "environment.yaml").write_text(INBOX_YAML)
    (tmp_path / "injection_vectors.yaml").write_text("{}")
    return Suite(
        name="test", domains=(EMAIL,), environment_cls=InboxEnvironment, data_path=tmp_path, security_policy=allow_all
    )


def make_task(
    ground_truth: Callable[[], list[ToolCall]],
    check: Callable[[str, InboxEnvironment, InboxEnvironment], bool],
    ground_truth_output: str = "",
) -> Task[InboxEnvironment]:
    return Task(
        id="email_user_task_0",
        prompt="Do it.",
        domain="email",
        difficulty=TaskDifficulty.EASY,
        ground_truth_output=ground_truth_output,
        ground_truth=ground_truth,
        check=check,
    )


def test_suite_without_tasks_has_empty_task_tuples():
    suite = make_suite(EMAIL, WEB)

    assert suite.user_tasks == ()
    assert suite.injection_tasks == ()


def test_check_ground_truth_runs_calls_on_post_environment_only(tmp_path):
    send = ToolCall("send_email", {"recipients": ["bob@example.com"], "subject": "Hi", "body": "Hello."})
    seen = {}

    def check(model_output: str, pre: InboxEnvironment, post: InboxEnvironment) -> bool:
        seen.update(pre=pre, post=post)
        return True

    assert make_inbox_suite(tmp_path).check_ground_truth(make_task(lambda: [send], check))
    assert seen["pre"].inbox.sent == []
    assert [email.subject for email in seen["post"].inbox.sent] == ["Hi"]


def test_check_ground_truth_returns_the_checks_verdict_on_the_ground_truth_output(tmp_path):
    suite = make_inbox_suite(tmp_path)

    def check(model_output: str, pre: InboxEnvironment, post: InboxEnvironment) -> bool:
        return model_output == "42"

    assert suite.check_ground_truth(make_task(lambda: [], check, ground_truth_output="42"))
    assert not suite.check_ground_truth(make_task(lambda: [], check, ground_truth_output="41"))


def test_check_ground_truth_with_unknown_tool_raises(tmp_path):
    task = make_task(lambda: [ToolCall("no_such_tool", {})], lambda *_: True)

    with pytest.raises(KeyError, match="no_such_tool"):
        make_inbox_suite(tmp_path).check_ground_truth(task)


def test_check_ground_truth_records_a_raising_tool_and_runs_the_next_call(tmp_path):
    delete = ToolCall("delete_email", {"email_id": "99"})
    send = ToolCall("send_email", {"recipients": ["bob@example.com"], "subject": "Hi", "body": "Hello."})

    def check(model_output: str, pre: InboxEnvironment, post: InboxEnvironment) -> bool:
        return [email.subject for email in post.inbox.sent] == ["Hi"]

    assert make_inbox_suite(tmp_path).check_ground_truth(make_task(lambda: [delete, send], check))


TWO_VECTOR_YAML = """
inbox:
  account_email: emma@example.com
  current_datetime: 2026-05-14T09:00:00Z
  received:
    - id: "0"
      sender: a@example.com
      recipients: [emma@example.com]
      subject: Alpha
      body: "First. {@inject:email_body}"
      timestamp: 2026-05-13T08:00:00Z
    - id: "1"
      sender: b@example.com
      recipients: [emma@example.com]
      subject: Beta
      body: "Second. {@inject:email_body_2}"
      timestamp: 2026-05-13T09:00:00Z
"""

TWO_VECTORS = """
email_body:
  description: "end of the Alpha email"
  default: "Bye."
email_body_2:
  description: "end of the Beta email"
  default: "Cheers."
"""


def make_two_vector_suite(tmp_path: Path) -> Suite[InboxEnvironment]:
    (tmp_path / "environment.yaml").write_text(TWO_VECTOR_YAML)
    (tmp_path / "injection_vectors.yaml").write_text(TWO_VECTORS)
    return Suite(
        name="test", domains=(EMAIL,), environment_cls=InboxEnvironment, data_path=tmp_path, security_policy=allow_all
    )


def reading(*email_ids: str) -> Task[InboxEnvironment]:
    return make_task(
        lambda: [ToolCall("get_email_by_id", {"email_id": email_id}) for email_id in email_ids], lambda *_: True
    )


def searching(*queries: str) -> Task[InboxEnvironment]:
    return make_task(lambda: [ToolCall("search_emails", {"query": query}) for query in queries], lambda *_: True)


def test_injection_vectors_read_returns_the_vector_in_the_email_read(tmp_path):
    assert make_two_vector_suite(tmp_path).injection_vectors_read(reading("0")) == ["email_body"]


def test_injection_vectors_read_does_not_report_a_vector_whose_id_is_a_prefix(tmp_path):
    assert make_two_vector_suite(tmp_path).injection_vectors_read(reading("1")) == ["email_body_2"]


def test_injection_vectors_read_returns_vectors_in_declaration_order(tmp_path):
    vectors = make_two_vector_suite(tmp_path).injection_vectors_read(reading("1", "0"))

    assert vectors == ["email_body", "email_body_2"]


def test_injection_vectors_read_returns_a_vector_read_twice_once(tmp_path):
    assert make_two_vector_suite(tmp_path).injection_vectors_read(reading("0", "0")) == ["email_body"]


def test_injection_vectors_read_without_vector_text_in_outputs_is_empty(tmp_path):
    suite = make_two_vector_suite(tmp_path)

    assert suite.injection_vectors_read(reading()) == []
    assert suite.injection_vectors_read(searching("gamma")) == []


def test_injection_vectors_read_does_not_report_a_vector_in_a_search_result_without_the_body(tmp_path):
    assert make_two_vector_suite(tmp_path).injection_vectors_read(searching("alpha", "bye")) == []


def test_injection_vectors_read_does_not_match_a_query_on_a_vector_id(tmp_path):
    assert make_two_vector_suite(tmp_path).injection_vectors_read(searching("body")) == []


def test_injection_vectors_read_with_unknown_tool_raises(tmp_path):
    task = make_task(lambda: [ToolCall("no_such_tool", {})], lambda *_: True)

    with pytest.raises(KeyError, match="no_such_tool"):
        make_two_vector_suite(tmp_path).injection_vectors_read(task)


def test_injection_vectors_read_records_a_raising_tool_and_runs_the_next_call(tmp_path):
    calls = [ToolCall("delete_email", {"email_id": "99"}), ToolCall("get_email_by_id", {"email_id": "0"})]
    task = make_task(lambda: calls, lambda *_: True)

    assert make_two_vector_suite(tmp_path).injection_vectors_read(task) == ["email_body"]
