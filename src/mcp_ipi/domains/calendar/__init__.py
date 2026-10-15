"""Calendar domain with the calendar component and its tools."""

from ..base import Domain
from .models import Calendar, CalendarEvent, CalendarEventInfo
from .tools import (
    add_calendar_event_participants,
    cancel_calendar_event,
    create_calendar_event,
    get_calendar_event_by_id,
    get_day_calendar_events,
    reschedule_calendar_event,
    search_calendar_events,
)

CALENDAR = Domain(
    name="calendar",
    component="calendar",
    model=Calendar,
    tools=(
        get_day_calendar_events,
        search_calendar_events,
        get_calendar_event_by_id,
        create_calendar_event,
        reschedule_calendar_event,
        cancel_calendar_event,
        add_calendar_event_participants,
    ),
)

__all__ = ["CALENDAR", "Calendar", "CalendarEvent", "CalendarEventInfo"]
