[EN](README.md) | [SI](README.si.md)

# mcp

Orodja domen ponudi prek MCP in agenta poveže z njimi.

| Datoteka     | Kaj vsebuje                                                                                    |
|--------------|------------------------------------------------------------------------------------------------|
| `server.py`  | `build_server`: en strežnik MCP na domeno, z orodji, vezanimi na komponento te domene v okolju |
| `runtime.py` | `MCPRuntime`: en odjemalec v istem procesu na strežnik, en skupen seznam orodij in `call_tool` |

Strežniki okolje spreminjajo na mestu, zato je to po zagonu končno okolje, ki ga berejo preverjanja nalog. Rezultat
orodja pride do modela kot besedilo: niz nespremenjen, vse drugo kot YAML, izjema pa kot `ErrorType: message`.

## Primer

```python
environment = suite.load_environment()
async with MCPRuntime.connect(suite.domains, environment) as runtime:
    runtime.tools  # vsa orodja vseh domen
    await runtime.call_tool("search_emails", {"query": "invoice"})
```
