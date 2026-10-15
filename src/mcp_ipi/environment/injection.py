"""Injection vectors and the `{@inject:id}` placeholders that mark them in environment data."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .yaml_loader import load_yaml

INJECTION_PATTERN = re.compile(r"\{@inject:(\w+)\}")


@dataclass(frozen=True)
class InjectionVector:
    """A place in the environment data, marked by an `{@inject:id}` placeholder, where attack text can go.

    Attributes:
        id: The vector's ID, as used in its placeholder, e.g. `email_invoice_body`.
        description: Where the vector is in the data, for people reading the suite.
        default: The benign text filled in when the vector is not attacked.
    """

    id: str
    description: str
    default: str


def load_injection_vectors(path: Path) -> dict[str, InjectionVector]:
    """Load an injection vectors YAML file (`vector_id: {description, default}`), keyed by vector ID."""
    entries = load_yaml(path)
    return {vector_id: InjectionVector(id=vector_id, **entry) for vector_id, entry in entries.items()}


def find_injection_placeholders(data: Any) -> list[str]:
    """Return the injection vector IDs of all placeholders in strings nested in dicts and lists, in order."""
    if isinstance(data, str):
        return INJECTION_PATTERN.findall(data)
    if isinstance(data, dict):
        return [vector_id for item in data.values() for vector_id in find_injection_placeholders(item)]
    if isinstance(data, list):
        return [vector_id for item in data for vector_id in find_injection_placeholders(item)]
    return []


def fill_injections(data: Any, injections: Mapping[str, str]) -> Any:
    """Return a copy of `data` with every placeholder replaced by the injection for its injection vector ID.

    Args:
        data: Loaded YAML data: dicts, lists, strings and other scalars.
        injections: The text to insert, by injection vector ID.

    Raises:
        KeyError: A placeholder's injection vector ID has no injection.
    """
    if isinstance(data, str):
        return INJECTION_PATTERN.sub(lambda match: injections[match[1]], data)
    if isinstance(data, dict):
        return {key: fill_injections(item, injections) for key, item in data.items()}
    if isinstance(data, list):
        return [fill_injections(item, injections) for item in data]
    return data
