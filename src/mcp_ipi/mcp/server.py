"""Build one MCP server per domain, with its tools bound to the domain's component of an environment."""

import inspect
from collections.abc import Callable
from typing import Any

import yaml
from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, TextContent
from pydantic import BaseModel

from mcp_ipi.domains import Domain


def build_server(domain: Domain, environment: BaseModel) -> MCPServer:
    """Return an MCP server named after the domain that serves its tools on the environment, changing it in place."""
    server = MCPServer(domain.name)
    component = getattr(environment, domain.component)

    for tool in domain.tools:
        server.add_tool(_bind(tool, component), name=tool.__name__, description=tool.__doc__, structured_output=False)

    return server


def _bind(tool: Callable, component: BaseModel) -> Callable[..., str | CallToolResult]:
    """Wrap a tool so it takes only its own arguments and returns the text the model sees.

    The wrapper's signature is the tool's minus the component, so the server builds the input schema from it.
    A `str` result is returned as is, anything else as YAML; a raising tool gives `ErrorType: message` as an error.
    """

    def call(**arguments: Any) -> str | CallToolResult:
        try:
            result = tool(component, **arguments)
        except Exception as exc:
            text = f"{type(exc).__name__}: {exc}"
            return CallToolResult(content=[TextContent(type="text", text=text)], is_error=True)

        return result if isinstance(result, str) else _to_yaml(result)

    signature = inspect.signature(tool)
    call.__signature__ = signature.replace(
        parameters=list(signature.parameters.values())[1:], return_annotation=inspect.Signature.empty
    )
    return call


def _to_yaml(value: Any) -> str:
    """Dump a tool result to YAML, with Pydantic models (also inside lists) as JSON-compatible data."""
    data = [_to_data(item) for item in value] if isinstance(value, list) else _to_data(value)
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True).rstrip("\n")


def _to_data(value: Any) -> Any:
    return value.model_dump(mode="json") if isinstance(value, BaseModel) else value
