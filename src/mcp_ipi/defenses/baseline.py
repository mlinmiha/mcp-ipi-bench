"""The baseline: the agent pipeline without any defense."""

from mcp_ipi.agent import (
    DEFAULT_SYSTEM_MESSAGE,
    AgentPipeline,
    InitQuery,
    PipelineElement,
    SystemMessage,
    ToolsExecutionLoop,
    ToolsExecutor,
)
from mcp_ipi.suites import Policy


def baseline_pipeline(llm: PipelineElement, _: Policy) -> AgentPipeline:
    """Build the pipeline without any defense."""
    return AgentPipeline(
        [SystemMessage(DEFAULT_SYSTEM_MESSAGE), InitQuery(), llm, ToolsExecutionLoop([ToolsExecutor(), llm])]
    )
