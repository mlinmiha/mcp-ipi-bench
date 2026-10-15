"""Tests for `check_suite`: the problems it finds in a suite, each naming the task or vector it is about."""

from pathlib import Path
from typing import Any

from pydantic import BaseModel

from mcp_ipi.domains import EMAIL
from mcp_ipi.domains.email import Inbox
from mcp_ipi.suites import SUITES, Suite, Task, TaskDifficulty, ToolCall, check_suite


def allow_all(tool_name: str, arguments: dict[str, Any]) -> str | None:
    return None


class InboxEnvironment(BaseModel):
    inbox: Inbox


INBOX_YAML = """
inbox:
  account_email: emma@example.com
  current_datetime: 2026-05-14T09:00:00Z
  received:
    - id: "0"
      sender: a@example.com
      recipients: [emma@example.com]
      subject: Alpha
      body: "First. {@inject:email_note}"
      timestamp: 2026-05-13T08:00:00Z
    - id: "1"
      sender: b@example.com
      recipients: [emma@example.com]
      subject: Beta
      body: "Second. {@inject:web_note}"
      timestamp: 2026-05-13T09:00:00Z
"""

VECTORS = """
email_note:
  description: "end of the Alpha email"
  default: "Bye."
web_note:
  description: "end of the Beta email, named as if it were a web vector"
  default: "Cheers."
"""

UNUSED_VECTOR = """
email_unused:
  description: "nowhere in the environment"
  default: "Unused."
"""

READ_ALPHA = [ToolCall("search_emails", {"query": "alpha"}), ToolCall("get_email_by_id", {"email_id": "0"})]


def make_task(
    task_id: str, calls: list[ToolCall] = READ_ALPHA, passes: bool = True, domain: str = "email"
) -> Task[InboxEnvironment]:
    return Task(
        id=task_id,
        prompt="Do it.",
        domain=domain,
        difficulty=TaskDifficulty.EASY,
        ground_truth_output="",
        ground_truth=lambda: calls,
        check=lambda *_: passes,
    )


def make_suite(
    tmp_path: Path,
    user_tasks: list[Task[InboxEnvironment]],
    injection_tasks: list[Task[InboxEnvironment]],
    vectors: str = VECTORS,
) -> Suite[InboxEnvironment]:
    (tmp_path / "environment.yaml").write_text(INBOX_YAML)
    (tmp_path / "injection_vectors.yaml").write_text(vectors)
    return Suite(
        name="test",
        domains=(EMAIL,),
        environment_cls=InboxEnvironment,
        data_path=tmp_path,
        user_tasks=tuple(user_tasks),
        injection_tasks=tuple(injection_tasks),
        security_policy=allow_all,
    )


def about(problems: list[str], task_or_vector_id: str) -> list[str]:
    return [problem for problem in problems if problem.startswith(f"{task_or_vector_id}: ")]


def test_workspace_has_no_problems():
    assert check_suite(SUITES["workspace"]) == []


def test_a_sound_suite_has_no_problems(tmp_path):
    assert (
        check_suite(make_suite(tmp_path, [make_task("email_user_task_0")], [make_task("email_injection_task_0")])) == []
    )


def test_a_failing_and_an_unknown_tool_ground_truth_are_both_reported(tmp_path):
    suite = make_suite(
        tmp_path,
        [make_task("email_user_task_0", passes=False), make_task("email_user_task_1")],
        [make_task("email_injection_task_0", [ToolCall("no_such_tool", {})])],
    )

    problems = check_suite(suite)

    assert len(about(problems, "email_user_task_0")) == 1
    assert about(problems, "email_user_task_1") == []
    (unknown_tool,) = about(problems, "email_injection_task_0")
    assert "no_such_tool" in unknown_tool


def test_a_task_with_an_unknown_domain_is_reported(tmp_path):
    suite = make_suite(
        tmp_path,
        [make_task("email_user_task_0")],
        [make_task("email_injection_task_0"), make_task("mail_injection_task_0", domain="mail")],
    )

    (problem,) = check_suite(suite)

    assert problem.startswith("mail_injection_task_0: ")
    assert "'mail'" in problem


def test_a_user_task_that_reads_no_vector_is_reported(tmp_path):
    suite = make_suite(tmp_path, [make_task("email_user_task_0", [])], [make_task("email_injection_task_0")])

    (problem,) = check_suite(suite)

    assert problem.startswith("email_user_task_0: ")


def test_a_user_task_that_reads_only_another_domains_vector_is_reported(tmp_path):
    read_beta = [ToolCall("search_emails", {"query": "beta"}), ToolCall("get_email_by_id", {"email_id": "1"})]
    suite = make_suite(tmp_path, [make_task("email_user_task_0", read_beta)], [make_task("email_injection_task_0")])

    (problem,) = check_suite(suite)

    assert problem.startswith("email_user_task_0: ")


def test_a_declared_vector_without_a_placeholder_is_reported(tmp_path):
    suite = make_suite(
        tmp_path,
        [make_task("email_user_task_0")],
        [make_task("email_injection_task_0")],
        vectors=VECTORS + UNUSED_VECTOR,
    )

    (problem,) = check_suite(suite)

    assert problem.startswith("email_unused: ")


def test_a_placeholder_without_a_declared_vector_is_the_only_problem_reported(tmp_path):
    suite = make_suite(
        tmp_path,
        [make_task("email_user_task_0")],
        [make_task("email_injection_task_0")],
        vectors=VECTORS.split("web_note:")[0],
    )

    assert check_suite(suite) == ["web_note: has a placeholder but is not declared"]


def test_an_injection_task_used_more_often_than_another_is_reported(tmp_path):
    # Three user tasks over two injection tasks: injection task 0 gets user tasks 0 and 2, injection task 1 only 1.
    suite = make_suite(
        tmp_path,
        [make_task(f"email_user_task_{k}") for k in range(3)],
        [make_task("email_injection_task_0"), make_task("email_injection_task_1")],
    )

    (problem,) = check_suite(suite)

    assert problem.startswith("email_injection_task_0: ")


def test_problems_of_different_kinds_are_all_returned_in_one_call(tmp_path):
    suite = make_suite(
        tmp_path,
        [make_task("email_user_task_0", passes=False), make_task("email_user_task_1", [])],
        [make_task("email_injection_task_0", domain="mail")],
        vectors=VECTORS + UNUSED_VECTOR,
    )

    problems = check_suite(suite)

    assert len(about(problems, "email_user_task_0")) == 1
    assert len(about(problems, "email_user_task_1")) == 1
    assert len(about(problems, "email_injection_task_0")) == 1
    assert len(about(problems, "email_unused")) == 1
