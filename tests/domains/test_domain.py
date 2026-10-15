"""Tests for Domain descriptor validation and immutability."""

import dataclasses

import pytest
from pydantic import BaseModel

from mcp_ipi.domains import Domain


class Component(BaseModel):
    pass


def read_things(component: Component) -> list[str]:
    return []


def write_thing(component: Component, text: str) -> str:
    return text


def test_valid_domain_keeps_its_fields():
    domain = Domain(name="things", component="box", model=Component, tools=(read_things, write_thing))

    assert domain.name == "things"
    assert domain.component == "box"
    assert domain.model is Component
    assert domain.tools == (read_things, write_thing)


@pytest.mark.parametrize("name", ["", "   "])
def test_empty_name_is_rejected(name: str):
    with pytest.raises(ValueError, match="name"):
        Domain(name=name, component="box", model=Component, tools=(read_things,))


@pytest.mark.parametrize("component", ["", "   "])
def test_empty_component_is_rejected(component: str):
    with pytest.raises(ValueError, match="component"):
        Domain(name="things", component=component, model=Component, tools=(read_things,))


def test_duplicate_tool_name_is_rejected_and_named():
    with pytest.raises(ValueError, match="write_thing"):
        Domain(name="things", component="box", model=Component, tools=(read_things, write_thing, write_thing))


def test_domain_is_immutable():
    domain = Domain(name="things", component="box", model=Component, tools=(read_things,))

    with pytest.raises(dataclasses.FrozenInstanceError):
        domain.name = "other"  # type: ignore[misc]
