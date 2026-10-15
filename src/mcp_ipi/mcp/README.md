[EN](README.md) | [SI](README.si.md)

# mcp

Exposes the domains' tools over MCP and connects the agent to them.

| File         | What it holds                                                                                          |
|--------------|--------------------------------------------------------------------------------------------------------|
| `server.py`  | `build_server`: one MCP server per domain, its tools bound to the domain's component of an environment |
| `runtime.py` | `MCPRuntime`: one in-process client per server, one combined tool list, and `call_tool`                |

The servers change the environment in place, so after a run it is the post-environment that the tasks' checks read.
A tool's result reaches the model as text: a string as is, anything else as YAML, and an exception as
`ErrorType: message`.

## Example

```python
environment = suite.load_environment()
async with MCPRuntime.connect(suite.domains, environment) as runtime:
    runtime.tools  # every tool of every domain
    await runtime.call_tool("search_emails", {"query": "invoice"})
```
