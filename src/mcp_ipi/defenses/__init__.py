"""Defense strategies: each is a function that builds the agent pipeline with the defense in place."""

from collections.abc import Callable

from mcp_ipi.agent import AgentPipeline, PipelineElement
from mcp_ipi.suites import Policy

from .baseline import baseline_pipeline
from .sanitizer import SANITIZER_PROMPT, sanitizer_pipeline
from .security_policy import security_policy_pipeline
from .spotlighting import spotlighting_pipeline
from .tool_filter import TOOL_FILTER_PROMPT, tool_filter_pipeline

DefenseBuilder = Callable[[PipelineElement, Policy], AgentPipeline]
"""A defense: `(llm, policy) -> AgentPipeline`, the agent's pipeline with the defense in place."""

DEFENSES: dict[str, DefenseBuilder] = {
    "none": baseline_pipeline,
    "spotlighting": spotlighting_pipeline,
    "sanitizer": sanitizer_pipeline,
    "tool-filter": tool_filter_pipeline,
    "security-policy": security_policy_pipeline,
}
"""Each defense's builder by name, with `none` for the baseline."""

__all__ = [
    "DEFENSES",
    "SANITIZER_PROMPT",
    "TOOL_FILTER_PROMPT",
    "DefenseBuilder",
    "baseline_pipeline",
    "sanitizer_pipeline",
    "security_policy_pipeline",
    "spotlighting_pipeline",
    "tool_filter_pipeline",
]
