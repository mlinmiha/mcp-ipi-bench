"""Pydantic models for emails and the inbox."""

from datetime import datetime

from pydantic import BaseModel, Field


class Email(BaseModel):
    id: str
    sender: str
    recipients: list[str]
    cc: list[str] = Field(default_factory=list)
    bcc: list[str] = Field(default_factory=list)
    subject: str
    body: str
    timestamp: datetime
    read: bool = False


class EmailInfo(BaseModel):
    id: str
    sender: str
    recipients: list[str]
    cc: list[str]
    bcc: list[str]
    subject: str
    timestamp: datetime
    read: bool


class Inbox(BaseModel):
    account_email: str
    current_datetime: datetime
    received: list[Email] = Field(default_factory=list)
    sent: list[Email] = Field(default_factory=list)
