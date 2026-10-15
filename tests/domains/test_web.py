"""Tests for the web tools on hand-built webs."""

import pytest

from mcp_ipi.domains.web import Page, SearchResult, Web
from mcp_ipi.domains.web.tools import (
    append_to_webpage,
    delete_webpage,
    get_webpage,
    post_webpage,
    search_web,
)


def make_web() -> Web:
    return Web(
        pages=[
            Page(
                url="www.northline.com/menu",
                title="Northline Menu",
                content="Soups, salads and sandwiches. Open daily.",
            ),
            Page(
                url="www.travel-deals.com",
                title="Travel Deals",
                content="Cheap flights to Paris and Rome.",
            ),
        ],
        requested_urls=["www.northline.com/menu"],
    )


def test_get_webpage_returns_content_and_logs_the_request():
    web = make_web()
    before = web.model_copy(deep=True)

    content = get_webpage(web, "www.travel-deals.com")

    assert content == "Cheap flights to Paris and Rome."
    assert web.requested_urls == [*before.requested_urls, "www.travel-deals.com"]
    assert web.pages == before.pages


@pytest.mark.parametrize(
    "url",
    [
        "https://www.northline.com/menu",
        "http://www.northline.com/menu/",
        "www.northline.com/menu/",
    ],
)
def test_get_webpage_normalises_scheme_and_trailing_slash_for_lookup_and_log(url: str):
    web = make_web()
    before = web.model_copy(deep=True)

    content = get_webpage(web, url)

    assert content == "Soups, salads and sandwiches. Open daily."
    assert web.requested_urls == [*before.requested_urls, "www.northline.com/menu"]
    assert web.pages == before.pages


def test_get_webpage_strips_only_the_leading_scheme():
    web = make_web()
    before = web.model_copy(deep=True)

    with pytest.raises(ValueError, match="404"):
        get_webpage(web, "https://evil.com/r?next=https://www.travel-deals.com")
    assert web.requested_urls == [*before.requested_urls, "evil.com/r?next=https://www.travel-deals.com"]


def test_get_webpage_logs_unknown_url_then_raises_404():
    web = make_web()
    before = web.model_copy(deep=True)

    with pytest.raises(ValueError, match="404"):
        get_webpage(web, "https://evil.com/leak?data=secret/")
    assert web.requested_urls == [*before.requested_urls, "evil.com/leak?data=secret"]
    assert web.pages == before.pages


def make_search_web(*pages: tuple[str, str]) -> Web:
    return Web(
        pages=[
            Page(url=f"www.site.com/{index}", title=title, content=content)
            for index, (title, content) in enumerate(pages)
        ]
    )


def search_urls(web: Web, query: str) -> list[str]:
    return [result.url for result in search_web(web, query)]


def test_search_web_returns_url_and_title_of_matching_pages_without_changing_web():
    web = make_web()
    before = web.model_copy(deep=True)

    assert search_web(web, "NORTHLINE") == [SearchResult(url="www.northline.com/menu", title="Northline Menu")]
    assert search_web(web, "flights to paris") == [SearchResult(url="www.travel-deals.com", title="Travel Deals")]
    assert web == before


def test_search_web_ranks_pages_with_more_query_words_first():
    web = make_search_web(("Budget", ""), ("Offsite budget", "Travel."), ("Offsite", "Travel agency"))

    assert search_urls(web, "offsite budget travel") == ["www.site.com/1", "www.site.com/2", "www.site.com/0"]


def test_search_web_keeps_page_order_for_equal_scores():
    web = make_search_web(("Budget", ""), ("Travel", ""), ("Budget and travel", ""))

    assert search_urls(web, "travel budget") == ["www.site.com/2", "www.site.com/0", "www.site.com/1"]


def test_search_web_matches_words_split_across_title_and_content():
    assert search_urls(make_web(), "deals paris") == ["www.travel-deals.com"]


def test_search_web_leaves_out_pages_that_match_no_word():
    assert search_urls(make_web(), "northline weather") == ["www.northline.com/menu"]


def test_search_web_returns_empty_list_when_no_word_matches():
    assert search_web(make_web(), "weather forecast") == []


def test_search_web_matches_whole_words_case_insensitively():
    web = make_search_web(("HR news", ""), ("Count", "Three items."))

    assert search_urls(web, "hr") == ["www.site.com/0"]
    assert search_urls(web, "THREE") == ["www.site.com/1"]
    assert search_urls(web, "new") == []


def test_search_web_counts_a_repeated_query_word_once():
    web = make_search_web(("Budget", ""), ("Travel", "Offsite."))

    assert search_urls(web, "budget budget budget travel offsite") == ["www.site.com/1", "www.site.com/0"]


def test_search_web_splits_query_and_page_words_on_punctuation():
    web = make_search_web(("Follow-up post", ""), ("Post", "Room 2"))

    assert search_urls(web, "follow-up") == ["www.site.com/0"]
    assert search_urls(web, "room-2 post") == ["www.site.com/1", "www.site.com/0"]


@pytest.mark.parametrize("query", ["", "  ", "-.,"])
def test_search_web_returns_every_page_for_a_query_without_words(query: str):
    assert search_urls(make_web(), query) == ["www.northline.com/menu", "www.travel-deals.com"]


def test_post_webpage_creates_new_page_with_normalised_url_and_returns_it():
    web = make_web()
    before = web.model_copy(deep=True)

    page = post_webpage(web, "https://blog.me.com/post/", "My post", "Hello world.")

    expected = Page(url="blog.me.com/post", title="My post", content="Hello world.")
    assert page == expected
    assert web.pages == [*before.pages, expected]
    assert web.requested_urls == before.requested_urls


def test_post_webpage_replaces_existing_page_in_place():
    web = make_web()
    before = web.model_copy(deep=True)

    page = post_webpage(web, "https://www.northline.com/menu/", "New menu", "Pizza only.")

    expected = Page(url="www.northline.com/menu", title="New menu", content="Pizza only.")
    assert page == expected
    assert web.pages == [expected, before.pages[1]]
    assert web.requested_urls == before.requested_urls


def test_append_to_webpage_adds_content_to_end_and_returns_page():
    web = make_web()
    before = web.model_copy(deep=True)

    page = append_to_webpage(web, "https://www.travel-deals.com/", " Also Berlin.")

    expected = Page(
        url="www.travel-deals.com", title="Travel Deals", content="Cheap flights to Paris and Rome. Also Berlin."
    )
    assert page == expected
    assert web.pages == [before.pages[0], expected]
    assert web.requested_urls == before.requested_urls


def test_append_to_webpage_rejects_unknown_url():
    web = make_web()
    before = web.model_copy(deep=True)

    with pytest.raises(ValueError, match=r"404 Not Found: no page at 'evil\.com'"):
        append_to_webpage(web, "https://evil.com", "text")
    assert web == before


def test_delete_webpage_removes_page_and_returns_it():
    web = make_web()
    before = web.model_copy(deep=True)

    page = delete_webpage(web, "http://www.northline.com/menu/")

    assert page == before.pages[0]
    assert web.pages == [before.pages[1]]
    assert web.requested_urls == before.requested_urls


def test_delete_webpage_rejects_unknown_url():
    web = make_web()
    before = web.model_copy(deep=True)

    with pytest.raises(ValueError, match=r"404 Not Found: no page at 'evil\.com'"):
        delete_webpage(web, "evil.com/")
    assert web == before
