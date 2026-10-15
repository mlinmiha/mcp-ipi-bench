"""Tests for the issue tracking tools on hand-built trackers."""

from datetime import UTC, datetime

import pytest

from mcp_ipi.domains.issue_tracking import Comment, Issue, IssueInfo, Jira
from mcp_ipi.domains.issue_tracking.tools import add_comment, create_issue, get_issue, search_issues, update_issue


def make_jira() -> Jira:
    return Jira(
        current_user="me@corp.com",
        project="NL",
        current_datetime=datetime(2026, 5, 14, 9, 30, tzinfo=UTC),
        issues=[
            Issue(
                key="NL-1",
                summary="Billing export fails",
                description="The CSV export of invoices times out.",
                status="open",
                assignee="alice@corp.com",
                reporter="me@corp.com",
                comments=[
                    Comment(
                        id="0",
                        author="alice@corp.com",
                        body="Looking at the dashboard logs.",
                        created_at=datetime(2026, 5, 12, 11, 0, tzinfo=UTC),
                    )
                ],
            ),
            Issue(
                key="NL-2",
                summary="Dashboard loads slowly",
                description="Charts take ten seconds to appear.",
                status="in_progress",
                assignee="Bob@Corp.com",
                reporter="alice@corp.com",
            ),
            Issue(
                key="NL-10",
                summary="Update the onboarding guide",
                description="Add the new billing steps.",
                status="done",
                reporter="me@corp.com",
                comments=[
                    Comment(
                        id="3",
                        author="me@corp.com",
                        body="Done.",
                        created_at=datetime(2026, 5, 13, 16, 0, tzinfo=UTC),
                    )
                ],
            ),
        ],
    )


def make_search_jira(*issues: tuple[str, str]) -> Jira:
    return Jira(
        current_user="me@corp.com",
        project="NL",
        current_datetime=datetime(2026, 5, 14, 9, 30, tzinfo=UTC),
        issues=[
            Issue(
                key=f"NL-{index + 1}",
                summary=summary,
                description=description,
                status="open",
                reporter="me@corp.com",
            )
            for index, (summary, description) in enumerate(issues)
        ],
    )


def keys(issues: list[IssueInfo]) -> list[str]:
    return [issue.key for issue in issues]


def info(issue: Issue) -> IssueInfo:
    return IssueInfo(
        key=issue.key, summary=issue.summary, status=issue.status, assignee=issue.assignee, reporter=issue.reporter
    )


def test_search_issues_returns_matching_issues_without_description_and_comments_and_without_changing_tracker():
    jira = make_jira()
    before = jira.model_copy(deep=True)

    assert search_issues(jira, "BILLING") == [info(before.issues[0]), info(before.issues[2])]
    assert jira == before


def test_search_issues_matches_a_word_only_in_the_description():
    assert keys(search_issues(make_jira(), "charts")) == ["NL-2"]


def test_search_issues_ranks_issues_with_more_query_words_first():
    jira = make_search_jira(
        ("Notes", "The budget."), ("Offsite", "The budget for travel."), ("Trip", "Offsite travel.")
    )

    assert keys(search_issues(jira, "offsite budget travel")) == ["NL-2", "NL-3", "NL-1"]


def test_search_issues_keeps_tracker_order_for_equal_scores():
    jira = make_search_jira(("Budget", "Hi."), ("Travel", "Hi."), ("Budget", "And travel."))

    assert keys(search_issues(jira, "travel budget")) == ["NL-3", "NL-1", "NL-2"]


def test_search_issues_matches_words_split_across_summary_and_description():
    assert keys(search_issues(make_jira(), "invoices export billing")) == ["NL-1", "NL-10"]


def test_search_issues_leaves_out_issues_that_match_no_word():
    assert keys(search_issues(make_jira(), "charts payroll")) == ["NL-2"]


def test_search_issues_returns_empty_list_when_no_word_matches():
    assert search_issues(make_jira(), "payroll receipt") == []


def test_search_issues_matches_whole_words_case_insensitively():
    jira = make_search_jira(("Policy", "Written by HR."), ("Count", "Three items."))

    assert keys(search_issues(jira, "hr")) == ["NL-1"]
    assert keys(search_issues(jira, "THREE")) == ["NL-2"]
    assert keys(search_issues(jira, "polic")) == []


def test_search_issues_counts_a_repeated_query_word_once():
    jira = make_search_jira(("Budget", "Hi."), ("Travel", "And offsite."))

    assert keys(search_issues(jira, "budget budget budget travel offsite")) == ["NL-2", "NL-1"]


def test_search_issues_splits_query_and_issue_words_on_punctuation():
    jira = make_search_jira(("Re: follow-ups", "To do."), ("Demo", "Follow up."))

    assert keys(search_issues(jira, "follow-ups")) == ["NL-1", "NL-2"]
    assert keys(search_issues(jira, "re:")) == ["NL-1"]


def test_search_issues_does_not_match_comments():
    assert keys(search_issues(make_jira(), "logs")) == []
    assert keys(search_issues(make_jira(), "dashboard logs")) == ["NL-2"]


def test_search_issues_filters_by_status():
    assert keys(search_issues(make_jira(), "billing", status="done")) == ["NL-10"]
    assert keys(search_issues(make_jira(), "", status="in_progress")) == ["NL-2"]


def test_search_issues_filters_by_assignee_exactly_and_case_insensitively():
    jira = make_jira()

    assert keys(search_issues(jira, "", assignee="bob@corp.com")) == ["NL-2"]
    assert keys(search_issues(jira, "", assignee="ALICE@corp.com")) == ["NL-1"]
    assert keys(search_issues(jira, "", assignee="alice")) == []


def test_search_issues_filters_exclude_issues_that_match_more_words():
    jira = make_jira()

    assert keys(search_issues(jira, "billing export invoices csv", status="done")) == ["NL-10"]
    assert keys(search_issues(jira, "billing export dashboard", assignee="bob@corp.com")) == ["NL-2"]


def test_search_issues_combines_query_and_filters():
    jira = make_jira()

    assert keys(search_issues(jira, "billing", status="open", assignee="alice@corp.com")) == ["NL-1"]
    assert search_issues(jira, "billing", status="in_progress") == []


@pytest.mark.parametrize("query", ["", "  ", "-.,"])
def test_search_issues_returns_every_issue_that_passes_the_filters_for_a_query_without_words(query: str):
    assert keys(search_issues(make_jira(), query)) == ["NL-1", "NL-2", "NL-10"]
    assert keys(search_issues(make_jira(), query, status="done")) == ["NL-10"]
    assert keys(search_issues(make_jira(), query, assignee="alice@corp.com")) == ["NL-1"]


def test_get_issue_returns_the_header_description_and_comments_as_text_without_changing_tracker():
    jira = make_jira()
    add_comment(jira, "NL-1", "Found it.")
    before = jira.model_copy(deep=True)

    text = get_issue(jira, "NL-1")

    assert text == (
        "Key: NL-1\n"
        "Summary: Billing export fails\n"
        "Status: open\n"
        "Assignee: alice@corp.com\n"
        "Reporter: me@corp.com\n"
        "\n"
        "The CSV export of invoices times out.\n"
        "\n"
        "Comment by alice@corp.com, 2026-05-12 11:00:\n"
        "Looking at the dashboard logs.\n"
        "\n"
        "Comment by me@corp.com, 2026-05-14 09:30:\n"
        "Found it."
    )
    assert jira == before


def test_get_issue_leaves_out_empty_fields():
    jira = make_jira()
    create_issue(jira, "Fix login", "")

    assert get_issue(jira, "NL-11") == "Key: NL-11\nSummary: Fix login\nStatus: open\nReporter: me@corp.com\n\n"


def test_get_issue_rejects_unknown_key():
    with pytest.raises(ValueError, match="'NL-7' not found"):
        get_issue(make_jira(), "NL-7")


def test_create_issue_appends_open_issue_reported_by_current_user_and_returns_it_without_its_description():
    jira = make_jira()
    before = jira.model_copy(deep=True)

    issue = create_issue(jira, "Fix login", "Users are logged out.", assignee="bob@corp.com")

    expected = Issue(
        key="NL-11",
        summary="Fix login",
        description="Users are logged out.",
        status="open",
        assignee="bob@corp.com",
        reporter="me@corp.com",
        comments=[],
    )
    assert issue == info(expected)
    assert jira.issues == [*before.issues, expected]


def test_create_issue_without_assignee_is_unassigned():
    assert create_issue(make_jira(), "Fix login", "Users are logged out.").assignee is None


def test_create_issue_gives_key_one_to_first_issue_of_empty_project():
    jira = Jira(current_user="me@corp.com", project="NL", current_datetime=datetime(2026, 5, 14, 9, 30, tzinfo=UTC))

    assert create_issue(jira, "Fix login", "Users are logged out.").key == "NL-1"


def test_update_issue_changes_given_fields_only_and_returns_issue_without_its_description_and_comments():
    jira = make_jira()
    before = jira.model_copy(deep=True)

    issue = update_issue(jira, "NL-2", status="done", assignee="carol@corp.com")

    expected = before.issues[1].model_copy(update={"status": "done", "assignee": "carol@corp.com"})
    assert issue == info(expected)
    assert jira.issues == [before.issues[0], expected, before.issues[2]]


def test_update_issue_changes_summary():
    jira = make_jira()
    before = jira.model_copy(deep=True)

    update_issue(jira, "NL-1", summary="Billing CSV export fails")

    expected = before.issues[0].model_copy(update={"summary": "Billing CSV export fails"})
    assert jira.issues == [expected, *before.issues[1:]]


def test_update_issue_rejects_no_field():
    jira = make_jira()
    before = jira.model_copy(deep=True)

    with pytest.raises(ValueError, match="status, assignee or summary"):
        update_issue(jira, "NL-1")
    assert jira == before


def test_update_issue_rejects_unknown_key():
    jira = make_jira()
    before = jira.model_copy(deep=True)

    with pytest.raises(ValueError, match="'NL-7' not found"):
        update_issue(jira, "NL-7", status="done")
    assert jira == before


def test_add_comment_appends_comment_by_current_user_and_returns_the_issue_without_its_comments():
    jira = make_jira()
    before = jira.model_copy(deep=True)

    issue = add_comment(jira, "NL-2", "Fixed in the next release.")

    expected = Comment(
        id="4",
        author="me@corp.com",
        body="Fixed in the next release.",
        created_at=datetime(2026, 5, 14, 9, 30, tzinfo=UTC),
    )
    assert issue == info(before.issues[1])
    assert jira.issues == [
        before.issues[0],
        before.issues[1].model_copy(update={"comments": [expected]}),
        before.issues[2],
    ]


def test_add_comment_gives_id_zero_to_first_comment():
    jira = Jira(current_user="me@corp.com", project="NL", current_datetime=datetime(2026, 5, 14, 9, 30, tzinfo=UTC))
    create_issue(jira, "Fix login", "Users are logged out.")

    add_comment(jira, "NL-1", "On it.")

    assert jira.issues[0].comments[0].id == "0"


def test_add_comment_rejects_unknown_key():
    jira = make_jira()
    before = jira.model_copy(deep=True)

    with pytest.raises(ValueError, match="'NL-7' not found"):
        add_comment(jira, "NL-7", "On it.")
    assert jira == before
