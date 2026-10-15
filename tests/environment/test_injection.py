"""Tests for finding and filling `{@inject:id}` placeholders."""

from pathlib import Path

import pytest

from mcp_ipi.environment import InjectionVector, fill_injections, find_injection_placeholders, load_injection_vectors


def test_injection_vector_holds_id_description_and_default():
    vector = InjectionVector(id="email_body", description="end of an email body", default="Thanks!")

    assert (vector.id, vector.description, vector.default) == ("email_body", "end of an email body", "Thanks!")


def test_single_placeholder_is_filled():
    assert fill_injections("Hello {@inject:email_body}", {"email_body": "ATTACK"}) == "Hello ATTACK"


def test_multiple_placeholders_in_one_string_are_filled():
    data = "{@inject:a} and {@inject:b} and {@inject:a}"

    assert fill_injections(data, {"a": "1", "b": "2"}) == "1 and 2 and 1"


def test_placeholders_in_nested_dicts_and_lists_are_filled():
    data = {
        "received": [{"id": "1", "body": "Invoice. {@inject:email_body}", "read": False}],
        "pages": [{"content": "News {@inject:web_page}"}],
        "count": 3,
    }

    assert fill_injections(data, {"email_body": "X", "web_page": "Y"}) == {
        "received": [{"id": "1", "body": "Invoice. X", "read": False}],
        "pages": [{"content": "News Y"}],
        "count": 3,
    }


def test_filling_does_not_change_the_input():
    data = {"body": ["{@inject:a}"]}

    fill_injections(data, {"a": "X"})

    assert data == {"body": ["{@inject:a}"]}


def test_data_without_placeholders_is_returned_equal():
    data = {"a": [1, "text", None, True], "b": {"c": 2.5}}

    assert fill_injections(data, {}) == data


def test_placeholder_without_a_value_raises_key_error():
    with pytest.raises(KeyError, match="unknown"):
        fill_injections({"body": "{@inject:unknown}"}, {"email_body": "X"})


@pytest.mark.parametrize("text", ["{ @inject:a }", "{@inject: a}", "{inject:a}", "{@inj:a}", "{@inject:}"])
def test_text_that_is_not_an_exact_placeholder_is_left_unchanged(text: str):
    assert find_injection_placeholders(text) == []
    assert fill_injections(text, {"a": "X"}) == text


def test_find_returns_vector_ids_in_order():
    data = {"x": "{@inject:b}", "y": ["{@inject:a} {@inject:c}", 1], "z": None}

    assert find_injection_placeholders(data) == ["b", "a", "c"]


def test_find_on_data_without_placeholders_returns_empty_list():
    assert find_injection_placeholders({"a": ["text", 1]}) == []


def test_injection_vectors_load_keyed_by_id(tmp_path: Path):
    path = tmp_path / "injection_vectors.yaml"
    path.write_text('email_body:\n  description: "end of an email body"\n  default: "Thanks!"\n')

    assert load_injection_vectors(path) == {
        "email_body": InjectionVector(id="email_body", description="end of an email body", default="Thanks!")
    }
