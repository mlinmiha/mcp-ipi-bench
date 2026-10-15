"""Pydantic models for files and the cloud drive."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, SerializerFunctionWrapHandler, model_serializer


class File(BaseModel):
    id: str
    filename: str
    content: str
    owner: str
    shared_with: dict[str, Literal["r", "rw"]] = Field(default_factory=dict)
    last_modified: datetime


class FileInfo(BaseModel):
    id: str
    filename: str
    owner: str
    shared_with: dict[str, Literal["r", "rw"]]
    last_modified: datetime

    @model_serializer(mode="wrap")
    def _leave_out_empty_shared_with(self, handler: SerializerFunctionWrapHandler) -> dict:
        """Dump a file that is shared with nobody without `shared_with`, so a tool result has no `shared_with: {}`."""
        data = handler(self)

        if not self.shared_with:
            del data["shared_with"]

        return data


class CloudDrive(BaseModel):
    account_email: str
    current_datetime: datetime
    files: list[File] = Field(default_factory=list)
