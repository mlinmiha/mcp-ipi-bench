"""Web domain with the web component and its tools."""

from ..base import Domain
from .models import Page, SearchResult, Web
from .tools import append_to_webpage, delete_webpage, get_webpage, post_webpage, search_web

WEB = Domain(
    name="web",
    component="web",
    model=Web,
    tools=(search_web, get_webpage, post_webpage, append_to_webpage, delete_webpage),
)

__all__ = ["WEB", "Page", "SearchResult", "Web"]
