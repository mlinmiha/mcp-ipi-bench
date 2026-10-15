"""The agent-side MCP runtime: one in-process client per domain server, one combined tool list."""

from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

from mcp import Client
from mcp.types import TextContent, Tool
from pydantic import BaseModel

from mcp_ipi.domains import Domain

from .server import build_server


class MCPRuntime:
    """Clients connected to one server per domain, over one environment that the servers change in place.

    Attributes:
        tools: The MCP tool definitions (name, description, input schema) the agent can call, from all servers,
            in domain order and, within a domain, in the domain's tool order.
        _clients: Tool name → the client connected to the server that owns that tool, used to route `call_tool`.
    """

    def __init__(self, tools: list[Tool], clients: dict[str, Client]) -> None:
        self.tools = tools
        self._clients = clients

    @classmethod
    @asynccontextmanager
    async def connect(cls, domains: tuple[Domain, ...], environment: BaseModel) -> AsyncGenerator["MCPRuntime"]:
        """Start one server per domain on the environment, connect to each in-process and list their tools.

        All clients and servers are closed on exit; the environment passed in is then the post-environment.
        An exception raised in the body leaves inside the SDK's (nested) `ExceptionGroup`.
        """
        async with AsyncExitStack() as stack:
            tools: list[Tool] = []
            clients: dict[str, Client] = {}

            for domain in domains:
                client = await stack.enter_async_context(Client(build_server(domain, environment)))
                domain_tools = (await client.list_tools()).tools
                tools.extend(domain_tools)
                clients.update({tool.name: client for tool in domain_tools})

            yield cls(tools, clients)

    def restrict_tools(self, names: list[str]) -> "MCPRuntime":
        """Return a copy with only the named tools, in this runtime's order; other names are unknown to it."""
        tools = [tool for tool in self.tools if tool.name in names]
        return MCPRuntime(tools, {tool.name: self._clients[tool.name] for tool in tools})

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Call a tool on the server that owns it and return the result's text, also for an error result.

        Raises:
            KeyError: No server has a tool with this name.
        """
        result = await self._clients[name].call_tool(name, arguments)
        return "".join(block.text for block in result.content if isinstance(block, TextContent))
