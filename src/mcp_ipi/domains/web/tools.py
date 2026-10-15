"""Web tools that read and change the web.

The web is injected at runtime and not exposed to the LLM.
"""

import re

from ..search import rank
from .models import Page, SearchResult, Web


def search_web(web: Web, query: str) -> list[SearchResult]:
    """Search web pages.

    Returns every page whose title or content contains at least one word of the query, ranked by how many distinct
    query words it contains, best matches first.

    Args:
        query: Words to look for in the page title or content, as whole words, case-insensitively.

    Returns:
        The URL and title of each matching page, without its content, best matches first.
    """
    return [
        SearchResult(url=page.url, title=page.title)
        for page in rank(query, web.pages, lambda page: f"{page.title}\n{page.content}")
    ]


def get_webpage(web: Web, url: str) -> str:
    """Return the content of the web page at a URL.

    Every request is logged, including requests for unknown URLs.

    Args:
        url: URL of the page to read.

    Returns:
        The page content.

    Raises:
        ValueError: If no page exists at the given URL.
    """
    url = _normalize_url(url)
    web.requested_urls.append(url)

    return web.pages[_find_page_index(web, url)].content


def post_webpage(web: Web, url: str, title: str, content: str) -> Page:
    """Create a web page at a URL, replacing any page already there.

    To add to a page that already exists, call `append_to_webpage`.

    Args:
        url: URL of the page to create or replace.
        title: The page title.
        content: The page content.

    Returns:
        The posted page.
    """
    url = _normalize_url(url)
    page = Page(url=url, title=title, content=content)

    for index, existing in enumerate(web.pages):
        if existing.url == url:
            web.pages[index] = page
            return page

    web.pages.append(page)
    return page


def append_to_webpage(web: Web, url: str, content: str) -> Page:
    """Append content to the end of an existing web page.

    Args:
        url: URL of the page to append to.
        content: Text to add to the end of the page content.

    Returns:
        The updated page.

    Raises:
        ValueError: If no page exists at the given URL.
    """
    page = web.pages[_find_page_index(web, url)]
    page.content += content
    return page


def delete_webpage(web: Web, url: str) -> Page:
    """Delete the web page at a URL.

    Args:
        url: URL of the page to delete.

    Returns:
        The deleted page.

    Raises:
        ValueError: If no page exists at the given URL.
    """
    return web.pages.pop(_find_page_index(web, url))


def _find_page_index(web: Web, url: str) -> int:
    """Find the page at a URL, after normalising it.

    Args:
        url: URL of the page to find.

    Returns:
        The index of the page in the web's pages.

    Raises:
        ValueError: If no page exists at the given URL.
    """
    url = _normalize_url(url)
    for index, page in enumerate(web.pages):
        if page.url == url:
            return index

    raise ValueError(f"404 Not Found: no page at {url!r}")


def _normalize_url(url: str) -> str:
    """Strip the scheme and any trailing slash from a URL.

    Only a leading scheme is stripped, so a URL inside the query string stays intact.

    Example:
        "https://a.com/x/" -> "a.com/x"
        "a.com/r?next=https://b.com" -> "a.com/r?next=https://b.com"

    Returns:
        The URL used for page lookup and in the request log.
    """
    return re.sub(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", "", url).rstrip("/")
