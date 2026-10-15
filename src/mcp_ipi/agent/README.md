[EN](README.md) | [SI](README.si.md)

# agent

The agent: model calls and the pipeline that turns a prompt into a conversation with tool calls.

A pipeline is a list of elements run in order. Each element takes the run's state
`(query, runtime, messages, extra_args)` and returns it, possibly changed.

| File          | What it holds                                                                                                       |
|---------------|---------------------------------------------------------------------------------------------------------------------|
| `pipeline.py` | `AgentPipeline` and the elements `SystemMessage`, `InitQuery`, `SelectTools`, `ToolsExecutor`, `ToolsExecutionLoop` |
| `llm.py`      | `LLM`: the element that calls a model on OpenRouter; the only module that imports `openai`                          |
| `messages.py` | The chat messages, plain dicts in OpenAI chat-completions format                                                    |
| `usage.py`    | `Usage` (tokens, model calls, cost) and `CountingLLM`, the protocol of an element that counts it                    |

## Example

The baseline pipeline: the model answers, and while its last message has tool calls they are run over MCP and the
model is called again, at most 15 times.

```python
llm = LLM("openai/gpt-5.4-mini", provider="openai")
pipeline = AgentPipeline(
    [SystemMessage(DEFAULT_SYSTEM_MESSAGE), InitQuery(), llm, ToolsExecutionLoop([ToolsExecutor(), llm])]
)
_, _, messages, _ = await pipeline.query("When does my flight to Berlin leave?", runtime)
```

A defense is this pipeline with one part changed; see [`../defenses/`](../defenses/).
