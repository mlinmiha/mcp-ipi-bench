"""Pydantic models for calendar events and the calendar."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class CalendarEvent(BaseModel):
    id: str
    title: str
    description: str = ""
    start_time: datetime
    end_time: datetime
    timezone: str | None = None
    location: str = ""
    organizer: str
    participants: list[str] = Field(default_factory=list)
    status: Literal["confirmed", "canceled"] = "confirmed"


class CalendarEventInfo(BaseModel):
    id: str
    title: str
    start_time: datetime
    end_time: datetime
    timezone: str | None
    location: str
    organizer: str
    participants: list[str]
    status: Literal["confirmed", "canceled"]


class Calendar(BaseModel):
    """A calendar of events.

    An event's times are naive and local to its `timezone`, or to `default_timezone` when it has none.
    """

    account_email: str
    default_timezone: str
    current_day: date
    events: list[CalendarEvent] = Field(default_factory=list)
