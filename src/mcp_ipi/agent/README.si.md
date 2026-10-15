[EN](README.md) | [SI](README.si.md)

# agent

Agent: klici modela in cevovod, ki iz poziva naredi pogovor s klici orodij.

Cevovod je seznam elementov, ki se izvedejo po vrsti. Vsak element prejme stanje zagona
`(query, runtime, messages, extra_args)` in ga vrne, lahko spremenjenega.

| Datoteka      | Kaj vsebuje                                                                                                    |
|---------------|----------------------------------------------------------------------------------------------------------------|
| `pipeline.py` | `AgentPipeline` in elementi `SystemMessage`, `InitQuery`, `SelectTools`, `ToolsExecutor`, `ToolsExecutionLoop` |
| `llm.py`      | `LLM`: element, ki kliče model na OpenRouterju; edini modul, ki uvozi `openai`                                 |
| `messages.py` | Sporočila pogovora, navadni slovarji v obliki OpenAI chat-completions                                          |
| `usage.py`    | `Usage` (žetoni, klici modela, strošek) in `CountingLLM`, protokol elementa, ki jo šteje                       |

## Primer

Izhodiščni cevovod: model odgovori, in dokler ima njegovo zadnje sporočilo klice orodij, se ti izvedejo prek MCP in
model se pokliče znova, največ 15-krat.

```python
llm = LLM("openai/gpt-5.4-mini", provider="openai")
pipeline = AgentPipeline(
    [SystemMessage(DEFAULT_SYSTEM_MESSAGE), InitQuery(), llm, ToolsExecutionLoop([ToolsExecutor(), llm])]
)
_, _, messages, _ = await pipeline.query("When does my flight to Berlin leave?", runtime)
```

Obramba je ta cevovod z enim spremenjenim delom; glej [`../defenses/`](../defenses/README.si.md).
