"""Domain descriptors that tie each component model to its tools."""

from .base import Domain
from .calendar import CALENDAR
from .cloud_storage import CLOUD_STORAGE
from .email import EMAIL
from .issue_tracking import ISSUE_TRACKING
from .web import WEB

__all__ = ["CALENDAR", "CLOUD_STORAGE", "EMAIL", "ISSUE_TRACKING", "WEB", "Domain"]
