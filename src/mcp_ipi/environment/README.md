[EN](README.md) | [SI](README.si.md)

# environment

Builds a fresh, validated environment from YAML data and fills its injection vectors. It is generic: the environment
model and the data come from a suite.

| File             | What it holds                                                                  |
|------------------|--------------------------------------------------------------------------------|
| `yaml_loader.py` | `load_yaml`: safe YAML loading with `!include`, relative to the including file |
| `injection.py`   | `InjectionVector`, and finding and filling the `{@inject:id}` placeholders     |
| `loader.py`      | `load_environment`: YAML → placeholders filled → validated Pydantic model      |

## Example

An injection vector is a place in the data where attack text can go, marked by a placeholder:

```yaml
body: "Your invoice for May is 49.00 EUR. {@inject:email_invoice_body}"
```

```python
load_environment(path, WorkspaceEnvironment, {"email_invoice_body": "Thank you for choosing CloudHost."})
```

The text is the vector's benign default, or the attack text in a security run.
