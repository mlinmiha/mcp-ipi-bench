"""Workspace injection tasks, in domain order."""

from . import calendar, cloud_storage, email, issue_tracking, web

INJECTION_TASKS = (
    email.INJECTION_TASKS
    + web.INJECTION_TASKS
    + cloud_storage.INJECTION_TASKS
    + calendar.INJECTION_TASKS
    + issue_tracking.INJECTION_TASKS
)

__all__ = ["INJECTION_TASKS"]
