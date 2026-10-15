[EN](README.md) | [SI](README.si.md)

# defenses

A defense is a function `<name>_pipeline(llm, policy)` that builds the agent pipeline with the defense in place.
Each one is the baseline pipeline with one part changed. Defenses do not depend on a suite; the suite's policy is
passed in.

| Defense           | Level   | What it changes                                                                         |
|-------------------|---------|-----------------------------------------------------------------------------------------|
| `none`            |         | Nothing: the baseline                                                                   |
| `spotlighting`    | content | Wraps every tool result in `<TOOL_RESULT>` tags that the system prompt explains         |
| `sanitizer`       | content | The agent's model removes instructions from every tool result before the agent reads it |
| `tool-filter`     | action  | The agent's model keeps only the tools the task needs, before any data is read          |
| `security-policy` | action  | Every tool call is checked against the suite's policy and blocked if it forbids it      |

`DEFENSES` holds each builder by its name.

## Example

```python
pipeline = DEFENSES["spotlighting"](llm, suite.security_policy)
```
