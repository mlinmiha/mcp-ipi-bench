"""Tests for the calendar tools on hand-built calendars."""

import re
from datetime import date, datetime, timedelta

import pytest

from mcp_ipi.domains.calendar import Calendar, CalendarEvent, CalendarEventInfo
from mcp_ipi.domains.calendar.tools import (
    add_calendar_event_participants,
    cancel_calendar_event,
    create_calendar_event,
    get_calendar_event_by_id,
    get_day_calendar_events,
    reschedule_calendar_event,
    search_calendar_events,
)


def make_calendar() -> Calendar:
    return Calendar(
        account_email="me@corp.com",
        default_timezone="Europe/Ljubljana",
        current_day=date(2026, 5, 14),
        events=[
            CalendarEvent(
                id="0",
                title="Budget review",
                description="Go through the Q2 budget.",
                start_time=datetime(2026, 5, 14, 10, 0),
                end_time=datetime(2026, 5, 14, 11, 0),
                location="Room 2",
                organizer="me@corp.com",
                participants=["me@corp.com", "alice@corp.com"],
            ),
            CalendarEvent(
                id="1",
                title="Offsite planning",
                description="Pick the venue.",
                start_time=datetime(2026, 5, 15, 14, 0),
                end_time=datetime(2026, 5, 15, 15, 30),
                location="Lakeside Hotel",
                organizer="alice@corp.com",
                participants=["alice@corp.com", "me@corp.com"],
            ),
            CalendarEvent(
                id="2",
                title="Team lunch",
                description="Budget for the lunch is set.",
                start_time=datetime(2026, 5, 14, 12, 0),
                end_time=datetime(2026, 5, 14, 13, 0),
                location="Canteen",
                organizer="me@corp.com",
                participants=["me@corp.com"],
                status="canceled",
            ),
        ],
    )


def add_new_york_event(calendar: Calendar, event_id: str, start_time: datetime) -> CalendarEvent:
    """Append a one-hour event whose times are New York time (6 hours behind Ljubljana in May)."""
    event = CalendarEvent(
        id=event_id,
        title="Investor call",
        start_time=start_time,
        end_time=start_time + timedelta(hours=1),
        timezone="America/New_York",
        organizer="me@corp.com",
    )
    calendar.events.append(event)
    return event


def info(event: CalendarEvent) -> CalendarEventInfo:
    return CalendarEventInfo(
        id=event.id,
        title=event.title,
        start_time=event.start_time,
        end_time=event.end_time,
        timezone=event.timezone,
        location=event.location,
        organizer=event.organizer,
        participants=event.participants,
        status=event.status,
    )


def test_get_day_calendar_events_returns_confirmed_events_of_the_day_without_description_or_change():
    calendar = make_calendar()
    before = calendar.model_copy(deep=True)

    events = get_day_calendar_events(calendar, "2026-05-14")

    assert events == [info(before.events[0])]
    assert calendar == before


def test_get_day_calendar_events_returns_empty_list_for_a_day_without_events():
    assert get_day_calendar_events(make_calendar(), "2026-05-16") == []


def test_get_day_calendar_events_takes_the_day_of_an_event_in_another_timezone_in_the_default_timezone():
    calendar = make_calendar()
    evening = add_new_york_event(calendar, "3", datetime(2026, 5, 14, 19, 0))  # 01:00 on May 15 in Ljubljana
    morning = add_new_york_event(calendar, "4", datetime(2026, 5, 14, 9, 0))  # 15:00 on May 14 in Ljubljana

    assert get_day_calendar_events(calendar, "2026-05-14") == [info(calendar.events[0]), info(morning)]
    assert get_day_calendar_events(calendar, "2026-05-15") == [info(calendar.events[1]), info(evening)]


@pytest.mark.parametrize("day", ["14.5.2026", "2026-05-14 10:00", "2026-13-01", ""])
def test_get_day_calendar_events_rejects_malformed_day(day: str):
    with pytest.raises(ValueError, match=re.escape(repr(day))):
        get_day_calendar_events(make_calendar(), day)


def make_search_calendar(*events: tuple[str, str, str]) -> Calendar:
    return Calendar(
        account_email="me@corp.com",
        default_timezone="Europe/Ljubljana",
        current_day=date(2026, 5, 14),
        events=[
            CalendarEvent(
                id=str(index),
                title=title,
                description=description,
                start_time=datetime(2026, 5, 14, 10, 0),
                end_time=datetime(2026, 5, 14, 11, 0),
                location=location,
                organizer="me@corp.com",
            )
            for index, (title, description, location) in enumerate(events)
        ],
    )


def search_ids(calendar: Calendar, query: str, day: str | None = None) -> list[str]:
    return [event.id for event in search_calendar_events(calendar, query, day)]


def test_search_calendar_events_returns_matching_events_without_their_description_and_without_changing_calendar():
    calendar = make_calendar()
    before = calendar.model_copy(deep=True)

    assert search_calendar_events(calendar, "BUDGET") == [info(before.events[0])]
    assert search_calendar_events(calendar, "lakeside") == [info(before.events[1])]
    assert calendar == before


def test_search_calendar_events_matches_a_word_only_in_the_description():
    assert search_ids(make_calendar(), "venue") == ["1"]


def test_search_calendar_events_ranks_events_with_more_query_words_first():
    calendar = make_search_calendar(
        ("Budget", "", ""),
        ("Offsite budget", "Travel.", ""),
        ("Offsite", "", "Travel agency"),
    )

    assert search_ids(calendar, "offsite budget travel") == ["1", "2", "0"]


def test_search_calendar_events_keeps_calendar_order_for_equal_scores():
    calendar = make_search_calendar(("Budget", "", ""), ("Travel", "", ""), ("Budget and travel", "", ""))

    assert search_ids(calendar, "travel budget") == ["2", "0", "1"]


def test_search_calendar_events_matches_words_split_across_fields():
    assert search_ids(make_calendar(), "hotel offsite venue") == ["1"]


def test_search_calendar_events_leaves_out_events_that_match_no_word():
    assert search_ids(make_calendar(), "venue invoice") == ["1"]


def test_search_calendar_events_returns_empty_list_when_no_word_matches():
    assert search_calendar_events(make_calendar(), "invoice receipt") == []


def test_search_calendar_events_matches_whole_words_case_insensitively():
    calendar = make_search_calendar(("HR sync", "", ""), ("Count", "Three items.", ""))

    assert search_ids(calendar, "hr") == ["0"]
    assert search_ids(calendar, "THREE") == ["1"]
    assert search_ids(calendar, "syn") == []


def test_search_calendar_events_counts_a_repeated_query_word_once():
    calendar = make_search_calendar(("Budget", "", ""), ("Travel", "Offsite.", ""))

    assert search_ids(calendar, "budget budget budget travel offsite") == ["1", "0"]


def test_search_calendar_events_splits_query_and_event_words_on_punctuation():
    calendar = make_search_calendar(("Follow-up call", "", ""), ("Call", "", "Room 2"))

    assert search_ids(calendar, "follow-up") == ["0"]
    assert search_ids(calendar, "room-2 call") == ["1", "0"]


def test_search_calendar_events_hides_canceled_events_even_when_they_match():
    assert search_calendar_events(make_calendar(), "lunch") == []
    assert search_ids(make_calendar(), "team lunch budget") == ["0"]


def test_search_calendar_events_limits_to_the_given_day_even_when_events_match():
    calendar = make_calendar()

    assert search_ids(calendar, "", "2026-05-15") == ["1"]
    assert search_calendar_events(calendar, "budget", "2026-05-15") == []
    assert search_ids(calendar, "budget venue", "2026-05-15") == ["1"]


def test_search_calendar_events_takes_the_day_of_an_event_in_another_timezone_in_the_default_timezone():
    calendar = make_calendar()
    add_new_york_event(calendar, "3", datetime(2026, 5, 14, 19, 0))  # 01:00 on May 15 in Ljubljana

    assert search_calendar_events(calendar, "investor", "2026-05-14") == []
    assert search_ids(calendar, "investor", "2026-05-15") == ["3"]


@pytest.mark.parametrize("query", ["", "  ", "-.,"])
def test_search_calendar_events_returns_every_event_that_passes_the_filters_for_a_query_without_words(query: str):
    assert search_ids(make_calendar(), query) == ["0", "1"]


def test_search_calendar_events_rejects_malformed_day():
    with pytest.raises(ValueError, match=re.escape("'15.5.2026'")):
        search_calendar_events(make_calendar(), "budget", "15.5.2026")


def test_get_calendar_event_by_id_returns_the_header_and_description_as_text_without_changing_calendar():
    calendar = make_calendar()
    before = calendar.model_copy(deep=True)

    text = get_calendar_event_by_id(calendar, "1")

    assert text == (
        "Title: Offsite planning\n"
        "When: 2026-05-15 14:00–15:30 (Europe/Ljubljana)\n"  # noqa: RUF001
        "Location: Lakeside Hotel\n"
        "Organizer: alice@corp.com\n"
        "Participants: alice@corp.com, me@corp.com\n"
        "Status: confirmed\n"
        "\n"
        "Pick the venue."
    )
    assert calendar == before


def test_get_calendar_event_by_id_shows_the_event_timezone_and_leaves_out_empty_fields():
    calendar = make_calendar()
    add_new_york_event(calendar, "3", datetime(2026, 5, 14, 19, 0))

    assert get_calendar_event_by_id(calendar, "3") == (
        "Title: Investor call\n"
        "When: 2026-05-14 19:00–20:00 (America/New_York)\n"  # noqa: RUF001
        "Organizer: me@corp.com\n"
        "Status: confirmed\n"
        "\n"
    )


def test_get_calendar_event_by_id_shows_the_end_day_of_an_event_that_ends_on_another_day():
    calendar = make_calendar()
    create_calendar_event(calendar, "Hackathon", "2026-05-18 18:00", "2026-05-19 06:00")

    when = "When: 2026-05-18 18:00–2026-05-19 06:00 (Europe/Ljubljana)\n"  # noqa: RUF001
    assert when in get_calendar_event_by_id(calendar, "3")


def test_get_calendar_event_by_id_reads_a_canceled_event():
    text = get_calendar_event_by_id(make_calendar(), "2")

    assert "Status: canceled\n" in text
    assert text.endswith("\n\nBudget for the lunch is set.")


def test_get_calendar_event_by_id_rejects_unknown_id():
    with pytest.raises(ValueError, match="'7' not found"):
        get_calendar_event_by_id(make_calendar(), "7")


def test_create_calendar_event_appends_confirmed_event_organized_by_account_and_returns_it_without_its_description():
    calendar = make_calendar()
    before = calendar.model_copy(deep=True)

    event = create_calendar_event(
        calendar,
        "Sync",
        "2026-05-18 09:00",
        "2026-05-18 09:30",
        description="Weekly sync.",
        location="Room 1",
        participants=["bob@partner.org"],
    )

    expected = CalendarEvent(
        id="3",
        title="Sync",
        description="Weekly sync.",
        start_time=datetime(2026, 5, 18, 9, 0),
        end_time=datetime(2026, 5, 18, 9, 30),
        location="Room 1",
        organizer="me@corp.com",
        participants=["bob@partner.org"],
        status="confirmed",
    )
    assert event == info(expected)
    assert calendar.events == [*before.events, expected]


def test_create_calendar_event_defaults_to_empty_description_location_and_participants():
    calendar = make_calendar()

    create_calendar_event(calendar, "Focus", "2026-05-18 09:00", "2026-05-18 10:00")

    event = calendar.events[-1]
    assert (event.description, event.location, event.participants) == ("", "", [])


def test_create_calendar_event_has_no_timezone_by_default():
    assert create_calendar_event(make_calendar(), "Focus", "2026-05-18 09:00", "2026-05-18 10:00").timezone is None


def test_create_calendar_event_keeps_the_times_as_given_in_the_given_timezone():
    event = create_calendar_event(
        make_calendar(), "Investor call", "2026-05-18 09:00", "2026-05-18 10:00", timezone="America/New_York"
    )

    assert (event.start_time, event.end_time, event.timezone) == (
        datetime(2026, 5, 18, 9, 0),
        datetime(2026, 5, 18, 10, 0),
        "America/New_York",
    )


@pytest.mark.parametrize("timezone", ["Mars/Olympus", "new york", "../etc", ""])
def test_create_calendar_event_rejects_unknown_timezone(timezone: str):
    calendar = make_calendar()
    before = calendar.model_copy(deep=True)

    with pytest.raises(ValueError, match=re.escape(repr(timezone))):
        create_calendar_event(calendar, "Focus", "2026-05-18 09:00", "2026-05-18 10:00", timezone=timezone)
    assert calendar == before


def test_create_calendar_event_does_not_check_overlaps():
    event = create_calendar_event(make_calendar(), "Clash", "2026-05-14 10:00", "2026-05-14 11:00")

    assert event.id == "3"


def test_create_calendar_event_gives_id_zero_to_first_event():
    calendar = Calendar(account_email="me@corp.com", default_timezone="Europe/Ljubljana", current_day=date(2026, 5, 14))

    assert create_calendar_event(calendar, "Focus", "2026-05-18 09:00", "2026-05-18 10:00").id == "0"


@pytest.mark.parametrize("end_time", ["2026-05-18 09:00", "2026-05-18 08:00"])
def test_create_calendar_event_rejects_end_not_after_start(end_time: str):
    calendar = make_calendar()
    before = calendar.model_copy(deep=True)

    with pytest.raises(ValueError, match="after the start"):
        create_calendar_event(calendar, "Focus", "2026-05-18 09:00", end_time)
    assert calendar == before


@pytest.mark.parametrize(
    ("start_time", "end_time", "bad"),
    [
        ("2026-05-18", "2026-05-18 10:00", "2026-05-18"),
        ("2026-05-18 09:00", "tomorrow", "tomorrow"),
        ("2026-05-18 25:00", "2026-05-18 10:00", "2026-05-18 25:00"),
    ],
)
def test_create_calendar_event_rejects_unparseable_datetime(start_time: str, end_time: str, bad: str):
    calendar = make_calendar()
    before = calendar.model_copy(deep=True)

    with pytest.raises(ValueError, match=re.escape(repr(bad))):
        create_calendar_event(calendar, "Focus", start_time, end_time)
    assert calendar == before


def test_reschedule_calendar_event_keeps_duration_and_returns_event_without_its_description():
    calendar = make_calendar()
    before = calendar.model_copy(deep=True)

    event = reschedule_calendar_event(calendar, "1", "2026-05-18 09:00")

    expected = before.events[1].model_copy(
        update={"start_time": datetime(2026, 5, 18, 9, 0), "end_time": datetime(2026, 5, 18, 10, 30)}
    )
    assert event == info(expected)
    assert calendar.events == [before.events[0], expected, before.events[2]]


def test_reschedule_calendar_event_uses_new_end_when_given():
    calendar = make_calendar()

    event = reschedule_calendar_event(calendar, "1", "2026-05-18 09:00", "2026-05-18 09:15")

    assert (event.start_time, event.end_time) == (datetime(2026, 5, 18, 9, 0), datetime(2026, 5, 18, 9, 15))


def test_reschedule_calendar_event_reads_the_new_times_in_the_event_timezone():
    calendar = make_calendar()
    add_new_york_event(calendar, "3", datetime(2026, 5, 14, 19, 0))

    event = reschedule_calendar_event(calendar, "3", "2026-05-20 08:00")

    assert (event.start_time, event.end_time, event.timezone) == (
        datetime(2026, 5, 20, 8, 0),
        datetime(2026, 5, 20, 9, 0),
        "America/New_York",
    )


@pytest.mark.parametrize("new_end_time", ["2026-05-18 09:00", "2026-05-18 08:00"])
def test_reschedule_calendar_event_rejects_end_not_after_start(new_end_time: str):
    calendar = make_calendar()
    before = calendar.model_copy(deep=True)

    with pytest.raises(ValueError, match="after the start"):
        reschedule_calendar_event(calendar, "1", "2026-05-18 09:00", new_end_time)
    assert calendar == before


@pytest.mark.parametrize(
    ("new_start_time", "new_end_time", "bad"),
    [("next monday", None, "next monday"), ("2026-05-18 09:00", "2026-05-18", "2026-05-18")],
)
def test_reschedule_calendar_event_rejects_unparseable_datetime(
    new_start_time: str, new_end_time: str | None, bad: str
):
    calendar = make_calendar()
    before = calendar.model_copy(deep=True)

    with pytest.raises(ValueError, match=re.escape(repr(bad))):
        reschedule_calendar_event(calendar, "1", new_start_time, new_end_time)
    assert calendar == before


@pytest.mark.parametrize(("event_id", "message"), [("7", "'7' not found"), ("2", "'2' is canceled")])
def test_reschedule_calendar_event_rejects_unknown_or_canceled_event(event_id: str, message: str):
    calendar = make_calendar()
    before = calendar.model_copy(deep=True)

    with pytest.raises(ValueError, match=message):
        reschedule_calendar_event(calendar, event_id, "2026-05-18 09:00")
    assert calendar == before


def test_cancel_calendar_event_sets_status_keeps_event_and_returns_it_without_its_description():
    calendar = make_calendar()
    before = calendar.model_copy(deep=True)

    event = cancel_calendar_event(calendar, "0")

    expected = before.events[0].model_copy(update={"status": "canceled"})
    assert event == info(expected)
    assert calendar.events == [expected, before.events[1], before.events[2]]


@pytest.mark.parametrize(("event_id", "message"), [("7", "'7' not found"), ("2", "'2' is canceled")])
def test_cancel_calendar_event_rejects_unknown_or_canceled_event(event_id: str, message: str):
    calendar = make_calendar()
    before = calendar.model_copy(deep=True)

    with pytest.raises(ValueError, match=message):
        cancel_calendar_event(calendar, event_id)
    assert calendar == before


def test_add_calendar_event_participants_adds_new_addresses_and_returns_event_without_its_description():
    calendar = make_calendar()
    before = calendar.model_copy(deep=True)

    event = add_calendar_event_participants(calendar, "0", ["alice@corp.com", "bob@partner.org", "bob@partner.org"])

    expected = before.events[0].model_copy(
        update={"participants": ["me@corp.com", "alice@corp.com", "bob@partner.org"]}
    )
    assert event == info(expected)
    assert calendar.events == [expected, before.events[1], before.events[2]]


def test_add_calendar_event_participants_does_not_check_the_organizer():
    calendar = make_calendar()

    add_calendar_event_participants(calendar, "1", ["bob@partner.org"])

    assert calendar.events[1].participants == ["alice@corp.com", "me@corp.com", "bob@partner.org"]


@pytest.mark.parametrize(("event_id", "message"), [("7", "'7' not found"), ("2", "'2' is canceled")])
def test_add_calendar_event_participants_rejects_unknown_or_canceled_event(event_id: str, message: str):
    calendar = make_calendar()
    before = calendar.model_copy(deep=True)

    with pytest.raises(ValueError, match=message):
        add_calendar_event_participants(calendar, event_id, ["bob@partner.org"])
    assert calendar == before
