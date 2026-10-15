"""The `security-policy` defense: every tool call is checked against the suite's policy and blocked if it forbids it."""

from typing import Any

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


def enforce(policy: Policy, name: str, arguments: dict[str, Any]) -> None:
    """Allow the call, or raise when `policy` gives a reason to block it.

    Raises:
        PermissionError: The policy forbids the call; the message is `Blocked by the security policy: <reason>`.
    """
    if reason := policy(name, arguments):
        raise PermissionError(f"Blocked by the security policy: {reason}")


def security_policy_pipeline(llm: PipelineElement, policy: Policy) -> AgentPipeline:
    """Build the baseline pipeline with every tool call checked against `policy`, the suite's policy."""

    def check_call(name: str, arguments: dict[str, Any]) -> None:
        enforce(policy, name, arguments)

    return AgentPipeline(
        [
            SystemMessage(DEFAULT_SYSTEM_MESSAGE),
            InitQuery(),
            llm,
            ToolsExecutionLoop([ToolsExecutor(check_call=check_call), llm]),
        ]
    )
