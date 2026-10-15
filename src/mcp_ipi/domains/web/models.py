"""Pydantic models for web pages, search results and the web."""

from pydantic import BaseModel, Field


class Page(BaseModel):
    url: str
    title: str
    content: str


class SearchResult(BaseModel):
    url: str
    title: str


class Web(BaseModel):
    pages: list[Page] = Field(default_factory=list)
    requested_urls: list[str] = Field(default_factory=list)
