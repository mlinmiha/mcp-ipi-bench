"""Calendar tools that read and change a calendar.

The calendar is injected at runtime and not exposed to the LLM. Canceled events are hidden from the search and day
tools, readable by ID and rejected by the write tools. An event's times are local to its timezone, or to the calendar's
default timezone when it has none; days are always days in the default timezone.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from ..search import rank
from .models import Calendar, CalendarEvent, CalendarEventInfo


def get_day_calendar_events(calendar: Calendar, day: str) -> list[CalendarEventInfo]:
    """Return the events that start on a day, except canceled ones.

    To read an event's description, call `get_calendar_event_by_id` with its ID.

    Args:
        day: The day in the format YYYY-MM-DD, in the user's local time.

    Returns:
        Each event that starts on the day and is not canceled, without its description.

    Raises:
        ValueError: If the day is not in the format YYYY-MM-DD.
    """
    parsed_day = _parse_day(day)

    return [_info(event) for event in _active_events(calendar) if _local_day(calendar, event) == parsed_day]


def search_calendar_events(calendar: Calendar, query: str, day: str | None = None) -> list[CalendarEventInfo]:
    """Search calendar events, except canceled ones.

    Returns every event whose title, description or location contains at least one word of the query, ranked by how
    many distinct query words it contains, best matches first.

    To read an event's description, call `get_calendar_event_by_id` with its ID.

    Args:
        query: Words to look for in the title, description or location, as whole words, case-insensitively.
        day: Only return events that start on this day, in the format YYYY-MM-DD, in the user's local time. All days
            when omitted.

    Returns:
        Each event matching the query, without its description, best matches first.

    Raises:
        ValueError: If the day is not in the format YYYY-MM-DD.
    """
    parsed_day = _parse_day(day) if day is not None else None
    events = [
        event for event in _active_events(calendar) if parsed_day is None or _local_day(calendar, event) == parsed_day
    ]

    return [
        _info(event)
        for event in rank(query, events, lambda event: f"{event.title}\n{event.description}\n{event.location}")
    ]


def get_calendar_event_by_id(calendar: Calendar, event_id: str) -> str:
    """Return an event by its ID, canceled ones included.

    Args:
        event_id: ID of the event to read.

    Returns:
        The event as text: its title, time and timezone, location, organizer, participants and status, then a blank
        line and its description.

    Raises:
        ValueError: If no event with the given ID exists.
    """
    for event in calendar.events:
        if event.id == event_id:
            return _text(calendar, event)

    raise ValueError(f"Event with ID {event_id!r} not found")


def create_calendar_event(
    calendar: Calendar,
    title: str,
    start_time: str,
    end_time: str,
    description: str = "",
    location: str = "",
    participants: list[str] | None = None,
    timezone: str | None = None,
) -> CalendarEventInfo:
    """Create an event organized by the calendar account.

    Args:
        title: Title of the event.
        start_time: Start of the event in the format YYYY-MM-DD HH:MM.
        end_time: End of the event in the format YYYY-MM-DD HH:MM.
        description: Description of the event.
        location: Location of the event.
        participants: Email addresses of the participants.
        timezone: IANA timezone of the start and end time, e.g. "America/New_York". The user's local time when
            omitted.

    Returns:
        The newly created event, without its description.

    Raises:
        ValueError: If a time is not in the format YYYY-MM-DD HH:MM, the end is not after the start, or the timezone
            is unknown.
    """
    start, end = _parse_period(start_time, end_time)
    if timezone is not None:
        _check_timezone(timezone)
    event = CalendarEvent(
        id=_next_id(calendar),
        title=title,
        description=description,
        start_time=start,
        end_time=end,
        timezone=timezone,
        location=location,
        organizer=calendar.account_email,
        participants=participants or [],
    )

    calendar.events.append(event)
    return _info(event)


def reschedule_calendar_event(
    calendar: Calendar, event_id: str, new_start_time: str, new_end_time: str | None = None
) -> CalendarEventInfo:
    """Move an event to a new start time, keeping its duration unless a new end time is given.

    The new times are in the event's own timezone.

    Args:
        event_id: ID of the event to move.
        new_start_time: New start of the event in the format YYYY-MM-DD HH:MM.
        new_end_time: New end of the event in the format YYYY-MM-DD HH:MM. Keeps the duration when omitted.

    Returns:
        The rescheduled event, without its description.

    Raises:
        ValueError: If no event with the given ID exists, the event is canceled, a time is not in the format
            YYYY-MM-DD HH:MM, or the end is not after the start.
    """
    event = _find_active_event(calendar, event_id)
    if new_end_time is None:
        start = _parse_time(new_start_time)
        end = start + (event.end_time - event.start_time)
    else:
        start, end = _parse_period(new_start_time, new_end_time)

    event.start_time = start
    event.end_time = end
    return _info(event)


def cancel_calendar_event(calendar: Calendar, event_id: str) -> CalendarEventInfo:
    """Cancel an event.

    Args:
        event_id: ID of the event to cancel.

    Returns:
        The canceled event, without its description.

    Raises:
        ValueError: If no event with the given ID exists, or the event is already canceled.
    """
    event = _find_active_event(calendar, event_id)
    event.status = "canceled"
    return _info(event)


def add_calendar_event_participants(calendar: Calendar, event_id: str, participants: list[str]) -> CalendarEventInfo:
    """Add participants to an event; addresses that already take part are skipped.

    Args:
        event_id: ID of the event.
        participants: Email addresses of the participants to add.

    Returns:
        The updated event, without its description.

    Raises:
        ValueError: If no event with the given ID exists, or the event is canceled.
    """
    event = _find_active_event(calendar, event_id)
    for participant in participants:
        if participant not in event.participants:
            event.participants.append(participant)
    return _info(event)


def _info(event: CalendarEvent) -> CalendarEventInfo:
    """Return an event's metadata: everything but its description."""
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


def _text(calendar: Calendar, event: CalendarEvent) -> str:
    """Return an event as text: a header of the non-empty fields, a blank line, then the description."""
    start = event.start_time.strftime("%Y-%m-%d %H:%M")
    end = event.end_time.strftime("%H:%M" if event.end_time.date() == event.start_time.date() else "%Y-%m-%d %H:%M")
    header = {
        "Title": event.title,
        "When": f"{start}–{end} ({event.timezone or calendar.default_timezone})",  # noqa: RUF001
        "Location": event.location,
        "Organizer": event.organizer,
        "Participants": ", ".join(event.participants),
        "Status": event.status,
    }
    lines = [f"{name}: {value}" for name, value in header.items() if value]
    return "\n".join(lines) + "\n\n" + event.description


def _active_events(calendar: Calendar) -> list[CalendarEvent]:
    """Return the confirmed events."""
    return [event for event in calendar.events if event.status == "confirmed"]


def _find_active_event(calendar: Calendar, event_id: str) -> CalendarEvent:
    """Find an event that is not canceled by its ID.

    Args:
        event_id: ID of the event to find.

    Returns:
        The event.

    Raises:
        ValueError: If no event with the given ID exists, or the event is canceled.
    """
    for event in calendar.events:
        if event.id == event_id:
            if event.status == "canceled":
                raise ValueError(f"Event with ID {event_id!r} is canceled")
            return event

    raise ValueError(f"Event with ID {event_id!r} not found")


def _local_day(calendar: Calendar, event: CalendarEvent) -> date:
    """Return the day the event starts on in the calendar's default timezone."""
    start = event.start_time.replace(tzinfo=ZoneInfo(event.timezone or calendar.default_timezone))
    return start.astimezone(ZoneInfo(calendar.default_timezone)).date()


def _check_timezone(timezone: str) -> None:
    """Check that an IANA timezone exists.

    Raises:
        ValueError: If the timezone is unknown.
    """
    try:
        ZoneInfo(timezone)
    except (KeyError, ValueError):
        raise ValueError(f"Timezone {timezone!r} is unknown") from None


def _parse_day(day: str) -> date:
    """Parse a day in the format YYYY-MM-DD.

    Raises:
        ValueError: If the day is not in that format.
    """
    try:
        return datetime.strptime(day, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"Day {day!r} is not in the format YYYY-MM-DD") from None


def _parse_time(time: str) -> datetime:
    """Parse a time in the format YYYY-MM-DD HH:MM.

    Raises:
        ValueError: If the time is not in that format.
    """
    try:
        return datetime.strptime(time, "%Y-%m-%d %H:%M")
    except ValueError:
        raise ValueError(f"Time {time!r} is not in the format YYYY-MM-DD HH:MM") from None


def _parse_period(start_time: str, end_time: str) -> tuple[datetime, datetime]:
    """Parse a start and an end time in the format YYYY-MM-DD HH:MM.

    Raises:
        ValueError: If a time is not in that format, or the end is not after the start.
    """
    start, end = _parse_time(start_time), _parse_time(end_time)
    if end <= start:
        raise ValueError(f"End time {end_time!r} must be after the start time {start_time!r}")
    return start, end


def _next_id(calendar: Calendar) -> str:
    """Generate the next available event ID.

    Returns:
        The next available numeric event ID as a string.
    """
    ids = [int(event.id) for event in calendar.events if event.id.isdigit()]
    return str(max(ids, default=-1) + 1)
