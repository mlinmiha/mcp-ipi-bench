"""The Domain descriptor shared by all domains."""

from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel


@dataclass(frozen=True)
class Domain:
    """A domain: one environment component, its Pydantic model and the tools that work on it.

    Attributes:
        name: The domain's name, e.g. `email`.
        component: The environment field that holds the domain's data, e.g. `inbox`; each tool gets it as its
            first argument.
        model: The Pydantic model of the component, e.g. `Inbox`.
        tools: The domain's tool functions, in order.

    Raises:
        ValueError: The name or component is empty, or two tools have the same name.
    """

    name: str
    component: str
    model: type[BaseModel]
    tools: tuple[Callable, ...]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Domain name must not be empty")

        if not self.component.strip():
            raise ValueError(f"Domain {self.name!r} component must not be empty")

        seen: set[str] = set()
        for tool in self.tools:
            if tool.__name__ in seen:
                raise ValueError(f"Domain {self.name!r} has duplicate tool {tool.__name__!r}")
            seen.add(tool.__name__)
