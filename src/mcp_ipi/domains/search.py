"""The ranking rule shared by the domains' search tools."""

import re
from collections.abc import Callable, Sequence


def rank[T](query: str, items: Sequence[T], searched_text: Callable[[T], str]) -> list[T]:
    """Rank items by how many distinct query words they contain.

    A word is a run of letters and digits, lowercased. Items that contain none of the query's words are left out;
    the rest come back with the most matched words first and equal scores in the given order. A query without words
    returns every item in the given order.

    Args:
        query: The search query.
        items: The items to rank, already filtered.
        searched_text: Returns the searched text of an item.

    Returns:
        The matching items, best matches first.
    """
    words = _words(query)
    if not words:
        return list(items)

    scored = [(len(words & _words(searched_text(item))), item) for item in items]
    return [item for score, item in sorted(scored, key=lambda pair: -pair[0]) if score]


def _words(text: str) -> set[str]:
    return set(re.findall(r"[^\W_]+", text.lower()))
