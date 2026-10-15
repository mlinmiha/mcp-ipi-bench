"""Workspace user tasks, in domain order."""

from . import calendar, cloud_storage, email, issue_tracking, web

USER_TASKS = (
    email.USER_TASKS + web.USER_TASKS + cloud_storage.USER_TASKS + calendar.USER_TASKS + issue_tracking.USER_TASKS
)

__all__ = ["USER_TASKS"]
