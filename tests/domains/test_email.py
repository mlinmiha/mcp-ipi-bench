"""Tests for the email tools on hand-built inboxes."""

from datetime import UTC, datetime

import pytest

from mcp_ipi.domains.email import Email, EmailInfo, Inbox
from mcp_ipi.domains.email.tools import (
    delete_email,
    get_email_by_id,
    get_read_emails,
    get_received_emails,
    get_unread_emails,
    search_emails,
    send_email,
)


def make_inbox() -> Inbox:
    return Inbox(
        account_email="me@corp.com",
        current_datetime=datetime(2026, 5, 14, 9, 30, tzinfo=UTC),
        received=[
            Email(
                id="0",
                sender="alice@corp.com",
                recipients=["me@corp.com"],
                subject="Quarterly report",
                body="Please review the Q2 numbers.",
                timestamp=datetime(2026, 5, 13, 16, 0, tzinfo=UTC),
                read=True,
            ),
            Email(
                id="1",
                sender="bob@partner.org",
                recipients=["me@corp.com"],
                cc=["alice@corp.com"],
                subject="Lunch on Friday?",
                body="Are you free for lunch this week?",
                timestamp=datetime(2026, 5, 14, 8, 15, tzinfo=UTC),
                read=False,
            ),
        ],
        sent=[
            Email(
                id="2",
                sender="me@corp.com",
                recipients=["alice@corp.com"],
                bcc=["boss@corp.com"],
                subject="Re: Quarterly report",
                body="Numbers look good, report attached.",
                timestamp=datetime(2026, 5, 13, 17, 5, tzinfo=UTC),
                read=True,
            ),
        ],
    )


def info(email: Email) -> EmailInfo:
    return EmailInfo(
        id=email.id,
        sender=email.sender,
        recipients=email.recipients,
        cc=email.cc,
        bcc=email.bcc,
        subject=email.subject,
        timestamp=email.timestamp,
        read=email.read,
    )


def test_get_received_emails_returns_all_received_emails_without_their_body_and_without_changing_inbox():
    inbox = make_inbox()
    before = inbox.model_copy(deep=True)

    emails = get_received_emails(inbox)

    assert emails == [info(email) for email in before.received]
    assert inbox == before


def test_get_read_emails_returns_read_received_emails_without_their_body_and_without_changing_inbox():
    inbox = make_inbox()
    before = inbox.model_copy(deep=True)

    emails = get_read_emails(inbox)

    assert emails == [info(before.received[0])]
    assert inbox == before


def test_get_unread_emails_returns_unread_received_emails_without_their_body_and_without_changing_inbox():
    inbox = make_inbox()
    before = inbox.model_copy(deep=True)

    emails = get_unread_emails(inbox)

    assert emails == [info(before.received[1])]
    assert inbox == before


def make_search_inbox(*emails: tuple[str, str, str]) -> Inbox:
    return Inbox(
        account_email="me@corp.com",
        current_datetime=datetime(2026, 5, 14, 9, 30, tzinfo=UTC),
        received=[
            Email(
                id=str(index),
                sender=sender,
                recipients=["me@corp.com"],
                subject=subject,
                body=body,
                timestamp=datetime(2026, 5, 13, 16, 0, tzinfo=UTC),
            )
            for index, (sender, subject, body) in enumerate(emails)
        ],
    )


def search_ids(inbox: Inbox, query: str, sender: str | None = None) -> list[str]:
    return [email.id for email in search_emails(inbox, query, sender)]


def test_search_emails_returns_matching_received_and_sent_emails_without_their_body_and_without_changing_inbox():
    inbox = make_inbox()
    before = inbox.model_copy(deep=True)

    assert search_emails(inbox, "QUARTERLY") == [info(before.received[0]), info(before.sent[0])]
    assert search_emails(inbox, "lunch") == [info(before.received[1])]
    assert inbox == before


def test_search_emails_matches_a_word_only_in_the_body():
    assert search_ids(make_inbox(), "free") == ["1"]


def test_search_emails_ranks_emails_with_more_query_words_first():
    inbox = make_search_inbox(
        ("a@corp.com", "Notes", "The budget."),
        ("a@corp.com", "Offsite", "The budget for travel."),
        ("a@corp.com", "Trip", "Offsite travel."),
    )

    assert search_ids(inbox, "offsite budget travel") == ["1", "2", "0"]


def test_search_emails_keeps_inbox_order_for_equal_scores():
    inbox = make_search_inbox(
        ("a@corp.com", "Budget", "Hi."), ("a@corp.com", "Travel", "Hi."), ("a@corp.com", "Budget", "And travel.")
    )

    assert search_ids(inbox, "travel budget") == ["2", "0", "1"]


def test_search_emails_keeps_received_before_sent_for_equal_scores():
    assert search_ids(make_inbox(), "report quarterly numbers") == ["0", "2"]
    assert search_ids(make_inbox(), "attached lunch") == ["1", "2"]


def test_search_emails_matches_words_split_across_subject_and_body():
    assert search_ids(make_inbox(), "quarterly Q2") == ["0", "2"]


def test_search_emails_leaves_out_emails_that_match_no_word():
    assert search_ids(make_inbox(), "lunch invoice") == ["1"]


def test_search_emails_returns_empty_list_when_no_word_matches():
    assert search_emails(make_inbox(), "invoice receipt") == []


def test_search_emails_matches_whole_words_case_insensitively():
    inbox = make_search_inbox(("a@corp.com", "Policy", "Written by HR."), ("a@corp.com", "Count", "Three items."))

    assert search_ids(inbox, "hr") == ["0"]
    assert search_ids(inbox, "THREE") == ["1"]
    assert search_ids(inbox, "polic") == []


def test_search_emails_counts_a_repeated_query_word_once():
    inbox = make_search_inbox(("a@corp.com", "Budget", "Hi."), ("a@corp.com", "Travel", "And offsite."))

    assert search_ids(inbox, "budget budget budget travel offsite") == ["1", "0"]


def test_search_emails_splits_query_and_email_words_on_punctuation():
    inbox = make_search_inbox(("a@corp.com", "Re: follow-ups", "To do."), ("a@corp.com", "Demo", "Follow up."))

    assert search_ids(inbox, "follow-ups") == ["0", "1"]
    assert search_ids(inbox, "re:") == ["0"]


def test_search_emails_filters_by_sender_case_insensitively():
    assert search_ids(make_inbox(), "report", sender="Me@Corp.com") == ["2"]


def test_search_emails_sender_filter_excludes_emails_that_match_more_words():
    assert search_ids(make_inbox(), "quarterly report Q2 numbers review", sender="me@corp.com") == ["2"]
    assert search_ids(make_inbox(), "lunch", sender="me@corp.com") == []


@pytest.mark.parametrize("query", ["", "  ", "-.,"])
def test_search_emails_returns_every_email_that_passes_the_filter_for_a_query_without_words(query: str):
    assert search_ids(make_inbox(), query) == ["0", "1", "2"]
    assert search_ids(make_inbox(), query, sender="alice@corp.com") == ["0"]


def test_get_email_by_id_returns_the_header_and_body_as_text_without_changing_inbox():
    inbox = make_inbox()
    before = inbox.model_copy(deep=True)

    text = get_email_by_id(inbox, "1")

    assert text == (
        "From: bob@partner.org\n"
        "To: me@corp.com\n"
        "Cc: alice@corp.com\n"
        "Subject: Lunch on Friday?\n"
        "Date: 2026-05-14 08:15\n"
        "\n"
        "Are you free for lunch this week?"
    )
    assert inbox == before


def test_get_email_by_id_reads_a_sent_email_and_joins_the_addresses():
    inbox = make_inbox()
    inbox.sent[0].recipients.append("bob@partner.org")

    assert get_email_by_id(inbox, "2") == (
        "From: me@corp.com\n"
        "To: alice@corp.com, bob@partner.org\n"
        "Bcc: boss@corp.com\n"
        "Subject: Re: Quarterly report\n"
        "Date: 2026-05-13 17:05\n"
        "\n"
        "Numbers look good, report attached."
    )


def test_get_email_by_id_leaves_out_empty_cc_and_bcc():
    text = get_email_by_id(make_inbox(), "0")

    assert "Cc:" not in text
    assert "Bcc:" not in text


def test_get_email_by_id_rejects_unknown_id():
    with pytest.raises(ValueError, match="'7' not found"):
        get_email_by_id(make_inbox(), "7")


def test_send_email_appends_new_email_to_sent_and_returns_it_without_its_body():
    inbox = make_inbox()
    before = inbox.model_copy(deep=True)

    email = send_email(
        inbox, ["bob@partner.org"], "Lunch", "Friday works.", cc=["alice@corp.com"], bcc=["carol@corp.com"]
    )

    expected = Email(
        id="3",
        sender="me@corp.com",
        recipients=["bob@partner.org"],
        cc=["alice@corp.com"],
        bcc=["carol@corp.com"],
        subject="Lunch",
        body="Friday works.",
        timestamp=datetime(2026, 5, 14, 9, 30, tzinfo=UTC),
        read=True,
    )
    assert email == info(expected)
    assert inbox.sent == [*before.sent, expected]
    assert inbox.received == before.received


def test_send_email_defaults_to_no_cc_or_bcc():
    email = send_email(make_inbox(), ["bob@partner.org"], "Lunch", "Friday works.")

    assert (email.cc, email.bcc) == ([], [])


def test_send_email_gives_id_zero_to_first_email():
    inbox = Inbox(account_email="me@corp.com", current_datetime=datetime(2026, 5, 14, 9, 30, tzinfo=UTC))

    assert send_email(inbox, ["bob@partner.org"], "Hi", "Hello").id == "0"


def test_send_email_rejects_empty_recipients():
    inbox = make_inbox()
    before = inbox.model_copy(deep=True)

    with pytest.raises(ValueError, match="recipient"):
        send_email(inbox, [], "Lunch", "Friday works.")
    assert inbox == before


def test_delete_email_removes_received_email_and_returns_it_without_its_body():
    inbox = make_inbox()
    before = inbox.model_copy(deep=True)

    email = delete_email(inbox, "1")

    assert email == info(before.received[1])
    assert inbox.received == [before.received[0]]
    assert inbox.sent == before.sent


def test_delete_email_removes_sent_email_and_returns_it_without_its_body():
    inbox = make_inbox()
    before = inbox.model_copy(deep=True)

    email = delete_email(inbox, "2")

    assert email == info(before.sent[0])
    assert inbox.sent == []
    assert inbox.received == before.received


def test_delete_email_rejects_unknown_id():
    inbox = make_inbox()
    before = inbox.model_copy(deep=True)

    with pytest.raises(ValueError, match="'7' not found"):
        delete_email(inbox, "7")
    assert inbox == before
