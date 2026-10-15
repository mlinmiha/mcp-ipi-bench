"""Pydantic models for comments, issues and the issue tracker."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Comment(BaseModel):
    id: str
    author: str
    body: str
    created_at: datetime


class Issue(BaseModel):
    key: str
    summary: str
    description: str
    status: Literal["open", "in_progress", "done"]
    assignee: str | None = None
    reporter: str
    comments: list[Comment] = Field(default_factory=list)


class IssueInfo(BaseModel):
    key: str
    summary: str
    status: Literal["open", "in_progress", "done"]
    assignee: str | None
    reporter: str


class Jira(BaseModel):
    current_user: str
    project: str
    current_datetime: datetime
    issues: list[Issue] = Field(default_factory=list)
