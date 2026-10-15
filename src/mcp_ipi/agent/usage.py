"""Model usage: tokens, calls and cost, counted by the element that calls the model."""

from typing import Protocol

from pydantic import BaseModel

from .pipeline import PipelineElement


class Usage(BaseModel, frozen=True):
    """Input tokens, output tokens, model calls and cost in USD, summed over some calls.

    `cost` is `None` when any of the summed calls reported no cost, so an unknown cost is never counted as 0.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    llm_calls: int = 0
    cost: float | None = 0.0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            llm_calls=self.llm_calls + other.llm_calls,
            cost=None if self.cost is None or other.cost is None else self.cost + other.cost,
        )


class CountingLLM(PipelineElement, Protocol):
    """Any pipeline element that calls a model and keeps the running `usage` of its calls, like `LLM`.

    `providers` lists the distinct providers that served its calls, in the order of their first call, and
    `finish_reasons` every call's finish reason in call order, `None` where it is missing.
    """

    usage: Usage
    providers: list[str]
    finish_reasons: list[str | None]
